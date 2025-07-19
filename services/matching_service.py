"""
Servicio para matching entre candidatos y vacantes usando IA
"""
import logging
from typing import Dict, Any, List, Tuple
from services.candidato_service import candidato_service
from services.vacante_service import vacante_service
from utils.ai_processor import cv_analyzer
import json
from config.settings import Config, MatchingConfig

# Importaciones para optimizaciones de velocidad
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)

class MatchingCache:
    """Caché simple para resultados de matching"""
    
    def __init__(self, ttl_seconds=300):  # 5 minutos TTL
        self.cache = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
    
    def _generate_key(self, candidato_id: str, score_minimo: float, limite: int) -> str:
        """Generar clave única para el caché"""
        key_data = f"{candidato_id}_{score_minimo}_{limite}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, candidato_id: str, score_minimo: float, limite: int) -> List[Dict[str, Any]]:
        """Obtener resultado del caché si existe y es válido"""
        with self.lock:
            key = self._generate_key(candidato_id, score_minimo, limite)
            if key in self.cache:
                result, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    logger.info(f"💾 Cache HIT para candidato {candidato_id} - ahorro de tiempo")
                    return result
                else:
                    # Caché expirado, eliminarlo
                    del self.cache[key]
            return None
    
    def set(self, candidato_id: str, score_minimo: float, limite: int, result: List[Dict[str, Any]]):
        """Guardar resultado en caché"""
        with self.lock:
            key = self._generate_key(candidato_id, score_minimo, limite)
            self.cache[key] = (result, time.time())
            logger.info(f"💾 Cache SET para candidato {candidato_id}")
    
    def clear(self):
        """Limpiar caché"""
        with self.lock:
            self.cache.clear()
            logger.info("💾 Cache limpiado")
    
    def cleanup_expired(self):
        """Limpiar entradas expiradas"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self.cache.items()
                if current_time - timestamp >= self.ttl
            ]
            for key in expired_keys:
                del self.cache[key]
            if expired_keys:
                logger.info(f"💾 Cache cleanup: {len(expired_keys)} entradas expiradas eliminadas")

# Instancia global del caché
_matching_cache = MatchingCache()

class MatchingConfig:
    """Configuración para bolsa de trabajo general - Todos los sectores"""
    
    def __init__(self):
        # Pesos configurables para TODOS los tipos de empleos
        self.pesos = {
            "experiencia_area": 0.40,          # 40% - Experiencia en el área específica
            "ubicacion_modalidad": 0.25,       # 25% - Ubicación y modalidad de trabajo
            "educacion_requisitos": 0.20,      # 20% - Educación y requisitos específicos
            "habilidades_especificas": 0.15    # 15% - Habilidades específicas del puesto
        }
        
        # Factores de ajuste según área laboral - MÁS ESPECÍFICOS
        self.areas_laborales = {
            "contabilidad": ["contador", "contabilidad", "finanzas", "nominas", "facturacion", "cobranza", "credito", "fiscal", "auditoria"],
            "ventas": ["vendedor", "ventas", "comercial", "atencion al cliente", "call center", "telemarketing", "representante", "comisiones"],
            "administracion": ["administracion", "recursos humanos", "secretarial", "asistente", "coordinador", "supervisor", "gerente"],
            "seguridad": ["seguridad", "vigilancia", "proteccion", "riesgos", "guardia", "monitoreo"],
            "higiene_seguridad": ["higiene", "industrial", "dc3", "iso", "salud ocupacional", "prevencion"],
            "operaciones": ["operario", "produccion", "manufactura", "almacen", "logistica", "packaging"],
            "servicios": ["limpieza", "mantenimiento", "jardineria", "cocina", "mesero", "recepcionista"],
            "tecnologia": ["programador", "desarrollador", "sistemas", "software", "developer", "python", "javascript", "react", "full stack", "backend", "frontend"],
            "salud": ["enfermeria", "medicina", "cuidados", "terapia", "farmacia", "medico", "doctor"],
            "educacion": ["docente", "profesor", "instructor", "capacitacion", "entrenamiento", "maestro"],
            "eventos": ["eventos", "coordinacion", "organizacion", "bodas", "fiestas", "protocolo"],
            "marketing": ["marketing", "publicidad", "digital", "social media", "comunicacion", "branding"],
            "logistica": ["logistica", "transporte", "distribucion", "cadena", "supply", "almacen", "inventarios"]
        }
        
        # Scoring básico y real - MÁS ESTRICTO
        self.scoring_basico = {
            "match_area_exacta": 10,           # +10 pts por área exacta (reducido de 20)
            "experiencia_suficiente": 10,      # +10 pts por experiencia suficiente (reducido de 25)
            "ubicacion_compatible": 10,        # +10 pts por ubicación compatible (reducido de 20)
            "educacion_cumple": 5,             # +5 pts por educación que cumple (reducido de 15)
            "disponibilidad_compatible": 5     # +5 pts por disponibilidad compatible (reducido de 15)
        }
        
        # Factores de ajuste según demanda del mercado
        self.ajustes_mercado = {
            "alta_demanda_skills": ["React", "Python", "AWS", "Kubernetes", "Machine Learning"],
            "bonus_skills_demandadas": 5,      # +5 puntos por skill en alta demanda
            "penalty_skills_obsoletas": -3,    # -3 puntos por skills obsoletas
            "skills_obsoletas": ["jQuery", "Flash", "Silverlight"]
        }
        
        # Configuración de scoring dinámico
        self.scoring_dinamico = {
            "boost_ubicacion_remoto": 1.1,     # 10% boost para trabajos remotos
            "boost_mismo_pais": 1.05,          # 5% boost para mismo país
            "penalty_experiencia_insuficiente": 0.85,  # 15% penalty por experiencia insuficiente
            "bonus_over_qualified": 1.02       # 2% bonus por estar sobre-calificado (controlado)
        }

class MatchingService:
    """Servicio para matching inteligente candidato-vacante"""
    
    def __init__(self):
        self.candidato_service = candidato_service
        self.vacante_service = vacante_service
        self.ai_processor = cv_analyzer
        self.config = MatchingConfig  # Configuración avanzada
    
    def find_matches_for_candidato(self, candidato: Dict[str, Any], limite: int = 10, score_minimo: float = None, filtros_adicionales: Dict = None) -> List[Dict[str, Any]]:
        """Encontrar vacantes compatibles para un candidato - VERSIÓN OPTIMIZADA"""
        if score_minimo is None:
            score_minimo = MatchingConfig.score_minimo / 100  # Convertir de porcentaje a decimal
            
        candidato_id = candidato.get('id', candidato.get('usuario_id', 'unknown'))
        
        try:
            # 1. 💾 VERIFICAR CACHÉ PRIMERO
            cached_result = _matching_cache.get(candidato_id, score_minimo, limite)
            if cached_result is not None:
                return cached_result
            
            logger.info(f"🚀 Buscando matches OPTIMIZADO para candidato {candidato_id} con score mínimo {score_minimo*100}%")
            start_time = time.time()
            
            # 2. 🔍 OBTENER VACANTES Y APLICAR FILTROS TEMPRANOS
            vacantes = vacante_service.get_all_vacantes()
            logger.info(f"📊 Total vacantes disponibles: {len(vacantes)}")
            
            # 3. 🚀 FILTRO RÁPIDO PRE-PROCESAMIENTO
            vacantes_filtradas = self._filtro_rapido_compatibilidad(candidato, vacantes, score_minimo)
            logger.info(f"⚡ Vacantes tras filtro rápido: {len(vacantes_filtradas)}")
            
            # 4. 🔄 PROCESAMIENTO PARALELO
            matches = self._procesar_vacantes_paralelo(candidato, vacantes_filtradas, score_minimo, limite)
            
            # 5. 📊 ORDENAR Y LIMITAR RESULTADOS
            matches.sort(key=lambda x: x['score'], reverse=True)
            final_matches = matches[:limite]
            
            # 6. 💾 GUARDAR EN CACHÉ
            _matching_cache.set(candidato_id, score_minimo, limite, final_matches)
            
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Matching completado en {elapsed_time:.2f}s - {len(final_matches)} matches encontrados")
            
            return final_matches
            
        except Exception as e:
            logger.error(f"❌ Error en find_matches_for_candidato optimizado: {e}")
            return []
    
    def _filtro_rapido_compatibilidad(self, candidato: Dict[str, Any], vacantes: List[Dict[str, Any]], score_minimo: float) -> List[Dict[str, Any]]:
        """Filtro rápido para descartar vacantes obviamente incompatibles"""
        vacantes_compatibles = []
        
        # Extraer información básica del candidato una sola vez
        candidato_ubicacion = (candidato.get('ciudad') or '').lower()
        candidato_pais = (candidato.get('pais') or '').lower()
        candidato_area = self._detectar_area_candidato(candidato)
        candidato_habilidades = self._extraer_habilidades_candidato(candidato)
        candidato_habilidades_lower = [h.lower() for h in candidato_habilidades if h]
        
        for vacante in vacantes:
            # Filtro 1: Verificar área laboral básica
            vacante_area = self._detectar_area_vacante(vacante)
            if not self._areas_relacionadas(candidato_area, vacante_area) and candidato_area != vacante_area:
                continue
            
            # Filtro 2: Verificar ubicación básica (solo para presencial)
            modalidad = (vacante.get('modalidad') or '').lower()
            if 'presencial' in modalidad:
                vacante_ubicacion = (vacante.get('ubicacion') or '').lower()
                if candidato_ubicacion and vacante_ubicacion:
                    if candidato_ubicacion not in vacante_ubicacion and vacante_ubicacion not in candidato_ubicacion:
                        # Verificar si al menos están en el mismo país
                        if candidato_pais not in vacante_ubicacion and vacante_ubicacion not in candidato_pais:
                            continue
            
            # Filtro 3: Verificar al menos una habilidad coincidente
            descripcion = (vacante.get('descripcion') or '') + ' ' + (vacante.get('titulo') or '')
            habilidades_vacante = self._extraer_habilidades_descripcion(descripcion)
            if habilidades_vacante and candidato_habilidades_lower:
                tiene_habilidad = any(
                    any(hab_v.lower() in hab_c or hab_c in hab_v.lower() 
                        for hab_c in candidato_habilidades_lower)
                    for hab_v in habilidades_vacante if hab_v
                )
                if not tiene_habilidad:
                    continue
            
            # Si pasa todos los filtros, es candidata para procesamiento profundo
            vacantes_compatibles.append(vacante)
        
        return vacantes_compatibles
    
    def _procesar_vacantes_paralelo(self, candidato: Dict[str, Any], vacantes: List[Dict[str, Any]], score_minimo: float, limite: int) -> List[Dict[str, Any]]:
        """Procesar vacantes en paralelo para mejor rendimiento"""
        matches = []
        
        # Configurar el pool de threads
        max_workers = min(len(vacantes), 8)  # Máximo 8 threads
        
        def procesar_vacante(vacante):
            """Función para procesar una vacante individual"""
            try:
                # Calcular score y compatibilidad
                habilidades_match = self.calcular_habilidades_match(candidato, vacante)
                match_result = self.calcular_score_match_rapido(candidato, vacante, habilidades_match)
                
                score = match_result[0] if isinstance(match_result, tuple) else match_result.get('score', 0)
                
                if match_result and score >= (score_minimo * 100):
                    return {
                        'vacante': vacante,
                        'score': score,
                        'analisis': match_result[1] if isinstance(match_result, tuple) else match_result,
                        'habilidades_match': habilidades_match
                    }
                return None
            except Exception as e:
                logger.warning(f"⚠️ Error procesando vacante {vacante.get('id', 'N/A')}: {e}")
                return None
        
        # Ejecutar en paralelo
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_vacante = {executor.submit(procesar_vacante, vacante): vacante for vacante in vacantes}
            
            for future in as_completed(future_to_vacante):
                result = future.result()
                if result is not None:
                    matches.append(result)
                    # Optimización: detener si tenemos suficientes matches
                    if len(matches) >= limite * 2:  # 2x para tener margen
                        break
        
        return matches
    
    def calcular_score_match_rapido(self, candidato, vacante, habilidades_match):
        """Versión rápida del cálculo de score con timeout para OpenAI"""
        try:
            logger.info(f"⚡ Matching rápido para candidato {candidato.get('id', 'N/A')}")
            
            # Preparar datos una sola vez
            candidato_text = self._preparar_perfil_candidato_detallado(candidato)
            vacante_text = self._preparar_descripcion_vacante_detallada(vacante)
            
            # Intentar OpenAI con timeout reducido
            try:
                score_ia, analisis_ia = self._analizar_match_con_openai_rapido(candidato_text, vacante_text, habilidades_match, candidato, vacante)
                logger.info(f"✅ OpenAI Score rápido: {score_ia}%")
                return score_ia, analisis_ia
            except Exception as e:
                logger.warning(f"⚠️ OpenAI timeout/error, usando fallback: {e}")
                # Fallback rápido
                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
        except Exception as e:
            logger.error(f"❌ Error en calcular_score_match_rapido: {e}")
            return 35, {"error": str(e), "fallback": True}
    
    def find_matches_for_vacante(self, vacante: Dict[str, Any], limite: int = 10, score_minimo: float = None) -> List[Dict[str, Any]]:
        """Encontrar candidatos compatibles para una vacante"""
        if score_minimo is None:
            score_minimo = MatchingConfig.score_minimo / 100  # Convertir de porcentaje a decimal
            
        try:
            logger.info(f"Buscando candidatos para vacante {vacante.get('id', 'N/A')} con score mínimo {score_minimo*100}%")
            
            # Obtener todos los candidatos
            candidatos = candidato_service.get_all_candidatos()
            
            matches = []
            for candidato in candidatos:
                # Calcular score y compatibilidad
                habilidades_match = self.calcular_habilidades_match(candidato, vacante)
                match_result = self.calcular_score_match(candidato, vacante, habilidades_match)
                
                score = match_result[0] if isinstance(match_result, tuple) else match_result.get('score', 0)
                
                if match_result and score >= (score_minimo * 100):
                    match_info = {
                        'candidato': candidato,
                        'score': score,
                        'analisis': match_result[1] if isinstance(match_result, tuple) else match_result,
                        'habilidades_match': habilidades_match
                    }
                    matches.append(match_info)
            
            # Ordenar por score descendente
            matches.sort(key=lambda x: x['score'], reverse=True)
            return matches[:limite]
            
        except Exception as e:
            logger.error(f"Error en find_matches_for_vacante: {e}")
            return []
    
    def _calculate_match_score(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Calcular score de match REAL para bolsa de trabajo general"""
        try:
            # Usar el nuevo algoritmo más estricto
            skills_analysis = self._analizar_habilidades_real(candidato, vacante)
            habilidades_match = {
                "coincidentes": skills_analysis.get('habilidades_encontradas', []),
                "faltantes": skills_analysis.get('habilidades_vacante_detectadas', [])
            }
            
            # Calcular score con el nuevo algoritmo más estricto
            score_final, detalles = self.calcular_score_match(candidato, vacante, habilidades_match)
            
            # Análisis adicional para el resultado
            ubicacion_analysis = self._analizar_ubicacion_real(candidato, vacante)
            educacion_analysis = self._analizar_educacion_requisitos(candidato, vacante)
            area_analysis = self._analizar_area_laboral(candidato, vacante)
            
            # Generar análisis comprensible usando el nuevo algoritmo
            coincidentes = habilidades_match.get('coincidentes', [])
            habilidades_vacante = skills_analysis.get('habilidades_vacante_detectadas', [])
            
            # Calcular faltantes basado en las habilidades requeridas vs las que tiene
            faltantes = []
            for hab_vacante in habilidades_vacante:
                if not any(hab_vacante.lower() in coin.lower() for coin in coincidentes):
                    faltantes.append(hab_vacante)
            
            # Análisis específico para el sector con nueva detección
            sector_candidato = self.detectar_area_laboral(candidato)
            sector_vacante = self.detectar_area_laboral_vacante(vacante)
            
            return {
                "vacante": {
                    "id": vacante.get('id', ''),
                    "titulo": vacante.get('titulo', ''),
                    "empresa": vacante.get('empresa', vacante.get('empresa_nombre', '')),
                    "ubicacion": vacante.get('ubicacion', ''),
                    "modalidad": vacante.get('modalidad', vacante.get('tipo_empleo', 'No especificada')),
                    "salario_min": vacante.get('salario_min', int(float(vacante.get('salario', 0)) * 0.85) if vacante.get('salario') else 0),
                    "salario_max": vacante.get('salario_max', int(float(vacante.get('salario', 0)) * 1.15) if vacante.get('salario') else 0),
                    "nivel_experiencia": vacante.get('nivel_experiencia', ''),
                    "descripcion": vacante.get('descripcion', ''),
                    "requisitos": educacion_analysis.get('requisitos_detectados', [])
                },
                "score": score_final,
                "skills_match": {
                    "coincidentes": coincidentes,
                    "faltantes": faltantes,
                    "relacionadas": [],  # Sin datos ficticios
                    "transferibles": []  # Sin datos ficticios
                },
                "ubicacion_compatible": ubicacion_analysis.get('es_compatible', False),
                "requisitos_cumplidos": educacion_analysis.get('cumplidos', 0),
                "fortalezas": self._generar_fortalezas_generales(area_analysis, ubicacion_analysis, educacion_analysis, skills_analysis),
                "debilidades": self._generar_debilidades_generales(area_analysis, ubicacion_analysis, educacion_analysis, skills_analysis),
                "recomendacion": self._generar_recomendacion_general(score_final, sector_candidato, sector_vacante),
                "analisis_detallado": {
                    "area_laboral": f"Candidato: {sector_candidato} | Vacante: {sector_vacante}",
                    "ubicacion": ubicacion_analysis.get('analisis', 'Sin análisis de ubicación'),
                    "experiencia": f"Candidato tiene {len(candidato.get('experiencias', []))} experiencias registradas",
                    "educacion": educacion_analysis.get('analisis', 'Sin análisis educativo'),
                    "habilidades_especificas": skills_analysis.get('analisis', 'Sin habilidades específicas')
                }
            }
            
        except Exception as e:
            logger.error(f"Error en cálculo de match general: {e}")
            return {
                "vacante": {
                    "id": vacante.get('id', '') if vacante else '',
                    "titulo": vacante.get('titulo', '') if vacante else 'Error',
                    "empresa": vacante.get('empresa', vacante.get('empresa_nombre', '')) if vacante else '',
                    "ubicacion": vacante.get('ubicacion', '') if vacante else '',
                    "modalidad": vacante.get('modalidad', vacante.get('tipo_empleo', '')) if vacante else '',
                    "salario_min": 0,
                    "salario_max": 0,
                    "nivel_experiencia": '',
                    "descripcion": '',
                    "requisitos": []
                },
                "score": 0,
                "skills_match": {"coincidentes": [], "faltantes": [], "relacionadas": [], "transferibles": []},
                "ubicacion_compatible": False,
                "requisitos_cumplidos": 0,
                "fortalezas": [],
                "debilidades": ["Error en el análisis"],
                "recomendacion": "No se pudo evaluar este candidato",
                "analisis_detallado": {"error": str(e)}
            }
    
    def _contar_requisitos_cumplidos(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> int:
        """Contar requisitos cumplidos de forma inteligente"""
        req_analysis = self._analizar_requisitos(candidato, vacante)
        return req_analysis.get('cumplidos', 0)
    
    def _combinar_fortalezas(self, skills_analysis: Dict, cultural_analysis: Dict, potencial_analysis: Dict, exp_analysis: Dict) -> List[str]:
        """Combinar fortalezas de todos los análisis"""
        fortalezas = []
        
        # Fortalezas técnicas
        if skills_analysis.get('score_habilidades', 0) >= 70:
            fortalezas.append(f"Excelente match técnico ({skills_analysis.get('score_habilidades')}%)")
        
        # Fortalezas culturales
        if cultural_analysis.get('score_cultural', 0) >= 70:
            fortalezas.extend(cultural_analysis.get('fortalezas_culturales', [])[:2])
        
        # Fortalezas de experiencia
        if exp_analysis.get('fortaleza'):
            fortalezas.append(exp_analysis['fortaleza'])
        
        # Fortalezas de potencial
        if potencial_analysis.get('score_potencial', 0) >= 70:
            fortalezas.append("Alto potencial de crecimiento")
        
        return fortalezas[:5]  # Top 5
    
    def _combinar_debilidades(self, skills_analysis: Dict, cultural_analysis: Dict, exp_analysis: Dict) -> List[str]:
        """Combinar debilidades de todos los análisis"""
        debilidades = []
        
        # Debilidades técnicas
        if skills_analysis.get('faltantes'):
            debilidades.append(f"Habilidades faltantes: {', '.join(skills_analysis['faltantes'][:3])}")
        
        # Debilidades culturales
        if cultural_analysis.get('areas_atencion'):
            debilidades.extend(cultural_analysis['areas_atencion'][:2])
        
        # Debilidades de experiencia
        if exp_analysis.get('debilidad'):
            debilidades.append(exp_analysis['debilidad'])
        
        return debilidades[:3]  # Top 3
    
    def _generar_recomendacion_avanzada(self, score_final: float, skills_analysis: Dict, cultural_analysis: Dict, potencial_analysis: Dict) -> str:
        """Generar recomendación integral basada en todos los análisis"""
        
        nivel_skills = skills_analysis.get('score_habilidades', 0)
        nivel_cultural = cultural_analysis.get('score_cultural', 50)
        nivel_potencial = potencial_analysis.get('score_potencial', 50)
        
        if score_final >= 85:
            return f"🌟 CANDIDATO EXCEPCIONAL ({score_final:.0f}%): Match técnico {nivel_skills}%, fit cultural {nivel_cultural}%, alto potencial {nivel_potencial}%. Proceder inmediatamente a entrevista final."
        
        elif score_final >= 70:
            return f"✅ CANDIDATO RECOMENDADO ({score_final:.0f}%): Buen equilibrio entre habilidades técnicas ({nivel_skills}%) y compatibilidad cultural ({nivel_cultural}%). Continuar proceso de selección."
        
        elif score_final >= 55:
            return f"⚡ CANDIDATO CON POTENCIAL ({score_final:.0f}%): Areas fuertes identificadas. Considerar entrevista para evaluar fit específico y posibilidades de capacitación."
        
        else:
            return f"⚠️ MATCH LIMITADO ({score_final:.0f}%): Aunque tiene algunas fortalezas, requiere evaluación cuidadosa de gaps significativos antes de continuar."
    
    def _calcular_ajustes_mercado(self, skills_analysis: Dict, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> float:
        """Calcular ajustes basados en tendencias del mercado laboral"""
        ajuste_total = 0
        
        # Obtener habilidades del candidato
        skills_candidato = skills_analysis.get('coincidentes', []) + skills_analysis.get('relacionadas', [])
        
        # Bonus por habilidades en alta demanda
        skills_demandadas = set(skills_candidato).intersection(set(self.config.ajustes_mercado["alta_demanda_skills"]))
        ajuste_total += len(skills_demandadas) * self.config.ajustes_mercado["bonus_skills_demandadas"]
        
        # Penalty por habilidades obsoletas
        skills_obsoletas = set(skills_candidato).intersection(set(self.config.ajustes_mercado["skills_obsoletas"]))
        ajuste_total += len(skills_obsoletas) * self.config.ajustes_mercado["penalty_skills_obsoletas"]
        
        # Ajuste por especialización en tecnologías emergentes
        emerging_tech = ["React Native", "Kubernetes", "GraphQL", "TypeScript", "Next.js", "Vue 3"]
        skills_emergentes = set(skills_candidato).intersection(set(emerging_tech))
        ajuste_total += len(skills_emergentes) * 3  # +3 puntos por tech emergente
        
        return min(ajuste_total, 15)  # Máximo 15 puntos de ajuste
    
    def _aplicar_scoring_dinamico(self, score_base: float, candidato: Dict[str, Any], vacante: Dict[str, Any], ubicacion_analysis: Dict) -> float:
        """Aplicar factores de scoring dinámico"""
        score_final = score_base
        
        # Boost para trabajos remotos (más flexibilidad)
        modalidad = vacante.get('modalidad', vacante.get('tipo_empleo', '')).lower()
        if 'remoto' in modalidad:
            score_final *= self.config.scoring_dinamico["boost_ubicacion_remoto"]
        
        # Boost para candidatos del mismo país
        candidato_pais = candidato.get('pais', '').lower()
        vacante_ubicacion = vacante.get('ubicacion', '').lower()
        if candidato_pais and candidato_pais in vacante_ubicacion:
            score_final *= self.config.scoring_dinamico["boost_mismo_pais"]
        
        # Penalty por experiencia insuficiente
        años_exp = len(candidato.get('experiencias', []))
        nivel_req = vacante.get('nivel_experiencia', '').lower()
        
        if ('senior' in nivel_req and años_exp < 3) or ('mid' in nivel_req and años_exp < 2):
            score_final *= self.config.scoring_dinamico["penalty_experiencia_insuficiente"]
        
        # Bonus controlado por estar sobre-calificado (evitar brain drain)
        if 'junior' in nivel_req and años_exp > 5:
            score_final *= self.config.scoring_dinamico["bonus_over_qualified"]
        
        return min(score_final, 100)  # Cap en 100
    
    def generar_reporte_mercado(self, candidato: Dict[str, Any]) -> Dict[str, Any]:
        """Generar reporte de análisis de mercado para el candidato"""
        skills_candidato = []
        
        # Extraer skills del candidato
        for exp in candidato.get('experiencias', []):
            descripcion = exp.get('descripcion', '').lower()
            for skill in self.config.ajustes_mercado["alta_demanda_skills"]:
                if skill.lower() in descripcion:
                    skills_candidato.append(skill)
        
        # Análisis de posicionamiento en el mercado
        skills_demandadas = set(skills_candidato).intersection(set(self.config.ajustes_mercado["alta_demanda_skills"]))
        skills_obsoletas = set(skills_candidato).intersection(set(self.config.ajustes_mercado["skills_obsoletas"]))
        
        # Calcular score de empleabilidad
        score_empleabilidad = len(skills_demandadas) * 15 - len(skills_obsoletas) * 10
        score_empleabilidad = max(0, min(score_empleabilidad, 100))
        
        return {
            "score_empleabilidad": score_empleabilidad,
            "skills_alta_demanda": list(skills_demandadas),
            "skills_obsoletas": list(skills_obsoletas),
            "recomendaciones_mejora": self._generar_recomendaciones_mercado(skills_demandadas, skills_obsoletas),
            "tendencias_sector": {
                "tecnologias_crecientes": ["React", "Python", "AWS", "Kubernetes"],
                "sectores_demanda": ["FinTech", "HealthTech", "E-commerce", "AI/ML"],
                "modalidades_preferidas": ["Remoto", "Híbrido"]
            }
        }
    
    def _generar_recomendaciones_mercado(self, skills_demandadas: set, skills_obsoletas: set) -> List[str]:
        """Generar recomendaciones específicas basadas en análisis de mercado"""
        recomendaciones = []
        
        if len(skills_demandadas) >= 3:
            recomendaciones.append("Perfil muy competitivo en el mercado actual")
        elif len(skills_demandadas) >= 1:
            recomendaciones.append("Buen potencial, considera expandir skills en tecnologías demandadas")
        else:
            recomendaciones.append("Recomendable actualizar stack tecnológico hacia skills en demanda")
        
        if skills_obsoletas:
            recomendaciones.append(f"Considera migrar de {', '.join(skills_obsoletas)} hacia tecnologías modernas")
        
        recomendaciones.append("Enfócate en certificaciones cloud (AWS, Azure) para mayor empleabilidad")
        recomendaciones.append("Desarrolla skills en metodologías ágiles y DevOps")
        
        return recomendaciones
    
    def _create_matching_prompt(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> str:
        """Crear prompt para matching con IA"""
        
        # Preparar información detallada del candidato
        candidato_info = {
            "nombre": candidato.get('nombre', ''),
            "titulo_profesional": candidato.get('titulo_profesional', ''),
            "ciudad": candidato.get('ciudad', ''),
            "pais": candidato.get('pais', ''),
            "resumen_profesional": candidato.get('resumen_profesional', ''),
            "experiencias": candidato.get('experiencias', []),
            "educaciones": candidato.get('educaciones', []),
            "certificaciones": candidato.get('certificaciones', []),
            "idiomas": candidato.get('idiomas', [])
        }
        
        # Calcular años de experiencia total
        años_experiencia = len(candidato.get('experiencias', []))
        
        return f"""
        Analiza EXHAUSTIVAMENTE la compatibilidad entre este candidato y esta vacante considerando TODOS los aspectos:

        CANDIDATO COMPLETO:
        {json.dumps(candidato_info, indent=2, ensure_ascii=False)}
        
        Años de experiencia total: {años_experiencia}
        
        VACANTE COMPLETA:
        Título: {vacante.get('titulo', 'No especificado')}
        Empresa: {vacante.get('empresa', vacante.get('empresa_nombre', 'No especificada'))}
        Ubicación: {vacante.get('ubicacion', 'No especificada')}
        Modalidad: {vacante.get('modalidad', vacante.get('tipo_empleo', 'No especificada'))}
        Nivel requerido: {vacante.get('nivel_experiencia', 'No especificado')}
        Salario: €{vacante.get('salario_min', 0)} - €{vacante.get('salario_max', 0)}
        
        DESCRIPCIÓN DETALLADA:
        {vacante.get('descripcion', 'Sin descripción disponible')}
        
        REQUISITOS ESPECÍFICOS:
        {chr(10).join('- ' + req for req in vacante.get('requisitos', []))}
        
        HABILIDADES TÉCNICAS REQUERIDAS:
        {', '.join(vacante.get('habilidades_requeridas', []))}
        
        INSTRUCCIONES DE ANÁLISIS:
        1. UBICACIÓN: Compara la ubicación del candidato con la vacante. Considera compatibilidad geográfica y modalidad.
        2. REQUISITOS: Verifica si el candidato cumple cada requisito específico mencionado.
        3. HABILIDADES: Analiza coincidencias exactas y relacionadas entre habilidades del candidato y requeridas.
        4. EXPERIENCIA: Evalúa si el nivel de experiencia coincide con lo solicitado.
        5. DESCRIPCIÓN: Haz matching semántico entre el perfil del candidato y la descripción del puesto.
        6. EDUCACIÓN: Considera si la formación es relevante para el puesto.
        7. IDIOMAS: Evalúa si los idiomas del candidato son adecuados.
        
        Responde en formato JSON con esta estructura EXACTA:
        {{
            "score": número_del_0_al_100,
            "match_percentage": número_del_0_al_100,
            "ubicacion_compatible": true/false,
            "requisitos_cumplidos": número_de_0_a_{len(vacante['requisitos'])},
            "fortalezas": ["fortaleza1", "fortaleza2", "fortaleza3"],
            "debilidades": ["debilidad1", "debilidad2"],
            "recomendacion": "recomendacion_detallada_de_2_3_lineas",
            "skills_match": {{
                "coincidentes": ["skill1", "skill2"],
                "faltantes": ["skill3", "skill4"],
                "relacionadas": ["skill5", "skill6"]
            }},
            "analisis_detallado": {{
                "ubicacion": "analisis_ubicacion",
                "experiencia": "analisis_experiencia", 
                "educacion": "analisis_educacion",
                "fit_cultural": "analisis_cultural"
            }}
        }}
        
        Responde SOLO con el JSON, sin texto adicional.
        """
    
    def _parse_matching_response(self, response: str, vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Parsear respuesta de matching con IA"""
        try:
            # Limpiar respuesta
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            match_data = json.loads(clean_response)
            
            # Agregar información completa de la vacante y análisis
            return {
                "vacante": {
                    "id": vacante.get('id', ''),
                    "titulo": vacante.get('titulo', ''),
                    "empresa": vacante.get('empresa', vacante.get('empresa_nombre', '')),
                    "ubicacion": vacante.get('ubicacion', ''),
                    "modalidad": vacante.get('modalidad', vacante.get('tipo_empleo', 'No especificada')),
                    "salario_min": vacante.get('salario_min', 0),
                    "salario_max": vacante.get('salario_max', 0),
                    "nivel_experiencia": vacante.get('nivel_experiencia', ''),
                    "descripcion": vacante.get('descripcion', ''),
                    "requisitos": vacante.get('requisitos', [])
                },
                "score": match_data.get('score', 0),
                "match_percentage": match_data.get('match_percentage', 0),
                "ubicacion_compatible": match_data.get('ubicacion_compatible', False),
                "requisitos_cumplidos": match_data.get('requisitos_cumplidos', 0),
                "fortalezas": match_data.get('fortalezas', []),
                "debilidades": match_data.get('debilidades', []),
                "recomendacion": match_data.get('recomendacion', ''),
                "skills_match": match_data.get('skills_match', {
                    "coincidentes": [],
                    "faltantes": [],
                    "relacionadas": []
                }),
                "analisis_detallado": match_data.get('analisis_detallado', {
                    "ubicacion": "No analizado",
                    "experiencia": "No analizado",
                    "educacion": "No analizado",
                    "fit_cultural": "No analizado"
                })
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta de matching: {e}")
            return self._basic_match_score_result(vacante, 50)
    
    def _basic_match_score(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Matching básico mejorado sin IA - análisis completo"""
        
        score = 0
        fortalezas = []
        debilidades = []
        
        # 1. ANÁLISIS DE UBICACIÓN (15% del score)
        ubicacion_compatible = self._analizar_ubicacion(candidato, vacante)
        if ubicacion_compatible['compatible']:
            score += 15
            fortalezas.append(f"Ubicación compatible: {ubicacion_compatible['razon']}")
        else:
            debilidades.append(f"Ubicación: {ubicacion_compatible['razon']}")
        
        # 2. ANÁLISIS DE HABILIDADES (40% del score)
        skills_analysis = self._analizar_habilidades(candidato, vacante)
        habilidades_requeridas = vacante.get('habilidades_requeridas', [])
        skills_score = (len(skills_analysis['coincidentes']) / len(habilidades_requeridas)) * 40 if habilidades_requeridas else 0
        score += skills_score
        
        if skills_analysis['coincidentes']:
            fortalezas.append(f"Habilidades técnicas: {', '.join(skills_analysis['coincidentes'][:3])}")
        if skills_analysis['faltantes']:
            debilidades.append(f"Faltantes: {', '.join(skills_analysis['faltantes'][:3])}")
        
        # 3. ANÁLISIS DE EXPERIENCIA (25% del score)
        exp_analysis = self._analizar_experiencia(candidato, vacante)
        score += exp_analysis['score']
        if exp_analysis['fortaleza']:
            fortalezas.append(exp_analysis['fortaleza'])
        if exp_analysis['debilidad']:
            debilidades.append(exp_analysis['debilidad'])
        
        # 4. ANÁLISIS DE REQUISITOS (15% del score)
        req_analysis = self._analizar_requisitos(candidato, vacante)
        score += req_analysis['score']
        if req_analysis['cumplidos'] > 0:
            fortalezas.append(f"Cumple {req_analysis['cumplidos']}/{len(vacante['requisitos'])} requisitos")
        
        # 5. ANÁLISIS DE EDUCACIÓN (5% del score)
        if candidato.get('educaciones'):
            score += 5
            fortalezas.append("Tiene formación académica")
        else:
            debilidades.append("Sin información de educación formal")
        
        # Generar recomendación
        recomendacion = self._generar_recomendacion_basica(score, fortalezas, debilidades)
        
        return {
            "vacante": {
                "id": vacante.get('id', ''),
                "titulo": vacante.get('titulo', ''),
                "empresa": vacante.get('empresa', vacante.get('empresa_nombre', '')),
                "ubicacion": vacante.get('ubicacion', ''),
                "modalidad": vacante.get('modalidad', vacante.get('tipo_empleo', 'No especificada')),
                "salario_min": vacante.get('salario_min', 0),
                "salario_max": vacante.get('salario_max', 0),
                "nivel_experiencia": vacante.get('nivel_experiencia', ''),
                "descripcion": vacante.get('descripcion', ''),
                "requisitos": vacante.get('requisitos', [])
            },
            "score": min(int(score), 100),
            "match_percentage": min(int(score), 100),
            "ubicacion_compatible": ubicacion_compatible['compatible'],
            "requisitos_cumplidos": req_analysis['cumplidos'],
            "fortalezas": fortalezas[:5],  # Top 5
            "debilidades": debilidades[:3],  # Top 3
            "recomendacion": recomendacion,
            "skills_match": skills_analysis,
            "analisis_detallado": {
                "ubicacion": ubicacion_compatible['analisis'],
                "experiencia": exp_analysis['analisis'],
                "educacion": "Análisis básico de formación académica",
                "fit_cultural": "Requiere evaluación detallada"
            }
        }
    
    def _analizar_ubicacion(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar compatibilidad de ubicación"""
        candidato_ciudad = candidato.get('ciudad', '').lower()
        candidato_pais = candidato.get('pais', '').lower()
        vacante_ubicacion = vacante.get('ubicacion', '').lower()
        modalidad = vacante.get('modalidad', vacante.get('tipo_empleo', '')).lower()
        
        # Si es remoto, siempre compatible
        if 'remoto' in modalidad:
            return {
                'compatible': True,
                'razon': 'Modalidad remota',
                'analisis': 'Trabajo remoto - ubicación no es limitante'
            }
        
        # Verificar si están en la misma ciudad
        if candidato_ciudad and candidato_ciudad in vacante_ubicacion:
            return {
                'compatible': True,
                'razon': 'Misma ciudad',
                'analisis': f'Candidato y vacante en {candidato_ciudad}'
            }
        
        # Verificar si están en el mismo país
        if candidato_pais and candidato_pais in vacante_ubicacion:
            return {
                'compatible': True,
                'razon': 'Mismo país',
                'analisis': f'Ambos en {candidato_pais} - posible reubicación'
            }
        
        # Si es híbrido, menor compatibilidad
        if 'híbrido' in modalidad or 'hibrido' in modalidad:
            return {
                'compatible': False,
                'razon': 'Modalidad híbrida requiere presencia local',
                'analisis': 'Modalidad híbrida puede requerir reubicación'
            }
        
        return {
            'compatible': False,
            'razon': 'Ubicación incompatible',
            'analisis': 'Diferentes ubicaciones - modalidad presencial'
        }
    
    def _analizar_habilidades(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar habilidades del candidato vs requeridas"""
        candidato_skills = set()
        
        # Extraer habilidades desde experiencias
        habilidades_requeridas = vacante.get('habilidades_requeridas', [])
        for exp in candidato.get('experiencias', []):
            descripcion = exp.get('descripcion', '').lower()
            cargo = exp.get('cargo', '').lower()
            for skill in habilidades_requeridas:
                if skill.lower() in descripcion or skill.lower() in cargo:
                    candidato_skills.add(skill)
        
        # Extraer desde título profesional
        titulo = candidato.get('titulo_profesional', '').lower()
        for skill in habilidades_requeridas:
            if skill.lower() in titulo:
                candidato_skills.add(skill)
        
        required_skills = set(habilidades_requeridas)
        coincidentes = list(candidato_skills.intersection(required_skills))
        faltantes = list(required_skills - candidato_skills)
        
        return {
            'coincidentes': coincidentes,
            'faltantes': faltantes,
            'relacionadas': []  # Para el matching básico no calculamos relacionadas
        }
    
    def _analizar_experiencia(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar experiencia del candidato"""
        experiencias = candidato.get('experiencias', [])
        años_experiencia = len(experiencias)
        nivel_requerido = vacante.get('nivel_experiencia', '').lower()
        
        # Calcular score basado en nivel requerido
        if 'junior' in nivel_requerido:
            if años_experiencia >= 0:
                return {
                    'score': 25,
                    'fortaleza': f"{años_experiencia} años de experiencia adecuados para nivel Junior",
                    'debilidad': None,
                    'analisis': f"Experiencia compatible con nivel Junior ({años_experiencia} años)"
                }
        elif 'mid' in nivel_requerido or 'medio' in nivel_requerido:
            if años_experiencia >= 2:
                return {
                    'score': 25,
                    'fortaleza': f"{años_experiencia} años de experiencia para nivel Mid-level",
                    'debilidad': None,
                    'analisis': f"Experiencia suficiente para nivel Mid ({años_experiencia} años)"
                }
            else:
                return {
                    'score': 10,
                    'fortaleza': None,
                    'debilidad': f"Solo {años_experiencia} años para nivel Mid-level",
                    'analisis': f"Experiencia limitada para nivel Mid ({años_experiencia} años)"
                }
        elif 'senior' in nivel_requerido:
            if años_experiencia >= 3:
                return {
                    'score': 25,
                    'fortaleza': f"{años_experiencia} años de experiencia para nivel Senior",
                    'debilidad': None,
                    'analisis': f"Experiencia adecuada para nivel Senior ({años_experiencia} años)"
                }
            else:
                return {
                    'score': 5,
                    'fortaleza': None,
                    'debilidad': f"Solo {años_experiencia} años para nivel Senior",
                    'analisis': f"Experiencia insuficiente para nivel Senior ({años_experiencia} años)"
                }
        
        return {
            'score': 15,
            'fortaleza': f"{años_experiencia} años de experiencia",
            'debilidad': None,
            'analisis': f"Experiencia general: {años_experiencia} años"
        }
    
    def _analizar_requisitos(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar cumplimiento de requisitos específicos"""
        requisitos = vacante.get('requisitos', [])
        cumplidos = 0
        
        # Crear texto de búsqueda del candidato
        texto_candidato = ""
        for exp in candidato.get('experiencias', []):
            texto_candidato += f" {exp.get('descripcion', '')} {exp.get('cargo', '')}"
        
        for edu in candidato.get('educaciones', []):
            texto_candidato += f" {edu.get('titulo', '')} {edu.get('campo_estudio', '')}"
        
        texto_candidato += f" {candidato.get('titulo_profesional', '')} {candidato.get('resumen_profesional', '')}"
        texto_candidato = texto_candidato.lower()
        
        # Verificar cada requisito
        for requisito in requisitos:
            requisito_lower = requisito.lower()
            # Buscar palabras clave del requisito en el perfil
            palabras_clave = requisito_lower.replace('+', '').split()
            if any(palabra in texto_candidato for palabra in palabras_clave if len(palabra) > 3):
                cumplidos += 1
        
        score = (cumplidos / len(requisitos)) * 15 if requisitos else 15
        
        return {
            'score': score,
            'cumplidos': cumplidos,
            'total': len(requisitos)
        }
    
    def _generar_recomendacion_basica(self, score: float, fortalezas: List[str], debilidades: List[str]) -> str:
        """Generar recomendación basada en el score y análisis"""
        if score >= 80:
            return f"Excelente candidato con {score}% de compatibilidad. Perfil muy alineado con los requisitos de la posición. Se recomienda continuar con el proceso de selección."
        elif score >= 60:
            return f"Buen candidato con {score}% de compatibilidad. Tiene potencial pero requiere evaluación adicional en algunas áreas. Considerar para entrevista."
        elif score >= 40:
            return f"Candidato con {score}% de compatibilidad. Perfil parcialmente alineado que podría funcionar con capacitación adicional o en un rol modificado."
        else:
            return f"Candidato con {score}% de compatibilidad. Perfil no muy alineado con los requisitos actuales de la posición. Se sugiere buscar otros perfiles más afines."
    
    def _basic_match_score_result(self, vacante: Dict[str, Any], score: int) -> Dict[str, Any]:
        """Crear resultado de match básico"""
        return {
            "vacante": {
                "id": vacante.get('id', ''),
                "titulo": vacante.get('titulo', ''),
                "empresa": vacante.get('empresa', vacante.get('empresa_nombre', '')),
                "ubicacion": vacante.get('ubicacion', ''),
                "modalidad": vacante.get('modalidad', vacante.get('tipo_empleo', 'No especificada')),
                "salario_min": vacante.get('salario_min', 0),
                "salario_max": vacante.get('salario_max', 0),
                "nivel_experiencia": vacante.get('nivel_experiencia', ''),
                "descripcion": vacante.get('descripcion', ''),
                "requisitos": vacante.get('requisitos', [])
            },
            "score": score,
            "match_percentage": score,
            "fortalezas": ["Experiencia relevante", "Perfil técnico adecuado"],
            "debilidades": ["Análisis básico - se requiere evaluación detallada"],
            "recomendacion": "Candidato con potencial para la posición",
            "skills_match": {
                "coincidentes": [],
                "faltantes": []
            }
        }

    def _analizar_habilidades_semantico(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis semántico avanzado de habilidades usando IA"""
        if not self.ai_processor.ai_available:
            return self._analizar_habilidades(candidato, vacante)
        
        try:
            # Extraer todas las habilidades mencionadas del candidato
            texto_habilidades_candidato = ""
            for exp in candidato.get('experiencias', []):
                texto_habilidades_candidato += f" {exp.get('descripcion', '')} {exp.get('cargo', '')}"
            
            texto_habilidades_candidato += f" {candidato.get('titulo_profesional', '')} {candidato.get('resumen_profesional', '')}"
            
            for cert in candidato.get('certificaciones', []):
                texto_habilidades_candidato += f" {cert.get('nombre', '')}"
            
            prompt = f"""
            Analiza las habilidades del candidato y compáralas con las requeridas para la vacante.
            
            HABILIDADES DEL CANDIDATO (extraer de texto):
            {texto_habilidades_candidato}
            
            HABILIDADES REQUERIDAS:
            {', '.join(vacante.get('habilidades_requeridas', []))}
            
            Instrucciones:
            1. Identifica habilidades EXACTAS que coinciden
            2. Identifica habilidades RELACIONADAS o SIMILARES (ej: React Native ≈ React, PostgreSQL ≈ SQL)
            3. Identifica habilidades TRANSFERIBLES (ej: Python + Django puede transferirse a Flask)
            4. Lista las habilidades completamente FALTANTES
            5. Asigna un score de 0-100 basado en la cobertura total
            
            Responde en JSON:
            {{
                "score_habilidades": número_0_100,
                "coincidentes": ["skill1", "skill2"],
                "relacionadas": ["skill3", "skill4"],
                "transferibles": ["skill5", "skill6"],
                "faltantes": ["skill7", "skill8"],
                "nivel_tecnico": "JUNIOR|MID|SENIOR",
                "recomendacion_skills": "breve_recomendacion"
            }}
            """
            
            response = self.ai_processor.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto técnico en evaluación de habilidades de programación y tecnología."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            clean_response = result.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            return json.loads(clean_response)
            
        except Exception as e:
            logger.error(f"Error en análisis semántico de habilidades: {e}")
            return self._analizar_habilidades(candidato, vacante)

    def _calcular_score_cultural_fit(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Calcular compatibilidad cultural y soft skills"""
        if not self.ai_processor.ai_available:
            return {"score": 50, "analisis": "Análisis cultural no disponible sin IA"}
        
        try:
            # Crear perfil del candidato para análisis cultural
            perfil_candidato = {
                "experiencias": candidato.get('experiencias', []),
                "educaciones": candidato.get('educaciones', []),
                "idiomas": candidato.get('idiomas', []),
                "resumen": candidato.get('resumen_profesional', ''),
                "ubicacion": f"{candidato.get('ciudad', '')} {candidato.get('pais', '')}"
            }
            
            prompt = f"""
            Analiza la compatibilidad cultural y soft skills entre el candidato y la empresa/puesto.
            
            CANDIDATO:
            {json.dumps(perfil_candidato, indent=2, ensure_ascii=False)}
            
            VACANTE:
            Empresa: {vacante['empresa']}
            Título: {vacante['titulo']}
            Modalidad: {vacante['modalidad']}
            Ubicación: {vacante['ubicacion']}
            Descripción: {vacante['descripcion']}
            
            Evalúa:
            1. Adaptabilidad a la modalidad de trabajo
            2. Experiencia en empresas similares
            3. Nivel de comunicación (por idiomas y experiencias)
            4. Fit con el tipo de empresa y cultura
            5. Capacidad de crecimiento
            
            Responde en JSON:
            {{
                "score_cultural": número_0_100,
                "fortalezas_culturales": ["fortaleza1", "fortaleza2"],
                "areas_atencion": ["area1", "area2"],
                "recomendacion_cultural": "análisis_detallado"
            }}
            """
            
            response = self.ai_processor.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en recursos humanos especializado en cultural fit y soft skills."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.2
            )
            
            result = response.choices[0].message.content
            clean_response = result.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            return json.loads(clean_response)
            
        except Exception as e:
            logger.error(f"Error en análisis cultural: {e}")
            return {"score_cultural": 50, "analisis": "Error en análisis cultural"}

    def _calcular_potencial_crecimiento(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluar el potencial de crecimiento del candidato en la posición"""
        experiencias = candidato.get('experiencias', [])
        educaciones = candidato.get('educaciones', [])
        certificaciones = candidato.get('certificaciones', [])
        
        # Calcular factores de crecimiento
        factores = {
            "diversidad_experiencia": len(set(exp.get('empresa', '') for exp in experiencias)),
            "progression_roles": self._evaluar_progresion_roles(experiencias),
            "educacion_continua": len(certificaciones),
            "educacion_formal": len(educaciones),
            "años_experiencia": len(experiencias)
        }
        
        # Score basado en factores
        score_potencial = 0
        
        # Diversidad de empresas (20 puntos)
        if factores["diversidad_experiencia"] >= 3:
            score_potencial += 20
        elif factores["diversidad_experiencia"] >= 2:
            score_potencial += 15
        elif factores["diversidad_experiencia"] >= 1:
            score_potencial += 10
        
        # Progresión en roles (25 puntos)
        score_potencial += min(factores["progression_roles"] * 5, 25)
        
        # Educación continua (20 puntos)
        score_potencial += min(factores["educacion_continua"] * 4, 20)
        
        # Educación formal (15 puntos)
        score_potencial += min(factores["educacion_formal"] * 7, 15)
        
        # Experiencia balanceada (20 puntos)
        if 2 <= factores["años_experiencia"] <= 8:
            score_potencial += 20
        elif factores["años_experiencia"] > 8:
            score_potencial += 15
        else:
            score_potencial += 10
        
        return {
            "score_potencial": min(score_potencial, 100),
            "factores": factores,
            "recomendacion_potencial": self._generar_recomendacion_potencial(score_potencial, factores)
        }
    
    def _evaluar_progresion_roles(self, experiencias: List[Dict[str, Any]]) -> int:
        """Evaluar si hay progresión en los roles del candidato"""
        if len(experiencias) < 2:
            return 0
        
        roles_progresivos = ["junior", "developer", "senior", "lead", "architect", "manager", "director"]
        scores = []
        
        for exp in experiencias:
            cargo = exp.get('cargo', '').lower()
            for i, role in enumerate(roles_progresivos):
                if role in cargo:
                    scores.append(i)
                    break
            else:
                scores.append(1)  # Score neutral si no se identifica
        
        # Calcular si hay progresión
        if len(scores) >= 2:
            return max(0, max(scores) - min(scores))
        return 0
    
    def _generar_recomendacion_potencial(self, score: int, factores: Dict[str, Any]) -> str:
        """Generar recomendación basada en potencial de crecimiento"""
        if score >= 80:
            return f"Alto potencial de crecimiento. Candidato con {factores['diversidad_experiencia']} empresas diferentes y progresión evidente en roles. Excelente para posiciones con proyección."
        elif score >= 60:
            return f"Buen potencial de crecimiento. Muestra {factores['educacion_continua']} certificaciones y diversidad de experiencia. Candidato prometedor para desarrollo interno."
        elif score >= 40:
            return f"Potencial moderado. {factores['años_experiencia']} años de experiencia con algunas oportunidades de mejora en diversidad de roles."
        else:
            return f"Potencial limitado actualmente. Recomendable para roles específicos más que para crecimiento acelerado en la organización."

    def _analizar_habilidades_real(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar habilidades usando SOLO datos reales de la BD"""
        try:
            habilidades_candidato = self._extraer_habilidades_candidato(candidato)
            
            # Extraer habilidades específicas de ESTA vacante
            descripcion_vacante = vacante.get('descripcion', '') + ' ' + vacante.get('titulo', '')
            habilidades_vacante_extraidas = self._extraer_habilidades_descripcion(descripcion_vacante)
            
            # También usar habilidades_requeridas si existen (para compatibilidad)
            habilidades_requeridas_estructura = vacante.get('habilidades_requeridas', [])
            habilidades_vacante = habilidades_vacante_extraidas + habilidades_requeridas_estructura
            habilidades_vacante = list(set(habilidades_vacante))  # Eliminar duplicados
            
            if not habilidades_vacante:
                # Si no hay habilidades específicas, dar un score base moderado
                return {
                    "score_skills": 60,  # Score base para vacantes sin habilidades específicas
                    "coincidencias": 0,
                    "total_requeridas": 0,
                    "habilidades_encontradas": [],
                    "habilidades_vacante_detectadas": [],
                    "analisis": "Sin habilidades técnicas específicas requeridas en la descripción"
                }
            
            coincidencias = 0
            habilidades_encontradas = []
            
            # Normalizar habilidades para mejor matching
            habilidades_candidato_lower = [h.lower() for h in habilidades_candidato]
            
            for hab_vacante in habilidades_vacante:
                hab_vacante_lower = hab_vacante.lower()
                encontrada = False
                
                # Buscar coincidencias exactas o parciales
                for hab_candidato_lower in habilidades_candidato_lower:
                    if (hab_vacante_lower in hab_candidato_lower or 
                        hab_candidato_lower in hab_vacante_lower or
                        hab_vacante_lower == hab_candidato_lower or
                        self._son_habilidades_relacionadas(hab_vacante_lower, hab_candidato_lower)):
                        coincidencias += 1
                        habilidades_encontradas.append(hab_vacante)
                        encontrada = True
                        break
                
                # Buscar coincidencias parciales con puntaje reducido
                if not encontrada:
                    for hab_candidato_lower in habilidades_candidato_lower:
                        if self._coincidencia_parcial(hab_vacante_lower, hab_candidato_lower):
                            coincidencias += 0.5
                            habilidades_encontradas.append(f"{hab_vacante} (parcial)")
                            break
            
            # Score basado en porcentaje de coincidencias
            score_skills = min((coincidencias / len(habilidades_vacante)) * 100, 100) if habilidades_vacante else 0
            
            return {
                "score_skills": int(score_skills),
                "coincidencias": round(coincidencias, 1),
                "total_requeridas": len(habilidades_vacante),
                "habilidades_encontradas": habilidades_encontradas,
                "habilidades_vacante_detectadas": habilidades_vacante,
                "analisis": f"Coinciden {coincidencias:.1f} de {len(habilidades_vacante)} habilidades específicas de esta vacante"
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de habilidades real: {e}")
            return {"score_skills": 0, "analisis": "Error en análisis"}
    
    def _son_habilidades_relacionadas(self, hab1: str, hab2: str) -> bool:
        """Verificar si dos habilidades están relacionadas"""
        # Validar que ambas habilidades no sean None o vacías
        if not hab1 or not hab2:
            return False
        
        # Convertir a string y lowercase para comparación
        hab1_lower = str(hab1).lower()
        hab2_lower = str(hab2).lower()
        
        relaciones = {
            'excel': ['office', 'microsoft', 'hoja de calculo', 'spreadsheet'],
            'sql': ['mysql', 'postgresql', 'oracle', 'database', 'base de datos'],
            'javascript': ['js', 'node', 'react', 'angular', 'vue'],
            'python': ['django', 'flask', 'pandas', 'numpy'],
            'contabilidad': ['finanzas', 'administracion', 'contador'],
            'ingles': ['english', 'bilingue'],
            'ventas': ['atencion al cliente', 'call center', 'comercial'],
            'seguridad': ['higiene', 'industrial', 'riesgos'],
            'erp': ['sap', 'oracle', 'netsuite', 'compac', 'intelisis']
        }
        
        for palabra_clave, relacionadas in relaciones.items():
            if palabra_clave in hab1_lower and any(rel in hab2_lower for rel in relacionadas):
                return True
            if palabra_clave in hab2_lower and any(rel in hab1_lower for rel in relacionadas):
                return True
        
        return False
    
    def _coincidencia_parcial(self, hab_vacante: str, hab_candidato: str) -> bool:
        """Verificar coincidencias parciales entre habilidades"""
        # Validar que ambas habilidades no sean None o vacías
        if not hab_vacante or not hab_candidato:
            return False
        
        # Convertir a string para comparación
        hab_vacante_str = str(hab_vacante).lower()
        hab_candidato_str = str(hab_candidato).lower()
        
        # Coincidencias por palabras clave comunes
        palabras_vacante = set(hab_vacante_str.split())
        palabras_candidato = set(hab_candidato_str.split())
        
        # Si comparten al menos 1 palabra significativa (>3 caracteres)
        palabras_comunes = palabras_vacante.intersection(palabras_candidato)
        return any(len(palabra) > 3 for palabra in palabras_comunes)
    
    def _analizar_ubicacion_real(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar ubicación usando solo datos reales"""
        try:
            candidato_ciudad = candidato.get('ciudad', '').lower()
            candidato_pais = candidato.get('pais', '').lower()
            vacante_ubicacion = vacante.get('ubicacion', '').lower()
            modalidad = vacante.get('modalidad', vacante.get('tipo_empleo', '')).lower()
            
            # Si es remoto, compatible al 100%
            if 'remoto' in modalidad:
                return {
                    "compatible": True,
                    "score_ubicacion": 100,
                    "analisis": "Modalidad remota - ubicación no es limitante"
                }
            
            # Verificar si están en la misma ciudad
            if candidato_ciudad and candidato_ciudad in vacante_ubicacion:
                return {
                    "compatible": True,
                    "score_ubicacion": 100,
                    "analisis": f"Misma ciudad: {candidato_ciudad}"
                }
            
            # Verificar si están en el mismo país
            if candidato_pais and candidato_pais in vacante_ubicacion:
                return {
                    "compatible": True,
                    "score_ubicacion": 70,
                    "analisis": f"Mismo país: {candidato_pais}"
                }
            
            # Diferentes ubicaciones
            return {
                "compatible": False,
                "score_ubicacion": 20,
                "analisis": "Diferentes ubicaciones - modalidad presencial"
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de ubicación real: {e}")
            return {"compatible": False, "score_ubicacion": 0, "analisis": "Error en análisis"}
    
    def _analizar_experiencia_real(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar experiencia usando solo datos reales"""
        try:
            experiencias = candidato.get('experiencias', [])
            años_experiencia = len(experiencias)
            nivel_requerido = vacante.get('nivel_experiencia', '').lower()
            
            if not nivel_requerido:
                return {
                    "score_experiencia": 50,
                    "analisis": f"Sin nivel específico requerido. Candidato tiene {años_experiencia} años de experiencia"
                }
            
            # Evaluar según nivel requerido
            if 'junior' in nivel_requerido:
                if años_experiencia <= 2:
                    score = 100
                    analisis = f"Perfecto para Junior: {años_experiencia} años"
                elif años_experiencia <= 4:
                    score = 80
                    analisis = f"Algo de experiencia para Junior: {años_experiencia} años"
                else:
                    score = 60
                    analisis = f"Sobre-calificado para Junior: {años_experiencia} años"
                    
            elif 'mid' in nivel_requerido or 'middle' in nivel_requerido:
                if 2 <= años_experiencia <= 5:
                    score = 100
                    analisis = f"Perfecto para Mid-level: {años_experiencia} años"
                elif años_experiencia < 2:
                    score = 40
                    analisis = f"Poca experiencia para Mid-level: {años_experiencia} años"
                else:
                    score = 80
                    analisis = f"Experiencia senior para Mid-level: {años_experiencia} años"
                    
            elif 'senior' in nivel_requerido:
                if años_experiencia >= 5:
                    score = 100
                    analisis = f"Experiencia adecuada para Senior: {años_experiencia} años"
                elif años_experiencia >= 3:
                    score = 70
                    analisis = f"Experiencia moderada para Senior: {años_experiencia} años"
                else:
                    score = 30
                    analisis = f"Poca experiencia para Senior: {años_experiencia} años"
            else:
                # Sin nivel específico
                score = 60
                analisis = f"Nivel no especificado. Candidato: {años_experiencia} años"
            
            return {
                "score_experiencia": score,
                "años_experiencia": años_experiencia,
                "nivel_requerido": nivel_requerido,
                "analisis": analisis
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de experiencia real: {e}")
            return {"score_experiencia": 0, "analisis": "Error en análisis"}
    
    def _analizar_requisitos_real(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar requisitos usando solo datos reales"""
        try:
            # Extraer requisitos específicos de la descripción de esta vacante
            descripcion = vacante.get('descripcion', '')
            requisitos_extraidos = self._extraer_requisitos_especificos(descripcion)
            
            # También usar requisitos estructurados si existen
            requisitos_estructura = vacante.get('requisitos', [])
            todos_requisitos = requisitos_extraidos + requisitos_estructura
            todos_requisitos = list(set(todos_requisitos))  # Eliminar duplicados
            
            if not todos_requisitos:
                return {
                    "score_requisitos": 80,  # Score alto si no hay requisitos específicos
                    "cumplidos": 0,
                    "total": 0,
                    "requisitos_detectados": [],
                    "analisis": "Sin requisitos específicos detectados en la descripción"
                }
            
            # Crear texto de búsqueda del candidato
            texto_candidato = ""
            for exp in candidato.get('experiencias', []):
                texto_candidato += f" {exp.get('descripcion', '')} {exp.get('cargo', '')}"
            
            for edu in candidato.get('educaciones', []):
                texto_candidato += f" {edu.get('titulo', '')} {edu.get('campo_estudio', '')}"
            
            texto_candidato += f" {candidato.get('titulo_profesional', '')} {candidato.get('resumen_profesional', '')}"
            texto_candidato = texto_candidato.lower()
            
            # Verificar cada requisito específico
            cumplidos = 0
            requisitos_cumplidos = []
            
            for requisito in todos_requisitos:
                requisito_lower = requisito.lower()
                
                # Verificación más inteligente de requisitos
                if self._cumple_requisito(requisito_lower, texto_candidato, candidato):
                    cumplidos += 1
                    requisitos_cumplidos.append(requisito)
            
            score_requisitos = (cumplidos / len(todos_requisitos)) * 100 if todos_requisitos else 80
            
            return {
                "score_requisitos": int(score_requisitos),
                "cumplidos": cumplidos,
                "total": len(todos_requisitos),
                "requisitos_detectados": todos_requisitos,
                "requisitos_cumplidos": requisitos_cumplidos,
                "analisis": f"Cumple {cumplidos} de {len(todos_requisitos)} requisitos específicos"
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de requisitos real: {e}")
            return {"score_requisitos": 0, "cumplidos": 0, "analisis": "Error en análisis"}
    
    def _extraer_requisitos_especificos(self, descripcion: str) -> List[str]:
        """Extraer requisitos específicos de la descripción de la vacante"""
        requisitos = []
        descripcion_lower = descripcion.lower()
        
        # Patrones de requisitos comunes
        import re
        
        # Experiencia específica
        experiencia_patterns = [
            r'(\d+)\s*a[ñn]os?\s+de\s+experiencia',
            r'experiencia\s+de\s+(\d+)\s*a[ñn]os?',
            r'mínimo\s+(\d+)\s*a[ñn]os?',
            r'experiencia\s+en\s+([^\.]+)',
            r'conocimiento\s+en\s+([^\.]+)',
            r'dominio\s+de\s+([^\.]+)'
        ]
        
        for pattern in experiencia_patterns:
            matches = re.findall(pattern, descripcion_lower)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                if len(match.strip()) > 2:
                    requisitos.append(match.strip())
        
        # Educación
        if 'licenciatura' in descripcion_lower:
            requisitos.append('Licenciatura')
        if 'ingeniería' in descripcion_lower or 'ingeniero' in descripcion_lower:
            requisitos.append('Ingeniería')
        if 'maestría' in descripcion_lower:
            requisitos.append('Maestría')
        if 'carrera' in descripcion_lower:
            requisitos.append('Carrera universitaria')
        
        # Idiomas
        if 'inglés' in descripcion_lower or 'english' in descripcion_lower:
            if 'avanzado' in descripcion_lower:
                requisitos.append('Inglés avanzado')
            else:
                requisitos.append('Inglés')
        
        # Habilidades específicas detectadas en la descripción
        if 'excel' in descripcion_lower:
            if 'avanzado' in descripcion_lower or 'intermedio' in descripcion_lower:
                requisitos.append('Excel avanzado')
            else:
                requisitos.append('Excel')
        
        # Certificaciones
        if 'dc3' in descripcion_lower:
            requisitos.append('Certificación DC3')
        
        # Disponibilidad
        if 'disponibilidad para viajar' in descripcion_lower:
            requisitos.append('Disponibilidad para viajar')
        if 'tiempo completo' in descripcion_lower:
            requisitos.append('Tiempo completo')
        
        # Limpiar y filtrar requisitos
        requisitos_limpios = []
        for req in requisitos:
            req_clean = req.strip()
            if len(req_clean) > 3 and req_clean not in requisitos_limpios:
                requisitos_limpios.append(req_clean.title())
        
        return requisitos_limpios[:8]  # Máximo 8 requisitos más relevantes
    
    def _cumple_requisito(self, requisito: str, texto_candidato: str, candidato: Dict) -> bool:
        """Verificar si el candidato cumple un requisito específico"""
        
        # Verificar experiencia en años
        if 'años' in requisito and 'experiencia' in requisito:
            import re
            anos_req = re.findall(r'(\d+)', requisito)
            if anos_req:
                anos_requeridos = int(anos_req[0])
                anos_candidato = len(candidato.get('experiencias', []))
                return anos_candidato >= anos_requeridos
        
        # Verificar educación
        if requisito in ['licenciatura', 'carrera universitaria']:
            return any('licenciatura' in edu.get('titulo', '').lower() or 
                      'universitario' in edu.get('titulo', '').lower()
                      for edu in candidato.get('educaciones', []))
        
        if requisito in ['ingeniería', 'ingeniero']:
            return (any('ingenier' in edu.get('titulo', '').lower() 
                       for edu in candidato.get('educaciones', [])) or
                   'ingenier' in candidato.get('titulo_profesional', '').lower())
        
        # Verificar habilidades específicas
        palabras_clave = requisito.replace(',', ' ').split()
        return any(palabra in texto_candidato for palabra in palabras_clave if len(palabra) > 3)
    
    def _extraer_habilidades_candidato(self, candidato: Dict[str, Any]) -> List[str]:
        """Extraer habilidades del candidato desde sus datos reales"""
        habilidades = []
        
        # Términos técnicos comunes a buscar
        terminos_tecnicos = [
            'python', 'javascript', 'java', 'react', 'angular', 'vue', 'node', 'php', 'c#', 'c++',
            'sql', 'mysql', 'postgresql', 'mongodb', 'oracle', 'firebase',
            'html', 'css', 'sass', 'bootstrap', 'tailwind',
            'git', 'github', 'gitlab', 'docker', 'kubernetes', 'aws', 'azure', 'gcp',
            'scrum', 'agile', 'kanban', 'devops', 'ci/cd',
            'excel', 'word', 'powerpoint', 'office', 'google', 'sheets',
            'contabilidad', 'finanzas', 'administracion', 'marketing', 'ventas',
            'ingenieria', 'arquitectura', 'diseño', 'desarrollo', 'programacion',
            'full stack', 'backend', 'frontend', 'mobile', 'web',
            'machine learning', 'ai', 'inteligencia artificial', 'data science',
            'erp', 'sap', 'compac', 'intelisis', 'netsuite'
        ]
        
        # Buscar en experiencias
        for exp in candidato.get('experiencias', []):
            descripcion = exp.get('descripcion', '').lower()
            cargo = exp.get('cargo', '').lower()
            
            for termino in terminos_tecnicos:
                if termino in descripcion or termino in cargo:
                    if termino.title() not in habilidades:
                        habilidades.append(termino.title())
        
        # Buscar en título profesional
        titulo = candidato.get('titulo_profesional', '').lower()
        for termino in terminos_tecnicos:
            if termino in titulo:
                if termino.title() not in habilidades:
                    habilidades.append(termino.title())
        
        # Buscar en resumen
        resumen = candidato.get('resumen_profesional', '').lower()
        for termino in terminos_tecnicos:
            if termino in resumen:
                if termino.title() not in habilidades:
                    habilidades.append(termino.title())
        
        # Buscar en certificaciones (nombres exactos)
        for cert in candidato.get('certificaciones', []):
            nombre = cert.get('nombre', '')
            if nombre and nombre not in habilidades:
                habilidades.append(nombre)
        
        # Filtrar valores None o vacíos antes de devolver
        habilidades_filtradas = [h for h in habilidades if h and str(h).strip()]
        return habilidades_filtradas
    
    def _extraer_habilidades_descripcion(self, texto: str) -> List[str]:
        """Extraer habilidades técnicas de la descripción usando palabras clave y patrones"""
        habilidades_conocidas = {
            # Lenguajes de programación
            'python': 'Python', 'javascript': 'JavaScript', 'java': 'Java', 'c#': 'C#', 
            'php': 'PHP', 'ruby': 'Ruby', 'golang': 'Go', 'rust': 'Rust', 'typescript': 'TypeScript',
            'html': 'HTML', 'css': 'CSS', 'sql': 'SQL', 'matlab': 'MATLAB', 
            'c++': 'C++', 'swift': 'Swift', 'kotlin': 'Kotlin',
            # NOTA: Removí 'r' y 'go' porque causan falsos positivos
            
            # Frameworks y librerías
            'react': 'React', 'angular': 'Angular', 'vue': 'Vue', 'django': 'Django', 
            'flask': 'Flask', 'laravel': 'Laravel', 'spring': 'Spring', 'express': 'Express',
            'node.js': 'Node.js', 'nodejs': 'Node.js', 'jquery': 'jQuery', 
            'bootstrap': 'Bootstrap', 'next.js': 'Next.js', 'nuxt.js': 'Nuxt.js',
            
            # Bases de datos
            'postgresql': 'PostgreSQL', 'mysql': 'MySQL', 'mongodb': 'MongoDB', 
            'redis': 'Redis', 'oracle': 'Oracle', 'sql server': 'SQL Server', 
            'firebase': 'Firebase', 'dynamodb': 'DynamoDB', 'cassandra': 'Cassandra',
            
            # Cloud y DevOps
            'aws': 'AWS', 'azure': 'Azure', 'gcp': 'GCP', 'docker': 'Docker', 
            'kubernetes': 'Kubernetes', 'jenkins': 'Jenkins', 'gitlab': 'GitLab', 
            'terraform': 'Terraform', 'ansible': 'Ansible', 'linux': 'Linux',
            
            # Herramientas de oficina y software
            'excel': 'Excel', 'word': 'Word', 'powerpoint': 'PowerPoint', 
            'office': 'Office', 'google sheets': 'Google Sheets', 'outlook': 'Outlook',
            
            # ERPs y sistemas empresariales
            'sap': 'SAP', 'oracle netsuite': 'Oracle NetSuite', 'netsuite': 'NetSuite',
            'compac': 'COMPAC', 'intelisis': 'Intelisis', 'contpaqui': 'CONTPAQUI',
            'erp': 'ERP', 'crm': 'CRM',
            
            # Metodologías y conceptos
            'scrum': 'Scrum', 'agile': 'Agile', 'kanban': 'Kanban', 'devops': 'DevOps', 
            'ci/cd': 'CI/CD', 'tdd': 'TDD', 'bdd': 'BDD',
            
            # Análisis de datos
            'tableau': 'Tableau', 'power bi': 'Power BI', 'pandas': 'Pandas', 
            'numpy': 'NumPy', 'scikit-learn': 'Scikit-learn', 'tensorflow': 'TensorFlow', 
            'pytorch': 'PyTorch', 'machine learning': 'Machine Learning', 
            'data science': 'Data Science', 'inteligencia artificial': 'Inteligencia Artificial',
            
            # Áreas profesionales
            'contabilidad': 'Contabilidad', 'finanzas': 'Finanzas', 'administracion': 'Administración',
            'marketing': 'Marketing', 'ventas': 'Ventas', 'recursos humanos': 'Recursos Humanos',
            'ingenieria': 'Ingeniería', 'arquitectura': 'Arquitectura', 'diseño': 'Diseño',
            'desarrollo': 'Desarrollo', 'programacion': 'Programación',
            
            # Especialidades específicas
            'seguridad industrial': 'Seguridad Industrial', 'higiene': 'Higiene y Seguridad',
            'liderazgo': 'Liderazgo', 'gestion de proyectos': 'Gestión de Proyectos',
            'atencion al cliente': 'Atención al Cliente', 'call center': 'Call Center',
            'facturacion': 'Facturación', 'cobranza': 'Cobranza', 'credito': 'Crédito',
            'logistica': 'Logística', 'packaging': 'Packaging', 'procesos': 'Procesos',
            
            # Idiomas
            'ingles': 'Inglés', 'english': 'Inglés', 'frances': 'Francés', 'aleman': 'Alemán',
            
            # Herramientas específicas
            'photoshop': 'Photoshop', 'illustrator': 'Illustrator', 'autocad': 'AutoCAD',
            'solidworks': 'SolidWorks', 'git': 'Git', 'github': 'GitHub'
        }
        
        texto_lower = texto.lower()
        habilidades_encontradas = []
        
        # Buscar habilidades por coincidencia exacta CON VALIDACIÓN DE CONTEXTO
        for keyword, habilidad_formal in habilidades_conocidas.items():
            # Buscar con límites de palabra para evitar falsos positivos
            import re
            
            # Crear patrón que busque la palabra completa
            patron = r'\b' + re.escape(keyword) + r'\b'
            if re.search(patron, texto_lower):
                # Validación adicional para palabras muy cortas
                if len(keyword) <= 2:
                    # Para palabras de 1-2 caracteres, verificar contexto
                    if self._validar_contexto_habilidad(keyword, texto_lower):
                        if habilidad_formal not in habilidades_encontradas:
                            habilidades_encontradas.append(habilidad_formal)
                else:
                    # Para palabras más largas, agregar directamente
                    if habilidad_formal not in habilidades_encontradas:
                        habilidades_encontradas.append(habilidad_formal)
        
        # Buscar patrones específicos
        import re
        
        # Buscar años de experiencia como habilidad
        anos_exp = re.findall(r'(\d+)\s*a[ñn]os?\s+de\s+experiencia', texto_lower)
        if anos_exp:
            for anos in anos_exp:
                habilidades_encontradas.append(f"{anos} años de experiencia")
        
        # Buscar niveles educativos
        if 'licenciatura' in texto_lower or 'licenciado' in texto_lower:
            habilidades_encontradas.append('Licenciatura')
        if 'ingenieria' in texto_lower or 'ingeniero' in texto_lower:
            habilidades_encontradas.append('Ingeniería')
        if 'maestria' in texto_lower or 'maestría' in texto_lower:
            habilidades_encontradas.append('Maestría')
        
        # Buscar certificaciones específicas
        if 'dc3' in texto_lower:
            habilidades_encontradas.append('DC3')
        if re.search(r'\biso\b', texto_lower):
            habilidades_encontradas.append('ISO')
        
        # Filtrar valores None o vacíos antes de devolver
        habilidades_filtradas = [h for h in habilidades_encontradas if h and str(h).strip()]
        return list(set(habilidades_filtradas))  # Eliminar duplicados
    
    def _validar_contexto_habilidad(self, keyword: str, texto: str) -> bool:
        """Validar contexto para habilidades de 1-2 caracteres para evitar falsos positivos"""
        
        # Para 'r': solo si está en contexto de programación
        if keyword == 'r':
            contextos_validos = ['lenguaje r', 'programacion r', 'estadistica r', 'r programming', 'software r']
            return any(contexto in texto for contexto in contextos_validos)
        
        # Para 'go': solo si está en contexto de programación
        if keyword == 'go':
            contextos_validos = ['golang', 'lenguaje go', 'programacion go', 'go programming']
            return any(contexto in texto for contexto in contextos_validos)
        
        # Para 'c': solo en contexto de programación
        if keyword == 'c':
            contextos_validos = ['lenguaje c', 'programacion c', 'c programming']
            return any(contexto in texto for contexto in contextos_validos)
        
        return False
    
    def _generar_fortalezas_reales(self, skills_analysis: Dict, ubicacion_analysis: Dict, exp_analysis: Dict) -> List[str]:
        """Generar fortalezas basadas en datos reales"""
        fortalezas = []
        
        if skills_analysis.get('score_skills', 0) >= 70:
            coincidencias = skills_analysis.get('coincidencias', 0)
            total = skills_analysis.get('total_requeridas', 1)
            fortalezas.append(f"Excelente match técnico: {coincidencias}/{total} habilidades")
        
        if ubicacion_analysis.get('compatible', False):
            fortalezas.append(f"Ubicación compatible: {ubicacion_analysis.get('analisis', '')}")
        
        if exp_analysis.get('score_experiencia', 0) >= 80:
            años = exp_analysis.get('años_experiencia', 0)
            fortalezas.append(f"Experiencia adecuada: {años} años")
        
        return fortalezas[:3]  # Máximo 3
    
    def _generar_debilidades_reales(self, skills_analysis: Dict, ubicacion_analysis: Dict, exp_analysis: Dict) -> List[str]:
        """Generar debilidades basadas en datos reales"""
        debilidades = []
        
        if skills_analysis.get('score_skills', 0) < 50:
            coincidencias = skills_analysis.get('coincidencias', 0)
            total = skills_analysis.get('total_requeridas', 1)
            debilidades.append(f"Pocas habilidades coincidentes: {coincidencias}/{total}")
        
        if not ubicacion_analysis.get('compatible', False):
            debilidades.append("Ubicación no compatible para modalidad presencial")
        
        if exp_analysis.get('score_experiencia', 0) < 40:
            debilidades.append(f"Experiencia limitada para el nivel requerido")
        
        return debilidades[:2]  # Máximo 2
    
    def _generar_recomendacion_real(self, score: int, coincidencias: int, faltantes: int) -> str:
        """Generar recomendación basada en datos reales"""
        if score >= 80:
            return f"✅ CANDIDATO EXCELENTE ({score}%): Alta compatibilidad con {coincidencias} habilidades coincidentes. Recomendado para entrevista."
        elif score >= 60:
            return f"⚡ CANDIDATO CON POTENCIAL ({score}%): Buena base con {coincidencias} habilidades. Considerar entrevista."
        elif score >= 40:
            return f"⚠️ CANDIDATO PARCIAL ({score}%): Algunas habilidades coincidentes pero le faltan {faltantes}. Evaluar si es entrenable."
        else:
            return f"❌ CANDIDATO NO RECOMENDADO ({score}%): Pocas coincidencias con los requisitos actuales."

    def _analizar_area_laboral(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar si el área laboral del candidato coincide con la vacante"""
        try:
            # Texto del candidato (experiencias + título)
            texto_candidato = ""
            for exp in candidato.get('experiencias', []):
                texto_candidato += f" {exp.get('descripcion', '')} {exp.get('cargo', '')}"
            texto_candidato += f" {candidato.get('titulo_profesional', '')}"
            texto_candidato = texto_candidato.lower()
            
            # Texto de la vacante (título + descripción)
            texto_vacante = f"{vacante.get('titulo', '')} {vacante.get('descripcion', '')}".lower()
            
            # Determinar sectores
            sector_candidato = self._detectar_sector(texto_candidato)
            sector_vacante = self._detectar_sector(texto_vacante)
            
            # Calcular score basado en compatibilidad de sectores
            if sector_candidato == sector_vacante:
                # Match exacto de sector
                score_area = 100
                match_exacta = True
                analisis = f"Match perfecto: ambos en sector {sector_candidato}"
            elif self._sectores_relacionados(sector_candidato, sector_vacante):
                # Sectores relacionados
                score_area = 75
                match_exacta = False
                analisis = f"Sectores relacionados: {sector_candidato} → {sector_vacante}"
            elif sector_candidato == "general" or sector_vacante == "general":
                # Uno es general (adaptable)
                score_area = 60
                match_exacta = False
                analisis = f"Perfil adaptable: {sector_candidato} → {sector_vacante}"
            else:
                # Sectores diferentes
                score_area = 30
                match_exacta = False
                analisis = f"Sectores diferentes: {sector_candidato} → {sector_vacante}"
            
            return {
                "score_area": score_area,
                "sector_candidato": sector_candidato.title(),
                "sector_vacante": sector_vacante.title(),
                "match_area_exacta": match_exacta,
                "analisis": analisis
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de área laboral: {e}")
            return {"score_area": 50, "sector_candidato": "General", "sector_vacante": "General", "analisis": "Error en análisis"}
    
    def _detectar_sector(self, texto: str) -> str:
        """Detectar el sector laboral predominante en un texto"""
        sectores_puntos = {}
        
        # Contar coincidencias por sector
        for sector, palabras_clave in self.config.areas_laborales.items():
            puntos = 0
            for palabra in palabras_clave:
                puntos += texto.count(palabra.lower())
            sectores_puntos[sector] = puntos
        
        # Retornar el sector con más puntos
        if max(sectores_puntos.values()) > 0:
            return max(sectores_puntos, key=sectores_puntos.get)
        return "general"
    
    def _sectores_relacionados(self, sector1: str, sector2: str) -> bool:
        """Verificar si dos sectores están relacionados"""
        relaciones = {
            "contabilidad": ["administracion"],
            "ventas": ["administracion"],
            "administracion": ["contabilidad", "ventas"],
            "seguridad": ["operaciones"],
            "operaciones": ["seguridad"],
            "servicios": ["operaciones"],
            "tecnologia": ["administracion"],
            "salud": ["servicios"],
            "educacion": ["administracion"]
        }
        
        return sector2 in relaciones.get(sector1, []) or area1 in relacionadas.get(area2, [])
    
    def _analizar_educacion_requisitos(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar educación y requisitos generales"""
        try:
            # Extraer requisitos de educación de la vacante
            descripcion = vacante.get('descripcion', '').lower()
            titulo_vacante = vacante.get('titulo', '').lower()
            
            requisitos_educacion = []
            puntos_cumplidos = 0
            total_requisitos = 0
            
            # Verificar requisitos educativos
            if 'licenciatura' in descripcion or 'licenciado' in descripcion:
                total_requisitos += 1
                requisitos_educacion.append('Licenciatura')
                if self._candidato_tiene_licenciatura(candidato):
                    puntos_cumplidos += 1
            
            if 'ingenier' in descripcion or 'ingenier' in titulo_vacante:
                total_requisitos += 1
                requisitos_educacion.append('Ingeniería')
                if self._candidato_tiene_ingenieria(candidato):
                    puntos_cumplidos += 1
            
            if 'maestr' in descripcion:
                total_requisitos += 1
                requisitos_educacion.append('Maestría')
                if self._candidato_tiene_maestria(candidato):
                    puntos_cumplidos += 1
            
            # Verificar experiencia mínima
            anos_requeridos = self._extraer_anos_experiencia_requeridos(descripcion)
            if anos_requeridos > 0:
                total_requisitos += 1
                requisitos_educacion.append(f'{anos_requeridos} años de experiencia')
                anos_candidato = len(candidato.get('experiencias', []))
                if anos_candidato >= anos_requeridos:
                    puntos_cumplidos += 1
            
            # Calcular score
            if total_requisitos == 0:
                score_educacion = 80  # Sin requisitos específicos
                analisis = "Sin requisitos educativos específicos"
            else:
                score_educacion = (puntos_cumplidos / total_requisitos) * 100
                analisis = f"Cumple {puntos_cumplidos} de {total_requisitos} requisitos educativos"
            
            return {
                "score_educacion": int(score_educacion),
                "cumplidos": puntos_cumplidos,
                "total": total_requisitos,
                "requisitos_detectados": requisitos_educacion,
                "analisis": analisis
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de educación: {e}")
            return {"score_educacion": 0, "cumplidos": 0, "total": 0, "analisis": "Error en análisis"}
    
    def _candidato_tiene_licenciatura(self, candidato: Dict[str, Any]) -> bool:
        """Verificar si el candidato tiene licenciatura"""
        for edu in candidato.get('educaciones', []):
            titulo = edu.get('titulo', '').lower()
            if 'licenciatura' in titulo or 'licenciado' in titulo:
                return True
        return 'licenciatura' in candidato.get('titulo_profesional', '').lower()
    
    def _candidato_tiene_ingenieria(self, candidato: Dict[str, Any]) -> bool:
        """Verificar si el candidato tiene ingeniería"""
        for edu in candidato.get('educaciones', []):
            titulo = edu.get('titulo', '').lower()
            if 'ingenier' in titulo:
                return True
        return 'ingenier' in candidato.get('titulo_profesional', '').lower()
    
    def _candidato_tiene_maestria(self, candidato: Dict[str, Any]) -> bool:
        """Verificar si el candidato tiene maestría"""
        for edu in candidato.get('educaciones', []):
            titulo = edu.get('titulo', '').lower()
            if 'maestr' in titulo:
                return True
        return False
    
    def _extraer_anos_experiencia_requeridos(self, texto: str) -> int:
        """Extraer años de experiencia requeridos"""
        import re
        patterns = [
            r'(\d+)\s*a[ñn]os?\s+de\s+experiencia',
            r'experiencia\s+de\s+(\d+)\s*a[ñn]os?',
            r'mínimo\s+(\d+)\s*a[ñn]os?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texto)
            if match:
                return int(match.group(1))
        return 0
    
    def _generar_fortalezas_generales(self, area_analysis: Dict, ubicacion_analysis: Dict, educacion_analysis: Dict, skills_analysis: Dict) -> List[str]:
        """Generar fortalezas basadas en análisis general"""
        fortalezas = []
        
        if area_analysis.get('match_area_exacta'):
            fortalezas.append(f"Experiencia específica en {area_analysis.get('sector_vacante', '')}")
        
        if ubicacion_analysis.get('es_compatible'):
            fortalezas.append("Ubicación compatible")
        
        cumplidos = educacion_analysis.get('cumplidos', 0)
        if cumplidos > 0:
            fortalezas.append(f"Cumple {cumplidos} requisitos educativos")
        
        coincidencias = len(skills_analysis.get('habilidades_encontradas', []))
        if coincidencias > 0:
            fortalezas.append(f"Tiene {coincidencias} habilidades específicas requeridas")
        
        return fortalezas[:3]  # Máximo 3 fortalezas principales
    
    def _generar_debilidades_generales(self, area_analysis: Dict, ubicacion_analysis: Dict, educacion_analysis: Dict, skills_analysis: Dict) -> List[str]:
        """Generar debilidades basadas en análisis general"""
        debilidades = []
        
        if not area_analysis.get('match_area_exacta'):
            debilidades.append(f"Experiencia en {area_analysis.get('sector_candidato', '')} vs vacante de {area_analysis.get('sector_vacante', '')}")
        
        if not ubicacion_analysis.get('es_compatible'):
            debilidades.append("Ubicación no compatible para modalidad presencial")
        
        faltantes = educacion_analysis.get('total', 0) - educacion_analysis.get('cumplidos', 0)
        if faltantes > 0:
            debilidades.append(f"Le faltan {faltantes} requisitos educativos")
        
        habilidades_faltantes = len(skills_analysis.get('habilidades_vacante_detectadas', [])) - len(skills_analysis.get('habilidades_encontradas', []))
        if habilidades_faltantes > 0:
            debilidades.append(f"Le faltan {habilidades_faltantes} habilidades específicas")
        
        return debilidades[:3]  # Máximo 3 debilidades principales
    
    def _generar_recomendacion_general(self, score: int, sector_candidato: str, sector_vacante: str) -> str:
        """Generar recomendación general basada en el score"""
        if score >= 80:
            return f"🌟 CANDIDATO IDEAL ({score}%): Excelente match para el puesto. Proceder con entrevista."
        elif score >= 65:
            return f"⚡ CANDIDATO RECOMENDADO ({score}%): Buen perfil con potencial. Considerar entrevista."
        elif score >= 45:
            return f"⚠️ CANDIDATO PARCIAL ({score}%): Algunas competencias relevantes. Evaluar si es entrenable."
        else:
            return f"❌ CANDIDATO NO RECOMENDADO ({score}%): Pocas coincidencias con los requisitos actuales."

    def calcular_score_match(self, candidato, vacante, habilidades_match):
        """Calcula el score de matching usando IA de OpenAI para análisis semántico MEJORADO"""
        try:
            logger.info(f"🤖 Iniciando matching IA avanzado para candidato {candidato.get('id', 'N/A')}")
            
            # 1. Preparar datos del candidato de forma más detallada
            candidato_text = self._preparar_perfil_candidato_detallado(candidato)
            
            # 2. Preparar datos de la vacante de forma más detallada
            vacante_text = self._preparar_descripcion_vacante_detallada(vacante)
            
            # 3. Usar OpenAI para análisis semántico avanzado
            try:
                score_ia, analisis_ia = self._analizar_match_con_openai_mejorado(candidato_text, vacante_text, habilidades_match, candidato, vacante)
                logger.info(f"🎯 OpenAI Score: {score_ia}% - {analisis_ia.get('resumen', 'Sin resumen')}")
                return score_ia, analisis_ia
            except Exception as e:
                logger.warning(f"⚠️ Error con OpenAI, usando algoritmo fallback: {e}")
                # Fallback al algoritmo mejorado si OpenAI falla
                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
        except Exception as e:
            logger.error(f"❌ Error en calcular_score_match: {e}")
            return 35, {"error": str(e), "fallback": True}

    def _preparar_perfil_candidato_detallado(self, candidato):
        """Preparar texto más detallado del perfil del candidato para análisis con IA"""
        perfil = []
        
        # Información básica
        nombre = candidato.get('nombre', 'Candidato')
        titulo = candidato.get('titulo_profesional', '')
        resumen = candidato.get('resumen_profesional', '')
        
        perfil.append(f"CANDIDATO: {nombre}")
        if titulo:
            perfil.append(f"TÍTULO PROFESIONAL: {titulo}")
        if resumen:
            perfil.append(f"RESUMEN: {resumen}")
        
        # Experiencias laborales con más detalle
        experiencias = candidato.get('experiencias', [])
        if experiencias:
            perfil.append("\n💼 EXPERIENCIA LABORAL:")
            for i, exp in enumerate(experiencias[:4]):  # Hasta 4 experiencias más recientes
                cargo = exp.get('cargo', '')
                empresa = exp.get('empresa', '')
                descripcion = exp.get('descripcion', '')
                fecha_inicio = exp.get('fecha_inicio', '')
                fecha_fin = exp.get('fecha_fin', 'Presente')
                
                if cargo and empresa:
                    perfil.append(f"\n{i+1}. {cargo} en {empresa}")
                    if fecha_inicio:
                        perfil.append(f"   Período: {fecha_inicio} - {fecha_fin}")
                    if descripcion:
                        # Incluir más descripción para mejor análisis
                        perfil.append(f"   Funciones: {descripcion[:300]}...")
        
        # Educación
        educaciones = candidato.get('educaciones', [])
        if educaciones:
            perfil.append("\n🎓 EDUCACIÓN:")
            for edu in educaciones:
                titulo_edu = edu.get('titulo', '')
                institucion = edu.get('institucion', '')
                campo = edu.get('campo_estudio', '')
                if titulo_edu:
                    perfil.append(f"- {titulo_edu}")
                    if campo:
                        perfil.append(f"  Campo: {campo}")
                    if institucion:
                        perfil.append(f"  Institución: {institucion}")
        
        # Habilidades técnicas y blandas
        habilidades = candidato.get('habilidades', [])
        if habilidades:
            perfil.append(f"\n🛠️ HABILIDADES TÉCNICAS: {', '.join(habilidades[:15])}")
        
        # Certificaciones
        certificaciones = candidato.get('certificaciones', [])
        if certificaciones:
            perfil.append("\n📜 CERTIFICACIONES:")
            for cert in certificaciones[:3]:
                nombre_cert = cert.get('nombre', '')
                entidad = cert.get('entidad_emisora', '')
                if nombre_cert:
                    perfil.append(f"- {nombre_cert} ({entidad})")
        
        # Idiomas
        idiomas = candidato.get('idiomas', [])
        if idiomas:
            idiomas_str = [f"{idioma.get('nombre', '')} ({idioma.get('nivel', '')})" for idioma in idiomas]
            perfil.append(f"\n🌐 IDIOMAS: {', '.join(idiomas_str)}")
        
        # Ubicación
        ciudad = candidato.get('ciudad', '')
        pais = candidato.get('pais', '')
        if ciudad or pais:
            perfil.append(f"\n📍 UBICACIÓN: {ciudad}, {pais}")
        
        return '\n'.join(perfil)

    def _preparar_descripcion_vacante_detallada(self, vacante):
        """Preparar texto más detallado de la vacante para análisis con IA"""
        descripcion = []
        
        titulo = vacante.get('titulo', '')
        empresa = vacante.get('empresa_nombre', vacante.get('empresa', ''))
        ubicacion = vacante.get('ubicacion', '')
        modalidad = vacante.get('modalidad', vacante.get('tipo_empleo', ''))
        categoria = vacante.get('categoria', '')
        
        descripcion.append(f"VACANTE: {titulo}")
        descripcion.append(f"🏢 EMPRESA: {empresa}")
        if categoria:
            descripcion.append(f"📂 CATEGORÍA: {categoria}")
        descripcion.append(f"📍 UBICACIÓN: {ubicacion}")
        descripcion.append(f"💼 MODALIDAD: {modalidad}")
        
        # Salario
        salario = vacante.get('salario')
        if salario and salario > 0:
            descripcion.append(f"💰 SALARIO: ${salario:,} MXN")
        
        # Descripción completa del puesto
        desc_puesto = vacante.get('descripcion', '')
        if desc_puesto:
            descripcion.append(f"\n📝 DESCRIPCIÓN COMPLETA:\n{desc_puesto}")
        
        # Nivel de experiencia si está disponible
        nivel_exp = vacante.get('nivel_experiencia', '')
        if nivel_exp:
            descripcion.append(f"\n📊 NIVEL REQUERIDO: {nivel_exp}")
        
        return '\n'.join(descripcion)

    def _analizar_match_con_openai_mejorado(self, candidato_text, vacante_text, habilidades_match, candidato=None, vacante=None):
        """Análisis mejorado con OpenAI para matching más preciso y diferenciado"""
        
        # Información adicional del análisis de habilidades
        habilidades_candidato = habilidades_match.get('habilidades_candidato', [])
        habilidades_vacante = habilidades_match.get('habilidades_vacante', [])
        coincidentes = habilidades_match.get('coincidentes', [])
        faltantes = habilidades_match.get('faltantes', [])
        
        prompt = f"""
Eres un reclutador SENIOR con 15 años de experiencia. Analiza DETALLADAMENTE la compatibilidad entre este candidato y esta vacante ESPECÍFICA. 

CANDIDATO:
{candidato_text}

VACANTE ESPECÍFICA:
{vacante_text}

ANÁLISIS TÉCNICO PREVIO:
- Habilidades del candidato: {', '.join(habilidades_candidato[:15])}
- Habilidades requeridas: {', '.join(habilidades_vacante[:15])}
- Coincidencias encontradas: {', '.join(coincidentes[:8])}
- Tecnologías/skills faltantes: {', '.join(faltantes[:10])}

INSTRUCCIONES CRÍTICAS PARA ANÁLISIS EXHAUSTIVO:

1. **EVALÚA EXPERIENCIA DIRECTA**: ¿Ha trabajado específicamente en este tipo de rol/industria?
2. **ANALIZA TECNOLOGÍAS ESPECÍFICAS**: ¿Maneja las herramientas exactas que pide la vacante?
3. **EVALÚA NIVEL DE SENIORITY**: ¿Su experiencia coincide con el nivel requerido?
4. **CONSIDERA SECTOR/INDUSTRIA**: ¿Tiene experiencia en este sector específico?
5. **ANALIZA SOFT SKILLS**: ¿Tiene las habilidades blandas necesarias para este rol?

CRITERIOS ESPECÍFICOS DE SCORING (SÉ MUY ESTRICTO):

📊 **SCORING ESPECÍFICO POR TIPO DE MATCH**:
- **MATCH PERFECTO (85-95%)**: Experiencia directa + todas las tecnologías + mismo nivel
- **MATCH EXCELENTE (70-84%)**: Experiencia directa + mayoría tecnologías + nivel apropiado  
- **MATCH BUENO (55-69%)**: Experiencia relacionada + algunas tecnologías + nivel cercano
- **MATCH REGULAR (35-54%)**: Experiencia transferible + pocas tecnologías + nivel diferente
- **MATCH BAJO (20-34%)**: Experiencia no relacionada + tecnologías diferentes + sector diferente
- **NO MATCH (5-19%)**: Completamente incompatible, diferentes industrias/roles

🎯 **EJEMPLOS ESPECÍFICOS DE SCORING CORRECTO**:
- Desarrollador Python Senior + Vacante Python Senior = 80-90%
- Desarrollador Python + Vacante React (sin Python) = 25-40%
- Desarrollador + Vacante Marketing = 10-25%
- Contador + Vacante Contabilidad = 75-85%
- Contador + Vacante Desarrollo = 5-20%
- Junior (1 año) + Vacante Senior (5+ años) = 30-45%
- Ingeniero Procesos + Vacante Desarrollo IA = 15-30%

RESPONDE CON ANÁLISIS DETALLADO ESPECÍFICO PARA ESTA VACANTE:
{{
    "score_final": [NÚMERO_ENTRE_5_Y_95_MUY_ESPECÍFICO],
    "experiencia_directa": [true/false],
    "anos_experiencia_relevante": [número de años en roles similares],
    "tecnologias_match_porcentaje": [0-100],
    "tecnologias_criticas_faltantes": ["tech1", "tech2", "tech3"],
    "nivel_seniority_apropiado": [true/false],
    "sector_experiencia_match": [true/false],
    "fortalezas_especificas": [
        "Fortaleza específica 1 para este rol exacto",
        "Fortaleza específica 2 detallada",
        "Fortaleza específica 3 con contexto",
        "Fortaleza específica 4 si aplica"
    ],
    "debilidades_detalladas": [
        "Falta de experiencia específica en [área exacta requerida]",
        "No maneja [tecnología crítica específica] requerida para [función específica]",
        "Nivel de experiencia insuficiente para responsabilidades de [área específica]",
        "Sin conocimiento en [herramienta/proceso específico] necesario para [tarea específica]",
        "Falta de experiencia en [industria/sector específico] que maneja [procesos específicos]"
    ],
    "gap_analysis": {{
        "tecnologico": "Descripción detallada de brechas tecnológicas específicas",
        "experiencial": "Descripción de falta de experiencia en áreas críticas", 
        "sectorial": "Descripción de diferencias de sector/industria",
        "nivel": "Descripción de diferencias de nivel de responsabilidad"
    }},
    "recomendacion_detallada": "Recomendación específica y detallada considerando esta vacante exacta y el perfil del candidato",
    "justificacion_score": "Explicación detallada del POR QUÉ este score específico, mencionando experiencias concretas y requisitos específicos no cumplidos",
    "probabilidad_exito": "muy_alta/alta/media/baja/muy_baja",
    "tiempo_adaptacion": "inmediato/1-3_meses/3-6_meses/6-12_meses/no_viable"
}}

IMPORTANTE: 
- El score debe ser MUY ESPECÍFICO y DIFERENTE para cada vacante
- Las debilidades deben ser DETALLADAS y ESPECÍFICAS para esta vacante exacta
- NO uses respuestas genéricas - cada análisis debe ser único
- SÉ REALISTA: Un desarrollador NO puede ser 60%+ compatible con roles de logística/eventos/finanzas
"""
        
        try:
            # Llamar a OpenAI con configuración optimizada para análisis detallado
            response = self.ai_processor.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un reclutador SENIOR experto que hace análisis MUY ESPECÍFICOS y DETALLADOS. Cada vacante debe tener un score MUY DIFERENTE basado en compatibilidad REAL. NO uses respuestas genéricas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,  # Más tokens para respuestas detalladas
                temperature=0.1
            )
            
            # Parsear respuesta
            content = response.choices[0].message.content.strip()
            
            # Limpiar y parsear JSON con múltiples intentos
            import json
            import re
            
            # Método 1: Extraer JSON directo
            try:
                analisis = json.loads(content)
            except json.JSONDecodeError:
                try:
                    # Método 2: Limpiar markdown
                    clean_content = content.strip()
                    if clean_content.startswith("```json"):
                        clean_content = clean_content[7:]
                    if clean_content.endswith("```"):
                        clean_content = clean_content[:-3]
                    clean_content = clean_content.strip()
                    analisis = json.loads(clean_content)
                except json.JSONDecodeError:
                    try:
                        # Método 3: Buscar JSON en la respuesta
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group()
                            # Intentar reparar JSON común
                            json_str = json_str.replace(",\n}", "\n}")  # Remover comas finales
                            json_str = json_str.replace(", }", " }")    # Remover comas antes de }
                            json_str = json_str.replace(",]", "]")      # Remover comas antes de ]
                            analisis = json.loads(json_str)
                        else:
                            raise json.JSONDecodeError("No JSON found", content, 0)
                    except json.JSONDecodeError as e:
                        # Método 4: Intentar parsear JSON con escape de caracteres especiales
                        try:
                            # Limpiar caracteres problemáticos
                            clean_json = content.replace('\r\n', '\\r\\n').replace('\n', '\\n').replace('\r', '\\r')
                            clean_json = clean_json.replace('\t', '\\t')
                            
                            # Buscar y extraer JSON
                            json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                # Reparar JSON común
                                json_str = json_str.replace(",\n}", "\n}")
                                json_str = json_str.replace(", }", " }")
                                json_str = json_str.replace(",]", "]")
                                analisis = json.loads(json_str)
                                logger.info("✅ JSON parseado exitosamente con método 4")
                            else:
                                raise json.JSONDecodeError("No JSON found", content, 0)
                        except json.JSONDecodeError as e2:
                            logger.warning(f"No se pudo parsear respuesta de OpenAI - Error: {str(e2)}")
                            logger.debug(f"Contenido problemático: {content[:300]}...")
                            
                            # Método 5: Extraer campos específicos como último recurso
                            try:
                                import re
                                score_match = re.search(r'"score_final":\s*(\d+)', content)
                                if score_match:
                                    score = int(score_match.group(1))
                                    logger.info(f"Score extraído manualmente: {score}")
                                    
                                    # Crear respuesta mínima
                                    analisis = {
                                        'score_final': score,
                                        'experiencia_directa': False,
                                        'tecnologias_match_porcentaje': 30,
                                        'sector_experiencia_match': False,
                                        'nivel_seniority_apropiado': False,
                                        'fortalezas_especificas': ['Perfil procesado parcialmente'],
                                        'debilidades_detalladas': ['Análisis limitado por error de parsing'],
                                        'recomendacion_detallada': 'Análisis básico realizado',
                                        'justificacion_score': 'Score extraído de respuesta parcial'
                                    }
                                else:
                                    raise Exception("No se pudo extraer información útil")
                            except Exception as fallback_error:
                                logger.warning(f"Fallback manual falló: {fallback_error}")
                                # Usar algoritmo fallback en lugar de valores por defecto
                                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
                
            # ✅ Si llegamos aquí, el JSON se parseó correctamente
            if analisis and isinstance(analisis, dict):
                logger.info("✅ JSON parseado exitosamente de OpenAI")
                
                score = analisis.get('score_final', 35)
                
                # Validaciones MÁS ESTRICTAS
                experiencia_directa = analisis.get('experiencia_directa', False)
                tech_match = analisis.get('tecnologias_match_porcentaje', 0)
                sector_match = analisis.get('sector_experiencia_match', False)
                nivel_apropiado = analisis.get('nivel_seniority_apropiado', False)
                
                # Aplicar límites más estrictos
                if not experiencia_directa and not sector_match:
                    # Sin experiencia directa ni sector = máximo 40%
                    score = min(score, 40)
                    logger.info(f"Score limitado a {score}% - sin experiencia directa ni sector match")
                
                elif not experiencia_directa:
                    # Sin experiencia directa = máximo 55%
                    score = min(score, 55)
                    logger.info(f"Score limitado a {score}% - sin experiencia directa")
                
                if tech_match < 20:
                    # Match tecnológico muy bajo = máximo 45%
                    score = min(score, 45)
                    logger.info(f"Score limitado a {score}% - tech match muy bajo ({tech_match}%)")
                
                elif tech_match < 40:
                    # Match tecnológico bajo = máximo 60%
                    score = min(score, 60)
                    logger.info(f"Score limitado a {score}% - tech match bajo ({tech_match}%)")
                
                if not nivel_apropiado:
                    # Nivel no apropiado = penalización de 10 puntos
                    score = max(score - 10, 5)
                    logger.info(f"Score penalizado a {score}% - nivel no apropiado")
                
                # Asegurar rango válido
                score = max(5, min(score, 95))
                analisis['score_final'] = score
                
                logger.info(f"✅ Análisis detallado: {score}% - Exp.Directa:{experiencia_directa}, Tech:{tech_match}%, Sector:{sector_match}")
                
                # Preparar respuesta más rica
                gap_analysis = analisis.get('gap_analysis', {})
                debilidades = analisis.get('debilidades_detalladas', [])
                
                # Convertir a formato esperado con más información
                analisis_compatible = {
                    'score_final': score,
                    'resumen': f"Compatibilidad: {analisis.get('probabilidad_exito', 'media')} - {analisis.get('recomendacion_detallada', '')[:100]}...",
                    'fortalezas': analisis.get('fortalezas_especificas', [])[:4],
                    'areas_mejora': debilidades[:6],  # Hasta 6 áreas de mejora
                    'recomendacion': analisis.get('recomendacion_detallada', ''),
                    'justificacion': analisis.get('justificacion_score', ''),
                    'experiencia_directa': experiencia_directa,
                    'tecnologias_match': tech_match,
                    'nivel_apropiado': nivel_apropiado,
                    'sector_compatible': sector_match,
                    'gap_tecnologico': gap_analysis.get('tecnologico', ''),
                    'gap_experiencial': gap_analysis.get('experiencial', ''),
                    'tiempo_adaptacion': analisis.get('tiempo_adaptacion', 'no_especificado'),
                    'tecnologias_criticas_faltantes': analisis.get('tecnologias_criticas_faltantes', [])
                }
                
                return score, analisis_compatible
            else:
                logger.warning("No se pudo parsear respuesta de OpenAI - analisis no válido")
                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
                
        except Exception as e:
            logger.error(f"Error llamando OpenAI: {e}")
            raise

    def _algoritmo_matching_mejorado(self, candidato, vacante, habilidades_match):
        """Algoritmo de fallback mejorado con análisis específico si OpenAI no está disponible"""
        
        # Análisis específico manual más estricto
        score_base = 15  # Base más baja para ser más estricto
        
        # 1. Análisis de área laboral específica (MÁS ESTRICTO)
        area_candidato = self._detectar_area_candidato(candidato)
        area_vacante = self._detectar_area_vacante(vacante)
        
        logger.info(f"🔍 Análisis manual estricto: Candidato área '{area_candidato}' vs Vacante área '{area_vacante}'")
        
        if area_candidato == area_vacante:
            score_base += 40  # Mismo sector = gran bonus
            logger.info(f"✅ Misma área laboral: +40 puntos")
        elif self._areas_relacionadas(area_candidato, area_vacante):
            score_base += 20  # Áreas relacionadas = bonus menor
            logger.info(f"🔗 Áreas relacionadas: +20 puntos")
        else:
            score_base += 5   # Diferentes áreas = bonus mínimo
            logger.info(f"❌ Áreas diferentes: +5 puntos")
        
        # 2. Análisis específico de habilidades (MÁS ESTRICTO)
        coincidentes = habilidades_match.get('coincidentes', [])
        total_requeridas = habilidades_match.get('total_requeridas', 1)
        
        if total_requeridas > 0:
            tech_match = (len(coincidentes) / total_requeridas) * 100
            
            # Scoring más estricto para tecnologías
            if tech_match >= 80:
                tech_bonus = 25
            elif tech_match >= 60:
                tech_bonus = 20
            elif tech_match >= 40:
                tech_bonus = 15
            elif tech_match >= 20:
                tech_bonus = 10
            else:
                tech_bonus = 5
                
            score_base += tech_bonus
            logger.info(f"🛠️ Match tecnológico {tech_match:.1f}%: +{tech_bonus} puntos")
        else:
            tech_match = 0
        
        # 3. Análisis de experiencia relevante MÁS DETALLADO
        experiencias = candidato.get('experiencias', [])
        experiencia_relevante = self._evaluar_experiencia_relevante_detallada(experiencias, vacante, area_vacante)
        score_base += experiencia_relevante
        logger.info(f"💼 Experiencia relevante: +{experiencia_relevante} puntos")
        
        # 4. Penalización por mismatch de nivel MÁS ESTRICTA
        nivel_penalty = self._evaluar_nivel_mismatch_estricto(candidato, vacante)
        score_base -= nivel_penalty
        if nivel_penalty > 0:
            logger.info(f"📊 Penalización por nivel: -{nivel_penalty} puntos")
        
        # 5. NUEVAS validaciones estrictas
        experiencia_directa = self._tiene_experiencia_directa(candidato, area_vacante)
        sector_match = area_candidato == area_vacante
        
        # Aplicar límites estrictos como en OpenAI
        if not experiencia_directa and not sector_match:
            score_base = min(score_base, 35)  # Máximo 35%
            logger.info(f"⚠️ Sin experiencia directa ni sector match - limitado a 35%")
        elif not experiencia_directa:
            score_base = min(score_base, 50)  # Máximo 50%
            logger.info(f"⚠️ Sin experiencia directa - limitado a 50%")
        
        if tech_match < 20:
            score_base = min(score_base, 40)  # Máximo 40%
            logger.info(f"⚠️ Tech match muy bajo - limitado a 40%")
        elif tech_match < 40:
            score_base = min(score_base, 55)  # Máximo 55%
            logger.info(f"⚠️ Tech match bajo - limitado a 55%")
        
        # Asegurar rango válido
        score_final = max(5, min(score_base, 85))  # Máximo 85% para fallback
        
        logger.info(f"📊 Score final manual estricto: {score_final}%")
        
        # Generar áreas de mejora detalladas
        areas_mejora = self._generar_areas_mejora_detalladas(candidato, vacante, area_candidato, area_vacante, coincidentes, total_requeridas)
        
        return score_final, {
            "fallback": True, 
            "metodo": "algoritmo_estricto",
            "resumen": f"Análisis manual estricto: {area_candidato} vs {area_vacante} (Tech: {tech_match:.1f}%)",
            "score_final": score_final,
            "area_candidato": area_candidato,
            "area_vacante": area_vacante,
            "tech_match": tech_match,
            "experiencia_directa": experiencia_directa,
            "sector_match": sector_match,
            "areas_mejora": areas_mejora,
            "fortalezas": self._generar_fortalezas_especificas(candidato, coincidentes, area_candidato),
            "recomendacion": self._generar_recomendacion_detallada(score_final, area_candidato, area_vacante, tech_match, experiencia_directa)
        }

    def _evaluar_experiencia_relevante_detallada(self, experiencias, vacante, area_vacante):
        """Evaluar experiencia relevante con más detalle y exigencia"""
        if not experiencias:
            return 0
        
        puntos = 0
        
        for exp in experiencias:
            cargo = exp.get('cargo', '').lower()
            descripcion = exp.get('descripcion', '').lower()
            texto_exp = f"{cargo} {descripcion}"
            
            # Experiencia directa específica (más puntos)
            if area_vacante == 'tecnologia':
                if any(palabra in texto_exp for palabra in ['desarrollador', 'programador', 'software engineer', 'backend', 'frontend']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['sistemas', 'ti', 'informática']):
                    puntos += 6
            elif area_vacante == 'marketing':
                if any(palabra in texto_exp for palabra in ['marketing', 'publicidad', 'digital marketing', 'social media']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['comunicación', 'ventas']):
                    puntos += 6
            elif area_vacante == 'contabilidad':
                if any(palabra in texto_exp for palabra in ['contador', 'contabilidad', 'finanzas', 'auditoría']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['administración', 'gestión']):
                    puntos += 6
            elif area_vacante == 'ventas':
                if any(palabra in texto_exp for palabra in ['ventas', 'comercial', 'vendedor']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['atención cliente', 'marketing']):
                    puntos += 6
            elif area_vacante == 'recursos_humanos':
                if any(palabra in texto_exp for palabra in ['recursos humanos', 'rrhh', 'reclutamiento', 'selección']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['administración', 'gestión']):
                    puntos += 6
            elif area_vacante == 'logistica':
                if any(palabra in texto_exp for palabra in ['logística', 'almacén', 'distribución', 'cadena suministro']):
                    puntos += 12
                elif any(palabra in texto_exp for palabra in ['operaciones', 'inventario']):
                    puntos += 6
            else:
                puntos += 3  # Experiencia general
        
        return min(puntos, 25)  # Máximo 25 puntos

    def _evaluar_nivel_mismatch_estricto(self, candidato, vacante):
        """Evaluar penalización por mismatch de nivel de forma más estricta"""
        experiencias = candidato.get('experiencias', [])
        anos_experiencia = len(experiencias)
        
        titulo_vacante = vacante.get('titulo', '').lower()
        descripcion_vacante = vacante.get('descripcion', '').lower()
        texto_vacante = f"{titulo_vacante} {descripcion_vacante}"
        
        # Detectar nivel requerido con más precisión
        if any(palabra in texto_vacante for palabra in ['senior', 'lead', 'jefe', 'manager', 'director', 'coordinador']):
            nivel_requerido = 'senior'
            anos_requeridos = 5
        elif any(palabra in texto_vacante for palabra in ['junior', 'trainee', 'becario', 'asistente', 'auxiliar']):
            nivel_requerido = 'junior'
            anos_requeridos = 1
        else:
            nivel_requerido = 'mid'
            anos_requeridos = 3
        
        # Calcular penalización más estricta
        if nivel_requerido == 'senior' and anos_experiencia < 4:
            return 20  # Penalización muy fuerte
        elif nivel_requerido == 'senior' and anos_experiencia < 6:
            return 10  # Penalización moderada
        elif nivel_requerido == 'mid' and anos_experiencia < 2:
            return 15  # Penalización fuerte para mid-level
        elif nivel_requerido == 'junior' and anos_experiencia > 8:
            return 8   # Penalización por sobre-cualificación
        elif nivel_requerido == 'junior' and anos_experiencia > 5:
            return 5   # Penalización leve por sobre-cualificación
        
        return 0

    def _tiene_experiencia_directa(self, candidato, area_vacante):
        """Verificar si tiene experiencia directa en el área específica"""
        experiencias = candidato.get('experiencias', [])
        
        for exp in experiencias:
            cargo = exp.get('cargo', '').lower()
            descripcion = exp.get('descripcion', '').lower()
            texto_exp = f"{cargo} {descripcion}"
            
            if area_vacante == 'tecnologia' and any(palabra in texto_exp for palabra in ['desarrollador', 'programador', 'software']):
                return True
            elif area_vacante == 'marketing' and any(palabra in texto_exp for palabra in ['marketing', 'publicidad']):
                return True
            elif area_vacante == 'contabilidad' and any(palabra in texto_exp for palabra in ['contador', 'contabilidad']):
                return True
            elif area_vacante == 'ventas' and any(palabra in texto_exp for palabra in ['ventas', 'comercial']):
                return True
            elif area_vacante == 'recursos_humanos' and any(palabra in texto_exp for palabra in ['recursos humanos', 'rrhh']):
                return True
            elif area_vacante == 'logistica' and any(palabra in texto_exp for palabra in ['logística', 'almacén']):
                return True
        
        return False

    def _generar_areas_mejora_detalladas(self, candidato, vacante, area_candidato, area_vacante, coincidentes, total_requeridas):
        """Generar áreas de mejora específicas y detalladas"""
        areas_mejora = []
        
        # 1. Área laboral
        if area_candidato != area_vacante:
            areas_mejora.append(f"Falta de experiencia directa en {area_vacante.replace('_', ' ')} - el candidato viene del área de {area_candidato.replace('_', ' ')}")
        
        # 2. Tecnologías faltantes
        if total_requeridas > 0:
            tech_match_pct = (len(coincidentes) / total_requeridas) * 100
            if tech_match_pct < 50:
                areas_mejora.append(f"Déficit significativo en tecnologías requeridas - solo maneja {len(coincidentes)} de {total_requeridas} herramientas necesarias")
        
        # 3. Análisis específico por vacante
        titulo_vacante = vacante.get('titulo', '').lower()
        descripcion_vacante = vacante.get('descripcion', '').lower()
        
        if 'senior' in f"{titulo_vacante} {descripcion_vacante}":
            anos_exp = len(candidato.get('experiencias', []))
            if anos_exp < 5:
                areas_mejora.append(f"Insuficiente experiencia para rol senior - tiene {anos_exp} años, se requieren 5+ años")
        
        if area_vacante == 'tecnologia':
            areas_mejora.append("Necesita certificaciones técnicas específicas para el stack tecnológico requerido")
            if 'python' not in titulo_vacante.lower() and any('python' in exp.get('descripcion', '').lower() for exp in candidato.get('experiencias', [])):
                areas_mejora.append("Experiencia principalmente en Python, pero la vacante requiere otras tecnologías")
        
        elif area_vacante == 'marketing':
            areas_mejora.append("Requiere experiencia práctica en campañas de marketing digital y análisis de métricas")
            areas_mejora.append("Falta conocimiento en herramientas de marketing automation y CRM")
        
        elif area_vacante == 'contabilidad':
            areas_mejora.append("Necesita certificación contable y conocimiento de normativas fiscales vigentes")
            areas_mejora.append("Falta experiencia en software contable especializado (SAP, ContPAQ, etc.)")
        
        elif area_vacante == 'ventas':
            areas_mejora.append("Requiere desarrollo de habilidades de negociación y cierre de ventas")
            areas_mejora.append("Falta experiencia en manejo de CRM y técnicas de prospección")
        
        elif area_vacante == 'logistica':
            areas_mejora.append("Necesita conocimiento en sistemas de gestión de almacenes (WMS)")
            areas_mejora.append("Falta experiencia en optimización de cadena de suministro")
        
        # 4. Soft skills específicos
        areas_mejora.append(f"Requiere desarrollar habilidades específicas para liderazgo en {area_vacante.replace('_', ' ')}")
        
        return areas_mejora[:6]  # Máximo 6 áreas de mejora

    def _generar_fortalezas_especificas(self, candidato, coincidentes, area_candidato):
        """Generar fortalezas específicas basadas en el perfil"""
        fortalezas = []
        
        # Fortalezas basadas en experiencias
        experiencias = candidato.get('experiencias', [])
        
        if area_candidato == 'tecnologia':
            fortalezas.append("Experiencia sólida en desarrollo de software")
            if any('python' in exp.get('descripcion', '').lower() for exp in experiencias):
                fortalezas.append("Dominio comprobado de Python para desarrollo")
        elif area_candidato == 'marketing':
            fortalezas.append("Conocimiento en estrategias de marketing")
        elif area_candidato == 'contabilidad':
            fortalezas.append("Base sólida en principios contables")
        
        # Fortalezas por tecnologías coincidentes
        if len(coincidentes) >= 3:
            fortalezas.append(f"Maneja {len(coincidentes)} tecnologías relevantes: {', '.join(coincidentes[:3])}")
        elif len(coincidentes) > 0:
            fortalezas.append(f"Conocimiento en: {', '.join(coincidentes)}")
        
        # Fortalezas generales
        if len(experiencias) >= 3:
            fortalezas.append("Experiencia laboral diversa y adaptabilidad")
        
        educaciones = candidato.get('educaciones', [])
        if educaciones:
            fortalezas.append("Formación académica sólida")
        
        return fortalezas[:4]  # Máximo 4 fortalezas

    def _generar_recomendacion_detallada(self, score, area_candidato, area_vacante, tech_match, experiencia_directa):
        """Generar recomendación específica basada en el análisis"""
        
        if score >= 70:
            return f"Candidato muy recomendable para la posición. Con experiencia directa en {area_vacante.replace('_', ' ')} y buen match tecnológico ({tech_match:.1f}%), puede integrarse rápidamente al equipo."
        
        elif score >= 50:
            if experiencia_directa:
                return f"Candidato aceptable con potencial. Aunque tiene experiencia en {area_vacante.replace('_', ' ')}, necesita capacitación en tecnologías específicas para optimizar su rendimiento."
            else:
                return f"Candidato con potencial pero requiere inversión significativa en capacitación. Su experiencia en {area_candidato.replace('_', ' ')} puede ser transferible con el entrenamiento adecuado."
        
        elif score >= 30:
            return f"Candidato marginal. La diferencia entre su perfil ({area_candidato.replace('_', ' ')}) y los requisitos ({area_vacante.replace('_', ' ')}) requiere capacitación extensiva. Considerar solo si no hay mejores opciones."
        
        else:
            return f"No recomendado para esta posición. El candidato está especializado en {area_candidato.replace('_', ' ')} mientras que la vacante requiere experiencia en {area_vacante.replace('_', ' ')}. Buscar candidatos con perfil más alineado."

    def _detectar_area_candidato(self, candidato):
        """Detectar área laboral principal del candidato basada en experiencias"""
        experiencias = candidato.get('experiencias', [])
        titulo_prof = candidato.get('titulo_profesional', '').lower()
        
        # Contar menciones por área
        areas_contador = {
            'tecnologia': 0,
            'marketing': 0,
            'ventas': 0,
            'contabilidad': 0,
            'recursos_humanos': 0,
            'logistica': 0,
            'educacion': 0,
            'salud': 0,
            'general': 0
        }
        
        # Analizar título profesional
        if any(palabra in titulo_prof for palabra in ['desarrollador', 'programador', 'ingeniero', 'software', 'sistemas']):
            areas_contador['tecnologia'] += 3
        elif any(palabra in titulo_prof for palabra in ['marketing', 'publicidad', 'digital']):
            areas_contador['marketing'] += 3
        elif any(palabra in titulo_prof for palabra in ['contador', 'contable', 'finanzas']):
            areas_contador['contabilidad'] += 3
        elif any(palabra in titulo_prof for palabra in ['vendedor', 'ventas', 'comercial']):
            areas_contador['ventas'] += 3
        elif any(palabra in titulo_prof for palabra in ['rrhh', 'recursos humanos', 'talento']):
            areas_contador['recursos_humanos'] += 3
        
        # Analizar experiencias
        for exp in experiencias:
            cargo = exp.get('cargo', '').lower()
            descripcion = exp.get('descripcion', '').lower()
            texto_completo = f"{cargo} {descripcion}"
            
            if any(palabra in texto_completo for palabra in ['desarrollador', 'programador', 'python', 'javascript', 'software', 'backend', 'frontend']):
                areas_contador['tecnologia'] += 2
            elif any(palabra in texto_completo for palabra in ['marketing', 'publicidad', 'social media', 'digital', 'campaña']):
                areas_contador['marketing'] += 2
            elif any(palabra in texto_completo for palabra in ['ventas', 'vendedor', 'comercial', 'cliente']):
                areas_contador['ventas'] += 2
            elif any(palabra in texto_completo for palabra in ['contador', 'contabilidad', 'facturación', 'impuestos', 'finanzas']):
                areas_contador['contabilidad'] += 2
            elif any(palabra in texto_completo for palabra in ['recursos humanos', 'rrhh', 'selección', 'reclutamiento']):
                areas_contador['recursos_humanos'] += 2
            elif any(palabra in texto_completo for palabra in ['logística', 'almacén', 'distribución', 'inventario']):
                areas_contador['logistica'] += 2
            else:
                areas_contador['general'] += 1
        
        # Retornar área con mayor puntuación
        area_principal = max(areas_contador, key=areas_contador.get)
        puntuacion_max = areas_contador[area_principal]
        
        logger.info(f"🎯 Área detectada candidato: {area_principal} (puntuación: {puntuacion_max})")
        return area_principal if puntuacion_max > 0 else 'general'

    def _detectar_area_vacante(self, vacante):
        """Detectar área laboral de la vacante basada en título y descripción"""
        titulo = vacante.get('titulo', '').lower()
        descripcion = vacante.get('descripcion', '').lower()
        categoria = vacante.get('categoria', '').lower()
        texto_completo = f"{titulo} {descripcion} {categoria}"
        
        # Mapeo directo por categoría
        if 'tecnologia' in categoria:
            return 'tecnologia'
        elif 'marketing' in categoria:
            return 'marketing'
        elif 'finanzas' in categoria:
            return 'contabilidad'
        elif 'ventas' in categoria:
            return 'ventas'
        elif 'recursos_humanos' in categoria:
            return 'recursos_humanos'
        elif 'logistica' in categoria:
            return 'logistica'
        
        # Análisis por contenido
        if any(palabra in texto_completo for palabra in ['desarrollador', 'programador', 'python', 'javascript', 'software', 'backend', 'frontend', 'react', 'django']):
            return 'tecnologia'
        elif any(palabra in texto_completo for palabra in ['marketing', 'publicidad', 'social media', 'digital', 'campaña', 'redes sociales']):
            return 'marketing'
        elif any(palabra in texto_completo for palabra in ['ventas', 'vendedor', 'comercial', 'cliente', 'venta']):
            return 'ventas'
        elif any(palabra in texto_completo for palabra in ['contador', 'contabilidad', 'facturación', 'impuestos', 'finanzas', 'contable']):
            return 'contabilidad'
        elif any(palabra in texto_completo for palabra in ['recursos humanos', 'rrhh', 'selección', 'reclutamiento', 'talento']):
            return 'recursos_humanos'
        elif any(palabra in texto_completo for palabra in ['logística', 'almacén', 'distribución', 'inventario', 'logistica']):
            return 'logistica'
        else:
            return 'general'

    def _areas_relacionadas(self, area1, area2):
        """Verificar si dos áreas están relacionadas"""
        relacionadas = {
            'tecnologia': ['general'],
            'marketing': ['ventas', 'general'],
            'ventas': ['marketing', 'general'],
            'contabilidad': ['general'],
            'recursos_humanos': ['general'],
            'logistica': ['general']
        }
        
        return area2 in relacionadas.get(area1, []) or area1 in relacionadas.get(area2, [])

    def _evaluar_experiencia_relevante(self, experiencias, vacante):
        """Evaluar qué tan relevante es la experiencia para esta vacante específica"""
        if not experiencias:
            return 0
        
        area_vacante = self._detectar_area_vacante(vacante)
        puntos = 0
        
        for exp in experiencias:
            cargo = exp.get('cargo', '').lower()
            descripcion = exp.get('descripcion', '').lower()
            
            # Experiencia directa en el área
            if area_vacante == 'tecnologia' and any(palabra in f"{cargo} {descripcion}" for palabra in ['desarrollador', 'programador', 'software']):
                puntos += 8
            elif area_vacante == 'marketing' and any(palabra in f"{cargo} {descripcion}" for palabra in ['marketing', 'publicidad', 'digital']):
                puntos += 8
            elif area_vacante == 'contabilidad' and any(palabra in f"{cargo} {descripcion}" for palabra in ['contador', 'contabilidad', 'finanzas']):
                puntos += 8
            elif area_vacante == 'ventas' and any(palabra in f"{cargo} {descripcion}" for palabra in ['ventas', 'comercial', 'vendedor']):
                puntos += 8
            else:
                puntos += 2  # Experiencia general
        
        return min(puntos, 20)  # Máximo 20 puntos

    def _evaluar_nivel_mismatch(self, candidato, vacante):
        """Evaluar penalización por mismatch de nivel"""
        experiencias = candidato.get('experiencias', [])
        anos_experiencia = len(experiencias)
        
        titulo_vacante = vacante.get('titulo', '').lower()
        descripcion_vacante = vacante.get('descripcion', '').lower()
        
        # Detectar nivel requerido
        if any(palabra in f"{titulo_vacante} {descripcion_vacante}" for palabra in ['senior', 'lead', 'jefe', 'manager']):
            nivel_requerido = 'senior'
            anos_requeridos = 5
        elif any(palabra in f"{titulo_vacante} {descripcion_vacante}" for palabra in ['junior', 'trainee', 'becario']):
            nivel_requerido = 'junior'
            anos_requeridos = 1
        else:
            nivel_requerido = 'mid'
            anos_requeridos = 3
        
        # Calcular penalización
        if nivel_requerido == 'senior' and anos_experiencia < 3:
            return 15  # Penalización fuerte por falta experiencia
        elif nivel_requerido == 'junior' and anos_experiencia > 6:
            return 5   # Penalización leve por sobre-cualificación
        
        return 0

    def calcular_habilidades_match(self, candidato: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Calcular match de habilidades entre candidato y vacante"""
        try:
            # Extraer habilidades del candidato
            habilidades_candidato = self._extraer_habilidades_candidato(candidato)
            
            # Extraer habilidades de la vacante
            descripcion_vacante = vacante.get('descripcion', '') + ' ' + vacante.get('titulo', '')
            habilidades_vacante = self._extraer_habilidades_descripcion(descripcion_vacante)
            
            # También incluir habilidades_requeridas si existen
            if vacante.get('habilidades_requeridas'):
                habilidades_vacante.extend(vacante['habilidades_requeridas'])
            
            # Filtrar valores None y vacíos, y eliminar duplicados
            habilidades_candidato = [h for h in habilidades_candidato if h and str(h).strip()]
            habilidades_vacante = [h for h in habilidades_vacante if h and str(h).strip()]
            habilidades_vacante = list(set(habilidades_vacante))
            
            # Buscar coincidencias exactas y similares
            coincidentes = []
            faltantes = []
            
            for hab_vacante in habilidades_vacante:
                # Validar que hab_vacante no sea None
                if not hab_vacante:
                    continue
                    
                encontrado = False
                
                # Buscar coincidencia exacta
                for hab_candidato in habilidades_candidato:
                    # Validar que hab_candidato no sea None
                    if not hab_candidato:
                        continue
                        
                    if str(hab_vacante).lower() == str(hab_candidato).lower():
                        coincidentes.append(hab_candidato)
                        encontrado = True
                        break
                
                # Si no hay coincidencia exacta, buscar similares
                if not encontrado:
                    for hab_candidato in habilidades_candidato:
                        # Validar que hab_candidato no sea None
                        if not hab_candidato:
                            continue
                            
                        hab_vacante_lower = str(hab_vacante).lower()
                        hab_candidato_lower = str(hab_candidato).lower()
                        
                        if (hab_vacante_lower in hab_candidato_lower or 
                            hab_candidato_lower in hab_vacante_lower or
                            self._son_habilidades_relacionadas(hab_vacante, hab_candidato)):
                            coincidentes.append(f"{hab_candidato} (similar a {hab_vacante})")
                            encontrado = True
                            break
                
                # Si no se encontró, es faltante
                if not encontrado:
                    faltantes.append(hab_vacante)
            
            # Calcular porcentaje de match
            total_requeridas = len(habilidades_vacante) if habilidades_vacante else 1
            match_percentage = (len(coincidentes) / total_requeridas) * 100
            
            return {
                'coincidentes': list(set(coincidentes)),  # Eliminar duplicados
                'faltantes': faltantes,
                'habilidades_candidato': habilidades_candidato,
                'habilidades_vacante': habilidades_vacante,
                'match_percentage': min(match_percentage, 100),
                'total_coincidencias': len(set(coincidentes)),
                'total_requeridas': total_requeridas
            }
            
        except Exception as e:
            logger.error(f"Error calculando match de habilidades: {e}")
            return {
                'coincidentes': [],
                'faltantes': [],
                'habilidades_candidato': [],
                'habilidades_vacante': [],
                'match_percentage': 0,
                'total_coincidencias': 0,
                'total_requeridas': 0
            }

    def detectar_area_laboral_vacante(self, vacante):
        """Detecta el área laboral de una vacante específicamente"""
        texto_analisis = f"{vacante.get('titulo', '')} {vacante.get('descripcion', '')} {vacante.get('categoria', '')}".lower()
        
        # Buscar matches específicos
        for area, keywords in self.config.areas_laborales.items():
            for keyword in keywords:
                if keyword in texto_analisis:
                    return area
        
        return "general"
    
    def areas_compatibles(self, area1, area2):
        """Define qué áreas laborales son compatibles entre sí"""
        compatibilidades = {
            "administracion": ["contabilidad", "ventas", "recursos_humanos"],
            "contabilidad": ["administracion", "finanzas"],
            "ventas": ["marketing", "comercial", "administracion"],
            "marketing": ["ventas", "comunicacion"],
            "logistica": ["operaciones", "almacen"],
            "operaciones": ["logistica", "manufactura"],
            "tecnologia": ["sistemas", "desarrollo"],
            "eventos": ["marketing", "administracion"],
            "seguridad": ["higiene_seguridad"]
        }
        
        return (area2 in compatibilidades.get(area1, []) or 
                area1 in compatibilidades.get(area2, []))

    def verificar_compatibilidad_ubicacion(self, candidato, vacante):
        """Verifica si la ubicación del candidato es compatible con la vacante"""
        ubicacion_candidato = candidato.get('ciudad', '').lower()
        ubicacion_vacante = vacante.get('ubicacion', '').lower()
        modalidad = vacante.get('modalidad', vacante.get('tipo_empleo', '')).lower()
        
        # Si es remoto, siempre compatible
        if 'remoto' in modalidad or 'home' in modalidad:
            return True
        
        # Si las ciudades coinciden exactamente
        if ubicacion_candidato == ubicacion_vacante:
            return True
        
        # Si una contiene a la otra (ej: "ciudad de mexico" vs "mexico")
        if ubicacion_candidato in ubicacion_vacante or ubicacion_vacante in ubicacion_candidato:
            return True
        
        return False
    
    def analizar_requisitos_educativos(self, candidato, vacante):
        """Analiza cuántos requisitos educativos cumple el candidato"""
        descripcion = vacante.get('descripcion', '').lower()
        requisitos_cumplidos = 0
        
        # Verificar licenciatura
        if 'licenciatura' in descripcion or 'carrera' in descripcion:
            if self._candidato_tiene_licenciatura(candidato):
                requisitos_cumplidos += 1
        
        # Verificar ingeniería
        if 'ingenier' in descripcion:
            if self._candidato_tiene_ingenieria(candidato):
                requisitos_cumplidos += 1
        
        # Verificar maestría
        if 'maestria' in descripcion or 'posgrado' in descripcion:
            if self._candidato_tiene_maestria(candidato):
                requisitos_cumplidos += 1
        
        # Verificar años de experiencia
        anos_requeridos = self._extraer_anos_experiencia_requeridos(descripcion)
        anos_candidato = len(candidato.get('experiencias', []))
        if anos_requeridos > 0 and anos_candidato >= anos_requeridos:
            requisitos_cumplidos += 1
        
        return requisitos_cumplidos

    def _analizar_match_con_openai_rapido(self, candidato_text, vacante_text, habilidades_match, candidato=None, vacante=None):
        """Análisis rápido con OpenAI con timeout reducido y prompt optimizado"""
        
        # Información básica para prompt más corto
        habilidades_candidato = habilidades_match.get('habilidades_candidato', [])[:8]  # Solo top 8
        habilidades_vacante = habilidades_match.get('habilidades_vacante', [])[:8]  # Solo top 8
        coincidentes = habilidades_match.get('coincidentes', [])[:5]  # Solo top 5
        
        # Prompt optimizado más corto
        prompt = f"""
Analiza rápidamente esta compatibilidad candidato-vacante:

CANDIDATO: {candidato_text[:800]}...
VACANTE: {vacante_text[:800]}...

HABILIDADES:
- Candidato: {', '.join(habilidades_candidato)}
- Vacante necesita: {', '.join(habilidades_vacante)}
- Coincidencias: {', '.join(coincidentes)}

RESPONDE SOLO JSON:
{{
    "score_final": numero_0_100,
    "experiencia_directa": true/false,
    "tecnologias_match_porcentaje": numero_0_100,
    "fortalezas_especificas": ["fortaleza1", "fortaleza2"],
    "debilidades_detalladas": ["debilidad1", "debilidad2"],
    "recomendacion_detallada": "texto_corto"
}}
        """
        
        try:
            # Llamar a OpenAI con timeout muy reducido
            response = self.ai_processor.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un reclutador experto. Responde SOLO JSON, sin texto adicional."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,  # Reducido para respuestas más rápidas
                temperature=0.1,
                timeout=5.0  # Timeout de 5 segundos
            )
            
            # Parsear respuesta rápido
            content = response.choices[0].message.content.strip()
            
            # Parsing JSON optimizado
            import json
            import re
            
            # Intentar parsing directo
            try:
                analisis = json.loads(content)
            except json.JSONDecodeError:
                # Fallback rápido - buscar JSON en el texto
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        analisis = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        # Si falla, usar algoritmo fallback
                        logger.warning("OpenAI parsing falló - usando fallback rápido")
                        return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
                else:
                    logger.warning("No se encontró JSON en respuesta OpenAI")
                    return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
            # Validar datos mínimos
            if not isinstance(analisis, dict) or 'score_final' not in analisis:
                logger.warning("Respuesta OpenAI inválida - usando fallback")
                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
            score = analisis.get('score_final', 35)
            
            # Crear respuesta optimizada
            analisis_compatible = {
                "fallback": False,
                "metodo": "openai_rapido",
                "score_final": score,
                "experiencia_directa": analisis.get('experiencia_directa', False),
                "tecnologias_match": analisis.get('tecnologias_match_porcentaje', 0),
                "fortalezas": analisis.get('fortalezas_especificas', [])[:3],
                "debilidades": analisis.get('debilidades_detalladas', [])[:2],
                "recomendacion": analisis.get('recomendacion_detallada', f"Match de {score}%")
            }
            
            return score, analisis_compatible
            
        except Exception as e:
            logger.warning(f"Error en OpenAI rápido: {e}")
            return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)

    def _analizar_match_con_openai_mejorado(self, candidato_text, vacante_text, habilidades_match, candidato=None, vacante=None):
        """Análisis mejorado con OpenAI para matching más preciso y diferenciado"""
        
        # Información adicional del análisis de habilidades
        habilidades_candidato = habilidades_match.get('habilidades_candidato', [])
        habilidades_vacante = habilidades_match.get('habilidades_vacante', [])
        coincidentes = habilidades_match.get('coincidentes', [])
        faltantes = habilidades_match.get('faltantes', [])
        
        prompt = f"""
Eres un reclutador SENIOR con 15 años de experiencia. Analiza DETALLADAMENTE la compatibilidad entre este candidato y esta vacante ESPECÍFICA. 

CANDIDATO:
{candidato_text}

VACANTE ESPECÍFICA:
{vacante_text}

ANÁLISIS TÉCNICO PREVIO:
- Habilidades del candidato: {', '.join(habilidades_candidato[:15])}
- Habilidades requeridas: {', '.join(habilidades_vacante[:15])}
- Coincidencias encontradas: {', '.join(coincidentes[:8])}
- Tecnologías/skills faltantes: {', '.join(faltantes[:10])}

INSTRUCCIONES CRÍTICAS PARA ANÁLISIS EXHAUSTIVO:

1. **EVALÚA EXPERIENCIA DIRECTA**: ¿Ha trabajado específicamente en este tipo de rol/industria?
2. **ANALIZA TECNOLOGÍAS ESPECÍFICAS**: ¿Maneja las herramientas exactas que pide la vacante?
3. **EVALÚA NIVEL DE SENIORITY**: ¿Su experiencia coincide con el nivel requerido?
4. **CONSIDERA SECTOR/INDUSTRIA**: ¿Tiene experiencia en este sector específico?
5. **ANALIZA SOFT SKILLS**: ¿Tiene las habilidades blandas necesarias para este rol?

CRITERIOS ESPECÍFICOS DE SCORING (SÉ MUY ESTRICTO):

📊 **SCORING ESPECÍFICO POR TIPO DE MATCH**:
- **MATCH PERFECTO (85-95%)**: Experiencia directa + todas las tecnologías + mismo nivel
- **MATCH EXCELENTE (70-84%)**: Experiencia directa + mayoría tecnologías + nivel apropiado  
- **MATCH BUENO (55-69%)**: Experiencia relacionada + algunas tecnologías + nivel cercano
- **MATCH REGULAR (35-54%)**: Experiencia transferible + pocas tecnologías + nivel diferente
- **MATCH BAJO (20-34%)**: Experiencia no relacionada + tecnologías diferentes + sector diferente
- **NO MATCH (5-19%)**: Completamente incompatible, diferentes industrias/roles

🎯 **EJEMPLOS ESPECÍFICOS DE SCORING CORRECTO**:
- Desarrollador Python Senior + Vacante Python Senior = 80-90%
- Desarrollador Python + Vacante React (sin Python) = 25-40%
- Desarrollador + Vacante Marketing = 10-25%
- Contador + Vacante Contabilidad = 75-85%
- Contador + Vacante Desarrollo = 5-20%
- Junior (1 año) + Vacante Senior (5+ años) = 30-45%
- Ingeniero Procesos + Vacante Desarrollo IA = 15-30%

RESPONDE CON ANÁLISIS DETALLADO ESPECÍFICO PARA ESTA VACANTE:
{{
    "score_final": [NÚMERO_ENTRE_5_Y_95_MUY_ESPECÍFICO],
    "experiencia_directa": [true/false],
    "anos_experiencia_relevante": [número de años en roles similares],
    "tecnologias_match_porcentaje": [0-100],
    "tecnologias_criticas_faltantes": ["tech1", "tech2", "tech3"],
    "nivel_seniority_apropiado": [true/false],
    "sector_experiencia_match": [true/false],
    "fortalezas_especificas": [
        "Fortaleza específica 1 para este rol exacto",
        "Fortaleza específica 2 detallada",
        "Fortaleza específica 3 con contexto",
        "Fortaleza específica 4 si aplica"
    ],
    "debilidades_detalladas": [
        "Falta de experiencia específica en [área exacta requerida]",
        "No maneja [tecnología crítica específica] requerida para [función específica]",
        "Nivel de experiencia insuficiente para responsabilidades de [área específica]",
        "Sin conocimiento en [herramienta/proceso específico] necesario para [tarea específica]",
        "Falta de experiencia en [industria/sector específico] que maneja [procesos específicos]"
    ],
    "gap_analysis": {{
        "tecnologico": "Descripción detallada de brechas tecnológicas específicas",
        "experiencial": "Descripción de falta de experiencia en áreas críticas", 
        "sectorial": "Descripción de diferencias de sector/industria",
        "nivel": "Descripción de diferencias de nivel de responsabilidad"
    }},
    "recomendacion_detallada": "Recomendación específica y detallada considerando esta vacante exacta y el perfil del candidato",
    "justificacion_score": "Explicación detallada del POR QUÉ este score específico, mencionando experiencias concretas y requisitos específicos no cumplidos",
    "probabilidad_exito": "muy_alta/alta/media/baja/muy_baja",
    "tiempo_adaptacion": "inmediato/1-3_meses/3-6_meses/6-12_meses/no_viable"
}}

IMPORTANTE: 
- El score debe ser MUY ESPECÍFICO y DIFERENTE para cada vacante
- Las debilidades deben ser DETALLADAS y ESPECÍFICAS para esta vacante exacta
- NO uses respuestas genéricas - cada análisis debe ser único
- SÉ REALISTA: Un desarrollador NO puede ser 60%+ compatible con roles de logística/eventos/finanzas
"""
        
        try:
            # Llamar a OpenAI con timeout muy reducido
            response = self.ai_processor.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un reclutador experto. Responde SOLO JSON, sin texto adicional."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,  # Reducido para respuestas más rápidas
                temperature=0.1,
                timeout=5.0  # Timeout de 5 segundos
            )
            
            # Parsear respuesta rápido
            content = response.choices[0].message.content.strip()
            
            # Parsing JSON optimizado
            import json
            import re
            
            # Intentar parsing directo
            try:
                analisis = json.loads(content)
            except json.JSONDecodeError:
                # Fallback rápido - buscar JSON en el texto
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        analisis = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        # Si falla, usar algoritmo fallback
                        logger.warning("OpenAI parsing falló - usando fallback rápido")
                        return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
                else:
                    logger.warning("No se encontró JSON en respuesta OpenAI")
                    return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
            # Validar datos mínimos
            if not isinstance(analisis, dict) or 'score_final' not in analisis:
                logger.warning("Respuesta OpenAI inválida - usando fallback")
                return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)
            
            score = analisis.get('score_final', 35)
            
            # Crear respuesta optimizada
            analisis_compatible = {
                "fallback": False,
                "metodo": "openai_rapido",
                "score_final": score,
                "experiencia_directa": analisis.get('experiencia_directa', False),
                "tecnologias_match": analisis.get('tecnologias_match_porcentaje', 0),
                "fortalezas": analisis.get('fortalezas_especificas', [])[:3],
                "debilidades": analisis.get('debilidades_detalladas', [])[:2],
                "recomendacion": analisis.get('recomendacion_detallada', f"Match de {score}%")
            }
            
            return score, analisis_compatible
            
        except Exception as e:
            logger.warning(f"Error en OpenAI rápido: {e}")
            return self._algoritmo_matching_mejorado(candidato, vacante, habilidades_match)





# Instancia global del servicio
matching_service = MatchingService() 
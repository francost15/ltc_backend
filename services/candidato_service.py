"""
Servicio para operaciones de candidatos
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from psycopg.rows import dict_row
from utils.database import get_db_manager
from utils.pdf_processor import document_processor
from utils.ai_processor import cv_analyzer

logger = logging.getLogger(__name__)

class CandidatoService:
    """Servicio para gestión de candidatos"""
    
    def __init__(self):
        self.db = get_db_manager()
    
    def get_candidato_by_usuario_id(self, usuario_id: str) -> Optional[Dict[str, Any]]:
        """Obtener candidato por ID de usuario con una sola conexión"""
        try:
            # Usar una sola conexión para todas las consultas
            with self.db.get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    # Obtener candidato básico
                    cursor.execute("""
                        SELECT c.*, u.email
                        FROM candidatos c
                        JOIN usuarios u ON c.usuario_id = u.id
                        WHERE c.usuario_id = %s
                    """, (usuario_id,))
                    
                    candidatos = cursor.fetchall()
                    if not candidatos:
                        return None
                    
                    candidato = dict(candidatos[0])
                    candidato_id = candidato['id']
                    
                    # Obtener experiencias
                    cursor.execute("""
                        SELECT * FROM experiencias 
                        WHERE candidato_id = %s 
                        ORDER BY fecha_inicio DESC
                    """, (candidato_id,))
                    candidato['experiencias'] = [dict(row) for row in cursor.fetchall()]
                    
                    # Obtener educaciones
                    cursor.execute("""
                        SELECT * FROM educaciones 
                        WHERE candidato_id = %s 
                        ORDER BY fecha_inicio DESC
                    """, (candidato_id,))
                    candidato['educaciones'] = [dict(row) for row in cursor.fetchall()]
                    
                    # Obtener certificaciones
                    cursor.execute("""
                        SELECT * FROM certificaciones 
                        WHERE candidato_id = %s 
                        ORDER BY anio_obtencion DESC
                    """, (candidato_id,))
                    candidato['certificaciones'] = [dict(row) for row in cursor.fetchall()]
                    
                    # Obtener idiomas
                    cursor.execute("""
                        SELECT * FROM idiomas 
                        WHERE candidato_id = %s
                    """, (candidato_id,))
                    candidato['idiomas'] = [dict(row) for row in cursor.fetchall()]
                    
                    # Obtener preferencias
                    cursor.execute("""
                        SELECT * FROM preferencias_empleo 
                        WHERE candidato_id = %s
                    """, (candidato_id,))
                    preferencias = cursor.fetchall()
                    candidato['preferencias'] = dict(preferencias[0]) if preferencias else None
                    
                    return candidato
            
        except Exception as e:
            logger.error(f"Error obteniendo candidato: {e}")
            raise
    
    def _get_experiencias(self, candidato_id: str) -> List[Dict[str, Any]]:
        """Obtener experiencias del candidato"""
        query = "SELECT * FROM experiencias WHERE candidato_id = %s ORDER BY fecha_inicio DESC"
        return self.db.execute_query(query, (candidato_id,))
    
    def _get_educaciones(self, candidato_id: str) -> List[Dict[str, Any]]:
        """Obtener educaciones del candidato"""
        query = "SELECT * FROM educaciones WHERE candidato_id = %s ORDER BY fecha_inicio DESC"
        return self.db.execute_query(query, (candidato_id,))
    
    def _get_certificaciones(self, candidato_id: str) -> List[Dict[str, Any]]:
        """Obtener certificaciones del candidato"""
        query = "SELECT * FROM certificaciones WHERE candidato_id = %s ORDER BY anio_obtencion DESC"
        return self.db.execute_query(query, (candidato_id,))
    
    def _get_idiomas(self, candidato_id: str) -> List[Dict[str, Any]]:
        """Obtener idiomas del candidato"""
        query = "SELECT * FROM idiomas WHERE candidato_id = %s"
        return self.db.execute_query(query, (candidato_id,))
    
    def _get_preferencias(self, candidato_id: str) -> Optional[Dict[str, Any]]:
        """Obtener preferencias del candidato"""
        query = "SELECT * FROM preferencias_empleo WHERE candidato_id = %s"
        preferencias = self.db.execute_query(query, (candidato_id,))
        return preferencias[0] if preferencias else None
    
    def process_cv_upload(self, usuario_id: str, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Procesar CV subido y actualizar información del candidato"""
        try:
            # 1. Verificar que existe el candidato
            candidato = self.get_candidato_by_usuario_id(usuario_id)
            if not candidato:
                raise Exception("Candidato no encontrado")
            
            # 2. Extraer texto del documento
            logger.info(f"Extrayendo texto de {filename}")
            cv_text = document_processor.extract_text(file_content, filename)
            
            # 3. Analizar CV con IA
            logger.info("Analizando CV con IA")
            if cv_analyzer:
                analyzed_data = cv_analyzer.analyze_cv_with_ai(cv_text)
            else:
                logger.warning("CV Analyzer no disponible, usando análisis básico")
                # Análisis básico como fallback
                analyzed_data = {
                    "informacion_personal": {
                        "nombre": None,
                        "telefono": None,
                        "ciudad": None,
                        "pais": None,
                        "linkedin_url": None,
                        "portfolio_url": None,
                        "titulo_profesional": None,
                        "resumen_profesional": None
                    },
                    "experiencias": [],
                    "educaciones": [],
                    "certificaciones": [],
                    "idiomas": []
                }
            
            # 4. Actualizar información del candidato
            self._update_candidato_info(candidato['id'], analyzed_data)
            
            # 5. Guardar documento (opcional - para histórico)
            # Se podría implementar una tabla de documentos si se requiere
            
            return {
                "success": True,
                "message": "CV procesado exitosamente",
                "candidato_id": candidato['id'],
                "data_extracted": analyzed_data
            }
            
        except Exception as e:
            logger.error(f"Error procesando CV: {e}")
            raise
    
    def _update_candidato_info(self, candidato_id: str, analyzed_data: Dict[str, Any]) -> None:
        """Actualizar información del candidato con datos analizados - REEMPLAZAR COMPLETAMENTE"""
        try:
            logger.info(f"🔄 Limpiando información existente del candidato {candidato_id}")
            
            # 🗑️ PASO 1: BORRAR TODA LA INFORMACIÓN EXISTENTE
            self._clear_candidato_data(candidato_id)
            
            logger.info(f"✨ Agregando nueva información del CV para candidato {candidato_id}")
            
            # 📝 PASO 2: AGREGAR NUEVA INFORMACIÓN
            # Actualizar información personal
            info_personal = analyzed_data.get('informacion_personal', {})
            if info_personal:
                self._update_personal_info(candidato_id, info_personal)
            
            # Insertar experiencias
            experiencias = analyzed_data.get('experiencias', [])
            for exp in experiencias:
                self._insert_experiencia(candidato_id, exp)
            
            # Insertar educaciones
            educaciones = analyzed_data.get('educaciones', [])
            for edu in educaciones:
                self._insert_educacion(candidato_id, edu)
            
            # Insertar certificaciones
            certificaciones = analyzed_data.get('certificaciones', [])
            for cert in certificaciones:
                self._insert_certificacion(candidato_id, cert)
            
            # Insertar idiomas
            idiomas = analyzed_data.get('idiomas', [])
            for idioma in idiomas:
                self._insert_idioma(candidato_id, idioma)
                
            # Actualizar habilidades si están en analyzed_data
            habilidades = analyzed_data.get('habilidades', [])
            if habilidades:
                self._update_habilidades(candidato_id, habilidades)
                
            logger.info(f"✅ Información del candidato {candidato_id} reemplazada completamente")
                
        except Exception as e:
            logger.error(f"Error actualizando información del candidato: {e}")
            raise

    def _clear_candidato_data(self, candidato_id: str) -> None:
        """Limpiar TODA la información existente del candidato antes de agregar nueva"""
        try:
            # Borrar experiencias
            query_exp = "DELETE FROM experiencias WHERE candidato_id = %s"
            self.db.execute_update(query_exp, (candidato_id,))
            logger.info(f"🗑️ Experiencias borradas para candidato {candidato_id}")
            
            # Borrar educaciones
            query_edu = "DELETE FROM educaciones WHERE candidato_id = %s"
            self.db.execute_update(query_edu, (candidato_id,))
            logger.info(f"🗑️ Educaciones borradas para candidato {candidato_id}")
            
            # Borrar certificaciones
            query_cert = "DELETE FROM certificaciones WHERE candidato_id = %s"
            self.db.execute_update(query_cert, (candidato_id,))
            logger.info(f"🗑️ Certificaciones borradas para candidato {candidato_id}")
            
            # Borrar idiomas
            query_idiomas = "DELETE FROM idiomas WHERE candidato_id = %s"
            self.db.execute_update(query_idiomas, (candidato_id,))
            logger.info(f"🗑️ Idiomas borrados para candidato {candidato_id}")
            
            # Limpiar campos del perfil principal (pero no borrar el candidato)
            query_clean = """
                UPDATE candidatos 
                SET titulo_profesional = NULL,
                    resumen_profesional = NULL,
                    telefono = NULL,
                    ciudad = NULL,
                    pais = NULL,
                    linkedin_url = NULL,
                    portfolio_url = NULL,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            self.db.execute_update(query_clean, (candidato_id,))
            logger.info(f"🗑️ Información personal limpiada para candidato {candidato_id}")
            
        except Exception as e:
            logger.error(f"Error limpiando datos del candidato {candidato_id}: {e}")
            raise

    def _update_personal_info(self, candidato_id: str, info: Dict[str, Any]) -> None:
        """Actualizar información personal del candidato"""
        update_fields = []
        params = []
        
        # Solo actualizar campos que no estén vacíos
        if info.get('nombre'):
            update_fields.append("nombre = %s")
            params.append(info['nombre'])
        
        if info.get('telefono'):
            update_fields.append("telefono = %s")
            params.append(info['telefono'])
        
        if info.get('ciudad'):
            update_fields.append("ciudad = %s")
            params.append(info['ciudad'])
        
        if info.get('pais'):
            update_fields.append("pais = %s")
            params.append(info['pais'])
        
        if info.get('linkedin_url'):
            update_fields.append("linkedin_url = %s")
            params.append(info['linkedin_url'])
        
        if info.get('portfolio_url'):
            update_fields.append("portfolio_url = %s")
            params.append(info['portfolio_url'])
        
        if info.get('titulo_profesional'):
            update_fields.append("titulo_profesional = %s")
            params.append(info['titulo_profesional'])
        
        if info.get('resumen_profesional'):
            update_fields.append("resumen_profesional = %s")
            params.append(info['resumen_profesional'])
        
        if update_fields:
            params.append(candidato_id)
            query = f"""
                UPDATE candidatos 
                SET {', '.join(update_fields)}, fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            self.db.execute_update(query, tuple(params))
    
    def _insert_experiencia(self, candidato_id: str, exp: Dict[str, Any]) -> None:
        """Insertar nueva experiencia"""
        if not exp.get('cargo') or not exp.get('empresa'):
            return  # Saltar si faltan datos esenciales
        
        try:
            # Procesar fechas
            fecha_inicio = exp.get('fecha_inicio')
            fecha_fin = exp.get('fecha_fin')
            
            # Convertir fechas a formato adecuado o None
            if fecha_inicio == 'null' or not fecha_inicio:
                fecha_inicio = None
            if fecha_fin == 'null' or not fecha_fin:
                fecha_fin = None
            
            query = """
                INSERT INTO experiencias (id, candidato_id, cargo, empresa, fecha_inicio, fecha_fin, trabajo_actual, descripcion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                str(uuid.uuid4()),
                candidato_id,
                exp['cargo'],
                exp['empresa'],
                fecha_inicio,
                fecha_fin,
                exp.get('trabajo_actual', False),
                exp.get('descripcion', '')
            )
            
            self.db.execute_insert(query, params)
            logger.info(f"✅ Experiencia insertada: {exp['cargo']} en {exp['empresa']}")
        except Exception as e:
            logger.warning(f"Error insertando experiencia: {e}")
    
    def _insert_educacion(self, candidato_id: str, edu: Dict[str, Any]) -> None:
        """Insertar nueva educación"""
        if not edu.get('institucion') or not edu.get('titulo'):
            return
        
        try:
            # Procesar fechas
            fecha_inicio = edu.get('fecha_inicio')
            fecha_fin = edu.get('fecha_fin')
            
            if fecha_inicio == 'null' or not fecha_inicio:
                fecha_inicio = None
            if fecha_fin == 'null' or not fecha_fin:
                fecha_fin = None
            
            query = """
                INSERT INTO educaciones (id, candidato_id, institucion, titulo, campo_estudio, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                str(uuid.uuid4()),
                candidato_id,
                edu['institucion'],
                edu['titulo'],
                edu.get('campo_estudio', ''),
                fecha_inicio,
                fecha_fin
            )
            
            self.db.execute_insert(query, params)
            logger.info(f"✅ Educación insertada: {edu['titulo']} en {edu['institucion']}")
        except Exception as e:
            logger.warning(f"Error insertando educación: {e}")
    
    def _insert_certificacion(self, candidato_id: str, cert: Dict[str, Any]) -> None:
        """Insertar nueva certificación"""
        if not cert.get('nombre') or not cert.get('entidad_emisora'):
            return
        
        try:
            query = """
                INSERT INTO certificaciones (id, candidato_id, nombre, entidad_emisora, anio_obtencion)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            params = (
                str(uuid.uuid4()),
                candidato_id,
                cert['nombre'],
                cert['entidad_emisora'],
                cert.get('anio_obtencion', datetime.now().year)
            )
            
            self.db.execute_insert(query, params)
        except Exception as e:
            logger.warning(f"Error insertando certificación: {e}")
    
    def _insert_idioma(self, candidato_id: str, idioma: Dict[str, Any]) -> None:
        """Insertar nuevo idioma"""
        if not idioma.get('nombre') or not idioma.get('nivel'):
            return
        
        try:
            # Verificar que no existe ya este idioma
            existing = self.db.execute_query(
                "SELECT id FROM idiomas WHERE candidato_id = %s AND nombre = %s",
                (candidato_id, idioma['nombre'])
            )
            
            if existing:
                return  # Ya existe
            
            query = """
                INSERT INTO idiomas (id, candidato_id, nombre, nivel)
                VALUES (%s, %s, %s, %s)
            """
            
            params = (
                str(uuid.uuid4()),
                candidato_id,
                idioma['nombre'],
                idioma['nivel']
            )
            
            self.db.execute_insert(query, params)
        except Exception as e:
            logger.warning(f"Error insertando idioma: {e}")
    
    def _update_habilidades(self, candidato_id: str, habilidades: List[str]) -> None:
        """Actualizar las habilidades del candidato"""
        try:
            # Convertir lista a JSON para almacenar en la BD
            import json
            habilidades_json = json.dumps(habilidades)
            
            query = """
                UPDATE candidatos 
                SET habilidades = %s::jsonb, fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            self.db.execute_update(query, (habilidades_json, candidato_id))
            logger.info(f"✅ {len(habilidades)} habilidades actualizadas para candidato {candidato_id}")
            
        except Exception as e:
            logger.warning(f"Error actualizando habilidades: {e}")
    
    def get_candidato_by_candidato_id(self, candidato_id: str) -> Optional[Dict[str, Any]]:
        """Obtener candidato por ID de candidato"""
        try:
            # Obtener información básica del candidato
            query = "SELECT * FROM candidatos WHERE id = %s"
            candidatos = self.db.execute_query(query, (candidato_id,))
            
            if not candidatos:
                return None
                
            candidato = candidatos[0]
            
            # Agregar información adicional
            candidato['experiencias'] = self._get_experiencias(candidato_id)
            candidato['educaciones'] = self._get_educaciones(candidato_id)
            candidato['certificaciones'] = self._get_certificaciones(candidato_id)
            candidato['idiomas'] = self._get_idiomas(candidato_id)
            candidato['preferencias'] = self._get_preferencias(candidato_id)
            
            return candidato
            
        except Exception as e:
            logger.error(f"Error obteniendo candidato por candidato_id {candidato_id}: {e}")
            return None
    
    def get_all_candidatos(self, filtros: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Obtener todos los candidatos con filtros opcionales"""
        try:
            # Por ahora implementación básica
            query = "SELECT * FROM candidatos LIMIT 50"
            candidatos = self.db.execute_query(query)
            return candidatos
        except Exception as e:
            logger.error(f"Error obteniendo candidatos: {e}")
            return []
    
    def get_estadisticas_candidatos(self) -> Dict[str, Any]:
        """Obtener estadísticas de candidatos"""
        try:
            stats = {}
            
            # Total candidatos
            query_total = "SELECT COUNT(*) as total FROM candidatos"
            stats['total_candidatos'] = self.db.execute_query(query_total)[0]['total']
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de candidatos: {e}")
            return {}

# Instancia global del servicio
candidato_service = CandidatoService() 
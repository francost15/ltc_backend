"""
Servicio para operaciones de vacantes - Adaptado a estructura real de BD
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.database import get_db_manager

logger = logging.getLogger(__name__)

class VacanteService:
    """Servicio para gestión de vacantes - Usando esquema real"""
    
    def __init__(self):
        self.db = get_db_manager()
    
    def get_all_vacantes(self) -> List[Dict[str, Any]]:
        """Obtener todas las vacantes activas"""
        try:
            query = """
                SELECT v.*, e.nombre as empresa_nombre, e.giro as empresa_giro, 
                       e.ubicacion as empresa_ubicacion, e.logo as empresa_logo
                FROM vacantes v
                LEFT JOIN empresas e ON v.empresa_id = e.id
                WHERE v.activa = true
                ORDER BY v.fecha_publicacion DESC
            """
            vacantes = self.db.execute_query(query)
            
            # Adaptar formato para compatibilidad con matching
            for vacante in vacantes:
                vacante = self._adaptar_formato_vacante(vacante)
            
            return vacantes
            
        except Exception as e:
            logger.error(f"Error obteniendo vacantes: {e}")
            raise
    
    def get_vacante_by_id(self, vacante_id: str) -> Optional[Dict[str, Any]]:
        """Obtener vacante por ID"""
        try:
            query = """
                SELECT v.*, e.nombre as empresa_nombre, e.giro as empresa_giro,
                       e.ubicacion as empresa_ubicacion, e.logo as empresa_logo,
                       u.email as empresa_email
                FROM vacantes v
                LEFT JOIN empresas e ON v.empresa_id = e.id
                LEFT JOIN usuarios u ON e.usuario_id = u.id
                WHERE v.id = %s
            """
            vacantes = self.db.execute_query(query, (vacante_id,))
            
            if not vacantes:
                return None
            
            vacante = vacantes[0]
            return self._adaptar_formato_vacante(vacante)
            
        except Exception as e:
            logger.error(f"Error obteniendo vacante {vacante_id}: {e}")
            raise
    
    def search_vacantes(self, filtros: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Buscar vacantes con filtros adaptados a tu esquema"""
        try:
            base_query = """
                SELECT v.*, e.nombre as empresa_nombre, e.giro as empresa_giro,
                       e.ubicacion as empresa_ubicacion, e.logo as empresa_logo
                FROM vacantes v
                LEFT JOIN empresas e ON v.empresa_id = e.id
                WHERE v.activa = true
            """
            
            where_conditions = []
            params = []
            
            if filtros:
                # Filtro por tipo de empleo (equivalente a modalidad)
                if filtros.get('modalidad') or filtros.get('tipo_empleo'):
                    tipo_empleo = filtros.get('modalidad') or filtros.get('tipo_empleo')
                    where_conditions.append("LOWER(v.tipo_empleo) LIKE LOWER(%s)")
                    params.append(f"%{tipo_empleo}%")
                
                # Filtro por categoría (equivalente a nivel_experiencia o área)
                if filtros.get('categoria'):
                    where_conditions.append("LOWER(v.categoria::text) = LOWER(%s)")
                    params.append(filtros['categoria'])
                
                # Filtro por ubicación
                if filtros.get('ubicacion'):
                    where_conditions.append("(LOWER(v.ubicacion) LIKE LOWER(%s) OR LOWER(e.ubicacion) LIKE LOWER(%s))")
                    params.extend([f"%{filtros['ubicacion']}%", f"%{filtros['ubicacion']}%"])
                
                # Filtro por empresa
                if filtros.get('empresa'):
                    where_conditions.append("LOWER(e.nombre) LIKE LOWER(%s)")
                    params.append(f"%{filtros['empresa']}%")
                
                # Filtro por giro/sector
                if filtros.get('giro') or filtros.get('sector'):
                    giro = filtros.get('giro') or filtros.get('sector')
                    where_conditions.append("LOWER(e.giro) LIKE LOWER(%s)")
                    params.append(f"%{giro}%")
                
                # Filtro por salario mínimo
                if filtros.get('salario_min'):
                    where_conditions.append("v.salario >= %s")
                    params.append(filtros['salario_min'])
                
                # Filtro por salario máximo
                if filtros.get('salario_max'):
                    where_conditions.append("v.salario <= %s")
                    params.append(filtros['salario_max'])
                
                # Filtro por búsqueda en título y descripción (habilidades)
                if filtros.get('habilidades'):
                    habilidades_query = []
                    for habilidad in filtros['habilidades']:
                        habilidades_query.append("(LOWER(v.titulo) LIKE LOWER(%s) OR LOWER(v.descripcion) LIKE LOWER(%s))")
                        params.extend([f"%{habilidad}%", f"%{habilidad}%"])
                    
                    if habilidades_query:
                        where_conditions.append(f"({' OR '.join(habilidades_query)})")
                
                # Filtro por búsqueda general en título y descripción
                if filtros.get('busqueda'):
                    where_conditions.append("(LOWER(v.titulo) LIKE LOWER(%s) OR LOWER(v.descripcion) LIKE LOWER(%s))")
                    params.extend([f"%{filtros['busqueda']}%", f"%{filtros['busqueda']}%"])
            
            # Construir query final
            if where_conditions:
                query = base_query + " AND " + " AND ".join(where_conditions)
            else:
                query = base_query
            
            query += " ORDER BY v.fecha_publicacion DESC"
            
            vacantes = self.db.execute_query(query, tuple(params))
            
            # Adaptar formato para cada vacante
            for i, vacante in enumerate(vacantes):
                vacantes[i] = self._adaptar_formato_vacante(vacante)
            
            return vacantes
            
        except Exception as e:
            logger.error(f"Error buscando vacantes: {e}")
            raise
    
    def get_vacantes_by_empresa(self, empresa_id: str) -> List[Dict[str, Any]]:
        """Obtener vacantes de una empresa específica"""
        try:
            query = """
                SELECT v.*, e.nombre as empresa_nombre, e.giro as empresa_giro,
                       e.ubicacion as empresa_ubicacion
                FROM vacantes v
                LEFT JOIN empresas e ON v.empresa_id = e.id
                WHERE v.empresa_id = %s AND v.activa = true
                ORDER BY v.fecha_publicacion DESC
            """
            vacantes = self.db.execute_query(query, (empresa_id,))
            
            # Adaptar formato
            for i, vacante in enumerate(vacantes):
                vacantes[i] = self._adaptar_formato_vacante(vacante)
            
            return vacantes
            
        except Exception as e:
            logger.error(f"Error obteniendo vacantes de empresa {empresa_id}: {e}")
            raise
    
    def _adaptar_formato_vacante(self, vacante: Dict[str, Any]) -> Dict[str, Any]:
        """Adaptar formato de vacante para compatibilidad con sistema de matching"""
        
        # Mapear campos a formato esperado por el matching
        vacante_adaptada = vacante.copy()
        
        # Mapear tipo_empleo a modalidad para compatibilidad
        if 'tipo_empleo' in vacante:
            vacante_adaptada['modalidad'] = vacante['tipo_empleo']
            # Inferir modalidad de trabajo
            tipo_empleo = str(vacante['tipo_empleo']).lower()
            if 'remoto' in tipo_empleo or 'home' in tipo_empleo:
                vacante_adaptada['modalidad'] = 'Remoto'
            elif 'presencial' in tipo_empleo or 'oficina' in tipo_empleo:
                vacante_adaptada['modalidad'] = 'Presencial'
            elif 'hibrido' in tipo_empleo or 'híbrido' in tipo_empleo or 'mixto' in tipo_empleo:
                vacante_adaptada['modalidad'] = 'Híbrido'
            else:
                vacante_adaptada['modalidad'] = vacante['tipo_empleo']
        
        # Mapear salario único a rango de salarios
        if 'salario' in vacante and vacante['salario']:
            salario = float(vacante['salario'])
            # Crear rango estimado (±15%)
            vacante_adaptada['salario_min'] = int(salario * 0.85)
            vacante_adaptada['salario_max'] = int(salario * 1.15)
        else:
            vacante_adaptada['salario_min'] = 0
            vacante_adaptada['salario_max'] = 0
        
        # Mapear categoria a nivel_experiencia
        if 'categoria' in vacante:
            categoria = str(vacante['categoria']).upper()
            
            # Inferir nivel de experiencia basado en categoría y descripción
            descripcion = str(vacante.get('descripcion', '')).lower()
            titulo = str(vacante.get('titulo', '')).lower()
            
            if any(keyword in descripcion or keyword in titulo for keyword in ['senior', 'líder', 'lead', 'jefe', 'manager', 'director']):
                vacante_adaptada['nivel_experiencia'] = 'Senior'
            elif any(keyword in descripcion or keyword in titulo for keyword in ['junior', 'trainee', 'becario', 'practicante']):
                vacante_adaptada['nivel_experiencia'] = 'Junior'
            else:
                vacante_adaptada['nivel_experiencia'] = 'Mid-level'
        else:
            vacante_adaptada['nivel_experiencia'] = 'Mid-level'
        
        # Mapear empresa_nombre a empresa para compatibilidad
        if 'empresa_nombre' in vacante:
            vacante_adaptada['empresa'] = vacante['empresa_nombre']
        
        # Extraer habilidades de la descripción (análisis básico)
        vacante_adaptada['habilidades_requeridas'] = self._extraer_habilidades_descripcion(
            vacante.get('descripcion', '') + ' ' + vacante.get('titulo', '')
        )
        
        # Extraer requisitos de la descripción
        vacante_adaptada['requisitos'] = self._extraer_requisitos_descripcion(
            vacante.get('descripcion', '')
        )
        
        return vacante_adaptada
    
    def _extraer_habilidades_descripcion(self, texto: str) -> List[str]:
        """Extraer habilidades técnicas de la descripción usando palabras clave"""
        habilidades_conocidas = [
            # Lenguajes de programación
            'Python', 'JavaScript', 'Java', 'C#', 'PHP', 'Ruby', 'Go', 'Rust', 'TypeScript',
            'HTML', 'CSS', 'SQL', 'R', 'MATLAB', 'C++', 'C', 'Swift', 'Kotlin',
            
            # Frameworks y librerías
            'React', 'Angular', 'Vue', 'Django', 'Flask', 'Laravel', 'Spring', 'Express',
            'Node.js', 'jQuery', 'Bootstrap', 'Material-UI', 'Next.js', 'Nuxt.js',
            
            # Bases de datos
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Oracle', 'SQL Server', 'Firebase',
            'DynamoDB', 'Cassandra', 'ElasticSearch',
            
            # Cloud y DevOps
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'GitLab', 'Terraform',
            'Ansible', 'Linux', 'Ubuntu', 'CentOS',
            
            # Herramientas
            'Git', 'GitHub', 'Jira', 'Confluence', 'Slack', 'Trello', 'Figma', 'Adobe',
            'Photoshop', 'Illustrator', 'Sketch',
            
            # Metodologías
            'Scrum', 'Agile', 'Kanban', 'DevOps', 'CI/CD', 'TDD', 'BDD',
            
            # Análisis de datos
            'Tableau', 'Power BI', 'Excel', 'Pandas', 'NumPy', 'Scikit-learn',
            'TensorFlow', 'PyTorch', 'Machine Learning', 'Data Science',
            
            # Otros
            'REST API', 'GraphQL', 'Microservices', 'API', 'JSON', 'XML'
        ]
        
        texto_lower = texto.lower()
        habilidades_encontradas = []
        
        for habilidad in habilidades_conocidas:
            if habilidad.lower() in texto_lower:
                habilidades_encontradas.append(habilidad)
        
        return list(set(habilidades_encontradas))  # Eliminar duplicados
    
    def _extraer_requisitos_descripcion(self, descripcion: str) -> List[str]:
        """Extraer requisitos básicos de la descripción"""
        requisitos = []
        
        # Buscar patrones comunes de requisitos
        lineas = descripcion.split('\n')
        
        for linea in lineas:
            linea = linea.strip()
            if any(keyword in linea.lower() for keyword in ['requisito', 'requerimos', 'necesario', 'experiencia', 'conocimiento']):
                if len(linea) > 10 and len(linea) < 200:  # Filtrar líneas muy cortas o muy largas
                    requisitos.append(linea)
        
        # Si no encontramos requisitos específicos, extraer algunos básicos
        if not requisitos:
            if 'experiencia' in descripcion.lower():
                requisitos.append("Experiencia en el área")
            if any(skill in descripcion.lower() for skill in ['inglés', 'english']):
                requisitos.append("Conocimiento de inglés")
            if any(skill in descripcion.lower() for skill in ['título', 'carrera', 'licenciatura']):
                requisitos.append("Formación académica")
        
        return requisitos[:5]  # Máximo 5 requisitos
    
    def crear_vacante(self, vacante_data: Dict[str, Any]) -> str:
        """Crear nueva vacante en tu esquema"""
        try:
            query = """
                INSERT INTO vacantes (
                    id, empresa_id, titulo, descripcion, tipo_empleo, categoria,
                    salario, ubicacion, fecha_publicacion, activa
                ) VALUES (
                    gen_random_uuid()::text, %s, %s, %s, %s, %s::categoria_enum, %s, %s, 
                    CURRENT_TIMESTAMP, true
                ) RETURNING id
            """
            
            params = (
                vacante_data['empresa_id'],
                vacante_data['titulo'],
                vacante_data['descripcion'],
                vacante_data.get('tipo_empleo', 'Tiempo Completo'),
                vacante_data.get('categoria', 'OTROS'),
                vacante_data.get('salario', 0),
                vacante_data.get('ubicacion', '')
            )
            
            result = self.db.execute_query(query, params)
            return result[0]['id']
            
        except Exception as e:
            logger.error(f"Error creando vacante: {e}")
            raise
    
    def actualizar_vacante(self, vacante_id: str, datos: Dict[str, Any]) -> bool:
        """Actualizar una vacante existente"""
        try:
            update_fields = []
            params = []
            
            # Campos actualizables en tu esquema
            campos_actualizables = {
                'titulo': 'titulo',
                'descripcion': 'descripcion',
                'tipo_empleo': 'tipo_empleo',
                'categoria': 'categoria',
                'salario': 'salario',
                'ubicacion': 'ubicacion'
            }
            
            for campo, columna in campos_actualizables.items():
                if campo in datos:
                    if campo == 'categoria':
                        update_fields.append(f"{columna} = %s::categoria_enum")
                    else:
                        update_fields.append(f"{columna} = %s")
                    params.append(datos[campo])
            
            if update_fields:
                params.append(vacante_id)
                query = f"""
                    UPDATE vacantes 
                    SET {', '.join(update_fields)}, fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = %s
                """
                self.db.execute_update(query, tuple(params))
            
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando vacante {vacante_id}: {e}")
            raise
    
    def desactivar_vacante(self, vacante_id: str) -> bool:
        """Desactivar una vacante"""
        try:
            query = "UPDATE vacantes SET activa = false WHERE id = %s"
            self.db.execute_update(query, (vacante_id,))
            return True
        except Exception as e:
            logger.error(f"Error desactivando vacante {vacante_id}: {e}")
            raise
    
    def get_categorias_disponibles(self) -> List[str]:
        """Obtener las categorías disponibles del enum"""
        try:
            query = """
                SELECT unnest(enum_range(NULL::categoria_enum))::text as categoria
            """
            result = self.db.execute_query(query)
            return [row['categoria'] for row in result]
        except Exception as e:
            logger.error(f"Error obteniendo categorías: {e}")
            return ['TECNOLOGIA', 'SALUD', 'EDUCACION', 'VENTAS', 'MARKETING', 'FINANZAS', 'RECURSOS_HUMANOS', 'LOGISTICA', 'OPERACIONES', 'OTROS']
    
    def get_estadisticas_vacantes(self) -> Dict[str, Any]:
        """Obtener estadísticas de vacantes"""
        try:
            stats = {}
            
            # Total vacantes activas
            query_total = "SELECT COUNT(*) as total FROM vacantes WHERE activa = true"
            stats['total_activas'] = self.db.execute_query(query_total)[0]['total']
            
            # Por categoría
            query_categoria = """
                SELECT categoria::text, COUNT(*) as cantidad 
                FROM vacantes 
                WHERE activa = true 
                GROUP BY categoria 
                ORDER BY cantidad DESC
            """
            stats['por_categoria'] = self.db.execute_query(query_categoria)
            
            # Por tipo de empleo
            query_tipo = """
                SELECT tipo_empleo, COUNT(*) as cantidad 
                FROM vacantes 
                WHERE activa = true AND tipo_empleo IS NOT NULL
                GROUP BY tipo_empleo 
                ORDER BY cantidad DESC
            """
            stats['por_tipo_empleo'] = self.db.execute_query(query_tipo)
            
            # Por ubicación
            query_ubicacion = """
                SELECT ubicacion, COUNT(*) as cantidad 
                FROM vacantes 
                WHERE activa = true AND ubicacion IS NOT NULL
                GROUP BY ubicacion 
                ORDER BY cantidad DESC
                LIMIT 10
            """
            stats['por_ubicacion'] = self.db.execute_query(query_ubicacion)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

# Instancia global del servicio
vacante_service = VacanteService() 
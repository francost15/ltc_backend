"""
Sistema LTC - Rutas Esenciales
Solo 2 rutas: Upload CV y Matching
"""
from flask import Blueprint, request, jsonify
import logging
from services.candidato_service import candidato_service
from services.matching_service import matching_service
from config.settings import MatchingConfig

logger = logging.getLogger(__name__)
candidatos_bp = Blueprint('candidatos', __name__)

# ===============================
# 1. UPLOAD CV
# ===============================

@candidatos_bp.route('/candidatos/<usuario_id>/upload-cv', methods=['POST'])
def upload_cv(usuario_id):
    """Subir y procesar CV de un candidato"""
    try:
        # Validar archivo
        if 'file' not in request.files:
            return jsonify({
                'error': 'No se encontró archivo en la solicitud',
                'code': 'NO_FILE'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'error': 'No se seleccionó ningún archivo',
                'code': 'EMPTY_FILENAME'
            }), 400
        
        # Validar formato
        allowed_extensions = ['.pdf', '.doc', '.docx']
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            return jsonify({
                'error': 'Solo se permiten archivos PDF, DOC o DOCX',
                'code': 'INVALID_FORMAT'
            }), 400
        
        # Leer y validar contenido
        file_content = file.read()
        if len(file_content) == 0:
            return jsonify({
                'error': 'El archivo está vacío',
                'code': 'EMPTY_FILE'
            }), 400
        
        # Procesar CV
        logger.info(f"📄 Procesando CV para usuario {usuario_id}: {file.filename}")
        result = candidato_service.process_cv_upload(usuario_id, file_content, file.filename)
        
        return jsonify({
            'success': True,
            'message': 'CV procesado exitosamente',
            'data': result,
            'filename': file.filename,
            'usuario_id': usuario_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error procesando CV para usuario {usuario_id}: {e}")
        return jsonify({
            'error': f'Error procesando CV: {str(e)}',
            'code': 'PROCESSING_ERROR'
        }), 500

# ===============================
# 2. MATCHING
# ===============================

@candidatos_bp.route('/candidatos/<usuario_id>/matches', methods=['GET'])
def get_matching(usuario_id: str):
    """Obtener vacantes compatibles para un candidato (60% mínimo)"""
    try:
        # Obtener candidato
        candidato = candidato_service.get_candidato_by_usuario_id(usuario_id)
        if not candidato:
            return jsonify({
                'error': 'Candidato no encontrado',
                'usuario_id': usuario_id,
                'sugerencia': 'Sube tu CV primero usando la ruta /candidatos/{usuario_id}/upload-cv'
            }), 404
        
        # Parámetros de matching (60% mínimo)
        limite = request.args.get('limite', default=10, type=int)
        score_minimo = MatchingConfig.score_minimo / 100  # 60% = 0.6
        
        # Realizar matching
        logger.info(f"🔍 Buscando matches para usuario {usuario_id} (mínimo {MatchingConfig.score_minimo}%)")
        matches = matching_service.find_matches_for_candidato(
            candidato, 
            limite=limite,
            score_minimo=score_minimo
        )
        
        # Respuesta limpia
        return jsonify({
            'success': True,
            'usuario_id': usuario_id,
            'candidato': {
                'id': candidato['id'],
                'nombre': candidato.get('nombre', 'No especificado'),
                'titulo_profesional': candidato.get('titulo_profesional', 'No especificado')
            },
            'matches_encontrados': len(matches),
            'score_minimo': f"{MatchingConfig.score_minimo}%",
            'matches': matches
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en matching para usuario {usuario_id}: {e}")
        return jsonify({
            'error': f'Error en matching: {str(e)}',
            'usuario_id': usuario_id
        }), 500 

 
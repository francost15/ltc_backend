"""
Aplicación principal Flask para procesamiento de CVs
"""
from flask import Flask
from flask_cors import CORS
from config.settings import Config
from routes.candidatos import candidatos_bp
from utils.database import init_db

def create_app():
    """Factory para crear la aplicación Flask"""
    app = Flask(__name__)
    
    # Configuración
    app.config.from_object(Config)
    
    # CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Inicializar base de datos
    init_db()
    
    # Registrar blueprints
    app.register_blueprint(candidatos_bp, url_prefix='/api/v1')
    
    @app.route('/')
    def home():
        return {
            "mensaje": "API de Procesamiento de CVs - LTC",
            "version": "1.0.0",
            "endpoints": {
                "candidatos": "/api/v1/candidatos",
                "subir_cv": "/api/v1/candidatos/{usuario_id}/upload-cv",
                "obtener_candidato": "/api/v1/candidatos/{usuario_id}",
                "matching_candidato": "/api/v1/candidatos/{usuario_id}/matches",
                "documentacion": "/docs"
            }
        }
    
    @app.route('/health')
    def health():
        return {
            "status": "ok",
            "database": "connected"
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8000) 
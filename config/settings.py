"""
Configuración de la aplicación
"""
import os
from dotenv import load_dotenv

# Intentar cargar .env, pero no fallar si no existe
load_dotenv()

class Config:
    """Configuración base de la aplicación"""
    
    # Base de datos - usar variable de entorno o valor por defecto
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # OpenAI para procesamiento de CVsgit
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Configuración de archivos
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
    
    # Configuración Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Configuración CORS
    CORS_ORIGINS = ['*']
    
    @staticmethod
    def init_app(app):
        """Inicializar configuración específica de la app"""
        # Crear directorio de uploads si no existe
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 

class MatchingConfig:
    """Configuración del sistema de matching"""
    score_minimo = 30  # TEMPORAL: Reducir a 30% para probar el sistema
    max_resultados = 10 
    usar_openai = True  # Usar OpenAI para análisis detallado 
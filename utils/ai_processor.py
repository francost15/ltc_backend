"""
Procesador de IA para análisis de CVs usando OpenAI
"""
from openai import OpenAI
import json
import os
import logging
from typing import Dict, Any, Optional, List
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class CVAnalyzer:
    """Analizador de CVs usando IA"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = None
        self.ai_available = False
        
        if self.openai_api_key and self.openai_api_key.strip():
            try:
                self.client = OpenAI(api_key=self.openai_api_key)
                self.ai_available = True
                logger.info("✅ Cliente OpenAI inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando OpenAI: {e}")
                self.ai_available = False
        else:
            logger.warning("⚠️ OpenAI API key no configurada - usando procesamiento básico")
    
    def analyze_cv_with_ai(self, cv_text: str) -> Dict[str, Any]:
        """Analizar CV usando OpenAI GPT"""
        if not self.ai_available or not self.client:
            logger.info("IA no disponible, usando análisis básico")
            return self._basic_analysis(cv_text)
        
        try:
            prompt = self._create_analysis_prompt(cv_text)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis de CVs. Extrae información estructurada del CV proporcionado."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            return self._parse_ai_response(result)
            
        except Exception as e:
            logger.error(f"Error en análisis con IA: {e}")
            return self._basic_analysis(cv_text)
    
    def _create_analysis_prompt(self, cv_text: str) -> str:
        """Crear prompt para OpenAI"""
        return f"""
INSTRUCCIONES IMPORTANTES:
- Extrae TODA la información en ESPAÑOL
- Si el CV está en inglés, traduce los títulos, cargos y descripciones al español
- Sé específico y detallado en las extracciones
- Normaliza los títulos de trabajo a términos estándar en español

Analiza el siguiente CV y extrae la información en formato JSON con esta estructura exacta:

{{
    "informacion_personal": {{
        "nombre": "nombre completo en español",
        "telefono": "telefono si está disponible", 
        "ciudad": "ciudad de residencia",
        "pais": "país de residencia",
        "linkedin_url": "URL de LinkedIn si está disponible",
        "portfolio_url": "URL de portfolio/GitHub si está disponible",
        "titulo_profesional": "título o profesión principal en ESPAÑOL (ej: Desarrollador de Software, Ingeniero de Sistemas, etc.)",
        "resumen_profesional": "resumen o descripción profesional en ESPAÑOL"
    }},
    "experiencias": [
        {{
            "cargo": "cargo traducido al español (ej: Software Developer -> Desarrollador de Software)",
            "empresa": "nombre de la empresa",
            "fecha_inicio": "YYYY-MM-DD",
            "fecha_fin": "YYYY-MM-DD o null si es trabajo actual",
            "trabajo_actual": true/false,
            "descripcion": "descripción de responsabilidades y logros en ESPAÑOL"
        }}
    ],
    "educaciones": [
        {{
            "institucion": "nombre de la institución",
            "titulo": "título obtenido traducido al español",
            "campo_estudio": "campo de estudio en español",
            "fecha_inicio": "YYYY-MM-DD",
            "fecha_fin": "YYYY-MM-DD o null si está en curso"
        }}
    ],
    "certificaciones": [
        {{
            "nombre": "nombre de la certificación (puede mantener nombre original si es técnico)",
            "entidad_emisora": "entidad que emitió",
            "anio_obtencion": año_numerico
        }}
    ],
    "idiomas": [
        {{
            "nombre": "Español|Inglés|Francés|etc.",
            "nivel": "NATIVO|AVANZADO_C2|AVANZADO_C1|INTERMEDIO_B2|INTERMEDIO_B1|BASICO_A2|BASICO_A1"
        }}
    ],
    "habilidades": [
        "lista de habilidades técnicas y blandas extraídas del CV"
    ]
}}

EJEMPLOS DE TRADUCCIONES:
- "Software Developer" -> "Desarrollador de Software"
- "Full Stack Developer" -> "Desarrollador Full Stack" 
- "Project Manager" -> "Gerente de Proyecto"
- "Data Scientist" -> "Científico de Datos"
- "UX Designer" -> "Diseñador UX"

CV a analizar:
{cv_text}

Responde SOLO con el JSON válido, sin texto adicional.
"""
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parsear respuesta de IA"""
        try:
            # Limpiar respuesta y extraer JSON
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            return json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta de IA: {e}")
            return self._basic_analysis(response)
    
    def _basic_analysis(self, cv_text: str) -> Dict[str, Any]:
        """Análisis básico sin IA (regex y patrones)"""
        logger.info("Usando análisis básico (sin IA)")
        
        # Extraer información básica con regex
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(\+?[\d\s\-\(\)]{8,})'
        
        emails = re.findall(email_pattern, cv_text)
        phones = re.findall(phone_pattern, cv_text)
        
        # Buscar nombres (primera línea que no sea email/teléfono)
        lines = cv_text.split('\n')
        name = ""
        for line in lines[:5]:  # Buscar en las primeras 5 líneas
            line = line.strip()
            if line and not re.search(email_pattern, line) and not re.search(phone_pattern, line):
                if len(line.split()) >= 2 and len(line) < 100:
                    name = line
                    break
        
        return {
            "informacion_personal": {
                "nombre": name,
                "telefono": phones[0] if phones else None,
                "ciudad": None,
                "pais": None,
                "linkedin_url": self._extract_linkedin(cv_text),
                "portfolio_url": None,
                "titulo_profesional": None,
                "resumen_profesional": None
            },
            "experiencias": [],
            "educaciones": [],
            "certificaciones": [],
            "idiomas": []
        }
    
    def _extract_linkedin(self, text: str) -> Optional[str]:
        """Extraer URL de LinkedIn"""
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w\-]+'
        matches = re.findall(linkedin_pattern, text)
        return matches[0] if matches else None

# Instancia global del analizador
cv_analyzer = CVAnalyzer() 
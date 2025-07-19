"""
Utilidades para procesamiento de documentos PDF
"""
import PyPDF2
import docx
from typing import Dict, Any, Optional
import logging
import io

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Procesador de documentos (PDF, DOC, DOCX)"""
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extraer texto de archivo PDF"""
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error extrayendo texto de PDF: {e}")
            raise Exception(f"Error procesando PDF: {str(e)}")
    
    def extract_text_from_docx(self, file_content: bytes) -> str:
        """Extraer texto de archivo DOCX"""
        try:
            doc_file = io.BytesIO(file_content)
            doc = docx.Document(doc_file)
            
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error extrayendo texto de DOCX: {e}")
            raise Exception(f"Error procesando DOCX: {str(e)}")
    
    def extract_text(self, file_content: bytes, filename: str) -> str:
        """Extraer texto según tipo de archivo"""
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext == 'pdf':
            return self.extract_text_from_pdf(file_content)
        elif file_ext in ['docx']:
            return self.extract_text_from_docx(file_content)
        else:
            raise Exception(f"Tipo de archivo no soportado: {file_ext}")

# Instancia global del procesador
document_processor = DocumentProcessor() 
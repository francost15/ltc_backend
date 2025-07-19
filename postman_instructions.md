# 🚀 Guía para Probar la API de Matching en Postman

## 📋 **Configuración Inicial**

### 1. Configurar el Entorno
- **Base URL**: `http://localhost:8000`
- **Puerto**: 8000
- **Protocolo**: HTTP

### 2. Asegurarse de que el servidor esté corriendo
```bash
python app.py
```

---

## 🔍 **Endpoint de Matching**

### **GET** `/api/v1/candidatos/{usuario_id}/matches`

**Descripción**: Obtiene vacantes compatibles para un candidato específico

### **Parámetros de URL**
- `usuario_id` (requerido): ID del usuario candidato

### **Parámetros de Query (opcionales)**
- `limite`: Número máximo de resultados (default: 10)
- Ejemplo: `?limite=5`

---

## 👥 **Candidatos Disponibles para Prueba**

| Nombre | Usuario ID | Título |
|--------|------------|--------|
| Patricia Hidalgo Ramé | `4b164479-1851-4d88-ae36-85570ea92664` | - |
| Antonio | `88bb8200-2f60-417d-adfd-ff5ff4119252` | - |
| Juan Espinosa Martínez | `243fddca-7d98-4c79-8ce2-309290133340` | - |
| Franco Alessandro Sanchez | `63d95430-26c0-499a-8c61-63d59807da10` | Ingeniero de Software |
| Abril Vargas Cacho | `710edf29-7106-40d8-989e-4b9c840c7a7c` | - |

---

## 🔧 **Ejemplos de Requests en Postman**

### **Ejemplo 1: Matching Básico**
```
GET http://localhost:8000/api/v1/candidatos/4b164479-1851-4d88-ae36-85570ea92664/matches
```

### **Ejemplo 2: Matching con Límite**
```
GET http://localhost:8000/api/v1/candidatos/4b164479-1851-4d88-ae36-85570ea92664/matches?limite=3
```

### **Ejemplo 3: Probar con Desarrollador**
```
GET http://localhost:8000/api/v1/candidatos/63d95430-26c0-499a-8c61-63d59807da10/matches?limite=5
```

---

## 📊 **Estructura de Respuesta Exitosa**

```json
{
  "success": true,
  "usuario_id": "4b164479-1851-4d88-ae36-85570ea92664",
  "candidato": {
    "id": "c16b712a-b13e-4790-8deb-277ea1f69093",
    "nombre": "Patricia Hidalgo Ramé",
    "titulo_profesional": null
  },
  "matches_encontrados": 5,
  "score_minimo": "30%",
  "matches": [
    {
      "score": 30,
      "vacante": {
        "id": "bea5ce9d-e03c-4e77-8d1b-657fff458a57",
        "titulo": "Vendedora de mayoreo",
        "empresa_nombre": "JM Consultoría",
        "ubicacion": "Ciudad de México",
        "salario": "12000.000000000000000000000000000000",
        "descripcion": "Te gustan las ventas...",
        "categoria": "VENTAS"
      },
      "analisis": {
        "score_final": 65,
        "experiencia_directa": true,
        "tecnologias_match_porcentaje": 70,
        "fortalezas_especificas": [...],
        "debilidades_detalladas": [...],
        "recomendacion_detallada": "..."
      },
      "habilidades_match": {
        "coincidentes": [],
        "faltantes": [],
        "match_percentage": 0
      }
    }
  ]
}
```

---

## ❌ **Posibles Errores**

### **404 - Candidato No Encontrado**
```json
{
  "error": "Candidato no encontrado",
  "usuario_id": "test_user",
  "sugerencia": "Sube tu CV primero usando la ruta /candidatos/{usuario_id}/upload-cv"
}
```

### **500 - Error del Servidor**
```json
{
  "error": "Error en matching: [detalle del error]",
  "usuario_id": "usuario_id"
}
```

### **Connection Error**
- **Causa**: Servidor no está corriendo
- **Solución**: Ejecutar `python app.py`

---

## 🔄 **Endpoints Adicionales**

### **1. Health Check**
```
GET http://localhost:8000/health
```

### **2. Información General**
```
GET http://localhost:8000/
```

### **3. Subir CV (POST)**
```
POST http://localhost:8000/api/v1/candidatos/{usuario_id}/upload-cv
Content-Type: multipart/form-data

Body:
- file: [seleccionar archivo PDF/DOC/DOCX]
```

---

## 📝 **Notas Importantes**

1. **Score Mínimo**: Actualmente configurado en 30% para testing
2. **OpenAI**: Está funcionando correctamente y genera análisis detallados
3. **Matches**: El sistema encuentra matches reales basados en compatibilidad
4. **Límite**: Por defecto retorna 10 matches, configurable con `?limite=N`

---

## 🧪 **Pruebas Recomendadas**

1. Probar con diferentes candidatos
2. Variar el parámetro `limite`
3. Verificar que los scores son consistentes
4. Revisar la calidad del análisis de OpenAI
5. Confirmar que las vacantes son relevantes

---

## 🔍 **Debugging**

Si algo no funciona:
1. Verificar que el servidor esté corriendo
2. Revisar los logs del servidor
3. Confirmar que el candidato existe en la BD
4. Verificar que hay vacantes activas 
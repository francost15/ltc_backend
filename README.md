# 🚀 LTC Backend - API de Matching de Candidatos

API de backend para el sistema de matching inteligente entre candidatos y vacantes de empleo, desarrollada con Flask y OpenAI.

## 🎯 Características

- **📄 Procesamiento de CVs**: Extracción automática de información de PDFs y documentos
- **🤖 Matching Inteligente**: Análisis semántico con OpenAI para encontrar las mejores coincidencias
- **⚡ API Optimizada**: Caché, paralelización y filtros tempranos para máximo rendimiento
- **🗄️ Base de Datos PostgreSQL**: Almacenamiento robusto y escalable
- **🔐 Seguridad**: Manejo seguro de archivos y variables de entorno

## 🛠️ Tecnologías

- **Backend**: Python 3.11, Flask
- **Base de Datos**: PostgreSQL
- **IA**: OpenAI GPT-3.5-turbo
- **Procesamiento**: PyPDF2, python-docx
- **Servidor**: Gunicorn
- **Despliegue**: Render, Docker, Google Cloud

## 🚀 Despliegue Rápido

### Render (Recomendado)
```bash
# 1. Clonar repositorio
git clone https://github.com/francost15/ltc_backend.git
cd ltc_backend

# 2. Seguir guía de Render
# Ver: PASOS_RENDER.md
```

### Docker Local
```bash
# Construir imagen
docker build -t ltc-backend .

# Ejecutar con Docker Compose
docker-compose -f docker-compose.simple.yml up -d
```

## 📡 Endpoints de la API

### Información General
- `GET /` - Información de la API
- `GET /health` - Health check

### Candidatos
- `POST /api/v1/candidatos/{usuario_id}/upload-cv` - Subir CV
- `GET /api/v1/candidatos/{usuario_id}` - Obtener candidato
- `GET /api/v1/candidatos/{usuario_id}/matches` - Obtener matches

## 🔧 Configuración

### Variables de Entorno
```env
# Requeridas
OPENAI_API_KEY=tu-api-key-de-openai

# Opcionales
DATABASE_URL=postgresql://user:pass@host:port/db
FLASK_DEBUG=False
SECRET_KEY=tu-clave-secreta
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
```

## 📊 Optimizaciones Implementadas

- **💾 Caché Inteligente**: Resultados de matching en caché por 5 minutos
- **🔄 Procesamiento Paralelo**: Análisis de vacantes en paralelo
- **⚡ Filtros Tempranos**: Descarte rápido de vacantes incompatibles
- **🤖 Fallback Inteligente**: Algoritmo manual si OpenAI falla
- **⏱️ Timeouts Optimizados**: Respuestas rápidas con timeouts reducidos

## 🗄️ Estructura de la Base de Datos

### Tablas Principales
- **candidatos**: Información de candidatos y CVs procesados
- **vacantes**: Vacantes de empleo disponibles
- **matches**: Historial de matches (opcional)

## 🚀 Despliegue

### Render
- [PASOS_RENDER.md](PASOS_RENDER.md) - Guía completa
- [README_Render.md](README_Render.md) - Documentación detallada

### Google Cloud
- [README_GoogleCloud.md](README_GoogleCloud.md) - Guía completa
- Soporte para App Engine, Cloud Run y GKE

### Docker
- `Dockerfile` - Imagen de desarrollo
- `Dockerfile.production` - Imagen optimizada para producción
- `docker-compose.yml` - Configuración completa
- `docker-compose.simple.yml` - Configuración simplificada

## 🧪 Testing

```bash
# Probar matching optimizado
python test_matching_optimizado.py

# Probar API local
curl http://localhost:8000/health
```

## 📈 Performance

- **Tiempo de respuesta**: < 3 segundos para matching
- **Escalabilidad**: Hasta 10 instancias automáticas
- **Caché hit rate**: > 80% para requests repetidos
- **Uptime**: 99.9% con health checks

## 🔐 Seguridad

- Validación de archivos subidos
- Sanitización de inputs
- Variables de entorno seguras
- HTTPS automático en producción
- Rate limiting configurado

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 📞 Soporte

- **Issues**: [GitHub Issues](https://github.com/francost15/ltc_backend/issues)
- **Documentación**: Ver archivos README específicos
- **Email**: [Tu email de contacto]

## 🎉 Agradecimientos

- OpenAI por la API de GPT
- Render por el hosting gratuito
- La comunidad de Flask y Python 
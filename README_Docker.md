# 🐳 Docker Compose para LTC Backend

Este proyecto incluye una configuración completa de Docker Compose para ejecutar la aplicación de matching de candidatos con PostgreSQL.

## 📋 Prerrequisitos

- Docker Desktop instalado
- Docker Compose instalado
- Al menos 4GB de RAM disponible

## 🚀 Inicio Rápido

### 1. Configuración Básica

```bash
# Clonar el repositorio (si no lo tienes)
git clone <tu-repositorio>
cd ltc-backend-python

# Configurar variables de entorno (opcional)
cp .env.example .env
# Editar .env con tus configuraciones
```

### 2. Ejecutar con Docker Compose

#### Opción A: Versión Simple (Recomendada para desarrollo)
```bash
# Ejecutar solo la app y PostgreSQL
docker-compose -f docker-compose.simple.yml up -d

# Ver logs
docker-compose -f docker-compose.simple.yml logs -f app
```

#### Opción B: Versión Completa (Producción)
```bash
# Ejecutar todos los servicios (PostgreSQL, App, Redis, Nginx)
docker-compose up -d

# Ver logs
docker-compose logs -f app
```

### 3. Verificar que todo funciona

```bash
# Verificar que los contenedores están corriendo
docker-compose ps

# Probar la API
curl http://localhost:8000/health
# o
curl http://localhost/health  # si usas la versión completa con Nginx
```

## 🔧 Configuración

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# OpenAI API Key (requerido para matching)
OPENAI_API_KEY=tu-api-key-de-openai

# Configuración de la aplicación
SECRET_KEY=tu-clave-secreta-super-segura
FLASK_DEBUG=False

# Base de datos (opcional, usa valores por defecto)
DATABASE_URL=postgresql://ltc_user:ltc_password_2024@postgres:5432/ltc_db
```

### Puertos

- **8000**: Aplicación Flask (versión simple)
- **80**: Nginx proxy (versión completa)
- **5432**: PostgreSQL
- **6379**: Redis (versión completa)

## 📊 Estructura de Servicios

### Versión Simple (`docker-compose.simple.yml`)
- **postgres**: Base de datos PostgreSQL
- **app**: Aplicación Flask con Gunicorn

### Versión Completa (`docker-compose.yml`)
- **postgres**: Base de datos PostgreSQL
- **app**: Aplicación Flask con Gunicorn
- **redis**: Caché Redis (opcional)
- **nginx**: Proxy reverso con rate limiting

## 🛠️ Comandos Útiles

### Gestión de Contenedores
```bash
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Reiniciar un servicio específico
docker-compose restart app

# Ver logs en tiempo real
docker-compose logs -f app

# Ejecutar comandos dentro del contenedor
docker-compose exec app python manage.py shell
```

### Base de Datos
```bash
# Conectar a PostgreSQL
docker-compose exec postgres psql -U ltc_user -d ltc_db

# Hacer backup
docker-compose exec postgres pg_dump -U ltc_user ltc_db > backup.sql

# Restaurar backup
docker-compose exec -T postgres psql -U ltc_user -d ltc_db < backup.sql
```

### Desarrollo
```bash
# Reconstruir imagen después de cambios
docker-compose build app

# Ejecutar tests
docker-compose exec app python -m pytest

# Ver logs de todos los servicios
docker-compose logs
```

## 🔍 Troubleshooting

### Problemas Comunes

#### 1. Puerto 8000 ya está en uso
```bash
# Cambiar puerto en docker-compose.yml
ports:
  - "8001:8000"  # Usar puerto 8001 en lugar de 8000
```

#### 2. Error de conexión a la base de datos
```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps postgres

# Ver logs de PostgreSQL
docker-compose logs postgres

# Reiniciar PostgreSQL
docker-compose restart postgres
```

#### 3. Error de permisos en uploads
```bash
# Crear directorio uploads con permisos correctos
mkdir -p uploads
chmod 755 uploads
```

#### 4. Problemas de memoria
```bash
# Aumentar memoria en Docker Desktop
# Settings > Resources > Memory: 4GB o más
```

### Logs y Debugging

```bash
# Ver logs de la aplicación
docker-compose logs app

# Ver logs de PostgreSQL
docker-compose logs postgres

# Ver logs de Nginx (versión completa)
docker-compose logs nginx

# Ver logs de Redis (versión completa)
docker-compose logs redis
```

## 📈 Monitoreo

### Health Checks
```bash
# Verificar estado de los servicios
curl http://localhost:8000/health

# Verificar estado de PostgreSQL
docker-compose exec postgres pg_isready -U ltc_user -d ltc_db
```

### Métricas
```bash
# Ver uso de recursos
docker stats

# Ver información de los contenedores
docker-compose ps
```

## 🚀 Despliegue en Producción

### 1. Configuración de Producción
```bash
# Usar versión completa
docker-compose -f docker-compose.yml up -d

# Configurar variables de entorno de producción
export FLASK_DEBUG=False
export SECRET_KEY=clave-super-segura-produccion
```

### 2. SSL/HTTPS
```bash
# Configurar certificados SSL en nginx.conf
# Agregar configuración SSL en el servidor Nginx
```

### 3. Backup Automático
```bash
# Crear script de backup
#!/bin/bash
docker-compose exec postgres pg_dump -U ltc_user ltc_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

## 📝 Notas Importantes

1. **Primera ejecución**: La base de datos se inicializa automáticamente con datos de ejemplo
2. **Persistencia**: Los datos de PostgreSQL se guardan en un volumen Docker
3. **Archivos**: Los CVs subidos se guardan en el directorio `./uploads`
4. **Caché**: Redis mejora el rendimiento del matching (versión completa)
5. **Rate Limiting**: Nginx incluye protección contra spam (versión completa)

## 🔗 Enlaces Útiles

- **API Health**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379 (versión completa)
- **Nginx**: http://localhost/ (versión completa) 
# 🚀 Despliegue en Render

Esta guía te ayudará a desplegar tu API de matching de candidatos en Render de forma rápida y sencilla.

## 📋 Prerrequisitos

1. **Cuenta en Render**
   - Crear cuenta en [Render.com](https://render.com)
   - Conectar tu cuenta de GitHub/GitLab

2. **Repositorio en GitHub/GitLab**
   - Tu código debe estar en un repositorio público o privado

## 🚀 Pasos para Desplegar

### Paso 1: Preparar el Repositorio

Asegúrate de que tu repositorio contenga estos archivos:

```
ltc-backend-python/
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias Python
├── render.yaml           # Configuración de Render
├── render-build.sh       # Script de build (opcional)
├── config/
├── routes/
├── services/
└── utils/
```

### Paso 2: Crear Servicio en Render

#### Opción A: Usando render.yaml (Recomendado)

1. **Ir a Render Dashboard**
   - Ve a [dashboard.render.com](https://dashboard.render.com)
   - Haz clic en "New +"

2. **Seleccionar "Blueprint"**
   - Elige "Blueprint" para usar render.yaml
   - Conecta tu repositorio de GitHub/GitLab

3. **Configurar Variables de Entorno**
   - Render detectará automáticamente la configuración
   - Solo necesitas configurar `OPENAI_API_KEY` manualmente

#### Opción B: Configuración Manual

1. **Crear Web Service**
   - Ve a "New +" → "Web Service"
   - Conecta tu repositorio

2. **Configurar Build**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:create_app()
   ```

3. **Configurar Variables de Entorno**
   ```
   PYTHON_VERSION: 3.11.0
   FLASK_DEBUG: False
   SECRET_KEY: [generar automáticamente]
   UPLOAD_FOLDER: /opt/render/project/src/uploads
   MAX_CONTENT_LENGTH: 16777216
   OPENAI_API_KEY: [tu-api-key-de-openai]
   ```

### Paso 3: Crear Base de Datos PostgreSQL

1. **Crear PostgreSQL Database**
   - Ve a "New +" → "PostgreSQL"
   - Nombre: `ltc-postgres`
   - Plan: `Starter` ($7/mes) o `Free` (para desarrollo)

2. **Configurar Base de Datos**
   - Database Name: `ltc_db`
   - User: `ltc_user`
   - Password: [generado automáticamente]

3. **Conectar con el Servicio**
   - En tu servicio web, agrega la variable:
   ```
   DATABASE_URL: [connection string de la base de datos]
   ```

### Paso 4: Configurar Variables de Entorno

En el dashboard de tu servicio web, configura estas variables:

#### Variables Requeridas
```
OPENAI_API_KEY=tu-api-key-de-openai-aqui
```

#### Variables Opcionales
```
FLASK_DEBUG=False
SECRET_KEY=[generado automáticamente por Render]
UPLOAD_FOLDER=/opt/render/project/src/uploads
MAX_CONTENT_LENGTH=16777216
```

## 🔧 Configuración Avanzada

### Personalizar render.yaml

```yaml
services:
  - type: web
    name: ltc-backend-api
    env: python
    plan: starter
    region: oregon
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:create_app()
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: FLASK_DEBUG
        value: False
      - key: SECRET_KEY
        generateValue: true
      - key: OPENAI_API_KEY
        sync: false
    healthCheckPath: /health
    autoDeploy: true

databases:
  - name: ltc-postgres
    databaseName: ltc_db
    user: ltc_user
    plan: starter
    region: oregon
```

### Configurar Dominio Personalizado

1. **En Render Dashboard**
   - Ve a tu servicio web
   - Pestaña "Settings"
   - Sección "Custom Domains"

2. **Agregar Dominio**
   - Agrega tu dominio: `api.tudominio.com`
   - Render te dará un registro CNAME

3. **Configurar DNS**
   - Ve a tu proveedor de DNS
   - Crea registro CNAME:
     ```
     api.tudominio.com → tu-servicio.onrender.com
     ```

## 📊 Monitoreo y Logs

### Ver Logs en Tiempo Real

```bash
# En Render Dashboard
# Ve a tu servicio → Pestaña "Logs"
# O usa la CLI de Render (si está disponible)
```

### Health Checks

Tu API incluye un endpoint de health check:
```
GET https://tu-servicio.onrender.com/health
```

Respuesta esperada:
```json
{
  "status": "ok",
  "database": "connected"
}
```

## 🔄 CI/CD Automático

Render se integra automáticamente con GitHub/GitLab:

### Configurar Auto-Deploy

1. **En Render Dashboard**
   - Ve a tu servicio
   - Pestaña "Settings"
   - Sección "Build & Deploy"

2. **Configurar Triggers**
   - Auto-Deploy: Enabled
   - Branch: `main` (o tu rama principal)

### Despliegue Manual

```bash
# Desde Render Dashboard
# Ve a tu servicio → "Manual Deploy" → "Deploy latest commit"
```

## 💰 Planes y Costos

### Planes Disponibles

1. **Free Plan** (Desarrollo)
   - $0/mes
   - 750 horas/mes
   - Sleep después de 15 min de inactividad
   - 512MB RAM
   - 0.1 CPU

2. **Starter Plan** (Producción)
   - $7/mes
   - Siempre activo
   - 512MB RAM
   - 0.5 CPU

3. **Standard Plan** (Alta demanda)
   - $25/mes
   - 1GB RAM
   - 1 CPU

### Base de Datos

1. **Free PostgreSQL**
   - $0/mes
   - 90 días máximo
   - 1GB almacenamiento

2. **Starter PostgreSQL**
   - $7/mes
   - Siempre activo
   - 1GB almacenamiento

## 🚨 Troubleshooting

### Problemas Comunes

#### 1. Error de Build
```bash
# Verificar requirements.txt
# Asegurarse de que todas las dependencias están listadas
# Verificar que no hay dependencias de sistema faltantes
```

#### 2. Error de Conexión a Base de Datos
```bash
# Verificar DATABASE_URL en variables de entorno
# Asegurarse de que la base de datos está activa
# Verificar que el usuario tiene permisos
```

#### 3. Error de Memoria
```bash
# Aumentar plan a Starter o Standard
# Optimizar el código para usar menos memoria
# Reducir número de workers en gunicorn
```

#### 4. Timeout en Requests
```bash
# Aumentar timeout en gunicorn
# Optimizar consultas de base de datos
# Usar caché para operaciones costosas
```

### Logs de Debug

```bash
# En Render Dashboard
# Ve a tu servicio → Pestaña "Logs"
# Buscar errores específicos
# Verificar variables de entorno
```

## 🔐 Seguridad

### Variables de Entorno Seguras

- **Nunca** commits API keys en el código
- Usa variables de entorno en Render
- Genera SECRET_KEY automáticamente

### HTTPS Automático

Render proporciona HTTPS automático:
- Certificados SSL gratuitos
- Redirección automática HTTP → HTTPS
- HSTS headers

## 📈 Performance y Escalado

### Optimizaciones Recomendadas

1. **Caché**
   ```python
   # Usar Redis o caché en memoria
   # Implementar caché para resultados de matching
   ```

2. **Base de Datos**
   ```sql
   -- Crear índices apropiados
   -- Optimizar consultas
   -- Usar connection pooling
   ```

3. **Workers**
   ```bash
   # Ajustar número de workers según CPU disponible
   # workers = (2 x CPU cores) + 1
   ```

### Monitoreo de Performance

```bash
# En Render Dashboard
# Ve a tu servicio → Pestaña "Metrics"
# Monitorear:
# - Response time
# - Memory usage
# - CPU usage
# - Request count
```

## 🔗 URLs y Endpoints

Después del despliegue, tu API estará disponible en:

- **URL Principal**: `https://tu-servicio.onrender.com`
- **Health Check**: `https://tu-servicio.onrender.com/health`
- **API Docs**: `https://tu-servicio.onrender.com/`

### Endpoints Disponibles

```
GET  /                    - Información de la API
GET  /health             - Health check
POST /api/v1/candidatos/{usuario_id}/upload-cv  - Subir CV
GET  /api/v1/candidatos/{usuario_id}/matches    - Obtener matches
```

## 🎉 ¡Listo!

Tu API estará funcionando en Render con:

- ✅ HTTPS automático
- ✅ Escalado automático
- ✅ Base de datos PostgreSQL
- ✅ Logs en tiempo real
- ✅ Monitoreo de performance
- ✅ CI/CD automático

## 📞 Soporte

- **Documentación**: [Render Docs](https://render.com/docs)
- **Comunidad**: [Render Community](https://community.render.com)
- **Soporte**: [Render Support](https://render.com/support) 
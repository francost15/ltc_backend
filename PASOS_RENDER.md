# 🚀 PASOS PARA SUBIR A RENDER

## 📋 Checklist de Preparación

### ✅ Archivos Necesarios (Ya creados)
- [x] `render.yaml` - Configuración de Render
- [x] `Dockerfile.render` - Dockerfile para Render
- [x] `render-build.sh` - Script de build
- [x] `requirements.txt` - Dependencias Python
- [x] `app.py` - Aplicación principal

### ✅ Repositorio en GitHub
- [ ] Subir código a GitHub
- [ ] Asegurarse de que el repositorio es público o privado

## 🚀 PASOS PASO A PASO

### Paso 1: Crear Cuenta en Render
1. Ve a [render.com](https://render.com)
2. Haz clic en "Get Started"
3. Conecta tu cuenta de GitHub
4. Autoriza acceso a tu repositorio

### Paso 2: Crear Base de Datos PostgreSQL
1. En Render Dashboard, haz clic en "New +"
2. Selecciona "PostgreSQL"
3. Configura:
   - **Name**: `ltc-postgres`
   - **Database**: `ltc_db`
   - **User**: `ltc_user`
   - **Plan**: `Free` (para desarrollo) o `Starter` ($7/mes)
   - **Region**: `Oregon (US West)`
4. Haz clic en "Create Database"
5. **IMPORTANTE**: Guarda la `Connection String` que te da Render

### Paso 3: Crear Web Service
1. En Render Dashboard, haz clic en "New +"
2. Selecciona "Blueprint"
3. Conecta tu repositorio de GitHub
4. Render detectará automáticamente `render.yaml`
5. Haz clic en "Apply"

### Paso 4: Configurar Variables de Entorno
En tu servicio web, ve a "Environment" y agrega:

#### Variables Requeridas:
```
OPENAI_API_KEY=tu-api-key-de-openai-aqui
```

#### Variables Opcionales (ya configuradas en render.yaml):
```
FLASK_DEBUG=False
SECRET_KEY=[generado automáticamente]
UPLOAD_FOLDER=/opt/render/project/src/uploads
MAX_CONTENT_LENGTH=16777216
```

### Paso 5: Conectar Base de Datos
1. En tu servicio web, ve a "Environment"
2. Agrega la variable:
```
DATABASE_URL=[connection-string-de-tu-base-de-datos]
```

### Paso 6: Desplegar
1. Haz clic en "Create Web Service"
2. Render comenzará el build automáticamente
3. Espera 5-10 minutos para que termine el despliegue

## 🔧 Configuración Manual (Si Blueprint no funciona)

### Opción B: Configuración Manual

1. **Crear Web Service**
   - "New +" → "Web Service"
   - Conecta tu repositorio

2. **Configurar Build Settings**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:create_app()
   ```

3. **Configurar Environment Variables**
   ```
   PYTHON_VERSION: 3.11.0
   FLASK_DEBUG: False
   SECRET_KEY: [generar automáticamente]
   UPLOAD_FOLDER: /opt/render/project/src/uploads
   MAX_CONTENT_LENGTH: 16777216
   OPENAI_API_KEY: [tu-api-key-de-openai]
   DATABASE_URL: [connection-string-de-postgres]
   ```

## 🧪 Probar el Despliegue

### Verificar que Funciona
1. Ve a la URL de tu servicio: `https://tu-servicio.onrender.com`
2. Deberías ver la información de la API
3. Prueba el health check: `https://tu-servicio.onrender.com/health`

### Probar Endpoints
```bash
# Health check
curl https://tu-servicio.onrender.com/health

# Información de la API
curl https://tu-servicio.onrender.com/

# Subir CV (reemplaza con usuario_id real)
curl -X POST https://tu-servicio.onrender.com/api/v1/candidatos/test-user/upload-cv \
  -F "file=@tu-cv.pdf"

# Obtener matches (reemplaza con usuario_id real)
curl https://tu-servicio.onrender.com/api/v1/candidatos/test-user/matches
```

## 🚨 Solución de Problemas

### Error de Build
- Verifica que `requirements.txt` existe y está correcto
- Revisa los logs en Render Dashboard
- Asegúrate de que todas las dependencias están listadas

### Error de Base de Datos
- Verifica que `DATABASE_URL` está configurada correctamente
- Asegúrate de que la base de datos está activa
- Revisa que el usuario tiene permisos

### Error de Memoria
- Cambia a plan Starter ($7/mes)
- Reduce el número de workers en gunicorn
- Optimiza el código

### Error de Timeout
- Aumenta el timeout en gunicorn
- Optimiza las consultas de base de datos
- Usa caché para operaciones costosas

## 📊 Monitoreo

### Ver Logs
1. Ve a tu servicio en Render Dashboard
2. Pestaña "Logs"
3. Ver logs en tiempo real

### Ver Métricas
1. Ve a tu servicio en Render Dashboard
2. Pestaña "Metrics"
3. Monitorear:
   - Response time
   - Memory usage
   - CPU usage
   - Request count

## 🔄 Actualizaciones

### Despliegue Automático
- Render se actualiza automáticamente cuando haces push a `main`
- No necesitas hacer nada más

### Despliegue Manual
1. Ve a tu servicio en Render Dashboard
2. Haz clic en "Manual Deploy"
3. Selecciona "Deploy latest commit"

## 💰 Costos

### Plan Free (Desarrollo)
- $0/mes
- 750 horas/mes
- Sleep después de 15 min de inactividad
- Perfecto para desarrollo y pruebas

### Plan Starter (Producción)
- $7/mes
- Siempre activo
- Ideal para producción

## 🎉 ¡Listo!

Tu API estará funcionando en:
```
https://tu-servicio.onrender.com
```

### URLs Importantes:
- **API Principal**: `https://tu-servicio.onrender.com/`
- **Health Check**: `https://tu-servicio.onrender.com/health`
- **Subir CV**: `https://tu-servicio.onrender.com/api/v1/candidatos/{usuario_id}/upload-cv`
- **Obtener Matches**: `https://tu-servicio.onrender.com/api/v1/candidatos/{usuario_id}/matches`

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs en Render Dashboard
2. Consulta la [documentación de Render](https://render.com/docs)
3. Únete a la [comunidad de Render](https://community.render.com) 
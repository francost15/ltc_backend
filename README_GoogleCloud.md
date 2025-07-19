# ☁️ Despliegue en Google Cloud Platform

Esta guía te ayudará a desplegar tu API de matching de candidatos en Google Cloud Platform.

## 📋 Prerrequisitos

1. **Cuenta de Google Cloud Platform**
   - Crear cuenta en [Google Cloud Console](https://console.cloud.google.com)
   - Habilitar facturación

2. **Google Cloud CLI**
   ```bash
   # Instalar gcloud CLI
   # Windows: https://cloud.google.com/sdk/docs/install#windows
   # macOS: brew install google-cloud-sdk
   # Linux: https://cloud.google.com/sdk/docs/install#linux
   ```

3. **Docker Desktop** (ya instalado)

## 🚀 Opciones de Despliegue

### 1. 🏗️ Google App Engine (Recomendado para principiantes)

**Ventajas:**
- Fácil de configurar
- Escalado automático
- Sin gestión de infraestructura
- Integración con Cloud SQL

**Desventajas:**
- Menos control sobre la configuración
- Puede ser más costoso para tráfico alto

### 2. 🚀 Cloud Run (Recomendado para APIs)

**Ventajas:**
- Escalado a cero (solo pagas cuando se usa)
- Muy rápido para APIs
- Fácil de configurar
- Costo optimizado

**Desventajas:**
- Cold starts
- Límites de tiempo de ejecución

### 3. 🐳 Google Kubernetes Engine (GKE) (Para producción avanzada)

**Ventajas:**
- Control total sobre la infraestructura
- Escalado avanzado
- Alta disponibilidad
- Ideal para microservicios

**Desventajas:**
- Complejidad de configuración
- Requiere conocimientos de Kubernetes
- Más costoso

## 🔧 Configuración Inicial

### 1. Autenticación con Google Cloud

```bash
# Iniciar sesión
gcloud auth login

# Configurar proyecto (reemplaza con tu PROJECT_ID)
gcloud config set project TU_PROJECT_ID

# Verificar configuración
gcloud config list
```

### 2. Habilitar APIs necesarias

```bash
# Habilitar APIs requeridas
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable appengine.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable sqladmin.googleapis.com
```

### 3. Configurar Docker para Google Cloud

```bash
# Configurar Docker para usar gcloud
gcloud auth configure-docker
```

## 🚀 Despliegue Rápido

### Opción A: Script Automatizado

```bash
# Dar permisos de ejecución
chmod +x scripts/deploy-to-gcp.sh

# Desplegar en App Engine
./scripts/deploy-to-gcp.sh TU_PROJECT_ID us-central1 app-engine

# Desplegar en Cloud Run
./scripts/deploy-to-gcp.sh TU_PROJECT_ID us-central1 cloud-run

# Desplegar en GKE
./scripts/deploy-to-gcp.sh TU_PROJECT_ID us-central1 gke
```

### Opción B: Despliegue Manual

#### 1. App Engine

```bash
# Build de la imagen
docker build -f Dockerfile.production -t gcr.io/TU_PROJECT_ID/ltc-backend:latest .

# Push a Container Registry
docker push gcr.io/TU_PROJECT_ID/ltc-backend:latest

# Desplegar
gcloud app deploy app.yaml
```

#### 2. Cloud Run

```bash
# Build y push
docker build -f Dockerfile.production -t gcr.io/TU_PROJECT_ID/ltc-backend:latest .
docker push gcr.io/TU_PROJECT_ID/ltc-backend:latest

# Desplegar
gcloud run deploy ltc-backend \
    --image gcr.io/TU_PROJECT_ID/ltc-backend:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --max-instances 10
```

#### 3. GKE

```bash
# Crear cluster
gcloud container clusters create ltc-cluster \
    --region us-central1 \
    --num-nodes 3 \
    --machine-type e2-standard-2 \
    --enable-autoscaling \
    --min-nodes 1 \
    --max-nodes 10

# Obtener credenciales
gcloud container clusters get-credentials ltc-cluster --region us-central1

# Aplicar deployment
kubectl apply -f deployment.yaml
```

## 🗄️ Configuración de Base de Datos

### Cloud SQL (PostgreSQL)

```bash
# Crear instancia de Cloud SQL
gcloud sql instances create ltc-postgres \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --root-password=tu-password-super-seguro

# Crear base de datos
gcloud sql databases create ltc_db --instance=ltc-postgres

# Crear usuario
gcloud sql users create ltc_user \
    --instance=ltc-postgres \
    --password=ltc_password_2024

# Obtener IP de la instancia
gcloud sql instances describe ltc-postgres --format='value(connectionName)'
```

### Actualizar Variables de Entorno

```bash
# Para App Engine
gcloud app deploy app.yaml --set-env-vars DATABASE_URL="postgresql://ltc_user:ltc_password_2024@/ltc_db?host=/cloudsql/TU_PROJECT_ID:us-central1:ltc-postgres"

# Para Cloud Run
gcloud run services update ltc-backend \
    --set-env-vars DATABASE_URL="postgresql://ltc_user:ltc_password_2024@/ltc_db?host=/cloudsql/TU_PROJECT_ID:us-central1:ltc-postgres"
```

## 🔐 Configuración de Seguridad

### Secrets Management

```bash
# Crear secret para OpenAI API Key
gcloud secrets create openai-api-key --data-file=- <<< "tu-api-key-de-openai"

# Crear secret para clave secreta
gcloud secrets create ltc-secret-key --data-file=- <<< "tu-clave-secreta-super-segura"
```

### Variables de Entorno Seguras

```yaml
# En app.yaml o deployment.yaml
env_variables:
  OPENAI_API_KEY: "projects/TU_PROJECT_ID/secrets/openai-api-key/versions/latest"
  SECRET_KEY: "projects/TU_PROJECT_ID/secrets/ltc-secret-key/versions/latest"
```

## 📊 Monitoreo y Logs

### Cloud Logging

```bash
# Ver logs de App Engine
gcloud app logs tail

# Ver logs de Cloud Run
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ltc-backend"

# Ver logs de GKE
kubectl logs -f deployment/ltc-backend
```

### Cloud Monitoring

```bash
# Habilitar Cloud Monitoring
gcloud services enable monitoring.googleapis.com

# Ver métricas
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com"
```

## 💰 Optimización de Costos

### App Engine
- Usar `F1` o `F2` instances para desarrollo
- Configurar `min_idle_instances: 0` para ahorrar en desarrollo

### Cloud Run
- Configurar `--max-instances` apropiado
- Usar `--cpu-throttling` para ahorrar CPU

### GKE
- Usar `e2-standard-2` para desarrollo
- Configurar `--enable-autoscaling` con límites apropiados

## 🔄 CI/CD con Cloud Build

### Configurar Trigger

```bash
# Crear trigger de Cloud Build
gcloud builds triggers create github \
    --repo-name=tu-repositorio \
    --repo-owner=tu-usuario \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml
```

### Automatizar Despliegue

```yaml
# En cloudbuild.yaml, agregar paso de despliegue
steps:
  # ... pasos de build ...
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'ltc-backend', '--image', 'gcr.io/$PROJECT_ID/ltc-backend:$COMMIT_SHA', '--region', 'us-central1', '--platform', 'managed', '--allow-unauthenticated']
```

## 🚨 Troubleshooting

### Problemas Comunes

#### 1. Error de permisos
```bash
# Verificar permisos
gcloud projects get-iam-policy TU_PROJECT_ID

# Asignar roles necesarios
gcloud projects add-iam-policy-binding TU_PROJECT_ID \
    --member="user:tu-email@gmail.com" \
    --role="roles/cloudbuild.builds.builder"
```

#### 2. Error de conexión a base de datos
```bash
# Verificar que Cloud SQL está corriendo
gcloud sql instances describe ltc-postgres

# Verificar conectividad
gcloud sql connect ltc-postgres --user=ltc_user
```

#### 3. Error de memoria
```bash
# Aumentar memoria en Cloud Run
gcloud run services update ltc-backend --memory 4Gi

# O en App Engine
# Cambiar en app.yaml: memory_gb: 4
```

### Logs de Debug

```bash
# Ver logs detallados
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50

# Ver métricas de rendimiento
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com/request_count"
```

## 📈 Escalado y Performance

### Configuración de Escalado

```yaml
# App Engine (app.yaml)
automatic_scaling:
  target_cpu_utilization: 0.65
  min_instances: 1
  max_instances: 20
  min_idle_instances: 1
  max_idle_instances: 5

# Cloud Run
gcloud run services update ltc-backend \
    --max-instances 20 \
    --concurrency 80 \
    --cpu-throttling
```

### Optimización de Performance

1. **Caché**: Usar Cloud Memorystore (Redis)
2. **CDN**: Configurar Cloud CDN
3. **Load Balancing**: Usar Cloud Load Balancing
4. **Monitoring**: Configurar alertas de performance

## 🔗 URLs y Endpoints

Después del despliegue, tu API estará disponible en:

- **App Engine**: `https://TU_PROJECT_ID.appspot.com`
- **Cloud Run**: `https://ltc-backend-XXXXX-uc.a.run.app`
- **GKE**: `https://api.tudominio.com` (con dominio configurado)

### Endpoints Disponibles

- `GET /` - Información de la API
- `GET /health` - Health check
- `POST /api/v1/candidatos/{usuario_id}/upload-cv` - Subir CV
- `GET /api/v1/candidatos/{usuario_id}/matches` - Obtener matches

## 📞 Soporte

- **Documentación oficial**: [Google Cloud Documentation](https://cloud.google.com/docs)
- **Comunidad**: [Google Cloud Community](https://cloud.google.com/community)
- **Soporte técnico**: [Google Cloud Support](https://cloud.google.com/support) 
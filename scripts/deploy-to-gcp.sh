#!/bin/bash

# Script de despliegue automatizado para Google Cloud Platform
# Uso: ./scripts/deploy-to-gcp.sh [PROJECT_ID] [REGION] [SERVICE]

set -e

# Configuración por defecto
PROJECT_ID=${1:-"tu-project-id"}
REGION=${2:-"us-central1"}
SERVICE=${3:-"app-engine"}  # app-engine, cloud-run, gke

echo "🚀 Iniciando despliegue en Google Cloud Platform"
echo "📊 Proyecto: $PROJECT_ID"
echo "🌍 Región: $REGION"
echo "🔧 Servicio: $SERVICE"

# Verificar que gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI no está instalado"
    echo "📥 Instala desde: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Configurar proyecto
echo "🔧 Configurando proyecto..."
gcloud config set project $PROJECT_ID

# Habilitar APIs necesarias
echo "🔌 Habilitando APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable appengine.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable sqladmin.googleapis.com

# Configurar Docker para usar gcloud
echo "🐳 Configurando Docker..."
gcloud auth configure-docker

# Build y push de la imagen
echo "🏗️ Construyendo imagen Docker..."
IMAGE_NAME="gcr.io/$PROJECT_ID/ltc-backend"
TAG="latest"

docker build -f Dockerfile.production -t $IMAGE_NAME:$TAG .
docker push $IMAGE_NAME:$TAG

echo "✅ Imagen subida: $IMAGE_NAME:$TAG"

# Desplegar según el servicio seleccionado
case $SERVICE in
    "app-engine")
        echo "🚀 Desplegando en App Engine..."
        gcloud app deploy app.yaml --quiet
        echo "✅ App Engine desplegado"
        echo "🌐 URL: https://$PROJECT_ID.appspot.com"
        ;;
    
    "cloud-run")
        echo "🚀 Desplegando en Cloud Run..."
        gcloud run deploy ltc-backend \
            --image $IMAGE_NAME:$TAG \
            --platform managed \
            --region $REGION \
            --allow-unauthenticated \
            --memory 2Gi \
            --cpu 1 \
            --timeout 300 \
            --concurrency 80 \
            --max-instances 10 \
            --set-env-vars FLASK_DEBUG=False \
            --quiet
        
        echo "✅ Cloud Run desplegado"
        echo "🌐 URL: $(gcloud run services describe ltc-backend --region=$REGION --format='value(status.url)')"
        ;;
    
    "gke")
        echo "🚀 Desplegando en Google Kubernetes Engine..."
        
        # Crear cluster si no existe
        CLUSTER_NAME="ltc-cluster"
        if ! gcloud container clusters describe $CLUSTER_NAME --region=$REGION &> /dev/null; then
            echo "🏗️ Creando cluster GKE..."
            gcloud container clusters create $CLUSTER_NAME \
                --region=$REGION \
                --num-nodes=3 \
                --machine-type=e2-standard-2 \
                --enable-autoscaling \
                --min-nodes=1 \
                --max-nodes=10
        fi
        
        # Obtener credenciales del cluster
        gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION
        
        # Crear secrets
        echo "🔐 Creando secrets..."
        kubectl create secret generic ltc-secrets \
            --from-literal=secret-key="tu-clave-secreta-super-segura-ltc-2024-produccion" \
            --from-literal=openai-api-key="tu-api-key-de-openai" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        # Aplicar deployment
        sed "s/PROJECT_ID/$PROJECT_ID/g; s/REGION/$REGION/g" deployment.yaml | kubectl apply -f -
        
        echo "✅ GKE desplegado"
        echo "🌐 Verificar con: kubectl get services"
        ;;
    
    *)
        echo "❌ Servicio no válido: $SERVICE"
        echo "📋 Opciones disponibles: app-engine, cloud-run, gke"
        exit 1
        ;;
esac

echo "🎉 ¡Despliegue completado exitosamente!"
echo "📊 Monitorear en: https://console.cloud.google.com" 
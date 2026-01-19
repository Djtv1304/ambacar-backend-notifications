#!/bin/bash
# =============================================================================
# Script de instalación de Prometheus y Grafana en Kubernetes
# =============================================================================
# Autor: Diego Toscano
# Fecha: Enero 2026
# Descripción: Script para configurar el stack de monitoreo con Helm
# =============================================================================

set -e

echo "=========================================="
echo "🚀 Setup de Monitoreo: Prometheus + Grafana"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que Minikube está corriendo
check_minikube() {
    log_info "Verificando estado de Minikube..."
    if ! minikube status > /dev/null 2>&1; then
        log_warn "Minikube no está corriendo. Iniciando..."
        minikube start --driver=docker --memory=4096 --cpus=2
    else
        log_info "Minikube está corriendo ✓"
    fi
}

# Verificar que Helm está instalado
check_helm() {
    log_info "Verificando Helm..."
    if ! command -v helm &> /dev/null; then
        log_error "Helm no está instalado. Por favor instala Helm primero."
        exit 1
    fi
    log_info "Helm instalado ✓"
}

# Agregar repositorios de Helm
add_helm_repos() {
    log_info "Agregando repositorios de Helm..."

    # Prometheus Community
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true

    # Grafana
    helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true

    # Actualizar repositorios
    helm repo update

    log_info "Repositorios actualizados ✓"
}

# Crear namespace para monitoreo
create_namespace() {
    log_info "Creando namespace 'monitoring'..."
    kubectl create namespace monitoring 2>/dev/null || log_warn "Namespace 'monitoring' ya existe"
}

# Instalar Prometheus
install_prometheus() {
    log_info "Instalando Prometheus..."

    helm upgrade --install prometheus prometheus-community/prometheus \
        --namespace monitoring \
        --set alertmanager.enabled=false \
        --set pushgateway.enabled=false \
        --set server.persistentVolume.enabled=false \
        --set server.service.type=NodePort \
        --wait

    log_info "Prometheus instalado ✓"
}

# Instalar Grafana
install_grafana() {
    log_info "Instalando Grafana..."

    helm upgrade --install grafana grafana/grafana \
        --namespace monitoring \
        --set adminPassword=admin123 \
        --set service.type=NodePort \
        --set persistence.enabled=false \
        --set datasources."datasources\.yaml".apiVersion=1 \
        --set datasources."datasources\.yaml".datasources[0].name=Prometheus \
        --set datasources."datasources\.yaml".datasources[0].type=prometheus \
        --set datasources."datasources\.yaml".datasources[0].url=http://prometheus-server:80 \
        --set datasources."datasources\.yaml".datasources[0].access=proxy \
        --set datasources."datasources\.yaml".datasources[0].isDefault=true \
        --wait

    log_info "Grafana instalado ✓"
}

# Mostrar información de acceso
show_access_info() {
    echo ""
    echo "=========================================="
    echo "🎉 Instalación completada!"
    echo "=========================================="
    echo ""

    # Obtener URL de Prometheus
    PROMETHEUS_PORT=$(kubectl get svc prometheus-server -n monitoring -o jsonpath='{.spec.ports[0].nodePort}')
    PROMETHEUS_URL=$(minikube service prometheus-server -n monitoring --url 2>/dev/null || echo "http://$(minikube ip):$PROMETHEUS_PORT")

    # Obtener URL de Grafana
    GRAFANA_PORT=$(kubectl get svc grafana -n monitoring -o jsonpath='{.spec.ports[0].nodePort}')
    GRAFANA_URL=$(minikube service grafana -n monitoring --url 2>/dev/null || echo "http://$(minikube ip):$GRAFANA_PORT")

    echo -e "${GREEN}📊 Prometheus:${NC}"
    echo "   URL: $PROMETHEUS_URL"
    echo ""
    echo -e "${GREEN}📈 Grafana:${NC}"
    echo "   URL: $GRAFANA_URL"
    echo "   Usuario: admin"
    echo "   Contraseña: admin123"
    echo ""
    echo "=========================================="
    echo "📝 Comandos útiles:"
    echo "=========================================="
    echo ""
    echo "# Abrir Prometheus en el navegador:"
    echo "minikube service prometheus-server -n monitoring"
    echo ""
    echo "# Abrir Grafana en el navegador:"
    echo "minikube service grafana -n monitoring"
    echo ""
    echo "# Ver pods de monitoreo:"
    echo "kubectl get pods -n monitoring"
    echo ""
    echo "# Ver logs de Prometheus:"
    echo "kubectl logs -f deployment/prometheus-server -n monitoring"
    echo ""
}

# Función principal
main() {
    echo ""
    log_info "Iniciando setup de monitoreo..."
    echo ""

    check_minikube
    check_helm
    add_helm_repos
    create_namespace
    install_prometheus
    install_grafana
    show_access_info
}

# Ejecutar
main "$@"
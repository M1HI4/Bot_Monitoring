#!/bin/bash
# Скрипт запуска всех сервисов в WSL2

echo "🚀 Starting monitoring services in WSL2..."

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found! Please install Docker first."
    exit 1
fi

# Создаем необходимые папки
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards

# Создаем конфигурационные файлы Grafana если их нет
if [ ! -f "grafana/provisioning/datasources/datasource.yml" ]; then
    cat > grafana/provisioning/datasources/datasource.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF
fi

if [ ! -f "grafana/provisioning/dashboards/dashboard.yml" ]; then
    cat > grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF
fi

echo "📦 Starting Prometheus, Alertmanager, Node Exporter, Grafana..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 15

echo ""
echo "✅ Services started:"
echo "   Prometheus:   http://localhost:9090"
echo "   Alertmanager: http://localhost:9093" 
echo "   Node Exporter: http://localhost:9100"
echo "   Grafana:      http://localhost:3000"
echo ""
echo "🔐 Grafana credentials:"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "🔍 Check if services are healthy:"
echo "   docker compose ps"
echo ""
echo "📊 Check Prometheus targets:"
echo "   curl -s http://localhost:9090/api/v1/targets | jq .data.activeTargets[].labels"
echo ""
echo "💡 To stop services: docker compose down"

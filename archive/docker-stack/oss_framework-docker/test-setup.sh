#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/../"

echo "==================================="
echo "OSS Framework Docker Setup Tests"
echo "==================================="

echo ""
echo "1. Checking Docker and Docker Compose..."
docker --version
docker-compose --version

echo ""
echo "2. Checking environment file..."
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env created - update values for your environment"
fi

echo ""
echo "3. Building Docker images..."
docker-compose build --no-cache 2>&1 | grep -E "(Building|built|Step)" || true

echo ""
echo "4. Starting services..."
docker-compose up -d

echo ""
echo "5. Waiting for services to be ready..."
sleep 10

echo ""
echo "6. Checking service health..."
echo ""

services=("postgres" "grafana" "metabase" "pgadmin" "prometheus")

for service in "${services[@]}"; do
    container=$(docker-compose ps -q $service)
    if [ -n "$container" ]; then
        status=$(docker inspect -f '{{.State.Status}}' $container)
        echo "✓ $service: $status"
    else
        echo "✗ $service: not running"
    fi
done

echo ""
echo "7. Testing PostgreSQL connectivity..."
if docker-compose exec -T postgres pg_isready -U sis_admin -d sis_analytics > /dev/null 2>&1; then
    echo "✓ PostgreSQL is ready"
else
    echo "✗ PostgreSQL connection failed"
fi

echo ""
echo "8. Checking database schema..."
table_count=$(docker-compose exec -T postgres psql -U sis_admin -d sis_analytics -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema LIKE 'stage_%';" 2>/dev/null || echo "0")
echo "✓ Found $table_count stage tables"

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Access your services:"
echo "  Grafana:     http://localhost:3000"
echo "  Metabase:    http://localhost:3001"
echo "  Superset:    http://localhost:8088"
echo "  pgAdmin:     http://localhost:5050"
echo "  Prometheus:  http://localhost:9090"
echo "  PostgreSQL:  localhost:5432"
echo ""
echo "Default credentials in .env file"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f [service]"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""

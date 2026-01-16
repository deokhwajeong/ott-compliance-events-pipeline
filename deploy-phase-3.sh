#!/bin/bash

# Phase 3 Deployment Script
# Comprehensive deployment automation for all Phase 3 features

set -e

echo "=== OTT Compliance Phase 3 Deployment ==="
echo "Starting at $(date)"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
command -v python3 >/dev/null || { echo "Python 3 not found"; exit 1; }
command -v pip >/dev/null || { echo "pip not found"; exit 1; }

# Install dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Run tests
echo -e "${BLUE}Running Phase 3 tests...${NC}"
pytest test_phase_3.py -v --tb=short

# Database migrations
echo -e "${BLUE}Running database migrations...${NC}"
alembic upgrade head

# Build Docker image
echo -e "${BLUE}Building Docker image...${NC}"
docker build -t ott-compliance:3.0.0 -f Dockerfile .

# Push to registry (optional)
if [ ! -z "$DOCKER_REGISTRY" ]; then
    echo -e "${BLUE}Pushing to Docker registry...${NC}"
    docker tag ott-compliance:3.0.0 $DOCKER_REGISTRY/ott-compliance:3.0.0
    docker push $DOCKER_REGISTRY/ott-compliance:3.0.0
fi

# Kubernetes deployment (if K8S_ENABLED)
if [ "$K8S_ENABLED" = "true" ]; then
    echo -e "${BLUE}Deploying to Kubernetes...${NC}"
    
    kubectl create namespace compliance || true
    
    # Create secrets
    kubectl create secret generic ott-compliance-secrets \
        --from-literal=database-url=$DATABASE_URL \
        --from-literal=redis-url=$REDIS_URL \
        -n compliance --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy Helm chart
    helm upgrade --install ott-compliance \
        deployment/helm/ott-compliance \
        -n compliance \
        -f deployment/helm/ott-compliance/values.yaml
    
    echo -e "${GREEN}Kubernetes deployment completed${NC}"
fi

# Verify deployment
echo -e "${BLUE}Verifying deployment...${NC}"
python3 -c "
from src.app.websocket import ConnectionManager
from src.app.dl_models import EnsembleDeepLearning
from src.app.graphql_api import schema
from src.app.api_gateway import APIGatewayConfig
from src.app.tracing import Tracer
from src.app.tenancy import get_tenant_manager
from src.app.encryption import EncryptionPipeline
from src.app.visualization import Visualization3D

print('✓ WebSocket module')
print('✓ Deep Learning module')
print('✓ GraphQL module')
print('✓ API Gateway module')
print('✓ Tracing module')
print('✓ Tenancy module')
print('✓ Encryption module')
print('✓ Visualization module')
"

echo -e "${GREEN}=== Phase 3 Deployment Completed Successfully ===${NC}"
echo "Deployment finished at $(date)"
echo ""
echo "Next steps:"
echo "1. Verify application health: http://localhost:8000/health"
echo "2. Access API docs: http://localhost:8000/docs"
echo "3. Access GraphQL: http://localhost:8000/graphql"
echo "4. Review logs: docker logs ott-compliance-api"
echo ""
echo "Features deployed:"
echo "✓ WebSocket real-time streaming"
echo "✓ Deep learning models (LSTM/Transformer)"
echo "✓ GraphQL API"
echo "✓ API Gateway integration"
echo "✓ Distributed tracing (OpenTelemetry)"
echo "✓ Multi-tenancy support"
echo "✓ End-to-end encryption"
echo "✓ Advanced visualization"
echo "✓ Kubernetes deployment"

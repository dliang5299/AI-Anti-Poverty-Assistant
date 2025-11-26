#!/bin/bash
# BenefitsFlow Auto-Start Script
# Runs docker-compose automatically on EC2 instance startup

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 BenefitsFlow Auto-Start Script"
echo "=================================="

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ ERROR: docker-compose not found. Please install docker-compose."
    exit 1
fi

# Check if docker.env exists
if [ ! -f "docker.env" ]; then
    echo "⚠️  WARNING: docker.env not found!"
    echo "📝 Creating docker.env from template..."
    
    if [ -f "docker.env.template" ]; then
        cp docker.env.template docker.env
        echo "✅ Created docker.env from template"
        echo "⚠️  IMPORTANT: Edit docker.env and add your AWS Secrets Manager ARNs!"
        echo "   Then run: docker-compose up -d"
        exit 1
    else
        echo "❌ ERROR: docker.env.template not found!"
        exit 1
    fi
fi

# Wait for Docker to be ready
echo "⏳ Waiting for Docker to be ready..."
timeout=30
counter=0
while ! docker info &> /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo "❌ ERROR: Docker not ready after $timeout seconds"
        exit 1
    fi
    sleep 1
    counter=$((counter + 1))
done
echo "✅ Docker is ready"

# Start services
echo "🔨 Starting BenefitsFlow services..."
docker-compose up -d --build

# Wait a moment for services to start
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

# Test services
echo ""
echo "🧪 Testing services..."
if curl -s http://localhost:8501/health > /dev/null; then
    echo "✅ UI service is running on port 8501"
else
    echo "⚠️  UI service may not be ready yet"
fi

if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ RAG service is running on port 8000"
else
    echo "⚠️  RAG service may not be ready yet"
fi

echo ""
echo "✅ BenefitsFlow startup complete!"
echo "🌐 Access your app at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8501"
echo "📚 API docs at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8501/api/docs"


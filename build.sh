#!/bin/bash

# Build script for A2A Server components
# Usage: ./build.sh [service-name] [tag]
# Services: a2a-server, docs, marketing, opencode, all

set -e

SERVICE=${1:-"all"}
TAG=${2:-"latest"}
REGISTRY="registry.quantum-forge.net/library"

echo "Building A2A Server components..."
echo "Service: $SERVICE"
echo "Tag: $TAG"

build_service() {
    local service=$1
    local full_tag="${REGISTRY}/${service}:${TAG}"
    echo "Building $service as $full_tag"

    if [ "$service" = "docs" ]; then
        docker build --target docs -f Dockerfile.unified -t $full_tag .
    elif [ "$service" = "marketing" ]; then
        docker build --target marketing -f Dockerfile.unified \
            --build-arg AUTH_SECRET="Gzez2UkA76TcFpnUEXUmT16+/G3UX2RmoGxyByfAJO4=" \
            --build-arg KEYCLOAK_CLIENT_SECRET="Boog6oMQhr6dlF5tebfQ2FuLMhAOU4i1" \
            -t $full_tag .
    elif [ "$service" = "opencode" ]; then
        docker build --target opencode -f Dockerfile.unified -t $full_tag .
    else
        docker build --target $service -f Dockerfile.unified -t $full_tag .
    fi

    echo "Pushing $full_tag"
    docker push $full_tag
}

if [ "$SERVICE" = "all" ]; then
    build_service "a2a-server"
    build_service "docs"
    build_service "marketing"
    build_service "opencode"
else
    build_service "$SERVICE"
fi

echo "Build completed successfully!"

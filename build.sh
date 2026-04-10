#!/bin/bash

# Build script for A2A Server components
# Usage: ./build.sh [service-name] [tag]
# Services: a2a-server, docs, marketing, worker, all

set -e

SERVICE=${1:-"all"}
TAG=${2:-"latest"}
REGISTRY="registry.quantum-forge.net/library"

echo "Building A2A Server components..."
echo "Service: $SERVICE"
echo "Tag: $TAG"

build_service() {
    local target=$1
    local image_name=$2
    local full_tag="${REGISTRY}/${image_name}:${TAG}"
    echo "Building ${target} as ${full_tag}"

    if [ "$target" = "docs" ]; then
        docker build --target docs -f Dockerfile.unified -t $full_tag .
    elif [ "$target" = "marketing" ]; then
        docker build --target marketing -f Dockerfile.unified \
            --build-arg AUTH_SECRET="Gzez2UkA76TcFpnUEXUmT16+/G3UX2RmoGxyByfAJO4=" \
            --build-arg KEYCLOAK_CLIENT_SECRET="Boog6oMQhr6dlF5tebfQ2FuLMhAOU4i1" \
            -t $full_tag .
    elif [ "$target" = "worker" ]; then
        docker build -f Dockerfile.worker -t $full_tag .
    else
        docker build --target $target -f Dockerfile.unified -t $full_tag .
    fi

    echo "Pushing $full_tag"
    docker push $full_tag
}

if [ "$SERVICE" = "all" ]; then
    # NOTE: image_name values must match what's referenced by Helm charts.
    build_service "a2a-server" "a2a-server"
    build_service "docs" "codetether-docs"
    build_service "marketing" "a2a-marketing"
    build_service "worker" "codetether-worker"
else
    # Backwards-compatible single-service mode:
    # - a2a-server -> a2a-server
    # - docs -> codetether-docs
    # - marketing -> a2a-marketing
    # - codetether -> codetether
    case "$SERVICE" in
        a2a-server) build_service "a2a-server" "a2a-server" ;;
        docs) build_service "docs" "codetether-docs" ;;
        marketing) build_service "marketing" "a2a-marketing" ;;
        worker) build_service "worker" "codetether-worker" ;;
        *)
            echo "Unknown service: $SERVICE"
            echo "Services: a2a-server, docs, marketing, worker, all"
            exit 1
            ;;
    esac
fi

echo "Build completed successfully!"

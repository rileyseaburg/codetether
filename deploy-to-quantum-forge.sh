#!/bin/bash
# Deploy A2A Server to Quantum Forge Registry
# This script builds, tags, and pushes the Docker image and Helm chart

set -e

# Configuration
VERSION="${VERSION:-latest}"
REGISTRY="${REGISTRY:-registry.quantum-forge.net}"
PROJECT="${PROJECT:-library}"
IMAGE_NAME="${IMAGE_NAME:-a2a-server}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SKIP_DOCKER="${SKIP_DOCKER:-false}"
SKIP_HELM="${SKIP_HELM:-false}"
DRY_RUN="${DRY_RUN:-false}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function info() { echo -e "${CYAN}$1${NC}"; }
function success() { echo -e "${GREEN}✓ $1${NC}"; }
function error() { echo -e "${RED}✗ $1${NC}"; }
function warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

echo -e "${CYAN}===============================================${NC}"
echo -e "${CYAN}   A2A Server - Quantum Forge Deployment${NC}"
echo -e "${CYAN}===============================================${NC}"
echo ""

# Build full image name
FULL_IMAGE_NAME="$REGISTRY/$PROJECT/$IMAGE_NAME:$VERSION"
CHART_PATH="chart/a2a-server"
CHART_VERSION="0.1.0"

info "Configuration:"
echo "  Registry:      $REGISTRY"
echo "  Project:       $PROJECT"
echo "  Image:         $FULL_IMAGE_NAME"
echo "  Chart Path:    $CHART_PATH"
echo "  Chart Version: $CHART_VERSION"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    warning "DRY RUN MODE - No actual push operations will be performed"
    echo ""
fi

# Step 1: Build Docker Image
if [ "$SKIP_DOCKER" != "true" ]; then
    if [ "$SKIP_BUILD" != "true" ]; then
        info "Step 1: Building Docker image..."
        if docker build -t a2a-server:$VERSION .; then
            success "Docker image built successfully"
        else
            error "Failed to build Docker image"
            exit 1
        fi
        echo ""
    fi

    # Step 2: Tag Docker Image
    info "Step 2: Tagging Docker image for Quantum Forge..."
    if docker tag a2a-server:$VERSION $FULL_IMAGE_NAME; then
        success "Image tagged as $FULL_IMAGE_NAME"
    else
        error "Failed to tag Docker image"
        exit 1
    fi
    echo ""

    # Step 3: Push Docker Image
    info "Step 3: Pushing Docker image to Quantum Forge..."
    if [ "$DRY_RUN" = "true" ]; then
        warning "Would execute: docker push $FULL_IMAGE_NAME"
    else
        echo -e "${YELLOW}Pushing to: $FULL_IMAGE_NAME${NC}"
        if docker push $FULL_IMAGE_NAME; then
            success "Docker image pushed successfully"
        else
            error "Failed to push Docker image"
            warning "Make sure you're logged in: docker login $REGISTRY"
            exit 1
        fi
    fi
    echo ""
fi

# Step 4: Package Helm Chart
if [ "$SKIP_HELM" != "true" ]; then
    info "Step 4: Packaging Helm chart..."

    # Update chart values with Quantum Forge image
    VALUES_PATH="$CHART_PATH/values.yaml"
    if [ -f "$VALUES_PATH" ]; then
        info "Updating chart values with Quantum Forge image reference..."
        sed -i.bak "s|repository:.*a2a-server|repository: $REGISTRY/$PROJECT/$IMAGE_NAME|g" "$VALUES_PATH"
        sed -i.bak "s|tag:.*\"latest\"|tag: \"$VERSION\"|g" "$VALUES_PATH"
        rm -f "$VALUES_PATH.bak"
        success "Chart values updated"
    fi

    # Build dependencies
    info "Building chart dependencies..."
    (cd $CHART_PATH && helm dependency build)

    # Package the chart
    if helm package $CHART_PATH; then
        CHART_PACKAGE="a2a-server-$CHART_VERSION.tgz"
        success "Helm chart packaged: $CHART_PACKAGE"
    else
        error "Failed to package Helm chart"
        exit 1
    fi
    echo ""

    # Step 5: Push Helm Chart
    info "Step 5: Pushing Helm chart to Quantum Forge..."
    if [ "$DRY_RUN" = "true" ]; then
        warning "Would execute: helm push $CHART_PACKAGE oci://$REGISTRY/$PROJECT"
    else
        CHART_PACKAGE="a2a-server-$CHART_VERSION.tgz"
        echo -e "${YELLOW}Pushing chart: $CHART_PACKAGE${NC}"
        echo -e "${YELLOW}To registry: oci://$REGISTRY/$PROJECT${NC}"

        if helm push $CHART_PACKAGE oci://$REGISTRY/$PROJECT; then
            success "Helm chart pushed successfully"

            # Cleanup package
            if [ -f "$CHART_PACKAGE" ]; then
                rm -f $CHART_PACKAGE
                info "Cleaned up local chart package"
            fi
        else
            error "Failed to push Helm chart"
            warning "Make sure you're logged in: helm registry login $REGISTRY"
            exit 1
        fi
    fi
    echo ""
fi

# Summary
echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}   Deployment Summary${NC}"
echo -e "${GREEN}===============================================${NC}"
echo ""

if [ "$SKIP_DOCKER" != "true" ]; then
    success "Docker Image: $FULL_IMAGE_NAME"
fi

if [ "$SKIP_HELM" != "true" ]; then
    success "Helm Chart: oci://$REGISTRY/$PROJECT/a2a-server:$CHART_VERSION"
fi

echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Verify image: docker pull $FULL_IMAGE_NAME"
echo "  2. Install chart: helm install a2a-server oci://$REGISTRY/$PROJECT/a2a-server --version $CHART_VERSION --namespace a2a-system --create-namespace"
echo "  3. Check status: kubectl get pods -n a2a-system"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    warning "This was a DRY RUN - no changes were made"
fi

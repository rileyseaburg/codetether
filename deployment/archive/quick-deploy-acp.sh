#!/bin/bash

# Quick Deploy to acp.quantum-forge.net
# Run this after logging in to Docker and Helm registries

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 Quick Deploy to acp.quantum-forge.net${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check Helm
if ! command -v helm &> /dev/null; then
    echo -e "${RED}✗ Helm not found. Please install Helm 3.8+.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Helm found${NC}"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl not found. Please install kubectl.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ kubectl found${NC}"

echo ""
echo -e "${YELLOW}Login to registries:${NC}"
echo "  docker login registry.quantum-forge.net"
echo "  helm registry login registry.quantum-forge.net"
echo ""

read -p "Have you logged in to both registries? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please login first, then run this script again.${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}Starting deployment...${NC}"
echo ""

# Make deploy script executable
chmod +x deploy-acp.sh

# Run deployment
PRODUCTION=true ./deploy-acp.sh

echo ""
echo -e "${GREEN}✅ Deployment initiated!${NC}"
echo ""
echo -e "${CYAN}Monitor deployment:${NC}"
echo "  kubectl get pods -n a2a-system -w"
echo ""

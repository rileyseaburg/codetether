# CodeTether Server Makefile
# Variables
DOCKER_IMAGE_NAME = a2a-server-mcp
DOCKER_TAG ?= latest
DOCKER_REGISTRY ?= us-central1-docker.pkg.dev/spotlessbinco/codetether
OCI_REGISTRY = us-central1-docker.pkg.dev/spotlessbinco/codetether
PORT ?= 8000
CHART_PATH = chart/a2a-server
CHART_VERSION ?= 0.4.2
NAMESPACE ?= a2a-server
RELEASE_NAME ?= codetether
VALUES_FILE ?= chart/codetether-values.yaml
RELOAD ?= 0

# Local systemd worker (optional)
LOCAL_WORKER_SERVICE ?= a2a-agent-worker
RESTART_LOCAL_WORKER ?= 1
AUTO_INSTALL_LOCAL_WORKER ?= 1
LOCAL_WORKER_INSTALL_SCRIPT ?= agent_worker/install.sh
SUDO ?= sudo

# Additional image names for full platform
MARKETING_IMAGE_NAME = a2a-marketing
DOCS_IMAGE_NAME = codetether-docs
VOICE_AGENT_IMAGE_NAME = codetether-voice-agent



# Default target
.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@echo ""
	@echo "Docker targets:"
	@grep -E '^docker-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Helm targets:"
	@grep -E '^helm-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Blue-Green Deployment:"
	@grep -E '^(bluegreen-|deploy-blue|deploy-green|rollback-|cleanup-|deploy-status|deploy-fast|deploy-now)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment Deployments (Blue-Green):"
	@grep -E '^k8s[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Kubernetes Utilities:"
	@grep -E '^(get-pods|describe-pod|scale-|rollout-)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "CodeTether targets:"
	@grep -E '^codetether-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Development targets:"
	@grep -E '^(install|test|lint|format|run|docs)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Other targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -vE '^(docker-|helm-|codetether-|bluegreen-|deploy-|rollback-|cleanup-|k8s|get-pods|describe-pod|scale-|rollout-|install|test|lint|format|run|docs)' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Worker management:"
	@grep -E '^local-worker-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment variables:"
	@echo "  DOCKER_TAG      - Docker image tag (default: latest)"
	@echo "  NAMESPACE       - Kubernetes namespace (default: a2a-server)"
	@echo "  CHART_VERSION   - Helm chart version (default: 0.4.2)"
	@echo "  VALUES_FILE     - Path to Helm values file"
	@echo "  DEBUG           - Enable debug output for deployments"


# Docker targets
.PHONY: docker-build
docker-build: ## Build Docker image (API server only)
	docker build -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) . --network=host

.PHONY: docker-build-marketing
docker-build-marketing: ## Build marketing site Docker image
	docker build -t $(MARKETING_IMAGE_NAME):$(DOCKER_TAG) ./marketing-site --network=host

.PHONY: docker-build-docs
docker-build-docs: ## Build docs site Docker image
	docker build -t $(DOCS_IMAGE_NAME):$(DOCKER_TAG) -f Dockerfile.docs . --network=host

.PHONY: docker-build-voice-agent
docker-build-voice-agent: ## Build voice agent Docker image
	docker build -t $(VOICE_AGENT_IMAGE_NAME):$(DOCKER_TAG) ./codetether_voice_agent --network=host

.PHONY: docker-build-all
docker-build-all: docker-build docker-build-marketing docker-build-docs docker-build-voice-agent ## Build all Docker images (server, marketing, docs, voice-agent)

.PHONY: docker-build-no-cache
docker-build-no-cache: ## Build Docker image without cache
	docker build --no-cache -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) .

.PHONY: docker-run
docker-run: ## Run Docker container
	docker run -p $(PORT):8000 --name a2a-server $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-run-detached
docker-run-detached: ## Run Docker container in detached mode
	docker run -d -p $(PORT):8000 --name a2a-server $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-stop
docker-stop: ## Stop Docker container
	docker stop a2a-server || true

.PHONY: docker-remove
docker-remove: ## Remove Docker container
	docker rm a2a-server || true

.PHONY: docker-clean
docker-clean: docker-stop docker-remove ## Stop and remove Docker container

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	docker logs a2a-server

.PHONY: docker-shell
docker-shell: ## Open shell in running container
	docker exec -it a2a-server /bin/bash

.PHONY: docker-push
docker-push: ## Push API server Docker image to OCI registry
	docker tag $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-push-marketing
docker-push-marketing: ## Push marketing site Docker image to OCI registry
	docker tag $(MARKETING_IMAGE_NAME):$(DOCKER_TAG) $(OCI_REGISTRY)/$(MARKETING_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(OCI_REGISTRY)/$(MARKETING_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-push-docs
docker-push-docs: ## Push docs site Docker image to OCI registry
	docker tag $(DOCS_IMAGE_NAME):$(DOCKER_TAG) $(OCI_REGISTRY)/$(DOCS_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(OCI_REGISTRY)/$(DOCS_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-push-voice-agent
docker-push-voice-agent: ## Push voice agent Docker image to OCI registry
	docker tag $(VOICE_AGENT_IMAGE_NAME):$(DOCKER_TAG) $(OCI_REGISTRY)/$(VOICE_AGENT_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(OCI_REGISTRY)/$(VOICE_AGENT_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-push-all
docker-push-all: docker-push docker-push-marketing docker-push-docs docker-push-voice-agent ## Push all Docker images to OCI registry

.PHONY: docker-push-custom
docker-push-custom: ## Push Docker image to custom registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "Error: DOCKER_REGISTRY not set. Use: make docker-push-custom DOCKER_REGISTRY=your-registry"; \
		exit 1; \
	fi
	docker tag $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-pull
docker-pull: ## Pull Docker image from OCI registry
	docker pull $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: docker-pull-custom
docker-pull-custom: ## Pull Docker image from custom registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "Error: DOCKER_REGISTRY not set. Use: make docker-pull-custom DOCKER_REGISTRY=your-registry"; \
		exit 1; \
	fi
	docker pull $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

# Helm targets
.PHONY: helm-package
helm-package: ## Package Helm chart
	helm package $(CHART_PATH)

.PHONY: helm-push
helm-push: helm-package ## Package and push Helm chart to OCI registry
	@CHART_PACKAGE="a2a-server-$(CHART_VERSION).tgz"; \
	if [ ! -f "$$CHART_PACKAGE" ]; then \
		CHART_PACKAGE=$$(ls -t a2a-server-*.tgz 2>/dev/null | head -n1); \
	fi; \
	if [ -z "$$CHART_PACKAGE" ]; then \
		echo "Error: No chart package found. Run 'make helm-package' first."; \
		exit 1; \
	fi; \
	helm push $$CHART_PACKAGE oci://$(OCI_REGISTRY)

.PHONY: helm-install
helm-install: ## Install Helm chart locally
	helm install a2a-server $(CHART_PATH)

.PHONY: helm-upgrade
helm-upgrade: ## Upgrade Helm chart
	helm upgrade a2a-server $(CHART_PATH)

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall Helm chart
	helm uninstall a2a-server

.PHONY: helm-template
helm-template: ## Generate Helm templates
	helm template a2a-server $(CHART_PATH)

.PHONY: helm-lint
helm-lint: ## Lint Helm chart
	helm lint $(CHART_PATH)

.PHONY: helm-test
helm-test: ## Test Helm chart
	helm test a2a-server

# Podman targets (alternative to Docker)
.PHONY: podman-build
podman-build: ## Build image with Podman
	podman build -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) .

.PHONY: podman-run
podman-run: ## Run container with Podman
	podman run -p $(PORT):8000 --name a2a-server $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: podman-push
podman-push: ## Push image to OCI registry with Podman
	@IMAGE_ID=$$(podman images -q $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) | head -n1); \
	if [ -z "$$IMAGE_ID" ]; then \
		echo "Error: Image not found. Run 'make podman-build' first."; \
		exit 1; \
	fi; \
	podman push $$IMAGE_ID $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

.PHONY: podman-stop
podman-stop: ## Stop Podman container
	podman stop a2a-server || true

.PHONY: podman-remove
podman-remove: ## Remove Podman container
	podman rm a2a-server || true

# Development targets
.PHONY: install
install: ## Install Python dependencies
	pip install -r requirements.txt

.PHONY: install-dev
install-dev: ## Install development dependencies
	pip install -r requirements.txt -r requirements-test.txt
	(cd marketing-site && npm install)

.PHONY: test
test: ## Run tests
	python -m pytest tests/

.PHONY: test-cypress
test-cypress: ## Run Cypress tests
	npm test

.PHONY: lint
lint: ## Run linting
	python -m flake8 a2a_server/
	python -m black --check a2a_server/

.PHONY: format
format: ## Format code
	python -m black a2a_server/
	python -m isort a2a_server/

# Python executable (use venv if available)
PYTHON ?= $(shell if [ -f venv/bin/python3 ]; then echo venv/bin/python3; else echo python3; fi)

.PHONY: run
run: ## Run the server locally
	@if [ "$(RELOAD)" = "1" ]; then \
		echo "🔄 Auto-reload enabled"; \
		$(PYTHON) -m watchdog.watchmedo auto-restart --directory=./a2a_server --directory=. --pattern="*.py" --recursive -- $(PYTHON) run_server.py run --host 0.0.0.0 --port $(PORT); \
	else \
		$(PYTHON) run_server.py run --host 0.0.0.0 --port $(PORT); \
	fi

.PHONY: run-dev
run-dev: ## Run the server in development mode (starts Python and Next.js)
	$(MAKE) run-all RELOAD=1

.PHONY: dev
dev: ## Alias for run-all (starts Python and Next.js)
	$(MAKE) run-all RELOAD=1

.PHONY: run-all
run-all: ## Run Python server, React (Next.js) dev server, and a local worker
	@echo "🚀 Starting Python server, React dev server, and local worker..."
	@trap 'kill 0' EXIT; \
	(if [ "$(RELOAD)" = "1" ]; then \
		echo "🔄 Worker auto-reload enabled"; \
		$(PYTHON) -m watchdog.watchmedo auto-restart --directory=./agent_worker --pattern="*.py" --recursive -- $(PYTHON) agent_worker/worker.py --server http://localhost:8000 --name "local-worker" --worker-id "local-worker-1" --codebase A2A-Server-MCP:.; \
	else \
		$(PYTHON) agent_worker/worker.py --server http://localhost:8000 --name "local-worker" --worker-id "local-worker-1" --codebase A2A-Server-MCP:.; \
	fi) & \
	$(MAKE) run RELOAD=$(RELOAD)

.PHONY: worker
worker: ## Run a local worker
	$(PYTHON) agent_worker/worker.py --server http://localhost:8000 --name "local-worker" --worker-id "local-worker-1" --codebase A2A-Server-MCP:.

# Keycloak utilities
.PHONY: keycloak-client
keycloak-client: ## Create/update Keycloak OIDC client via kcadm.sh (requires KEYCLOAK_* env vars)
	@chmod +x scripts/keycloak_upsert_client.sh
	@./scripts/keycloak_upsert_client.sh

# Documentation targets
.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	mkdocs serve

.PHONY: docs-build
docs-build: ## Build documentation
	mkdocs build

.PHONY: docs-deploy
docs-deploy: ## Deploy documentation
	mkdocs gh-deploy

.PHONY: codetether-docs-serve
codetether-docs-serve: ## Serve CodeTether documentation locally
	mkdocs serve -f codetether-mkdocs.yml

.PHONY: codetether-docs-build
codetether-docs-build: ## Build CodeTether documentation
	mkdocs build -f codetether-mkdocs.yml

.PHONY: codetether-docs-deploy
codetether-docs-deploy: ## Deploy CodeTether documentation
	mkdocs gh-deploy -f codetether-mkdocs.yml

# Cleanup targets
.PHONY: clean
clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/

.PHONY: clean-docker
clean-docker: ## Clean up Docker images and containers
	docker system prune -f
	docker image prune -f

# Composite targets
.PHONY: build
build: clean docker-build ## Clean and build Docker image

.PHONY: rebuild
rebuild: clean docker-build-no-cache ## Clean and rebuild Docker image without cache

.PHONY: deploy
deploy: docker-build docker-push ## Build and push Docker image to OCI registry

.PHONY: deploy-helm
deploy-helm: helm-push ## Package and push Helm chart to OCI registry

.PHONY: deploy-all
deploy-all: deploy deploy-helm ## Deploy both Docker image and Helm chart

.PHONY: quick-start
quick-start: docker-build docker-run ## Build and run Docker container

.PHONY: full-clean
full-clean: clean docker-clean clean-docker ## Full cleanup of all artifacts

## One-command deploy: build image, make available to cluster, and helm upgrade/install
.PHONY: one-command-deploy
one-command-deploy: ## Build image, load/push depending on environment, and deploy Helm chart
	@echo "Starting one-command deploy..."
	# Build the local image
	$(MAKE) docker-build

	# If DOCKER_REGISTRY is set we will push to the registry (Harbor)
	@if [ -n "$(DOCKER_REGISTRY)" ]; then \
		 echo "DOCKER_REGISTRY is set ($(DOCKER_REGISTRY)) - tagging and pushing image to registry..."; \
		 docker tag $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
		 docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
		 IMAGE_REF=$(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
	else \
		 # Try to detect minikube or kind and load the image into the cluster runtime
		 if command -v minikube >/dev/null 2>&1; then \
			 echo "minikube detected - loading image into minikube..."; \
			 minikube image load $(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
			 IMAGE_REF=$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
		 elif command -v kind >/dev/null 2>&1; then \
			 echo "kind detected - loading image into kind..."; \
			 kind load docker-image $(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
			 IMAGE_REF=$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
		 else \
			 echo "No minikube or kind detected and DOCKER_REGISTRY is not set. Building locally may not make the image available to the cluster."; \
			 IMAGE_REF=$(DOCKER_IMAGE_NAME):$(DOCKER_TAG); \
		 fi; \
	fi; \

	# Deploy with Helm using the chosen image reference
	if [ -z "$$IMAGE_REF" ]; then \
		 echo "Failed to determine image reference; aborting."; exit 1; \
	fi; \
	echo "Deploying Helm chart with image=$$IMAGE_REF"; \
	helm upgrade --install a2a-server ./chart/a2a-server --namespace spotlessbinco --create-namespace \
		--set image.repository=$$(echo $$IMAGE_REF | sed -e 's/:.*$$//') --set image.tag=$$(echo $$IMAGE_REF | sed -e 's/^.*://')

# =============================================================================
# Blue-Green Deployment Targets
# =============================================================================

# Force bash for advanced scripting used in deployment targets
SHELL := /bin/bash

# Git info for tagging
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH_SAFE := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/\//-/g' || echo "unknown")


.PHONY: deploy-blue
deploy-blue: ## Deploy to blue slot
	@./scripts/blue-green-deploy.sh blue $(CHART_VERSION) deploy

.PHONY: deploy-green
deploy-green: ## Deploy to green slot
	@./scripts/blue-green-deploy.sh green $(CHART_VERSION) deploy

.PHONY: rollback-blue
rollback-blue: ## Rollback to blue slot
	@./scripts/blue-green-deploy.sh blue $(CHART_VERSION) rollback

.PHONY: rollback-green
rollback-green: ## Rollback to green slot
	@./scripts/blue-green-deploy.sh green $(CHART_VERSION) rollback

.PHONY: cleanup-blue
cleanup-blue: ## Cleanup blue slot deployment
	@./scripts/blue-green-deploy.sh blue $(CHART_VERSION) cleanup

.PHONY: cleanup-green
cleanup-green: ## Cleanup green slot deployment
	@./scripts/blue-green-deploy.sh green $(CHART_VERSION) cleanup

.PHONY: deploy-status
deploy-status: ## Show blue-green deployment status
	@./scripts/blue-green-deploy.sh blue $(CHART_VERSION) status

# =============================================================================
# Blue-Green Deployment (New Script)
# =============================================================================

.PHONY: bluegreen-deploy
bluegreen-deploy: ## Deploy with blue-green strategy (zero-downtime)
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Starting blue-green deployment..."
	BACKEND_TAG=$(DOCKER_TAG) ./scripts/bluegreen-deploy.sh deploy

.PHONY: bluegreen-rollback
bluegreen-rollback: ## Rollback blue-green deployment to previous version
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "↩️  Rolling back blue-green deployment..."
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) ./scripts/bluegreen-deploy.sh rollback

.PHONY: bluegreen-status
bluegreen-status: ## Show blue-green deployment status
	@chmod +x scripts/bluegreen-deploy.sh
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) ./scripts/bluegreen-deploy.sh status

.PHONY: bluegreen-oci
bluegreen-oci: docker-build docker-push helm-package helm-push ## Build, push image and chart, then deploy with blue-green (OCI)
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Starting blue-green deployment with OCI chart..."
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) \
		CHART_SOURCE=oci CHART_VERSION=$(CHART_VERSION) BACKEND_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy

# =============================================================================
# Environment-Specific Deployments (Blue-Green)
# =============================================================================

.PHONY: k8s-dev
k8s-dev: docker-build-all docker-push-all ## Build and deploy all containers to dev environment
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Starting DEV environment blue-green deployment"
	NAMESPACE=a2a-server-dev RELEASE_NAME=a2a-server-dev \
		VALUES_FILE=$(CHART_PATH)/values-dev.yaml \
		BACKEND_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy

.PHONY: k8s-staging
k8s-staging: docker-build-all docker-push-all ## Build and deploy all containers to staging environment
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Starting STAGING environment blue-green deployment"
	NAMESPACE=a2a-server-staging RELEASE_NAME=a2a-server-staging \
		VALUES_FILE=$(CHART_PATH)/values-staging.yaml \
		BACKEND_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy

.PHONY: k8s-prod
k8s-prod: docker-build-all docker-push-all helm-package helm-push helm-package-voice-agent helm-push-voice-agent ## Build and deploy ALL containers to production (server, marketing, docs, voice-agent)
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Starting PRODUCTION environment blue-green deployment"
	@echo "⚠️  WARNING: This deploys to PRODUCTION!"
	@echo "📦 Deploying: API Server, Marketing Site, Documentation Site, Voice Agent"
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) \
		VALUES_FILE=$(VALUES_FILE) \
		CHART_SOURCE=oci CHART_VERSION=$(CHART_VERSION) \
		BACKEND_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy
	@$(MAKE) voice-agent-deploy
	@$(MAKE) local-worker-restart

.PHONY: k8s-prod-docs
k8s-prod-docs: docker-build-docs docker-push-docs ## Build and deploy Documentation Site only to production
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Deploying DOCS only to production"
	@echo "⚠️  WARNING: This deploys to PRODUCTION!"
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) \
		CHART_SOURCE=oci CHART_VERSION=$(CHART_VERSION) \
		DOCS_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy-docs

.PHONY: local-worker-restart
local-worker-restart: ## Restart local systemd worker (best effort). Set RESTART_LOCAL_WORKER=0 to skip.
	@set -euo pipefail; \
	if [ "$(RESTART_LOCAL_WORKER)" != "1" ]; then \
		echo "ℹ️  RESTART_LOCAL_WORKER=$(RESTART_LOCAL_WORKER) - skipping local systemd worker restart"; \
		exit 0; \
	fi; \
	if ! command -v systemctl >/dev/null 2>&1; then \
		echo "❌ systemctl not found but RESTART_LOCAL_WORKER=1. Cannot manage local worker via systemd."; \
		exit 1; \
	fi; \
	unit="$(LOCAL_WORKER_SERVICE)"; \
	: "Allow LOCAL_WORKER_SERVICE to be set with or without the .service suffix"; \
	if [[ "$$unit" != *.service ]]; then unit="$$unit.service"; fi; \
	unit_installed=0; \
	for p in \
		"/etc/systemd/system/$$unit" \
		"/lib/systemd/system/$$unit" \
		"/usr/lib/systemd/system/$$unit"; do \
		if [ -f "$$p" ]; then unit_installed=1; break; fi; \
	done; \
	if [ "$$unit_installed" -ne 1 ]; then \
		echo "⚠️  systemd unit $$unit not installed"; \
		if [ "$(AUTO_INSTALL_LOCAL_WORKER)" != "1" ]; then \
			echo "❌ AUTO_INSTALL_LOCAL_WORKER=$(AUTO_INSTALL_LOCAL_WORKER) so we will not auto-install. Install it, then rerun."; \
			exit 1; \
		fi; \
		if [ ! -f "$(LOCAL_WORKER_INSTALL_SCRIPT)" ]; then \
			echo "❌ Install script not found: $(LOCAL_WORKER_INSTALL_SCRIPT)"; \
			exit 1; \
		fi; \
		echo "🧰 Attempting to install local worker service via $(LOCAL_WORKER_INSTALL_SCRIPT)"; \
		if [ "$$(id -u)" -eq 0 ]; then \
			bash "$(LOCAL_WORKER_INSTALL_SCRIPT)"; \
		else \
			if command -v "$(SUDO)" >/dev/null 2>&1; then \
				if "$(SUDO)" -n true 2>/dev/null; then \
					"$(SUDO)" bash "$(LOCAL_WORKER_INSTALL_SCRIPT)"; \
				elif [ -t 0 ]; then \
					"$(SUDO)" bash "$(LOCAL_WORKER_INSTALL_SCRIPT)"; \
				else \
					echo "❌ sudo needs a password but this is a non-interactive session. Install the worker manually:"; \
					echo "   sudo bash $(LOCAL_WORKER_INSTALL_SCRIPT)"; \
					exit 1; \
				fi; \
			else \
				echo "❌ Not root and sudo not available. Install the worker as root:"; \
				echo "   bash $(LOCAL_WORKER_INSTALL_SCRIPT)"; \
				exit 1; \
			fi; \
		fi; \
	fi; \
	# Re-check now that we may have installed it. \
	unit_installed=0; \
	for p in \
		"/etc/systemd/system/$$unit" \
		"/lib/systemd/system/$$unit" \
		"/usr/lib/systemd/system/$$unit"; do \
		if [ -f "$$p" ]; then unit_installed=1; break; fi; \
	done; \
	if [ "$$unit_installed" -ne 1 ]; then \
		echo "❌ systemd unit $$unit still not installed after install attempt."; \
		exit 1; \
	fi; \
	echo "🔄 Restarting local worker: $$unit"; \
	if [ "$$(id -u)" -eq 0 ]; then \
		systemctl daemon-reload || true; \
		systemctl restart "$$unit"; \
		systemctl --no-pager --full status "$$unit"; \
	else \
		if command -v "$(SUDO)" >/dev/null 2>&1; then \
			if "$(SUDO)" -n true 2>/dev/null; then \
				"$(SUDO)" systemctl daemon-reload || true; \
				"$(SUDO)" systemctl restart "$$unit"; \
				"$(SUDO)" systemctl --no-pager --full status "$$unit"; \
			elif [ -t 0 ]; then \
				"$(SUDO)" systemctl daemon-reload || true; \
				"$(SUDO)" systemctl restart "$$unit"; \
				"$(SUDO)" systemctl --no-pager --full status "$$unit"; \
			else \
				echo "❌ sudo needs a password but this is a non-interactive session. Restart manually:"; \
				echo "   sudo systemctl restart $$unit"; \
				exit 1; \
			fi; \
		else \
			echo "❌ Not root and sudo not available. Restart manually as root:"; \
			echo "   systemctl restart $$unit"; \
			exit 1; \
		fi; \
	fi

# Convenience aliases
.PHONY: k8s
k8s: k8s-prod ## Alias for k8s-prod

.PHONY: deploy-fast
deploy-fast: helm-package helm-push ## Fast deploy (chart only, assumes images exist)
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "⚡ Fast deployment (chart update only)..."
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) \
		CHART_SOURCE=oci CHART_VERSION=$(CHART_VERSION) BACKEND_TAG=$(DOCKER_TAG) \
		./scripts/bluegreen-deploy.sh deploy

.PHONY: deploy-now
deploy-now: ## Immediate deploy with existing chart (no build)
	@chmod +x scripts/bluegreen-deploy.sh
	@echo "🚀 Immediate deployment with existing chart..."
	NAMESPACE=$(NAMESPACE) RELEASE_NAME=$(RELEASE_NAME) BACKEND_TAG=$(DOCKER_TAG) ./scripts/bluegreen-deploy.sh deploy

# =============================================================================
# Kubernetes Utilities
# =============================================================================

.PHONY: get-pods
get-pods: ## List pods in namespace
	kubectl get pods -n $(NAMESPACE)

.PHONY: describe-pod
describe-pod: ## Describe pods in namespace
	kubectl describe pod -n $(NAMESPACE)

.PHONY: scale-0
scale-0: ## Scale deployment to 0 replicas
	kubectl scale deployment a2a-server --replicas=0 -n $(NAMESPACE)

.PHONY: scale-1
scale-1: ## Scale deployment to 1 replica
	kubectl scale deployment a2a-server --replicas=1 -n $(NAMESPACE)

.PHONY: scale-2
scale-2: ## Scale deployment to 2 replicas
	kubectl scale deployment a2a-server --replicas=2 -n $(NAMESPACE)

.PHONY: rollout-status
rollout-status: ## Show deployment rollout status
	kubectl rollout status deployment/a2a-server -n $(NAMESPACE)

# =============================================================================
# CodeTether Deployment Targets
# =============================================================================

.PHONY: codetether-deploy
codetether-deploy: ## Deploy CodeTether with values file
	helm upgrade --install a2a-marketing oci://$(OCI_REGISTRY)/a2a-server \
		--version $(CHART_VERSION) \
		-n $(NAMESPACE) \
		-f $(VALUES_FILE)

.PHONY: codetether-build-marketing
codetether-build-marketing: ## Build and push marketing site
	cd marketing-site && docker build -t $(OCI_REGISTRY)/a2a-marketing:latest -t $(OCI_REGISTRY)/a2a-marketing:$(CHART_VERSION) .
	docker push $(OCI_REGISTRY)/a2a-marketing:latest
	docker push $(OCI_REGISTRY)/a2a-marketing:$(CHART_VERSION)

.PHONY: codetether-build-docs
codetether-build-docs: ## Build and push docs site
	docker build -t $(OCI_REGISTRY)/codetether-docs:latest -t $(OCI_REGISTRY)/codetether-docs:$(CHART_VERSION) -f Dockerfile.docs .
	docker push $(OCI_REGISTRY)/codetether-docs:latest
	docker push $(OCI_REGISTRY)/codetether-docs:$(CHART_VERSION)

.PHONY: codetether-build-all
codetether-build-all: codetether-build-marketing codetether-build-docs docker-build docker-push ## Build and push all CodeTether images

.PHONY: codetether-restart-marketing
codetether-restart-marketing: ## Restart marketing deployment
	kubectl rollout restart deployment/$(RELEASE_NAME)-marketing -n $(NAMESPACE)
	kubectl rollout status deployment/$(RELEASE_NAME)-marketing -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-docs
codetether-restart-docs: ## Restart docs deployment
	kubectl rollout restart deployment/$(RELEASE_NAME)-docs -n $(NAMESPACE)
	kubectl rollout status deployment/$(RELEASE_NAME)-docs -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-api
codetether-restart-api: ## Restart API deployment
	kubectl rollout restart deployment a2a-marketing-a2a-server -n $(NAMESPACE)
	kubectl rollout status deployment a2a-marketing-a2a-server -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-all
codetether-restart-all: codetether-restart-marketing codetether-restart-docs codetether-restart-api ## Restart all deployments

.PHONY: codetether-deploy-voice
codetether-deploy-voice: codetether-build-marketing docker-build-voice-agent docker-push-voice-agent ## Build and deploy marketing site + voice agent
	kubectl rollout restart deployment/a2a-marketing-a2a-server-marketing -n $(NAMESPACE)
	@$(MAKE) voice-agent-deploy

.PHONY: codetether-logs-marketing
codetether-logs-marketing: ## Show marketing site logs
	kubectl logs -f deployment/a2a-marketing-a2a-server-marketing -n $(NAMESPACE)

.PHONY: codetether-logs-api
codetether-logs-api: ## Show API server logs
	kubectl logs -f deployment/a2a-marketing-a2a-server -n $(NAMESPACE)

.PHONY: codetether-status
codetether-status: ## Show CodeTether deployment status
	@echo "=== Deployments ==="
	kubectl get deployments -n $(NAMESPACE)
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -n $(NAMESPACE)
	@echo ""
	@echo "=== Ingresses ==="
	kubectl get ingress -n $(NAMESPACE)
	@echo ""
	@echo "=== Certificates ==="
	kubectl get certificates -n $(NAMESPACE)

.PHONY: codetether-full-deploy
codetether-full-deploy: codetether-build-all helm-package helm-push codetether-deploy ## Full build and deploy pipeline


.PHONY: test-models
test-models:
	source .venv/bin/activate && pip install aiohttp && python3 tests/verify_models.py

# =============================================================================
# Voice Agent Deployment Targets
# =============================================================================

VOICE_AGENT_CHART_PATH = chart/codetether-voice-agent
VOICE_AGENT_CHART_VERSION ?= 0.1.0
VOICE_AGENT_RELEASE_NAME ?= codetether-voice-agent

.PHONY: helm-package-voice-agent
helm-package-voice-agent: ## Package voice agent Helm chart
	helm package $(VOICE_AGENT_CHART_PATH)

.PHONY: helm-push-voice-agent
helm-push-voice-agent: helm-package-voice-agent ## Package and push voice agent Helm chart to OCI registry
	@CHART_PACKAGE="codetether-voice-agent-$(VOICE_AGENT_CHART_VERSION).tgz"; \
	if [ ! -f "$$CHART_PACKAGE" ]; then \
		CHART_PACKAGE=$$(ls -t codetether-voice-agent-*.tgz 2>/dev/null | head -n1); \
	fi; \
	if [ -z "$$CHART_PACKAGE" ]; then \
		echo "Error: No voice agent chart package found. Run 'make helm-package-voice-agent' first."; \
		exit 1; \
	fi; \
	helm push $$CHART_PACKAGE oci://$(OCI_REGISTRY)

.PHONY: voice-agent-deploy
voice-agent-deploy: ## Deploy voice agent to production
	@echo "🎤 Deploying CodeTether Voice Agent..."
	helm upgrade --install $(VOICE_AGENT_RELEASE_NAME) \
		oci://$(OCI_REGISTRY)/codetether-voice-agent \
		--version $(VOICE_AGENT_CHART_VERSION) \
		-n $(NAMESPACE) \
		--set image.repository=$(OCI_REGISTRY)/$(VOICE_AGENT_IMAGE_NAME) \
		--set image.tag=$(DOCKER_TAG) \
		--wait --timeout 300s || \
	helm upgrade --install $(VOICE_AGENT_RELEASE_NAME) \
		$(VOICE_AGENT_CHART_PATH) \
		-n $(NAMESPACE) \
		--set image.repository=$(OCI_REGISTRY)/$(VOICE_AGENT_IMAGE_NAME) \
		--set image.tag=$(DOCKER_TAG) \
		--wait --timeout 300s
	@echo "✅ Voice Agent deployed successfully"

.PHONY: voice-agent-status
voice-agent-status: ## Show voice agent deployment status
	@echo "=== Voice Agent Deployment ==="
	kubectl get deployment -n $(NAMESPACE) -l app.kubernetes.io/name=codetether-voice-agent
	@echo ""
	@echo "=== Voice Agent Pods ==="
	kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=codetether-voice-agent

.PHONY: voice-agent-logs
voice-agent-logs: ## Show voice agent logs
	kubectl logs -f deployment/$(VOICE_AGENT_RELEASE_NAME) -n $(NAMESPACE)

.PHONY: voice-agent-restart
voice-agent-restart: ## Restart voice agent deployment
	kubectl rollout restart deployment/$(VOICE_AGENT_RELEASE_NAME) -n $(NAMESPACE)
	kubectl rollout status deployment/$(VOICE_AGENT_RELEASE_NAME) -n $(NAMESPACE) --timeout=120s

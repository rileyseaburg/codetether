# CodeTether Server Makefile
# Variables
DOCKER_IMAGE_NAME = a2a-server-mcp
DOCKER_TAG ?= latest
DOCKER_REGISTRY ?= registry.quantum-forge.net/library
OCI_REGISTRY = registry.quantum-forge.net/library
PORT ?= 8000
CHART_PATH = chart/a2a-server
CHART_VERSION ?= 0.3.0
NAMESPACE ?= a2a-server
VALUES_FILE ?= chart/codetether-values.yaml

# Default target
.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Docker targets
.PHONY: docker-build
docker-build: ## Build Docker image
	docker build -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) . --network=host

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
docker-push: ## Push Docker image to OCI registry
	docker tag $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)
	docker push $(OCI_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

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
	@CHART_PACKAGE=$$(ls a2a-server-*.tgz | head -n1); \
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

.PHONY: run
run: ## Run the server locally
	python run_server.py run --host 0.0.0.0 --port $(PORT)

.PHONY: run-dev
run-dev: ## Run the server in development mode
	python run_server.py run --host 0.0.0.0 --port $(PORT) --reload

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
	kubectl rollout restart deployment a2a-marketing-a2a-server-marketing -n $(NAMESPACE)
	kubectl rollout status deployment a2a-marketing-a2a-server-marketing -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-docs
codetether-restart-docs: ## Restart docs deployment
	kubectl rollout restart deployment a2a-marketing-a2a-server-docs -n $(NAMESPACE)
	kubectl rollout status deployment a2a-marketing-a2a-server-docs -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-api
codetether-restart-api: ## Restart API deployment
	kubectl rollout restart deployment a2a-marketing-a2a-server -n $(NAMESPACE)
	kubectl rollout status deployment a2a-marketing-a2a-server -n $(NAMESPACE) --timeout=120s

.PHONY: codetether-restart-all
codetether-restart-all: codetether-restart-marketing codetether-restart-docs codetether-restart-api ## Restart all deployments

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



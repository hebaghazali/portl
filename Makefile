# Portl CLI Makefile
# Provides convenient targets for building, running, and releasing the Docker image

# Configuration
REGISTRY_REPO ?= ghcr.io/hebaghazali/portl
IMAGE ?= $(REGISTRY_REPO):latest
VERSION ?= latest

# Docker build arguments
DOCKER_BUILDX ?= docker buildx
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64

# Help target
.PHONY: help
help: ## Show this help message
	@echo "Portl CLI - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Configuration:"
	@echo "  REGISTRY_REPO=$(REGISTRY_REPO)"
	@echo "  IMAGE=$(IMAGE)"
	@echo "  VERSION=$(VERSION)"

# Build targets
.PHONY: build
build: ## Build Docker image locally
	@echo "Building Docker image: $(IMAGE)"
	docker build -t $(IMAGE) .

.PHONY: build-multi
build-multi: ## Build multi-architecture Docker image
	@echo "Building multi-arch Docker image: $(IMAGE)"
	$(DOCKER_BUILDX) build --platform $(DOCKER_PLATFORMS) -t $(IMAGE) .

# Run targets
.PHONY: run
run: ## Run Docker container with current directory mounted
	@echo "Running portl with current directory mounted..."
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) $(ARGS)

.PHONY: run-help
run-help: ## Run portl --help
	@$(MAKE) run ARGS="--help"

.PHONY: run-version
run-version: ## Run portl --version
	@$(MAKE) run ARGS="--version"

.PHONY: run-init
run-init: ## Run portl init
	@$(MAKE) run ARGS="init"

# Development targets
.PHONY: dev
dev: ## Run in development mode with interactive shell
	@echo "Running development container..."
	docker run --rm -it -v "$(PWD):/work" -w /work $(IMAGE) /bin/bash

.PHONY: test
test: ## Run tests in Docker container
	@echo "Running tests..."
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) python -m pytest tests/

# Release targets
.PHONY: release
release: ## Create and push a new release tag
	@if [ -z "$(TAG)" ]; then \
		echo "Error: TAG is required. Usage: make release TAG=v1.0.0"; \
		exit 1; \
	fi
	@echo "Creating release tag: $(TAG)"
	git tag -a $(TAG) -m "Release $(TAG)"
	git push origin $(TAG)
	@echo "Release $(TAG) created and pushed!"

.PHONY: release-build
release-build: ## Build and push release images (requires TAG)
	@if [ -z "$(TAG)" ]; then \
		echo "Error: TAG is required. Usage: make release-build TAG=v1.0.0"; \
		exit 1; \
	fi
	@echo "Building and pushing release images for $(TAG)..."
	$(DOCKER_BUILDX) build --platform $(DOCKER_PLATFORMS) \
		-t $(REGISTRY_REPO):$(TAG) \
		-t $(REGISTRY_REPO):latest \
		--push .

# Cleanup targets
.PHONY: clean
clean: ## Remove local Docker images
	@echo "Removing local Docker images..."
	-docker rmi $(IMAGE) 2>/dev/null || true
	-docker rmi $(REGISTRY_REPO):latest 2>/dev/null || true

.PHONY: clean-all
clean-all: ## Remove all portl-related Docker images
	@echo "Removing all portl-related Docker images..."
	-docker images | grep portl | awk '{print $$3}' | xargs docker rmi 2>/dev/null || true

# Utility targets
.PHONY: check
check: ## Check if Docker and buildx are available
	@echo "Checking Docker installation..."
	@docker --version
	@echo "Checking Docker buildx..."
	@$(DOCKER_BUILDX) version
	@echo "All checks passed!"

.PHONY: info
info: ## Show build information
	@echo "Build Information:"
	@echo "  Registry: $(REGISTRY_REPO)"
	@echo "  Image: $(IMAGE)"
	@echo "  Version: $(VERSION)"
	@echo "  Platforms: $(DOCKER_PLATFORMS)"
	@echo "  Docker: $(shell docker --version)"
	@echo "  Buildx: $(shell $(DOCKER_BUILDX) version | head -n1)"

# Default target
.DEFAULT_GOAL := help

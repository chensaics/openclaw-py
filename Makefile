.PHONY: help install dev test lint test-full ci-check build-web build-desktop build-mobile build-all docker clean

PYTHON ?= python3
FLET   ?= flet

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ──────────────────────────────────────────────────

install: ## Install project in development mode
	$(PYTHON) -m pip install -e ".[dev]"

dev: ## Run Flet app in development mode
	$(FLET) run flet_app.py

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -q

test-full: ## Run all tests with coverage
	$(PYTHON) -m pytest --cov=pyclaw --cov-report=term-missing tests/

lint: ## Run linters (ruff)
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

type-check: ## Run type checker
	$(PYTHON) -m mypy src/pyclaw

ci-check: ## Run checks similar to CI (lint, type-check, basic security)
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/
	$(PYTHON) -m mypy src/pyclaw
	@echo "Checking for potential secrets in code..."
	@find src/ tests/ -name "*.py" -type f -exec python scripts/check_secrets.py {} \;

# ─── Desktop Builds ──────────────────────────────────────────────

build-web: ## Build PWA web app → build/web/
	bash scripts/build-web.sh

build-macos: ## Build macOS .app → build/macos/
	bash scripts/build-desktop.sh macos

build-linux: ## Build Linux package → build/linux/
	bash scripts/build-desktop.sh linux

build-windows: ## Build Windows .exe → build/windows/
	bash scripts/build-desktop.sh windows

build-desktop: ## Build for current OS
	bash scripts/build-desktop.sh

# ─── Mobile Builds ───────────────────────────────────────────────

build-apk: ## Build Android APK → build/apk/
	bash scripts/build-mobile.sh apk

build-aab: ## Build Android App Bundle → build/aab/
	bash scripts/build-mobile.sh aab

build-ipa: ## Build iOS IPA → build/ipa/ (macOS + Xcode required)
	bash scripts/build-mobile.sh ipa

# ─── All Platforms ───────────────────────────────────────────────

build-all: ## Build for all platforms (web + current desktop)
	bash scripts/build-all.sh

# ─── Docker ──────────────────────────────────────────────────────

docker: ## Build Docker image
	docker build -t openclaw:latest .

docker-up: ## Start gateway with docker-compose
	docker compose up -d pyclaw-gateway

docker-down: ## Stop docker-compose services
	docker compose down

# ─── Cleanup ─────────────────────────────────────────────────────

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
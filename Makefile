.PHONY: help install dev test lint test-full ci ci-matrix type-check ci-check build-web build-desktop build-mobile build-all docker clean

PYTHON ?= python3
FLET   ?= flet

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ──────────────────────────────────────────────────

install: ## Install project in development mode
	$(PYTHON) -m pip install -e ".[dev]"

dev: ## Run Flet app in development mode
	$(FLET) run flet_app.py

test: ## Run all tests (quick)
	$(PYTHON) -m pytest tests/ -q

test-full: ## Run all tests with coverage
	$(PYTHON) -m pytest --cov=pyclaw --cov-report=term-missing tests/

lint: ## Run linters (ruff)
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

type-check: ## Run type checker
	$(PYTHON) -m mypy src/pyclaw

# 与 GitHub Actions CI 完全一致（lint + typecheck + pytest 含 coverage），推送前建议执行
ci: ## Run same checks as CI (lint + typecheck + pytest with coverage)
	@bash scripts/ci-local.sh

# 在多个 Python 版本上跑 CI 校验（与 CI matrix 一致，需安装 python3.10 … 3.14）
ci-matrix: ## Run CI checks on all supported Python versions (3.10–3.14)
	@bash scripts/run-ci-matrix.sh

ci-check: ## Lint + type-check + secret scan (no pytest; use 'make ci' for full CI parity)
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
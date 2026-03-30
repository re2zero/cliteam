.PHONY: help build clean release bump test lint install

VERSION := $(shell grep -oP '(?<=^version = ")[^"]+' pyproject.toml)
TAG := v$(VERSION)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

build: ## Build wheel and sdist (requires pip install build)
	rm -rf dist/
	python -m build
	@echo "=== Build complete ==="
	@ls -lh dist/

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info/

bump: ## Bump patch version (0.2.0 -> 0.2.1)
	@NEXT=$$(python -c "parts='$(VERSION)'.split('.'); parts[2]=str(int(parts[2])+1); print('.'.join(parts))"); \
	echo "Bumping $(VERSION) -> $$NEXT"; \
	sed -i "s/^version = \"$(VERSION)\"/version = \"$$NEXT\"/" pyproject.toml; \
	sed -i "s/__version__ = \"$(VERSION)\"/__version__ = \"$$NEXT\"/" clawteam/__init__.py

bump-minor: ## Bump minor version (0.2.0 -> 0.3.0)
	@NEXT=$$(python -c "parts='$(VERSION)'.split('.'); parts[1]=str(int(parts[1])+1); parts[2]='0'; print('.'.join(parts))"); \
	echo "Bumping $(VERSION) -> $$NEXT"; \
	sed -i "s/^version = \"$(VERSION)\"/version = \"$$NEXT\"/" pyproject.toml; \
	sed -i "s/__version__ = \"$(VERSION)\"/__version__ = \"$$NEXT\"/" clawteam/__init__.py

release: ## Build and create GitHub release with tag
	@echo "=== Releasing $(TAG) ==="
	rm -rf dist/
	python -m build
	@echo "=== Creating release $(TAG) ==="
	gh release create $(TAG) dist/*.whl dist/*.tar.gz \
		--title "$(TAG)" \
		--generate-notes
	@echo "=== Release $(TAG) created ==="

test: ## Run tests
	python -m pytest tests/ -v --tb=short

lint: ## Run linter
	ruff check clawteam/ tests/

install: ## Install in editable mode with dev deps
	pip install -e ".[dev]"

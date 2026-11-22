# Common tasks. Run from the repository root.
.PHONY: setup data lint test types eval eval-compare eval-precision approve-capture measure demo dev backup

BACKEND := uv --project backend run
export TESSDATA_PREFIX := $(CURDIR)/var/tessdata

setup:
	cd backend && uv sync --frozen
	cd frontend && npm ci
	$(BACKEND) pre-commit install --hook-type pre-commit --hook-type commit-msg
	scripts/fetch_tessdata.sh

data:
	$(BACKEND) python scripts/gen_licences.py

lint:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .
	cd backend && uv run mypy
	cd frontend && npm run typecheck && npm run lint && npm run format:check
	@if [ -f scripts/lint_copy.py ]; then python3 scripts/lint_copy.py; fi

test:
	cd backend && uv run pytest -m "not live"
	$(BACKEND) pytest evals/tests -m "not live" -p no:cacheprovider
	cd frontend && npm test

types:
	$(BACKEND) python scripts/export_openapi.py var/openapi.json
	cd frontend && npx openapi-typescript ../var/openapi.json -o src/api/generated.ts

eval:              ## paid: calls the model API
	$(BACKEND) python -m evals.run

eval-compare:
	$(BACKEND) python -m evals.compare

eval-precision:    ## paid, release branches only
	$(BACKEND) python -m evals.run --precision

approve-capture:
	$(BACKEND) python scripts/make_twin.py --approve $(ID)

measure:           ## paid: throughput probe (task T034)
	$(BACKEND) python scripts/measure_throughput.py --yes-spend

demo:
	docker compose up --build

dev:               ## local demo backend (label answers, no model key); run `npm run dev` in frontend/
	scripts/dev_demo.sh

backup:
	mkdir -p var/backups && cp var/*.sqlite3 var/backups/ 2>/dev/null || true

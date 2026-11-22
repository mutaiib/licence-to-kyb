# Common tasks. Run from the repository root.
.PHONY: setup data lint test types eval eval-live eval-compare approve-capture measure demo dev backup local-model mutation

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

eval:              ## offline: scripted model from labels; checks routing and rules; no cost
	$(BACKEND) python -m evals.run --model scripted

eval-live:         ## the models of MODEL_PROFILE: paid on the API, free on a local model
	$(BACKEND) python -m evals.run --model profile --pass3

eval-compare:
	$(BACKEND) python -m evals.compare

approve-capture:
	PYTHONPATH=$(CURDIR) $(BACKEND) python scripts/make_twin.py $(ID)

measure:           ## paid: throughput probe (task T034)
	$(BACKEND) python scripts/measure_throughput.py --yes-spend

demo:
	docker compose up --build

dev:               ## local demo backend (label answers, no model key); run `npm run dev` in frontend/
	scripts/dev_demo.sh

# The databases live in DATA_DIR: var/demo/data for `make dev`; set it for another stack.
DATA_DIR ?= var/demo/data
backup:            ## consistent copies of the databases in DATA_DIR; fails when there are none
	python3 scripts/backup.py "$(DATA_DIR)" var/backups

# An open-weight model on this machine (ADR-004). Run scripts/fetch_llama_server.sh once,
# then `make local-model` in one terminal and `MODEL_PROFILE=local make dev` in another.
LOCAL_MODEL_PATH ?= $(HOME)/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
local-model:
	var/llama.cpp/llama-server -m "$(LOCAL_MODEL_PATH)" --alias local-model --jinja \
		--host 127.0.0.1 --port 8080 --ctx-size 8192 --threads $$(nproc)

# Mutation testing of the rules (T100). Slow, so not in CI. The copy of the code in
# backend/mutants/ reads data from this checkout.
mutation:
	cd backend && { LICENCE_KYB_REPO_ROOT=$(CURDIR) uv run mutmut run --max-children 8; \
	status=$$?; uv run mutmut results; exit $$status; }

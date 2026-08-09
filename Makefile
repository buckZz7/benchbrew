SEED ?= 42
N ?= 16
T2_DIR ?= ../tau2-bench
MODEL ?= qwen36-iq2xxs
BASE_URL ?= http://localhost:8000/v1

.PHONY: test bundle emit run board all

test: ## GPU-free tests + spec validation (37 tests, zero deps)
	python3 -m unittest discover -s tests -v
	python3 -m benchbrew --seed $(SEED) --tasks 8

bundle: ## generate a deterministic bundle to outputs/
	python3 -m benchbrew --seed $(SEED) --tasks $(N)

emit: ## emit the τ²-runnable domain into T2_DIR
	python3 -c "from benchbrew.generator import Generator; from benchbrew.emitter_tau2 import emit_tau2_domain; from domains.marketplace import MARKETPLACE; w,t=Generator(MARKETPLACE).generate($(SEED),$(N)); emit_tau2_domain(MARKETPLACE,$(SEED),t,w,'$(T2_DIR)')"

run: ## execute the lane through the arena harness (Pilsner's real runner)
	cd ../pilsner && PILSNER_T2_DOMAIN=marketplace PILSNER_MODEL=$(MODEL) PILSNER_BASE_URL=$(BASE_URL) PILSNER_T2_TASKS=$(N) PILSNER_SEED=$(SEED) PILSNER_SEED_SLOT=$(SEED) python3 -m arena.run_tau2

board: ## regenerate the leaderboard
	cd ../pilsner && python3 -m arena.board outputs --write

all: test emit run board ## the whole operational loop

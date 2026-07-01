CXX ?= g++
PYTHON ?= python3

ENGINE := build/affine_ladder_prefix
SOURCE := src/m96/affine_ladder_prefix.cpp
SAMPLE_RUNS := build/runs_sample

.PHONY: build audit sample verify-sample smoke clean

build:
	mkdir -p build
	$(CXX) -O3 -std=c++17 $(SOURCE) -lgmpxx -lgmp -o $(ENGINE)

audit:
	$(PYTHON) scripts/certify_constants.py
	$(PYTHON) scripts/audit_lower_bound.py

sample: build
	rm -rf $(SAMPLE_RUNS)
	$(PYTHON) scripts/run_tasks.py \
		--exe ./$(ENGINE) \
		--tasks manifests/tasks_sample_k1_1.jsonl \
		--out $(SAMPLE_RUNS) \
		--jobs 1 \
		--timeout 60

verify-sample:
	$(PYTHON) scripts/verify_certificate.py \
		--tasks manifests/tasks_sample_k1_1.jsonl \
		--runs $(SAMPLE_RUNS) \
		--source $(SOURCE) \
		--exe ./$(ENGINE)

smoke: audit sample verify-sample

clean:
	rm -rf build $(SAMPLE_RUNS)

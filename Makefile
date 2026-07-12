CXX ?= g++
PYTHON ?= python3

ENGINE := build/affine_ladder_prefix
SOURCE := src/m96/affine_ladder_prefix.cpp
SAMPLE_RUNS := build/runs_sample

.PHONY: build audit test verify-all verify-a29 release-manifest sanitize-smoke sample verify-sample smoke clean

build:
	mkdir -p build
	$(CXX) -O3 -std=c++17 $(SOURCE) -lgmpxx -lgmp -o $(ENGINE)

audit:
	$(PYTHON) scripts/certify_constants.py
	$(PYTHON) scripts/verify_reduction_certificates.py
	$(PYTHON) scripts/verify_frontier_certificate.py
	$(PYTHON) scripts/verify_frontier_oracle.py
	$(PYTHON) scripts/verify_first_spike_certificate.py
	$(PYTHON) scripts/verify_descent_certificates.py
	$(PYTHON) scripts/verify_a29_scan.py

test:
	$(PYTHON) -m unittest discover -s tests

verify-all:
	$(PYTHON) -B verify_all.py

verify-a29:
	mkdir -p build
	$(CXX) -O3 -std=c++17 -Wall -Wextra -Werror \
		src/frontier/independent_a29_scan.cpp -o build/independent_a29_scan
	$(PYTHON) scripts/verify_a29_scan.py --exe ./build/independent_a29_scan

release-manifest:
	$(PYTHON) scripts/generate_release_manifest.py
	$(PYTHON) scripts/verify_release_manifest.py

sanitize-smoke:
	mkdir -p build
	$(CXX) -O1 -g -std=c++17 -fsanitize=address,undefined \
		-fno-omit-frame-pointer $(SOURCE) -lgmpxx -lgmp \
		-o build/affine_ladder_prefix_sanitize
	ASAN_OPTIONS=detect_leaks=1 ./build/affine_ladder_prefix_sanitize 96 1 0 256

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

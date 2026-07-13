CXX ?= g++
PYTHON ?= python3

ENGINE := build/affine_ladder_prefix
SOURCE := src/m96/affine_ladder_prefix.cpp
SAMPLE_RUNS := build/runs_sample
PROVER_SOURCES := src/prover/search_core.hpp src/prover/search_core.cpp src/prover/main.cpp
PROVER := build/collatz_prover
RUST_MANIFEST := src/verifier-rust/Cargo.toml
RUST_SOURCES := $(RUST_MANIFEST) src/verifier-rust/Cargo.lock $(wildcard src/verifier-rust/src/*.rs)
RUST_VERIFIER := build/collatz_verify_unit

.PHONY: build build-prover build-fault-prover build-rust-verifier build-all freeze-authoritative-build audit engineering-audit engineering-smoke rust-clippy rust-test synthetic-survivor-test test verify-all verify-a29 release-manifest sanitize-smoke sample verify-sample smoke clean

build:
	mkdir -p build
	$(CXX) -O3 -std=c++17 $(SOURCE) -lgmpxx -lgmp -o $(ENGINE)

build-prover:
	mkdir -p build
	SOURCE_HASH=`$(PYTHON) tools/source_tree_hash.py $(PROVER_SOURCES)`; \
	$(CXX) -O3 -std=c++17 -Wall -Wextra -Werror \
		-DCOLLATZ_PROVER_SOURCE_SHA256=\"$$SOURCE_HASH\" \
		src/prover/search_core.cpp src/prover/main.cpp \
		-lgmpxx -lgmp -lcrypto -o $(PROVER)

build-fault-prover:
	mkdir -p build
	SOURCE_HASH=$$($(PYTHON) tools/source_tree_hash.py $(PROVER_SOURCES)); \
	$(CXX) -O2 -std=c++17 -Wall -Wextra -Werror \
		-DCOLLATZ_PROVER_SOURCE_SHA256=\"$$SOURCE_HASH\" \
		-DCOLLATZ_ENABLE_FAULT_INJECTION=1 \
		src/prover/search_core.cpp src/prover/main.cpp \
		-lgmpxx -lgmp -lcrypto -o build/collatz_prover_fault

build-rust-verifier:
	mkdir -p build
	SOURCE_HASH=$$($(PYTHON) tools/source_tree_hash.py $(RUST_SOURCES)); \
	COLLATZ_RUST_SOURCE_SHA256=$$SOURCE_HASH \
		cargo build --release --locked --manifest-path $(RUST_MANIFEST)
	cp src/verifier-rust/target/release/collatz-verify-unit $(RUST_VERIFIER)

build-all: build build-prover build-rust-verifier

freeze-authoritative-build:
	$(PYTHON) tools/freeze_authoritative_build.py

audit:
	$(PYTHON) scripts/certify_constants.py
	$(PYTHON) scripts/verify_reduction_certificates.py
	$(PYTHON) scripts/verify_frontier_certificate.py
	$(PYTHON) scripts/verify_frontier_oracle.py
	$(PYTHON) scripts/verify_first_spike_certificate.py
	$(PYTHON) scripts/verify_descent_certificates.py
	$(PYTHON) scripts/verify_a29_scan.py

engineering-audit:
	$(PYTHON) verifiers/verify_mathematical_reductions.py
	$(PYTHON) scripts/verify_frontier_certificate.py
	$(PYTHON) verifiers/verify_schemas.py

rust-clippy:
	SOURCE_HASH=$$($(PYTHON) tools/source_tree_hash.py $(RUST_SOURCES)); \
	COLLATZ_RUST_SOURCE_SHA256=$$SOURCE_HASH \
		cargo clippy --locked --manifest-path $(RUST_MANIFEST) --all-targets -- -D warnings

rust-test:
	SOURCE_HASH=$$($(PYTHON) tools/source_tree_hash.py $(RUST_SOURCES)); \
	COLLATZ_RUST_SOURCE_SHA256=$$SOURCE_HASH \
		cargo test --locked --manifest-path $(RUST_MANIFEST)

synthetic-survivor-test:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -Wall -Wextra -Werror \
		src/prover/search_core.cpp tests/fixtures/cpp_synthetic_survivor.cpp \
		-lgmpxx -lgmp -o build/cpp_synthetic_survivor
	./build/cpp_synthetic_survivor

engineering-smoke: build-prover build-rust-verifier engineering-audit
	rm -rf build/engineering-smoke
	$(PYTHON) tools/plan_work_units.py --case 92 --case 93 \
		--out build/engineering-smoke/plan
	$(PYTHON) verifiers/verify_partition_manifest.py --case 92 --case 93 \
		--partitions build/engineering-smoke/plan
	$(PYTHON) tools/run_prover_units.py --case 92 --case 93 --jobs 2 \
		--plan build/engineering-smoke/plan \
		--out build/engineering-smoke/results/prover
	$(PYTHON) tools/run_verifier_units.py --case 92 --case 93 --jobs 2 \
		--plan build/engineering-smoke/plan \
		--out build/engineering-smoke/results/verifier
	$(PYTHON) tools/aggregate_search_certificate.py --case 92 --case 93 \
		--plan build/engineering-smoke/plan \
		--prover-results build/engineering-smoke/results/prover \
		--verifier-results build/engineering-smoke/results/verifier \
		--out build/engineering-smoke/certificates
	$(PYTHON) verifiers/verify_global_search_certificate.py --allow-incomplete \
		--plan build/engineering-smoke/plan \
		--prover-results build/engineering-smoke/results/prover \
		--verifier-results build/engineering-smoke/results/verifier \
		--certificates build/engineering-smoke/certificates

test: rust-test synthetic-survivor-test
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

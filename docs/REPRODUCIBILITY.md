# Reproducibility

## Verify the committed artifact

From a clean checkout, run:

```bash
python3 -B verify_all.py
```

This checks the release inventory and hashes, regenerates the five analytic
reduction certificates byte-for-byte, verifies all 372 committed branch
log/metadata pairs, regenerates and verifies the frontier, first-spike and
descent certificates, compiles and runs the independent `A29` scan, and runs the
adversarial test suite. It does not rerun the expensive branch searches.

## Reproduce the searches

Install a C++17 compiler and GMP development libraries, then build with:

```bash
make build
```

The canonical resumable commands for `m=96` and `m=92..95` are maintained in
the top-level README. A reproduction must use manifests whose source SHA-256
matches the compiled source. Compare the verifier's task counts, zero-hit
results, and canonical combined hashes for the archived run; raw hashes from a
new run may differ because branch logs contain elapsed seconds.

For an independent reproduction, record the commit, compiler and version,
optimization flags, GMP version, operating system, CPU model, job count, start
and finish times, and final verifier output. Use a clean output directory and
retain every root-level `.log` and `.meta.json` pair.

## Regenerate inexpensive certificates

```bash
python3 scripts/generate_reduction_certificates.py
python3 scripts/verify_reduction_certificates.py
python3 scripts/generate_frontier_certificate.py
python3 scripts/verify_frontier_certificate.py
python3 scripts/generate_frontier_oracle.py
python3 scripts/verify_frontier_oracle.py
python3 scripts/generate_first_spike_certificate.py
python3 scripts/verify_first_spike_certificate.py
python3 scripts/generate_descent_certificates.py
python3 scripts/verify_descent_certificates.py
make verify-a29
python3 scripts/generate_release_manifest.py
python3 scripts/verify_release_manifest.py
```

Regenerate `certificates/release_manifest.json` and `SHA256SUMS` only after all
release content is frozen. The final external integrity anchor is the immutable
release tag or archival DOI.

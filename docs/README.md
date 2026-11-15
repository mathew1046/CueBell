# CueBell documentation

Start with the user problem, then explore the engineering and evidence.

## Understand the project

- [Project overview](../README.md): what CueBell does and how to try it.
- [Impact and evaluation](IMPACT.md): intended users, practical examples and what still needs field testing.
- [Demo](../DEMO.md): a short, reproducible presentation.
- [Architecture](ARCHITECTURE.md): capture, Gnani streaming, interpretation and alerts.
- [Product scope](../PRODUCT.md) and [interface principles](../DESIGN.md).

## Understand the results

- [Pipeline optimization](PIPELINE_OPTIMIZATION.md): latency improvements and quality tradeoffs.
- [Noise reduction](NOISE_REDUCTION.md): local GTCRN, real-time processing and recognition results.
- [Verification](VERIFICATION.md): how checks are run and what they establish.

Supporting reports preserve experiment-specific methods and evidence:

- [Latency campaign](LATENCY_BENCHMARK_2026-11-13.md)
- [Latency and noise research](LATENCY_NOISE_RESEARCH_2026-11-13.md)
- [Noise-reduction benchmark](NOISE_REDUCTION_BENCHMARK_2026-11-14.md)
- [Recorded real-noise evaluation](REAL_NOISE_DENOISING_2026-11-14.md)
- [Station public-address evaluation](STATION_PA_DENOISING_2026-11-14.md)
- [Gnani denoiser diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md)
- [Next engineering steps](OPTIMIZATION_ROADMAP.md)

The files under `benchmarks/` are the original experimental evidence, not required reading for a first review. Reports distinguish synthetic mixtures, recorded noisy speech and station recordings; none is a representative-user field trial.

## Build and operate

- [Backend](../backend/README.md)
- [Android](../mobile/README.md)
- [Web](WEB.md)
- [Deployment operations](../ops/README.md)
- [Contributing](../CONTRIBUTING.md)
- [Privacy](PRIVACY.md) and [security](../SECURITY.md)
- [Release history](../CHANGELOG.md)

# Containerized STIsim Simulation Pipeline

[![CI Tests](https://github.com/clark-kirkman-iv/stisim-cloud-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/clark-kirkman-iv/stisim-cloud-pipeline/actions/workflows/ci.yml)


A reproducible, multi-stage Docker execution harness wrapping the [STIsim](https://github.com/starsimhub/stisim) agent-based modeling framework (`hivsim` Zimbabwe example).

This repository implements **Phase 1 and Phase 2** of a cloud simulation architecture: packaging scenario-agnostic STIsim simulation runs in isolated, non-root containers with automated unit and regression testing prior to scaling onto cloud batch orchestration and remote storage.

---

## Quickstart

All workflows are managed via Docker Compose profiles so host environments remain clean and reproducible.

Clone the repository and configure your `.env` file so Docker Compose knows which host directory to mount into `/app/workspace/frames` (defaults to `./examples`):

```bash
git clone https://github.com/clark-kirkman-iv/stisim-cloud-pipeline.git
cd stisim-cloud-pipeline
cp .env.example .env
mkdir -p output  # especially if on Linux, output dir specified in .env MUST pre-exist
```

### 1. Run Automated Unit & Regression Tests
Builds the `test` stage (inheriting directly from `production`) and executes the test suite:
```bash
docker compose --profile test run --rm --build test-service
```

### 2. Run a Simulation (Production Container)
Executes `run_stisim.py` inside a minimal `python:3.14-slim` image running as non-root `appuser` against the mounted `FRAMES_DIR` (`frames/zimbabwe` inside the container):
```bash
docker compose --profile prod run --rm --build prod-service python run_stisim.py -f frames/zimbabwe
```

### 3. Interactive Developer Environment
Mounts your live `run_stisim.py` and `FRAMES_DIR` alongside an editable local clone of `stisim` (defaulting to `../stisim`; override with `STISIM_REPO_PATH`) so changes take effect immediately:
```bash
# Clone upstream stisim adjacent to this repo (first-time setup)
git clone https://github.com/starsimhub/stisim.git ../stisim

# Launch interactive developer container
docker compose --profile dev run --rm --build dev-service bash

# Inside the container: run simulations against your editable stisim checkout
python run_stisim.py -f frames/zimbabwe
```


---

## CLI Usage (`run_stisim.py`)

```text
python run_stisim.py -f FRAME_PATH [-n N_RUNS] [-o OUTPUT_DIR] [-p PLATFORM] [-v]
```

* `-f, --frame` **(Required):** Path to the simulation frame directory containing `__init__.py` (e.g., `examples/zimbabwe` locally, or `frames/zimbabwe` inside containers).
* `-n, --n-runs` *(Optional):* Number of stochastic simulation seed variations to execute.
* `-o, --output` *(Optional):* Directory where simulation results are written.
* `-p, --platform` *(Optional):* Target execution platform for simulation orchestration.
* `-v, --verbose` *(Optional):* Enable verbose progress logging during execution.

---

## Container & Repository Structure

The multi-stage `Dockerfile` separates local engine development, minimal production execution, and automated verification:

* **`developer` (`dev-service`):** Installs Git, C/C++ compilers (build-essential), and editable `stisim[dev]` dependencies for local framework debugging.
* **`production` (`prod-service`):** Minimal runtime environment installing `stisim` from PyPI, baking in `run_stisim.py`, and executing as non-root `appuser` for cloud/Kubernetes compliance.
* **`test` (`test-service`):** Inherits directly from `production` and adds `pytest`, ensuring CI runs against the exact environment used in production.

```text
.
├── .github/workflows/ci.yml   # GitHub Actions CI running containerized tests on push to main
├── Dockerfile                 # Multi-stage build (developer, production, test)
├── docker-compose.yml         # Service profiles (dev, prod, test)
├── .env.example               # Template for FRAMES_DIR and STISIM_REPO_PATH Compose variables
├── run_stisim.py              # STIsim scenario-agnostic CLI orchestration entrypoint
├── examples/zimbabwe/         # Reference simulation frame (__init__.py + co-located input/)
├── tests/                     # Unit and deterministic regression tests
└── pyproject.toml             # Project metadata and dependencies
```

---

## Model & Data Provenance

* **Simulation Framework:** [starsimhub/stisim](https://github.com/starsimhub/stisim) (built on the [Starsim](https://stisim.org) architecture).
* **Baseline Model & Input Data:** Adapted from the upstream STIsim Zimbabwe example ([`hivsim_examples/zimbabwe`](https://github.com/starsimhub/stisim/tree/main/hivsim_examples/zimbabwe)), including demographic (`zimbabwe_age_1990.csv`, `zimbabwe_asfr.csv`, `zimbabwe_deaths.csv`) and HIV/intervention datasets (`art_coverage.csv`, `condom_use.csv`, `init_prev_hiv.csv`, `vmmc_coverage.csv`, `zimbabwe_hiv_data.csv`).

---

## Roadmap & Open Exploration Issues

* **Phase 1 (Complete):** Multi-stage containerization (`dev`, `prod`, `test`), CLI orchestration harness (`run_stisim.py`), automated unit/regression testing, and GitHub Actions CI.
* **Phase 2 (Complete):** Decoupled simulation execution from scenario-specific configuration by introducing a `-f / --frame` module interface (each frame directory exposing `make_sim(seed)` alongside a co-located `input/` directory), turning `run_stisim.py` into a scenario-agnostic execution harness:
  * [Abstract model configuration and inputs into pluggable project packages](https://github.com/clark-kirkman-iv/stisim-cloud-pipeline/issues/3)
* **Phase 3 (Planned):** Containerized batch execution on Kubernetes and AWS cloud infrastructure with remote object storage persistence:
  * [Evaluate Kubernetes orchestration for parallel STIsim runs](https://github.com/clark-kirkman-iv/stisim-cloud-pipeline/issues/5)
  * [Evaluate AWS cloud deployment and storage integration via Kubernetes](https://github.com/clark-kirkman-iv/stisim-cloud-pipeline/issues/6)
* **Phase 4 (Planned):** Downstream data retrieval, aggregation, and diagnostic visualization pipeline.
* **Phase 5 (Planned):** Evolve the execution harness to be fully model-agnostic across any domain.

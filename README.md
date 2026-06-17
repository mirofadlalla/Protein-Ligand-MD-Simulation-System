# Protein-Ligand MD Simulation System

A production-ready Python system for running Molecular Dynamics simulations of
protein-ligand complexes using **OpenMM** (GPU-accelerated) and **AmberTools**
(GAFF2 force field). Exposes a **Flask REST API** and is fully containerized
with **Docker**.

Derived from the [Making it Rain](https://github.com/pablo-arantes/making-it-rain)
notebook by Pablo Arantes et al.

---

## Project Structure

```
protein_ligand_md/
├── app/
│   ├── config.py              # All paths, defaults, binary locations
│   ├── main.py                # Flask app factory
│   ├── api/
│   │   ├── routes.py          # REST endpoints
│   │   └── schemas.py         # Request dataclasses
│   ├── pipeline/
│   │   ├── prepare.py         # PDBFixer + pdb4amber + OpenBabel
│   │   ├── topology.py        # antechamber + parmchk2 + tleap
│   │   ├── simulate.py        # OpenMM equilibration + production
│   │   ├── analyze.py         # RMSD / RMSF / PCA / ProLIF / LIE
│   │   └── orchestrator.py    # Full pipeline coordinator
│   └── utils/
│       ├── job_manager.py     # Thread-safe job registry
│       └── file_utils.py      # Path helpers + ZIP packaging
├── data/                      # Job uploads and results (mounted as volume)
├── Dockerfile
├── docker-compose.yml
├── environment.yml            # Conda environment (pinned versions)
├── requirements.txt           # pip packages only
└── run.py                     # CLI server entry point
```

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
# Clone / copy this directory
cd protein_ligand_md

# Build the image (takes ~10 min — downloads AmberTools + OpenMM)
docker compose build

# Start the server (CPU mode)
docker compose up -d

# With GPU (NVIDIA Container Toolkit required):
# OPENMM_PLATFORM=CUDA docker compose up -d

# Check it's running
curl http://localhost:5005/health
```

### Option 2 — Local conda environment (Linux only)

> AmberTools and pytraj only run on **Linux x86_64**.
> On Windows/macOS, use Docker instead.

```bash
conda env create -f environment.yml
conda activate md_env
python run.py
```

---

## API Reference

### `POST /process` — Start a simulation

Upload protein and ligand PDB files and set simulation parameters.

**Form fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `protein` | file | — | Protein PDB file (required) |
| `ligand` | file | — | Ligand PDB file (required) |
| `net_charge` | int | `0` | Ligand net formal charge |
| `force_field` | str | `ff19SB` | `ff19SB` or `ff14SB` |
| `box_size` | float | `12.0` | Solvation box padding (Å) |
| `ion_type` | str | `NaCl` | `NaCl` or `KCl` |
| `salt_conc` | float | `0.15` | Salt concentration (M) |
| `remove_waters` | bool | `true` | Strip crystal waters |
| `add_hydrogens` | bool | `true` | Add H to ligand |
| `equil_time_ns` | float | `5.0` | Equilibration time (ns) |
| `sim_time_ns` | float | `0.1` | Production time per stride (ns) |
| `n_strides` | int | `1` | Number of production strides |
| `temperature_k` | float | `298.0` | Temperature (K) |
| `pressure_bar` | float | `1.0` | Pressure (bar) |
| `dt_fs` | int | `2` | Integration timestep (fs) |

**Response:** `202 Accepted`
```json
{ "job_id": "a1b2c3d4", "status": "Queued" }
```

**Example (curl):**
```bash
curl -X POST http://localhost:5005/process \
  -F "protein=@protein.pdb" \
  -F "ligand=@ligand.pdb" \
  -F "sim_time_ns=1.0" \
  -F "net_charge=0"
```

---

### `GET /status/<job_id>` — Poll job progress

```bash
curl http://localhost:5005/status/a1b2c3d4
```

**Response:**
```json
{
  "job_id": "a1b2c3d4",
  "status": "Step 4/7 — Production MD (1 × 1.0 ns) [60%]",
  "download_url": "/download/a1b2c3d4"
}
```

Status string format:
- `Queued` → `Step 1/7 — ...` → ... → `Success: MD Pipeline Completed`
- `Failed: <error message>`

---

### `GET /download/<job_id>` — Download simulation results

Returns a ZIP file containing:
- `*.prmtop` — AMBER topology
- `*.crd` — Coordinates  
- `*_SYS.pdb` — Solvated system PDB
- `*_equil.dcd` — Equilibration trajectory
- `*_prod_N.dcd` — Production trajectory (per stride)
- `*.rst` — Restart files (XML)
- `*.log` — Energy logs

```bash
curl -OJ http://localhost:5005/download/a1b2c3d4
```

---

### `POST /analyze` — Run post-simulation analysis

Triggers: RMSD, RMSF, Radius of Gyration, 2D RMSD, PCA, Cross-Correlation,
Interaction Energy (LIE), and ProLIF interaction network.

```bash
curl -X POST http://localhost:5005/analyze \
  -H "Content-Type: application/json" \
  -d '{"job_id": "a1b2c3d4", "rmsd_mask": "@CA", "skip": 1, "dpi": 300}'
```

**Response:**
```json
{
  "job_id": "a1b2c3d4",
  "download_url": "/download_analysis/a1b2c3d4",
  "outputs": ["rmsd", "rmsf", "radgyr", "2d_rmsd", "pca", "cross_corr", "interaction_e", "prolif"]
}
```

```bash
curl -OJ http://localhost:5005/download_analysis/a1b2c3d4
```

---

### `GET /health` — Liveness probe

```bash
curl http://localhost:5005/health
# {"status": "ok"}
```

---

## Configuration

Override any setting via environment variables:

| Variable | Default | Description |
|---|---|---|
| `MD_DATA_DIR` | `./data` | Directory for job files |
| `FLASK_HOST` | `0.0.0.0` | Server bind address |
| `FLASK_PORT` | `5005` | Server port |
| `FLASK_DEBUG` | `false` | Flask debug mode |
| `OPENMM_PLATFORM` | `AUTO` | `AUTO`, `CUDA`, `OpenCL`, or `CPU` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `OBABEL_BIN` | auto | OpenBabel binary path |
| `PDB4AMBER_BIN` | auto | pdb4amber binary path |
| `ANTECHAMBER_BIN` | auto | antechamber binary path |
| `PARMCHK2_BIN` | auto | parmchk2 binary path |
| `TLEAP_BIN` | auto | tleap binary path |

---

## Integrating Into Your App

The pipeline modules are designed to be imported directly:

```python
from app.pipeline.prepare import prepare_system
from app.pipeline.topology import build_topology
from app.pipeline.simulate import run_equilibration, run_production
from app.pipeline.analyze import compute_rmsd, compute_prolif_network

# Example: run just the preparation step
prep = prepare_system(
    job_id="my_job",
    protein_raw="/path/to/protein.pdb",
    ligand_raw="/path/to/ligand.pdb",
    work_dir="/tmp/my_job",
    remove_waters=True,
    add_hydrogens=True,
)
print(prep["fixed_protein"])
```

---

## Dependency Compatibility Notes

| Package | Version | Why pinned |
|---|---|---|
| `ambertools` | `22.*` | Required by `pytraj==2.0.*` |
| `pytraj` | `2.0.*` | Must match AmberTools — install via conda only |
| `openmm` | `8.1.*` | Stable API, CUDA 11/12 compatible |
| `numpy` | `1.26.*` | `<2.0` required by pytraj |
| `prolif` | `2.0.*` | v2 has breaking API changes vs 1.x used in the notebook |
| `MDAnalysis` | `2.8.*` | Stable with prolif 2.x |

> **Never install `pytraj` via pip** — it will break without the matching AmberTools C libraries.

---

## GPU Support

The system auto-detects the best available OpenMM platform: **CUDA → OpenCL → CPU**.

For Docker GPU support:
1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Set `OPENMM_PLATFORM=CUDA` in `docker-compose.yml`
3. The `deploy.resources.reservations.devices` block in `docker-compose.yml` passes the GPU through

---

## Original Paper

Arantes et al., *"Making it rain: Cloud-based molecular simulations for everyone"*,
JCIM 2021. [https://doi.org/10.1021/acs.jcim.1c00998](https://doi.org/10.1021/acs.jcim.1c00998)

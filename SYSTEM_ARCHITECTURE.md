# Protein-Ligand MD Simulation System — Complete Documentation

**Last Updated:** June 2026  
**Version:** 1.0  
**Status:** Production-Ready

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Technical Stack](#technical-stack)
4. [Component Architecture](#component-architecture)
5. [Data Flow & Pipeline](#data-flow--pipeline)
6. [API Reference](#api-reference)
7. [Installation & Setup](#installation--setup)
8. [Configuration Guide](#configuration-guide)
9. [Usage Examples](#usage-examples)
10. [File Structure](#file-structure)
11. [Development Guide](#development-guide)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

### What is This System?

The **Protein-Ligand MD Simulation System** is a production-ready, cloud-ready API for running **Molecular Dynamics (MD) simulations** of protein-ligand complexes. It automates the entire pipeline from raw PDB files to fully-analyzed simulation trajectories.

### Key Features

- **GPU-Accelerated**: Uses OpenMM with CUDA/OpenCL support
- **Fully Automated**: One API call triggers 7-stage pipeline
- **REST API**: Flask-based endpoints for remote submission
- **Containerized**: Docker & Docker Compose for easy deployment
- **Comprehensive Analysis**: RMSD, RMSF, PCA, Protein-Ligand Interactions (ProLIF), Binding Energy (LIE)
- **Production-Grade**: Error handling, logging, job tracking, CORS support
- **Based on Academia**: Derived from the [Making it Rain](https://github.com/pablo-arantes/making-it-rain) research

### Derived From

The system is inspired by and adapted from the Making it Rain notebook by Pablo Arantes et al., which pioneered accessible MD simulation workflows.

---

## System Architecture

### High-Level Overview

```
User/Client
    ↓
[REST API Endpoints]
    ↓
[Job Manager (Thread Pool)]
    ↓
[7-Stage MD Pipeline]
    ↓
[Results Database + File Storage]
    ↓
Download & Analysis
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT / WEB INTERFACE                             │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                    [REST API Gateway]
                    (Flask + CORS)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    [POST /process]  [GET /status]  [GET /download]
        │                 │                 │
    Validates      Polls Job        Returns
    Uploads        Status           ZIP
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                    [Job Manager]
                 (Thread-safe registry)
                          │
                ┌─────────┴─────────┐
                │                   │
            [Job Queue]        [Status Cache]
                │
        [ThreadPool Executor]
                │
        ┌───────┴───────────────────────────────────────┐
        │                                               │
    [7-STAGE PIPELINE]                            [File I/O]
        │                                               │
        ├─ Stage 1: Protein Prep                    ┌─┴─┐
        │           (PDBFixer + pdb4amber)          │   │
        │                                           │   │
        ├─ Stage 2: Ligand Prep                  [data/]
        │           (OpenBabel + pdb4amber)        │   │
        │                                           │   │
        ├─ Stage 3: GAFF2 Parameters             └─┬─┘
        │           (antechamber + parmchk2)       │
        │                                           │
        ├─ Stage 4: Topology Build              (CRUD ops)
        │           (tleap — solvation + ions)      │
        │                                           │
        ├─ Stage 5: Energy Minimization             │
        │           (OpenMM)                        │
        │                                           │
        ├─ Stage 6: NPT Equilibration               │
        │           (OpenMM)                        │
        │                                           │
        ├─ Stage 7: Production MD Run               │
        │           (OpenMM + Stride Loop)          │
        │                                           │
        └─ Stage 8: Results Packaging               │
                    (ZIP + Manifest)────────────────┘
```

---

## Technical Stack

### Core MD Engine

| Component | Version | Purpose |
|-----------|---------|---------|
| **OpenMM** | 8.1+ | GPU-accelerated MD simulation |
| **AmberTools** | 24.x | Force field & parameter generation |
| **GAFF2** | Latest | Ligand force field |
| **FF19SB / FF14SB** | Latest | Protein force field |

### Chemistry Tools

| Component | Purpose |
|-----------|---------|
| **PDBFixer** | Repair broken PDB structures |
| **pdb4amber** | Convert PDB → Amber format |
| **OpenBabel** | Ligand format conversion |
| **antechamber** | GAFF2 parameter assignment |
| **parmchk2** | Parameter sanity checks |
| **tleap** | System assembly & solvation |

### Python Stack

| Component | Purpose |
|-----------|---------|
| **Flask 3.0+** | Web framework & REST API |
| **Flask-CORS** | Cross-origin support |
| **RDKit** | Cheminformatics |
| **MDAnalysis** | Trajectory post-processing |
| **ProLIF** | Protein-Ligand interactions |
| **BioPandas** | PDB parsing & analysis |
| **NumPy / SciPy / Pandas** | Scientific computing |
| **Matplotlib / Seaborn** | Visualization |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |
| **Conda** | Environment management |

---

## Component Architecture

### Detailed Component Breakdown

```
protein_ligand_md/
│
├── app/
│   │
│   ├── config.py
│   │   └─ Central config hub
│   │      • Paths & directories
│   │      • Simulation defaults (force field, water model, etc.)
│   │      • Binary locations
│   │      • Environment variables
│   │
│   ├── main.py
│   │   └─ Flask app factory
│   │      • Creates Flask instance
│   │      • Registers blueprints
│   │      • Sets up CORS
│   │      • Configures logging
│   │
│   ├── api/
│   │   ├── routes.py
│   │   │   └─ REST endpoints
│   │   │      • POST /process (submit job)
│   │   │      • GET /status/<job_id> (poll status)
│   │   │      • GET /download/<job_id> (get results)
│   │   │      • POST /analyze (post-sim analysis)
│   │   │      • GET /health (liveness)
│   │   │
│   │   └── schemas.py
│   │       └─ Request/Response dataclasses
│   │          • SimulationRequest
│   │          • AnalysisRequest
│   │          • JobStatus
│   │
│   ├── pipeline/
│   │   ├── prepare.py
│   │   │   └─ Stage 1 & 2: Structure prep
│   │   │      • PDB format validation
│   │   │      • Water/hydrogen handling
│   │   │      • Pdb4amber conversion
│   │   │
│   │   ├── topology.py
│   │   │   └─ Stage 3 & 4: Parametrization
│   │   │      • antechamber (GAFF2)
│   │   │      • parmchk2 validation
│   │   │      • tleap solvation
│   │   │
│   │   ├── simulate.py
│   │   │   └─ Stage 5, 6, & 7: MD simulations
│   │   │      • Minimization (20k steps)
│   │   │      • NPT equilibration (5 ns)
│   │   │      • Production run (0.1 ns default)
│   │   │      • Frame striding & trajectory writing
│   │   │
│   │   ├── analyze.py
│   │   │   └─ Post-simulation analysis
│   │   │      • RMSD (Cα & ligand)
│   │   │      • RMSF (per-residue flexibility)
│   │   │      • PCA (principal component analysis)
│   │   │      • ProLIF (interaction fingerprints)
│   │   │      • LIE (binding energy estimate)
│   │   │      • Visualization & CSV export
│   │   │
│   │   └── orchestrator.py
│   │       └─ Pipeline coordinator
│   │          • Chains all stages
│   │          • Error handling & recovery
│   │          • Status updates
│   │          • Results packaging
│   │
│   └── utils/
│       ├── job_manager.py
│       │   └─ Thread-safe job registry
│       │      • Job submission & tracking
│       │      • Status caching
│       │      • Error recording
│       │      • ThreadPoolExecutor management
│       │
│       └── file_utils.py
│           └─ File I/O utilities
│              • Path resolution
│              • ZIP packaging
│              • Safe file reads
│              • Directory cleanup
│
├── tests/
│   └── test_api.py
│       └─ Unit & integration tests
│
├── data/
│   └─ [Volume mount] Job uploads & results
│       └─ <job_id>/ (per-job directory)
│           ├─ inputs/
│           ├─ work/
│           ├─ results/
│           └─ analysis/
│
├── Dockerfile
├── docker-compose.yml
├── environment.yml (conda)
├── requirements.txt (pip)
├── run.py (CLI entry)
└── README.md

```

---

## Data Flow & Pipeline

### Complete Simulation Pipeline

```
                        ┌──────────────────┐
                        │   User Uploads   │
                        │ Protein + Ligand │
                        │   (PDB files)    │
                        └────────┬─────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
        ┌───────▼──────────┐            ┌────────▼────────┐
        │ STAGE 1: PROTEIN │            │ STAGE 2: LIGAND │
        │       PREP       │            │      PREP       │
        │                  │            │                 │
        │  • PDBFixer      │            │  • OpenBabel    │
        │  • pdb4amber     │            │  • pdb4amber    │
        │  • Sanitize      │            │  • Validate     │
        │  • Add H/chains  │            │  • Format conv. │
        │                  │            │                 │
        └────────┬─────────┘            └────────┬────────┘
                 │                              │
                 └──────────────┬───────────────┘
                                │
                        ┌───────▼────────────┐
                        │ STAGE 3: GAFF2     │
                        │ PARAMETERS         │
                        │                    │
                        │ • antechamber      │
                        │ • parmchk2         │
                        │ • Charge calc.     │
                        │ • Bond/angle info  │
                        │                    │
                        └────────┬───────────┘
                                 │
                        ┌────────▼──────────┐
                        │  STAGE 4:         │
                        │  TOPOLOGY BUILD   │
                        │                   │
                        │  • tleap solvation│
                        │  • Add ions (NaCl)│
                        │  • Set forcefield │
                        │  • Generate coords│
                        │                   │
                        └────────┬──────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
    ┌───▼──────┐        ┌───────▼────┐         ┌────────▼─┐
    │ STAGE 5: │        │  STAGE 6:  │         │ STAGE 7: │
    │MINIMIZAT│        │    NPT     │         │PRODUCTION│
    │   ION   │        │ EQUILIBRAT │         │   RUN    │
    │          │        │    ION     │         │          │
    │20k steps │        │  5 ns @ 298K       │0.1-∞ ns  │
    │          │        │                    │          │
    └────┬─────┘        └────┬────────┘       └────┬─────┘
         │                   │                     │
         └───────────────────┼─────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  STAGE 8:        │
                    │  RESULTS PACKAGE │
                    │                  │
                    │ • Trajectories   │
                    │ • Energies       │
                    │ • Final structures
                    │ • Manifest.json  │
                    │                  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  POST-ANALYSIS   │
                    │  (Optional)      │
                    │                  │
                    │ • RMSD (Cα/lig)  │
                    │ • RMSF (per-res) │
                    │ • PCA analysis   │
                    │ • ProLIF intx.   │
                    │ • LIE binding E. │
                    │ • Plots + CSV    │
                    │                  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  DOWNLOAD LINK   │
                    │  (ZIP file)      │
                    └──────────────────┘
```

### Data Storage & Organization

```
data/
└── <job_id>/
    ├── inputs/
    │   ├── protein_raw.pdb    (user upload)
    │   └── ligand_raw.pdb     (user upload)
    │
    ├── work/                   (intermediate files)
    │   ├── protein_fixed.pdb
    │   ├── ligand_clean.mol2
    │   ├── ligand.gaff2.mol2
    │   ├── GAFF_LIG.frcmod
    │   ├── protein.prmtop
    │   ├── complex.prmtop
    │   ├── complex.inpcrd
    │   ├── solvated.prmtop
    │   ├── solvated.inpcrd
    │   └── [other intermediate files]
    │
    ├── results/
    │   ├── minimized.pdb
    │   ├── equilibrated.pdb
    │   ├── production.dcd (trajectory)
    │   ├── production.nc  (NetCDF trajectory)
    │   ├── energies.csv
    │   ├── manifest.json  (metadata)
    │   └── [final outputs]
    │
    ├── analysis/           (if /analyze requested)
    │   ├── rmsd.csv
    │   ├── rmsf.csv
    │   ├── pca_coords.csv
    │   ├── prolif.csv
    │   ├── rmsd_plot.png
    │   ├── rmsf_plot.png
    │   ├── pca_plot.png
    │   └── [analysis artifacts]
    │
    └── logs/
        └── job_<job_id>.log
```

---

## API Reference

### Base URL

```
http://<host>:<port>  # Default: http://localhost:5005
```

### Endpoints Overview

| Method | Endpoint | Purpose | Returns |
|--------|----------|---------|---------|
| `GET` | `/health` | Health check | `{"status": "ok"}` |
| `GET` | `/` | Root status | `{"status": "ok"}` |
| `POST` | `/process` | Submit simulation job | `{"job_id": "..."}` |
| `GET` | `/status/<job_id>` | Poll job status | Job status object |
| `GET` | `/download/<job_id>` | Download results ZIP | Binary ZIP file |
| `POST` | `/analyze` | Run analysis on completed job | Analysis job status |
| `GET` | `/download_analysis/<job_id>` | Download analysis ZIP | Binary ZIP file |

### 1. Health Check

```http
GET /health
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### 2. Submit Simulation Job

```http
POST /process
Content-Type: multipart/form-data

protein: <file>  (PDB)
ligand: <file>   (PDB)
ff: "ff19SB"                    (optional, default: ff19SB)
water_model: "TIP3P"            (optional, default: TIP3P)
box_size: 12.0                  (optional, default: 12.0 Å)
salt_conc: 0.15                 (optional, default: 0.15 M)
remove_waters: true             (optional, default: true)
add_hydrogens: true             (optional, default: true)
sim_time_ns: 0.1                (optional, default: 0.1 ns)
equil_time_ns: 5.0              (optional, default: 5.0 ns)
temp_k: 298.15                  (optional, default: 298 K)
seed: 12345                     (optional, random if omitted)
```

**Response (202 Accepted):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890",
  "status": "submitted"
}
```

**Errors:**
- `400 Bad Request`: Missing or invalid files
- `413 Payload Too Large`: File exceeds size limit

---

### 3. Check Job Status

```http
GET /status/a1b2c3d4-e5f6-7890
```

**Response (200 OK) — Job Running:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890",
  "status": "running",
  "current_step": "Step 5/7 — Energy minimization",
  "progress_percent": 45,
  "elapsed_seconds": 123,
  "error": null
}
```

**Response (200 OK) — Job Completed:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890",
  "status": "completed",
  "current_step": "Step 7/7 — Production MD run complete",
  "progress_percent": 100,
  "elapsed_seconds": 456,
  "result": {
    "trajectory_frames": 10,
    "final_energy_kcal_mol": -8234.5,
    "output_files": ["production.dcd", "energies.csv", "manifest.json"]
  },
  "error": null
}
```

**Response (200 OK) — Job Failed:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890",
  "status": "failed",
  "current_step": "Step 3/7 — GAFF2 topology",
  "progress_percent": 35,
  "elapsed_seconds": 78,
  "error": "antechamber failed: Invalid ligand structure"
}
```

**Possible Job Statuses:**
- `submitted` — Queued
- `running` — In progress
- `completed` — Success
- `failed` — Error occurred
- `cancelled` — User cancelled

---

### 4. Download Results

```http
GET /download/a1b2c3d4-e5f6-7890
```

**Response (200 OK):**
- Binary ZIP file containing:
  - `production.dcd` (DCD trajectory)
  - `production.nc` (NetCDF trajectory)
  - `results/manifest.json` (metadata)
  - `energies.csv` (time-series energies)
  - `final.pdb` (final structure)
  - Various intermediate files

**Headers:**
```
Content-Type: application/zip
Content-Disposition: attachment; filename="job_a1b2c3d4_results.zip"
```

---

### 5. Run Post-Simulation Analysis

```http
POST /analyze
Content-Type: application/json

{
  "job_id": "a1b2c3d4-e5f6-7890",
  "analyses": ["rmsd", "rmsf", "pca", "prolif", "lie"],
  "ref_frame": 0,
  "plot_format": "png"
}
```

**Response (202 Accepted):**
```json
{
  "analysis_job_id": "b2c3d4e5-f6g7-8901",
  "status": "queued"
}
```

---

### 6. Download Analysis Results

```http
GET /download_analysis/b2c3d4e5-f6g7-8901
```

**Response (200 OK):**
- Binary ZIP file containing:
  - `rmsd.csv` & `rmsd_plot.png`
  - `rmsf.csv` & `rmsf_plot.png`
  - `pca_coords.csv` & `pca_plot.png`
  - `prolif_frame_*.pkl` (interaction fingerprints)
  - `lie_results.csv`
  - Summary report

---

## Installation & Setup

### Option 1: Docker (Recommended)

#### Prerequisites
- Docker >= 20.10
- Docker Compose >= 1.29
- GPU drivers (NVIDIA CUDA for GPU acceleration) — optional but recommended

#### Installation Steps

```bash
# Clone or download the repository
cd protein_ligand_md

# Build the Docker image (10-15 minutes)
docker build -t protein-ligand-md:latest .

# Start the container
docker-compose up -d

# Check logs
docker-compose logs -f web

# Access API
curl http://localhost:5005/health
```

#### Verify Installation

```bash
# Test health endpoint
curl -s http://localhost:5005/health | jq .

# Expected output:
# {"status": "ok"}
```

#### Docker Compose Configuration

The `docker-compose.yml` includes:
- **Service Name:** `web`
- **Image:** `protein-ligand-md:latest`
- **Port Mapping:** `5005:5005` (host:container)
- **Volume Mounts:**
  - `./data:/app/data` (persistent results storage)
  - `./logs:/app/logs` (log files)
- **Environment Variables:**
  - `FLASK_HOST=0.0.0.0`
  - `FLASK_PORT=5005`
  - `MD_DATA_DIR=/app/data`
  - `OPENMM_PLATFORM=AUTO` (or CUDA/OpenCL)

---

### Option 2: Manual Installation (venv)

#### Prerequisites
- Python 3.9+
- Conda (for AmberTools, OpenMM)
- CUDA Toolkit 11.8+ (for GPU support)

#### Installation Steps

```bash
# Clone repository
cd protein_ligand_md

# Create conda environment (recommended)
conda env create -f environment.yml
conda activate md-sim

# Install pip requirements
pip install -r requirements.txt

# Verify AmberTools
which antechamber
which tleap

# Run the server
python run.py --host 0.0.0.0 --port 5005
```

#### Environment Setup (environment.yml)

The `environment.yml` includes:
- Python 3.11
- OpenMM 8.1
- AmberTools 24
- GROMACS (optional)
- Scientific stack (NumPy, SciPy, Pandas, Matplotlib)
- RDKit, MDAnalysis, ProLIF, BioPandas

---

### Option 3: Singularity (HPC Clusters)

```bash
# Build Singularity image from Dockerfile
singularity build md-sim.sif docker-daemon://protein-ligand-md:latest

# Run in HPC environment
singularity run --nv md-sim.sif python run.py --port 5005
```

---

## Configuration Guide

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_HOST` | `0.0.0.0` | Listen address |
| `FLASK_PORT` | `5005` | Listen port |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `MD_DATA_DIR` | `./data` | Job storage directory |
| `OPENMM_PLATFORM` | `AUTO` | GPU platform: `AUTO`, `CUDA`, `OpenCL`, `CPU` |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

#### Set via Docker

```yaml
# docker-compose.yml
environment:
  FLASK_HOST: "0.0.0.0"
  FLASK_PORT: "5005"
  OPENMM_PLATFORM: "CUDA"  # or AUTO, OpenCL, CPU
  LOG_LEVEL: "INFO"
```

#### Set via CLI

```bash
export FLASK_PORT=5005
export OPENMM_PLATFORM=CUDA
python run.py --host 0.0.0.0 --port 5005 --debug
```

---

### Simulation Defaults (config.py)

All defaults can be overridden per-job via API parameters:

```python
DEFAULT_FORCE_FIELD = "ff19SB"      # Protein FF
DEFAULT_WATER_MODEL = "TIP3P"       # Water model
DEFAULT_BOX_SIZE = 12.0             # Angstrom
DEFAULT_SALT_CONC = 0.15            # Molar (NaCl)
DEFAULT_ION_TYPE = "NaCl"
DEFAULT_SIM_TIME_NS = 0.1           # Production MD
DEFAULT_EQUIL_TIME_NS = 5.0         # NPT equilibration
DEFAULT_TEMP_K = 298.15             # 25°C
DEFAULT_PRESSURE_BAR = 1.0
DEFAULT_DT_FS = 2                   # Timestep (fs)
DEFAULT_SAVCRD_PS = 10              # Save freq (ps)
DEFAULT_RESTRAINT_FC = 700          # Ligand restraint (kJ/mol)
DEFAULT_MIN_STEPS = 20000           # Minimization steps
```

---

## Usage Examples

### Example 1: Simple Simulation (Python + requests)

```python
import requests
import json
from pathlib import Path

# Configuration
API_URL = "http://localhost:5005"
PROTEIN_FILE = "protein.pdb"
LIGAND_FILE = "ligand.pdb"

# 1. Submit job
with open(PROTEIN_FILE, "rb") as pf, open(LIGAND_FILE, "rb") as lf:
    files = {
        "protein": pf,
        "ligand": lf,
    }
    data = {
        "ff": "ff19SB",
        "water_model": "TIP3P",
        "sim_time_ns": 1.0,
        "equil_time_ns": 5.0,
    }
    response = requests.post(f"{API_URL}/process", files=files, data=data)

result = response.json()
job_id = result["job_id"]
print(f"Job submitted: {job_id}")

# 2. Poll status
import time

while True:
    status_response = requests.get(f"{API_URL}/status/{job_id}")
    status = status_response.json()
    
    print(f"Status: {status['status']}")
    print(f"Progress: {status.get('progress_percent', 0)}%")
    print(f"Current step: {status.get('current_step', 'N/A')}")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(10)  # Poll every 10 seconds

# 3. Download results
if status["status"] == "completed":
    download_response = requests.get(f"{API_URL}/download/{job_id}")
    with open(f"results_{job_id}.zip", "wb") as f:
        f.write(download_response.content)
    print(f"Results downloaded: results_{job_id}.zip")

# 4. Run analysis
analysis_data = {
    "job_id": job_id,
    "analyses": ["rmsd", "rmsf", "pca", "prolif"],
}
analysis_response = requests.post(f"{API_URL}/analyze", json=analysis_data)
analysis_job = analysis_response.json()
print(f"Analysis job: {analysis_job['analysis_job_id']}")
```

---

### Example 2: cURL Commands

```bash
# Health check
curl -s http://localhost:5005/health | jq .

# Submit job
curl -X POST http://localhost:5005/process \
  -F "protein=@protein.pdb" \
  -F "ligand=@ligand.pdb" \
  -F "ff=ff19SB" \
  -F "sim_time_ns=1.0" | jq .

# Get job ID from response and check status
JOB_ID="a1b2c3d4-e5f6-7890"
curl -s http://localhost:5005/status/$JOB_ID | jq .

# Download results
curl -O http://localhost:5005/download/$JOB_ID

# Run analysis
curl -X POST http://localhost:5005/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "'$JOB_ID'",
    "analyses": ["rmsd", "rmsf", "pca"]
  }' | jq .
```

---

### Example 3: Web UI Form (HTML)

```html
<!DOCTYPE html>
<html>
<head>
    <title>MD Simulation Processor</title>
</head>
<body>
    <h1>Protein-Ligand MD Simulator</h1>
    
    <form id="simulationForm">
        <label>Protein PDB:</label>
        <input type="file" id="protein" accept=".pdb" required>
        
        <label>Ligand PDB:</label>
        <input type="file" id="ligand" accept=".pdb" required>
        
        <label>Force Field:</label>
        <select id="ff">
            <option value="ff19SB" selected>ff19SB</option>
            <option value="ff14SB">ff14SB</option>
        </select>
        
        <label>Simulation Time (ns):</label>
        <input type="number" id="simTime" value="0.1" step="0.1" min="0.01">
        
        <button type="submit">Submit</button>
    </form>
    
    <div id="status"></div>
    <div id="download"></div>
    
    <script>
        const API_URL = "http://localhost:5005";
        
        document.getElementById("simulationForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            
            const formData = new FormData();
            formData.append("protein", document.getElementById("protein").files[0]);
            formData.append("ligand", document.getElementById("ligand").files[0]);
            formData.append("ff", document.getElementById("ff").value);
            formData.append("sim_time_ns", document.getElementById("simTime").value);
            
            const response = await fetch(`${API_URL}/process`, {
                method: "POST",
                body: formData,
            });
            
            const result = await response.json();
            const jobId = result.job_id;
            
            // Poll status
            const pollInterval = setInterval(async () => {
                const statusResponse = await fetch(`${API_URL}/status/${jobId}`);
                const status = await statusResponse.json();
                
                document.getElementById("status").innerHTML = `
                    <p>Job ID: ${jobId}</p>
                    <p>Status: ${status.status}</p>
                    <p>Progress: ${status.progress_percent}%</p>
                    <p>Step: ${status.current_step}</p>
                `;
                
                if (status.status === "completed") {
                    clearInterval(pollInterval);
                    document.getElementById("download").innerHTML = `
                        <a href="${API_URL}/download/${jobId}">Download Results</a>
                    `;
                }
            }, 5000);
        });
    </script>
</body>
</html>
```

---

## File Structure

### Detailed File Descriptions

#### `run.py`
- **Purpose:** CLI entry point for starting the server
- **Key Functions:**
  - `parse_args()`: Parse command-line arguments
  - `main()`: Initialize app and start Flask server
- **Usage:** `python run.py --host 0.0.0.0 --port 5005 --debug`

#### `app/config.py`
- **Purpose:** Central configuration hub
- **Key Variables:**
  - `BASE_DATA_DIR`: Data storage location
  - `FLASK_HOST`, `FLASK_PORT`, `FLASK_DEBUG`
  - Simulation defaults (FF, water model, time scales)
  - Binary paths (antechamber, tleap, etc.)
- **Note:** Auto-detects binaries from PATH

#### `app/main.py`
- **Purpose:** Flask application factory
- **Key Functions:**
  - `create_app()`: Create and configure Flask instance
- **Includes:** CORS setup, logging config, blueprint registration

#### `app/api/routes.py`
- **Purpose:** All REST API endpoints
- **Key Endpoints:**
  - `POST /process` — Submit simulation
  - `GET /status/<job_id>` — Check status
  - `GET /download/<job_id>` — Retrieve results
  - `POST /analyze` — Run analysis
  - `GET /health` — Health check
- **Features:** Request validation, file handling, response formatting

#### `app/api/schemas.py`
- **Purpose:** DataClasses for request/response validation
- **Classes:**
  - `SimulationRequest`: POST /process payload
  - `AnalysisRequest`: POST /analyze payload
  - `JobStatus`: Status response object
- **Features:** Type hints, default values, validation

#### `app/pipeline/prepare.py`
- **Purpose:** Stages 1 & 2 — Structure preparation
- **Key Functions:**
  - `prepare_system()`: Main entry point
  - `_fix_protein_with_pdbt()`: PDBFixer wrapper
  - `_clean_ligand_with_openbabel()`: Ligand prep
- **Dependencies:** PDBFixer, pdb4amber, OpenBabel
- **Output:** Fixed PDB + cleaned ligand MOL2

#### `app/pipeline/topology.py`
- **Purpose:** Stages 3 & 4 — Force field and system assembly
- **Key Functions:**
  - `build_topology()`: Main entry point
  - `_run_antechamber()`: GAFF2 parametrization
  - `_run_tleap()`: Solvation and ion addition
- **Dependencies:** antechamber, parmchk2, tleap
- **Output:** AMBER parameter + coordinate files

#### `app/pipeline/simulate.py`
- **Purpose:** Stages 5, 6, 7 — MD simulations
- **Key Functions:**
  - `run_minimization()`: Energy minimization
  - `run_equilibration()`: NPT equilibration (5 ns)
  - `run_production()`: Production MD run
  - `_setup_openmm_context()`: Initializes OpenMM system
- **Dependencies:** OpenMM
- **Output:** Trajectories + energy files

#### `app/pipeline/analyze.py`
- **Purpose:** Post-simulation analysis
- **Key Functions:**
  - `run_analysis()`: Dispatcher
  - `calculate_rmsd()`: RMSD (Cα, ligand, heavy atoms)
  - `calculate_rmsf()`: Per-residue flexibility
  - `run_pca()`: Principal component analysis
  - `run_prolif()`: Protein-ligand interactions
  - `estimate_lie()`: Binding energy (LIE method)
- **Dependencies:** MDAnalysis, RDKit, ProLIF, scikit-learn
- **Output:** CSV files + visualization plots

#### `app/pipeline/orchestrator.py`
- **Purpose:** Pipeline coordinator
- **Key Functions:**
  - `run_full_pipeline()`: 7-stage orchestrator
- **Features:**
  - Error handling & recovery
  - Status tracking
  - Results packaging
  - Environment setup (PATH, conda)
- **Called By:** Job manager via ThreadPoolExecutor

#### `app/utils/job_manager.py`
- **Purpose:** Thread-safe job registry
- **Key Classes:**
  - `JobManager`: Central job coordinator
- **Key Methods:**
  - `submit()`: Queue job for execution
  - `set_status()`: Update job status
  - `get_status()`: Retrieve job status
  - `list_jobs()`: Get all jobs
  - `cleanup()`: Remove old jobs
- **Features:** ThreadPoolExecutor pooling, status caching, error recording

#### `app/utils/file_utils.py`
- **Purpose:** File I/O utilities
- **Key Functions:**
  - `job_dir()`: Get job working directory
  - `job_path()`: Get full path for job file
  - `pack_zip()`: Create downloadable ZIP
  - `safe_read()`: Read file with error handling
  - `cleanup_job()`: Remove job directory
- **Features:** Path normalization, ZIP creation, safe cleanup

---

## Development Guide

### Project Dependencies

#### Required (Conda)
```bash
conda install -c conda-forge \
  openmm=8.1 \
  ambertools=24 \
  pdbfixer \
  openbabel \
  parmed \
  pytraj
```

#### Required (Pip)
```bash
pip install \
  flask>=3.0 \
  flask-cors>=4.0 \
  rdkit \
  mdanalysis>=2.8 \
  prolif>=2.0 \
  biopandas \
  numpy scipy pandas matplotlib seaborn
```

---

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_api.py::TestProcessEndpoint -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

---

### Code Structure & Best Practices

#### Module Organization
- **`config.py`**: Single source of truth for configuration
- **`api/routes.py`**: Thin request/response layer
- **`pipeline/*.py`**: Single responsibility per stage
- **`utils/*.py`**: Reusable utilities (no domain logic)

#### Error Handling
```python
try:
    result = run_stage()
except SpecificError as e:
    logger.error(f"Stage failed: {e}")
    job_manager.set_status(job_id, f"Error: {e}")
    return None
```

#### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"[{job_id}] Starting stage")
logger.warning(f"[{job_id}] Potential issue: {msg}")
logger.error(f"[{job_id}] Failure: {msg}", exc_info=True)
```

#### Status Updates
```python
job_manager.set_status(job_id, "Step X/7 — Descriptive message")
```

---

### Adding a New Analysis Method

To add a new post-simulation analysis:

1. **Add function to `app/pipeline/analyze.py`:**
```python
def my_new_analysis(job_id: str, trajectory_path: str, topology_path: str) -> dict:
    """
    Calculate my_new_analysis metric.
    
    Returns
    -------
    dict with keys: "output_file", "summary", "plot_path"
    """
    # Implementation
    return {
        "output_file": "my_analysis.csv",
        "summary": value,
        "plot_path": "my_analysis.png",
    }
```

2. **Register in dispatcher:**
```python
# In run_analysis()
elif requested_analysis == "my_new":
    results["my_new"] = my_new_analysis(...)
```

3. **Update API schema:**
```python
# In schemas.py, add to AnalysisRequest
AVAILABLE_ANALYSES = ["rmsd", "rmsf", "pca", "prolif", "lie", "my_new"]
```

4. **Test:**
```python
result = requests.post(f"{API_URL}/analyze", json={
    "job_id": job_id,
    "analyses": ["my_new"],
})
```

---

### Local Development Workflow

```bash
# 1. Clone repo & create environment
git clone <repo>
cd protein_ligand_md
conda env create -f environment.yml
conda activate md-sim

# 2. Install in development mode
pip install -e .

# 3. Start server with auto-reload
FLASK_ENV=development flask run --host 0.0.0.0 --port 5005 --reload

# 4. In another terminal, run tests
pytest -v --tb=short

# 5. Make changes, tests auto-rerun
# Server auto-reloads on file changes
```

---

### Docker Development

```bash
# Build development image (with pytest, ipython, etc.)
docker build --target development -t md-dev .

# Run interactive container
docker run -it --rm \
  -v /path/to/repo:/app \
  -p 5005:5005 \
  md-dev bash

# Inside container
python run.py --host 0.0.0.0 --debug

# In another container terminal
pytest tests/ -v
```

---

## Troubleshooting

### Problem: "antechamber: command not found"

**Cause:** AmberTools not in PATH

**Solutions:**
```bash
# 1. Activate conda environment
conda activate md-sim

# 2. Verify installation
which antechamber

# 3. If still missing, reinstall
conda install -c conda-forge ambertools=24
```

---

### Problem: "OpenMM CUDA not available, falling back to CPU"

**Cause:** CUDA drivers not installed or OpenMM not built for CUDA

**Solutions:**
```bash
# 1. Check CUDA availability
nvidia-smi

# 2. Reinstall OpenMM with CUDA
conda install -c conda-forge openmm-cudatoolkit

# 3. Set platform explicitly
export OPENMM_PLATFORM=CPU  # or CUDA, OpenCL

# 4. In Docker, ensure CUDA base image
# FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04
```

---

### Problem: "Job failed: PDB parsing error"

**Cause:** Malformed or incomplete PDB file

**Solutions:**
```bash
# 1. Validate PDB format
vi protein.pdb

# 2. Use PDB validation tool
# Online: https://www.rcsb.org/validation

# 3. Common issues:
#    - Missing chain IDs
#    - Unconventional residue names
#    - Non-standard atoms
#    - Disulfide bonds not formatted

# 4. Fix with BioPandas
python -c "
from biopandas.pdb import PandasPdb
ppdb = PandasPdb()
ppdb.read_pdb('protein.pdb')
ppdb.to_pdb(path='protein_clean.pdb')
"
```

---

### Problem: "tleap: unknown residue"

**Cause:** Ligand has unrecognized atom types or charges

**Solutions:**
```bash
# 1. Check GAFF2 definition
cd work
cat GAFF_LIG.frcmod

# 2. Verify parmchk2 output
cat GAFF_LIGcheck.frcmod

# 3. Use OpenBabel to standardize
obabel ligand.pdb -O ligand_std.mol2 -h
```

---

### Problem: "Simulation diverged / NaN energy"

**Cause:** Bad initial structure, too large timestep, or bad restraints

**Solutions:**
```python
# 1. Increase minimization steps
DEFAULT_MIN_STEPS = 50000  # was 20000

# 2. Reduce timestep
DEFAULT_DT_FS = 1  # was 2

# 3. Reduce restraint force constant
DEFAULT_RESTRAINT_FC = 500  # was 700

# 4. Increase equilibration time
DEFAULT_EQUIL_TIME_NS = 10.0  # was 5.0

# Submit with custom parameters:
data = {
    "ff": "ff19SB",
    "sim_time_ns": 0.01,  # Very short test
    ...
}
```

---

### Problem: "Out of memory" during trajectory write

**Cause:** Trajectory files too large

**Solutions:**
```python
# Reduce stride or production time
DEFAULT_SAVCRD_PS = 20  # was 10 (save every 20 ps, not 10)
DEFAULT_SIM_TIME_NS = 0.05  # was 0.1 (shorter simulation)

# Or increase available RAM
# In Docker: increase memory limit
# docker-compose.yml:
# services:
#   web:
#     mem_limit: 16g
```

---

### Problem: API returns 500 error

**Solution: Check logs**
```bash
# Docker
docker-compose logs -f web

# Manual
tail -f logs/app.log

# Look for traceback and specific error message
# Most common:
#  - File not found (check MD_DATA_DIR)
#  - Job not found (check job_id)
#  - Subprocess error (check config.py paths)
```

---

## Performance Optimization

### Hardware Recommendations

| Component | Minimum | Recommended | High-Performance |
|-----------|---------|-------------|------------------|
| **CPU** | 4 cores | 8+ cores | 16+ cores |
| **RAM** | 16 GB | 32+ GB | 64+ GB |
| **GPU** | Optional | NVIDIA RTX 3080 | NVIDIA A100 / H100 |
| **Storage** | 100 GB | 500 GB | 1+ TB SSD |
| **Network** | 1 Gbps | 10 Gbps | N/A |

### Simulation Speedup

- **GPU (CUDA):** 20–50× faster than CPU
- **Timestep:** Larger timesteps (2 fs) vs (1 fs) = 2× faster (but riskier)
- **Solvation:** Implicit solvent faster but less accurate than explicit
- **Parallelization:** Multi-GPU via OpenMM (requires code changes)

### Profiling

```bash
# CPU profiling
python -m cProfile -s cumtime run.py

# Memory profiling
pip install memory_profiler
python -m memory_profiler app/pipeline/simulate.py

# GPU utilization
nvidia-smi -l 1  # Refresh every 1 sec
```

---

## Version History & Roadmap

### Current Version: 1.0

**Completed Features:**
- ✅ 7-stage MD pipeline
- ✅ REST API with job tracking
- ✅ Docker containerization
- ✅ Post-simulation analysis (RMSD, RMSF, PCA, ProLIF, LIE)
- ✅ Multi-platform GPU support (CUDA, OpenCL, CPU)

**Planned Features (v1.1+):**
- 🔲 Enhanced MD protocols (replica exchange, umbrella sampling)
- 🔲 Web dashboard with real-time monitoring
- 🔲 Workflow management (AIDAgo, CWL integration)
- 🔲 Multi-protein docking
- 🔲 ML-based binding affinity prediction
- 🔲 Movie generation from trajectories
- 🔲 Publication-ready figure generation
- 🔲 Advanced visualization (PyMOL integration)

---

## References & Citation

If you use this system for research, please cite:

**Original "Making it Rain" Notebook:**
```bibtex
@article{arantes2023making,
  title={Making it rain: cloud-based molecular simulations of protein-ligand complexes},
  author={Arantes, Pablo R and others},
  journal={Journal of Chemical Theory and Computation},
  year={2023},
  publisher={ACS Publications}
}
```

**OpenMM:**
```bibtex
@article{eastman2017openmm,
  title={OpenMM 7: Rapid development of high performance molecular dynamics simulations},
  author={Eastman, Peter and others},
  journal={PLOS Computational Biology},
  year={2017}
}
```

**AmberTools:**
```
AMBER 2024, University of California, San Francisco.
```

---

## License & Support

**License:** [Specify your license]

**Support:**
- Issues: [GitHub Issues]
- Email: [contact email]
- Documentation: [This file]
- Examples: See `tests/` and API examples above

---

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -am 'Add feature'`)
4. Push to branch (`git push origin feature/my-feature`)
5. Open a Pull Request

**Code Style:**
- Python: PEP 8 (use `black` + `flake8`)
- Comments: Docstrings for all functions
- Tests: 80%+ coverage required

---

## FAQ

### Q: How long does a simulation take?
**A:** Typical 0.1 ns production run: 5–15 minutes on GPU, 30–60 min on CPU.
Equilibration adds 5–10 min. Customizable via API parameters.

### Q: Can I run multiple simulations in parallel?
**A:** Yes! The ThreadPoolExecutor pools concurrent jobs. Default: 4 workers (configurable).

### Q: What if I need a longer simulation (e.g., 10 ns)?
**A:** Submit via API with `sim_time_ns=10.0`. Longer simulations take proportionally longer.

### Q: Can I use different force fields?
**A:** Protein: ff19SB or ff14SB. Ligand: GAFF2 (auto). Water: TIP3P or OPC. All configurable per-job.

### Q: Do you support implicit solvent?
**A:** Not yet. Currently explicit solvent only. Implicit support planned for v1.1.

### Q: How do I install this on an HPC cluster?
**A:** Use Singularity container or manual conda install. See Option 3 above.

### Q: Can I extend the analysis?
**A:** Yes! Add function to `analyze.py` and register in dispatcher. See Development Guide.

---

## Appendix: Quick Command Reference

```bash
# Start server
python run.py --host 0.0.0.0 --port 5005

# Docker start
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop
docker-compose down

# Health check
curl http://localhost:5005/health

# Submit job (bash)
curl -X POST http://localhost:5005/process \
  -F "protein=@protein.pdb" \
  -F "ligand=@ligand.pdb"

# Check status
curl http://localhost:5005/status/JOB_ID

# Download results
curl -O http://localhost:5005/download/JOB_ID

# Run tests
pytest tests/ -v

# Build Docker image
docker build -t protein-ligand-md .
```

---

**End of Documentation**

For updates, detailed technical discussions, or to report issues, please refer to the repository's issue tracker or contact the maintainers.

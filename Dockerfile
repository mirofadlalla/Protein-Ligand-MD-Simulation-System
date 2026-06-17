# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile
#
# Base: continuumio/miniconda3 (Debian-based, linux/amd64)
# Required for AmberTools + OpenMM which only support Linux x86_64.
#
# Build:  docker build -t md-simulation .
# Run:    docker run -p 5005:5005 -v $(pwd)/data:/app/data md-simulation
# ─────────────────────────────────────────────────────────────────────────────

FROM continuumio/miniconda3:24.1.2-0

# Metadata
LABEL maintainer="MD Simulation System"
LABEL description="Protein-Ligand Molecular Dynamics API (OpenMM + AmberTools)"

# ── System packages ───────────────────────────────────────────────────────────
# libgomp1: required by AmberTools for OpenMP parallelism
# procps  : provides ps / free (useful for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        procps \
        curl \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Copy environment spec first (cache-friendly layer) ───────────────────────
COPY environment.yml .

# ── Create conda environment ──────────────────────────────────────────────────
# Using native libmamba solver for fast resolution
RUN conda config --set solver libmamba && \
    conda env create -f environment.yml && \
    conda clean --all -f -y

# Make conda activate work in non-interactive shells
SHELL ["/bin/bash", "--login", "-c"]

# ── Copy application source ───────────────────────────────────────────────────
COPY app/     ./app/
COPY run.py   .

# ── Create persistent data directory ─────────────────────────────────────────
RUN mkdir -p /app/data

# ── Environment variables ─────────────────────────────────────────────────────
ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5005 \
    FLASK_DEBUG=false \
    MD_DATA_DIR=/app/data \
    OPENMM_PLATFORM=AUTO \
    LOG_LEVEL=INFO \
    # Activate our conda env for all subsequent RUN / CMD calls
    PATH=/opt/conda/envs/md_env/bin:$PATH \
    CONDA_DEFAULT_ENV=md_env

# ── Expose API port ───────────────────────────────────────────────────────────
EXPOSE 5005

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5005/health || exit 1

# ── Entry point ───────────────────────────────────────────────────────────────
CMD ["python", "run.py"]

"""
orchestrator.py — Full MD pipeline orchestrator.

Ties together:
  prepare → topology → simulate (equil + prod) → package results

This is the function submitted to the background ThreadPoolExecutor by the
/process endpoint. All status updates go through job_manager.
"""

import logging
import os
from typing import Optional

from app.api.schemas import SimulationRequest
from app.config import BASE_DATA_DIR
from app.pipeline.prepare import prepare_system
from app.pipeline.topology import build_topology
from app.pipeline.simulate import run_equilibration, run_production
from app.utils.file_utils import job_dir, job_path, pack_zip, safe_read
from app.utils.job_manager import job_manager

logger = logging.getLogger(__name__)


def run_full_pipeline(job_id: str, req: SimulationRequest) -> None:
    """
    Execute the complete MD simulation pipeline for *job_id*.

    Stages
    ------
    1  Protein repair       (PDBFixer + pdb4amber)
    2  Ligand preparation   (OpenBabel + pdb4amber)
    3  GAFF2 parameters     (antechamber + parmchk2)
    4  System build         (tleap — solvation + ions)
    5  Energy minimization  (OpenMM)
    6  NPT equilibration    (OpenMM)
    7  NPT production       (OpenMM, stride loop)
    8  Package results      (ZIP)
    """

    def _status(msg: str) -> None:
        logger.info("[%s] %s", job_id, msg)
        job_manager.set_status(job_id, msg)

    try:
        work = job_dir(job_id)

        # Absolute paths to uploaded input files
        protein_raw = job_path(job_id, req.protein_filename)
        ligand_raw  = job_path(job_id, req.ligand_filename)

        # ── Build subprocess env (add conda bin to PATH) ──────────────────
        import shutil
        my_env = os.environ.copy()
        for prefix in ["/opt/conda/bin", "/usr/local/bin", "/opt/miniconda3/bin"]:
            if os.path.isdir(prefix):
                my_env["PATH"] = prefix + ":" + my_env.get("PATH", "")

        # ─────────────────────────────────────────────────────────────────
        # Stage 1 & 2 — Prepare protein + ligand
        # ─────────────────────────────────────────────────────────────────
        _status("Step 1/7 — Preparing protein and ligand structures")
        prep = prepare_system(
            job_id=job_id,
            protein_raw=protein_raw,
            ligand_raw=ligand_raw,
            work_dir=work,
            remove_waters=req.remove_waters,
            add_hydrogens=req.add_hydrogens,
            env=my_env,
        )
        fixed_protein = prep["fixed_protein"]
        clean_ligand  = prep["clean_ligand"]

        # ─────────────────────────────────────────────────────────────────
        # Stage 3 & 4 — GAFF2 topology + solvated system
        # ─────────────────────────────────────────────────────────────────
        _status("Step 2/7 — Building GAFF2 topology and solvated system")
        topo = build_topology(
            job_id=job_id,
            fixed_protein=fixed_protein,
            clean_ligand=clean_ligand,
            work_dir=work,
            net_charge=req.net_charge,
            force_field=req.force_field,
            box_size=req.box_size,
            ion_type=req.ion_type,
            salt_conc=req.salt_conc,
            env=my_env,
        )
        top_path = topo["top"]
        crd_path = topo["crd"]
        sys_pdb  = topo["pdb"]

        # ─────────────────────────────────────────────────────────────────
        # Stage 5 & 6 — Energy minimization + NPT equilibration
        # ─────────────────────────────────────────────────────────────────
        _status("Step 3/7 — Energy minimization and NPT equilibration")
        equil_prefix = job_path(job_id, f"{job_id}_equil")
        equil = run_equilibration(
            top_path=top_path,
            crd_path=crd_path,
            output_prefix=equil_prefix,
            time_ns=req.equil_time_ns,
            dt_fs=req.dt_fs,
            temp_k=req.temperature_k,
            pressure_bar=req.pressure_bar,
            restraint_fc=req.restraint_fc,
            min_steps=req.min_steps,
            savcrd_ps=req.savcrd_ps,
            print_ps=req.print_ps,
        )
        equil_rst = equil["rst"]
        equil_pdb = equil["pdb"]

        # ─────────────────────────────────────────────────────────────────
        # Stage 7 — Production MD
        # ─────────────────────────────────────────────────────────────────
        _status(f"Step 4/7 — Production MD ({req.n_strides} × {req.sim_time_ns} ns) [0%]")

        prod_prefix = job_path(job_id, f"{job_id}_prod")

        def _progress(stride_n: int, pct: int) -> None:
            _status(
                f"Step 4/7 — Production MD "
                f"({req.n_strides} × {req.sim_time_ns} ns) [{pct}%]"
            )

        prod = run_production(
            top_path=top_path,
            crd_path=crd_path,
            equil_rst=equil_rst,
            output_prefix=prod_prefix,
            stride_time_ns=req.sim_time_ns,
            n_strides=req.n_strides,
            dt_fs=req.dt_fs,
            temp_k=req.temperature_k,
            pressure_bar=req.pressure_bar,
            savcrd_ps=req.savcrd_ps,
            print_ps=req.print_ps,
            status_callback=_progress,
        )

        # ─────────────────────────────────────────────────────────────────
        # Stage 8 — Package results
        # ─────────────────────────────────────────────────────────────────
        _status("Step 5/7 — Packaging results")

        files_to_zip = [
            top_path,
            crd_path,
            sys_pdb,
            equil_pdb,
            equil["dcd"],
            equil["log"],
            *prod["dcd_files"],
            *prod["rst_files"],
            *prod.get("pdb_files", []),
        ]
        zip_path = pack_zip(job_id, files_to_zip, zip_name="Results.zip")

        # Read the final PDB for the status response
        last_pdb = prod["pdb_files"][-1] if prod.get("pdb_files") else equil_pdb
        pdb_content = safe_read(last_pdb)

        # ─────────────────────────────────────────────────────────────────
        # Store result
        # ─────────────────────────────────────────────────────────────────
        job_manager.set_result(job_id, {
            "zip_file":    zip_path,
            "top":         top_path,
            "crd":         crd_path,
            "pdb":         sys_pdb,
            "dcd_files":   prod["dcd_files"],
            "pdb_content": pdb_content,
        })
        logger.info("[%s] Pipeline completed successfully.", job_id)

    except Exception as exc:
        logger.exception("[%s] Pipeline failed: %s", job_id, exc)
        job_manager.set_error(job_id, str(exc))

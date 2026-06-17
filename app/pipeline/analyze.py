"""
analyze.py — Post-simulation trajectory analysis.

Provides:
  - RMSD / RMSF / 2D-RMSD / Radius of Gyration
  - Principal Component Analysis (PCA)
  - Pearson Cross-Correlation
  - Interaction Energy (LIE via pytraj)
  - ProLIF Ligand Interaction Fingerprint network
  - MM-PBSA / MM-GBSA via MMPBSA.py

All plotting uses Matplotlib with the 'Agg' backend (no display required).
"""

import logging
import os
import subprocess
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # must be set before pyplot import
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytraj as pt
from pytraj import matrix

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_and_close(fig: plt.Figure, path: str, dpi: int = 300) -> str:
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _load_traj(traj_path: str, top_path: str, stride: int = 1) -> pt.TrajectoryIterator:
    return pt.iterload(traj_path, top_path, stride=stride)


def _time_array(n_frames: int, savcrd_ps: int = 10, skip: int = 1) -> np.ndarray:
    dt_ns = savcrd_ps / 1000.0
    return np.arange(0, n_frames * dt_ns, dt_ns) * skip


# ─────────────────────────────────────────────────────────────────────────────
# RMSD
# ─────────────────────────────────────────────────────────────────────────────

def compute_rmsd(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    output_prefix: str = "rmsd",
    savcrd_ps: int = 10,
    skip: int = 1,
    dpi: int = 300,
) -> Dict[str, str]:
    """
    Compute and plot RMSD for *mask* atoms, referenced to frame 0.

    Returns
    -------
    dict with keys "png" and "csv".
    """
    traj   = _load_traj(traj_path, top_path, stride=skip)
    rmsd   = pt.rmsd(traj, ref=0, mask=mask)
    t_arr  = _time_array(len(rmsd), savcrd_ps, skip)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t_arr, rmsd, alpha=0.7, color="#3b82f6", linewidth=1.2, label=f"RMSD ({mask})")
    ax.set_xlabel("Time (ns)", fontsize=13, fontweight="bold")
    ax.set_ylabel("RMSD (Å)", fontsize=13, fontweight="bold")
    ax.legend(frameon=False)
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame({"time_ns": t_arr, "rmsd_A": rmsd}).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# RMSF
# ─────────────────────────────────────────────────────────────────────────────

def compute_rmsf(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    output_prefix: str = "rmsf",
    dpi: int = 300,
) -> Dict[str, str]:
    traj = _load_traj(traj_path, top_path)
    rmsf = pt.rmsf(traj, mask)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(rmsf[:, 0], rmsf[:, 1], color="#ef4444", linewidth=1.0)
    ax.set_xlabel("Residue", fontsize=13, fontweight="bold")
    ax.set_ylabel("RMSF (Å)", fontsize=13, fontweight="bold")
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame({"residue": rmsf[:, 0], "rmsf_A": rmsf[:, 1]}).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# Radius of Gyration
# ─────────────────────────────────────────────────────────────────────────────

def compute_radgyr(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    output_prefix: str = "radgyr",
    savcrd_ps: int = 10,
    skip: int = 1,
    dpi: int = 300,
) -> Dict[str, str]:
    traj   = _load_traj(traj_path, top_path, stride=skip)
    radgyr = pt.radgyr(traj, mask=mask)
    t_arr  = _time_array(len(radgyr), savcrd_ps, skip)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t_arr, radgyr, color="#22c55e", linewidth=1.0)
    ax.set_xlabel("Time (ns)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Radius of Gyration (Å)", fontsize=13, fontweight="bold")
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame({"time_ns": t_arr, "radgyr_A": radgyr}).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# 2D RMSD (pairwise)
# ─────────────────────────────────────────────────────────────────────────────

def compute_2d_rmsd(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    output_prefix: str = "2d_rmsd",
    simulation_ns: float = 10.0,
    dpi: int = 300,
) -> Dict[str, str]:
    traj   = _load_traj(traj_path, top_path)
    n      = len(traj)
    mat    = pt.pairwise_rmsd(traj, mask=mask, frame_indices=range(n))

    tick_n    = min(5, n)
    tick_idx  = np.linspace(0, n - 1, tick_n + 1)
    tick_time = np.linspace(0, simulation_ns, tick_n + 1).round(2)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(mat, cmap="PRGn", origin="lower", interpolation="bicubic")
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_time)
    ax.set_yticks(tick_idx)
    ax.set_yticklabels(tick_time)
    ax.set_xlabel("Time (ns)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Time (ns)", fontsize=13, fontweight="bold")
    ax.set_title("Pairwise 2D RMSD")
    fig.colorbar(im, label="RMSD (Å)")
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame(mat).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# PCA
# ─────────────────────────────────────────────────────────────────────────────

def compute_pca(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    n_vecs: int = 2,
    output_prefix: str = "pca",
    simulation_ns: float = 10.0,
    dpi: int = 300,
) -> Dict[str, str]:
    traj = _load_traj(traj_path, top_path)
    n    = len(traj)
    data = pt.pca(traj, fit=True, ref=0, mask=mask, n_vecs=n_vecs)
    pc1  = data[0][0]
    pc2  = data[0][1]

    fig, ax = plt.subplots(figsize=(7, 6))
    sc = ax.scatter(pc1, pc2, c=range(n), cmap="plasma", s=6, alpha=0.8)
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Frame", fontsize=12)
    ax.set_xlabel("PC1", fontsize=13, fontweight="bold")
    ax.set_ylabel("PC2", fontsize=13, fontweight="bold")
    ax.set_title(r"PCA of C-$\alpha$")
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame({"PC1": pc1, "PC2": pc2}).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# Pearson Cross-Correlation
# ─────────────────────────────────────────────────────────────────────────────

def compute_cross_corr(
    traj_path: str,
    top_path: str,
    mask: str = "@CA",
    output_prefix: str = "cross_corr",
    dpi: int = 300,
) -> Dict[str, str]:
    traj  = _load_traj(traj_path, top_path)
    traj_aligned = pt.align(traj, mask=mask, ref=0)
    mat_cc = matrix.correl(traj_aligned, mask)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(mat_cc, cmap="PiYG_r", interpolation="bicubic", vmin=-1, vmax=1, origin="lower")
    ax.set_xlabel("Residues", fontsize=13, fontweight="bold")
    ax.set_ylabel("Residues", fontsize=13, fontweight="bold")
    ax.set_title("Pearson Cross-Correlation")
    fig.colorbar(im, label="CC$_{ij}$")
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame(mat_cc).to_csv(csv, index=False)

    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# Interaction Energy (LIE)
# ─────────────────────────────────────────────────────────────────────────────

def compute_interaction_energy(
    traj_path: str,
    top_path: str,
    output_prefix: str = "interaction_energy",
    savcrd_ps: int = 10,
    skip: int = 1,
    dpi: int = 300,
) -> Dict[str, str]:
    traj    = _load_traj(traj_path, top_path, stride=skip)
    pt_top  = traj.top

    sel_mask = "!(:WAT) & !(:Na+) & !(:Cl-) & !(:Mg+) & !(:K+) & !(:LIG)"
    indices  = pt.select_atoms(sel_mask, pt_top)
    first    = int(indices[0])
    last     = int(indices[-1])
    lie_mask = f"LIE :LIG @{first+1}-{last+1}"

    lie     = pt.analysis.energy_analysis.lie(
        traj, mask=lie_mask, options="cutvdw 12.0 cutelec 12.0 diel 2.0", dtype="dict"
    )
    elec    = lie["LIE[EELEC]"]
    vdw     = lie["LIE[EVDW]"]
    total   = elec + vdw
    t_arr   = _time_array(len(total), savcrd_ps, skip)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t_arr, total, alpha=0.7, color="#3b82f6",  label="Total",  linewidth=1.2)
    ax.plot(t_arr, elec,  alpha=0.7, color="#22c55e",  label="Electrostatic", linewidth=1.2)
    ax.plot(t_arr, vdw,   alpha=0.7, color="#ef4444",  label="van der Waals", linewidth=1.2)
    ax.set_xlabel("Time (ns)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Interaction Energy (kcal/mol)", fontsize=13, fontweight="bold")
    ax.legend(frameon=False)
    fig.tight_layout()

    png = _save_and_close(fig, output_prefix + ".png", dpi=dpi)
    csv = output_prefix + ".csv"
    pd.DataFrame({"time_ns": t_arr, "total": total, "elec": elec, "vdw": vdw}).to_csv(csv, index=False)

    logger.info(
        "IE: total=%.2f ± %.2f kcal/mol", mean(list(total)), stdev(list(total))
    )
    return {"png": png, "csv": csv}


# ─────────────────────────────────────────────────────────────────────────────
# ProLIF Interaction Fingerprint Network
# ─────────────────────────────────────────────────────────────────────────────

def compute_prolif_network(
    top_path: str,
    traj_path: str,
    output_html: str,
    stride: int = 1,
    threshold: float = 0.3,
    kind: str = "aggregate",
) -> str:
    """
    Compute ProLIF ligand-protein interaction fingerprint and save as HTML.

    Returns
    -------
    Absolute path of the saved HTML file.
    """
    try:
        import MDAnalysis as mda
        import prolif as plf
        from prolif.plotting.network import LigNetwork
    except ImportError as exc:
        raise ImportError("MDAnalysis and prolif are required for ProLIF analysis.") from exc

    u    = mda.Universe(top_path, traj_path)
    lig  = u.select_atoms("resname LIG")
    prot = u.select_atoms("protein")

    lmol = plf.Molecule.from_mda(lig)

    fp = plf.Fingerprint()
    fp.run(u.trajectory[::stride], lig, prot)
    df = fp.to_dataframe(return_atoms=True)

    net = LigNetwork.from_ifp(df, lmol, kind=kind, threshold=threshold, rotation=270)
    net.save(output_html)
    logger.info("ProLIF network saved to: %s", output_html)
    return output_html


# ─────────────────────────────────────────────────────────────────────────────
# Convenience bundle
# ─────────────────────────────────────────────────────────────────────────────

def run_standard_analysis(
    job_id: str,
    top_path: str,
    traj_path: str,
    work_dir: str,
    simulation_ns: float = 10.0,
    savcrd_ps: int = 10,
    skip: int = 1,
    dpi: int = 300,
) -> Dict[str, str]:
    """
    Run the standard analysis suite and return a dict of output file paths.

    Analyses performed:
      RMSD, RMSF, Radius of Gyration, 2D RMSD, PCA, Cross-Correlation,
      Interaction Energy, ProLIF network.
    """
    results: Dict[str, str] = {}
    base = os.path.join(work_dir, job_id)

    def _p(name):
        return f"{base}_{name}"

    try:
        results["rmsd"]         = compute_rmsd(traj_path, top_path, output_prefix=_p("rmsd"), savcrd_ps=savcrd_ps, skip=skip, dpi=dpi)["png"]
        results["rmsf"]         = compute_rmsf(traj_path, top_path, output_prefix=_p("rmsf"), dpi=dpi)["png"]
        results["radgyr"]       = compute_radgyr(traj_path, top_path, output_prefix=_p("radgyr"), savcrd_ps=savcrd_ps, skip=skip, dpi=dpi)["png"]
        results["2d_rmsd"]      = compute_2d_rmsd(traj_path, top_path, output_prefix=_p("2d_rmsd"), simulation_ns=simulation_ns, dpi=dpi)["png"]
        results["pca"]          = compute_pca(traj_path, top_path, output_prefix=_p("pca"), simulation_ns=simulation_ns, dpi=dpi)["png"]
        results["cross_corr"]   = compute_cross_corr(traj_path, top_path, output_prefix=_p("cross_corr"), dpi=dpi)["png"]
        results["interaction_e"]= compute_interaction_energy(traj_path, top_path, output_prefix=_p("lie"), savcrd_ps=savcrd_ps, skip=skip, dpi=dpi)["png"]
    except Exception as exc:
        logger.error("Analysis error: %s", exc)

    try:
        prolif_html = _p("prolif.html")
        compute_prolif_network(top_path, traj_path, prolif_html)
        results["prolif"] = prolif_html
    except Exception as exc:
        logger.warning("ProLIF analysis skipped: %s", exc)

    return results

"""
prepare.py — Protein and ligand preparation stage.

Handles:
  1. Protein repair    (PDBFixer)
  2. Protein cleanup   (pdb4amber)
  3. Ligand H-addition (OpenBabel)
  4. Ligand cleanup    (pdb4amber)

All Google-Drive / Colab-specific code has been removed. The module works
purely on local files and uses subprocess calls to AmberTools binaries.
"""

import logging
import os
import subprocess
from typing import Optional

from pdbfixer import PDBFixer
from openmm.app import PDBFile

from app.config import OBABEL_BIN, PDB4AMBER_BIN

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Protein preparation
# ─────────────────────────────────────────────────────────────────────────────

def fix_protein(
    input_pdb: str,
    output_pdb: str,
    remove_waters: bool = True,
    remove_heterogens: bool = True,
) -> str:
    """
    Repair a protein PDB file using PDBFixer.

    Steps
    -----
    - Find and fill missing residues.
    - Find and add missing heavy atoms.
    - Optionally remove waters / heterogens (ligands bound in the crystal).

    Parameters
    ----------
    input_pdb        : Absolute path to the raw protein PDB.
    output_pdb       : Destination path for the fixed PDB.
    remove_waters    : Strip crystallographic water molecules.
    remove_heterogens: Strip all HETATM records (including crystal ligands).

    Returns
    -------
    Absolute path of the written output file.
    """
    logger.info("Fixing protein: %s", input_pdb)
    fixer = PDBFixer(filename=input_pdb)
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(7.0)  # pH 7

    if remove_heterogens:
        fixer.removeHeterogens(keepWater=not remove_waters)
    elif remove_waters:
        fixer.removeHeterogens(keepWater=False)

    with open(output_pdb, "w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh)

    logger.info("Fixed protein written to: %s", output_pdb)
    return output_pdb


def clean_protein_pdb4amber(
    input_pdb: str,
    output_pdb: str,
    env: Optional[dict] = None,
) -> str:
    """
    Run pdb4amber to standardise residue names and remove non-standard atoms.

    Parameters
    ----------
    input_pdb  : Path to the PDBFixer-repaired protein PDB.
    output_pdb : Destination path.
    env        : Optional environment variables dict for subprocess.

    Returns
    -------
    Absolute path of the pdb4amber-cleaned file.

    Raises
    ------
    RuntimeError if pdb4amber returns a non-zero exit code.
    """
    logger.info("Running pdb4amber on: %s", input_pdb)
    cmd = [PDB4AMBER_BIN, "-i", input_pdb, "-o", output_pdb, "-a"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"pdb4amber failed (protein).\nSTDERR:\n{result.stderr}"
        )
    logger.info("pdb4amber output: %s", output_pdb)
    return output_pdb


# ─────────────────────────────────────────────────────────────────────────────
# Ligand preparation
# ─────────────────────────────────────────────────────────────────────────────

def add_hydrogens_obabel(
    input_pdb: str,
    output_pdb: str,
    env: Optional[dict] = None,
) -> str:
    """
    Add hydrogens to a ligand PDB using OpenBabel.

    Parameters
    ----------
    input_pdb  : Raw ligand PDB path.
    output_pdb : Output PDB with added hydrogens.
    env        : Optional environment for subprocess.

    Returns
    -------
    Absolute path of the hydrogen-added file.

    Raises
    ------
    RuntimeError if obabel returns a non-zero exit code.
    """
    logger.info("Adding hydrogens to ligand via OpenBabel: %s", input_pdb)
    cmd = [OBABEL_BIN, input_pdb, "-O", output_pdb, "-h", "--partialcharge", "gasteiger"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    # obabel often writes warnings to stderr even on success; check returncode only
    if result.returncode != 0:
        raise RuntimeError(
            f"OpenBabel (add-H) failed.\nSTDERR:\n{result.stderr}"
        )
    logger.info("H-added ligand written to: %s", output_pdb)
    return output_pdb


def clean_ligand_pdb4amber(
    input_pdb: str,
    output_pdb: str,
    env: Optional[dict] = None,
) -> str:
    """
    Run pdb4amber on the ligand to standardise atom names.

    Returns
    -------
    Absolute path of the pdb4amber-cleaned ligand file.

    Raises
    ------
    RuntimeError if pdb4amber returns a non-zero exit code.
    """
    logger.info("Running pdb4amber on ligand: %s", input_pdb)
    cmd = [PDB4AMBER_BIN, "-i", input_pdb, "-o", output_pdb]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"pdb4amber failed (ligand).\nSTDERR:\n{result.stderr}"
        )
    logger.info("pdb4amber ligand output: %s", output_pdb)
    return output_pdb


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: full preparation pipeline for one job
# ─────────────────────────────────────────────────────────────────────────────

def prepare_system(
    job_id: str,
    protein_raw: str,
    ligand_raw: str,
    work_dir: str,
    remove_waters: bool = True,
    add_hydrogens: bool = True,
    env: Optional[dict] = None,
) -> dict:
    """
    Run the full protein + ligand preparation pipeline.

    Returns
    -------
    dict with keys:
        "fixed_protein"  – PDBFixer + pdb4amber cleaned protein PDB
        "clean_ligand"   – pdb4amber cleaned ligand PDB (hydrogens added)
    """
    # ── Protein ──────────────────────────────────────────────────────────────
    pdbfixer_out  = os.path.join(work_dir, f"{job_id}_pdbfixer.pdb")
    fixed_protein = os.path.join(work_dir, f"{job_id}_fixed_protein.pdb")

    fix_protein(protein_raw, pdbfixer_out, remove_waters=remove_waters)
    clean_protein_pdb4amber(pdbfixer_out, fixed_protein, env=env)

    # ── Ligand ───────────────────────────────────────────────────────────────
    if add_hydrogens:
        lig_h = os.path.join(work_dir, f"{job_id}_lig_H.pdb")
        add_hydrogens_obabel(ligand_raw, lig_h, env=env)
        lig_input = lig_h
    else:
        lig_input = ligand_raw

    clean_ligand = os.path.join(work_dir, f"{job_id}_clean_ligand.pdb")
    clean_ligand_pdb4amber(lig_input, clean_ligand, env=env)

    return {
        "fixed_protein": fixed_protein,
        "clean_ligand":  clean_ligand,
    }

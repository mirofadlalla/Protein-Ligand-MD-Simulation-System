"""
topology.py — System building: GAFF2 parameterization and tleap solvation.

Handles:
  1. antechamber  — GAFF2 partial charges (BCC) + mol2 output
  2. parmchk2     — Missing GAFF2 parameter check → .frcmod
  3. tleap        — Two-pass solvation + ion addition → .prmtop / .crd / .pdb
"""

import logging
import os
import subprocess
from typing import Optional

from app.config import (
    ANTECHAMBER_BIN,
    PARMCHK2_BIN,
    TLEAP_BIN,
    FF_MAP,
    DEFAULT_FORCE_FIELD,
    DEFAULT_BOX_SIZE,
    DEFAULT_SALT_CONC,
    DEFAULT_ION_TYPE,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Antechamber — GAFF2 parameterization
# ─────────────────────────────────────────────────────────────────────────────

def run_antechamber(
    ligand_pdb: str,
    output_mol2: str,
    net_charge: int = 0,
    env: Optional[dict] = None,
) -> str:
    """
    Parameterize a ligand with GAFF2 using BCC partial charges.

    Parameters
    ----------
    ligand_pdb   : Cleaned ligand PDB (from pdb4amber).
    output_mol2  : Output mol2 file path.
    net_charge   : Net formal charge of the ligand.
    env          : Optional subprocess environment.

    Returns
    -------
    Absolute path of the output mol2 file.

    Raises
    ------
    RuntimeError on non-zero exit.
    """
    logger.info("Running antechamber on: %s (charge=%d)", ligand_pdb, net_charge)
    cmd = [
        ANTECHAMBER_BIN,
        "-i",   ligand_pdb,
        "-fi",  "pdb",
        "-o",   output_mol2,
        "-fo",  "mol2",
        "-c",   "bcc",
        "-at",  "gaff2",
        "-nc",  str(net_charge),
        "-rn",  "LIG",
        "-s",   "2",   # verbosity
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(output_mol2),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"antechamber failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    logger.info("mol2 written to: %s", output_mol2)
    return output_mol2


# ─────────────────────────────────────────────────────────────────────────────
# parmchk2 — Missing parameter check
# ─────────────────────────────────────────────────────────────────────────────

def run_parmchk2(
    input_mol2: str,
    output_frcmod: str,
    env: Optional[dict] = None,
) -> str:
    """
    Generate missing GAFF2 parameters with parmchk2.

    Returns
    -------
    Absolute path of the output .frcmod file.

    Raises
    ------
    RuntimeError on non-zero exit.
    """
    logger.info("Running parmchk2 on: %s", input_mol2)
    cmd = [PARMCHK2_BIN, "-i", input_mol2, "-f", "mol2", "-o", output_frcmod, "-s", "gaff2"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"parmchk2 failed.\nSTDERR:\n{result.stderr}"
        )
    logger.info("frcmod written to: %s", output_frcmod)
    return output_frcmod


# ─────────────────────────────────────────────────────────────────────────────
# tleap — System building
# ─────────────────────────────────────────────────────────────────────────────

def _write_tleap_script(path: str, content: str) -> None:
    with open(path, "w") as fh:
        fh.write(content)


def _run_tleap(script_path: str, env: Optional[dict] = None) -> str:
    """Run tleap with *script_path* and return stdout."""
    cmd = [TLEAP_BIN, "-f", script_path]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(script_path),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tleap failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout


def build_ligand_lib(
    mol2_path: str,
    frcmod_path: str,
    lib_path: str,
    gaff_pdb_path: str,
    tleap_in: str,
    force_field: str = DEFAULT_FORCE_FIELD,
    env: Optional[dict] = None,
) -> str:
    """
    First tleap pass: generate .lib and .pdb for the ligand alone.

    Returns
    -------
    Absolute path of the created .lib file.
    """
    leaprc_ff, _, _ = FF_MAP.get(force_field, FF_MAP[DEFAULT_FORCE_FIELD])
    script = (
        f"source {leaprc_ff}\n"
        f"source leaprc.gaff2\n"
        f"LIG = loadmol2 {mol2_path}\n"
        f"loadamberparams {frcmod_path}\n"
        f"saveoff LIG {lib_path}\n"
        f"savepdb LIG {gaff_pdb_path}\n"
        f"quit\n"
    )
    _write_tleap_script(tleap_in, script)
    _run_tleap(tleap_in, env=env)
    logger.info("Ligand lib written to: %s", lib_path)
    return lib_path


def build_solvated_system(
    protein_pdb: str,
    ligand_gaff_pdb: str,
    mol2_path: str,
    frcmod_path: str,
    lib_path: str,
    output_top: str,
    output_crd: str,
    output_pdb: str,
    tleap_in: str,
    force_field: str = DEFAULT_FORCE_FIELD,
    box_size: float = DEFAULT_BOX_SIZE,
    ion_type: str = DEFAULT_ION_TYPE,
    salt_conc: float = DEFAULT_SALT_CONC,
    env: Optional[dict] = None,
) -> dict:
    """
    Second tleap pass: combine protein + ligand, solvate, add ions.

    Returns
    -------
    dict with keys "top", "crd", "pdb" pointing to the output files.

    Raises
    ------
    RuntimeError on tleap failure.
    """
    leaprc_ff, leaprc_water, water_box = FF_MAP.get(force_field, FF_MAP[DEFAULT_FORCE_FIELD])

    # ── First pass: get box volume for ion counting ───────────────────────
    protein_ligand_pdb = output_pdb + ".tmp_nw.pdb"
    nw_top = output_top + ".tmp_nw.prmtop"
    nw_crd = output_crd + ".tmp_nw.crd"

    script_nw = (
        f"source {leaprc_ff}\n"
        f"source leaprc.DNA.OL15\n"
        f"source leaprc.RNA.OL3\n"
        f"source leaprc.GLYCAM_06j-1\n"
        f"source leaprc.gaff2\n"
        f"source {leaprc_water}\n"
        f"loadamberparams {frcmod_path}\n"
        f"loadoff {lib_path}\n"
        f"PROT = loadpdb {protein_pdb}\n"
        f"LIG  = loadpdb {ligand_gaff_pdb}\n"
        f"SYS  = combine {{ PROT LIG }}\n"
        f"alignaxes SYS\n"
        f"solvatebox SYS {water_box} {box_size} 0.7\n"
        f"saveamberparm SYS {nw_top} {nw_crd}\n"
        f"savepdb SYS {protein_ligand_pdb}\n"
        f"quit\n"
    )
    _write_tleap_script(tleap_in, script_nw)
    stdout_nw = _run_tleap(tleap_in, env=env)

    # Parse box volume from tleap output
    vol = 200_000.0
    for line in stdout_nw.splitlines():
        if "Volume:" in line:
            try:
                vol = float(line.split()[1])
            except (IndexError, ValueError):
                pass

    # Calculate number of ion pairs
    vol_lit  = vol * 1e-27
    atom_lit = 9.03e22
    num_ion  = int(vol_lit * (salt_conc / 0.15) * atom_lit) if salt_conc > 0 else 0
    pos_ion  = "Na+" if ion_type == "NaCl" else "K+"

    logger.info(
        "Box volume=%.1f Å³  →  %d %s / %d Cl- pairs", vol, num_ion, pos_ion, num_ion
    )

    # ── Second pass: add ions + save final topology ───────────────────────
    add_salt_str = f"addIonsRand SYS {pos_ion} {num_ion} Cl- {num_ion}\n" if num_ion > 0 else ""
    script_final = (
        f"source {leaprc_ff}\n"
        f"source leaprc.DNA.OL15\n"
        f"source leaprc.RNA.OL3\n"
        f"source leaprc.GLYCAM_06j-1\n"
        f"source leaprc.gaff2\n"
        f"source {leaprc_water}\n"
        f"loadamberparams {frcmod_path}\n"
        f"loadoff {lib_path}\n"
        f"PROT = loadpdb {protein_pdb}\n"
        f"LIG  = loadpdb {ligand_gaff_pdb}\n"
        f"SYS  = combine {{ PROT LIG }}\n"
        f"alignaxes SYS\n"
        f"check SYS\n"
        f"charge SYS\n"
        f"addions SYS {pos_ion} 0\n"
        f"addions SYS Cl- 0\n"
        f"check SYS\n"
        f"charge SYS\n"
        f"solvatebox SYS {water_box} {box_size} 0.7\n"
        f"{add_salt_str}"
        f"saveamberparm SYS {output_top} {output_crd}\n"
        f"savepdb SYS {output_pdb}\n"
        f"quit\n"
    )
    _write_tleap_script(tleap_in, script_final)
    _run_tleap(tleap_in, env=env)

    logger.info("Solvated system: top=%s crd=%s pdb=%s", output_top, output_crd, output_pdb)

    # Clean up temp files
    for tmp in [protein_ligand_pdb, nw_top, nw_crd]:
        try:
            os.remove(tmp)
        except OSError:
            pass

    return {"top": output_top, "crd": output_crd, "pdb": output_pdb}


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: full topology pipeline for one job
# ─────────────────────────────────────────────────────────────────────────────

def build_topology(
    job_id: str,
    fixed_protein: str,
    clean_ligand: str,
    work_dir: str,
    net_charge: int = 0,
    force_field: str = DEFAULT_FORCE_FIELD,
    box_size: float = DEFAULT_BOX_SIZE,
    ion_type: str = DEFAULT_ION_TYPE,
    salt_conc: float = DEFAULT_SALT_CONC,
    env: Optional[dict] = None,
) -> dict:
    """
    Full topology build for one job: antechamber → parmchk2 → tleap.

    Returns
    -------
    dict with keys "top", "crd", "pdb", "mol2", "frcmod", "lib".
    """
    mol2      = os.path.join(work_dir, f"{job_id}_lig.mol2")
    frcmod    = os.path.join(work_dir, f"{job_id}_lig.frcmod")
    lib       = os.path.join(work_dir, f"{job_id}_lig.lib")
    gaff_pdb  = os.path.join(work_dir, f"{job_id}_ligand_gaff.pdb")
    tleap_in  = os.path.join(work_dir, f"{job_id}_tleap.in")
    top_out   = os.path.join(work_dir, f"{job_id}_SYS.prmtop")
    crd_out   = os.path.join(work_dir, f"{job_id}_SYS.crd")
    pdb_out   = os.path.join(work_dir, f"{job_id}_SYS.pdb")

    run_antechamber(clean_ligand, mol2, net_charge=net_charge, env=env)
    run_parmchk2(mol2, frcmod, env=env)
    build_ligand_lib(mol2, frcmod, lib, gaff_pdb, tleap_in, force_field=force_field, env=env)

    sys_files = build_solvated_system(
        protein_pdb=fixed_protein,
        ligand_gaff_pdb=gaff_pdb,
        mol2_path=mol2,
        frcmod_path=frcmod,
        lib_path=lib,
        output_top=top_out,
        output_crd=crd_out,
        output_pdb=pdb_out,
        tleap_in=tleap_in,
        force_field=force_field,
        box_size=box_size,
        ion_type=ion_type,
        salt_conc=salt_conc,
        env=env,
    )

    return {**sys_files, "mol2": mol2, "frcmod": frcmod, "lib": lib}

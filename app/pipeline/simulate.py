"""
simulate.py — OpenMM NPT Equilibration + Production MD.

Directly derived from the notebook's equilibration and production cells, but
refactored into standalone functions that accept configuration objects instead
of global variables.

Key changes vs notebook:
  - Google Drive / Colab code removed
  - Platform auto-detected (CUDA → OpenCL → CPU)
  - Positional restraints using pytraj atom selection
  - Stride loop with per-stride .rst XML state files
"""

import fnmatch
import logging
import os
from typing import Optional

import openmm as mm
from openmm import XmlSerializer
from openmm.app import (
    AmberInpcrdFile,
    AmberPrmtopFile,
    DCDReporter,
    HBonds,
    PME,
    PDBFile,
    Simulation,
    StateDataReporter,
)
from openmm.unit import (
    bar,
    femtosecond,
    kelvin,
    kilojoule,
    mole,
    nanometer,
    nanometers,
    picosecond,
)
import pytraj as pt

from app.config import (
    DEFAULT_DT_FS,
    DEFAULT_EQUIL_TIME_NS,
    DEFAULT_MIN_STEPS,
    DEFAULT_PRESSURE_BAR,
    DEFAULT_PRINT_PS,
    DEFAULT_RESTRAINT_FC,
    DEFAULT_SAVCRD_PS,
    DEFAULT_SIM_TIME_NS,
    DEFAULT_TEMP_K,
    OPENMM_PLATFORM,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Platform selection
# ─────────────────────────────────────────────────────────────────────────────

def _get_platform() -> mm.Platform:
    """
    Return the best available OpenMM Platform.

    Order: CUDA → OpenCL → CPU (or whatever OPENMM_PLATFORM is set to).
    """
    if OPENMM_PLATFORM != "AUTO":
        try:
            return mm.Platform.getPlatformByName(OPENMM_PLATFORM)
        except Exception:
            logger.warning("Requested platform %s not available; falling back.", OPENMM_PLATFORM)

    for name in ("CUDA", "OpenCL", "CPU"):
        try:
            platform = mm.Platform.getPlatformByName(name)
            logger.info("Using OpenMM platform: %s", name)
            return platform
        except Exception:
            continue

    raise RuntimeError("No usable OpenMM platform found.")


def _platform_properties(platform: mm.Platform) -> dict:
    """Return platform-specific properties (precision for CUDA/OpenCL)."""
    if platform.getName() in ("CUDA", "OpenCL"):
        return {"Precision": "mixed"}
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Positional restraints (from notebook)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_restraints(system: mm.System, inpcrd: AmberInpcrdFile, fc: float, top_path: str) -> mm.System:
    """
    Apply positional restraints on all non-hydrogen heavy atoms (protein + ligand)
    using pytraj atom selection.

    Parameters
    ----------
    system  : OpenMM System to modify.
    inpcrd  : Loaded AmberInpcrdFile (has positions).
    fc      : Force constant in kJ/mol/nm².
    top_path: Path to the .prmtop file used for pytraj selection.
    """
    if fc <= 0:
        return system

    pt_traj    = pt.iterload(inpcrd.file.name if hasattr(inpcrd, "file") else "", top_path)
    pt_top     = pt_traj.top
    # Select all non-hydrogen, non-solvent, non-ion atoms
    sel_mask   = "!(:H*) & !(:WAT) & !(:Na+) & !(:Cl-) & !(:Mg+) & !(:K+)"
    try:
        indices = pt.select_atoms(sel_mask, pt_top)
    except Exception:
        # If pytraj can't parse, fall back to an empty selection (no restraints)
        logger.warning("pytraj selection failed — no positional restraints applied.")
        return system

    posres = mm.CustomExternalForce("k*periodicdistance(x, y, z, x0, y0, z0)^2;")
    posres.addPerParticleParameter("k")
    posres.addPerParticleParameter("x0")
    posres.addPerParticleParameter("y0")
    posres.addPerParticleParameter("z0")

    for idx in indices:
        idx = int(idx)
        pos = inpcrd.positions[idx].value_in_unit(nanometers)
        posres.addParticle(idx, [fc, pos[0], pos[1], pos[2]])

    system.addForce(posres)
    logger.info("Applied positional restraints (k=%.1f kJ/mol) on %d atoms.", fc, len(indices))
    return system


# ─────────────────────────────────────────────────────────────────────────────
# Equilibration
# ─────────────────────────────────────────────────────────────────────────────

def run_equilibration(
    top_path: str,
    crd_path: str,
    output_prefix: str,
    time_ns: float = DEFAULT_EQUIL_TIME_NS,
    dt_fs: int = DEFAULT_DT_FS,
    temp_k: float = DEFAULT_TEMP_K,
    pressure_bar: float = DEFAULT_PRESSURE_BAR,
    restraint_fc: float = DEFAULT_RESTRAINT_FC,
    min_steps: int = DEFAULT_MIN_STEPS,
    savcrd_ps: int = DEFAULT_SAVCRD_PS,
    print_ps: int = DEFAULT_PRINT_PS,
) -> dict:
    """
    Run NPT equilibration.

    Parameters
    ----------
    top_path      : .prmtop topology file.
    crd_path      : .crd / .inpcrd coordinate file.
    output_prefix : Base path for output files (no extension).
    time_ns       : Equilibration duration in nanoseconds.
    dt_fs         : Integration time step in femtoseconds.
    temp_k        : Target temperature in Kelvin.
    pressure_bar  : Target pressure in bar.
    restraint_fc  : Position restraint force constant (kJ/mol). 0 = no restraints.
    min_steps     : Number of energy minimization steps.
    savcrd_ps     : Frequency to write trajectory (picoseconds).
    print_ps      : Frequency to write log (picoseconds).

    Returns
    -------
    dict with keys "dcd", "log", "rst", "pdb" (output file paths).
    """
    dcd_file = output_prefix + ".dcd"
    log_file = output_prefix + ".log"
    rst_file = output_prefix + ".rst"
    pdb_file = output_prefix + ".pdb"

    # ── Unit conversions ─────────────────────────────────────────────────────
    sim_time  = float(time_ns) * 1000 * picosecond   # ns → ps
    dt        = int(dt_fs) * femtosecond
    temp      = float(temp_k) * kelvin
    pres      = float(pressure_bar) * bar
    sav_freq  = int(savcrd_ps) * picosecond
    prnt_freq = int(print_ps) * picosecond
    nsteps    = int(sim_time.value_in_unit(picosecond) / dt.value_in_unit(picosecond))
    nsavcrd   = int(sav_freq.value_in_unit(picosecond)  / dt.value_in_unit(picosecond))
    nprint    = int(prnt_freq.value_in_unit(picosecond) / dt.value_in_unit(picosecond))

    logger.info(
        "Equilibration: %.1f ns, T=%.0f K, P=%.1f bar, restraint_fc=%.0f kJ/mol",
        time_ns, temp_k, pressure_bar, restraint_fc,
    )

    # ── Load topology ────────────────────────────────────────────────────────
    prmtop = AmberPrmtopFile(top_path)
    inpcrd = AmberInpcrdFile(crd_path)

    # ── Create system ────────────────────────────────────────────────────────
    system = prmtop.createSystem(
        nonbondedMethod=PME,
        nonbondedCutoff=1.0 * nanometers,
        ewaldErrorTolerance=0.0005,
        constraints=HBonds,
        rigidWater=True,
    )

    # Positional restraints
    system = _apply_restraints(system, inpcrd, restraint_fc, top_path)

    system.addForce(mm.MonteCarloBarostat(pres, temp))

    friction = 1.0
    integrator = mm.LangevinIntegrator(temp, friction, dt)
    integrator.setConstraintTolerance(1e-6)

    platform = _get_platform()
    simulation = Simulation(
        prmtop.topology, system, integrator, platform, _platform_properties(platform)
    )
    simulation.context.setPositions(inpcrd.positions)
    if inpcrd.boxVectors is not None:
        simulation.context.setPeriodicBoxVectors(*inpcrd.boxVectors)

    # ── Minimization ─────────────────────────────────────────────────────────
    logger.info("Minimizing energy (%d steps)...", min_steps)
    simulation.minimizeEnergy(
        tolerance=10 * kilojoule / mole / nanometer,
        maxIterations=min_steps,
    )
    pe = simulation.context.getState(getEnergy=True).getPotentialEnergy()
    logger.info("Potential energy after minimization: %s", pe)

    simulation.context.setVelocitiesToTemperature(temp)

    # ── Reporters ────────────────────────────────────────────────────────────
    dcd = DCDReporter(dcd_file, nsavcrd)
    dcd._dcd = dcd._dcd.__class__(
        dcd._out, simulation.topology, simulation.integrator.getStepSize(),
        nsteps + nsavcrd, nsavcrd,
    )
    simulation.reporters.append(dcd)
    simulation.reporters.append(
        StateDataReporter(log_file, nprint, step=True, kineticEnergy=True,
                          potentialEnergy=True, totalEnergy=True, temperature=True,
                          volume=True, speed=True)
    )

    # ── Run ──────────────────────────────────────────────────────────────────
    logger.info("Running equilibration: %d steps...", nsteps)
    simulation.step(nsteps)
    simulation.reporters.clear()

    # ── Save state ───────────────────────────────────────────────────────────
    state = simulation.context.getState(getPositions=True, getVelocities=True)
    with open(rst_file, "w") as fh:
        fh.write(XmlSerializer.serialize(state))

    positions = simulation.context.getState(getPositions=True).getPositions()
    PDBFile.writeFile(simulation.topology, positions, open(pdb_file, "w"))
    logger.info("Equilibration done. RST: %s, PDB: %s", rst_file, pdb_file)

    return {"dcd": dcd_file, "log": log_file, "rst": rst_file, "pdb": pdb_file}


# ─────────────────────────────────────────────────────────────────────────────
# Production MD
# ─────────────────────────────────────────────────────────────────────────────

def run_production(
    top_path: str,
    crd_path: str,
    equil_rst: str,
    output_prefix: str,
    stride_time_ns: float = DEFAULT_SIM_TIME_NS,
    n_strides: int = 1,
    dt_fs: int = DEFAULT_DT_FS,
    temp_k: float = DEFAULT_TEMP_K,
    pressure_bar: float = DEFAULT_PRESSURE_BAR,
    savcrd_ps: int = DEFAULT_SAVCRD_PS,
    print_ps: int = DEFAULT_PRINT_PS,
    status_callback=None,
) -> dict:
    """
    Run NPT production MD in strides, resuming from XML state files.

    Parameters
    ----------
    top_path       : .prmtop file.
    crd_path       : .crd / .inpcrd file.
    equil_rst      : XML state file from equilibration.
    output_prefix  : Base path for all output files.
    stride_time_ns : Duration of each stride in ns.
    n_strides      : Total number of strides.
    dt_fs          : Integration timestep in fs.
    temp_k         : Temperature in K.
    pressure_bar   : Pressure in bar.
    savcrd_ps      : Trajectory write frequency (ps).
    print_ps       : Log write frequency (ps).
    status_callback: Optional callable(step: int, pct: int) for progress updates.

    Returns
    -------
    dict with key "dcd_files" (list of per-stride DCD paths) and "rst_files".
    """
    stride_time_ps = float(stride_time_ns) * 1000
    dt        = int(dt_fs) * femtosecond
    temp      = float(temp_k) * kelvin
    pres      = float(pressure_bar) * bar
    sav_freq  = int(savcrd_ps) * picosecond
    prnt_freq = int(print_ps) * picosecond

    nsteps  = int(stride_time_ps / dt.value_in_unit(picosecond))
    nsavcrd = int(sav_freq.value_in_unit(picosecond)  / dt.value_in_unit(picosecond))
    nprint  = int(prnt_freq.value_in_unit(picosecond) / dt.value_in_unit(picosecond))

    logger.info(
        "Production: %d × %.1f ns, T=%.0f K, P=%.1f bar",
        n_strides, stride_time_ns, temp_k, pressure_bar,
    )

    # ── Build system once ─────────────────────────────────────────────────────
    prmtop = AmberPrmtopFile(top_path)
    inpcrd = AmberInpcrdFile(crd_path)

    system = prmtop.createSystem(
        nonbondedMethod=PME,
        nonbondedCutoff=1.0 * nanometers,
        ewaldErrorTolerance=0.0005,
        constraints=HBonds,
        rigidWater=True,
    )
    system.addForce(mm.MonteCarloBarostat(pres, temp))

    friction = 1.0
    integrator = mm.LangevinIntegrator(temp, friction, dt)
    integrator.setConstraintTolerance(1e-6)

    platform = _get_platform()
    simulation = Simulation(
        prmtop.topology, system, integrator, platform, _platform_properties(platform)
    )
    simulation.context.setPositions(inpcrd.positions)
    if inpcrd.boxVectors is not None:
        simulation.context.setPeriodicBoxVectors(*inpcrd.boxVectors)

    dcd_files, rst_files, pdb_files = [], [], []

    for n in range(1, n_strides + 1):
        dcd_file = f"{output_prefix}_{n}.dcd"
        log_file = f"{output_prefix}_{n}.log"
        rst_file = f"{output_prefix}_{n}.rst"
        pdb_file = f"{output_prefix}_{n}.pdb"
        prv_rst  = f"{output_prefix}_{n-1}.rst"

        # ── Resume from previous state ────────────────────────────────────────
        if os.path.exists(rst_file):
            logger.info("Stride #%d already done (%s present). Skipping.", n, rst_file)
            dcd_files.append(dcd_file)
            rst_files.append(rst_file)
            continue

        if n == 1:
            rst_source = equil_rst
        else:
            rst_source = prv_rst

        logger.info("Stride #%d: loading state from %s", n, rst_source)
        with open(rst_source, "r") as fh:
            simulation.context.setState(XmlSerializer.deserialize(fh.read()))

        currstep = int((n - 1) * nsteps)
        currtime = currstep * dt.value_in_unit(picosecond) * picosecond
        simulation.currentStep = currstep
        simulation.context.setTime(currtime)

        # ── Reporters ─────────────────────────────────────────────────────────
        dcd = DCDReporter(dcd_file, nsavcrd)
        dcd._dcd = dcd._dcd.__class__(
            dcd._out, simulation.topology, simulation.integrator.getStepSize(),
            currstep + nsavcrd, nsavcrd,
        )
        simulation.reporters.append(dcd)
        simulation.reporters.append(
            StateDataReporter(log_file, nprint, step=True, kineticEnergy=True,
                              potentialEnergy=True, totalEnergy=True, temperature=True,
                              volume=True, speed=True)
        )

        # ── Step ──────────────────────────────────────────────────────────────
        logger.info("Stride #%d: running %d steps...", n, nsteps)
        simulation.step(nsteps)
        simulation.reporters.clear()

        # ── Save state ────────────────────────────────────────────────────────
        state = simulation.context.getState(getPositions=True, getVelocities=True)
        with open(rst_file, "w") as fh:
            fh.write(XmlSerializer.serialize(state))

        positions = simulation.context.getState(getPositions=True).getPositions()
        PDBFile.writeFile(simulation.topology, positions, open(pdb_file, "w"))
        logger.info("Stride #%d complete. RST: %s", n, rst_file)

        dcd_files.append(dcd_file)
        rst_files.append(rst_file)
        pdb_files.append(pdb_file)

        if status_callback:
            pct = int(n / n_strides * 100)
            status_callback(n, pct)

    return {
        "dcd_files": dcd_files,
        "rst_files": rst_files,
        "pdb_files": pdb_files,
    }

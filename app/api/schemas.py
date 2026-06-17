"""
schemas.py — Request/response dataclasses for the MD Simulation API.

Using Python dataclasses (stdlib) to keep the project free of Pydantic as a
hard dependency while still providing typed, validated request objects.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SimulationRequest:
    """
    Parameters submitted to the /process endpoint.

    All fields have sensible defaults so callers only need to supply the
    protein and ligand files plus anything they want to customise.
    """
    # ── Input files (required — filenames saved server-side) ────────────────
    protein_filename: str = ""
    ligand_filename:  str = ""

    # ── Force field ──────────────────────────────────────────────────────────
    force_field:  str   = "ff19SB"   # ff19SB | ff14SB
    net_charge:   int   = 0          # ligand net formal charge

    # ── Box & solvation ──────────────────────────────────────────────────────
    box_size:     float = 12.0       # Angstrom
    ion_type:     str   = "NaCl"     # NaCl | KCl
    salt_conc:    float = 0.15       # Molar

    # ── Protein/ligand prep ──────────────────────────────────────────────────
    remove_waters:  bool = True
    add_hydrogens:  bool = True

    # ── Equilibration ────────────────────────────────────────────────────────
    equil_time_ns:  float = 5.0
    restraint_fc:   float = 700.0    # kJ/mol
    min_steps:      int   = 20000

    # ── Production ───────────────────────────────────────────────────────────
    sim_time_ns:    float = 0.1      # per stride
    n_strides:      int   = 1

    # ── Common MD ────────────────────────────────────────────────────────────
    temperature_k:  float = 298.0
    pressure_bar:   float = 1.0
    dt_fs:          int   = 2        # femtoseconds
    savcrd_ps:      int   = 10       # picoseconds
    print_ps:       int   = 10       # picoseconds

    @classmethod
    def from_form(cls, form: dict) -> "SimulationRequest":
        """Build a SimulationRequest from a Flask request.form dict."""
        def _bool(key, default):
            val = form.get(key, str(default)).lower()
            return val in ("yes", "true", "1")

        return cls(
            force_field    = form.get("force_field",    "ff19SB"),
            net_charge     = int(form.get("net_charge",     0)),
            box_size       = float(form.get("box_size",    12.0)),
            ion_type       = form.get("ion_type",       "NaCl"),
            salt_conc      = float(form.get("salt_conc",   0.15)),
            remove_waters  = _bool("remove_waters", True),
            add_hydrogens  = _bool("add_hydrogens", True),
            equil_time_ns  = float(form.get("equil_time_ns",  5.0)),
            restraint_fc   = float(form.get("restraint_fc",  700.0)),
            min_steps      = int(form.get("min_steps",   20000)),
            sim_time_ns    = float(form.get("sim_time_ns",   0.1)),
            n_strides      = int(form.get("n_strides",      1)),
            temperature_k  = float(form.get("temperature_k", 298.0)),
            pressure_bar   = float(form.get("pressure_bar",   1.0)),
            dt_fs          = int(form.get("dt_fs",            2)),
            savcrd_ps      = int(form.get("savcrd_ps",       10)),
            print_ps       = int(form.get("print_ps",        10)),
        )


@dataclass
class AnalysisRequest:
    """Parameters for the /analyze endpoint."""
    job_id:       str   = ""
    rmsd_mask:    str   = "@CA"
    cc_mask:      str   = "@CA"
    skip:         int   = 1
    dpi:          int   = 300
    threshold:    float = 0.3        # ProLIF threshold

    @classmethod
    def from_json(cls, data: dict) -> "AnalysisRequest":
        return cls(
            job_id    = data.get("job_id",    ""),
            rmsd_mask = data.get("rmsd_mask", "@CA"),
            cc_mask   = data.get("cc_mask",   "@CA"),
            skip      = int(data.get("skip",   1)),
            dpi       = int(data.get("dpi",  300)),
            threshold = float(data.get("threshold", 0.3)),
        )

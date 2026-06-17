"""
config.py — Central configuration for the MD Simulation system.

All paths, defaults, and binary locations are resolved here so that
every other module simply imports from this file.
"""

import os
import shutil

# ─── Directories ──────────────────────────────────────────────────────────────

# Root data directory — override via MD_DATA_DIR env variable
BASE_DATA_DIR: str = os.environ.get(
    "MD_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
)
os.makedirs(BASE_DATA_DIR, exist_ok=True)

# ─── Flask ────────────────────────────────────────────────────────────────────

FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.environ.get("FLASK_PORT", 5005))
FLASK_DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# ─── Simulation defaults ──────────────────────────────────────────────────────

DEFAULT_FORCE_FIELD: str = "ff19SB"   # ff19SB | ff14SB
DEFAULT_WATER_MODEL: str = "TIP3P"    # TIP3P | OPC
DEFAULT_BOX_SIZE: float = 12.0        # Angstrom
DEFAULT_SALT_CONC: float = 0.15       # Molar
DEFAULT_ION_TYPE: str = "NaCl"        # NaCl | KCl
DEFAULT_SIM_TIME_NS: float = 0.1      # nanoseconds
DEFAULT_EQUIL_TIME_NS: float = 5.0    # nanoseconds
DEFAULT_TEMP_K: float = 298.0         # Kelvin
DEFAULT_PRESSURE_BAR: float = 1.0     # Bar
DEFAULT_DT_FS: int = 2                # femtoseconds
DEFAULT_SAVCRD_PS: int = 10           # picoseconds
DEFAULT_PRINT_PS: int = 10            # picoseconds
DEFAULT_RESTRAINT_FC: int = 700       # kJ/mol
DEFAULT_MIN_STEPS: int = 20000

# Force field map: name → (leaprc_ff, leaprc_water, water_box_keyword)
FF_MAP: dict = {
    "ff19SB": ("leaprc.protein.ff19SB", "leaprc.water.opc",   "OPCBOX"),
    "ff14SB": ("leaprc.protein.ff14SB", "leaprc.water.tip3p", "TIP3PBOX"),
}

# ─── External tool binaries ───────────────────────────────────────────────────
# These are auto-detected from PATH; you can override via environment variables.

def _find_bin(name: str, env_var: str) -> str:
    """Return binary path from env var, PATH search, or common conda locations."""
    override = os.environ.get(env_var)
    if override and os.path.isfile(override):
        return override
    found = shutil.which(name)
    if found:
        return found
    # Common conda-forge install locations inside Docker/conda
    for prefix in ["/usr/local/bin", "/opt/conda/bin", "/opt/miniconda3/bin"]:
        candidate = os.path.join(prefix, name)
        if os.path.isfile(candidate):
            return candidate
    return name  # Fall back to bare name and let subprocess raise if missing

OBABEL_BIN:      str = _find_bin("obabel",      "OBABEL_BIN")
PDB4AMBER_BIN:   str = _find_bin("pdb4amber",   "PDB4AMBER_BIN")
ANTECHAMBER_BIN: str = _find_bin("antechamber", "ANTECHAMBER_BIN")
PARMCHK2_BIN:    str = _find_bin("parmchk2",    "PARMCHK2_BIN")
TLEAP_BIN:       str = _find_bin("tleap",       "TLEAP_BIN")
CPPTRAJ_BIN:     str = _find_bin("cpptraj",     "CPPTRAJ_BIN")

# ─── OpenMM Platform ──────────────────────────────────────────────────────────
# AUTO → try CUDA first, then OpenCL, then CPU
OPENMM_PLATFORM: str = os.environ.get("OPENMM_PLATFORM", "AUTO")

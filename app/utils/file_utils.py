"""
file_utils.py — Path helpers, temporary file management, and ZIP packaging.
"""

import os
import zipfile
from pathlib import Path
from typing import List

from app.config import BASE_DATA_DIR


def job_dir(job_id: str) -> str:
    """Return (and create) the dedicated directory for a job."""
    path = os.path.join(BASE_DATA_DIR, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def job_path(job_id: str, filename: str) -> str:
    """Build an absolute path inside the job directory."""
    return os.path.join(job_dir(job_id), filename)


def pack_zip(job_id: str, files: List[str], zip_name: str = "Results.zip") -> str:
    """
    Zip *files* into a single archive inside the job directory.

    Parameters
    ----------
    job_id   : The job identifier (used to locate the job directory).
    files    : List of absolute file paths to include.
    zip_name : Name of the output ZIP file.

    Returns
    -------
    Absolute path of the created ZIP file.
    """
    zip_path = job_path(job_id, zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            if os.path.exists(fpath):
                zf.write(fpath, os.path.basename(fpath))
    return zip_path


def ensure_dir(path: str) -> str:
    """Create *path* (and parents) if it does not exist; return *path*."""
    os.makedirs(path, exist_ok=True)
    return path


def safe_read(path: str) -> str:
    """Read a text file and return its contents, or empty string on error."""
    try:
        with open(path, "r") as fh:
            return fh.read()
    except OSError:
        return ""

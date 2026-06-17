"""
job_manager.py — Thread-safe job registry and background executor.

Replaces the scattered global variables (job_registry, pipeline_status,
_status_lock, _executor) from the original notebook with a clean class.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional


class JobManager:
    """Thread-safe store for simulation job state."""

    def __init__(self, max_workers: int = 2) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    # ── Job creation ──────────────────────────────────────────────────────────

    def create_job(self) -> str:
        """Create a new job entry and return its unique ID."""
        job_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._jobs[job_id] = {
                "status": "Queued",
                "result": None,
                "error": None,
            }
        return job_id

    # ── Status management ─────────────────────────────────────────────────────

    def set_status(self, job_id: str, status: str) -> None:
        """Update status for a job (no-op if job_id is unknown)."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status

    def set_result(self, job_id: str, result: Dict[str, Any]) -> None:
        """Store result payload for a completed job."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["result"] = result
                self._jobs[job_id]["status"] = "Success: MD Pipeline Completed"

    def set_error(self, job_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = f"Failed: {error[:400]}"
                self._jobs[job_id]["error"] = error

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the job dict, or None if not found."""
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Return a snapshot of all jobs."""
        with self._lock:
            return {jid: dict(info) for jid, info in self._jobs.items()}

    # ── Background execution ──────────────────────────────────────────────────

    def submit(self, fn, *args, **kwargs):
        """Submit *fn* to the background thread pool and return a Future."""
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


# Module-level singleton used by all API routes
job_manager = JobManager(max_workers=2)

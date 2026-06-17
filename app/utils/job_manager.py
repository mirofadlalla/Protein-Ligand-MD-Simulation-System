"""
job_manager.py — Redis-backed job registry with in-memory fallback.

Provides a unified interface for storing, updating, and retrieving simulation
job states. Automatically falls back to local memory if Redis is unavailable.
"""

import json
import logging
import threading
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class JobManager:
    """Registry for simulation job state, supporting Redis or in-memory fallback."""

    def __init__(self, use_redis: bool = True) -> None:
        self.use_redis = use_redis
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._redis = None

        if self.use_redis:
            from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, USE_REDIS
            if not USE_REDIS:
                logger.info("Redis storage explicitly disabled via configuration.")
                self.use_redis = False
                return

            import redis
            try:
                self._redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=2.0,
                    socket_connect_timeout=2.0
                )
                # Test connection
                self._redis.ping()
                logger.info("Successfully connected to Redis for job state storage.")
            except Exception as exc:
                logger.warning(
                    "Failed to connect to Redis: %s. "
                    "Falling back to thread-safe in-memory job registry.",
                    exc
                )
                self.use_redis = False
                self._redis = None

    def _job_key(self, job_id: str) -> str:
        return f"job:{job_id}"

    # ── Job creation ──────────────────────────────────────────────────────────

    def create_job(self) -> str:
        """Create a new job entry and return its unique ID."""
        job_id = str(uuid.uuid4())[:8]
        job_data = {
            "status": "Queued",
            "result": None,
            "error": None,
        }
        if self.use_redis and self._redis:
            self._redis.set(self._job_key(job_id), json.dumps(job_data))
        else:
            with self._lock:
                self._jobs[job_id] = job_data
        return job_id

    # ── Status management ─────────────────────────────────────────────────────

    def set_status(self, job_id: str, status: str) -> None:
        """Update status for a job (no-op if job_id is unknown)."""
        if self.use_redis and self._redis:
            key = self._job_key(job_id)
            raw = self._redis.get(key)
            if raw:
                job_data = json.loads(raw)
                job_data["status"] = status
                self._redis.set(key, json.dumps(job_data))
        else:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = status

    def set_result(self, job_id: str, result: Dict[str, Any]) -> None:
        """Store result payload for a completed job."""
        if self.use_redis and self._redis:
            key = self._job_key(job_id)
            raw = self._redis.get(key)
            if raw:
                job_data = json.loads(raw)
                job_data["result"] = result
                job_data["status"] = "Success: MD Pipeline Completed"
                self._redis.set(key, json.dumps(job_data))
        else:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["result"] = result
                    self._jobs[job_id]["status"] = "Success: MD Pipeline Completed"

    def set_error(self, job_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        if self.use_redis and self._redis:
            key = self._job_key(job_id)
            raw = self._redis.get(key)
            if raw:
                job_data = json.loads(raw)
                job_data["status"] = f"Failed: {error[:400]}"
                job_data["error"] = error
                self._redis.set(key, json.dumps(job_data))
        else:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = f"Failed: {error[:400]}"
                    self._jobs[job_id]["error"] = error

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the job dict, or None if not found."""
        if self.use_redis and self._redis:
            raw = self._redis.get(self._job_key(job_id))
            if raw:
                return json.loads(raw)
            return None
        else:
            with self._lock:
                job = self._jobs.get(job_id)
                return dict(job) if job else None

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Return a snapshot of all jobs."""
        if self.use_redis and self._redis:
            jobs = {}
            for key in self._redis.scan_iter(match="job:*"):
                job_id = key.split(":", 1)[1]
                raw = self._redis.get(key)
                if raw:
                    jobs[job_id] = json.loads(raw)
            return jobs
        else:
            with self._lock:
                return {jid: dict(info) for jid, info in self._jobs.items()}

    # ── Cleaning (for testing) ────────────────────────────────────────────────

    def clear_all(self) -> None:
        """Clear all job records."""
        if self.use_redis and self._redis:
            for key in self._redis.scan_iter(match="job:*"):
                self._redis.delete(key)
        else:
            with self._lock:
                self._jobs.clear()

    # ── Legacy/Fallback background execution ──────────────────────────────────

    def submit(self, fn, *args, **kwargs):
        """Submit *fn* to the background thread pool and return a Future."""
        if not hasattr(self, "_executor"):
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=2)
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True) -> None:
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=wait)


# Module-level singleton used by all API routes
job_manager = JobManager(use_redis=True)

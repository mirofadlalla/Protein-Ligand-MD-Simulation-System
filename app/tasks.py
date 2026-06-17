"""
tasks.py — Celery tasks for the MD simulation pipeline.
"""

from app.celery_app import celery_app
from app.pipeline.orchestrator import run_full_pipeline
from app.api.schemas import SimulationRequest

@celery_app.task(name="tasks.run_full_pipeline_task")
def run_full_pipeline_task(job_id: str, req_dict: dict) -> None:
    """
    Celery task wrapper around the main run_full_pipeline function.
    Reconstructs the SimulationRequest dataclass from the serialized dictionary.
    """
    req = SimulationRequest(**req_dict)
    run_full_pipeline(job_id, req)

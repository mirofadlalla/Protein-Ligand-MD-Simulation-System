"""
routes.py — All Flask API endpoints.

Endpoints
---------
POST /process           Upload PDB files + parameters → start pipeline → job_id
GET  /status/<job_id>   Poll job status and result
GET  /download/<job_id> Download simulation results ZIP
POST /analyze           Run post-simulation analysis on a completed job
GET  /download_analysis/<job_id> Download analysis ZIP
GET  /health            Liveness probe
"""

import logging
import os

from flask import Blueprint, app, jsonify, make_response, request, send_file, render_template

from app.api.schemas import AnalysisRequest, SimulationRequest
from app.pipeline.orchestrator import run_full_pipeline
from app.utils.file_utils import job_path, pack_zip, job_dir
from app.utils.job_manager import job_manager

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Root route & Dashboard
# ─────────────────────────────────────────────────────────────────────────────

# @bp.route("/", methods=["GET"])
# def index():
#     return render_template("index.html")

@bp.route("/")
def index():
    return {"status": "ok"}, 200

# ─────────────────────────────────────────────────────────────────────────────
# Middleware helpers
# ─────────────────────────────────────────────────────────────────────────────

@bp.after_request
def _add_headers(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /process — Start a new simulation job
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/process", methods=["POST", "OPTIONS"])
def process():
    if request.method == "OPTIONS":
        return make_response("", 200)

    # ── Validate uploaded files ───────────────────────────────────────────────
    if "protein" not in request.files or "ligand" not in request.files:
        return jsonify({"error": "Both 'protein' and 'ligand' PDB files are required."}), 400

    prot_file = request.files["protein"]
    lig_file  = request.files["ligand"]

    if not prot_file.filename or not lig_file.filename:
        return jsonify({"error": "File names must not be empty."}), 400

    # ── Parse simulation parameters ───────────────────────────────────────────
    sim_req = SimulationRequest.from_form(request.form)

    # ── Create job & save uploads ─────────────────────────────────────────────
    job_id = job_manager.create_job()
    work   = job_dir(job_id)

    prot_fname = f"{job_id}_input_protein.pdb"
    lig_fname  = f"{job_id}_input_ligand.pdb"
    prot_file.save(os.path.join(work, prot_fname))
    lig_file.save(os.path.join(work, lig_fname))

    sim_req.protein_filename = prot_fname
    sim_req.ligand_filename  = lig_fname

    # ── Submit to background executor ─────────────────────────────────────────
    job_manager.submit(run_full_pipeline, job_id, sim_req)

    logger.info("Job %s queued.", job_id)
    return jsonify({"job_id": job_id, "status": "Queued"}), 202


# ─────────────────────────────────────────────────────────────────────────────
# GET /status/<job_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/status/<job_id>", methods=["GET"])
def get_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404

    response = {
        "job_id": job_id,
        "status": job.get("status", "Unknown"),
    }

    # Include download URL once finished
    result = job.get("result")
    if result:
        response["download_url"]          = f"/download/{job_id}"
        response["download_analysis_url"] = f"/download_analysis/{job_id}"
        if "pdb_content" in result:
            response["pdb_content"] = result["pdb_content"]

    return jsonify(response), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /download/<job_id> — Download simulation results ZIP
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/download/<job_id>", methods=["GET"])
def download_results(job_id: str):
    zip_path = job_path(job_id, "Results.zip")
    if not os.path.exists(zip_path):
        return jsonify({"error": "Results not ready or job not found."}), 404
    return send_file(zip_path, as_attachment=True, download_name=f"{job_id}_Results.zip")


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyze — Run post-simulation analysis
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/analyze", methods=["POST"])
def analyze():
    data    = request.get_json(force=True, silent=True) or {}
    ana_req = AnalysisRequest.from_json(data)

    if not ana_req.job_id:
        return jsonify({"error": "job_id is required."}), 400

    # Lazy import to keep the module fast when analysis isn't needed
    from app.pipeline.analyze import run_standard_analysis

    job = job_manager.get_job(ana_req.job_id)
    work = job_dir(ana_req.job_id)
    if not job or not job.get("result"):
        return jsonify({"error": "Simulation results not found. Has the job completed?"}), 404

    result = job["result"]
    top_path = result.get("top")
    dcd_paths = result.get("dcd_files")

    if not top_path or not dcd_paths:
        return jsonify({"error": "Simulation files not found in job results."}), 404

    # Verify that the files exist on the filesystem
    if not os.path.exists(top_path) or not any(os.path.exists(p) for p in dcd_paths):
        return jsonify({"error": "Simulation files not found on disk."}), 404

    try:
        results = run_standard_analysis(
            job_id=ana_req.job_id,
            top_path=top_path,
            traj_path=dcd_paths,
            work_dir=work,
            skip=ana_req.skip,
            dpi=ana_req.dpi,
        )
    except Exception as exc:
        logger.error("Analysis failed for job %s: %s", ana_req.job_id, exc)
        return jsonify({"error": str(exc)}), 500

    # Package analysis outputs into a ZIP
    output_files = list(results.values())
    analysis_zip = pack_zip(ana_req.job_id, output_files, zip_name="Analysis.zip")

    return jsonify({
        "job_id":      ana_req.job_id,
        "download_url": f"/download_analysis/{ana_req.job_id}",
        "outputs":     list(results.keys()),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /download_analysis/<job_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/download_analysis/<job_id>", methods=["GET"])
def download_analysis(job_id: str):
    zip_path = job_path(job_id, "Analysis.zip")
    if not os.path.exists(zip_path):
        return jsonify({"error": "Analysis results not found."}), 404
    return send_file(zip_path, as_attachment=True, download_name=f"{job_id}_Analysis.zip")

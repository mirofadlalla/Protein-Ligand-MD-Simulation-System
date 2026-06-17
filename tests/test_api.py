import io
import os
import shutil
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask
from app.main import create_app
from app.utils.job_manager import job_manager
from app.utils.file_utils import job_dir, job_path


class TestMDAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def tearDown(self) -> None:
        # Clear the jobs registry between tests
        with job_manager._lock:
            job_manager._jobs.clear()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_index(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html_content = response.get_data(as_text=True)
        self.assertIn("MD Simulation Studio", html_content)
        self.assertIn("Backend API Connection", html_content)

    def test_process_missing_files(self) -> None:
        response = self.client.post("/process", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Both 'protein' and 'ligand' PDB files are required.", response.get_json()["error"])

    @patch("app.utils.job_manager.JobManager.submit")
    def test_process_success(self, mock_submit: MagicMock) -> None:
        data = {
            "protein": (io.BytesIO(b"ATOM      1  N   ALA A   1\n"), "protein.pdb"),
            "ligand": (io.BytesIO(b"ATOM      1  C1  LIG A   1\n"), "ligand.pdb"),
            "force_field": "ff19SB",
            "sim_time_ns": "0.1",
        }
        response = self.client.post("/process", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 202)
        res_json = response.get_json()
        self.assertIn("job_id", res_json)
        self.assertEqual(res_json["status"], "Queued")

        # Verify job exists in manager and background task was submitted
        job_id = res_json["job_id"]
        job = job_manager.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "Queued")
        mock_submit.assert_called_once()

        # Clean up created job directory
        shutil.rmtree(job_dir(job_id), ignore_errors=True)

    def test_status_not_found(self) -> None:
        response = self.client.get("/status/nonexistent")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Job not found."})

    def test_status_queued(self) -> None:
        job_id = job_manager.create_job()
        response = self.client.get(f"/status/{job_id}")
        self.assertEqual(response.status_code, 200)
        res_json = response.get_json()
        self.assertEqual(res_json["job_id"], job_id)
        self.assertEqual(res_json["status"], "Queued")

    def test_status_success(self) -> None:
        job_id = job_manager.create_job()
        job_manager.set_result(job_id, {
            "zip_file": "/app/data/test/Results.zip",
            "top": "/app/data/test/SYS.prmtop",
            "crd": "/app/data/test/SYS.crd",
            "pdb_content": "PDB DUMMY CONTENT",
        })
        response = self.client.get(f"/status/{job_id}")
        self.assertEqual(response.status_code, 200)
        res_json = response.get_json()
        self.assertEqual(res_json["job_id"], job_id)
        self.assertIn("Success", res_json["status"])
        self.assertEqual(res_json["download_url"], f"/download/{job_id}")
        self.assertEqual(res_json["download_analysis_url"], f"/download_analysis/{job_id}")
        self.assertEqual(res_json["pdb_content"], "PDB DUMMY CONTENT")

    def test_download_not_found(self) -> None:
        response = self.client.get("/download/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_download_success(self) -> None:
        job_id = job_manager.create_job()
        work = job_dir(job_id)
        zip_path = job_path(job_id, "Results.zip")
        with open(zip_path, "w") as f:
            f.write("mock zip file content")

        response = self.client.get(f"/download/{job_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/zip")
        self.assertEqual(response.headers["Content-Disposition"], f"attachment; filename={job_id}_Results.zip")

        # Clean up
        shutil.rmtree(work, ignore_errors=True)

    @patch("app.pipeline.analyze.run_standard_analysis")
    def test_analyze_success(self, mock_run_analysis: MagicMock) -> None:
        mock_run_analysis.return_value = {
            "rmsd": "/app/data/test/test_rmsd.png",
            "prolif": "/app/data/test/test_prolif.html"
        }

        job_id = job_manager.create_job()
        work = job_dir(job_id)
        
        # Mock file system requirements
        top_path = job_path(job_id, f"{job_id}_SYS.prmtop")
        dcd_path = job_path(job_id, f"{job_id}_prod_1.dcd")
        with open(top_path, "w") as f: f.write("top")
        with open(dcd_path, "w") as f: f.write("dcd")

        job_manager.set_result(job_id, {
            "zip_file": "/app/data/test/Results.zip",
            "top": top_path,
            "crd": "/app/data/test/SYS.crd",
            "dcd_files": [dcd_path],
        })

        response = self.client.post("/analyze", json={"job_id": job_id})
        self.assertEqual(response.status_code, 200)
        res_json = response.get_json()
        self.assertEqual(res_json["job_id"], job_id)
        self.assertEqual(res_json["download_url"], f"/download_analysis/{job_id}")

        # Clean up
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

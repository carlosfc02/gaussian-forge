from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "web" / "backend"))

import run_full_pipeline
from app.services.pipeline_service import choose_log_stage
from pipeline_manifest import write_json


class FakeProcess:
    def __init__(self, lines: list[str], return_code: int = 0) -> None:
        self.stdout = iter(lines)
        self.return_code = return_code

    def wait(self) -> int:
        return self.return_code


class PipelineLiveLogTests(unittest.TestCase):
    def test_run_stage_publishes_running_manifest_before_process_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            log_dir = Path(temporary_dir)
            manifest = {
                "status": "running",
                "stages": [
                    {"stage": "segment_video", "status": "success", "log_path": str(log_dir / "segment_video.log")}
                ],
            }

            def inspect_transition(command: list[str], log_path: Path) -> str:
                persisted = json.loads((log_dir / "full_pipeline_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(persisted["stages"][-1]["stage"], "prepare_3dgs_dataset")
                self.assertEqual(persisted["stages"][-1]["status"], "running")
                self.assertTrue(log_path.exists())
                return "stage output\n"

            with mock.patch.object(run_full_pipeline, "run_logged", side_effect=inspect_transition):
                output = run_full_pipeline.run_stage(
                    [sys.executable, "-c", "print('unused')"],
                    "prepare_3dgs_dataset",
                    log_dir,
                    manifest,
                )

            self.assertEqual(output, "stage output\n")
            persisted = json.loads((log_dir / "full_pipeline_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["stages"][-1]["status"], "success")

    def test_run_logged_writes_command_before_streamed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            log_path = Path(temporary_dir) / "train_3dgs.log"
            fake_process = FakeProcess(["first line\n", "second line\n"])
            with mock.patch.object(run_full_pipeline.subprocess, "Popen", return_value=fake_process):
                output = run_full_pipeline.run_logged(["python", "train.py", "--iterations", "10"], log_path)

            content = log_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("[cmd] python train.py --iterations 10\n"))
            self.assertIn("first line\nsecond line\n", content)
            self.assertEqual(output, "first line\nsecond line\n")

    def test_backend_prefers_new_running_stage_over_previous_success(self) -> None:
        previous = {"stage": "segment_video", "status": "success", "log_path": "segment_video.log"}
        active = {"stage": "prepare_3dgs_dataset", "status": "running", "log_path": "prepare_3dgs_dataset.log"}
        manifest = {"stages": [previous, active]}

        self.assertIs(choose_log_stage(manifest, None), active)
        self.assertIs(choose_log_stage(manifest, "segment_video"), previous)

    def test_atomic_json_writes_never_expose_partial_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "manifest.json"
            write_json(path, {"sequence": 0, "payload": "initial"})
            stop = threading.Event()
            errors: list[Exception] = []

            def reader() -> None:
                while not stop.is_set():
                    try:
                        json.loads(path.read_text(encoding="utf-8"))
                    except Exception as exc:  # pragma: no cover - assertion reports the concrete exception
                        errors.append(exc)
                        stop.set()

            thread = threading.Thread(target=reader)
            thread.start()
            try:
                for sequence in range(100):
                    write_json(path, {"sequence": sequence, "payload": "x" * 2000})
            finally:
                stop.set()
                thread.join(timeout=5)

            self.assertEqual(errors, [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["sequence"], 99)

    def test_dn_consistency_metrics_use_official_density_artifact_name(self) -> None:
        params = {
            "surface_level": "0.3",
            "n_vertices_in_mesh": "1000000",
            "gaussians_per_triangle": "1",
            "refinement_iterations": "15000",
        }

        refined_dir = run_full_pipeline.expected_refined_sugar_dir(
            Path("sugar_output") / "bagels",
            "source",
            "dn_consistency",
            params,
        )

        self.assertIn("densityestim02_sdfnorm02", refined_dir.as_posix())
        self.assertNotIn("dn_consistencyestim", refined_dir.as_posix())

    def test_sugar_metrics_regularization_maps_dn_consistency_to_density(self) -> None:
        self.assertEqual(run_full_pipeline.sugar_metrics_regularization_type("dn_consistency"), "density")
        self.assertEqual(run_full_pipeline.sugar_metrics_regularization_type("sdf"), "sdf")


if __name__ == "__main__":
    unittest.main()

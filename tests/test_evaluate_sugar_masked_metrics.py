from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_sugar_masked_metrics as masked_sugar


SUGAR_STEM = "sugarfine_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000_normalconsistency01_gaussperface1"
MESH_STEM = "sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000"


class MaskedSugarMetricsTests(unittest.TestCase):
    def test_latest_refined_sugar_ply_selects_newest_scene_match(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            old_ply = data_root / "sugar_output" / "mario" / "refined_ply" / "source" / "old.ply"
            new_ply = data_root / "sugar_output" / "mario_20260628" / "refined_ply" / "source" / "new.ply"
            old_ply.parent.mkdir(parents=True)
            new_ply.parent.mkdir(parents=True)
            old_ply.write_text("old", encoding="utf-8")
            new_ply.write_text("new", encoding="utf-8")
            os.utime(old_ply, (1, 1))
            os.utime(new_ply, (2, 2))

            self.assertEqual(masked_sugar.latest_refined_sugar_ply(data_root, "mario"), new_ply)

    def test_resolve_sugar_artifacts_selects_latest_checkpoint_and_matching_mesh(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scene_output = Path(temporary_directory) / "sugar_output" / "bagels"
            sugar_ply = scene_output / "refined_ply" / "source" / f"{SUGAR_STEM}.ply"
            refined_dir = scene_output / "refined" / "source" / SUGAR_STEM
            coarse_mesh = scene_output / "coarse_mesh" / "source" / f"{MESH_STEM}.ply"
            sugar_ply.parent.mkdir(parents=True)
            refined_dir.mkdir(parents=True)
            coarse_mesh.parent.mkdir(parents=True)
            sugar_ply.write_text("ply", encoding="utf-8")
            (refined_dir / "7000.pt").write_text("7k", encoding="utf-8")
            expected_checkpoint = refined_dir / "15000.pt"
            expected_checkpoint.write_text("15k", encoding="utf-8")
            coarse_mesh.write_text("mesh", encoding="utf-8")

            checkpoint, mesh = masked_sugar.resolve_sugar_artifacts(sugar_ply)

            self.assertEqual(checkpoint, expected_checkpoint)
            self.assertEqual(mesh, coarse_mesh)

    def test_build_sugar_metrics_command_uses_sugar_container_and_official_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "data"
            scene_dir = data_root / "3dgs" / "bagels"
            source_dir = scene_dir / "gs" / "source"
            base_model_dir = scene_dir / "gs" / "model"
            output_dir = scene_dir / "metrics" / "masked_sugar"
            render_dir = output_dir / "renders"
            sugar_ply = data_root / "sugar_output" / "bagels" / "refined_ply" / "source" / f"{SUGAR_STEM}.ply"
            checkpoint = data_root / "sugar_output" / "bagels" / "refined" / "source" / SUGAR_STEM / "15000.pt"
            coarse_mesh = data_root / "sugar_output" / "bagels" / "coarse_mesh" / "source" / f"{MESH_STEM}.ply"
            for path in (source_dir, base_model_dir, output_dir, render_dir, sugar_ply.parent, checkpoint.parent, coarse_mesh.parent):
                path.mkdir(parents=True, exist_ok=True)
            args = argparse.Namespace(split="test", masks_dir="masks", crop_padding=8, white_background=True)

            command = masked_sugar.build_sugar_metrics_command(
                args,
                data_root,
                scene_dir,
                source_dir,
                base_model_dir,
                output_dir,
                sugar_ply,
                checkpoint,
                coarse_mesh,
                render_dir,
            )

            self.assertIn("sugar", command)
            self.assertIn("/app/scripts/evaluate_sugar_masked_metrics.py", command)
            self.assertIn("--inside-container", command)
            self.assertIn("--refined-checkpoint", command)
            self.assertIn("/data/sugar_output/bagels/refined/source/" + SUGAR_STEM + "/15000.pt", command)
            self.assertIn("--coarse-mesh", command)
            self.assertNotIn("evaluate_3dgs_masked_metrics.py", " ".join(command))
            self.assertIn("--white-background", command)

    def test_render_file_name_adds_png_for_extensionless_camera_names(self):
        self.assertEqual(masked_sugar.render_file_name("000001"), "000001.png")
        self.assertEqual(masked_sugar.render_file_name("frames/000001.jpg"), "000001.jpg")

    def test_write_report_records_official_sugar_input_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "metrics" / "masked_sugar"
            report = {
                "status": "success",
                "input_paths": {
                    "sugar_ply": "/data/sugar_output/bagels/refined_ply/source/model.ply",
                    "refined_checkpoint": "/data/sugar_output/bagels/refined/source/model/15000.pt",
                    "coarse_mesh": "/data/sugar_output/bagels/coarse_mesh/source/sugarmesh_model.ply",
                    "base_model_dir": "/data/3dgs/bagels/gs/model",
                    "render_dir": "/data/3dgs/bagels/metrics/masked_sugar/renders",
                },
                "metrics": {"preferred_split": "test", "splits": {}},
                "frames": [],
            }

            report_path = masked_sugar.write_report(output_dir, report)
            latest = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))

            self.assertTrue(report_path.is_file())
            self.assertEqual(latest["input_paths"]["sugar_ply"], report["input_paths"]["sugar_ply"])
            self.assertEqual(latest["input_paths"]["refined_checkpoint"], report["input_paths"]["refined_checkpoint"])
            self.assertEqual(latest["input_paths"]["coarse_mesh"], report["input_paths"]["coarse_mesh"])
            self.assertEqual(latest["input_paths"]["render_dir"], report["input_paths"]["render_dir"])

    def test_aggregate_split_keeps_masked_sugar_report_shape(self):
        frames = [
            {
                "full_image": {"l1": 0.2, "psnr": 20.0, "ssim": 0.8, "lpips": 0.3},
                "masked_object": {"l1": 0.4, "psnr": 15.0, "ssim": 0.7, "lpips": 0.5},
                "mask_coverage": 0.2,
            },
            {
                "full_image": {"l1": 0.4, "psnr": 22.0, "ssim": 0.9, "lpips": 0.1},
                "masked_object": None,
                "mask_coverage": 0.0,
            },
        ]

        summary = masked_sugar.aggregate_split(frames)

        self.assertEqual(summary["frame_count"], 2)
        self.assertEqual(summary["masked_frame_count"], 1)
        self.assertAlmostEqual(summary["full_image"]["l1"], 0.3)
        self.assertAlmostEqual(summary["masked_object"]["psnr"], 15.0)


if __name__ == "__main__":
    unittest.main()

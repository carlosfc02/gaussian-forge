from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_3dgs_masked_metrics as masked_metrics


class Masked3dgsMetricsTests(unittest.TestCase):
    def test_latest_iteration_selects_highest_point_cloud(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_dir = Path(temporary_directory)
            for iteration in (1000, 7000, 30000):
                point_cloud_dir = model_dir / "point_cloud" / f"iteration_{iteration}"
                point_cloud_dir.mkdir(parents=True)
                (point_cloud_dir / "point_cloud.ply").write_text("ply", encoding="utf-8")

            self.assertEqual(masked_metrics.latest_iteration(model_dir), 30000)

    def test_aggregate_split_ignores_empty_masked_frames(self):
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

        summary = masked_metrics.aggregate_split(frames)

        self.assertEqual(summary["frame_count"], 2)
        self.assertEqual(summary["masked_frame_count"], 1)
        self.assertAlmostEqual(summary["full_image"]["l1"], 0.3)
        self.assertAlmostEqual(summary["masked_object"]["psnr"], 15.0)

    def test_find_mask_path_reports_missing_mask(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            (source_dir / "masks").mkdir()

            with self.assertRaises(FileNotFoundError) as error:
                masked_metrics.find_mask_path(source_dir, "masks", "000001.png")

            self.assertIn("000001.png", str(error.exception))

    def test_write_report_updates_latest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            report_path = masked_metrics.write_report(output_dir, {"status": "success"})

            self.assertTrue(report_path.is_file())
            self.assertEqual((output_dir / "latest.json").read_text(encoding="utf-8"), report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

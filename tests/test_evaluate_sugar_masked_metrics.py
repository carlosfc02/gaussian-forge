from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_sugar_masked_metrics as masked_sugar


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

    def test_prepare_eval_model_copies_refined_ply_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sugar_ply = root / "refined.ply"
            base_model = root / "model"
            eval_model = root / "eval"
            sugar_ply.write_text("ply", encoding="utf-8")
            base_model.mkdir()
            for filename in ("cfg_args", "cameras.json", "input.ply", "exposure.json"):
                (base_model / filename).write_text(filename, encoding="utf-8")

            masked_sugar.prepare_eval_model(sugar_ply, base_model, eval_model)

            self.assertEqual((eval_model / "point_cloud" / "iteration_0" / "point_cloud.ply").read_text(encoding="utf-8"), "ply")
            self.assertEqual((eval_model / "cfg_args").read_text(encoding="utf-8"), "cfg_args")
            self.assertEqual((eval_model / "cameras.json").read_text(encoding="utf-8"), "cameras.json")

    def test_prepare_eval_model_requires_cfg_args(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sugar_ply = root / "refined.ply"
            base_model = root / "model"
            sugar_ply.write_text("ply", encoding="utf-8")
            base_model.mkdir()

            with self.assertRaises(FileNotFoundError) as error:
                masked_sugar.prepare_eval_model(sugar_ply, base_model, root / "eval")

            self.assertIn("cfg_args", str(error.exception))

    def test_build_3dgs_metrics_command_uses_iteration_zero(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            scene_dir = data_root / "3dgs" / "mario"
            source_dir = scene_dir / "gs" / "source"
            eval_model = data_root / "sugar_output" / "eval" / "mario" / "refined"
            output_dir = scene_dir / "metrics" / "masked_sugar"
            for directory in (scene_dir, source_dir, eval_model, output_dir):
                directory.mkdir(parents=True)
            args = argparse.Namespace(split="test", masks_dir="masks", crop_padding=8, white_background=True)

            command = masked_sugar.build_3dgs_metrics_command(args, data_root, scene_dir, source_dir, eval_model, output_dir)

            self.assertIn("evaluate_3dgs_masked_metrics.py", " ".join(command))
            self.assertEqual(command[command.index("--iteration") + 1], "0")
            self.assertEqual(command[command.index("--output-dir") + 1], "3dgs/mario/metrics/masked_sugar")
            self.assertIn("--white-background", command)


if __name__ == "__main__":
    unittest.main()

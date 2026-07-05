from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_colmap_pipeline


class RunColmapPipelineTests(unittest.TestCase):
    def test_parse_last_integer_line_ignores_docker_banner_noise(self):
        output = """==========
== CUDA ==
==========

CUDA Version 12.4.1

84
Container gaussian-forge-colmap-run-abc Creating
 Container gaussian-forge-colmap-run-abc Created
"""

        self.assertEqual(run_colmap_pipeline.parse_last_integer_line(output), 84)


if __name__ == "__main__":
    unittest.main()
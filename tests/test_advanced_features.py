from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class AdvancedFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_for_and_match(self) -> None:
        env = self.pipeline.execute_file(ROOT / "examples" / "控制流增强.xy")
        self.assertEqual(env["合计"], 10)

    def test_optimizer_folds_constants(self) -> None:
        data = self.pipeline.optimized_ast_to_data(
            """
            令 值 = 2 + 3 * 4；
            若 真 {
                显("保留")；
            } 否则 {
                显("移除")；
            }
            """
        )
        self.assertEqual(data["statements"][0]["value"]["value"], 14)
        self.assertEqual(len(data["statements"]), 2)

    def test_ai_runtime_module(self) -> None:
        env = self.pipeline.execute_file(ROOT / "examples" / "ai核心.xy")
        self.assertEqual(env["c"].size(), 1)
        self.assertEqual(env["q8"].bits, 8)


if __name__ == "__main__":
    unittest.main()

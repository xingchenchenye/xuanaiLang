from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_inline_function_and_assert(self) -> None:
        env = self.pipeline.execute_source(
            """
            术 求和(a: 整, b: 整) -> 整 {
                返 a + b；
            }
            令 结果 = 求和(4, 5)；
            断 结果 == 9, "求和失败"；
            """,
            file_path=str(ROOT / "tests" / "inline.xy"),
        )
        self.assertEqual(env["结果"], 9)

    def test_tensor_and_stdlib(self) -> None:
        env = self.pipeline.execute_source(
            """
            引 标准.数学 为 数；
            令 x = 张([[1, 2], [3, 4]])；
            令 y = 张([[1, 0], [0, 1]])；
            令 z = x @ y；
            令 q = 量化4(z)；
            断 数.平方(3) == 9；
            """,
            file_path=str(ROOT / "tests" / "tensor.xy"),
        )
        self.assertEqual(env["数"].平方(5), 25)
        self.assertEqual(env["z"].shape, (2, 2))
        self.assertEqual(env["q"].bits, 4)

    def test_relative_module_import(self) -> None:
        env = self.pipeline.execute_file(ROOT / "examples" / "模块演示.xy")
        self.assertEqual(env["值"], 42)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class ErrorFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_error_example_runs_on_all_backends(self) -> None:
        file_path = ROOT / "examples" / "异常演示.xy"
        interp = self.pipeline.execute_file(file_path)
        python = self.pipeline.execute_file_python(file_path)
        vm = self.pipeline.execute_file_vm(file_path)
        for env in (interp, python, vm):
            self.assertEqual(env["正常"], 4)
            self.assertEqual(env["业务错"]["类型"], "业务异常")
            self.assertEqual(env["业务错"]["信息"], "除数不能为零")
            self.assertEqual(env["断言错"], "手动断言失败")
            self.assertEqual(env["运行错"]["类型"], "IndexError")

    def test_formatter_keeps_try_catch_canonical(self) -> None:
        source = '试{抛 "失败"；}捕 错{显(错)；}\n'
        formatted = self.pipeline.format_source(source)
        self.assertIn("试 {", formatted)
        self.assertIn("捕 错 {", formatted)
        self.assertIn('抛 "失败"；', formatted)

    def test_try_without_binding_is_supported(self) -> None:
        env = self.pipeline.execute_source(
            """
            令 标记 = 0；
            试 {
                抛 "失败"；
            } 捕 {
                标记 = 1；
            }
            """
        )
        self.assertEqual(env["标记"], 1)

    def test_disassembler_contains_try_and_throw(self) -> None:
        asm = self.pipeline.disassemble(
            """
            试 {
                抛 "失败"；
            } 捕 错 {
                显(错)；
            }
            """
        )
        self.assertIn("TRY 错", asm)
        self.assertIn("THROW", asm)


if __name__ == "__main__":
    unittest.main()

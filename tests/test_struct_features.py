from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.errors import XuanError
from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class StructFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_struct_example_runs_on_all_backends(self) -> None:
        file_path = ROOT / "examples" / "结构演示.xy"
        interp = self.pipeline.execute_file(file_path)
        python = self.pipeline.execute_file_python(file_path)
        vm = self.pipeline.execute_file_vm(file_path)
        for env in (interp, python, vm):
            self.assertEqual(env["核心"].名称, "玄言核")
            self.assertEqual(env["核心"].版本, 2)
            self.assertEqual(env["核心"].配置["后端"], "结构")

    def test_struct_symbol_table_and_annotation(self) -> None:
        table = self.pipeline.symbol_table(
            """
            构 引擎 {
                名称: 文,
                版本: 整
            }
            令 核心: 引擎 = 新 引擎 {名称: "玄言核", 版本: 1}；
            """
        )
        self.assertEqual(table["引擎"], "构型")
        self.assertEqual(table["核心"], "引擎")

    def test_struct_missing_field_is_rejected(self) -> None:
        source = """
        构 引擎 {
            名称: 文,
            版本: 整
        }
        令 核心 = 新 引擎 {名称: "玄言核"}；
        """
        with self.assertRaises(XuanError):
            self.pipeline.check(source)

    def test_formatter_keeps_struct_canonical(self) -> None:
        source = '构 引擎{名称:文,版本:整}\n令 核心:引擎=新 引擎{名称:"玄言核",版本:1}；\n'
        formatted = self.pipeline.format_source(source)
        self.assertIn("构 引擎 {", formatted)
        self.assertIn('令 核心: 引擎 = 新 引擎 {名称: "玄言核", 版本: 1}；', formatted)


if __name__ == "__main__":
    unittest.main()

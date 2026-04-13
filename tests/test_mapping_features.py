from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class MappingFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_mapping_example_runs_on_all_backends(self) -> None:
        file_path = ROOT / "examples" / "映射演示.xy"
        interp = self.pipeline.execute_file(file_path)
        python = self.pipeline.execute_file_python(file_path)
        vm = self.pipeline.execute_file_vm(file_path)
        for env in (interp, python, vm):
            self.assertEqual(env["用户"]["名称"], "玄言")
            self.assertEqual(env["用户"]["作者"], "开发者星尘_尘夜")
            self.assertEqual(env["用户"]["版本"], 6)
            self.assertEqual(env["用户"]["配置"]["后端"], "三栈")
            self.assertEqual(env["合并"]["阶段"], "左值赋值")

    def test_mapping_types_and_constant_lookup(self) -> None:
        table = self.pipeline.symbol_table('令 配置: 映[文, 整] = {"层": 7, "头": 8}；')
        self.assertEqual(table["配置"], "映[文, 整]")
        data = self.pipeline.optimized_ast_to_data('令 值 = {"层": 7, "头": 8}["头"]；')
        self.assertEqual(data["statements"][0]["value"]["value"], 8)

    def test_index_and_member_assignment(self) -> None:
        source = """
        令 用户: 映[文, 任意] = {"名称": "玄言", "配置": {"后端": "旧"}}；
        用户.作者 = "开发者星尘_尘夜"；
        用户["名称"] = "玄言二号"；
        用户.配置["后端"] = "vm"；
        """
        for runner in (
            self.pipeline.execute_source,
            self.pipeline.execute_source_python,
            self.pipeline.execute_source_vm,
        ):
            env = runner(source, file_path=str(ROOT / "tests" / "assign_target.xy"))
            self.assertEqual(env["用户"]["作者"], "开发者星尘_尘夜")
            self.assertEqual(env["用户"]["名称"], "玄言二号")
            self.assertEqual(env["用户"]["配置"]["后端"], "vm")

    def test_formatter_keeps_mapping_canonical(self) -> None:
        source = '令 用户={"名称":"玄言","版本":5}；\n用户.版本=6；\n'
        formatted = self.pipeline.format_source(source)
        self.assertIn('令 用户 = {"名称": "玄言", "版本": 5}；', formatted)
        self.assertIn('用户.版本 = 6；', formatted)


if __name__ == "__main__":
    unittest.main()

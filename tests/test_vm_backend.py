from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class VmBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_vm_backend_matches_existing_backends(self) -> None:
        source = """
        术 外层(x: 整) -> 整 {
            术 内层(y: 整) -> 整 {
                返 x + y；
            }
            返 内层(5)；
        }
        令 值 = 外层(7)；
        """
        interp = self.pipeline.execute_source(source, file_path=str(ROOT / "tests" / "closure_vm.xy"))
        python = self.pipeline.execute_source_python(source, file_path=str(ROOT / "tests" / "closure_vm.xy"))
        vm = self.pipeline.execute_source_vm(source, file_path=str(ROOT / "tests" / "closure_vm.xy"))
        self.assertEqual(interp["值"], 12)
        self.assertEqual(python["值"], 12)
        self.assertEqual(vm["值"], 12)
        self.assertEqual(interp["值"], vm["值"])
        self.assertEqual(python["值"], vm["值"])
        self.assertEqual(vm["__backend__"], "vm")

    def test_vm_backend_handles_modules_and_ai_runtime(self) -> None:
        module_env = self.pipeline.execute_file_vm(ROOT / "examples" / "模块演示.xy")
        ai_env = self.pipeline.execute_file_vm(ROOT / "examples" / "ai核心.xy")
        map_env = self.pipeline.execute_file_vm(ROOT / "examples" / "映射演示.xy")
        self.assertEqual(module_env["值"], 42)
        self.assertEqual(ai_env["c"].size(), 1)
        self.assertEqual(ai_env["q8"].bits, 8)
        self.assertEqual(map_env["用户"]["作者"], "开发者星尘_尘夜")

    def test_disassembler_contains_key_instructions(self) -> None:
        asm = self.pipeline.disassemble(
            """
            术 求和(a: 整, b: 整) -> 整 {
                返 a + b；
            }
            令 结果 = 求和(2, 3)；
            """
        )
        self.assertIn("FUNCTION 求和(a, b)", asm)
        self.assertIn("DECLARE 令 结果", asm)
        self.assertIn("CALL 2", asm)

    def test_disassembler_contains_complex_assign(self) -> None:
        asm = self.pipeline.disassemble(
            """
            令 用户 = {"名称": "玄言"}；
            用户.作者 = "星尘"；
            用户["名称"] = "玄言二号"；
            """
        )
        self.assertIn("ASSIGN .作者", asm)
        self.assertIn("ASSIGN []", asm)

    def test_disassembler_contains_struct(self) -> None:
        asm = self.pipeline.disassemble(
            """
            构 引擎 {
                名称: 文,
                版本: 整
            }
            令 核心 = 新 引擎 {名称: "玄言核", 版本: 1}；
            """
        )
        self.assertIn("STRUCT 引擎", asm)
        self.assertIn("STRUCT_INIT ('引擎'", asm)

    def test_disassembler_contains_error_flow(self) -> None:
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

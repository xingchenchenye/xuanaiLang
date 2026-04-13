from __future__ import annotations

import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline


ROOT = Path(__file__).resolve().parents[1]


class BackendParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CompilerPipeline()

    def test_break_and_continue(self) -> None:
        env = self.pipeline.execute_file(ROOT / "examples" / "循环控制.xy")
        self.assertEqual(env["合计"], 13)

    def test_interpreter_and_python_backend_parity(self) -> None:
        source = """
        术 外层(x: 整) -> 整 {
            术 内层(y: 整) -> 整 {
                返 x + y；
            }
            返 内层(5)；
        }
        令 值 = 外层(7)；
        """
        interp = self.pipeline.execute_source(source, file_path=str(ROOT / "tests" / "closure.xy"))
        python = self.pipeline.execute_source_python(source, file_path=str(ROOT / "tests" / "closure.xy"))
        self.assertEqual(interp["值"], 12)
        self.assertEqual(python["值"], 12)
        self.assertEqual(interp["值"], python["值"])

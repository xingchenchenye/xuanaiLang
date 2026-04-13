from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline
from xuanlang.project import ProjectManager
from xuanlang.scaffold import ProjectScaffolder


class ProjectToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = Path(tempfile.mkdtemp(prefix="xuanlang_project_"))
        self.project = ProjectScaffolder().create(str(self.tempdir / "demo"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_project_manager_resolves_entry(self) -> None:
        manager = ProjectManager()
        entry = manager.resolve_source(self.project)
        self.assertEqual(entry.name, "main.xy")

    def test_project_manager_discovers_tests(self) -> None:
        manager = ProjectManager()
        tests = manager.discover_tests(self.project)
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0].name, "smoke.xy")

    def test_formatter_outputs_canonical_source(self) -> None:
        source = "令  值=1+2；\n若 真{显(\"好\")；}否则{显(\"坏\")；}\n"
        formatted = CompilerPipeline().format_source(source)
        self.assertIn("令 值 = (1 + 2)；", formatted)
        self.assertIn("若 真 {", formatted)


if __name__ == "__main__":
    unittest.main()

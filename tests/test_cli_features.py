from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from xuanlang.pipeline import CompilerPipeline
from xuanlang.scaffold import ProjectScaffolder


class CliFeatureTests(unittest.TestCase):
    def test_symbol_table_contains_user_names(self) -> None:
        table = CompilerPipeline().symbol_table(
            """
            常 名称 = "玄言"；
            术 求和(a: 整, b: 整) -> 整 {
                返 a + b；
            }
            """
        )
        self.assertIn("名称", table)
        self.assertIn("求和", table)

    def test_scaffolder_creates_project(self) -> None:
        tempdir = Path(tempfile.mkdtemp(prefix="xuanlang_scaffold_"))
        try:
            root = ProjectScaffolder().create(str(tempdir / "demo"))
            self.assertTrue((root / "xuan.toml").exists())
            self.assertTrue((root / "src" / "main.xy").exists())
            self.assertTrue((root / ".gitignore").exists())
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

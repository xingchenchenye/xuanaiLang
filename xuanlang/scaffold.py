from __future__ import annotations

from pathlib import Path


class ProjectScaffolder:
    def create(self, target: str, developer: str = "开发者星尘_尘夜") -> Path:
        root = Path(target).resolve()
        src = root / "src"
        tests = root / "tests"
        src.mkdir(parents=True, exist_ok=True)
        tests.mkdir(parents=True, exist_ok=True)

        project_name = root.name
        (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.xuan-cache/\n", encoding="utf-8")
        (root / "README.md").write_text(
            f"# {project_name}\n\n由玄言项目脚手架创建。\n\n开发者：{developer}\n",
            encoding="utf-8",
        )
        (root / "xuan.toml").write_text(
            "[language]\n"
            f'name = "{project_name}"\n'
            'codename = "XuanProject"\n'
            'version = "0.7.0"\n\n'
            "[project]\n"
            'entry = "src/main.xy"\n'
            'test_dir = "tests"\n\n'
            "[developer]\n"
            f'name = "{developer}"\n',
            encoding="utf-8",
        )
        (src / "main.xy").write_text(
            '显("欢迎来到玄言项目")；\n',
            encoding="utf-8",
        )
        (tests / "smoke.xy").write_text(
            '令 值 = 1 + 1；\n断 值 == 2, "脚手架测试失败"；\n',
            encoding="utf-8",
        )
        return root

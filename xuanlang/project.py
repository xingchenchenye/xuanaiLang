from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProjectConfig:
    root: Path
    name: str
    entry: str | None = None
    test_dir: str = "tests"
    developer: str = ""

    @property
    def entry_path(self) -> Path | None:
        if not self.entry:
            return None
        return (self.root / self.entry).resolve()

    @property
    def tests_path(self) -> Path:
        return (self.root / self.test_dir).resolve()


class ProjectManager:
    def find_root(self, start: str | Path) -> Path | None:
        path = Path(start).resolve()
        current = path if path.is_dir() else path.parent
        for candidate in (current, *current.parents):
            if (candidate / "xuan.toml").exists():
                return candidate
        return None

    def load(self, start: str | Path) -> ProjectConfig | None:
        root = self.find_root(start)
        if root is None:
            return None
        data = tomllib.loads((root / "xuan.toml").read_text(encoding="utf-8"))
        language = data.get("language", {})
        project = data.get("project", {})
        developer = data.get("developer", {})
        return ProjectConfig(
            root=root,
            name=language.get("name") or root.name,
            entry=project.get("entry") or language.get("entry"),
            test_dir=project.get("test_dir", "tests"),
            developer=developer.get("name", ""),
        )

    def resolve_source(self, target: str | Path) -> Path:
        path = Path(target).resolve()
        if path.is_file():
            return path
        config = self.load(path)
        if config is None or config.entry_path is None:
            raise FileNotFoundError(f"未找到可运行的玄言项目入口: {path}")
        return config.entry_path

    def discover_tests(self, target: str | Path) -> list[Path]:
        config = self.load(target)
        if config is None:
            path = Path(target).resolve()
            if path.is_file():
                return [path]
            tests_dir = path / "tests"
            return sorted(tests_dir.rglob("*.xy")) if tests_dir.exists() else []
        if not config.tests_path.exists():
            return []
        return sorted(config.tests_path.rglob("*.xy"))

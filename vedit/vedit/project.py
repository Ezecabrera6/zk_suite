"""Estructura de un proyecto y rutas estándar.

Un proyecto es una carpeta con:
  01_main/ ... 12_project/project.json
Todas las rutas dentro de JSON son RELATIVAS a la carpeta del proyecto (portables Windows/Linux).
"""
from __future__ import annotations

import os
from pathlib import Path

from .util import load_json, save_json


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not (self.root / "12_project").is_dir():
            raise SystemExit(f"[vedit] {self.root} no parece un proyecto (falta 12_project/)")
        self.cfg_path = self.root / "12_project" / "project.json"
        self.cfg = load_json(self.cfg_path, {}) or {}

    # ---------- rutas ----------
    def p(self, rel: str | Path) -> Path:
        return self.root / Path(str(rel).replace("\\", "/"))

    def rel(self, path: str | Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    @property
    def project_dir(self) -> Path:
        return self.root / "12_project"

    @property
    def timelines_dir(self) -> Path:
        return self.project_dir / "timelines"

    @property
    def timeline_current(self) -> Path:
        return self.project_dir / "timeline_current.json"

    @property
    def analysis_dir(self) -> Path:
        return self.project_dir / "analysis"

    @property
    def subs_dir(self) -> Path:
        return self.project_dir / "subtitles"

    @property
    def cache_dir(self) -> Path:
        return self.root / "10_work" / "cache"

    @property
    def proxy_dir(self) -> Path:
        return self.root / "10_work" / "proxy"

    @property
    def previews_dir(self) -> Path:
        return self.root / "11_exports" / "previews"

    @property
    def final_dir(self) -> Path:
        return self.root / "11_exports" / "final"

    def source(self, key: str) -> dict:
        return self.cfg["sources"][key]

    def save_cfg(self):
        save_json(self.cfg_path, self.cfg)

    def ensure_dirs(self):
        for d in (self.timelines_dir, self.analysis_dir, self.subs_dir, self.cache_dir, self.proxy_dir,
                  self.previews_dir):
            d.mkdir(parents=True, exist_ok=True)


def find_project(arg: str | None) -> Project:
    if arg:
        return Project(arg)
    if os.environ.get("VEDIT_PROJECT"):
        return Project(os.environ["VEDIT_PROJECT"])
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "12_project").is_dir() and (parent / "01_main").is_dir():
            return Project(parent)
    return Project(Path.cwd())

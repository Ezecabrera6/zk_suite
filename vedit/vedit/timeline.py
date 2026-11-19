"""Timeline: fuente de verdad NO destructiva de la edición.

Formato (schema vedit.timeline/1):
{
  "schema": "vedit.timeline/1",
  "version": 3, "parent_version": 2, "note": "...", "created_at": "...",
  "output": {"width":1920,"height":1080,"fps":30},
  "sequence": [                      # orden de reproducción / render
     {"id":"logo","source":"logo","in":0,"out":1.733,"kind":"LOGO"},
     {"id":"k001","source":"main","in":0.0,"out":15.0,"kind":"KEEP", "speed":1.0, "zoom":null, "crop":null},
     {"id":"outro","source":"outro","in":0,"out":5.883,"kind":"OUTRO"}
  ],
  "decisions": [                     # por qué se corta (sobre el tiempo de la fuente main)
     {"id":"d001","start":787.0,"end":852.0,"action":"remove|shorten|keep","category":"SILENCE",
      "reason":"...","confidence":0.95,"status":"applied|proposed|rejected","keep_seconds":0.6}
  ],
  "effects": [                       # sobre tiempo de fuente main
     {"id":"blur1","type":"privacy_blur","start":556,"end":566,"rect":{"x":0.77,"y":0.64,"w":0.23,"h":0.17},"strength":24},
     {"id":"sub1","type":"overlay","asset":"subscribe","start":30.0,"duration":3.3,"rect":{"x":0.0,"y":0.0,"w":1.0,"h":1.0}}
  ],
  "markers": [{"t":561.0,"label":"Teams","category":"PRIVACY_BLUR"}],
  "subtitles": {"enabled":true,"file":"12_project/subtitles/subtitles.vtt","burn":false,"style":{...}},
  "audio": {"normalize":{"standard":"EBU R128","I":-14,"TP":-1,"LRA":11}, "fade_in":0.3,"fade_out":0.8, "music":[]},
  "broll": [], "music": [], "transitions": []      # reservados para el futuro
}
Versionado: cada cambio crea timelines/timeline_vNNN.json y actualiza timeline_current.json.
Nunca se borra una versión: "undo" crea una versión nueva copiando la anterior.
"""
from __future__ import annotations

import copy
import glob
import re
from pathlib import Path

from .util import load_json, now_iso, save_json, snap

KINDS = ["KEEP", "CUT", "SILENCE", "REPETITION", "ERROR", "PRIVACY_BLUR", "BROLL", "LOGO", "OUTRO", "SUBTITLE"]

DEFAULT_SUB_STYLE = {
    "font": "Arial", "size": 46, "color": "#FFFFFF", "outline_color": "#000000", "outline": 3,
    "shadow": 1, "background": "rgba(0,0,0,0)", "position": "bottom", "margin_v": 60, "bold": True,
}


def empty_timeline(project_name: str) -> dict:
    return {
        "schema": "vedit.timeline/1", "project": project_name, "version": 0, "parent_version": None,
        "note": "", "created_at": now_iso(),
        "output": {"width": 1920, "height": 1080, "fps": 30},
        "sequence": [], "decisions": [], "effects": [], "markers": [],
        "subtitles": {"enabled": False, "file": None, "burn": False, "style": dict(DEFAULT_SUB_STYLE)},
        "audio": {"normalize": {"standard": "EBU R128", "I": -14.0, "TP": -1.0, "LRA": 11.0},
                  "fade_in": 0.3, "fade_out": 0.8},
        "broll": [], "music": [], "transitions": [],
    }


# ---------------------------------------------------------------- versionado
def _versions(prj) -> list[int]:
    out = []
    for f in glob.glob(str(prj.timelines_dir / "timeline_v*.json")):
        m = re.search(r"timeline_v(\d+)\.json$", f)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def load_current(prj) -> dict | None:
    return load_json(prj.timeline_current)


def save_version(prj, tl: dict, note: str) -> dict:
    prj.timelines_dir.mkdir(parents=True, exist_ok=True)
    vs = _versions(prj)
    tl = copy.deepcopy(tl)
    tl["parent_version"] = tl.get("version") or (vs[-1] if vs else None)
    tl["version"] = (vs[-1] + 1) if vs else 1
    tl["note"] = note
    tl["created_at"] = now_iso()
    normalize(tl)
    save_json(prj.timelines_dir / f"timeline_v{tl['version']:03d}.json", tl)
    save_json(prj.timeline_current, tl)
    return tl


def list_versions(prj) -> list[dict]:
    rows = []
    for v in _versions(prj):
        t = load_json(prj.timelines_dir / f"timeline_v{v:03d}.json", {})
        rows.append({"version": v, "note": t.get("note", ""), "created_at": t.get("created_at"),
                     "duration": round(edited_duration(t), 2)})
    return rows


def restore(prj, version: int) -> dict:
    t = load_json(prj.timelines_dir / f"timeline_v{version:03d}.json")
    if not t:
        raise SystemExit(f"No existe la versión {version}")
    t["version"] = _versions(prj)[-1]
    return save_version(prj, t, f"restaurada desde v{version:03d}")


def undo(prj) -> dict:
    cur = load_current(prj)
    if not cur or not cur.get("parent_version"):
        raise SystemExit("No hay versión anterior")
    return restore(prj, cur["parent_version"])


# ---------------------------------------------------------------- cálculo
def normalize(tl: dict) -> None:
    for c in tl["sequence"]:
        c["in"], c["out"] = snap(c["in"]), snap(c["out"])
    for d in tl["decisions"]:
        d["start"], d["end"] = round(float(d["start"]), 3), round(float(d["end"]), 3)
    tl["sequence"] = [c for c in tl["sequence"] if c["out"] - c["in"] >= 1 / 30]


def clip_dur(c: dict) -> float:
    return (c["out"] - c["in"]) / float(c.get("speed") or 1.0)


def edited_duration(tl: dict) -> float:
    return sum(clip_dur(c) for c in tl.get("sequence", []))


def rebuild_main_sequence(tl: dict, main_duration: float, logo: dict | None = None, outro: dict | None = None,
                          head: float = 0.0, tail: float | None = None, min_keep: float = 0.35) -> dict:
    """Recalcula los clips KEEP de 'main' a partir de las decisiones aplicadas.

    - remove  → se quita [start, end]
    - shorten → se quita el centro dejando keep_seconds (mitad a cada lado)
    - keep / rejected / proposed → no se toca
    """
    tail = main_duration if tail is None else tail
    cuts = []
    for d in tl["decisions"]:
        if d.get("status") != "applied":
            continue
        s, e = float(d["start"]), float(d["end"])
        if d["action"] == "shorten":
            k = float(d.get("keep_seconds", 0.6))
            if e - s <= k:
                continue
            s, e = s + k / 2, e - k / 2
        elif d["action"] != "remove":
            continue
        cuts.append((max(head, s), min(tail, e)))
    cuts.sort()
    merged = []
    for s, e in cuts:
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    keeps, cur = [], head
    for s, e in merged:
        if s > cur:
            keeps.append((cur, s))
        cur = max(cur, e)
    if cur < tail:
        keeps.append((cur, tail))
    # fragmentos conservados muy cortos (< min_keep) se ven como un parpadeo: se descartan
    keeps = [(s, e) for s, e in keeps if e - s >= min_keep]
    seq = []
    if logo:
        seq.append(logo)
    for i, (s, e) in enumerate(keeps, 1):
        seq.append({"id": f"k{i:03d}", "source": "main", "in": snap(s), "out": snap(e), "kind": "KEEP"})
    if outro:
        seq.append(outro)
    tl["sequence"] = seq
    normalize(tl)
    return tl


def source_to_edit(tl: dict, t: float, source: str = "main") -> float | None:
    acc = 0.0
    for c in tl["sequence"]:
        if c["source"] == source and c["in"] <= t < c["out"]:
            return acc + (t - c["in"]) / float(c.get("speed") or 1.0)
        acc += clip_dur(c)
    return None


def edit_to_source(tl: dict, t: float) -> tuple[dict, float] | None:
    acc = 0.0
    for c in tl["sequence"]:
        d = clip_dur(c)
        if acc <= t < acc + d:
            return c, c["in"] + (t - acc) * float(c.get("speed") or 1.0)
        acc += d
    return None


def removed_ranges(tl: dict, main_duration: float) -> list[tuple[float, float]]:
    keeps = sorted((c["in"], c["out"]) for c in tl["sequence"] if c["source"] == "main")
    out, cur = [], 0.0
    for s, e in keeps:
        if s > cur + 1e-3:
            out.append((cur, s))
        cur = max(cur, e)
    if cur < main_duration - 1e-3:
        out.append((cur, main_duration))
    return out


# ---------------------------------------------------------------- finishing sobre la base de la editora
# timeline_preedited_base.json (inmutable) → timelines/timeline_enhanced_vNNN.json → timeline_current.json
# Clips: {"source":"base"} = tramo de la base; {"source":"main", "base_at": t} = reparación con el original,
# donde base_at es el tiempo de la base al que corresponde (para sincronizar A/B).
def base_timeline_path(prj) -> Path:
    return prj.project_dir / "timeline_preedited_base.json"


def _enhanced_versions(prj) -> list[int]:
    out = []
    for f in glob.glob(str(prj.timelines_dir / "timeline_enhanced_v*.json")):
        m = re.search(r"timeline_enhanced_v(\d+)\.json$", f)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def save_enhanced(prj, tl: dict, note: str) -> dict:
    """Crea timelines/timeline_enhanced_vNNN.json (nunca sobrescribe) y lo activa en timeline_current.json."""
    prj.timelines_dir.mkdir(parents=True, exist_ok=True)
    vs = _enhanced_versions(prj)
    tl = copy.deepcopy(tl)
    tl["parent_version"] = tl.get("version") if tl.get("track") == "enhanced" and vs else None
    tl["track"] = "enhanced"
    tl["version"] = (vs[-1] + 1) if vs else 1
    tl["note"] = note
    tl["created_at"] = now_iso()
    normalize(tl)
    path = prj.timelines_dir / f"timeline_enhanced_v{tl['version']:03d}.json"
    if path.exists():
        raise SystemExit(f"{path} ya existe: no se sobrescribe")
    tl["active_file"] = prj.rel(path)
    save_json(path, tl)
    save_json(prj.timeline_current, tl)
    return tl


def list_enhanced(prj) -> list[dict]:
    rows = []
    for v in _enhanced_versions(prj):
        t = load_json(prj.timelines_dir / f"timeline_enhanced_v{v:03d}.json", {})
        rows.append({"version": v, "note": t.get("note", ""), "created_at": t.get("created_at"),
                     "duration": round(edited_duration(t), 3), "changes": len(t.get("changes", []))})
    return rows


def restore_enhanced(prj, version: int) -> dict:
    t = load_json(prj.timelines_dir / f"timeline_enhanced_v{version:03d}.json")
    if not t:
        raise SystemExit(f"No existe enhanced v{version:03d}")
    t["version"] = _enhanced_versions(prj)[-1]
    return save_enhanced(prj, t, f"restaurada desde enhanced v{version:03d}")


def edit_to_base(tl: dict, t: float) -> float | None:
    """Tiempo de la edición → tiempo de la base (para A/B)."""
    r = edit_to_source(tl, t)
    if not r:
        return None
    c, st = r
    if c["source"] == "base":
        return st
    if c.get("base_at") is not None:  # base_hold: material nuevo (logo) sin equivalente en la base
        return float(c["base_at"]) + (0.0 if c.get("base_hold") else st - c["in"])
    return None

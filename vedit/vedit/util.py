"""Utilidades comunes: ffmpeg/ffprobe, hashing, tiempos, JSON."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

FPS_GRID = 30  # todas las marcas de corte se alinean a 1/30 s (sin deriva A/V)


def ffmpeg_bin() -> str:
    return os.environ.get("VEDIT_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    return os.environ.get("VEDIT_FFPROBE") or shutil.which("ffprobe") or "ffprobe"


def run(cmd: list[str], check: bool = True, quiet: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta un comando. Si falla, muestra comando + stderr (no inventa resultados)."""
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        sys.stderr.write("\n[vedit] COMANDO FALLÓ:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")
        sys.stderr.write(p.stderr[-4000:] + "\n")
        raise RuntimeError(f"comando falló ({p.returncode})")
    if not quiet:
        sys.stdout.write(p.stdout)
    return p


def ffprobe_json(path: str | Path) -> dict:
    p = run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(p.stdout or "{}")


def snap(t: float, grid: int = FPS_GRID) -> float:
    """Alinea un tiempo a la grilla de frames de salida."""
    return round(round(float(t) * grid) / grid, 6)


def fmt_tc(t: float) -> str:
    t = max(0.0, float(t))
    m, s = divmod(t, 60)
    h, m = divmod(int(m), 60)
    return f"{h:d}:{m:02d}:{s:06.3f}" if h else f"{m:d}:{s:06.3f}"


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def file_fingerprint(path: str | Path) -> str:
    """Huella rápida (tamaño + mtime) para decidir si un caché sigue siendo válido."""
    st = os.stat(path)
    return f"{st.st_size}-{int(st.st_mtime)}"


def sha256_file(path: str | Path, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def load_json(path: str | Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path: str | Path, data) -> None:
    """Escritura atómica (tmp + replace) para que el visor nunca lea un JSON a medias."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

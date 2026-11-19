"""Detección REAL de aceleración: se prueba cada encoder codificando 1 s de video.

No se asume hardware: un encoder cuenta como disponible solo si la prueba funciona.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess

from .util import ffmpeg_bin, now_iso, run

# Orden de preferencia para H.264
CANDIDATES = [
    ("h264_nvenc", ["-preset", "p4", "-tune", "hq"]),
    ("h264_amf", ["-quality", "speed"]),
    ("h264_qsv", ["-preset", "veryfast"]),
    ("libx264", ["-preset", "veryfast"]),
]


def _try_encoder(name: str) -> bool:
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
           "testsrc2=s=1280x720:r=30", "-t", "1", "-c:v", name, "-f", "null", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode == 0
    except Exception:
        return False


def _nvidia() -> dict:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {}
    try:
        p = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=10)
        name, mem, drv = [x.strip() for x in p.stdout.strip().splitlines()[0].split(",")]
        return {"gpu": name, "vram": mem, "driver": drv}
    except Exception:
        return {}


def _cuda_for_whisper() -> bool:
    try:
        import ctranslate2  # noqa
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def detect() -> dict:
    enc = {name: _try_encoder(name) for name, _ in CANDIDATES}
    chosen = next((n for n, _ in CANDIDATES if enc.get(n)), "libx264")
    nv = _nvidia()
    cuda = _cuda_for_whisper()
    vram_mb = 0
    if nv.get("vram"):
        try:
            vram_mb = int(nv["vram"].split()[0])
        except Exception:
            pass
    if cuda:
        model = "medium" if vram_mb >= 3500 else "small"
        ctype = "float16"
    else:
        model, ctype = "small", "int8"
    return {
        "detected_at": now_iso(),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu": platform.processor() or "desconocido",
        "cpu_threads": os.cpu_count(),
        "nvidia": nv,
        "encoders_tested": enc,
        "nvenc": enc.get("h264_nvenc", False),
        "amf": enc.get("h264_amf", False),
        "qsv": enc.get("h264_qsv", False),
        "recommended_encoder": chosen,
        "cuda_for_whisper": cuda,
        "recommended_transcription_device": "cuda" if cuda else "cpu",
        "recommended_transcription_compute_type": ctype,
        "recommended_whisper_model": model,
    }


def encoder_args(name: str, quality: str = "preview") -> list[str]:
    """Argumentos de codificación por encoder y modo (preview rápido / final calidad)."""
    if name == "h264_nvenc":
        return (["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "30", "-b:v", "0"] if quality == "preview"
                else ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-profile:v", "high"])
    if name == "h264_amf":
        return (["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "30", "-qp_p", "30"] if quality == "preview"
                else ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "19", "-qp_p", "21"])
    if name == "h264_qsv":
        return (["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "30"] if quality == "preview"
                else ["-c:v", "h264_qsv", "-preset", "slow", "-global_quality", "20"])
    return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "27"] if quality == "preview"
            else ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high"])

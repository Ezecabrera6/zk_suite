"""Proxy de edición (720p30, GOP 1 s para seek instantáneo en el navegador).

- Incremental: se genera por bloques (chunks) y cada bloque terminado queda en caché.
  Si se corta, al volver a ejecutar sigue donde quedó.
- Nunca toca el original. El render final siempre usa el original.
- El audio del proxy va normalizado (EBU R128, 2 pasadas) para que el preview suene como el final.
"""
from __future__ import annotations

import json
import os
import re
import time

from .hw import encoder_args
from .util import ffmpeg_bin, ffprobe_json, file_fingerprint, load_json, run, save_json, sha256_text

CHUNK_S = 90
PROXY_W, PROXY_H, PROXY_FPS = 1280, 720, 30


def _settings(encoder: str) -> dict:
    return {"w": PROXY_W, "h": PROXY_H, "fps": PROXY_FPS, "chunk": CHUNK_S, "encoder": encoder, "gop": PROXY_FPS}


def _venc(encoder: str) -> list[str]:
    if encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "27"]
    return encoder_args(encoder, "preview")


def loudnorm_measure(prj, src_key="main", I=-14.0, TP=-1.0, LRA=11.0) -> dict:
    """Primera pasada de loudnorm (EBU R128) sobre el audio completo. Cacheada."""
    src = prj.p(prj.source(src_key)["path"])
    out = prj.analysis_dir / f"loudnorm_{src_key}.json"
    fp = file_fingerprint(src)
    cached = load_json(out)
    if cached and cached.get("source_fp") == fp and cached.get("target") == {"I": I, "TP": TP, "LRA": LRA}:
        return cached
    p = run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-i", str(src), "-vn",
             "-af", f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]*\}", p.stderr, re.S)[-1])
    data = {"source_fp": fp, "target": {"I": I, "TP": TP, "LRA": LRA}, "measured": m, "measured_at": time.time()}
    save_json(out, data)
    return data


def loudnorm_filter(meas: dict, linear: bool = True) -> str:
    t, m = meas["target"], meas["measured"]
    return (f"loudnorm=I={t['I']}:TP={t['TP']}:LRA={t['LRA']}:measured_I={m['input_i']}:"
            f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear={'true' if linear else 'false'}")


def gain_filter(meas: dict) -> str:
    """Ganancia lineal EBU R128 (I objetivo − I medido) + limitador de pico. Mismo criterio que el render final,
    para que preview y final suenen igual y sin clipping."""
    t, m = meas["target"], meas["measured"]
    gain = float(t["I"]) - float(m["input_i"])
    return f"volume={gain:.2f}dB,alimiter=limit={10 ** (float(t['TP']) / 20):.4f}:level=disabled"


def build_proxy(prj, src_key="main", encoder="libx264", max_chunks: int | None = None, log=print) -> dict:
    src_rel = prj.source(src_key)["path"]
    src = prj.p(src_rel)
    info = ffprobe_json(src)
    dur = float(info["format"]["duration"])
    d = prj.proxy_dir
    cdir = d / "chunks"
    cdir.mkdir(parents=True, exist_ok=True)
    man_path = d / f"{src_key}_manifest.json"
    settings = _settings(encoder)
    key = sha256_text(json.dumps([file_fingerprint(src), settings]))
    man = load_json(man_path, {})
    if man.get("key") != key:
        # la fuente o los ajustes cambiaron: se invalida el caché de chunks
        man = {"key": key, "source": src_rel, "settings": settings, "duration": dur, "chunks": {}}
    n = int(-(-dur // CHUNK_S))
    done_now = 0
    for i in range(n):
        name = f"c{i:03d}.mp4"
        if man["chunks"].get(name) and (cdir / name).exists():
            continue
        if max_chunks is not None and done_now >= max_chunks:
            save_json(man_path, man)
            return {"status": "partial", "done": len(man["chunks"]), "total": n}
        s = i * CHUNK_S
        t = min(CHUNK_S, dur - s)
        log(f"[proxy] chunk {i + 1}/{n}  {s:.0f}s → {s + t:.0f}s")
        run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{s}", "-t", f"{t}", "-i", str(src),
             "-an", "-vf", f"fps={PROXY_FPS},scale={PROXY_W}:{PROXY_H}:flags=fast_bilinear", *_venc(encoder),
             "-g", str(PROXY_FPS), "-keyint_min", str(PROXY_FPS), "-sc_threshold", "0", "-pix_fmt", "yuv420p",
             "-y", str(cdir / name)])
        man["chunks"][name] = True
        done_now += 1
        save_json(man_path, man)

    # audio normalizado completo (una sola pasada, rápido)
    aud = d / f"{src_key}_proxy_audio.m4a"
    meas = loudnorm_measure(prj, src_key)
    akey = sha256_text(json.dumps([key, meas["measured"]]))
    if man.get("audio_key") != akey or not aud.exists():
        wav = d / f"{src_key}_proxy_audio.wav"
        if man.get("wav_key") != akey or not wav.exists():
            log("[proxy] audio normalizado (EBU R128) → wav")
            run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(src), "-vn",
                 "-af", gain_filter(meas) + ",aresample=48000", "-ar", "48000", "-c:a", "pcm_s16le",
                 "-y", str(wav.with_suffix(".tmp.wav"))])
            os.replace(wav.with_suffix(".tmp.wav"), wav)
            man["wav_key"] = akey
            save_json(man_path, man)
        log("[proxy] audio → AAC")
        run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(wav),
             "-c:a", "aac", "-b:a", "128k", "-y", str(aud.with_suffix(".tmp.m4a"))])
        os.replace(aud.with_suffix(".tmp.m4a"), aud)
        man["audio_key"] = akey
        save_json(man_path, man)

    out = d / f"{src_key}_proxy.mp4"
    if man.get("mux_key") != akey or not out.exists():
        lst = d / f"{src_key}_chunks.txt"
        lst.write_text("".join(f"file 'chunks/c{i:03d}.mp4'\n" for i in range(n)), encoding="utf-8")
        log("[proxy] uniendo chunks (sin recomprimir)")
        run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-i", str(aud), "-map", "0:v", "-map", "1:a", "-c", "copy",
             "-movflags", "+faststart", "-y", str(out.with_suffix(".tmp.mp4"))])
        os.replace(out.with_suffix(".tmp.mp4"), out)
        man["mux_key"] = akey
        save_json(man_path, man)
    prj.cfg["sources"][src_key]["proxy"] = prj.rel(out)
    prj.save_cfg()
    return {"status": "done", "proxy": prj.rel(out), "chunks": n}

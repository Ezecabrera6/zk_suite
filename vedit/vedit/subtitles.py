"""Transcripción (faster-whisper) y subtítulos SRT / VTT / ASS a partir de transcript.json."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .util import file_fingerprint, load_json, save_json


def transcribe(prj, src_key="main", model="auto", device="auto", compute_type="auto", language="es", log=print) -> dict:
    """faster-whisper. Cacheado: si la fuente no cambió, no se vuelve a ejecutar."""
    src = prj.p(prj.source(src_key)["path"])
    out = prj.project_dir / "transcript.json"
    fp = file_fingerprint(src)
    cur = load_json(out)
    if cur and cur.get("source_fp") == fp:
        log("[transcribe] transcript.json vigente (caché) — no se vuelve a procesar")
        return cur
    from faster_whisper import WhisperModel  # import tardío: solo si hace falta
    hw = load_json(prj.project_dir / "hardware.json", {}) or {}
    device = hw.get("recommended_transcription_device", "cpu") if device == "auto" else device
    compute_type = hw.get("recommended_transcription_compute_type", "int8") if compute_type == "auto" else compute_type
    model = hw.get("recommended_whisper_model", "small") if model == "auto" else model
    tried = []
    for dev, ct in [(device, compute_type), (device, "int8_float16"), ("cpu", "int8")]:
        if (dev, ct) in tried or (dev == "cpu" and ct == "int8_float16"):
            continue
        tried.append((dev, ct))
        try:
            log(f"[transcribe] faster-whisper {model} · {dev} · {ct}")
            m = WhisperModel(model, device=dev, compute_type=ct)
            t0 = time.time()
            segs, info = m.transcribe(str(src), language=language, vad_filter=True, word_timestamps=True,
                                      vad_parameters={"min_silence_duration_ms": 350})
            rows = []
            for s in segs:
                rows.append({"id": len(rows), "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
                             "confidence": round(float(__import__("math").exp(s.avg_logprob)), 3),
                             "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word,
                                        "p": round(w.probability, 3)} for w in (s.words or [])]})
            data = {"engine": f"faster-whisper {model}", "device": dev, "compute_type": ct, "language": language,
                    "source": prj.source(src_key)["path"], "source_fp": fp, "seconds": round(time.time() - t0, 1),
                    "segments": rows}
            save_json(out, data)
            return data
        except Exception as e:  # p.ej. falta de VRAM → se reduce el consumo y se documenta
            log(f"[transcribe] falló con {dev}/{ct}: {e}")
    raise SystemExit("No se pudo transcribir con ninguna configuración")


def _t(t, sep=","):
    ms = int(round(max(0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _wrap(text: str, width: int = 42) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:  # máx. 2 líneas
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    return "\n".join(lines)


def cues_from_transcript(tr: dict, max_chars: int = 84, max_dur: float = 5.0) -> list[dict]:
    cues = []
    for s in tr["segments"]:
        text = s["text"].strip()
        if not text or text in ("[Música]", "*música*"):
            continue
        words = text.split()
        dur = s["end"] - s["start"]
        n = max(1, int(-(-len(text) // max_chars)), int(-(-dur // max_dur)))
        per = -(-len(words) // n)
        for k in range(n):
            chunk = words[k * per:(k + 1) * per]
            if not chunk:
                continue
            a = s["start"] + dur * (k * per) / len(words)
            b = s["start"] + dur * min(len(words), (k + 1) * per) / len(words)
            cues.append({"start": round(a, 3), "end": round(b, 3), "text": _wrap(" ".join(chunk))})
    return cues


def write_subtitles(prj, tr: dict | None = None, style: dict | None = None) -> dict:
    tr = tr or load_json(prj.project_dir / "transcript.json")
    cues = cues_from_transcript(tr)
    d = prj.subs_dir
    d.mkdir(parents=True, exist_ok=True)
    srt = "".join(f"{i}\n{_t(c['start'])} --> {_t(c['end'])}\n{c['text']}\n\n" for i, c in enumerate(cues, 1))
    vtt = "WEBVTT\n\n" + "".join(f"{_t(c['start'], '.')} --> {_t(c['end'], '.')}\n{c['text']}\n\n" for c in cues)
    (d / "subtitles.srt").write_text(srt, encoding="utf-8")
    (d / "subtitles.vtt").write_text(vtt, encoding="utf-8")
    st = style or {}
    col = lambda h: "&H00" + h.lstrip("#")[4:6] + h.lstrip("#")[2:4] + h.lstrip("#")[0:2]
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
           f"Style: Default,{st.get('font', 'Arial')},{st.get('size', 46)},{col(st.get('color', '#FFFFFF'))},"
           f"{col(st.get('outline_color', '#000000'))},&H80000000,{-1 if st.get('bold', True) else 0},1,"
           f"{st.get('outline', 3)},{st.get('shadow', 1)},{ {'top': 8, 'middle': 5}.get(st.get('position'), 2) },60,60,{st.get('margin_v', 60)}",
           "", "[Events]", "Format: Layer, Start, End, Style, Text"]
    for c in cues:
        a = _t(c["start"], ".")[1:-1]
        b = _t(c["end"], ".")[1:-1]
        body = c["text"].replace("\n", "\\N")
        ass.append(f"Dialogue: 0,{a},{b},Default,{body}")
    (d / "subtitles.ass").write_text("\n".join(ass) + "\n", encoding="utf-8")
    txt = "\n".join(f"[{_t(s['start'], '.')}] {s['text']}" for s in tr["segments"])
    (prj.project_dir / "transcript.txt").write_text(txt, encoding="utf-8")
    return {"cues": len(cues), "files": ["subtitles.srt", "subtitles.vtt", "subtitles.ass", "transcript.txt"]}

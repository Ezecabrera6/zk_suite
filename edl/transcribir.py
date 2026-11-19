"""Transcripción con marcas por palabra (faster-whisper large-v3 en CPU int8; CUDA falla en esta PC).
uso: python transcribir.py VIDEO.mp4 SALIDA.json   (usa la pista 1 = mezcla de OBS)
"""
import json, subprocess, sys, os, tempfile
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
wav = os.path.join(tempfile.gettempdir(), "tx_tmp.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "16000", wav], check=True)
m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=14)
segs, _ = m.transcribe(wav, language="es", word_timestamps=True, vad_filter=False)
res = []
with open(out.replace(".json", ".txt"), "w", encoding="utf-8") as f:
    for s in segs:
        res.append({"start": s.start, "end": s.end, "text": s.text, "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]})
        f.write(f"{s.start:7.2f}-{s.end:7.2f} {s.text}\n"); f.flush()
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OK", out)

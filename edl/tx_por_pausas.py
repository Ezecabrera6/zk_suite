"""Transcripción PAUSA POR PAUSA de un render o una toma.
Whisper sobre el archivo entero se saltea arranques cortados y retomas («y el G… vamos de nuevo»); acá cada tramo de voz
entre silencios se transcribe solo, sin contexto previo, así no se pierde nada.
uso: python tx_por_pausas.py VIDEO SALIDA.txt [pista_audio=0]"""
import os, glob, sys, subprocess, tempfile, wave
import numpy as np
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]; pista = sys.argv[3] if len(sys.argv) > 3 else "0"
wav = os.path.join(tempfile.gettempdir(), "txp.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", f"0:a:{pista}", "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
hop = int(sr * 0.02); rms = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12))
v = rms > -38   # en el render hay música de fondo: umbral más alto que en la toma
runs, cur = [], None
for f, on in enumerate(v):
    t = f * 0.02
    if on:
        if cur is None: cur = [t, t]
        elif t - cur[1] > 0.35: runs.append(cur); cur = [t, t]
        else: cur[1] = t
if cur: runs.append(cur)
runs = [r for r in runs if r[1] - r[0] > 0.15]
m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
with open(out, "w", encoding="utf-8") as fo:
    for a, b in runs:
        seg = x[int(max(0, a - 0.15) * sr):int((b + 0.25) * sr)]
        segs, _ = m.transcribe(seg, language="es", vad_filter=False, condition_on_previous_text=False, temperature=0.0)
        txt = " ".join(s.text.strip() for s in segs).strip()
        fo.write(f"{int(a // 60)}:{a % 60:05.2f}-{int(b // 60)}:{b % 60:05.2f} {txt}\n"); fo.flush()
print(out, len(runs), "tramos")

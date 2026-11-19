"""Control de los tramos elegidos ANTES de renderizar: cada tramo del EDL se divide en frases (por pausas en la voz) y cada frase
se transcribe sola, sin contexto. Así aparecen los arranques cortados («y el G… vamos de nuevo»), las retomas dentro de un tramo
(«este round lo ganó el… este round lo ganó el A16») y las frases que quedan sin terminar.
uso: python chequeo_tramos.py <carpeta 12_project> SALIDA.txt"""
import os, glob, sys, wave, importlib.util, pathlib
import numpy as np
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
PRJ = pathlib.Path(sys.argv[1]); out = sys.argv[2]
spec = importlib.util.spec_from_file_location("edl", PRJ / "narrado" / "edl_manual.py"); edl = importlib.util.module_from_spec(spec); spec.loader.exec_module(edl)
w = wave.open(str(PRJ / "analysis" / "voz16k.wav")); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
hop = int(sr * 0.02); rms = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12)); v = rms > -50
m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
with open(out, "w", encoding="utf-8") as fo:
    for k, (pl, a, b, cam) in enumerate(edl.KEEP):
        runs, cur = [], None
        for f in range(int(a / 0.02), min(int(b / 0.02), len(v))):
            t = f * 0.02
            if v[f]:
                if cur is None: cur = [t, t]
                elif t - cur[1] > 0.30: runs.append(cur); cur = [t, t]
                else: cur[1] = t
        if cur: runs.append(cur)
        fo.write(f"\n## tramo {k} · placa {pl} · {a:.2f}-{b:.2f}{' · CAM' if cam else ''}\n")
        for r0, r1 in runs:
            if r1 - r0 < 0.12: continue
            seg = x[int(max(a, r0 - 0.1) * sr):int(min(b + 0.05, r1 + 0.22) * sr)]
            segs, _ = m.transcribe(seg, language="es", vad_filter=False, condition_on_previous_text=False, temperature=0.0)
            fo.write(f"  {r0:7.2f}-{r1:7.2f}  {' '.join(s.text.strip() for s in segs).strip()}\n"); fo.flush()
print(out)

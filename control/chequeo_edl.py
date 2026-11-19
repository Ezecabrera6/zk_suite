"""Control del EDL antes de renderizar: en cada tramo, ¿hay voz (por energía) sin palabras transcriptas? Ahí suele esconderse una
retoma que Whisper no oyó (pasó en la comparativa: «Yo usé el G06…» y «Ah, y los Motorola» quedaban repetidos).
uso: python chequeo_edl.py <carpeta 12_project>"""
import json, sys, wave, pathlib, importlib.util
import numpy as np
PRJ = pathlib.Path(sys.argv[1]); AN = PRJ / "analysis"
spec = importlib.util.spec_from_file_location("edl", PRJ / "narrado" / "edl_manual.py"); edl = importlib.util.module_from_spec(spec); spec.loader.exec_module(edl)
W = json.load(open(AN / "words.json", encoding="utf-8"))
w_ = wave.open(str(AN / "voz16k.wav")); sr = w_.getframerate()
x = np.frombuffer(w_.readframes(w_.getnframes()), np.int16).astype(np.float32) / 32768
hop = int(sr * 0.02); r = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12); v = 20 * np.log10(r) > -50
n_warn = 0
for pl, a, b, cam in edl.KEEP:
    runs, cur = [], None
    for f in range(int(a / 0.02), int(b / 0.02)):
        t = f * 0.02
        if v[f]:
            if cur is None: cur = [t, t]
            elif t - cur[1] > 0.3: runs.append(cur); cur = [t, t]
            else: cur[1] = t
    if cur: runs.append(cur)
    for s, e in runs:
        if e - s < 0.5: continue
        cubierto = sum(max(0, min(e, we + 0.15) - max(s, ws - 0.15)) for _, ws, we in W)
        if cubierto < 0.4 * (e - s):
            n_warn += 1; print(f"  placa {pl}: voz sin palabras {s:.2f}-{e:.2f} ({e - s:.1f} s) en el tramo {a:.2f}-{b:.2f}")
print("avisos:", n_warn)

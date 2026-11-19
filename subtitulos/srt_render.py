"""Subtítulos .srt desde el render FINAL (regla del canal: transcribir el mp4 final, no la toma).
Whisper large-v3 en la GPU, cues de hasta 42 caracteres y 3,5 s, sin superposición (Studio da 400 si se pisan) y correcciones
de palabras que Whisper entiende mal en la voz del creador.
uso: python srt_render.py VIDEO.mp4 SALIDA.srt [correcciones.json]"""
import os, glob, sys, json, re
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
FIX = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
segs, _ = m.transcribe(src, language="es", word_timestamps=True, condition_on_previous_text=False, vad_filter=True)
words = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words if w.word.strip()]
cues, cur = [], []
for w in words:
    txt = " ".join(x[0] for x in cur + [w])
    if cur and (len(txt) > 42 or w[2] - cur[0][1] > 3.5 or w[1] - cur[-1][2] > 0.8):
        cues.append(cur); cur = []
    cur.append(w)
    if re.search(r"[.?!]$", w[0]) and len(" ".join(x[0] for x in cur)) > 18: cues.append(cur); cur = []
if cur: cues.append(cur)
def ts(t): h, r = divmod(t, 3600); mi, s = divmod(r, 60); return f"{int(h):02d}:{int(mi):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
lines = []
for i, c in enumerate(cues):
    a, b = c[0][1], c[-1][2] + 0.15
    if i + 1 < len(cues): b = min(b, cues[i + 1][0][1] - 0.02)
    t = " ".join(x[0] for x in c)
    for k, v in FIX.items(): t = re.sub(k, v, t)
    lines.append(f"{i + 1}\n{ts(a)} --> {ts(max(b, a + 0.3))}\n{t}\n")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print(out, len(cues), "cues")

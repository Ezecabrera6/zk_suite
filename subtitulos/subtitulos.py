"""Subtítulos SRT del video final a partir de las palabras de la fuente + narraciones (mapeadas al tiempo de edición)."""
import json, os, sys
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
MODE = sys.argv[2] if len(sys.argv) > 2 else "final"
P = CFG["proyecto"]
A = os.path.join(P, "12_project", "analysis")
tl = json.load(open(os.path.join(P, "10_work", CFG["slug"], "final", f"timeline_{MODE}.json"), encoding="utf-8"))
words = [w for s in json.load(open(os.path.join(A, CFG["transcripcion"]), encoding="utf-8")) for w in s["words"]]
ev = []
for a, b, te in tl["src2edit"]:
    for w in words:
        m = (w["s"] + w["e"]) / 2
        if a <= m < b:
            ev.append((te + max(w["s"], a) - a, te + min(w["e"], b) - a, w["w"].strip()))
for t0, t1, txt in tl.get("vo_subs", []):
    ev.append((t0, t1, txt))
ev.sort()
FIX = CFG.get("correcciones_subtitulos", {})   # {"lo que entiende Whisper": "lo correcto"}
def fx(w):
    for k, v in FIX.items():
        w = w.replace(k, v)
    return w
cues, cur = [], []
for e in ev:
    if cur and (e[0] - cur[-1][1] > 0.6 or len(" ".join(x[2] for x in cur + [e])) > 42 or cur[-1][2][-1:] in ".?!"):
        cues.append(cur); cur = []
    cur.append(e)
if cur: cues.append(cur)
def ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}".replace(",1000", ",999")
out = os.path.join(P, "11_exports", "final", CFG["slug"] + "_subtitulos_es.srt")
with open(out, "w", encoding="utf-8") as f:
    for i, c in enumerate(cues, 1):
        end = c[-1][1] + 0.15
        if i < len(cues):
            end = min(end, cues[i][0][0] - 0.02)
        txt = fx(" ".join(x[2] for x in c))
        prev = cues[i - 2][-1][2] if i > 1 else "."
        if prev[-1:] in ".?!":
            txt = txt[:1].upper() + txt[1:]
        f.write(f"{i}\n{ts(c[0][0])} --> {ts(end)}\n{txt}\n\n")
print(len(cues), "subtítulos →", out)

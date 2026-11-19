"""Preview rápida en 360p a partir de un edl.json (formato en render/README.md).
- Cara solo en los pedazos cam=True (mira al lente), alternando normal y cerca cada ~3 s.
- El resto: el B-roll de ese pedazo en orden (clips sin sonido) o una placa provisoria con lo que falta conseguir.
- Arriba a la izquierda va el tiempo, para poder comentar «en 1:23 tal cosa».
uso: python preview_360p.py <video>/12_project/edl.json   → <video>/11_exports/previews/<slug>_prev_vNNN.mp4"""
import json, os, subprocess, pathlib, glob, sys
from concurrent.futures import ThreadPoolExecutor

EDL_F = pathlib.Path(sys.argv[1]).resolve(); P = EDL_F.parent          # la carpeta 12_project del video
OUT = P.parent / "11_exports" / "previews"; OUT.mkdir(parents=True, exist_ok=True)
TMP = P.parent / "10_work" / "prev"; TMP.mkdir(parents=True, exist_ok=True)
for f in TMP.glob("*"): f.unlink()
D = json.load(open(EDL_F, encoding="utf-8"))
F, C, EDL = D["fuentes"], D["clips"], D["edl"]
SLUG = D.get("slug", "preview")
W, H, FPS = 640, 360, 30
FONT = os.environ.get("ZK_FUENTE", r"C:\Windows\Fonts\bahnschrift.ttf").replace("\\", "/").replace(":", "\\:")   # drawtext pide «C\:/…»
esc = lambda s: s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")

DUR = {k: float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v])) for k, v in C.items()}
planos, t, alterna = [], 0.0, 0
for x in EDL:
    nb = 0
    for a, b in x["partes"]:
        n = max(1, round((b - a) / 3.0))
        for j in range(n):
            d = (b - a) / n
            p = {"src": F[x["src"]], "in": a + d * j, "d": d, "t": t}
            if x["cam"]:
                p["tipo"] = "cam" if alterna % 2 == 0 else "cerca"; alterna += 1
            else:
                k, v = x["broll"][nb % len(x["broll"])]; nb += 1
                if k == "CARD":
                    p.update(tipo="card", txt=v)
                else:  # nunca pedir más allá del final del tráiler (eso dejaba planos vacíos y corría el video)
                    p.update(tipo="broll", b=C[k], bin=min(v + (nb // len(x["broll"])) * 3, DUR[k] - d - 0.5))
            planos.append(p); t += d


def render(i):
    p = planos[i]; o = TMP / f"{i:04d}.mp4"
    # cuadros exactos según el tiempo acumulado: así el redondeo no se suma plano a plano (desfase de audio)
    nf = round((p["t"] + p["d"]) * FPS) - round(p["t"] * FPS)
    mm, ss = divmod(int(p["t"]), 60)
    marca = f"drawtext=fontfile='{FONT}':text='{mm}\\:{ss:02d}':x=8:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5"
    if p["tipo"] == "card":
        cmd = ["-f", "lavfi", "-i", f"color=c=0x14161A:s={W}x{H}:r={FPS}"]
        vf = f"drawtext=fontfile='{FONT}':text='{esc(p['txt'])}':x=(w-tw)/2:y=(h-th)/2:fontsize=26:fontcolor=0xFFC531,{marca}"
    elif p["tipo"] == "broll":
        cmd = ["-ss", f"{p['bin']:.3f}", "-i", p["b"]]
        vf = f"scale={W}:{H},fps={FPS},{marca}"
    else:
        cmd = ["-ss", f"{p['in']:.3f}", "-i", p["src"]]
        z = "scale" if p["tipo"] == "cam" else "crop=iw/1.35:ih/1.35:(iw-iw/1.35)/2:ih*0.08,scale"
        vf = f"{z}={W}:{H},fps={FPS},{marca}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd, "-an", "-vf", vf, "-frames:v", str(nf), "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                    "-pix_fmt", "yuv420p", str(o)], check=True)
    got = subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(o)]).decode().strip()
    assert got == str(nf), f"plano {i} salió con {got or 0} cuadros y tenía que tener {nf}: {p}"
    return o


with ThreadPoolExecutor(6) as ex:
    vids = list(ex.map(render, range(len(planos))))
(TMP / "v.txt").write_text("".join(f"file '{v.as_posix()}'\n" for v in vids))

# Voz: pista 1 (mezcla procesada de OBS), parte por parte con fundidos de 10 ms para que no haya clics
auds, i = [], 0
for x in EDL:
    for a, b in x["partes"]:
        o = TMP / f"a{i:03d}.wav"; i += 1
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", F[x["src"]], "-t", f"{b - a:.3f}", "-map", "0:a:0",
                        "-af", f"afade=t=in:d=0.01,afade=t=out:st={max(0, b - a - 0.01):.3f}:d=0.01", "-ac", "2", "-ar", "48000", str(o)], check=True)
        auds.append(o)
(TMP / "a.txt").write_text("".join(f"file '{a.as_posix()}'\n" for a in auds))

import re as _re
ver = max([int(_re.search(r"_prev_v(\d+)", os.path.basename(f)).group(1)) for f in glob.glob(str(OUT / "**" / f"{SLUG}_prev_v*.mp4"), recursive=True)] + [0]) + 1
final = OUT / f"{SLUG}_prev_v{ver:03d}.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(TMP / "v.txt"),
                "-f", "concat", "-safe", "0", "-i", str(TMP / "a.txt"), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", str(final)], check=True)
cams = sum(p["d"] for p in planos if p["tipo"] in ("cam", "cerca"))
dv = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=duration", "-of", "csv=p=0", str(final)]))
da = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=duration", "-of", "csv=p=0", str(final)]))
assert abs(dv - da) < 0.1, f"video {dv:.2f} s y audio {da:.2f} s: desfasado"
print(f"sync ok: video {dv:.2f} s / audio {da:.2f} s")
print(f"{final}  ·  {t/60:.2f} min  ·  {len(planos)} planos (cada {t/len(planos):.1f} s)  ·  cara {cams:.0f} s · B-roll/placas {t-cams:.0f} s")

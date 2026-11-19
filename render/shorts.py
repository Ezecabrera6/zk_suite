"""4 Shorts/TikToks 9:16 de un video del canal, definidos en proyecto.json → "shorts".
Reglas: gancho en 2 s, una idea, corte cada 2-4 s, subtítulos grandes por palabra (clave en serif itálica dorada),
título fijo arriba sin barras, firma chica, el producto en pantalla (BROLL), fotos enteras sobre fondo desenfocado,
cierre con la miniatura real + "Miralo completo".
uso: python shorts.py RUTA/proyecto.json [1-4|all]
Variables de entorno: ZK_MUSICA, ZK_FUENTE y ZK_CANAL (nombre del canal en la firma y el cierre).
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CFG = json.load(open(sys.argv[1], encoding="utf-8"))
P = CFG["proyecto"]
J = lambda *x: os.path.join(P, *x)
rel = lambda s: J(*s.split("/"))
SRC = rel(CFG["toma"])
NARR = {k: rel(v) for k, v in CFG.get("narraciones", {}).items()}
FOT = rel(CFG.get("fotos", "06_material_usuario"))
THUMB = rel(CFG["miniatura"])
MUSIC = CFG.get("musica") or os.environ.get("ZK_MUSICA", "assets/musica.wav")
CANAL = os.environ.get("ZK_CANAL", "mi canal")
A = J("12_project", "analysis")
WK = J("10_work", CFG["slug"], "shorts"); os.makedirs(WK, exist_ok=True)
OUT = J("11_exports", "shorts"); os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1080, 1920, 30
FB = os.environ.get("ZK_FUENTE", r"C:\Windows\Fonts\bahnschrift.ttf")
AMBER = (245, 185, 66, 255)

def words(fn):
    return [w for s in json.load(open(os.path.join(A, fn), encoding="utf-8")) for w in s["words"]]
WORDS = {SRC: words(CFG["transcripcion"])}
for k, v in CFG.get("transcripciones_narraciones", {}).items():
    WORDS[NARR[k]] = words(v)
FIX = CFG.get("correcciones_subtitulos", {})
src_of = lambda name: SRC if name == "toma" else NARR[name]
SHORTS = {}
for n, s in enumerate(CFG["shorts"], 1):
    SHORTS[n] = dict(slug=s["slug"], titulo=s["titulo"], parte=s.get("parte", f"{n}/{len(CFG['shorts'])}"),
                     hook_txt=s["gancho_texto"], claves=set(s.get("claves", [])),
                     escenas=[(e[0], src_of(e[1]), e[2], e[3], e[4] if len(e) > 4 else {}) for e in s["escenas"]])
SLUGP = CFG["slug"]

def run(a):
    r = subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode:
        print(r.stderr[-2500:]); sys.exit(1)
    return r.stderr

def snap(src, a, b):
    ws = [w for w in WORDS[src] if w["s"] >= a - 0.12 and w["e"] <= b + 0.12]
    return (max(0, ws[0]["s"] - 0.08), ws[-1]["e"] + 0.12) if ws else (a, b)

def cam_vf(o):
    z = o.get("z", 1.0); cx = o.get("cx", 960); cy = 470
    ch = int(1080 / z) // 2 * 2; cw = int(ch * 9 / 16) // 2 * 2
    x = max(0, min(1920 - cw, cx - cw // 2)); y = max(0, min(1080 - ch, cy - ch // 2 if z > 1 else 0))
    return f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS},format=yuv420p"

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-color_range", "tv",
       "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
AF = "aformat=sample_rates=48000:channel_layouts=stereo"

def font(sz):
    return ImageFont.truetype(FB, sz)

def shadow_text(im, xy, t, f, fill, blur=8, alpha=170, anchor="la"):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 3), t, font=f, fill=(0, 0, 0, alpha), anchor=anchor)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(im).text(xy, t, font=f, fill=fill, anchor=anchor)

def top_png(cfg, path):
    """Título fijo arriba + firma chica. Sin barras ni cajas."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_text(im, (W // 2, 270), cfg["titulo"], font(46), (255, 255, 255, 245), anchor="mm")
    shadow_text(im, (W // 2, 325), f"Parte {cfg['parte']}  ·  {CANAL} en YouTube", font(30), (255, 255, 255, 200), anchor="mm")
    im.save(path)

def hook_png(lines, path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = 860
    for k, t in enumerate(lines):
        f = font(118 if k == 0 else 104)
        shadow_text(im, (W // 2, y), t, f, (255, 255, 255, 255) if k == 0 else AMBER, blur=12, alpha=210, anchor="mm")
        y += 130
    im.save(path)

def end_png(path):
    """Cierre: miniatura real del video largo + "Miralo completo en YouTube" + flecha hacia abajo."""
    im = Image.new("RGBA", (W, H), (8, 10, 14, 235))
    th = Image.open(THUMB).convert("RGB").resize((940, 529), Image.LANCZOS)
    m = Image.new("L", th.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, th.width - 1, th.height - 1), radius=28, fill=255)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((70, 640, 1010, 1180), radius=28, fill=(0, 0, 0, 200))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)))
    im.paste(th, (70, 620), m)
    shadow_text(im, (W // 2, 470), "MIRALO COMPLETO", font(84), (255, 255, 255, 255), anchor="mm")
    shadow_text(im, (W // 2, 560), f"en YouTube · {CANAL}", font(46), AMBER, anchor="mm")
    d = ImageDraw.Draw(im)
    cx, y0 = W // 2, 1250
    d.polygon([(cx - 60, y0), (cx + 60, y0), (cx, y0 + 80)], fill=AMBER)
    d.rectangle((cx - 18, y0 - 70, cx + 18, y0), fill=AMBER)
    im.save(path)

def ass_time(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def build(n):
    cfg = SHORTS[n]; slug = cfg["slug"]
    parts, subs, t = [], [], 0.0
    esc = []
    for (kind, src, a, b, o) in cfg["escenas"]:
        a, b = snap(src, a, b)
        if kind == "BROLL" and src == SRC and b - a > 3.8:
            # el celular sale de cuadro a los ~3 s: cortar en el fin de palabra más cercano y volver a la cara
            ws = [w for w in WORDS[SRC] if a + 2.4 < w["e"] < a + 3.6]
            c = ws[-1]["e"] + 0.03 if ws else a + 3.2
            esc += [(kind, src, a, c, o, True), ("CAM", src, c, b, {"z": 1.18}, True)]
        else:
            esc.append((kind, src, a, b, o, True))
    for i, (kind, src, a, b, o, _) in enumerate(esc):
        d = b - a
        out = os.path.join(WK, f"{slug}_p{i:02d}.mkv")
        if kind == "CAM":
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", SRC, "-map", "0:v", "-map", "0:a:0",
                 "-vf", cam_vf(o), "-af", f"{AF},afade=t=in:d=0.02,afade=t=out:st={d - 0.04:.3f}:d=0.04", *ENC, out])
        elif kind == "BROLL":
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{o['va']:.3f}", "-t", f"{d:.3f}", "-i", SRC, "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", src,
                 "-map", "0:v", "-map", "1:a:0", "-vf", cam_vf(o), "-af", f"{AF},afade=t=in:d=0.02", *ENC, out])
        else:  # FOTO
            fr = int(d * FPS) + 2
            lab = os.path.join(WK, f"{slug}_lab{i}.png")
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow_text(im, (W // 2, 1520), o["lab"].upper(), font(64), AMBER, anchor="mm"); im.save(lab)
            run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.join(FOT, o["img"]),
                 "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", src, "-loop", "1", "-framerate", str(FPS), "-i", lab,
                 "-filter_complex",
                 f"[0:v]split=2[f0][f1];[f0]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.18[bgb];"
                 f"[f1]scale={W * 2}:-2,zoompan=z='1+0.06*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{int(W * 3 / 4) // 2 * 2}:fps={FPS}[fg];"
                 f"[bgb][fg]overlay=0:(H-h)/2-60,scale=out_range=tv,format=yuva420p[bg];[bg][2:v]overlay=0:0:shortest=1,format=yuv420p[v];"
                 f"[1:a:0]{AF},afade=t=in:d=0.02[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", *ENC, out])
        for w in WORDS[src]:
            m_ = (w["s"] + w["e"]) / 2
            if a <= m_ < b:
                subs.append((t + max(w["s"], a) - a, t + min(w["e"], b) - a, w["w"].strip()))
        parts.append(out); t += d
    t_end = t
    endp = os.path.join(WK, f"{slug}_end.png"); end_png(endp)
    endv = os.path.join(WK, f"{slug}_end.mkv")
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-t", "3.2", "-i", endp, "-f", "lavfi", "-t", "3.2",
         "-i", "anullsrc=r=48000:cl=stereo", "-vf", f"scale={W}:{H},format=yuv420p,fade=t=in:d=0.25", *ENC, endv])
    parts.append(endv); t += 3.2
    lst = os.path.join(WK, f"{slug}_lista.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '" + x + "'\n" for x in parts))
    cat = os.path.join(WK, f"{slug}_cat.mkv")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", cat])

    # Subtítulos ASS: 1-3 palabras, grandes, al centro-abajo; la clave en serif itálica dorada.
    ass = os.path.join(WK, f"{slug}.ass")
    hdr = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
           "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           "Style: S,Bahnschrift,92,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,5,3,2,60,60,560,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev, cur = [], []
    def flush():
        if not cur: return
        txt = []
        for (_, _, w) in cur:
            w2 = w
            for k, v in FIX.items(): w2 = w2.replace(k, v)
            bare = w2.strip(".,¿?¡!").lower()
            if any(bare == c.lower() for c in cfg["claves"]):
                txt.append("{\\fnGeorgia\\i1\\b1\\c&H42B9F5&}" + w2.upper() + "{\\r}")
            else:
                txt.append(w2.upper())
        ev.append((cur[0][0], cur[-1][1], " ".join(txt)))
    hook_end = None
    for s_ in subs:
        if cur and (len(cur) >= 3 or s_[0] - cur[-1][1] > 0.35 or cur[-1][2][-1:] in ".?!,"):
            flush(); cur.clear()
        cur.append(s_)
    flush()
    with open(ass, "w", encoding="utf-8") as f:
        f.write(hdr)
        for k, (s0, s1, tx) in enumerate(ev):
            e1 = min(s1 + 0.12, ev[k + 1][0] - 0.01) if k + 1 < len(ev) else min(s1 + 0.3, t_end)
            f.write(f"Dialogue: 0,{ass_time(s0)},{ass_time(e1)},S,,0,0,0,,{tx}\n")

    top = os.path.join(WK, f"{slug}_top.png"); top_png(cfg, top)
    hook = os.path.join(WK, f"{slug}_hook.png"); hook_png(cfg["hook_txt"], hook)
    hook_d = min(2.6, (snap(*cfg["escenas"][0][1:4])[1] - snap(*cfg["escenas"][0][1:4])[0]))
    assp = ass.replace("\\", "/").replace(":", "\\:")
    vid = os.path.join(WK, f"{slug}_video.mkv")
    run(["ffmpeg", "-v", "error", "-y", "-reinit_filter", "0", "-i", cat, "-loop", "1", "-framerate", str(FPS), "-t", f"{t_end:.3f}", "-i", top,
         "-loop", "1", "-framerate", str(FPS), "-t", f"{hook_d:.3f}", "-i", hook,
         "-filter_complex",
         f"[0:v]subtitles='{assp}'[s];[1:v]format=rgba,fade=t=out:st={t_end - 0.3:.3f}:d=0.3:alpha=1[tp];"
         f"[2:v]format=rgba,fade=t=out:st={hook_d - 0.25:.3f}:d=0.25:alpha=1[hk];"
         f"[s][tp]overlay=0:0:eof_action=pass[s2];[s2][hk]overlay=0:0:eof_action=pass,format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", vid])
    # Mezcla: voz + música baja con ducking → −14 LUFS
    mix = os.path.join(WK, f"{slug}_mix.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-stream_loop", "-1", "-i", MUSIC, "-filter_complex",
         f"[0:a]{AF},asplit=2[v][k];[1:a]atrim=0:{t:.3f},{AF},highpass=f=70,volume=0.20,afade=t=out:st={t - 1.2:.2f}:d=1.2[m0];"
         f"[m0][k]sidechaincompress=threshold=0.04:ratio=4:attack=25:release=400[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
         f"loudnorm=I=-14:TP=-1.5:LRA=9[o]", "-map", "[o]", "-ar", "48000", mix])
    out = os.path.join(OUT, f"{SLUGP}_short_{slug}.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out])
    # Portada: cuadro del gancho con el texto
    cov = os.path.join(OUT, f"{SLUGP}_short_{slug}_portada.jpg")
    run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", out, "-frames:v", "1", "-q:v", "2", cov])
    print(f"OK {out} · {t:.1f} s")

for n in ([int(sys.argv[2])] if len(sys.argv) > 2 and sys.argv[2] != "all" else SHORTS):   # argv[1] es el proyecto.json
    build(n)

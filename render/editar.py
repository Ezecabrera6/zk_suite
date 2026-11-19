"""Edición de un video largo a partir de un proyecto.json (formato en ejemplos/proyecto/proyecto_ejemplo.json).
uso: python editar.py RUTA/proyecto.json [preview|final]
- preview: 1280x720 rápido · final: 1920x1080 (x264 slow crf 17).
Estructura: gancho (narración sobre un plano de la toma) → logo → cuerpo (tramos KEEP partidos por frase con
encuadre alterno 1.0/1.14, fotos a pantalla completa con narración, rótulos sobrios con panel translúcido) → outro.
Música baja con ducking (feedback del público: la voz manda) y master a −14 LUFS / −1 dBTP.
Variables de entorno (config.example.env): ZK_LOGO, ZK_OUTRO, ZK_MUSICA, ZK_FUENTE. Ver render/README.md.
"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CFG_PATH = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else "preview"
CFG = json.load(open(CFG_PATH, encoding="utf-8"))
P = CFG["proyecto"]
J = lambda *x: os.path.join(P, *x)
rel = lambda s: J(*s.split("/"))
SRC = rel(CFG["toma"])
NARR = {k: rel(v) for k, v in CFG.get("narraciones", {}).items()}
FOT = rel(CFG.get("fotos", "06_material_usuario"))
LOGO = rel(CFG["logo"]) if "logo" in CFG else os.environ.get("ZK_LOGO", "assets/logo_intro_3s.mp4")
OUTRO = rel(CFG["outro"]) if "outro" in CFG else os.environ.get("ZK_OUTRO", "assets/outro.mp4")
MUSIC = CFG.get("musica") or os.environ.get("ZK_MUSICA", "assets/musica.wav")
SLUG = CFG["slug"]
WORK = J("10_work", SLUG, "final"); os.makedirs(WORK, exist_ok=True)
W, H = (1920, 1080) if MODE == "final" else (1280, 720)
S = W / 1920
FPS = 30
FONT_B = os.environ.get("ZK_FUENTE", r"C:\Windows\Fonts\bahnschrift.ttf")
AMBER = (245, 185, 66, 255)
TAG = CFG.get("version", "v001") + ("" if MODE == "final" else "_720p")
OUT = J("11_exports", "final" if MODE == "final" else "previews", f"{SLUG}_{TAG}.mp4")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
A = J("12_project", "analysis")
def load_words(fn):
    return [w for s in json.load(open(os.path.join(A, fn), encoding="utf-8")) for w in s["words"]]
WS = load_words(CFG["transcripcion"])
SEGS = json.load(open(os.path.join(A, CFG["transcripcion"]), encoding="utf-8"))
NW = {NARR[k]: load_words(v) for k, v in CFG.get("transcripciones_narraciones", {}).items()}

def snap(a, b, ws=WS, pre=0.10, post=0.18, tol=0.08):
    sel = [w for w in ws if w["s"] >= a - tol and w["e"] <= b + tol]
    return (max(0, sel[0]["s"] - pre), sel[-1]["e"] + post) if sel else (a, b)

KEEP = [tuple(x) if x != "FOTOS" else "FOTOS" for x in CFG["keep"]]
FOTOS = [(f["img"], NARR[f["narr"]], f["desde"], f["hasta"], f["rotulo"]) for f in CFG.get("fotos_vo", [])]
_h = CFG["gancho"]; HOOK = (NARR[_h["narr"]], _h["desde"], _h["hasta"], _h["plano"])
GFX = [(g["t"], g["dur"], g["tipo"], g.get("c")) for g in CFG.get("graficos", [])]
THUMBS = rel(CFG.get("miniaturas_otros", f"10_work/{SLUG}/thumbs"))
MUS = CFG.get("musica_vol", {"gancho": 0.10, "logo": 0.35, "cuerpo": 0.045, "outro": 0.30})

def run(args, cap=False):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode:
        print(r.stderr[-3000:]); sys.exit(1)
    return r.stderr

def font(sz):
    return ImageFont.truetype(FONT_B, int(sz * S))

def shadow_text(im, xy, text, f, fill, blur=7, alpha=150):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 2 * S), text, font=f, fill=(0, 0, 0, alpha))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur * S)))
    ImageDraw.Draw(im).text(xy, text, font=f, fill=fill)

def bottom_shade(im, h_frac=0.42, alpha=150):
    """Degradé oscuro suave desde abajo a la izquierda (para leer texto sobre la imagen, sin cajas)."""
    import numpy as np
    h = int(im.height * h_frac)
    y = np.linspace(0, 1, h)[:, None] ** 1.1
    x = np.clip(1.15 - np.linspace(0, 1, im.width)[None, :] * 0.9, 0, 1)
    a = (alpha * 1.25 * y * x).clip(0, 255).astype("uint8")
    sh = Image.new("RGBA", (im.width, h), (0, 0, 0, 255)); sh.putalpha(Image.fromarray(a, "L"))
    im.alpha_composite(sh, (0, im.height - h))

def panelize(txt):
    """Panel oscuro translúcido (≈45 %) con bordes difuminados detrás del texto. Sin borde ni color."""
    bb = txt.getbbox()
    if not bb:
        return txt
    pad_x, pad_y = int(34 * S), int(24 * S)
    x0, y0, x1, y1 = bb[0] - pad_x, bb[1] - pad_y, bb[2] + pad_x, bb[3] + pad_y
    m = Image.new("L", txt.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1, y1), radius=int(18 * S), fill=145)
    m = m.filter(ImageFilter.GaussianBlur(10 * S))
    out = Image.new("RGBA", txt.size, (8, 10, 14, 0)); out.putalpha(m)
    out.alpha_composite(txt)
    return out

def mini_png(i, fn, texto, slot):
    """Tarjeta: miniatura de otro video + franja oscura del mismo ancho con el título, esquinas redondeadas y sombra."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    th = Image.open(os.path.join(THUMBS, fn)).convert("RGB")
    tw, thh = th.size
    if tw / thh < 16 / 9:                       # 4:3 con franjas → recorte 16:9
        nh = int(tw * 9 / 16); th = th.crop((0, (thh - nh) // 2, tw, (thh - nh) // 2 + nh)); tw, thh = th.size
    w_ = int(460 * S); h_ = int(w_ * 9 / 16); bar = int(64 * S); r = int(14 * S)
    th = th.resize((w_, h_), Image.LANCZOS)
    x = W - int(80 * S) - w_
    y = int(90 * S) + slot * (h_ + bar + int(40 * S))
    card = Image.new("RGBA", (w_, h_ + bar), (14, 16, 20, 235))
    card.paste(th, (0, 0))
    d = ImageDraw.Draw(card); f = font(30)
    tb = d.textbbox((0, 0), texto, font=f)
    d.text((int(20 * S), h_ + (bar - (tb[3] - tb[1])) // 2 - tb[1]), texto, font=f, fill=(255, 255, 255, 245))
    m = Image.new("L", card.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w_ - 1, h_ + bar - 1), radius=r, fill=255)
    card.putalpha(Image.fromarray(__import__("numpy").minimum(__import__("numpy").array(card.getchannel("A")), __import__("numpy").array(m))))
    sh = Image.new("L", (W, H), 0); ImageDraw.Draw(sh).rounded_rectangle((x, y + int(8 * S), x + w_, y + h_ + bar + int(8 * S)), radius=r, fill=140)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(16 * S)))
    im.alpha_composite(shadow); im.alpha_composite(card, (x, y))
    p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p

def gfx_png(i, kind, c):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    TXT = []
    X = int(96 * S)
    if kind == "sec":          # kicker numérico en ámbar + título; arriba a la izquierda
        shadow_text(im, (X, int(64 * S)), c[0], font(40), AMBER)
        shadow_text(im, (X, int(110 * S)), c[1].upper(), font(84), (255, 255, 255, 245))
    elif kind == "dato":       # dato clave abajo a la izquierda
        shadow_text(im, (X, H - int(222 * S)), c[0], font(72), AMBER)
        shadow_text(im, (X, H - int(132 * S)), c[1], font(42), (255, 255, 255, 240))
    elif kind == "resumen":
        pros, cons = c["bueno"], c["malo"]
        y0 = H - int(400 * S)
        shadow_text(im, (X, y0), "LO BUENO", font(30), AMBER)
        shadow_text(im, (W // 2 + X // 2, y0), "LO MALO", font(30), (255, 140, 120, 255))
        for k, t in enumerate(pros):
            shadow_text(im, (X, y0 + int((50 + 52 * k) * S)), t, font(38), (255, 255, 255, 240))
        for k, t in enumerate(cons):
            shadow_text(im, (W // 2 + X // 2, y0 + int((50 + 52 * k) * S)), t, font(38), (255, 255, 255, 240))
    elif kind == "precio":
        y0 = H - int(260 * S)
        for k, (a_, b_) in enumerate(c):
            shadow_text(im, (X, y0 + int(84 * k * S)), a_, font(34), (255, 255, 255, 220))
            shadow_text(im, (X + int(300 * S), y0 + int(84 * k * S) - int(6 * S)), b_, font(44), AMBER if k == 0 else (255, 255, 255, 245))
    elif kind == "veredicto":
        rows = c
        y0 = H - int(330 * S)
        for k, (q, r) in enumerate(rows):
            shadow_text(im, (X, y0 + int(92 * k * S)), q, font(32), (255, 255, 255, 215))
            shadow_text(im, (X, y0 + int((92 * k + 38) * S)), r, font(42), AMBER)
    if kind == "mini":
        return mini_png(i, *c)
    if kind == "numero":       # puesto del ranking: número gigante centrado sobre velo oscuro; c = ["3", "3.er LUGAR · CON 300 MIL"]
        im = Image.new("RGBA", (W, H), (6, 8, 12, 150))
        fN, fS = font(560), font(56)
        d = ImageDraw.Draw(im)
        bb = d.textbbox((0, 0), c[0], font=fN); tw = bb[2] - bb[0]
        shadow_text(im, ((W - tw) // 2 - bb[0], int(H * 0.40) - (bb[3] - bb[1]) // 2 - bb[1]), c[0], fN, AMBER, blur=14, alpha=200)
        bb = d.textbbox((0, 0), c[1], font=fS); tw = bb[2] - bb[0]
        shadow_text(im, ((W - tw) // 2, int(H * 0.78)), c[1], fS, (255, 255, 255, 245))
        p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p
    if kind == "clave":        # dato clave grande y centrado (estilo guía de compra): c = ["256 GB"]
        f_ = font(150); d = ImageDraw.Draw(im)
        bb = d.textbbox((0, 0), c[0], font=f_, stroke_width=int(4 * S)); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x, y = (W - tw) // 2 - bb[0], int(H * 0.42) - th // 2 - bb[1]
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x, y + int(6 * S)), c[0], font=f_, fill=(0, 0, 0, 190))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16 * S)))
        ImageDraw.Draw(im).text((x, y), c[0], font=f_, fill=(255, 255, 255, 255), stroke_width=int(4 * S), stroke_fill=(20, 20, 20, 255))
        im = panelize(im)   # panel oscuro: se lee sobre fondos blancos (capturas de tiendas)
        p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p
    if kind == "recap":        # resumen final por perfil: c = [["título", "modelo"], ...]
        y0 = int(H * 0.18); X2 = int(W * 0.18)
        shadow_text(im, (X2, y0 - int(90 * S)), "MI ELECCIÓN", font(52), AMBER)
        for k, (a_, b_) in enumerate(c):
            shadow_text(im, (X2, y0 + int(k * 140 * S)), a_, font(40), (220, 224, 230, 240))
            shadow_text(im, (X2, y0 + int((k * 140 + 46) * S)), b_, font(70), (255, 255, 255, 250))
        im = panelize(im)
        p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p
    if kind == "captura":      # captura a pantalla completa: fondo desenfocado de la misma imagen + captura centrada con sombra
        cap = Image.open(rel(c[0])).convert("RGB")
        bgi = cap.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40 * S)).point(lambda v: int(v * 0.45))
        im = bgi.convert("RGBA")
        k = min(W * 0.88 / cap.width, H * 0.80 / cap.height)
        cw, chh = int(cap.width * k), int(cap.height * k)
        x, y = (W - cw) // 2, (H - chh) // 2 - int(30 * S)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((x, y + int(12 * S), x + cw, y + chh + int(12 * S)), int(16 * S), fill=(0, 0, 0, 170))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18 * S)))
        m = Image.new("L", (cw, chh), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, chh - 1), int(16 * S), fill=255)
        im.paste(cap.resize((cw, chh), Image.LANCZOS), (x, y), m)
        p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p
    im = panelize(im)
    p = os.path.join(WORK, f"gfx{i:02d}.png"); im.save(p); return p

def label_png(i, text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bottom_shade(im, 0.22, 90)
    shadow_text(im, (int(96 * S), H - int(96 * S)), text, font(34), (255, 255, 255, 235))
    p = os.path.join(WORK, f"lab{i:02d}.png"); im.save(p); return p

# ---------- Línea de tiempo ----------
# Cada tramo de la toma principal se parte en las fronteras de frase en bloques de 6-14 s
# y se alterna el encuadre (plano general / plano cerrado) para que algo cambie cada pocos segundos.
def chunks(a, b):
    cuts = [s["start"] for s in SEGS if a + 5.5 < s["start"] < b - 4.0]
    out, cur = [], a
    for c in cuts:
        if c - cur >= 6.0:
            out.append((cur, c)); cur = c
    out.append((cur, b))
    if len(out) > 1 and out[-1][1] - out[-1][0] < 4.0:
        out[-2] = (out[-2][0], out[-1][1]); out.pop()
    return out

INTER = (["-c:v", "libx264", "-preset", "veryfast", "-crf", "12"] if MODE == "final" else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"])
INTER += ["-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
AUD = ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
VBASE = f"fps={FPS},scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p"
parts, src2edit, vo_subs = [], [], []
def add_vo(ws, a, b, te):
    for w in ws:
        if a <= w['s'] and w['e'] <= b + 0.05:
            vo_subs.append((te + w['s'] - a, te + w['e'] - a, w['w'].strip()))

t_edit = 0.0

def punch(z):
    if z == 1.0:
        return ""
    cw, ch = int(1920 / z) // 2 * 2, int(1080 / z) // 2 * 2
    x, y = (1920 - cw) // 2, max(0, min(1080 - ch, int(1080 * 0.40 - ch / 2)))
    return f"crop={cw}:{ch}:{x}:{y},"

import hashlib
def part(args_in, fc, d):
    global t_edit
    out = os.path.join(WORK, f"p{len(parts):03d}_{MODE}.mkv")
    key = hashlib.md5(repr((args_in, fc, d, INTER)).encode()).hexdigest()
    if os.path.exists(out) and os.path.exists(out + ".key") and open(out + ".key").read() == key:
        parts.append(out); t_edit += d; return
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args_in, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-t", f"{d:.3f}", *INTER, "-r", str(FPS), *AUD, out])
    open(out + ".key", "w").write(key)
    parts.append(out); t_edit += d

AF = "aformat=sample_rates=48000:channel_layouts=stereo"
# Gancho
nv, na_, nb_, va = HOOK
na_, nb_ = snap(na_, nb_, NW[nv], pre=0.06, post=0.25, tol=0.3)
d = nb_ - na_ + 0.35
add_vo(NW[nv], na_, nb_, t_edit)
part(["-ss", f"{va}", "-t", f"{d:.3f}", "-i", SRC, "-ss", f"{na_:.3f}", "-t", f"{d:.3f}", "-i", nv],
     f"[0:v]{punch(1.12)}{VBASE},fade=t=in:d=0.2[v];[1:a:0]{AF},afade=t=in:d=0.03,afade=t=out:st={d - 0.15:.3f}:d=0.15[a]", d)
t_logo = t_edit
part(["-i", LOGO], f"[0:v]{VBASE}[v];[0:a]{AF}[a]", 3.0)
t_body = t_edit

zoom_toggle = False
for r in KEEP:
    if r == "FOTOS":
        for k, (foto, vo, a, b, txt) in enumerate(FOTOS):
            a, b = snap(a, b, NW[vo], pre=0.06, post=0.15, tol=0.3)
            d = b - a + 0.6
            fr = int(d * FPS) + 2
            add_vo(NW[vo], a, b, t_edit)
            part(["-loop", "1", "-framerate", str(FPS), "-i", os.path.join(FOT, foto), "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", vo,
                  "-loop", "1", "-framerate", str(FPS), "-i", label_png(k, txt)],
                 f"[0:v]scale=3840:-2,crop=3840:2160,zoompan=z='1+0.07*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                 f"d=1:s={W}x{H}:fps={FPS},setsar=1,format=yuva420p[pf];[2:v]format=rgba,fade=t=in:st=0.3:d=0.3:alpha=1[pl];"
                 f"[pf][pl]overlay=0:0:shortest=1,fade=t=in:d=0.2,fade=t=out:st={d - 0.2:.3f}:d=0.2,scale=out_range=tv,format=yuv420p[v];"
                 f"[1:a:0]{AF},afade=t=in:d=0.03,afade=t=out:st={d - 0.1:.3f}:d=0.1[a]", d)
        continue
    if len(r) > 3 and r[3] == "exacto":   # tramo ya medido sobre el audio (silencios reales): no se ajusta a las palabras
        a, b = r[0], r[1]
    else:
        a, b = snap(r[0], r[1], pre=r[2] if len(r) > 2 else 0.10)  # 3.er valor opcional: aire antes del tramo (palabras pegadas)
    ch_ = chunks(a, b)
    for j, (ca, cb) in enumerate(ch_):
        z = 1.14 if zoom_toggle else 1.0
        zoom_toggle = not zoom_toggle
        d = cb - ca
        af = AF + (",afade=t=in:d=0.03" if j == 0 else "") + (f",afade=t=out:st={d - 0.05:.3f}:d=0.05" if j == len(ch_) - 1 else "")
        src2edit.append((ca, cb, t_edit))
        part(["-ss", f"{ca:.3f}", "-t", f"{d:.3f}", "-i", SRC], f"[0:v]{punch(z)}{VBASE}[v];[0:a:0]{af}[a]", d)
t_outro = t_edit
part(["-i", OUTRO], f"[0:v]{VBASE}[v];[0:a]{AF}[a]", 5.883)

lst = os.path.join(WORK, f"lista_{MODE}.txt")
open(lst, "w", encoding="utf-8").write("".join("file '" + x + "'" + chr(10) for x in parts))
cat = os.path.join(WORK, f"concat_{MODE}.mkv")
run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", cat])
inputs = [cat]
def add_input(path):
    inputs.append(("IMG", path, dur_, te_)); return len(inputs) - 1
fc = []

def edit_t(ts):
    for a, b, te in src2edit:
        if a <= ts <= b:
            return te + ts - a
    return None

cur = "0:v"
chapters = []
for i, (ts, dur, kind, c) in enumerate(GFX):
    te = edit_t(ts)
    if te is None:
        print("rótulo fuera del corte:", ts, kind); continue
    if kind == "sec":
        chapters.append((te, c[1]))
    dur_, te_ = dur, te
    if kind == "clip":   # b-roll de video a pantalla completa: c = [ruta, segundo de inicio, zoom]; la voz sigue debajo
        inputs.append(("CLIP", rel(c[0]), dur, te, c[1]))
        gi = len(inputs) - 1
        z = c[2] if len(c) > 2 else 1.0
        fc.append(f"[{gi}:v]scale={int(W * z) // 2 * 2}:{int(H * z) // 2 * 2}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},"
                  f"format=yuva420p,setpts=PTS+{te:.3f}/TB,fade=t=in:st={te:.3f}:d=0.15:alpha=1,fade=t=out:st={te + dur - 0.15:.3f}:d=0.15:alpha=1[g{i}]")
        fc.append(f"[{cur}][g{i}]overlay=0:0:eof_action=pass:format=auto[o{i}]")
        cur = f"o{i}"
        continue
    gi = add_input(gfx_png(i, kind, c))
    fc.append(f"[{gi}:v]format=rgba,fade=t=in:st={te:.3f}:d=0.25:alpha=1,fade=t=out:st={te + dur - 0.3:.3f}:d=0.3:alpha=1[g{i}]")
    fc.append(f"[{cur}][g{i}]overlay=0:0:eof_action=pass:format=auto[o{i}]")
    cur = f"o{i}"
fc.append(f"[{cur}]format=yuv420p[vout]")
fc_ok = True

graph = os.path.join(WORK, f"graph_{MODE}.txt")
open(graph, "w", encoding="utf-8").write(";\n".join(fc))
args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
for x in inputs:
    if isinstance(x, tuple) and x[0] == "CLIP":
        args += ["-ss", f"{x[4]:.3f}", "-t", f"{x[2]:.3f}", "-i", x[1]]
    elif isinstance(x, tuple):
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{x[2]:.3f}", "-itsoffset", f"{x[3]:.3f}", "-i", x[1]]
    else:
        args += ["-i", x]
venc = (["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p"] if MODE == "final"
        else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"])
voice = os.path.join(WORK, f"voz_{MODE}.wav")
tmpv = os.path.join(WORK, f"video_{MODE}.mp4")
print(f"partes {len(parts)} · duración {t_edit:.1f} s · render {MODE}…", flush=True)
run(args + ["-filter_complex_script", graph, "-map", "[vout]", "-map", "0:a", *venc, "-r", str(FPS),
            "-c:a", "pcm_s16le", "-f", "matroska", tmpv.replace(".mp4", ".mkv")])

# ---------- Mezcla: voz + música con ducking → −14 LUFS ----------
dur = t_edit
vol = (f"if(lt(t,{t_logo:.2f}),{MUS['gancho']},if(lt(t,{t_body + 0.5:.2f}),{MUS['logo']},if(lt(t,{t_outro - 1:.2f}),{MUS['cuerpo']},{MUS['outro']})))")
mix = os.path.join(WORK, f"mix_{MODE}.wav")
run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmpv.replace(".mp4", ".mkv"), "-stream_loop", "-1", "-i", MUSIC,
     "-filter_complex",
     f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voz][key];"
     f"[1:a]atrim=0:{dur:.3f},aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=80,lowpass=f=9000,equalizer=f=2500:t=q:w=1.2:g=-6,"
     f"volume='{vol}':eval=frame,afade=t=in:d=0.4,afade=t=out:st={dur - 2:.2f}:d=2[m0];"
     f"[m0][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=500[mus];"
     f"[voz][mus]amix=inputs=2:duration=first:normalize=0[mx]",
     "-map", "[mx]", "-c:a", "pcm_f32le", mix])
st = run(["ffmpeg", "-hide_banner", "-nostats", "-i", mix, "-af", "loudnorm=print_format=json", "-f", "null", "-"])
m = json.loads(re.findall(r"\{[^{}]*\}", st, re.S)[-1])
gain = -14.0 - float(m["input_i"])
run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmpv.replace(".mp4", ".mkv"), "-i", mix, "-map", "0:v", "-map", "1:a",
     "-c:v", "copy", "-af", f"volume={gain:.2f}dB,aresample=192000,alimiter=limit=0.80:attack=2:release=60:level=disabled,aresample=48000",
     "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", OUT])
st = run(["ffmpeg", "-hide_banner", "-nostats", "-i", OUT, "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"])
f = json.loads(re.findall(r"\{[^{}]*\}", st, re.S)[-1])
print(f"final {f['input_i']} LUFS · TP {f['input_tp']} dBTP")
json.dump({"chapters": [(0.0, "Gancho")] + [(round(t, 2), c) for t, c in chapters], "t_body": t_body, "t_outro": t_outro,
           "src2edit": src2edit, "vo_subs": vo_subs, "dur": dur}, open(os.path.join(WORK, f"timeline_{MODE}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OK", OUT)

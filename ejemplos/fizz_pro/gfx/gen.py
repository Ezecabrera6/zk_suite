"""Overlays del unboxing Redragon Fizz Pro, v2 (10/11/2026): UN solo estilo limpio tipo SupraPixel.
Se rechazó la v1 (sticker zk_style amarillo condensado con contorno, sellos y pastillas: «cutre y hecho con IA»;
queda en gen_v1_sticker.py). Reglas: Bahnschrift SemiBold blanca sin contorno; bajada gris 28 px; panel #14161A al
80 %, radio 12, sin borde ni brillo; un solo acento #FFC531 por gráfico (barra de 5 px o el número); siempre arriba a
la izquierda con margen de 64 px; entrada y salida de 180 ms deslizando 30 px con fundido, sin rebote ni escala.
Cada gráfico: PNG 1920x1080 con alfa (en reposo) + MOV qtrle argb. Todo se dibuja en capas y se compone con
alpha_composite (lección del Carrito, v030). Uso: python gen.py [prefijo ...]   (sin argumentos, todos)"""
import os, sys, subprocess, functools
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import objetos as O

W, H, FPS = 1920, 1080, 30
OUT = Path(os.environ.get("ZK_GFX_OUT", "10_work/gfx"))   # carpeta de salida de los gráficos
FF = os.environ.get("ZK_FFMPEG", "ffmpeg")
THUMB = OUT / "_ref" / "miniatura.jpg"          # miniatura del video al que apunta la tarjeta
BAHN = "C:/Windows/Fonts/bahnschrift.ttf"
PANEL = (20, 22, 26, 204)            # #14161A al 80 %
WHITE, GREY, AMBER = (255, 255, 255, 255), (184, 188, 196, 255), (255, 197, 49, 255)   # acento #FFC531
M, R, BAR = 64, 12, 5                # margen, radio, barra de acento
PX, PY = 26, 18                      # relleno del panel
MAIN, SUB = 54, 28
ANIM, SLIDE = 0.18, 30


@functools.lru_cache(maxsize=None)
def font(size, var=b"SemiBold"):
    f = ImageFont.truetype(BAHN, size); f.set_variation_by_name(var); return f


def tw(s, size): return font(size).getlength(s)


def panel(w, h, bar=True):
    """Panel pizarra + sombra muy suave; la barra ámbar a la izquierda es el acento (si el gráfico no usa otro)."""
    pad = 40; L = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", L.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 6, pad + w, pad + h + 6), R, fill=(0, 0, 0, 70))
    L.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    top = Image.new("RGBA", L.size, (0, 0, 0, 0)); d = ImageDraw.Draw(top)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), R, fill=PANEL)
    if bar: d.rounded_rectangle((pad + 12, pad + 16, pad + 12 + BAR, pad + h - 16), 2, fill=AMBER)
    L.alpha_composite(top)
    return L, pad


def frame_with(L, pad):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); img.alpha_composite(L, (M - pad, M - pad)); return img


def text_panel(lines, bar=True):
    """lines: [(texto, tamaño, color)] o [[(seg, tamaño, color), ...]] para mezclar colores en un renglón.
    Cada renglón se dibuja en su capa y se compone (ImageDraw directo sobre el panel translúcido pisaría el alfa)."""
    lines = [l if isinstance(l, list) else [l] for l in lines]
    x0 = PX + (BAR + 14 if bar else 0)
    hs = [max(int(sz * 1.22) for _, sz, _ in ln) for ln in lines]
    w = int(x0 + max(sum(tw(s, sz) for s, sz, _ in ln) for ln in lines) + PX); h = PY * 2 + sum(hs) - 4
    L, pad = panel(w, h, bar); txt = Image.new("RGBA", L.size, (0, 0, 0, 0)); d = ImageDraw.Draw(txt); y = pad + PY
    for ln, lh in zip(lines, hs):
        x = pad + x0
        for s, sz, col in ln:
            d.text((x, y + lh / 2), s, font=font(sz), fill=col, anchor="lm"); x += tw(s, sz)
        y += lh
    L.alpha_composite(txt)
    return frame_with(L, pad)


# ---------------------------------------------------------------------------------------------------- gráficos
def g60_panel(t): return text_panel([("60 %", 60, WHITE), ("sin numérico ni flechas", SUB, GREY)])
def gswitch_panel(t): return text_panel([("Switch red", MAIN, WHITE), ("menos ruidoso que el blue", SUB, GREY)])
def gmodos_panel(t): return text_panel([("2.4G · BT · Cable", MAIN, WHITE), ("tres formas de conectarlo", SUB, GREY)])
def gprecio(t): return text_panel([("$60.000 – $70.000", MAIN, WHITE), ("precio actual", SUB, GREY)])
def gnopubli(t): return text_panel([("Lo compré yo", MAIN, WHITE), ("no es publicidad", SUB, GREY)])
def gmalo(t): return text_panel([[("— ", 48, AMBER), ("Sin flechas", 48, WHITE)], [("— ", 48, AMBER), ("Sin F1–F12", 48, WHITE)]], bar=False)
def gkvm(t): return text_panel([("¿Un switch para pasar", 46, WHITE), ("de PC con un botón?", 46, WHITE), ("contame en los comentarios", SUB, GREY)])


def gsec(n, name):
    def f(t): return text_panel([[(f"{n:02d}", 46, AMBER), (" · ", 46, GREY), (name, 46, WHITE)]], bar=False)
    return f


def gfn_panel(t):
    """(v2, ya no se usa) Dos teclas dibujadas simples (contorno gris claro, sin brillo) + bajada."""
    kh, gap = 74, 18; keys = [("Fn", 96), ("+", None), ("F9", 74)]
    x0 = PX + BAR + 14; h = PY * 2 + kh + 12 + int(SUB * 1.22)
    w = int(max(x0 + 96 + gap + tw("+", 44) + gap + 74 + PX, x0 + tw("cambia las luces", SUB) + PX))
    L, pad = panel(w, h); top = Image.new("RGBA", L.size, (0, 0, 0, 0)); d = ImageDraw.Draw(top); x = pad + x0; y = pad + PY
    for lab, kw in keys:
        if kw is None:
            d.text((x, y + kh / 2), lab, font=font(44), fill=GREY, anchor="lm"); x += tw(lab, 44) + gap; continue
        d.rounded_rectangle((x, y, x + kw, y + kh), 10, fill=(255, 255, 255, 18), outline=GREY, width=2)
        d.text((x + kw / 2, y + kh / 2 - 2), lab, font=font(36), fill=WHITE, anchor="mm"); x += kw + gap
    d.text((pad + x0, y + kh + 12 + SUB * 0.61), "cambia las luces", font=font(SUB), fill=GREY, anchor="lm")
    L.alpha_composite(top)
    return frame_with(L, pad)


def gtiempo(t):
    """Indicador chico; el acento es el punto ámbar que titila."""
    s = "Tiempo real"; dot = 14; w = int(PX + dot + 14 + tw(s, 44) + PX); h = PY * 2 + 52
    L, pad = panel(w, h, bar=False); top = Image.new("RGBA", L.size, (0, 0, 0, 0)); d = ImageDraw.Draw(top); cy = pad + h / 2
    a = 255 if (t % 1.0) < 0.6 else 70
    d.ellipse((pad + PX, cy - dot / 2, pad + PX + dot, cy + dot / 2), fill=AMBER[:3] + (a,))
    d.text((pad + PX + dot + 14, cy), s, font=font(44), fill=WHITE, anchor="lm")
    L.alpha_composite(top)
    return frame_with(L, pad)


@functools.lru_cache(maxsize=1)
def _card():
    tw_, th_ = 432, 243; sh_ = 96; w, h = tw_, th_ + sh_
    L, pad = panel(w, h, bar=False)
    thumb = Image.open(THUMB).convert("RGBA").resize((tw_, th_), Image.LANCZOS)
    mask = Image.new("L", (tw_, th_), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw_, th_ + R), R, fill=255)   # solo esquinas de arriba
    L.paste(thumb, (pad, pad), mask)
    top = Image.new("RGBA", L.size, (0, 0, 0, 0)); d = ImageDraw.Draw(top)
    d.rounded_rectangle((pad + 14, pad + th_ + 18, pad + 14 + BAR, pad + h - 18), 2, fill=AMBER)
    d.text((pad + 14 + BAR + 14, pad + th_ + 18 + 15), "Así te ESTAFAN en el", font=font(28), fill=WHITE, anchor="lm")
    d.text((pad + 14 + BAR + 14, pad + th_ + 18 + 46), "CyberMonday 2026", font=font(28), fill=WHITE, anchor="lm")
    L.alpha_composite(top)
    return frame_with(L, pad)


def gcard(t): return _card()


# ---------------------------------------------------------------------------------------------------- catálogo
S = lambda f, t, v: [{"archivo": f"sfx/{f}", "t": t, "vol": v}]
WHOOSH = lambda: S("air_woosh_1489.mp3", -0.1, 0.07)
CLICK = lambda: S("dry_pop_2356.mp3", 0.0, 0.08)
POS = "arriba a la izquierda, margen 64 px (mismo lugar en todos)"
OBJPOS = "arriba a la izquierda (x 60–780, y 50–430), objeto grande con el texto abajo"
OBJ = {"g01_60_por_ciento", "g02_switch_red", "g03_modos", "g04_fn_f9", "g12_like_suscribite", "g13_vamos_por_3000"}
SECS = ["Unboxing", "Accesorios", "Luces", "Conexiones", "Prueba de sonido", "Lo malo", "Veredicto"]
G = [  # id, función, dur, hold (cuadro del PNG), posición, sfx (como mucho uno, suave)
    # objetos dibujados (v3, línea del g04 de la v1 que le encantó al creador): render propio con pop y salida de 0,25 s
    ("g01_60_por_ciento", O.g60, 4.5, 2.4, OBJPOS, S("dry_pop_2356.mp3", 1.35, 0.08)),
    ("g02_switch_red", O.gswitch, 4.0, 1.4, OBJPOS, S("dry_pop_2356.mp3", 0.85, 0.08)),
    ("g03_modos", O.gmodos, 4.0, 1.5, OBJPOS, S("dry_pop_2356.mp3", 0.0, 0.08)),
    ("g04_fn_f9", O.v1.gfn, 4.5, 1.2, OBJPOS, S("dry_pop_2356.mp3", 0.85, 0.08)),
    ("g05_precio", gprecio, 4.0, 1.0, POS, CLICK()),
    ("g06_no_es_publicidad", gnopubli, 3.5, 1.0, POS, CLICK()),
    ("g07_lo_malo", gmalo, 4.0, 1.0, POS, CLICK()),
    ("g08_tiempo_real", gtiempo, 10.0, 0.5, POS + "; el punto titila, se puede cortar en cualquier momento", S("dry_pop_2356.mp3", 0.0, 0.06)),
] + [(f"g09_seccion_{i + 1}_{n.lower().replace(' ', '_')}", gsec(i + 1, n), 2.5, 1.0, POS, WHOOSH()) for i, n in enumerate(SECS)] + [
    ("g10_tarjeta_cybermonday", gcard, 5.0, 1.0, POS + " (x 64–496, y 64–403)", WHOOSH()),
    ("g11_idea_kvm", gkvm, 5.5, 1.0, POS, CLICK()),
    # cierre (toma 1229–1236 s: «denme like, suscríbanse. Estamos a nada de los 3000»), línea objeto del g04
    ("g12_like_suscribite", O.glike, 3.5, 2.2, OBJPOS.replace("y 50–430", "y 50–330"), S("classic_click_1117.mp3", 1.35, 0.08)),
    ("g13_vamos_por_3000", O.g3000, 3.5, 2.0, OBJPOS.replace("y 50–430", "y 50–350"), S("dry_pop_2356.mp3", 0.0, 0.08)),
]


def motion(img, t, dur):
    """Entrada y salida iguales: 180 ms, 30 px desde la izquierda con fundido, ease-out sin rebote."""
    k = max(0.0, min(1.0, t / ANIM, (dur - 1 / FPS - t) / ANIM))   # el último cuadro sale vacío
    if k >= 1: return img
    e = 1 - (1 - k) ** 3
    im = img.copy(); im.putalpha(img.getchannel("A").point(lambda v: int(v * e)))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0)); out.alpha_composite(im.crop((int(SLIDE * (1 - e)), 0, W, H)), (0, 0))
    return out


def render(gid, fn, dur, hold):
    fn(hold).save(OUT / f"{gid}.png")
    p = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "qtrle", "-pix_fmt", "argb", str(OUT / f"{gid}.mov")], stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)):
        t = i / FPS; p.stdin.write(motion(fn(t), t, dur).tobytes())
    p.stdin.close(); assert p.wait() == 0, gid


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for gid, fn, dur, hold, pos, sfx in G:
        if want and not any(gid.startswith(w) for w in want): continue
        (O.v1.render if gid in OBJ else render)(gid, fn, dur, hold); print("ok", gid, flush=True)

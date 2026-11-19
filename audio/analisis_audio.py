"""Análisis de audio de voz contra el estándar «sonido pro» del canal (objetivos en OBJ, abajo).
Para cada archivo mide loudness, picos, rango, piso de ruido, ancho de banda y balance por bandas, y dibuja
la forma de onda y el espectrograma (sin matplotlib: numpy + PIL).
uso: python analisis_audio.py salida.png "Nombre|archivo" ["Nombre2|archivo2" ...]
"""
import sys, os, json, re, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 48000
FB = r"C:\Windows\Fonts\bahnschrift.ttf"
BANDAS = [(20, 80, "sub"), (80, 250, "cuerpo"), (250, 500, "barro"), (500, 2000, "medios"), (2000, 5000, "inteligib."),
          (5000, 8000, "presencia/s"), (8000, 12000, "brillo"), (12000, 20000, "aire")]
# objetivos (voz a cámara/narración, entregada para YouTube/Reels/TikTok)
OBJ = {"I": (-15, -13), "TP": (-99, -1.0), "LRA": (3, 9), "piso": (-99, -55), "banda": (12000, 99999)}

def cargar(f):
    tmp = tempfile.mktemp(suffix=".f32")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", tmp], check=True)
    x = np.fromfile(tmp, dtype=np.float32); os.remove(tmp); return x

def ebur(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    s = r[r.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", s).group(1).replace("-inf", "-99"))
    return g("I"), g("LRA"), g("Peak")

def medir(x):
    h = int(SR * 0.05); n = len(x) // h
    rms = 20 * np.log10(np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
    voz = rms > np.percentile(rms, 70) - 20
    piso = float(np.percentile(rms, 5))                     # lo más bajo: pausas
    pico = float(20 * np.log10(np.abs(x).max() + 1e-9))
    # espectro promedio de las partes con voz
    seg = x[:n * h].reshape(n, h)[voz].reshape(-1)
    win = 4096; m = len(seg) // win
    S = np.abs(np.fft.rfft(seg[:m * win].reshape(m, win) * np.hanning(win), axis=1)) ** 2
    P = S.mean(0); fr = np.fft.rfftfreq(win, 1 / SR)
    tot = P[(fr >= 20) & (fr < 20000)].sum()
    bandas = {nm: 100 * P[(fr >= a) & (fr < b)].sum() / tot for a, b, nm in BANDAS}
    # ancho de banda: hasta dónde hay energía a menos de 50 dB del máximo (suavizado)
    Pd = 10 * np.log10(np.convolve(P, np.ones(9) / 9, "same") + 1e-20); top = Pd[(fr > 100) & (fr < 5000)].max()
    ok = np.where((Pd > top - 50) & (fr < 20000))[0]; banda = float(fr[ok.max()]) if len(ok) else 0
    return dict(piso=piso, pico=pico, banda=banda, bandas=bandas)

def colormap(v):   # 0..1 → RGB (negro → violeta → naranja → amarillo)
    stops = np.array([[0, 0, 4], [60, 15, 110], [180, 50, 110], [250, 140, 40], [252, 250, 160]], float)
    v = np.clip(v, 0, 1) * (len(stops) - 1); i = np.minimum(v.astype(int), len(stops) - 2); t = (v - i)[..., None]
    return (stops[i] * (1 - t) + stops[i + 1] * t).astype(np.uint8)

def dibujar(x, w=1400, hw=180, hs=300):
    im = Image.new("RGB", (w, hw + hs + 10), (14, 16, 20)); d = ImageDraw.Draw(im)
    # forma de onda (escala lineal) con líneas de -1, -6 y -12 dBFS
    n = len(x) // w; blk = np.abs(x[:n * w].reshape(w, n)); mx = blk.max(1); rm = np.sqrt((blk ** 2).mean(1))
    for db, c in [(-1, (200, 60, 60)), (-6, (120, 120, 60)), (-12, (60, 90, 60))]:
        y = 10 ** (db / 20) * (hw / 2 - 4); d.line((0, hw / 2 - y, w, hw / 2 - y), fill=c); d.line((0, hw / 2 + y, w, hw / 2 + y), fill=c)
    for i in range(w):
        a = mx[i] * (hw / 2 - 4); b = rm[i] * (hw / 2 - 4)
        d.line((i, hw / 2 - a, i, hw / 2 + a), fill=(70, 130, 200)); d.line((i, hw / 2 - b, i, hw / 2 + b), fill=(150, 200, 255))
    # espectrograma 0–20 kHz (escala log en frecuencia), ventana de 20 ms
    win = 1024; hop = max(1, len(x) // w)
    frames = [x[i:i + win] * np.hanning(win) for i in range(0, len(x) - win, hop)][:w]
    S = 20 * np.log10(np.abs(np.fft.rfft(np.array(frames), axis=1)) + 1e-9); fr = np.fft.rfftfreq(win, 1 / SR)
    fy = np.logspace(np.log10(50), np.log10(20000), hs)[::-1]
    idx = np.searchsorted(fr, fy).clip(0, len(fr) - 1)
    Z = S[:, idx].T; Z = (Z - (Z.max() - 80)) / 80
    sp = Image.fromarray(colormap(Z)).resize((w, hs)); im.paste(sp, (0, hw + 10))
    f = ImageFont.truetype(FB, 14)
    for hz in (100, 250, 500, 1000, 2000, 5000, 8000, 12000):
        y = hw + 10 + int(np.argmin(np.abs(fy - hz)))
        d.line((0, y, 18, y), fill=(255, 255, 255)); d.text((22, y - 8), f"{hz // 1000}k" if hz >= 1000 else str(hz), font=f, fill=(255, 255, 255))
    return im

def estado(k, v):
    lo, hi = OBJ[k]; return "OK" if lo <= v <= hi else "MAL"

def main():
    salida, items = sys.argv[1], sys.argv[2:]
    paneles, filas = [], []
    for it in items:
        nombre, f = it.split("|", 1) if "|" in it else (os.path.basename(it), it)
        x = cargar(f); I, LRA, TP = ebur(f); m = medir(x)
        fila = dict(nombre=nombre, I=I, TP=TP, LRA=LRA, **{k: m[k] for k in ("piso", "pico", "banda")}, bandas=m["bandas"])
        filas.append(fila)
        im = dibujar(x[: SR * 30]); hdr = Image.new("RGB", (im.width, 120), (24, 26, 32)); d = ImageDraw.Draw(hdr)
        F = ImageFont.truetype(FB, 24); f2 = ImageFont.truetype(FB, 17)
        d.text((14, 8), nombre, font=F, fill=(245, 185, 66))
        txt = (f"Volumen {I:.1f} LUFS [{estado('I', I)}]   Pico real {TP:.1f} dBTP [{estado('TP', TP)}]   "
               f"Rango LRA {LRA:.1f} LU [{estado('LRA', LRA)}]   Piso de ruido {m['piso']:.0f} dBFS [{estado('piso', m['piso'])}]   "
               f"Llega hasta {m['banda'] / 1000:.1f} kHz [{estado('banda', m['banda'])}]")
        d.text((14, 44), txt, font=f2, fill=(235, 235, 235))
        d.text((14, 76), "Bandas: " + "  ".join(f"{k} {v:.0f}%" for k, v in m["bandas"].items()), font=f2, fill=(170, 175, 185))
        p = Image.new("RGB", (im.width, im.height + 120)); p.paste(hdr, (0, 0)); p.paste(im, (0, 120)); paneles.append(p)
    tot = Image.new("RGB", (paneles[0].width, sum(p.height + 12 for p in paneles)), (8, 9, 12)); y = 0
    for p in paneles: tot.paste(p, (0, y)); y += p.height + 12
    tot.save(salida)
    json.dump(filas, open(os.path.splitext(salida)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in filas:
        print(f"{r['nombre']:<28} I {r['I']:6.1f}  TP {r['TP']:5.1f}  LRA {r['LRA']:4.1f}  piso {r['piso']:5.0f}  banda {r['banda'] / 1000:4.1f}k  "
              + " ".join(f"{k}:{v:.0f}" for k, v in r["bandas"].items()))

if __name__ == "__main__": main()

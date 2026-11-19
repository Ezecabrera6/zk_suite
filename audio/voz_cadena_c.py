"""Voz lista para el render: una pista del micrófono de la toma de OBS → mono 48 kHz → adeclip + reducción de ruido +
«cadena C» (EQ, compresor suave, de-esser). Sin normalizar: el render nivela a −14 LUFS.
Sin compuerta: los ruidos que importan (la caja, los clics, una mascota) quedan. Los huecos sin voz bajan 10 dB.
También deja voz16k.wav, que usan control/bordes_edl.py, control/chequeo_tramos.py y control/chequeo_edl.py.

uso: python voz_cadena_c.py TOMA.mp4 PISTA SALIDA_voz_c.wav [<video>/12_project/analysis]
     PISTA = índice de la pista de audio en ffmpeg (0 = la primera). En OBS conviene grabar el micrófono crudo en su
     propia pista (en los videos del canal fue la 5 o la 6)."""
import subprocess, sys, pathlib
import numpy as np

SRC, PISTA, OUT = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
AN = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else None
OUT.parent.mkdir(parents=True, exist_ok=True)
CHAIN_C = ("highpass=f=80,afftdn=nr=10:nf=-60,equalizer=f=300:t=q:w=1:g=-3,"
           "acompressor=threshold=-12dB:ratio=2:attack=20:release=200:makeup=1,deesser=i=0.4,"
           "equalizer=f=4000:t=q:w=1:g=2,equalizer=f=10000:t=h:w=0.7:g=1.5")
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-map", f"0:a:{PISTA}", "-af",
                      f"aformat=sample_rates=48000,adeclip,{CHAIN_C}", "-ac", "1", "-f", "f32le", "-"],
                     capture_output=True, check=True).stdout
# Huecos sin sonido −10 dB: umbral relativo a la voz; 200 ms de cola y 60 ms antes, rampa de 40 ms.
# Lo que suena fuerte sin voz (bolsa, clics) pasa el umbral y queda.
v = np.frombuffer(raw, np.float32).copy(); n10 = len(v) // 480
d = 20 * np.log10(np.sqrt((v[:n10 * 480].reshape(n10, 480) ** 2).mean(1)) + 1e-9)
on = d > np.percentile(d[d > -80], 90) - 24
keep = np.convolve(on.astype(float), np.ones(20), "full")[:n10] > 0
keep |= np.convolve(on[::-1].astype(float), np.ones(6), "full")[:n10][::-1] > 0
g = np.convolve(np.where(keep, 1.0, 10 ** (-10 / 20)), np.ones(4) / 4, "same")
v[:n10 * 480] *= np.repeat(g, 480).astype(np.float32)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "1", "-ar", "48000", "-i", "-", "-c:a", "pcm_s24le", str(OUT)],
               input=v.tobytes(), check=True)
print(f"umbral {np.percentile(d[d > -80], 90) - 24:.1f} dBFS · huecos bajados: {100 * (1 - keep.mean()):.0f} % del tiempo")
if AN:
    AN.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT), "-ar", "16000", "-c:a", "pcm_s16le", str(AN / "voz16k.wav")], check=True)

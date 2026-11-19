"""Transcribe una pista de audio de cada toma con marcas por palabra, en la GPU (faster-whisper large-v3, CUDA).
uso: python transcribir_gpu.py SALIDA_DIR toma1.mp4 [toma2.mp4 ...]  → tx_<n>.json / .txt
ZK_PISTA = índice de la pista de audio (por defecto 4: el micrófono crudo en su propia pista de OBS)."""
import os, glob, sys, json, subprocess, tempfile, pathlib
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
out = pathlib.Path(sys.argv[1]); m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
for n, src in enumerate(sys.argv[2:]):
    wav = os.path.join(tempfile.gettempdir(), f"txg{n}.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", f"0:a:{os.environ.get('ZK_PISTA', '4')}", "-ac", "1", "-ar", "16000", wav], check=True)
    segs, _ = m.transcribe(wav, language="es", word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
    res = []
    with open(out / f"tx_{n}.txt", "w", encoding="utf-8") as f:
        for s in segs:
            res.append({"start": s.start, "end": s.end, "text": s.text, "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]})
            f.write(f"{s.start:7.2f}-{s.end:7.2f} {s.text}\n")
    json.dump(res, open(out / f"tx_{n}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("OK", n, src, flush=True)

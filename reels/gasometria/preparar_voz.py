#!/usr/bin/env python3
"""
Prepara los audios de narración (uno por escena) para generar.py --voz-dir:
  - recorta el silencio de inicio y final,
  - acorta pausas internas largas (> max_pausa) a max_pausa,
  - opcionalmente acelera la voz sin cambiar el tono (ffmpeg atempo) para que
    el video completo quede por debajo de un tiempo objetivo.

Uso:
    python preparar_voz.py ENTRADA SALIDA [--objetivo 178] [--escenas 12]
"""
import argparse
import glob
import os
import subprocess

import numpy as np
import soundfile as sf

SR = 44100
LEAD, PAD, MIN_DUR = 0.25, 0.85, 5.0   # mismos valores que el motor del ECG v2


def leer(path):
    tmp = path + ".tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", str(SR), tmp], check=True)
    a, _ = sf.read(tmp, dtype="float32")
    os.remove(tmp)
    return a


def compactar(a, umbral=0.015, max_pausa=0.38, ventana=0.02):
    n = int(ventana * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a), n)])
    voz = rms > umbral
    if not voz.any():
        return a
    ini, fin = np.argmax(voz), len(voz) - np.argmax(voz[::-1])
    out, silencio = [], 0
    for k in range(ini, fin):
        bloque = a[k * n:(k + 1) * n]
        if voz[k]:
            silencio = 0
            out.append(bloque)
        else:
            silencio += ventana
            if silencio <= max_pausa:
                out.append(bloque)
    y = np.concatenate(out)
    f = int(0.01 * SR)
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--objetivo", type=float, default=178.0, help="duración máxima del video (s)")
    ap.add_argument("--max-tempo", type=float, default=1.18, help="1.0 = nunca acelerar")
    ap.add_argument("--max-pausa", type=float, default=0.38, help="pausa interna máxima (s)")
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    archivos = sorted(glob.glob(os.path.join(args.entrada, "escena_*")))
    audios = [compactar(leer(f), max_pausa=args.max_pausa) for f in archivos]
    total = lambda tempo: sum(max(MIN_DUR, LEAD + len(a) / SR / tempo + PAD) for a in audios)
    tempo = 1.0
    while total(tempo) > args.objetivo and tempo < args.max_tempo:
        tempo = round(tempo + 0.01, 2)
    print(f"Duración del video: {total(1.0):.1f}s sin acelerar -> {total(tempo):.1f}s con tempo {tempo}")
    for f, a in zip(archivos, audios):
        nombre = os.path.splitext(os.path.basename(f))[0] + ".wav"
        tmp = os.path.join(args.salida, "_tmp.wav")
        sf.write(tmp, a, SR)
        filtro = f"atempo={tempo}" if tempo != 1.0 else "anull"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", filtro, os.path.join(args.salida, nombre)],
                       check=True)
        os.remove(tmp)
    print("Listo:", args.salida)


if __name__ == "__main__":
    main()

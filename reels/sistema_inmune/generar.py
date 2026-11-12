#!/usr/bin/env python3
"""
Reel vertical (1080x1920) sobre la función de las células del sistema inmune.

- Voz: Kokoro TTS (offline) en español.
- Visuales: ilustraciones animadas generadas con Pillow.
- Subtítulos sincronizados por escena + música ambiental sintetizada.

Uso:
    python generar.py --modelo models/kokoro.onnx --voces models/voices.bin --salida reel.mp4

Modelos: https://github.com/thewh1teagle/kokoro-onnx/releases (model-files-v1.0)
"""
import argparse
import math
import os
import random
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SR = 24000
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ----------------------------------------------------------------------------
# GUION
# ----------------------------------------------------------------------------
ESCENAS = [
    dict(id="intro", titulo="TU EJÉRCITO INTERNO", rol="El sistema inmune",
         color=(90, 200, 255),
         texto="¿Sabías que dentro de ti hay un ejército que trabaja las veinticuatro horas? "
               "Te presento a las células de tu sistema inmune."),
    dict(id="neutrofilo", titulo="NEUTRÓFILOS", rol="Primera línea de defensa",
         color=(255, 150, 190),
         texto="Los neutrófilos son los primeros en llegar a una infección. "
               "Devoran bacterias y mueren en la batalla. De hecho, el pus está hecho de ellos."),
    dict(id="macrofago", titulo="MACRÓFAGOS", rol="Los grandes comelones",
         color=(255, 170, 80),
         texto="Los macrófagos engullen invasores, células muertas y basura. "
               "Además, lanzan alarmas químicas para llamar refuerzos."),
    dict(id="dendritica", titulo="CÉLULAS DENDRÍTICAS", rol="Las mensajeras",
         color=(80, 230, 200),
         texto="Las células dendríticas capturan trozos del enemigo "
               "y se los muestran a los linfocitos en los ganglios. Así empieza el ataque dirigido."),
    dict(id="t_helper", titulo="LINFOCITOS T CD4", rol="Los generales",
         color=(110, 150, 255),
         texto="Los linfocitos T colaboradores son los generales. "
               "Coordinan la respuesta y activan a las demás células para el combate."),
    dict(id="t_citotoxico", titulo="LINFOCITOS T CD8", rol="Asesinos de precisión",
         color=(255, 90, 110),
         texto="Los linfocitos T citotóxicos buscan células infectadas por virus, o células cancerosas, "
               "y las destruyen desde adentro."),
    dict(id="linfocito_b", titulo="LINFOCITOS B", rol="Fábricas de anticuerpos",
         color=(255, 215, 80),
         texto="Los linfocitos B fabrican anticuerpos: proteínas en forma de Y "
               "que se pegan al enemigo y lo marcan para su destrucción."),
    dict(id="nk", titulo="CÉLULAS NK", rol="Asesinas naturales",
         color=(190, 120, 255),
         texto="Las células asesinas naturales patrullan sin necesidad de entrenamiento "
               "y eliminan cualquier célula que parezca sospechosa."),
    dict(id="memoria", titulo="CÉLULAS DE MEMORIA", rol="Nunca olvidan",
         color=(255, 200, 120),
         texto="Y las células de memoria recuerdan a cada enemigo, "
               "para responder mucho más rápido la próxima vez. Por eso funcionan las vacunas."),
    dict(id="outro", titulo="CUIDA A TU EJÉRCITO", rol="Duerme · Come sano · Muévete",
         color=(120, 255, 160),
         texto="Cuida a tu ejército: duerme bien, come sano y muévete. "
               "Guarda este video y síguenos para aprender más."),
]

PAUSA = 0.45  # segundos de silencio al final de cada escena


# ----------------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------------
def ease_out_back(x):
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_in_out(x):
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def clamp01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def fuente(path, size, _cache={}):
    key = (path, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(path, size)
    return _cache[key]


# ----------------------------------------------------------------------------
# SPRITES (dibujados a 2x y reducidos para antialiasing)
# ----------------------------------------------------------------------------
SS = 2


def lienzo(size):
    s = size * SS
    return Image.new("RGBA", (s, s), (0, 0, 0, 0)), s


def finalizar(img, size, glow=None):
    img = img.resize((size, size), Image.LANCZOS)
    if glow:
        halo = Image.new("RGBA", img.size, glow + (0,))
        a = img.split()[3].filter(ImageFilter.GaussianBlur(size * 0.05))
        a = a.point(lambda v: int(v * 0.55))
        halo.putalpha(a)
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.alpha_composite(halo)
        out.alpha_composite(img)
        return out
    return img


def blob(cx, cy, r, fase, amp=0.08, lobulos=5, n=90):
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        rr = r * (1 + amp * math.sin(lobulos * th + fase) + amp * 0.5 * math.sin((lobulos + 2) * th - 1.3 * fase))
        pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
    return pts


def celula_base(size, fase, cuerpo, borde, amp=0.05, lobulos=5, r_frac=0.40):
    img, s = lienzo(size)
    d = ImageDraw.Draw(img)
    c = s / 2
    r = s * r_frac
    d.polygon(blob(c, c, r, fase, amp, lobulos), fill=borde)
    d.polygon(blob(c, c, r * 0.94, fase, amp, lobulos), fill=cuerpo)
    # brillo interno
    d.ellipse([c - r * 0.7, c - r * 0.75, c - r * 0.1, c - r * 0.35], fill=(255, 255, 255, 40))
    return img, d, s, c, r


def granulos(d, c, r, color, n, seed, rmin=0.25, rmax=0.85, tam=0.035):
    rnd = random.Random(seed)
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        rr = r * math.sqrt(rnd.uniform(rmin ** 2, rmax ** 2))
        x, y = c + rr * math.cos(a), c + rr * math.sin(a)
        t = r * tam * rnd.uniform(0.7, 1.3)
        d.ellipse([x - t, y - t, x + t, y + t], fill=color)


def spr_neutrofilo(size, fase):
    img, d, s, c, r = celula_base(size, fase, (255, 205, 220, 255), (230, 120, 160, 255), 0.06, 6)
    granulos(d, c, r, (220, 140, 180, 255), 40, 1)
    # núcleo multilobulado
    for (dx, dy) in [(-0.32, 0.05), (0.0, -0.18), (0.30, 0.08), (0.05, 0.30)]:
        x, y = c + dx * r, c + dy * r
        rr = r * 0.22
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(120, 50, 140, 255))
    d.line([(c - 0.32 * r, c + 0.05 * r), (c, c - 0.18 * r), (c + 0.3 * r, c + 0.08 * r),
            (c + 0.05 * r, c + 0.3 * r)], fill=(120, 50, 140, 255), width=int(r * 0.12))
    return finalizar(img, size, (255, 150, 190))


def spr_macrofago(size, fase):
    img, d, s, c, r = celula_base(size, fase, (255, 200, 140, 255), (220, 120, 50, 255), 0.13, 4, 0.36)
    granulos(d, c, r, (230, 150, 90, 255), 30, 2, tam=0.05)
    rr = r * 0.32
    d.ellipse([c - rr * 1.2 + r * 0.15, c - rr, c + rr * 1.2 + r * 0.15, c + rr], fill=(140, 70, 40, 255))
    # vacuolas
    for (dx, dy, k) in [(-0.45, -0.25, 0.12), (-0.35, 0.35, 0.09), (0.45, -0.4, 0.08)]:
        x, y, t = c + dx * r, c + dy * r, r * k
        d.ellipse([x - t, y - t, x + t, y + t], fill=(255, 235, 200, 255), outline=(200, 120, 60, 255), width=3)
    return finalizar(img, size, (255, 170, 80))


def spr_dendritica(size, fase):
    img, s = lienzo(size)
    d = ImageDraw.Draw(img)
    c = s / 2
    r = s * 0.17
    n = 7
    for i in range(n):
        a = 2 * math.pi * i / n + 0.15 * math.sin(fase + i)
        largo = s * (0.36 + 0.05 * math.sin(fase * 1.3 + i * 2))
        x2, y2 = c + largo * math.cos(a), c + largo * math.sin(a)
        xm, ym = c + largo * 0.55 * math.cos(a + 0.25), c + largo * 0.55 * math.sin(a + 0.25)
        for w, col in [(int(s * 0.07), (40, 160, 140, 255)), (int(s * 0.05), (140, 240, 215, 255))]:
            d.line([(c, c), (xm, ym), (x2, y2)], fill=col, width=w, joint="curve")
            t = w / 2
            d.ellipse([x2 - t, y2 - t, x2 + t, y2 + t], fill=col)
    d.ellipse([c - r * 1.15, c - r * 1.15, c + r * 1.15, c + r * 1.15], fill=(40, 160, 140, 255))
    d.ellipse([c - r, c - r, c + r, c + r], fill=(140, 240, 215, 255))
    d.ellipse([c - r * 0.55, c - r * 0.5, c + r * 0.55, c + r * 0.5], fill=(20, 110, 100, 255))
    return finalizar(img, size, (80, 230, 200))


def spr_linfocito(size, fase, cuerpo, borde, nucleo, glow, etiqueta=None, receptores=None):
    img, d, s, c, r = celula_base(size, fase, cuerpo, borde, 0.03, 7)
    if receptores:
        for i in range(14):
            a = 2 * math.pi * i / 14 + fase * 0.05
            x1, y1 = c + r * 0.98 * math.cos(a), c + r * 0.98 * math.sin(a)
            x2, y2 = c + r * 1.13 * math.cos(a), c + r * 1.13 * math.sin(a)
            d.line([(x1, y1), (x2, y2)], fill=receptores, width=int(s * 0.012))
            t = s * 0.014
            d.ellipse([x2 - t, y2 - t, x2 + t, y2 + t], fill=receptores)
    rr = r * 0.66
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=nucleo)
    if etiqueta:
        f = fuente(FONT_BOLD, int(r * 0.42))
        d.text((c, c), etiqueta, font=f, fill=(255, 255, 255, 235), anchor="mm")
    return finalizar(img, size, glow)


def spr_t_helper(size, fase):
    return spr_linfocito(size, fase, (170, 195, 255, 255), (70, 100, 220, 255), (50, 70, 180, 255),
                         (110, 150, 255), "CD4", (200, 220, 255, 255))


def spr_t_cito(size, fase):
    img = spr_linfocito(size, fase, (255, 170, 180, 255), (200, 50, 80, 255), (150, 30, 60, 255),
                        (255, 90, 110), "CD8", (255, 210, 215, 255))
    return img


def spr_b(size, fase):
    img, d, s, c, r = celula_base(size, fase, (255, 235, 160, 255), (220, 170, 40, 255), 0.03, 7)
    for i in range(10):
        a = 2 * math.pi * i / 10 + 0.2
        dibujar_y(d, c + r * 1.0 * math.cos(a), c + r * 1.0 * math.sin(a), a, s * 0.07,
                  (255, 200, 60, 255), int(s * 0.013))
    rr = r * 0.6
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(180, 120, 20, 255))
    f = fuente(FONT_BOLD, int(r * 0.5))
    d.text((c, c), "B", font=f, fill=(255, 255, 255, 235), anchor="mm")
    return finalizar(img, size, (255, 215, 80))


def spr_nk(size, fase):
    img, d, s, c, r = celula_base(size, fase, (220, 190, 255, 255), (140, 70, 220, 255), 0.04, 6)
    granulos(d, c, r, (120, 40, 200, 255), 22, 5, 0.5, 0.88, 0.06)
    rr = r * 0.48
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(100, 40, 170, 255))
    f = fuente(FONT_BOLD, int(r * 0.4))
    d.text((c, c), "NK", font=f, fill=(255, 255, 255, 235), anchor="mm")
    return finalizar(img, size, (190, 120, 255))


def spr_memoria(size, fase):
    img, d, s, c, r = celula_base(size, fase, (255, 230, 170, 255), (230, 160, 60, 255), 0.03, 7)
    rr = r * 0.62
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(200, 120, 30, 255))
    # estrella
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        R = r * (0.45 if i % 2 == 0 else 0.19)
        pts.append((c + R * math.cos(a), c + R * math.sin(a)))
    d.polygon(pts, fill=(255, 245, 200, 255))
    return finalizar(img, size, (255, 210, 120))


def spr_bacteria(size, fase):
    img, s = lienzo(size)
    d = ImageDraw.Draw(img)
    c = s / 2
    # flagelos
    for k in range(3):
        pts = []
        for i in range(30):
            t = i / 29
            x = c + s * 0.18 + t * s * 0.3
            y = c + (k - 1) * s * 0.06 + math.sin(t * 9 + fase * 2 + k) * s * 0.035
            pts.append((x, y))
        d.line(pts, fill=(80, 170, 60, 255), width=int(s * 0.015))
    d.rounded_rectangle([c - s * 0.3, c - s * 0.13, c + s * 0.26, c + s * 0.13], radius=int(s * 0.13),
                        fill=(60, 150, 50, 255))
    d.rounded_rectangle([c - s * 0.28, c - s * 0.11, c + s * 0.24, c + s * 0.11], radius=int(s * 0.11),
                        fill=(130, 220, 90, 255))
    for i in range(4):
        x = c - s * 0.18 + i * s * 0.11
        d.ellipse([x - s * 0.02, c - s * 0.02, x + s * 0.02, c + s * 0.02], fill=(70, 150, 50, 255))
    return finalizar(img, size)


def spr_virus(size, fase):
    img, s = lienzo(size)
    d = ImageDraw.Draw(img)
    c = s / 2
    r = s * 0.25
    for i in range(12):
        a = 2 * math.pi * i / 12 + fase * 0.3
        x1, y1 = c + r * math.cos(a), c + r * math.sin(a)
        x2, y2 = c + r * 1.55 * math.cos(a), c + r * 1.55 * math.sin(a)
        d.line([(x1, y1), (x2, y2)], fill=(200, 40, 60, 255), width=int(s * 0.03))
        t = s * 0.045
        d.ellipse([x2 - t, y2 - t, x2 + t, y2 + t], fill=(255, 90, 90, 255))
    d.ellipse([c - r, c - r, c + r, c + r], fill=(200, 40, 60, 255))
    d.ellipse([c - r * 0.88, c - r * 0.88, c + r * 0.88, c + r * 0.88], fill=(255, 100, 110, 255))
    d.ellipse([c - r * 0.5, c - r * 0.6, c - r * 0.05, c - r * 0.25], fill=(255, 200, 200, 120))
    return finalizar(img, size)


def spr_infectada(size, fase):
    img, d, s, c, r = celula_base(size, fase, (170, 190, 160, 255), (100, 120, 90, 255), 0.07, 5)
    rr = r * 0.35
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(90, 100, 80, 255))
    rnd = random.Random(9)
    for _ in range(6):
        a = rnd.uniform(0, 2 * math.pi)
        R = r * rnd.uniform(0.5, 0.75)
        x, y = c + R * math.cos(a), c + R * math.sin(a)
        t = r * 0.1
        d.ellipse([x - t, y - t, x + t, y + t], fill=(230, 60, 80, 255))
    return finalizar(img, size)


def spr_tumoral(size, fase):
    img, d, s, c, r = celula_base(size, fase, (150, 110, 130, 255), (90, 50, 80, 255), 0.18, 3)
    for (dx, dy) in [(-0.2, -0.1), (0.25, 0.15)]:
        x, y, t = c + dx * r, c + dy * r, r * 0.28
        d.ellipse([x - t, y - t, x + t, y + t], fill=(70, 30, 60, 255))
    return finalizar(img, size)


def dibujar_y(d, x, y, ang, L, col, w):
    """Anticuerpo en forma de Y: base en (x, y), apuntando hacia fuera con ángulo ang."""
    xm, ym = x + L * 0.55 * math.cos(ang), y + L * 0.55 * math.sin(ang)
    d.line([(x, y), (xm, ym)], fill=col, width=w)
    for da in (-0.55, 0.55):
        d.line([(xm, ym), (xm + L * 0.5 * math.cos(ang + da), ym + L * 0.5 * math.sin(ang + da))],
               fill=col, width=w)


def spr_anticuerpo(size, ang):
    img, s = lienzo(size)
    d = ImageDraw.Draw(img)
    c = s / 2
    x, y = c - s * 0.35 * math.cos(ang), c - s * 0.35 * math.sin(ang)
    dibujar_y(d, x, y, ang, s * 0.75, (255, 220, 80, 255), int(s * 0.09))
    return finalizar(img, size)


class Sprite:
    """Animación en bucle pre-renderizada."""

    def __init__(self, fn, size, frames=16):
        self.frames = [fn(size, 2 * math.pi * i / frames) for i in range(frames)]
        self.cache = {}

    def get(self, t, escala=1.0, alpha=1.0, vel=1.0):
        i = int(t * FPS * vel / 3) % len(self.frames)
        img = self.frames[i]
        if abs(escala - 1.0) > 1e-3:
            sz = max(2, int(img.width * escala))
            key = (i, sz)
            if key not in self.cache:
                if len(self.cache) > 400:
                    self.cache.clear()
                self.cache[key] = img.resize((sz, sz), Image.BILINEAR)
            img = self.cache[key]
        if alpha < 0.999:
            img = img.copy()
            img.putalpha(img.split()[3].point(lambda v: int(v * max(0.0, alpha))))
        return img


def pegar(frame, img, cx, cy):
    frame.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)


# ----------------------------------------------------------------------------
# FONDO
# ----------------------------------------------------------------------------
def fondo_base(color):
    top = mix((8, 10, 30), color, 0.18)
    bot = (4, 4, 14)
    grad = np.zeros((H, W, 3), dtype=np.float32)
    ys = np.linspace(0, 1, H)[:, None]
    for k in range(3):
        grad[:, :, k] = top[k] * (1 - ys) + bot[k] * ys
    # viñeta radial con el color de la escena
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - 850) / H) ** 2)
    glow = np.clip(1 - dist * 2.4, 0, 1)[:, :, None] ** 2
    grad += glow * np.array(color, dtype=np.float32)[None, None, :] * 0.22
    return Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8), "RGB")


PARTICULAS = [(random.Random(i).uniform(0, W), random.Random(i * 7).uniform(0, H),
               random.Random(i * 13).uniform(3, 11), random.Random(i * 17).uniform(10, 40))
              for i in range(45)]


def dibujar_particulas(d, t, color):
    for (x0, y0, r, v) in PARTICULAS:
        y = (y0 - t * v) % (H + 40) - 20
        x = x0 + 18 * math.sin(t * 0.6 + y0)
        col = mix((20, 22, 45), color, 0.35)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)


# ----------------------------------------------------------------------------
# TEXTO
# ----------------------------------------------------------------------------
def partir_frases(texto, max_chars=30):
    palabras = texto.split()
    trozos, actual = [], ""
    for p in palabras:
        cand = (actual + " " + p).strip()
        if len(cand) > max_chars and actual:
            trozos.append(actual)
            actual = p
        else:
            actual = cand
        if actual.endswith((".", "?", ":")) and len(actual) > 8:
            trozos.append(actual)
            actual = ""
    if actual:
        trozos.append(actual)
    return trozos


def tiempos_subtitulos(trozos, dur):
    pesos = [len(t) + 6 for t in trozos]
    total = sum(pesos)
    out, acc = [], 0.0
    for t, p in zip(trozos, pesos):
        ini = acc / total * dur
        acc += p
        out.append((ini, acc / total * dur, t))
    return out


def texto_envuelto(d, txt, cx, cy, font, fill, max_w, stroke=0, stroke_fill=(0, 0, 0), spacing=1.15):
    palabras = txt.split()
    lineas, act = [], ""
    for p in palabras:
        cand = (act + " " + p).strip()
        if d.textlength(cand, font=font) > max_w and act:
            lineas.append(act)
            act = p
        else:
            act = cand
    lineas.append(act)
    lh = font.size * spacing
    y0 = cy - lh * (len(lineas) - 1) / 2
    for i, l in enumerate(lineas):
        d.text((cx, y0 + i * lh), l, font=font, fill=fill, anchor="mm",
               stroke_width=stroke, stroke_fill=stroke_fill)


# ----------------------------------------------------------------------------
# ESCENAS ANIMADAS
# ----------------------------------------------------------------------------
CY = 860  # centro vertical de la ilustración


class Recursos:
    def __init__(self):
        print("Pre-renderizando sprites...")
        self.neut = Sprite(spr_neutrofilo, 520)
        self.macro = Sprite(spr_macrofago, 600)
        self.dend = Sprite(spr_dendritica, 640)
        self.th = Sprite(spr_t_helper, 480)
        self.tc = Sprite(spr_t_cito, 460)
        self.b = Sprite(spr_b, 480)
        self.nk = Sprite(spr_nk, 460)
        self.mem = Sprite(spr_memoria, 480)
        self.bact = Sprite(spr_bacteria, 170)
        self.virus = Sprite(spr_virus, 150)
        self.inf = Sprite(spr_infectada, 330)
        self.tum = Sprite(spr_tumoral, 330)
        self.ab = [spr_anticuerpo(90, a) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        self.mini = {
            "neut": Sprite(spr_neutrofilo, 190, 8), "macro": Sprite(spr_macrofago, 200, 8),
            "dend": Sprite(spr_dendritica, 210, 8), "th": Sprite(spr_t_helper, 180, 8),
            "tc": Sprite(spr_t_cito, 180, 8), "b": Sprite(spr_b, 180, 8),
            "nk": Sprite(spr_nk, 180, 8), "mem": Sprite(spr_memoria, 180, 8),
        }


def entrada(t, dur=0.6):
    return ease_out_back(t / dur)


def anim_fagocito(fr, R, sprite, t, dur, n_presas=4, presa="bact"):
    s = entrada(t)
    pegar(fr, sprite.get(t, s * (1 + 0.03 * math.sin(t * 3))), W / 2, CY)
    presas = R.bact if presa == "bact" else R.virus
    for i in range(n_presas):
        ang = math.pi * 2 * i / n_presas + 0.4
        t0 = 0.5 + i * (dur - 1.5) / n_presas
        p = clamp01((t - t0) / 1.6)
        if p >= 1:
            continue
        dist = lerp(520, 40, ease_in_out(p))
        x, y = W / 2 + dist * math.cos(ang), CY + dist * math.sin(ang) * 0.9
        esc = 1.0 if p < 0.7 else lerp(1.0, 0.2, (p - 0.7) / 0.3)
        al = 1.0 if p < 0.75 else lerp(1.0, 0.0, (p - 0.75) / 0.25)
        pegar(fr, presas.get(t + i, esc * min(1, s), al), x, y)


def escena_intro(fr, d, R, t, dur, esc):
    # órbita de células alrededor de un núcleo brillante
    nombres = ["neut", "macro", "dend", "th", "tc", "b", "nk", "mem"]
    pulso = 1 + 0.06 * math.sin(t * 4)
    rr = 150 * pulso * entrada(t, 0.8)
    for k in range(4, 0, -1):
        col = mix((10, 10, 30), esc["color"], 0.18 * (5 - k))
        d.ellipse([W / 2 - rr * k * 0.45, CY - rr * k * 0.45, W / 2 + rr * k * 0.45, CY + rr * k * 0.45], fill=col)
    f = fuente(FONT_BOLD, 120)
    d.text((W / 2, CY), "+", font=f, fill=(255, 255, 255), anchor="mm")
    for i, n in enumerate(nombres):
        aparece = clamp01((t - 0.2 - i * 0.18) / 0.5)
        if aparece <= 0:
            continue
        a = 2 * math.pi * i / len(nombres) + t * 0.45
        rad = 360 * ease_out_back(aparece)
        x, y = W / 2 + rad * math.cos(a), CY + rad * math.sin(a)
        pegar(fr, R.mini[n].get(t, 0.8 + 0.2 * aparece), x, y)


def escena_neutrofilo(fr, d, R, t, dur, esc):
    anim_fagocito(fr, R, R.neut, t, dur, 4)


def escena_macrofago(fr, d, R, t, dur, esc):
    anim_fagocito(fr, R, R.macro, t, dur, 5)
    # ondas de alarma (citocinas) en la segunda mitad
    if t > dur * 0.5:
        for k in range(3):
            fase = ((t - dur * 0.5) * 0.7 + k / 3) % 1
            r = 300 + fase * 380
            col = mix((10, 10, 25), esc["color"], 0.8 * (1 - fase))
            d.ellipse([W / 2 - r, CY - r, W / 2 + r, CY + r], outline=col, width=6)


def escena_dendritica(fr, d, R, t, dur, esc):
    s = entrada(t)
    mover = ease_in_out((t - dur * 0.55) / (dur * 0.35))
    cx = W / 2 - 160 * mover
    pegar(fr, R.dend.get(t, s), cx, CY)
    # fragmentos de virus capturados
    for i in range(3):
        t0 = 0.4 + i * 0.7
        p = clamp01((t - t0) / 1.4)
        ang = -0.6 + i * 1.6
        if p < 1:
            dist = lerp(520, 60, ease_in_out(p))
            pegar(fr, R.virus.get(t + i, 0.8 * (1 - 0.6 * max(0, p - 0.6) / 0.4)),
                  cx + dist * math.cos(ang), CY + dist * math.sin(ang))
    # presentación de antígeno a un linfocito T
    if t > dur * 0.55:
        ap = clamp01((t - dur * 0.55) / 0.8)
        pegar(fr, R.mini["th"].get(t, 1.3 * ease_out_back(ap)), W / 2 + 290, CY + 40)
        brillo = 0.5 + 0.5 * math.sin(t * 8)
        col = mix(esc["color"], (255, 255, 255), brillo)
        d.polygon([(W / 2 + 120, CY + 15), (W / 2 + 160, CY + 40), (W / 2 + 120, CY + 65)], fill=col)


def escena_t_helper(fr, d, R, t, dur, esc):
    s = entrada(t)
    otros = ["b", "tc", "macro", "nk", "neut"]
    for i, n in enumerate(otros):
        t0 = 0.8 + i * 0.5
        p = clamp01((t - t0) / 0.6)
        x, y = W / 2 + 390 * math.cos(-math.pi / 2 + 2 * math.pi * i / 5), \
            CY + 360 * math.sin(-math.pi / 2 + 2 * math.pi * i / 5)
        if p > 0:
            # señal viajando
            q = clamp01((t - t0) / 0.6)
            sx, sy = lerp(W / 2, x, q), lerp(CY, y, q)
            d.line([(W / 2, CY), (sx, sy)], fill=mix((20, 20, 40), esc["color"], 0.9), width=5)
            d.ellipse([sx - 12, sy - 12, sx + 12, sy + 12], fill=(220, 235, 255))
        act = clamp01((t - t0 - 0.5) / 0.4)
        if act > 0:
            pegar(fr, R.mini[n].get(t, 0.6 + 0.35 * ease_out_back(act)), x, y)
    pegar(fr, R.th.get(t, s * (1 + 0.04 * math.sin(t * 5))), W / 2, CY)


def escena_t_cito(fr, d, R, t, dur, esc):
    s = entrada(t)
    acerca = ease_in_out((t - 0.6) / (dur * 0.4))
    tx = lerp(W / 2 - 160, W / 2 - 60, acerca)
    ix = W / 2 + 230
    golpe = t - (0.6 + dur * 0.4)
    if golpe < 0.8:
        esc_inf = 1.0 if golpe < 0 else 1.0 + 0.15 * math.sin(golpe * 30) * (1 - golpe / 0.8)
        pegar(fr, R.inf.get(t, esc_inf), ix, CY)
    else:
        # explosión en fragmentos
        q = clamp01((golpe - 0.8) / 1.2)
        rnd = random.Random(4)
        for k in range(14):
            a = rnd.uniform(0, 2 * math.pi)
            dist = 40 + 260 * ease_in_out(q) * rnd.uniform(0.6, 1.2)
            rr = 26 * (1 - q) + 4
            col = mix((170, 190, 160), (40, 40, 60), q)
            x, y = ix + dist * math.cos(a), CY + dist * math.sin(a)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col)
    if 0 < golpe < 1.6:
        # gránulos de perforina
        for k in range(8):
            q = clamp01((golpe - k * 0.05) / 0.5)
            x = lerp(tx + 150, ix, q)
            y = CY + (k - 4) * 14
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 220, 230))
    pegar(fr, R.tc.get(t, s), tx, CY)


def escena_b(fr, d, R, t, dur, esc):
    s = entrada(t)
    bx, by = W / 2, CY + 150
    pegar(fr, R.b.get(t, s * 0.85), bx, by)
    objetivos = [(W / 2 - 300, CY - 320), (W / 2, CY - 380), (W / 2 + 300, CY - 320)]
    pegados = [0, 0, 0]
    n_ab = 18
    for k in range(n_ab):
        t0 = 0.7 + k * (dur - 2.5) / n_ab
        p = clamp01((t - t0) / 0.9)
        if p <= 0:
            continue
        j = k % 3
        ox, oy = objetivos[j]
        ang = math.atan2(oy - by, ox - bx)
        if p < 1:
            x, y = lerp(bx, ox, ease_in_out(p)), lerp(by, oy, ease_in_out(p))
        else:
            pegados[j] += 1
            a2 = ang + math.pi + (pegados[j] - 3.5) * 0.45
            x, y = ox + 70 * math.cos(a2), oy + 70 * math.sin(a2)
            ang = a2 + math.pi
        idx = int(((ang % (2 * math.pi)) / (2 * math.pi)) * 24) % 24
        pegar(fr, R.ab[idx], x, y)
    for j, (ox, oy) in enumerate(objetivos):
        marcado = pegados[j] / 6
        pegar(fr, R.bact.get(t + j, 1.0 * min(1, s), 1.0 - 0.4 * marcado), ox, oy)


def escena_nk(fr, d, R, t, dur, esc):
    s = entrada(t)
    # patrulla: se mueve en zigzag hacia la célula sospechosa
    fase = clamp01(t / (dur * 0.55))
    nx = lerp(W / 2 - 250, W / 2 - 80, ease_in_out(fase)) + 40 * math.sin(t * 2.5) * (1 - fase)
    ny = CY - 60 + 90 * math.sin(t * 1.7) * (1 - fase)
    tx, ty = W / 2 + 230, CY + 80
    golpe = t - dur * 0.55
    if golpe < 0.7:
        pegar(fr, R.tum.get(t, 1.0 if golpe < 0 else 1 + 0.12 * math.sin(golpe * 28)), tx, ty)
        if golpe < 0:
            f = fuente(FONT_BOLD, 90)
            d.text((tx, ty - 220), "?", font=f, fill=(255, 120, 160), anchor="mm")
    else:
        q = clamp01((golpe - 0.7) / 1.0)
        rnd = random.Random(8)
        for k in range(14):
            a = rnd.uniform(0, 2 * math.pi)
            dist = 30 + 260 * ease_in_out(q) * rnd.uniform(0.6, 1.2)
            rr = 26 * (1 - q) + 4
            x, y = tx + dist * math.cos(a), ty + dist * math.sin(a)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=mix((150, 110, 130), (30, 20, 40), q))
    pegar(fr, R.nk.get(t, s), nx, ny)


def escena_memoria(fr, d, R, t, dur, esc):
    s = entrada(t)
    for k in range(3):
        fase = (t * 0.5 + k / 3) % 1
        r = 230 + fase * 300
        col = mix((10, 10, 25), esc["color"], 0.7 * (1 - fase))
        d.ellipse([W / 2 - r, CY - r, W / 2 + r, CY + r], outline=col, width=5)
    # enemigos recordados orbitando como "fantasmas"
    for i in range(5):
        a = 2 * math.pi * i / 5 + t * 0.6
        x, y = W / 2 + 380 * math.cos(a), CY + 380 * math.sin(a)
        spr = R.virus if i % 2 else R.bact
        al = 0.55 * clamp01((t - 0.5 - i * 0.2) / 0.5)
        if al > 0:
            pegar(fr, spr.get(t + i, 0.75, al), x, y)
    pegar(fr, R.mem.get(t, s * (1 + 0.05 * math.sin(t * 3))), W / 2, CY)
    if t > dur * 0.6:
        p = ease_out_back((t - dur * 0.6) / 0.6)
        f = fuente(FONT_BOLD, int(64 * max(0.01, p)))
        d.text((W / 2, CY + 330), "VACUNAS", font=f, fill=(255, 235, 180), anchor="mm",
               stroke_width=4, stroke_fill=(60, 30, 0))


def escena_outro(fr, d, R, t, dur, esc):
    nombres = ["neut", "macro", "dend", "th", "tc", "b", "nk", "mem"]
    for i, n in enumerate(nombres):
        fila, col = divmod(i, 4)
        x = W / 2 + (col - 1.5) * 235
        y = CY - 170 + fila * 260 + 18 * math.sin(t * 3 + i)
        p = clamp01((t - i * 0.12) / 0.5)
        if p > 0:
            pegar(fr, R.mini[n].get(t, ease_out_back(p)), x, y)
    p = ease_out_back((t - 1.2) / 0.6)
    if p > 0:
        bw, bh = 560 * p, 110 * p
        y = CY + 300
        d.rounded_rectangle([W / 2 - bw / 2, y - bh / 2, W / 2 + bw / 2, y + bh / 2], radius=int(bh / 2),
                            fill=(255, 60, 100))
        f = fuente(FONT_BOLD, max(1, int(56 * p)))
        d.text((W / 2, y), "SÍGUENOS", font=f, fill=(255, 255, 255), anchor="mm")


ANIM = {
    "intro": escena_intro, "neutrofilo": escena_neutrofilo, "macrofago": escena_macrofago,
    "dendritica": escena_dendritica, "t_helper": escena_t_helper, "t_citotoxico": escena_t_cito,
    "linfocito_b": escena_b, "nk": escena_nk, "memoria": escena_memoria, "outro": escena_outro,
}


# ----------------------------------------------------------------------------
# AUDIO
# ----------------------------------------------------------------------------
def generar_voz(modelo, voces, voz, velocidad):
    from kokoro_onnx import Kokoro
    k = Kokoro(modelo, voces)
    pistas = []
    for e in ESCENAS:
        print(f"  voz: {e['id']}")
        s, sr = k.create(e["texto"], voice=voz, speed=velocidad, lang="es")
        assert sr == SR
        s = np.asarray(s, dtype=np.float32)
        s = s / (np.max(np.abs(s)) + 1e-6) * 0.92
        lead = np.zeros(int(0.15 * SR), dtype=np.float32)
        tail = np.zeros(int(PAUSA * SR), dtype=np.float32)
        pistas.append(np.concatenate([lead, s, tail]))
    return pistas


def musica(dur):
    """Pad ambiental + pulso suave, sintetizado."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    acordes = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 207.65, 246.94]]
    out = np.zeros(n, dtype=np.float32)
    seg = 4.0
    for i in range(int(dur / seg) + 1):
        a = acordes[i % len(acordes)]
        i0, i1 = int(i * seg * SR), min(n, int((i + 1) * seg * SR + SR))
        if i0 >= n:
            break
        tt = t[i0:i1] - i * seg
        env = np.clip(tt / 1.0, 0, 1) * np.clip((seg + 1 - tt) / 1.0, 0, 1)
        for f in a:
            out[i0:i1] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt)) * env * 0.08
    # pulso de bajo
    beat = 60 / 100
    kick_env = np.exp(-((t % beat) * 18))
    out += np.sin(2 * np.pi * 55 * t) * kick_env * 0.18
    out *= 0.5 + 0.5 * np.clip(t / 2, 0, 1)
    out *= np.clip((dur - t) / 2.0, 0, 1)
    return out / (np.max(np.abs(out)) + 1e-6)


# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
def dibujar_hud(d, idx, t_esc, dur, esc, total):
    # barras de progreso tipo historias
    m, gap = 40, 10
    bw = (W - 2 * m - gap * (total - 1)) / total
    for i in range(total):
        x = m + i * (bw + gap)
        d.rounded_rectangle([x, 60, x + bw, 68], radius=4, fill=(60, 60, 80))
        fill = 1.0 if i < idx else (clamp01(t_esc / dur) if i == idx else 0)
        if fill > 0:
            d.rounded_rectangle([x, 60, x + bw * fill, 68], radius=4, fill=(255, 255, 255))
    # etiqueta
    f = fuente(FONT_BOLD, 34)
    d.text((W / 2, 130), "SISTEMA INMUNE", font=f, fill=mix((200, 200, 220), esc["color"], 0.4), anchor="mm")
    # título con entrada
    p = ease_out_back((t_esc - 0.05) / 0.5)
    if p > 0:
        ft = fuente(FONT_BOLD, 84 if len(esc["titulo"]) <= 16 else 70)
        y = 270 - 40 * (1 - clamp01(p))
        texto_envuelto(d, esc["titulo"], W / 2, y, ft, esc["color"], W - 100, stroke=5,
                       stroke_fill=(5, 5, 20))
        fr = fuente(FONT_REG, 46)
        d.text((W / 2, 390), esc["rol"], font=fr, fill=(235, 235, 245), anchor="mm")


def dibujar_subtitulo(d, subs, t_esc, esc):
    for ini, fin, txt in subs:
        if ini <= t_esc < fin:
            p = clamp01((t_esc - ini) / 0.12)
            f = fuente(FONT_BOLD, int(lerp(60, 68, p)))
            # caja
            texto_envuelto(d, txt.upper(), W / 2, 1500, f, (255, 255, 255), W - 140, stroke=8,
                           stroke_fill=(0, 0, 0))
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--voces", required=True)
    ap.add_argument("--voz", default="em_alex")
    ap.add_argument("--velocidad", type=float, default=1.08)
    ap.add_argument("--salida", default="reel_sistema_inmune.mp4")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp()
    print("Generando voz...")
    pistas = generar_voz(args.modelo, args.voces, args.voz, args.velocidad)
    duraciones = [len(p) / SR for p in pistas]
    voz = np.concatenate(pistas)
    total = len(voz) / SR
    print(f"Duración total: {total:.1f}s")

    mus = musica(total)
    mus = np.pad(mus, (0, max(0, len(voz) - len(mus))))[:len(voz)]
    mezcla = voz + mus * 0.10
    mezcla = mezcla / (np.max(np.abs(mezcla)) + 1e-6) * 0.95
    wav = os.path.join(tmp, "audio.wav")
    sf.write(wav, mezcla, SR)

    R = Recursos()
    fondos = [fondo_base(e["color"]) for e in ESCENAS]
    subs = [tiempos_subtitulos(partir_frases(e["texto"]), len(p) / SR - PAUSA - 0.15)
            for e, p in zip(ESCENAS, pistas)]
    for s in subs:  # compensar el silencio inicial
        for i, (a, b, txt) in enumerate(s):
            s[i] = (a + 0.15, b + 0.15, txt)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           args.salida]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    n_frames = int(math.ceil(total * FPS))
    limites = np.cumsum([0] + duraciones)
    for fi in range(n_frames):
        t = fi / FPS
        idx = min(len(ESCENAS) - 1, int(np.searchsorted(limites, t, side="right") - 1))
        esc = ESCENAS[idx]
        t_esc = t - limites[idx]
        dur = duraciones[idx]
        fr = fondos[idx].copy()
        d = ImageDraw.Draw(fr)
        dibujar_particulas(d, t, esc["color"])
        ANIM[esc["id"]](fr, d, R, t_esc, dur, esc)
        dibujar_hud(d, idx, t_esc, dur, esc, len(ESCENAS))
        dibujar_subtitulo(d, subs[idx], t_esc, esc)
        # fundido entre escenas
        fade = min(clamp01(t_esc / 0.2), clamp01((dur - t_esc) / 0.15) if idx < len(ESCENAS) - 1 else 1)
        if idx == len(ESCENAS) - 1:
            fade = min(fade, clamp01((dur - t_esc) / 0.6))
        if fade < 1:
            fr = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), fr, fade)
        proc.stdin.write(fr.tobytes())
        if fi % (FPS * 5) == 0:
            print(f"  frame {fi}/{n_frames}")
    proc.stdin.close()
    proc.wait()
    print("Listo:", args.salida)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Reel v2 — "Biología en Minutos": las células del sistema inmunológico.

Versión SIN VOZ: subtítulos estilo karaoke + efectos de sonido caricaturescos
+ música suave, para agregar la narración después (por ejemplo con ElevenLabs).

La duración de cada escena se calcula con una voz de referencia (Kokoro, offline)
que NO se incluye en el video. Si ya tienes los audios de ElevenLabs por escena
(escena_01.mp3, escena_02.mp3, ...), pásalos con --voz-dir y el video se
re-sincroniza con tus audios reales (y los mezcla).

Salidas (en --out):
    reel_sistema_inmune_v2.mp4           video con efectos + música
    reel_sistema_inmune_v2_sin_musica.mp4  solo efectos de sonido
    subtitulos.srt                       subtítulos por frase
    guion_elevenlabs.txt                 guion por escena con tiempos
"""
import argparse
import glob
import importlib.util
import math
import os
import random
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw

# Reutilizamos los sprites de la versión 1.
_v1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sistema_inmune", "generar.py")
_spec = importlib.util.spec_from_file_location("reel_v1", _v1)
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)

W, H, FPS = 1080, 1920, 30
SR = 44100
FONT_BOLD, FONT_REG = v1.FONT_BOLD, v1.FONT_REG
fuente, mix, lerp, clamp01 = v1.fuente, v1.mix, v1.lerp, v1.clamp01
ease_out_back, ease_in_out = v1.ease_out_back, v1.ease_in_out
Sprite = v1.Sprite

MARCA = "BIOLOGÍA EN MINUTOS"
NOMBRE = "reel_sistema_inmune_v2"  # prefijo de los archivos de salida
TEMAS = ["Sistema nervioso", "El ADN", "Las neuronas", "La fotosíntesis"]  # tecleados en el cierre

# ----------------------------------------------------------------------------
# GUION
# ----------------------------------------------------------------------------
ESCENAS = [
    dict(id="intro", titulo="BIOLOGÍA EN MINUTOS", rol="Células del sistema inmunológico",
         color=(90, 210, 255),
         texto="¡Hola! Soy Biología en Minutos, y hoy te voy a hablar sobre "
               "las células del sistema inmunológico."),
    dict(id="neutrofilo", titulo="NEUTRÓFILOS", rol="Primera línea de defensa",
         color=(255, 140, 190),
         texto="Primero, los neutrófilos. Son los primeros en llegar a una infección: "
               "devoran bacterias sin parar y mueren en la batalla. ¡El pus está hecho de ellos!"),
    dict(id="macrofago", titulo="MACRÓFAGOS", rol="Los grandes comelones",
         color=(255, 165, 70),
         texto="Luego llegan los macrófagos, los grandes comelones. Se tragan bacterias, "
               "virus y restos de células muertas, y lanzan alarmas para llamar refuerzos."),
    dict(id="dendritica", titulo="CÉLULAS DENDRÍTICAS", rol="Las mensajeras",
         color=(80, 230, 200),
         texto="Las células dendríticas son las mensajeras: capturan pedacitos del enemigo "
               "y se los presentan a los linfocitos T."),
    dict(id="t_helper", titulo="LINFOCITOS T CD4", rol="Los generales",
         color=(120, 155, 255),
         texto="Los linfocitos T colaboradores, o CD4, son los generales: "
               "dan las órdenes y activan a las demás células del ejército."),
    dict(id="linfocito_b", titulo="LINFOCITOS B", rol="Anticuerpos y opsonización",
         color=(255, 215, 70),
         texto="Los linfocitos B fabrican anticuerpos que se pegan al enemigo y lo marcan. "
               "A esto se le llama opsonización, y así los fagocitos se lo comen más fácil."),
    dict(id="t_citotoxico", titulo="LINFOCITOS T CD8", rol="Asesinos de precisión",
         color=(255, 85, 110),
         texto="Los linfocitos T citotóxicos, o CD8, son asesinos de precisión: "
               "detectan células infectadas por virus y las destruyen."),
    dict(id="nk", titulo="CÉLULAS NK", rol="Asesinas naturales",
         color=(190, 120, 255),
         texto="Las células NK, o asesinas naturales, patrullan tu cuerpo y eliminan "
               "células tumorales o sospechosas, sin entrenamiento previo."),
    dict(id="memoria", titulo="CÉLULAS DE MEMORIA", rol="Nunca olvidan",
         color=(255, 200, 110),
         texto="Y finalmente, las células de memoria: recuerdan a cada enemigo para atacarlo "
               "más rápido la próxima vez. ¡Por eso funcionan las vacunas!"),
    dict(id="outro", titulo="¿Y AHORA QUÉ?", rol="Tu turno",
         color=(120, 255, 160),
         texto="¿De qué te gustaría que fuera nuestro siguiente video? "
               "Déjalo en la caja de comentarios y regálame un follow."),
]

LEAD = 0.25   # silencio antes de que empiece a hablar en cada escena
PAD = 0.75    # respiro al final de cada escena
MIN_DUR = 5.0


# ----------------------------------------------------------------------------
# EFECTOS DE SONIDO (sintetizados)
# ----------------------------------------------------------------------------
def _t(d):
    return np.arange(int(d * SR)) / SR


def _sweep(f0, f1, d, onda="sin", curva="exp"):
    t = _t(d)
    if curva == "exp":
        f = f0 * (f1 / f0) ** (t / d)
    else:
        f = np.linspace(f0, f1, len(t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    if onda == "sin":
        return np.sin(ph)
    if onda == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if onda == "sq":
        return np.sign(np.sin(ph))
    return np.sin(ph)


def _lowpass(x, a):
    """Filtro de un polo; a puede ser escalar o array (0..1, más alto = más brillante)."""
    a = np.broadcast_to(np.asarray(a, dtype=np.float64), x.shape)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def _env(n, ataque=0.005, decay=8.0):
    t = np.arange(n) / SR
    return np.clip(t / ataque, 0, 1) * np.exp(-t * decay)


_rng = np.random.default_rng(7)


def _noise(d):
    return _rng.uniform(-1, 1, int(d * SR))


def sfx_whoosh():
    d = 0.5
    n = _noise(d)
    t = _t(d)
    a = 0.02 + 0.25 * np.sin(np.pi * t / d) ** 2
    y = _lowpass(n, a) * np.sin(np.pi * t / d) ** 1.5
    return y * 1.6


def sfx_ding():
    t = _t(0.9)
    y = sum(np.sin(2 * np.pi * f * t) * w for f, w in [(1318.5, 1), (1975.5, 0.5), (2637, 0.3)])
    return y * _env(len(t), 0.002, 5.5) * 0.45


def sfx_chime():
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate([1046.5, 1318.5, 1568, 2093]):
        t = _t(0.9)
        s = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * _env(len(t), 0.002, 5) * 0.35
        i0 = int(i * 0.08 * SR)
        out[i0:i0 + len(s)] += s
    return out


def sfx_nam():
    """Mordida caricaturesca: ñam-ñam + glup."""
    out = np.zeros(int(0.55 * SR))
    for k, t0 in enumerate([0.0, 0.14]):
        b = _sweep(340 - 40 * k, 110, 0.1) * _env(int(0.1 * SR), 0.003, 25)
        cr = _lowpass(_noise(0.06), 0.35) * _env(int(0.06 * SR), 0.001, 60) * 0.8
        i0 = int(t0 * SR)
        out[i0:i0 + len(b)] += b
        out[i0:i0 + len(cr)] += cr
    g = _sweep(180, 520, 0.13) * np.sin(np.pi * _t(0.13) / 0.13) * 0.8
    i0 = int(0.32 * SR)
    out[i0:i0 + len(g)] += g
    return out * 0.9


def sfx_pop():
    d = 0.09
    y = _sweep(380, 1400, d) * _env(int(d * SR), 0.001, 30)
    c = _noise(0.006) * 0.6
    y[:len(c)] += c
    return y * 0.8


def sfx_boing():
    """Resorte: para cuando un anticuerpo se pega (opsonización)."""
    d = 0.45
    t = _t(d)
    f = 520 * (1 + 0.35 * np.exp(-t * 6) * np.sin(2 * np.pi * 16 * t)) * (1 + 0.6 * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 6)
    return y * 0.6


def sfx_pew():
    d = 0.16
    return _sweep(1700, 420, d, "sq") * _env(int(d * SR), 0.001, 18) * 0.22


def sfx_zap():
    d = 0.4
    y = _sweep(1500, 160, d, "saw") * 0.6 + _noise(d) * 0.35
    y = _lowpass(y, 0.45) * _env(int(d * SR), 0.002, 7)
    return y * 1.1


def sfx_boom():
    d = 0.8
    t = _t(d)
    y = _sweep(110, 35, d) * _env(len(t), 0.002, 5) * 1.0
    y += _lowpass(_noise(d), np.linspace(0.5, 0.03, len(t))) * _env(len(t), 0.001, 6) * 1.4
    return y * 0.9


def sfx_blip():
    out = np.zeros(int(0.16 * SR))
    for i, f in enumerate([880, 1320]):
        s = np.sign(np.sin(2 * np.pi * f * _t(0.06))) * _env(int(0.06 * SR), 0.001, 20) * 0.18
        i0 = int(i * 0.07 * SR)
        out[i0:i0 + len(s)] += s
    return out


def sfx_alarma():
    out = np.zeros(int(0.75 * SR))
    for i in range(4):
        f = 950 if i % 2 == 0 else 720
        s = _sweep(f, f, 0.17, "sq")
        s = _lowpass(s, 0.3) * np.clip(np.sin(np.pi * _t(0.17) / 0.17) * 3, 0, 1) * 0.22
        i0 = int(i * 0.18 * SR)
        out[i0:i0 + len(s)] += s
    return out


def sfx_click():
    y = _noise(0.012) * _env(int(0.012 * SR), 0.0005, 250)
    y2 = np.sin(2 * np.pi * 2200 * _t(0.03)) * _env(int(0.03 * SR), 0.001, 120) * 0.4
    out = np.zeros(int(0.04 * SR))
    out[:len(y)] += y
    out[:len(y2)] += y2
    return out * 0.8


def sfx_tecla():
    return sfx_click() * 0.35


def sfx_splat():
    d = 0.3
    y = _lowpass(_noise(d), np.linspace(0.6, 0.05, int(d * SR))) * _env(int(d * SR), 0.001, 12)
    y += _sweep(300, 90, d) * _env(int(d * SR), 0.001, 14) * 0.6
    return y


def sfx_thud():
    d = 0.35
    return _sweep(160, 50, d) * _env(int(d * SR), 0.001, 12) * 0.9


SFX = {k[4:]: v() for k, v in list(globals().items()) if k.startswith("sfx_")}
SFX_VOL = {"whoosh": 0.5, "ding": 0.55, "chime": 0.6, "nam": 0.85, "pop": 0.55, "boing": 0.6,
           "pew": 0.45, "zap": 0.55, "boom": 0.75, "blip": 0.6, "alarma": 0.55, "click": 0.7,
           "tecla": 0.6, "splat": 0.6, "thud": 0.7}


def musica(dur):
    """Música juguetona y suave (pizzicato + bajo) para ir debajo de la voz."""
    n = int(dur * SR)
    out = np.zeros(n + SR * 2)
    bpm = 112
    beat = 60 / bpm
    prog = [(220.0, [0, 3, 7, 10]), (174.61, [0, 4, 7, 11]), (261.63, [0, 4, 7, 9]), (196.0, [0, 4, 7, 10])]
    rnd = random.Random(3)
    pluck_t = _t(0.35)
    i = 0
    while i * beat / 2 < dur:
        t0 = i * beat / 2
        compas = int(t0 / (beat * 4)) % len(prog)
        raiz, inter = prog[compas]
        if i % 2 == 0 or rnd.random() < 0.45:
            st = rnd.choice(inter) + 12 * rnd.choice([1, 1, 2])
            f = raiz * 2 ** (st / 12)
            s = (np.sin(2 * np.pi * f * pluck_t) + 0.25 * np.sin(4 * np.pi * f * pluck_t)) * _env(len(pluck_t), 0.003, 11)
            i0 = int(t0 * SR)
            out[i0:i0 + len(s)] += s * 0.25
        if i % 4 == 0:
            bt = _t(beat * 1.6)
            s = np.sin(2 * np.pi * raiz / 2 * bt) * _env(len(bt), 0.01, 3) * 0.35
            i0 = int(t0 * SR)
            out[i0:i0 + len(s)] += s
        i += 1
    out = out[:n]
    t = np.arange(n) / SR
    out *= np.clip(t / 1.5, 0, 1) * np.clip((dur - t) / 2.0, 0, 1)
    return out / (np.max(np.abs(out)) + 1e-6)


# ----------------------------------------------------------------------------
# SISTEMA DE EFECTOS (sonido + partículas + globos de cómic + temblor)
# ----------------------------------------------------------------------------
class FX:
    def __init__(self):
        self.sonidos = []      # (tiempo_global, nombre, volumen)
        self.bursts = []       # (t0, x, y, color, n, fuerza, seed)
        self.popups = []       # (t0, x, y, texto, color)
        self.shakes = []       # (t0, amplitud)
        self.flashes = []      # (t0, color)
        self.t_prev = -1.0
        self.t = 0.0
        self.t_glob = 0.0

    def frame(self, t_esc, t_prev, t_glob):
        self.t, self.t_prev, self.t_glob = t_esc, t_prev, t_glob

    def cruza(self, t0):
        return self.t_prev < t0 <= self.t

    def en(self, t0, sonido=None, x=None, y=None, color=(255, 255, 255), burst=0, texto=None,
           shake=0, flash=None, vol=1.0, fuerza=1.0):
        """Dispara un evento cuando el tiempo de la escena cruza t0."""
        if not self.cruza(t0):
            return False
        tg = self.t_glob - (self.t - t0)
        if sonido:
            self.sonidos.append((tg, sonido, vol))
        if burst and x is not None:
            self.bursts.append((tg, x, y, color, burst, fuerza, len(self.bursts)))
        if texto and x is not None:
            self.popups.append((tg, x, y, texto, color))
        if shake:
            self.shakes.append((tg, shake))
        if flash:
            self.flashes.append((tg, flash))
        return True

    def offset(self):
        a = 0.0
        for t0, amp in self.shakes:
            dt = self.t_glob - t0
            if 0 <= dt < 0.6:
                a += amp * math.exp(-dt * 9)
        tg = self.t_glob
        return a * math.sin(tg * 73), a * math.cos(tg * 61)

    def dibujar(self, fr, d):
        tg = self.t_glob
        for (t0, x, y, col, n, fuerza, seed) in self.bursts:
            dt = tg - t0
            if not (0 <= dt < 0.9):
                continue
            rnd = random.Random(seed)
            for _ in range(n):
                a = rnd.uniform(0, 2 * math.pi)
                v = rnd.uniform(250, 700) * fuerza
                px = x + v * dt * math.cos(a)
                py = y + v * dt * math.sin(a) + 500 * dt * dt
                r = rnd.uniform(6, 16) * (1 - dt / 0.9)
                c = mix(col, (255, 255, 255), rnd.uniform(0, 0.4))
                d.ellipse([px - r, py - r, px + r, py + r], fill=c)
        for (t0, x, y, txt, col) in self.popups:
            dt = tg - t0
            if not (0 <= dt < 1.0):
                continue
            globo_comic(d, x, y - 60 * dt, txt, col, ease_out_back(dt / 0.25), dt)

    def dibujar_flash(self, fr):
        for t0, col in self.flashes:
            dt = self.t_glob - t0
            if 0 <= dt < 0.25:
                a = 0.55 * (1 - dt / 0.25)
                return Image.blend(fr, Image.new("RGB", fr.size, col), a)
        return fr


def globo_comic(d, x, y, txt, col, p, dt):
    if p <= 0:
        return
    f = fuente(FONT_BOLD, max(4, int(62 * p)))
    tw = d.textlength(txt, font=f)
    rx, ry = tw / 2 + 50 * p, 70 * p
    rot = 0.15 * math.sin(dt * 12)
    pts = []
    for i in range(24):
        a = 2 * math.pi * i / 24 + rot
        k = 1.0 if i % 2 == 0 else 0.78
        pts.append((x + rx * k * math.cos(a), y + ry * k * math.sin(a)))
    d.polygon(pts, fill=(255, 255, 255), outline=(20, 20, 30))
    pts2 = [((px - x) * 0.86 + x, (py - y) * 0.86 + y) for px, py in pts]
    d.polygon(pts2, fill=col)
    d.text((x, y), txt, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=max(1, int(5 * p)),
           stroke_fill=(20, 20, 30))


# ----------------------------------------------------------------------------
# DIBUJO DE CÉLULAS CON SQUASH & STRETCH
# ----------------------------------------------------------------------------
def celula(fr, spr, t, x, y, esc=1.0, sx=1.0, sy=1.0, rot=0.0, alpha=1.0):
    if esc <= 0.01 or alpha <= 0.01:
        return
    img = spr.get(t, esc, alpha)
    if abs(sx - 1) > 0.01 or abs(sy - 1) > 0.01:
        img = img.resize((max(2, int(img.width * sx)), max(2, int(img.height * sy))), Image.BILINEAR)
    if abs(rot) > 0.5:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    fr.paste(img, (int(x - img.width / 2), int(y - img.height / 2)), img)


def respirar(t, k=1.0):
    """Squash & stretch suave en reposo."""
    s = 0.035 * k * math.sin(t * 4.2)
    return 1 + s, 1 - s


def mordida(t, tiempos, dur=0.28):
    """Deformación al comer: aplastamiento y rebote."""
    for t0 in tiempos:
        dt = t - t0
        if 0 <= dt < dur:
            q = math.sin(math.pi * dt / dur) * math.exp(-dt * 4)
            return 1 + 0.16 * q, 1 - 0.13 * q
    return 1.0, 1.0


def entrada_swoop(t, desde=(-700, 0), dur=0.75, giro=360):
    """Entrada desde fuera de cámara con giro y estiramiento."""
    p = clamp01(t / dur)
    e = ease_out_back(p)
    dx, dy = desde[0] * (1 - e), desde[1] * (1 - e)
    rot = giro * (1 - ease_in_out(p))
    estir = 1 + 0.25 * math.sin(math.pi * p) if p < 1 else 1.0
    return dx, dy, rot, estir


CY = 900


class Recursos:
    def __init__(self):
        print("Pre-renderizando sprites...")
        self.neut = Sprite(v1.spr_neutrofilo, 500)
        self.macro = Sprite(v1.spr_macrofago, 620)
        self.dend = Sprite(v1.spr_dendritica, 600)
        self.th = Sprite(v1.spr_t_helper, 460)
        self.tc = Sprite(v1.spr_t_cito, 440)
        self.b = Sprite(v1.spr_b, 420)
        self.nk = Sprite(v1.spr_nk, 440)
        self.mem = Sprite(v1.spr_memoria, 460)
        self.bact = Sprite(v1.spr_bacteria, 170)
        self.virus = Sprite(v1.spr_virus, 150)
        self.inf = Sprite(v1.spr_infectada, 330)
        self.tum = Sprite(v1.spr_tumoral, 330)
        self.sana = Sprite(lambda s, f: v1.spr_linfocito(s, f, (200, 230, 200, 255), (90, 150, 90, 255),
                                                          (70, 120, 70, 255), None), 260)
        self.ab = [v1.spr_anticuerpo(80, a) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        self.mini = {
            "neut": Sprite(v1.spr_neutrofilo, 190, 8), "macro": Sprite(v1.spr_macrofago, 210, 8),
            "dend": Sprite(v1.spr_dendritica, 210, 8), "th": Sprite(v1.spr_t_helper, 180, 8),
            "tc": Sprite(v1.spr_t_cito, 180, 8), "b": Sprite(v1.spr_b, 180, 8),
            "nk": Sprite(v1.spr_nk, 180, 8), "mem": Sprite(v1.spr_memoria, 180, 8),
        }


def ab_idx(ang):
    return int(((ang % (2 * math.pi)) / (2 * math.pi)) * 24) % 24


def presa_entrante(t, t_llegada, ang, dist0=620, viaje=1.6, cx=W / 2, cy=CY, radio_fin=60):
    """Posición de una bacteria/virus que se acerca nadando hasta ser comida."""
    p = clamp01((t - (t_llegada - viaje)) / viaje)
    if p <= 0:
        return None
    dist = lerp(dist0, radio_fin, ease_in_out(p))
    wig = 40 * math.sin(t * 7 + ang * 3) * (1 - p)
    x = cx + dist * math.cos(ang) - wig * math.sin(ang)
    y = cy + dist * math.sin(ang) * 0.9 + wig * math.cos(ang)
    return x, y, p


# ----------------------------------------------------------------------------
# ESCENAS
# ----------------------------------------------------------------------------
def esc_intro(fr, d, R, fx, t, dur, esc):
    # insignia de la marca con reloj
    p = ease_out_back(t / 0.6)
    fx.en(0.02, "whoosh")
    fx.en(0.45, "ding", W / 2, CY, esc["color"], burst=22, shake=10)
    r = 210 * p
    if r > 2:
        rr = r * (1 + 0.03 * math.sin(t * 5))
        d.ellipse([W / 2 - rr - 14, CY - rr - 14, W / 2 + rr + 14, CY + rr + 14], fill=(255, 255, 255))
        d.ellipse([W / 2 - rr, CY - rr, W / 2 + rr, CY + rr], fill=(25, 60, 120))
        # marcas del reloj
        for i in range(12):
            a = 2 * math.pi * i / 12
            d.line([(W / 2 + rr * 0.82 * math.cos(a), CY + rr * 0.82 * math.sin(a)),
                    (W / 2 + rr * 0.92 * math.cos(a), CY + rr * 0.92 * math.sin(a))], fill=esc["color"], width=6)
        # manecilla girando
        a = -math.pi / 2 + t * 4
        d.line([(W / 2, CY), (W / 2 + rr * 0.7 * math.cos(a), CY + rr * 0.7 * math.sin(a))],
               fill=(255, 220, 90), width=12)
        d.ellipse([W / 2 - 16, CY - 16, W / 2 + 16, CY + 16], fill=(255, 220, 90))
        f = fuente(FONT_BOLD, max(4, int(44 * p)))
        d.text((W / 2, CY + rr * 0.42), "EN MINUTOS", font=f, fill=(255, 255, 255), anchor="mm")
        f2 = fuente(FONT_BOLD, max(4, int(50 * p)))
        d.text((W / 2, CY - rr * 0.42), "BIOLOGÍA", font=f2, fill=(255, 255, 255), anchor="mm")
    # células que aparecen haciendo pop alrededor
    nombres = ["neut", "macro", "dend", "th", "b", "tc", "nk", "mem"]
    t_inicio = max(1.0, dur * 0.42)
    for i, n in enumerate(nombres):
        t0 = t_inicio + i * 0.22
        a = 2 * math.pi * i / len(nombres) - math.pi / 2 + t * 0.35
        x, y = W / 2 + 380 * math.cos(a), CY + 380 * math.sin(a)
        fx.en(t0, "pop", x, y, esc["color"], burst=8, vol=0.7, fuerza=0.5)
        q = clamp01((t - t0) / 0.4)
        if q > 0:
            sx, sy = respirar(t + i, 1.5)
            celula(fr, R.mini[n], t, x, y + 14 * math.sin(t * 3 + i), ease_out_back(q), sx, sy)


def esc_neutrofilo(fr, d, R, fx, t, dur, esc):
    dx, dy, rot, est = entrada_swoop(t, (-750, -200))
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY, esc["color"], burst=16)
    n = 4
    t_fin_comida = dur * 0.68
    tiempos = [1.6 + i * (t_fin_comida - 1.6) / (n - 1) for i in range(n)]
    t_muere = min(dur - 1.0, t_fin_comida + 1.0)
    # presas
    for i, te in enumerate(tiempos):
        ang = [2.6, -0.5, 0.6, 3.8][i]
        pos = presa_entrante(t, te, ang)
        if pos and t < te:
            x, y, p = pos
            celula(fr, R.bact, t + i, x, y, 1.0, rot=math.degrees(-ang) + 180 + 15 * math.sin(t * 9))
        txt = ["¡ÑAM!", "¡ÑAM!", "¡GLUP!", "¡ÑAM!"][i]
        fx.en(te, "nam", W / 2 + 140 * math.cos(ang), CY - 230, (130, 220, 90), burst=10, texto=txt, shake=6)
    if t < t_muere:
        sx, sy = respirar(t)
        mx, my = mordida(t, tiempos)
        celula(fr, R.neut, t, W / 2 + dx, CY + dy, est, sx * mx, sy * my, rot)
    else:
        # se "sacrifica": se desinfla y deja pus
        q = clamp01((t - t_muere) / 0.5)
        if q < 1:
            celula(fr, R.neut, t, W / 2, CY + 60 * q, 1 - 0.4 * q, 1 + 0.4 * q, 1 - 0.5 * q, 0, 1 - q)
        rnd = random.Random(2)
        for k in range(9):
            x = W / 2 + rnd.uniform(-180, 180)
            y = CY + 120 + rnd.uniform(-30, 40)
            r = rnd.uniform(25, 55) * ease_out_back(q)
            d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=(235, 220, 130))
    fx.en(t_muere, "splat", W / 2, CY + 100, (235, 220, 130), burst=18, texto="PUS", shake=8)


def esc_macrofago(fr, d, R, fx, t, dur, esc):
    dx, dy, rot, est = entrada_swoop(t, (800, 150), giro=-300)
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY, esc["color"], burst=16)
    t_alarma = dur * 0.62
    n = 5
    tiempos = [1.4 + i * (t_alarma - 0.4 - 1.4) / (n - 1) for i in range(n)]
    angs = [3.0, -0.4, 1.9, 0.5, 4.2]
    estir_x = 1.0
    for i, te in enumerate(tiempos):
        pos = presa_entrante(t, te, angs[i], radio_fin=90)
        spr = R.virus if i % 2 else R.bact
        if pos and t < te:
            x, y, p = pos
            celula(fr, spr, t + i, x, y, 1.0, rot=(15 * math.sin(t * 9) if i % 2 == 0 else t * 90))
            if p > 0.6:  # pseudópodo que se estira hacia la presa
                estir_x = max(estir_x, 1 + 0.12 * (p - 0.6) / 0.4)
        txt = ["¡ÑAM!", "¡CHOMP!", "¡ÑAM!", "¡GLUP!", "¡ÑAM!"][i]
        fx.en(te, "nam", W / 2 + 150 * math.cos(angs[i]), CY - 260, (255, 190, 90), burst=10, texto=txt, shake=7)
    # alarma -> refuerzos
    fx.en(t_alarma, "alarma", W / 2, CY - 300, (255, 80, 80), texto="¡ALERTA!", shake=5)
    if t > t_alarma:
        for k in range(3):
            fase = ((t - t_alarma) * 0.9 + k / 3) % 1
            r = 320 + fase * 380
            d.ellipse([W / 2 - r, CY - r, W / 2 + r, CY + r], outline=mix((20, 15, 20), (255, 90, 80), 1 - fase),
                      width=7)
        for j in range(3):
            t0 = t_alarma + 0.6 + j * 0.3
            fx.en(t0, "whoosh", vol=0.6)
            q = clamp01((t - t0) / 0.6)
            if q > 0:
                x = W / 2 + (j - 1) * 300
                y = lerp(H + 150, CY + 380, ease_out_back(q))
                celula(fr, R.mini["neut"], t + j, x, y, 0.9, rot=10 * math.sin(t * 6 + j))
    sx, sy = respirar(t, 1.4)
    mx, my = mordida(t, tiempos, 0.35)
    celula(fr, R.macro, t, W / 2 + dx, CY + dy, est, sx * mx * estir_x, sy * my, rot + 6 * math.sin(t * 1.5))


def esc_dendritica(fr, d, R, fx, t, dur, esc):
    dx, dy, rot, est = entrada_swoop(t, (0, -900), giro=540)
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY, esc["color"], burst=16)
    tiempos = [1.3, 1.9, 2.5]
    angs = [-0.5, 2.7, 1.2]
    t_mueve = max(3.1, dur * 0.42)
    mov = ease_in_out((t - t_mueve) / 0.9)
    cx = W / 2 - 170 * mov
    for i, te in enumerate(tiempos):
        pos = presa_entrante(t, te, angs[i], radio_fin=50, viaje=1.1)
        if pos and t < te:
            x, y, p = pos
            celula(fr, R.virus, t + i, x, y, 0.85, rot=t * 120)
        fx.en(te, "pop", W / 2, CY - 200, esc["color"], burst=8, texto="¡TE TENGO!" if i == 0 else None)
    fx.en(t_mueve, "whoosh", vol=0.7)
    # linfocito T que recibe el mensaje
    t_t = t_mueve + 0.5
    q = clamp01((t - t_t) / 0.6)
    t_presenta = t_t + 0.9
    if q > 0:
        sx, sy = respirar(t, 1.2)
        act = clamp01((t - t_presenta - 0.2) / 0.3)
        esc_t = 1.25 * ease_out_back(q) * (1 + 0.15 * math.sin(math.pi * act) * (act < 1))
        celula(fr, R.mini["th"], t, lerp(W + 200, W / 2 + 300, ease_out_back(q)), CY + 30, esc_t, sx, sy)
    fx.en(t_presenta, "blip", W / 2 + 70, CY - 60, esc["color"], texto="¡MIRA ESTO!")
    fx.en(t_presenta + 0.5, "ding", W / 2 + 300, CY + 30, (120, 155, 255), burst=14, vol=0.8)
    if t > t_presenta:
        # antígeno brillando en la punta
        b = 0.5 + 0.5 * math.sin(t * 10)
        x0 = cx + 150
        col = mix(esc["color"], (255, 80, 100), b)
        d.polygon([(x0, CY - 10), (x0 + 50, CY + 30), (x0, CY + 70)], fill=col, outline=(255, 255, 255))
        # señal punteada
        for k in range(5):
            u = ((t * 1.5 + k / 5) % 1)
            x = lerp(x0 + 60, W / 2 + 200, u)
            d.ellipse([x - 7, CY + 23, x + 7, CY + 37], fill=(255, 255, 255))
    sx, sy = respirar(t, 1.3)
    celula(fr, R.dend, t, cx + dx, CY + dy, est, sx, sy, rot + 8 * math.sin(t * 2))


def gorra_general(d, x, y, esc):
    """Gorra de general sobre el linfocito T CD4."""
    w = 170 * esc
    d.polygon([(x - w, y), (x + w, y), (x + w * 0.75, y - w * 0.75), (x - w * 0.75, y - w * 0.75)], fill=(30, 50, 110),
              outline=(10, 20, 50))
    d.rounded_rectangle([x - w * 1.15, y - 14 * esc, x + w * 1.15, y + 16 * esc], radius=int(12 * esc),
                        fill=(20, 30, 70))
    # estrella
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        R_ = (36 if i % 2 == 0 else 15) * esc
        pts.append((x + R_ * math.cos(a), y - w * 0.38 + R_ * math.sin(a)))
    d.polygon(pts, fill=(255, 215, 70))


def esc_t_helper(fr, d, R, fx, t, dur, esc):
    # cae desde arriba y rebota
    q = clamp01(t / 0.8)
    yb = lerp(-400, CY, min(1, q * q * 1.6)) if q < 0.79 else CY
    rebote = 0
    if t > 0.5:
        rebote = -60 * abs(math.sin((t - 0.5) * 9)) * math.exp(-(t - 0.5) * 5)
    fx.en(0.05, "whoosh")
    fx.en(0.5, "thud", W / 2, CY + 200, esc["color"], burst=14, shake=12)
    fx.en(0.75, "ding", vol=0.8)
    otros = ["b", "tc", "macro", "nk", "neut"]
    n = len(otros)
    t_ini = 1.6
    paso = (dur * 0.85 - t_ini) / n
    for i, nm in enumerate(otros):
        t0 = t_ini + i * paso
        ang = -math.pi / 2 + 2 * math.pi * (i + 0.5) / n
        x, y = W / 2 + 390 * math.cos(ang), CY + 380 * math.sin(ang)
        fx.en(t0, "blip", vol=0.8)
        fx.en(t0 + 0.4, "pop", x, y, esc["color"], burst=10, texto="¡ACTIVADO!" if i == 0 else None)
        if t > t0:
            u = clamp01((t - t0) / 0.4)
            sx_, sy_ = lerp(W / 2, x, u), lerp(CY, y, u)
            d.line([(W / 2, CY), (sx_, sy_)], fill=mix((20, 20, 40), esc["color"], 0.9), width=6)
            d.ellipse([sx_ - 14, sy_ - 14, sx_ + 14, sy_ + 14], fill=(230, 240, 255))
        apagada = t < t0 + 0.4
        a = clamp01((t - t0 - 0.4) / 0.4)
        esc_c = 0.6 if apagada else 0.6 + 0.4 * ease_out_back(a)
        celula(fr, R.mini[nm], t, x, y + (0 if apagada else 12 * math.sin(t * 6 + i)), esc_c,
               alpha=0.45 if apagada else 1.0)
    sx, sy = respirar(t, 1.3)
    pulso = 1 + 0.06 * max(0, math.sin(t * 7)) if t > t_ini else 1
    y = yb + rebote
    celula(fr, R.th, t, W / 2, y, pulso, sx, sy)
    gorra_general(d, W / 2, y - 150 * pulso, pulso)


def esc_b(fr, d, R, fx, t, dur, esc):
    dx, dy, rot, est = entrada_swoop(t, (-800, 300))
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY + 230, esc["color"], burst=14)
    bx, by = W / 2, CY + 230
    objetivos = [(W / 2 - 290, CY - 250), (W / 2, CY - 330), (W / 2 + 290, CY - 250)]
    t_disp_fin = dur * 0.52
    n_ab = 12
    pegados = [0, 0, 0]
    disparos = [1.0 + k * (t_disp_fin - 1.0) / n_ab for k in range(n_ab)]
    for k, t0 in enumerate(disparos):
        j = k % 3
        fx.en(t0, "pew", vol=0.7)
        ox, oy = objetivos[j]
        fx.en(t0 + 0.55, "boing", ox, oy, esc["color"], burst=6, vol=0.8,
              texto="¡MARCADA!" if k == 2 else None, fuerza=0.4)
    # el macrófago llega y se come a las marcadas
    t_macro = t_disp_fin + 0.4
    tiempos_comer = [t_macro + 0.9 + j * 0.65 for j in range(3)]
    q_m = clamp01((t - t_macro) / 0.7)
    fx.en(t_macro, "whoosh")
    if q_m > 0:
        # el macrófago recorre las bacterias de izquierda a derecha
        if t < tiempos_comer[0]:
            mx = lerp(-250, objetivos[0][0], ease_out_back(q_m))
            my = objetivos[0][1]
        else:
            seg = min(2, int((t - tiempos_comer[0]) / 0.65))
            u = ease_in_out(clamp01((t - tiempos_comer[0] - seg * 0.65) / 0.45))
            a, b = objetivos[seg], objetivos[min(2, seg + 1)]
            mx, my = lerp(a[0], b[0], u), lerp(a[1], b[1], u)
    for k, t0 in enumerate(disparos):
        j = k % 3
        p = clamp01((t - t0) / 0.55)
        if p <= 0 or t >= tiempos_comer[j]:
            continue
        ox, oy = objetivos[j]
        ang = math.atan2(oy - by, ox - bx)
        if p < 1:
            x, y = lerp(bx, ox, ease_in_out(p)), lerp(by + 0, oy, ease_in_out(p))
            fr.paste(R.ab[ab_idx(ang)], (int(x - 40), int(y - 40)), R.ab[ab_idx(ang)])
    for j, (ox, oy) in enumerate(objetivos):
        if t >= tiempos_comer[j]:
            continue
        n_peg = sum(1 for k, t0 in enumerate(disparos) if k % 3 == j and t >= t0 + 0.55)
        if n_peg:
            r = 95 + 6 * math.sin(t * 8)
            d.ellipse([ox - r, oy - r, ox + r, oy + r], outline=esc["color"], width=5)
        celula(fr, R.bact, t + j, ox + 6 * math.sin(t * 10 + j), oy, 1.0, rot=10 * math.sin(t * 5 + j))
        for m in range(n_peg):
            a2 = math.pi / 2 + (m - (n_peg - 1) / 2) * 0.7 + math.pi
            x, y = ox + 75 * math.cos(a2), oy + 75 * math.sin(a2)
            img = R.ab[ab_idx(a2 + math.pi)]
            fr.paste(img, (int(x - 40), int(y - 40)), img)
        fx.en(tiempos_comer[j], "nam", ox, oy - 150, (255, 190, 90), burst=10, texto="¡ÑAM!", shake=6)
    sx, sy = respirar(t)
    disparando = any(0 <= t - t0 < 0.15 for t0 in disparos)
    celula(fr, R.b, t, bx + dx, by + dy, est * (1.08 if disparando else 1), sx, sy, rot)
    if q_m > 0:
        mxs, mys = mordida(t, tiempos_comer, 0.3)
        celula(fr, R.mini["macro"], t, mx, my, 1.35, mxs, mys)


def esc_t_cito(fr, d, R, fx, t, dur, esc):
    dx, dy, rot, est = entrada_swoop(t, (-800, 0), giro=0)
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2 - 200, CY, esc["color"], burst=14)
    ix, iy = W / 2 + 240, CY
    t_mira = 1.4
    t_ataque = max(2.6, dur * 0.5)
    t_boom = t_ataque + 0.9
    acerca = ease_in_out((t - t_mira) / (t_ataque - t_mira))
    tx = lerp(W / 2 - 240, W / 2 - 70, acerca)
    fx.en(t_mira, "blip", ix, iy - 230, (255, 80, 100), texto="¡INFECTADA!")
    fx.en(t_mira + 0.3, "blip", vol=0.7)
    for k in range(4):
        fx.en(t_ataque + k * 0.15, "pew", vol=0.7)
    fx.en(t_boom, "boom", ix, iy, (180, 200, 160), burst=30, texto="¡ZAS!", shake=22, flash=(255, 255, 255),
          fuerza=1.3)
    if t < t_boom:
        if t > t_mira:  # retícula de mira
            r = 210 + 20 * math.sin(t * 8)
            col = (255, 80, 100)
            d.ellipse([ix - r, iy - r, ix + r, iy + r], outline=col, width=6)
            for a in range(4):
                an = a * math.pi / 2 + t * 1.5
                d.line([(ix + (r - 30) * math.cos(an), iy + (r - 30) * math.sin(an)),
                        (ix + (r + 30) * math.cos(an), iy + (r + 30) * math.sin(an))], fill=col, width=6)
        temb = 0 if t < t_ataque else 10 * math.sin(t * 60)
        hinch = 1 + (0.18 * clamp01((t - t_ataque) / 0.9) if t > t_ataque else 0)
        celula(fr, R.inf, t, ix + temb, iy, hinch)
        for k in range(10):
            q = clamp01((t - t_ataque - k * 0.06) / 0.35)
            if 0 < q < 1:
                x = lerp(tx + 140, ix - 60, q)
                y = iy + (k - 4.5) * 16
                d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(255, 225, 235), outline=(200, 50, 80))
    else:
        # virus liberados que se desvanecen
        q = clamp01((t - t_boom) / 1.2)
        for k in range(5):
            a = k * 2 * math.pi / 5 + 0.3
            dist = 60 + 300 * ease_in_out(q)
            celula(fr, R.virus, t + k, ix + dist * math.cos(a), iy + dist * math.sin(a), 0.6 * (1 - q) + 0.05,
                   alpha=1 - q, rot=t * 200)
    sx, sy = respirar(t)
    emp = 1.12 if 0 <= t - t_ataque < 0.5 else 1.0
    celula(fr, R.tc, t, tx + dx, CY + dy, est, sx * emp, sy / emp, rot)


def esc_nk(fr, d, R, fx, t, dur, esc):
    fx.en(0.05, "whoosh")
    fx.en(0.6, "ding", W / 2, CY - 300, esc["color"], burst=14)
    sana_x, sana_y = W / 2 - 220, CY + 280
    tum_x, tum_y = W / 2 + 230, CY + 230
    t_scan1 = 1.3
    t_scan2 = max(2.8, dur * 0.42)
    t_kill = t_scan2 + 1.1
    # recorrido: entra -> sobre la sana -> sobre la tumoral
    if t < t_scan1:
        u = ease_out_back(clamp01(t / 0.9))
        nx, ny = lerp(-300, sana_x, u), lerp(CY - 350, sana_y - 330, u)
    elif t < t_scan2:
        u = ease_in_out(clamp01((t - t_scan1 - 0.9) / 0.8))
        nx, ny = lerp(sana_x, tum_x, u), sana_y - 330 + 40 * math.sin(u * math.pi) - (tum_y - sana_y) * 0
        ny = lerp(sana_y - 330, tum_y - 330, u)
    else:
        u = ease_in_out(clamp01((t - t_scan2 - 0.6) / 0.4))
        nx, ny = tum_x - 40 * u, lerp(tum_y - 330, tum_y - 230, u)
    fx.en(t_scan1 + 0.35, "ding", sana_x, sana_y - 150, (120, 230, 120), texto="¡SANA!",
          vol=0.5)
    fx.en(t_scan2 + 0.35, "alarma", tum_x, tum_y - 170, (255, 80, 140), texto="¡SOSPECHOSA!", vol=0.7)
    fx.en(t_kill - 0.25, "zap", vol=0.9)
    fx.en(t_kill, "boom", tum_x, tum_y, (170, 120, 150), burst=28, texto="¡POW!", shake=20, flash=(230, 200, 255))
    # rayo de escaneo
    for (ts, x, y, col) in [(t_scan1, sana_x, sana_y, (120, 230, 120)), (t_scan2, tum_x, tum_y, (255, 80, 140))]:
        if ts < t < ts + 0.8:
            yy = y - 120 + 240 * ((t - ts) / 0.8)
            d.line([(x - 150, yy), (x + 150, yy)], fill=col, width=8)
            d.polygon([(nx - 40, ny + 150), (nx + 40, ny + 150), (x + 150, yy), (x - 150, yy)],
                      outline=col)
    celula(fr, R.sana, t, sana_x, sana_y + 8 * math.sin(t * 3), 1.0)
    if t < t_kill:
        temb = 8 * math.sin(t * 50) if t > t_scan2 + 0.35 else 0
        celula(fr, R.tum, t, tum_x + temb, tum_y, 1.0)
    if t_kill - 0.25 < t < t_kill + 0.1:
        # rayo
        pts = [(nx, ny + 120)]
        rnd = random.Random(int(t * 30))
        for k in range(1, 6):
            pts.append((lerp(nx, tum_x, k / 6) + rnd.uniform(-30, 30), lerp(ny + 120, tum_y, k / 6)))
        pts.append((tum_x, tum_y))
        d.line(pts, fill=(255, 240, 120), width=12)
        d.line(pts, fill=(255, 255, 255), width=4)
    sx, sy = respirar(t, 1.3)
    celula(fr, R.nk, t, nx, ny, 0.85, sx, sy, 8 * math.sin(t * 4))


def esc_memoria(fr, d, R, fx, t, dur, esc):
    fx.en(0.05, "chime", W / 2, CY, esc["color"], burst=24)
    q = ease_out_back(t / 0.7)
    for k in range(3):
        fase = (t * 0.5 + k / 3) % 1
        r = 230 + fase * 320
        d.ellipse([W / 2 - r, CY - r, W / 2 + r, CY + r], outline=mix((15, 12, 20), esc["color"], 0.7 * (1 - fase)),
                  width=5)
    # recuerdos: enemigos fantasma orbitando
    for i in range(5):
        a = 2 * math.pi * i / 5 + t * 0.7
        al = 0.5 * clamp01((t - 0.6 - i * 0.15) / 0.4)
        if al > 0:
            spr = R.virus if i % 2 else R.bact
            celula(fr, spr, t + i, W / 2 + 390 * math.cos(a), CY + 390 * math.sin(a), 0.7, alpha=al, rot=t * 40)
    # un virus conocido vuelve... ¡y cae al instante!
    t_vuelve = max(2.0, dur * 0.36)
    t_cae = t_vuelve + 0.9
    fx.en(t_vuelve, "whoosh", vol=0.6)
    fx.en(t_cae - 0.15, "zap", vol=0.7)
    fx.en(t_cae, "pop", W / 2 + 300, CY - 120, (255, 90, 90), burst=20, texto="¡TE RECUERDO!", shake=10)
    if t_vuelve < t < t_cae:
        u = (t - t_vuelve) / 0.9
        celula(fr, R.virus, t, lerp(W + 100, W / 2 + 300, ease_in_out(u)), CY - 120, 1.0, rot=t * 150)
    sx, sy = respirar(t, 1.2)
    celula(fr, R.mem, t, W / 2, CY, q * (1 + 0.05 * math.sin(t * 3)), sx, sy)
    # sello VACUNAS
    t_sello = max(t_cae + 0.8, dur * 0.72)
    fx.en(t_sello, "thud", W / 2, CY + 360, (255, 220, 150), burst=16, shake=14)
    if t > t_sello - 0.2:
        p = clamp01((t - t_sello + 0.2) / 0.2)
        s = lerp(2.4, 1.0, p)
        f = fuente(FONT_BOLD, int(72 * s))
        ang_y = CY + 360
        d.rounded_rectangle([W / 2 - 230 * s, ang_y - 60 * s, W / 2 + 230 * s, ang_y + 60 * s], radius=int(20 * s),
                            outline=(255, 90, 90), width=int(8 * s))
        d.text((W / 2, ang_y), "VACUNAS", font=f, fill=(255, 90, 90), anchor="mm")


def esc_outro(fr, d, R, fx, t, dur, esc):
    # caja de comentarios
    fx.en(0.05, "whoosh")
    p = ease_out_back(t / 0.6)
    bx0, by0, bx1, by1 = 90, CY - 400, W - 90, CY - 100
    if p > 0:
        cy = (by0 + by1) / 2
        h2 = (by1 - by0) / 2 * p
        d.rounded_rectangle([bx0, cy - h2, bx1, cy + h2], radius=36, fill=(245, 246, 250), outline=(255, 255, 255))
        if p > 0.8:
            f = fuente(FONT_BOLD, 40)
            d.text((bx0 + 40, by0 + 45), "Comentarios", font=f, fill=(30, 30, 40), anchor="lm")
            d.ellipse([bx0 + 40, by0 + 110, bx0 + 130, by0 + 200], fill=esc["color"])
            d.text((bx0 + 85, by0 + 155), "?", font=fuente(FONT_BOLD, 50), fill=(255, 255, 255), anchor="mm")
            d.rounded_rectangle([bx0 + 160, by0 + 115, bx1 - 40, by0 + 195], radius=40, fill=(225, 228, 238))
            temas = TEMAS
            t_esc = max(0.0, t - 0.7)
            ciclo = 2.0
            idx = int(t_esc / ciclo) % len(temas)
            u = (t_esc % ciclo)
            tema = temas[idx]
            nchar = min(len(tema), int(u * 14))
            for c in range(1, len(tema) + 1):
                fx.en(0.7 + int(t_esc / ciclo) * ciclo + c / 14, "tecla", vol=0.6)
            txt = tema[:nchar] + ("|" if int(t * 3) % 2 == 0 else "")
            d.text((bx0 + 190, by0 + 155), txt, font=fuente(FONT_REG, 44), fill=(40, 40, 60), anchor="lm")
    # botón seguir + cursor
    t_click = max(2.6, dur * 0.62)
    bcy = CY + 70
    q = ease_out_back((t - 0.6) / 0.6)
    if q > 0:
        seguido = t >= t_click
        bw, bh = 520 * q, 130 * q
        pres = 0.92 if 0 <= t - t_click < 0.12 else 1.0
        bw, bh = bw * pres, bh * pres
        col = (60, 200, 120) if seguido else (255, 60, 100)
        d.rounded_rectangle([W / 2 - bw / 2, bcy - bh / 2, W / 2 + bw / 2, bcy + bh / 2], radius=int(bh / 2),
                            fill=col, outline=(255, 255, 255), width=5)
        f = fuente(FONT_BOLD, max(4, int(58 * q * pres)))
        d.text((W / 2, bcy), "SIGUIENDO" if seguido else "SEGUIR", font=f, fill=(255, 255, 255), anchor="mm")
    fx.en(t_click, "click", W / 2, bcy, (255, 220, 90), burst=36, shake=8, fuerza=1.2)
    fx.en(t_click + 0.08, "chime", W / 2, bcy - 140, (60, 200, 120), texto="¡GRACIAS!")
    # mano/cursor
    if t > 1.2:
        u = ease_in_out(clamp01((t - 1.2) / (t_click - 1.3)))
        hx, hy = lerp(W - 150, W / 2 + 80, u), lerp(H - 250, bcy + 30, u)
        if t >= t_click:
            hy += 14 * math.exp(-(t - t_click) * 6)
        d.ellipse([hx - 34, hy - 34, hx + 34, hy + 34], fill=(255, 255, 255), outline=(30, 30, 40), width=5)
        d.ellipse([hx - 12, hy - 12, hx + 12, hy + 12], fill=(30, 30, 40))
    # células saludando abajo
    nombres = ["neut", "macro", "th", "b", "nk"]
    for i, n in enumerate(nombres):
        q2 = clamp01((t - 0.3 - i * 0.1) / 0.5)
        if q2 > 0:
            x = W / 2 + (i - 2) * 200
            y = CY + 330 + 25 * math.sin(t * 5 + i)
            sx, sy = respirar(t * 1.5 + i, 2)
            celula(fr, R.mini[n], t, x, y, 0.8 * ease_out_back(q2), sx, sy, 12 * math.sin(t * 4 + i))


ANIM = {
    "intro": esc_intro, "neutrofilo": esc_neutrofilo, "macrofago": esc_macrofago, "dendritica": esc_dendritica,
    "t_helper": esc_t_helper, "linfocito_b": esc_b, "t_citotoxico": esc_t_cito, "nk": esc_nk,
    "memoria": esc_memoria, "outro": esc_outro,
}


# ----------------------------------------------------------------------------
# SUBTÍTULOS
# ----------------------------------------------------------------------------
def palabras_con_tiempo(texto, ini, fin):
    pal = texto.split()
    pesos = []
    for p in pal:
        w = len(p) + 2.5
        if p.endswith((",", ":")):
            w += 4
        if p.endswith((".", "!", "?")):
            w += 7
        pesos.append(w)
    tot = sum(pesos)
    out, acc = [], 0.0
    for p, w in zip(pal, pesos):
        a = ini + acc / tot * (fin - ini)
        acc += w
        out.append([a, ini + acc / tot * (fin - ini), p])
    return out


def agrupar(palabras, max_chars=30):
    grupos, act = [], []
    for w in palabras:
        largo = len(" ".join(x[2] for x in act + [w]))
        if act and largo > max_chars:
            grupos.append(act)
            act = []
        act.append(w)
        if w[2].endswith((".", "!", "?", ":")) and len(" ".join(x[2] for x in act)) > 10:
            grupos.append(act)
            act = []
    if act:
        grupos.append(act)
    return grupos


def dibujar_karaoke(d, grupos, t, color):
    for g in grupos:
        if g[0][0] <= t < g[-1][1] + 0.05:
            break
    else:
        return
    f = fuente(FONT_BOLD, 70)
    esp = d.textlength(" ", font=f)
    palabras = [w[2].upper() for w in g]
    anchos = [d.textlength(p, font=f) for p in palabras]
    lineas, act, ancho = [], [], 0
    maxw = W - 140
    for i, a in enumerate(anchos):
        if act and ancho + esp + a > maxw:
            lineas.append(act)
            act, ancho = [], 0
        ancho += (esp if act else 0) + a
        act.append(i)
    lineas.append(act)
    entra = ease_out_back((t - g[0][0]) / 0.18)
    y0 = 1530 - (len(lineas) - 1) * 45 + 30 * (1 - clamp01(entra))
    for li, idxs in enumerate(lineas):
        tot = sum(anchos[i] for i in idxs) + esp * (len(idxs) - 1)
        x = W / 2 - tot / 2
        y = y0 + li * 90
        for i in idxs:
            a, b, _ = g[i]
            activo = a <= t < b
            if activo:
                pad = 12
                d.rounded_rectangle([x - pad, y - 46, x + anchos[i] + pad, y + 44], radius=16, fill=color)
            d.text((x, y), palabras[i], font=f, fill=(255, 255, 255) if not activo else (15, 15, 25), anchor="lm",
                   stroke_width=0 if activo else 7, stroke_fill=(0, 0, 0))
            x += anchos[i] + esp


def hud(d, idx, t_esc, dur, esc, total):
    m, gap = 40, 10
    bw = (W - 2 * m - gap * (total - 1)) / total
    for i in range(total):
        x = m + i * (bw + gap)
        d.rounded_rectangle([x, 60, x + bw, 68], radius=4, fill=(60, 60, 80))
        fill = 1.0 if i < idx else (clamp01(t_esc / dur) if i == idx else 0)
        if fill > 0:
            d.rounded_rectangle([x, 60, x + bw * fill, 68], radius=4, fill=(255, 255, 255))
    d.text((W / 2, 128), MARCA, font=fuente(FONT_BOLD, 34), fill=mix((210, 210, 225), esc["color"], 0.4), anchor="mm")
    p = ease_out_back((t_esc - 0.15) / 0.5)
    if p > 0:
        tam = 84 if len(esc["titulo"]) <= 16 else 68
        ft = fuente(FONT_BOLD, max(4, int(tam * min(1.0, p) + tam * 0.15 * (p - 1) * (p > 1))))
        wob = 3 * math.sin(t_esc * 3)
        d.text((W / 2, 265 + wob), esc["titulo"], font=ft, fill=esc["color"], anchor="mm", stroke_width=6,
               stroke_fill=(5, 5, 20))
        fr_ = fuente(FONT_BOLD, 40)
        tw = d.textlength(esc["rol"], font=fr_)
        a = clamp01((t_esc - 0.35) / 0.3)
        if a > 0:
            y = 370
            xoff = (1 - ease_out_back(a)) * 300
            d.rounded_rectangle([W / 2 - tw / 2 - 30 + xoff, y - 34, W / 2 + tw / 2 + 30 + xoff, y + 34], radius=34,
                                fill=mix((20, 20, 35), esc["color"], 0.35), outline=esc["color"], width=3)
            d.text((W / 2 + xoff, y), esc["rol"], font=fr_, fill=(255, 255, 255), anchor="mm")


def fmt_srt(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def fmt_mmss(s):
    return f"{int(s // 60)}:{s % 60:05.2f}"


# ----------------------------------------------------------------------------
# DURACIONES
# ----------------------------------------------------------------------------
def leer_audio(path):
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", str(SR), tmp], check=True)
    a, _ = sf.read(tmp, dtype="float32")
    os.remove(tmp)
    return a


def duraciones_habla(args):
    """Devuelve (lista de duraciones de habla por escena, lista de audios o None)."""
    if args.voz_dir:
        archivos = sorted(glob.glob(os.path.join(args.voz_dir, "escena_*")))
        assert len(archivos) == len(ESCENAS), f"Se esperaban {len(ESCENAS)} audios escena_XX en {args.voz_dir}"
        audios = [leer_audio(a) for a in archivos]
        return [len(a) / SR for a in audios], audios
    from kokoro_onnx import Kokoro
    k = Kokoro(args.modelo, args.voces)
    durs = []
    for e in ESCENAS:
        s, sr = k.create(e["texto"], voice=args.voz_ref, speed=args.velocidad, lang="es")
        # recorta silencios de los extremos
        s = np.asarray(s)
        idx = np.where(np.abs(s) > 0.02)[0]
        durs.append((idx[-1] - idx[0]) / sr if len(idx) else len(s) / sr)
        print(f"  {e['id']}: {durs[-1]:.2f}s")
    return durs, None


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", help="kokoro .onnx (solo para estimar tiempos)")
    ap.add_argument("--voces", help="voices .bin de kokoro")
    ap.add_argument("--voz-ref", default="em_alex")
    ap.add_argument("--velocidad", type=float, default=1.0)
    ap.add_argument("--voz-dir", help="carpeta con escena_01.mp3 ... (audios reales de ElevenLabs)")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("Calculando tiempos...")
    habla, audios = duraciones_habla(args)
    duraciones = [max(MIN_DUR, LEAD + h + PAD) for h in habla]
    inicios = np.concatenate([[0], np.cumsum(duraciones)])
    total = float(inicios[-1])
    print(f"Duración total: {total:.1f}s")

    # subtítulos
    karaoke, srt, guion = [], [], []
    n_srt = 1
    guion.append(f"GUION PARA ELEVENLABS — {MARCA}\n")
    guion.append("Genera un audio por escena y colócalo en el tiempo indicado,\n"
                 f"o pásame los audios (escena_01.mp3 ... escena_{len(ESCENAS):02d}.mp3) y re-sincronizo el video.\n")
    for i, (e, h) in enumerate(zip(ESCENAS, habla)):
        ini = inicios[i] + LEAD
        pal = palabras_con_tiempo(e["texto"], LEAD, LEAD + h)
        grupos = agrupar(pal)
        karaoke.append(grupos)
        for g in grupos:
            srt.append(f"{n_srt}\n{fmt_srt(inicios[i] + g[0][0])} --> {fmt_srt(inicios[i] + g[-1][1])}\n"
                       f"{' '.join(w[2] for w in g)}\n")
            n_srt += 1
        guion.append(f"\n[ESCENA {i + 1:02d} — {e['titulo']}]  empieza en {fmt_mmss(ini)}  "
                     f"(duración aprox. de la voz: {h:.1f}s)\n{e['texto']}\n")
    guion.append("\n\nTEXTO COMPLETO (para pegar de una sola vez):\n\n" + "\n\n".join(e["texto"] for e in ESCENAS) + "\n")
    with open(os.path.join(args.out, "subtitulos.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    with open(os.path.join(args.out, "guion_elevenlabs.txt"), "w", encoding="utf-8") as f:
        f.write("".join(guion))

    R = Recursos()
    fx = FX()
    fondos = [v1.fondo_base(e["color"]) for e in ESCENAS]

    tmp = tempfile.mkdtemp()
    video_mudo = os.path.join(tmp, "video.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           video_mudo]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n_frames = int(math.ceil(total * FPS))
    t_prev_esc, idx_prev = -1.0, -1
    for fi in range(n_frames):
        t = fi / FPS
        idx = min(len(ESCENAS) - 1, int(np.searchsorted(inicios, t, side="right") - 1))
        esc = ESCENAS[idx]
        t_esc = t - inicios[idx]
        dur = duraciones[idx]
        if idx != idx_prev:
            t_prev_esc, idx_prev = -1.0, idx
        fx.frame(t_esc, t_prev_esc, t)
        t_prev_esc = t_esc

        fr = fondos[idx].copy()
        d = ImageDraw.Draw(fr)
        v1.dibujar_particulas(d, t, esc["color"])
        ANIM[esc["id"]](fr, d, R, fx, t_esc, dur, esc)
        fx.dibujar(fr, d)
        ox, oy = fx.offset()
        if abs(ox) + abs(oy) > 0.5:
            fr = fr.transform(fr.size, Image.AFFINE, (1, 0, -ox, 0, 1, -oy), fillcolor=(5, 5, 15))
        fr = fx.dibujar_flash(fr)
        d = ImageDraw.Draw(fr)
        hud(d, idx, t_esc, dur, esc, len(ESCENAS))
        dibujar_karaoke(d, karaoke[idx], t_esc, esc["color"])
        # transición: barrido de color
        if t_esc < 0.18 and idx > 0:
            a = 1 - t_esc / 0.18
            fr = Image.blend(fr, Image.new("RGB", fr.size, mix((0, 0, 0), esc["color"], 0.5)), a * 0.8)
        if idx == len(ESCENAS) - 1:
            fr = Image.blend(Image.new("RGB", fr.size, (0, 0, 0)), fr, clamp01((dur - t_esc) / 0.5))
        proc.stdin.write(fr.tobytes())
        if fi % (FPS * 5) == 0:
            print(f"  frame {fi}/{n_frames}")
    proc.stdin.close()
    proc.wait()

    # audio: efectos (+ transiciones) + música (+ voz si la hay)
    n = int(total * SR) + SR
    efectos = np.zeros(n)
    for i in range(1, len(ESCENAS)):
        fx.sonidos.append((inicios[i] - 0.05, "whoosh", 0.35))
    for (tg, nombre, vol) in fx.sonidos:
        s = SFX[nombre] * SFX_VOL[nombre] * vol
        i0 = int(max(0, tg) * SR)
        efectos[i0:i0 + len(s)] += s[:max(0, n - i0)]
    voz = np.zeros(n)
    if audios:
        for i, a in enumerate(audios):
            i0 = int((inicios[i] + LEAD) * SR)
            voz[i0:i0 + len(a)] += a[:max(0, n - i0)]
    mus = np.pad(musica(total), (0, n - int(total * SR)))
    pistas = {
        f"{NOMBRE}.mp4": efectos * 0.55 + mus * 0.12 + voz,
        f"{NOMBRE}_sin_musica.mp4": efectos * 0.55 + voz,
    }
    if audios:  # con voz: los efectos y música más bajos para no tapar
        pistas = {f"{NOMBRE}_con_voz.mp4": efectos * 0.35 + mus * 0.07 + voz * 0.95}
    for nombre, a in pistas.items():
        a = a[:int(total * SR)]
        pico = np.max(np.abs(a)) + 1e-6
        if pico > 0.97:
            a = a / pico * 0.97
        wav = os.path.join(tmp, "a.wav")
        sf.write(wav, a.astype(np.float32), SR)
        salida = os.path.join(args.out, nombre)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video_mudo, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", "-movflags", "+faststart", salida], check=True)
        print("Listo:", salida)


if __name__ == "__main__":
    main()

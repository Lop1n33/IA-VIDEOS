#!/usr/bin/env python3
"""
Reel — "Biología en Minutos": EL SISTEMA INMUNE INNATO.

Mismo formato que el reel v2 (sin voz, subtítulos karaoke, onomatopeyas y
efectos caricaturescos). Reutiliza el motor de ../sistema_inmune_v2/generar.py
y agrega escenas nuevas (división innato/adaptativo, barreras, redes de los
neutrófilos, mastocitos, eosinófilos y resumen).

Las animaciones clave se sincronizan con la palabra del guion en la que se
mencionan (por ejemplo, el muro aparece cuando se dice "piel").

Uso:
    python generar.py --modelo kokoro.onnx --voces voices.bin --out .
    python generar.py --voz-dir audios_elevenlabs --out .   # con tus audios reales
"""
import importlib.util
import math
import os
import random

import numpy as np
from PIL import Image

_v2p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sistema_inmune_v2", "generar.py")
_spec = importlib.util.spec_from_file_location("reel_v2", _v2p)
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)
v1 = v2.v1

W, H, CY = v2.W, v2.H, v2.CY
fuente, mix, lerp, clamp01 = v2.fuente, v2.mix, v2.lerp, v2.clamp01
ease_out_back, ease_in_out = v2.ease_out_back, v2.ease_in_out
celula, respirar, mordida, entrada_swoop, presa_entrante = (v2.celula, v2.respirar, v2.mordida,
                                                           v2.entrada_swoop, v2.presa_entrante)
FONT_BOLD, FONT_REG = v2.FONT_BOLD, v2.FONT_REG
Sprite = v2.Sprite

# ----------------------------------------------------------------------------
# GUION
# ----------------------------------------------------------------------------
ESCENAS = [
    dict(id="intro", titulo="BIOLOGÍA EN MINUTOS", rol="Sistema inmune innato",
         color=(90, 210, 255),
         texto="¡Hola! Soy Biología en Minutos. Como recordarán, en el video pasado hablamos sobre "
               "las células del sistema inmunológico. Pero... ¿sabías que el sistema inmunológico se divide en dos?"),
    dict(id="division", titulo="INNATO VS ADAPTATIVO", rol="Dos sistemas, un equipo",
         color=(150, 170, 255),
         texto="Por un lado está el sistema inmune innato, y por el otro, el sistema inmune adaptativo. "
               "¡Y hoy vamos a hablar del sistema inmune innato!"),
    dict(id="barreras", titulo="EL SISTEMA INNATO", rol="Primera línea de defensa",
         color=(90, 220, 255),
         texto="El sistema innato es tu primera línea de defensa: naces con él y responde en minutos "
               "contra cualquier invasor. Su primera barrera son la piel y las mucosas."),
    dict(id="neutrofilo", titulo="NEUTRÓFILOS", rol="Los primeros en llegar",
         color=(255, 140, 190),
         texto="Si un microbio logra pasar, llegan los neutrófilos, los primeros en la escena. "
               "Devoran bacterias y hasta lanzan redes para atraparlas."),
    dict(id="macrofago", titulo="MACRÓFAGOS", rol="Los grandes comelones",
         color=(255, 165, 70),
         texto="Después, los macrófagos se comen a los microbios y a las células muertas, y liberan citocinas: "
               "alarmas que provocan inflamación y llaman refuerzos."),
    dict(id="dendritica", titulo="CÉLULAS DENDRÍTICAS", rol="El puente al adaptativo",
         color=(80, 230, 200),
         texto="Las células dendríticas capturan pedacitos del enemigo y se los muestran a los linfocitos. "
               "¡Son el puente hacia el sistema adaptativo!"),
    dict(id="nk", titulo="CÉLULAS NK", rol="Asesinas naturales",
         color=(190, 120, 255),
         texto="Las células NK, o asesinas naturales, revisan a las células de tu cuerpo, "
               "y si encuentran una infectada o tumoral, ¡la destruyen!"),
    dict(id="mastocito", titulo="MASTOCITOS", rol="Bombas de histamina",
         color=(120, 140, 255),
         texto="Los mastocitos están llenos de gránulos de histamina. Cuando detectan peligro, los liberan "
               "y provocan inflamación... ¡y también las alergias!"),
    dict(id="eosinofilo", titulo="EOSINÓFILOS", rol="Cazadores de parásitos",
         color=(255, 120, 90),
         texto="Los eosinófilos combaten parásitos, como los gusanos, que son demasiado grandes para comérselos. "
               "¡Así que los atacan con sustancias tóxicas!"),
    dict(id="resumen", titulo="EN RESUMEN", rol="Sistema inmune innato",
         color=(120, 230, 255),
         texto="En resumen: el sistema innato es rápido y siempre actúa igual, pero no tiene memoria. "
               "Para eso está el sistema adaptativo, ¡del que hablaremos en el próximo video!"),
    dict(id="outro", titulo="¿Y AHORA QUÉ?", rol="Tu turno",
         color=(120, 255, 160),
         texto="¿Y de qué otro tema te gustaría que habláramos? "
               "Déjalo en la caja de comentarios y regálame un follow."),
]

TEMAS = ["Sistema adaptativo", "Las alergias", "Las vacunas", "El sistema nervioso"]


# ----------------------------------------------------------------------------
# SINCRONÍA CON PALABRAS DEL GUION
# ----------------------------------------------------------------------------
_orig_dur = v2.duraciones_habla


def _dur_con_registro(args):
    durs, audios = _orig_dur(args)
    for e, h in zip(v2.ESCENAS, durs):
        e["_habla"] = h
    return durs, audios


def tpal(esc, sub, k=0, fin=False):
    """Tiempo (dentro de la escena) en que se dice la palabra que contiene `sub` (k-ésima aparición)."""
    pal = v2.palabras_con_tiempo(esc["texto"], v2.LEAD, v2.LEAD + esc["_habla"])
    m = [w for w in pal if sub.lower() in w[2].lower()]
    w = m[min(k, len(m) - 1)]
    return w[1] if fin else w[0]


# ----------------------------------------------------------------------------
# SONIDOS NUEVOS
# ----------------------------------------------------------------------------
def sfx_achu():
    """Estornudo caricaturesco: "aaah... ¡CHÚ!"."""
    sr = v2.SR
    ah = v2._sweep(240, 380, 0.4, "saw")
    ah = v2._lowpass(ah, 0.12) * np.clip(np.linspace(0, 1.4, len(ah)), 0, 1) * 0.5
    ch = v2._noise(0.32)
    ch = (ch - v2._lowpass(ch, 0.25)) * v2._env(len(ch), 0.003, 9) * 1.2
    out = np.zeros(int(0.85 * sr))
    out[:len(ah)] += ah
    i0 = int(0.45 * sr)
    out[i0:i0 + len(ch)] += ch
    return out


def sfx_buzz():
    """Sonido de "incorrecto"."""
    out = np.zeros(int(0.55 * v2.SR))
    for i in range(2):
        s = v2._lowpass(v2._sweep(150, 140, 0.2, "sq"), 0.25) * 0.5
        i0 = int(i * 0.25 * v2.SR)
        out[i0:i0 + len(s)] += s
    return out


def sfx_tic():
    t = v2._t(0.03)
    return np.sin(2 * np.pi * 3200 * t) * v2._env(len(t), 0.0005, 160) * 0.5


v2.SFX.update({"achu": sfx_achu(), "buzz": sfx_buzz(), "tic": sfx_tic()})
v2.SFX_VOL.update({"achu": 0.8, "buzz": 0.5, "tic": 0.5})


# ----------------------------------------------------------------------------
# SPRITES NUEVOS
# ----------------------------------------------------------------------------
def spr_mastocito(size, fase):
    img, d, s, c, r = v1.celula_base(size, fase, (185, 190, 255, 255), (80, 90, 200, 255), 0.06, 5)
    v1.granulos(d, c, r, (70, 40, 150, 255), 70, 11, 0.2, 0.9, 0.07)
    rr = r * 0.26
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(50, 50, 130, 255))
    return v1.finalizar(img, size, (120, 140, 255))


def spr_eosinofilo(size, fase):
    img, d, s, c, r = v1.celula_base(size, fase, (255, 200, 190, 255), (220, 90, 80, 255), 0.05, 6)
    v1.granulos(d, c, r, (240, 90, 60, 255), 45, 12, 0.3, 0.9, 0.06)
    for dx in (-0.3, 0.3):
        x = c + dx * r
        rr = r * 0.27
        d.ellipse([x - rr, c - rr * 1.1, x + rr, c + rr * 1.1], fill=(70, 70, 170, 255))
    d.line([(c - 0.3 * r, c), (c + 0.3 * r, c)], fill=(70, 70, 170, 255), width=int(r * 0.1))
    return v1.finalizar(img, size, (255, 120, 90))


def spr_polen(size, fase):
    img, s = v1.lienzo(size)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    c, r = s / 2, s * 0.27
    pts = []
    for i in range(32):
        a = 2 * math.pi * i / 32 + fase * 0.1
        R = r * (1.35 if i % 2 == 0 else 1.0)
        pts.append((c + R * math.cos(a), c + R * math.sin(a)))
    d.polygon(pts, fill=(230, 170, 30, 255))
    d.ellipse([c - r, c - r, c + r, c + r], fill=(255, 215, 70, 255))
    for i in range(7):
        a = i * 0.9
        x, y = c + r * 0.55 * math.cos(a), c + r * 0.55 * math.sin(a)
        d.ellipse([x - r * 0.12, y - r * 0.12, x + r * 0.12, y + r * 0.12], fill=(230, 160, 20, 255))
    return v1.finalizar(img, size)


class Recursos(v2.Recursos):
    def __init__(self):
        super().__init__()
        self.mast = Sprite(spr_mastocito, 480)
        self.eos = Sprite(spr_eosinofilo, 300)
        self.polen = Sprite(spr_polen, 150)
        self.mini["eos"] = Sprite(spr_eosinofilo, 180, 8)
        self.mini["mast"] = Sprite(spr_mastocito, 180, 8)


# ----------------------------------------------------------------------------
# ELEMENTOS GRÁFICOS
# ----------------------------------------------------------------------------
def escudo(d, x, y, s, col):
    pts = [(x - 150 * s, y - 170 * s), (x + 150 * s, y - 170 * s), (x + 150 * s, y + 10 * s),
           (x, y + 190 * s), (x - 150 * s, y + 10 * s)]
    d.polygon(pts, fill=(255, 255, 255))
    pts2 = [((px - x) * 0.85 + x, (py - y) * 0.85 + y) for px, py in pts]
    d.polygon(pts2, fill=col)
    f = fuente(FONT_BOLD, max(4, int(78 * s)))
    d.text((x, y - 10 * s), "1ª", font=f, fill=(255, 255, 255), anchor="mm", stroke_width=max(1, int(4 * s)),
           stroke_fill=(20, 40, 80))


def cronometro(d, x, y, s, t, col):
    r = 95 * s
    d.rectangle([x - 16 * s, y - r - 40 * s, x + 16 * s, y - r], fill=(230, 230, 240))
    d.ellipse([x - r - 10 * s, y - r - 10 * s, x + r + 10 * s, y + r + 10 * s], fill=(230, 230, 240))
    d.ellipse([x - r, y - r, x + r, y + r], fill=(25, 40, 70))
    a = -math.pi / 2 + t * 6
    d.line([(x, y), (x + r * 0.8 * math.cos(a), y + r * 0.8 * math.sin(a))], fill=col, width=max(1, int(9 * s)))
    d.ellipse([x - 10 * s, y - 10 * s, x + 10 * s, y + 10 * s], fill=col)


def palomita(d, x, y, s, col, p=1.0):
    """Check (✓) dibujado progresivamente."""
    a, b, c = (x - 30 * s, y), (x - 8 * s, y + 24 * s), (x + 34 * s, y - 26 * s)
    if p < 0.4:
        q = p / 0.4
        d.line([a, (lerp(a[0], b[0], q), lerp(a[1], b[1], q))], fill=col, width=int(12 * s))
    else:
        q = (p - 0.4) / 0.6
        d.line([a, b, (lerp(b[0], c[0], q), lerp(b[1], c[1], q))], fill=col, width=int(12 * s), joint="curve")


def tache(d, x, y, s, col):
    d.line([(x - 26 * s, y - 26 * s), (x + 26 * s, y + 26 * s)], fill=col, width=int(12 * s))
    d.line([(x - 26 * s, y + 26 * s), (x + 26 * s, y - 26 * s)], fill=col, width=int(12 * s))


def gusano(d, t, x, y, esc, alpha_col=1.0, temb=0.0):
    """Parásito (gusano) segmentado y ondulante."""
    n = 26
    base = mix((40, 20, 40), (235, 150, 175), alpha_col)
    borde = mix((40, 20, 40), (170, 80, 110), alpha_col)
    puntos = []
    for i in range(n):
        u = i / (n - 1)
        px = x + (u - 0.5) * 620 * esc
        py = y + math.sin(u * 7 + t * 4) * 55 * esc + temb * math.sin(t * 50 + i)
        puntos.append((px, py, (38 - 14 * abs(u - 0.35) * 2) * esc))
    for px, py, r in puntos:
        d.ellipse([px - r - 5, py - r - 5, px + r + 5, py + r + 5], fill=borde)
    for px, py, r in puntos:
        d.ellipse([px - r, py - r, px + r, py + r], fill=base)
    # cara
    hx, hy, hr = puntos[0]
    for dy in (-12, 12):
        d.ellipse([hx - 14 * esc, hy + dy * esc - 8 * esc, hx + 2 * esc, hy + dy * esc + 8 * esc], fill=(255, 255, 255))
        d.ellipse([hx - 11 * esc, hy + dy * esc - 4 * esc, hx - 3 * esc, hy + dy * esc + 4 * esc], fill=(20, 20, 30))


def panel(d, x0, y0, x1, y1, col, alpha=1.0):
    d.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=mix((12, 12, 28), col, 0.28 * alpha),
                        outline=mix((12, 12, 28), col, alpha), width=6)


# ----------------------------------------------------------------------------
# ESCENAS NUEVAS
# ----------------------------------------------------------------------------
def esc_intro(fr, d, R, fx, t, dur, esc):
    t_rec = tpal(esc, "recordarán")
    t_cel = tpal(esc, "células")
    t_pero = tpal(esc, "Pero")
    t_dos = tpal(esc, "dos?")
    # insignia de la marca (se encoge cuando aparece el recuerdo)
    fx.en(0.02, "whoosh")
    fx.en(0.45, "ding", W / 2, CY, esc["color"], burst=22, shake=10)
    p = ease_out_back(t / 0.6)
    enc = 1 - 0.55 * ease_in_out((t - t_rec + 0.3) / 0.5)
    sal = ease_in_out((t - t_pero + 0.2) / 0.4)
    r = 210 * p * enc * (1 - sal)
    by = lerp(CY, CY - 360, (1 - enc) / 0.55)
    if r > 4:
        d.ellipse([W / 2 - r - 14, by - r - 14, W / 2 + r + 14, by + r + 14], fill=(255, 255, 255))
        d.ellipse([W / 2 - r, by - r, W / 2 + r, by + r], fill=(25, 60, 120))
        a = -math.pi / 2 + t * 4
        d.line([(W / 2, by), (W / 2 + r * 0.7 * math.cos(a), by + r * 0.7 * math.sin(a))], fill=(255, 220, 90),
               width=max(2, int(12 * r / 210)))
        k = r / 210
        d.text((W / 2, by - r * 0.42), "BIOLOGÍA", font=fuente(FONT_BOLD, max(4, int(50 * k))), fill=(255, 255, 255),
               anchor="mm")
        d.text((W / 2, by + r * 0.42), "EN MINUTOS", font=fuente(FONT_BOLD, max(4, int(44 * k))),
               fill=(255, 255, 255), anchor="mm")
    # tarjeta "VIDEO ANTERIOR"
    fx.en(t_rec, "whoosh")
    fx.en(t_rec + 0.4, "pop", W / 2, CY + 60, esc["color"], burst=10, texto="¡REPASO!")
    q = ease_out_back((t - t_rec) / 0.5)
    if q > 0 and sal < 1:
        xo = (1 - q) * -900 + sal * 1100
        x0, y0, x1, y1 = 110 + xo, CY - 170, W - 110 + xo, CY + 300
        panel(d, x0, y0, x1, y1, esc["color"])
        d.text(((x0 + x1) / 2, y0 + 55), "EN EL VIDEO ANTERIOR", font=fuente(FONT_BOLD, 40), fill=(255, 255, 255),
               anchor="mm")
        # icono de "rebobinar"
        rx, ry = x0 + 70, y0 + 55
        for k in range(2):
            d.polygon([(rx + k * 28, ry), (rx + 28 + k * 28, ry - 20), (rx + 28 + k * 28, ry + 20)],
                      fill=esc["color"])
        nombres = ["neut", "macro", "dend", "th", "b", "tc", "nk", "mem"]
        for i, n in enumerate(nombres):
            ti = t_cel + i * 0.12
            fx.en(ti, "pop", vol=0.45)
            a = clamp01((t - ti) / 0.35)
            if a > 0:
                fila, col = divmod(i, 4)
                x = x0 + (x1 - x0) * (0.14 + col * 0.24)
                y = y0 + 180 + fila * 160 + 10 * math.sin(t * 4 + i)
                celula(fr, R.mini[n], t, x, y, 0.75 * ease_out_back(a))
    # gran signo de interrogación con un "2"
    fx.en(t_pero, "boing", W / 2, CY, (255, 220, 90))
    fx.en(t_dos, "thud", W / 2, CY + 80, (255, 220, 90), burst=20, texto="¡EN DOS!", shake=14)
    qq = ease_out_back((t - t_pero) / 0.45)
    if qq > 0.02 and t > t_pero:
        f = fuente(FONT_BOLD, max(4, int(360 * qq)))
        rot_y = 15 * math.sin(t * 5)
        d.text((W / 2, CY + rot_y), "?", font=f, fill=(255, 220, 90), anchor="mm", stroke_width=10,
               stroke_fill=(40, 20, 0))
        if t > t_dos:
            q2 = ease_out_back((t - t_dos) / 0.4)
            d.ellipse([W / 2 + 120 - 90 * q2, CY - 200 - 90 * q2, W / 2 + 120 + 90 * q2, CY - 200 + 90 * q2],
                      fill=(255, 80, 120), outline=(255, 255, 255), width=6)
            d.text((W / 2 + 120, CY - 200), "2", font=fuente(FONT_BOLD, max(4, int(110 * q2))), fill=(255, 255, 255),
                   anchor="mm")


def esc_division(fr, d, R, fx, t, dur, esc):
    t_inn = tpal(esc, "innato,")
    t_ada = tpal(esc, "adaptativo.")
    t_hoy = tpal(esc, "hoy")
    C_INN, C_ADA = (90, 220, 255), (200, 130, 255)
    fx.en(t_inn - 0.25, "whoosh")
    fx.en(t_inn + 0.2, "ding", W / 4, CY - 250, C_INN, burst=14)
    fx.en(t_ada - 0.25, "whoosh")
    fx.en(t_ada + 0.2, "ding", 3 * W / 4, CY - 250, C_ADA, burst=14)
    fx.en(t_hoy, "whoosh", vol=0.8)
    fx.en(t_hoy + 0.55, "thud", W / 2, CY - 430, (255, 220, 90), burst=18, shake=14, texto="¡HOY!")
    gana = ease_in_out((t - t_hoy) / 0.55)
    # panel innato (izquierda -> crece al centro)
    pi = ease_out_back((t - t_inn + 0.25) / 0.5)
    if pi > 0:
        x0 = lerp(lerp(-500, 40, pi), 60, gana)
        x1 = lerp(lerp(-40, W / 2 - 15, pi), W - 60, gana)
        y0, y1 = CY - 330, CY + 380
        panel(d, x0, y0, x1, y1, C_INN)
        cx = (x0 + x1) / 2
        d.text((cx, y0 + 70), "INNATO", font=fuente(FONT_BOLD, int(lerp(56, 84, gana))), fill=C_INN, anchor="mm",
               stroke_width=5, stroke_fill=(5, 5, 20))
        d.text((cx, y0 + 140), "Rápido · Nace contigo", font=fuente(FONT_REG, int(lerp(30, 42, gana))),
               fill=(230, 235, 245), anchor="mm")
        n = ["neut", "macro", "nk", "dend"] if gana > 0.5 else ["neut", "macro"]
        for i, nm in enumerate(n):
            col, fila = (i % 2, i // 2)
            x = cx + (col - 0.5) * lerp(200, 360, gana)
            y = CY + 60 + fila * 210 * (1 if len(n) > 2 else 0) + (0 if len(n) > 2 else 60) + 12 * math.sin(t * 4 + i)
            sx, sy = respirar(t + i, 1.5)
            celula(fr, R.mini[nm], t, x, y - (90 if len(n) > 2 else 0), lerp(0.85, 1.05, gana), sx, sy)
    # panel adaptativo (derecha -> sale por la derecha)
    pa = ease_out_back((t - t_ada + 0.25) / 0.5)
    if pa > 0 and gana < 1:
        x0 = lerp(W + 40, W / 2 + 15, pa) + gana * 700
        x1 = lerp(W + 500, W - 40, pa) + gana * 700
        y0, y1 = CY - 330, CY + 380
        panel(d, x0, y0, x1, y1, C_ADA)
        cx = (x0 + x1) / 2
        d.text((cx, y0 + 70), "ADAPTATIVO", font=fuente(FONT_BOLD, 50), fill=C_ADA, anchor="mm", stroke_width=5,
               stroke_fill=(5, 5, 20))
        d.text((cx, y0 + 140), "Específico · Memoria", font=fuente(FONT_REG, 30), fill=(230, 235, 245), anchor="mm")
        for i, nm in enumerate(["th", "b"]):
            x = cx + (i - 0.5) * 200
            celula(fr, R.mini[nm], t, x, CY + 120 + 12 * math.sin(t * 4 + i), 0.85)
    # "VS"
    if pi > 0 and pa > 0 and gana < 0.3:
        s = ease_out_back((t - t_ada) / 0.4) * (1 - gana / 0.3)
        if s > 0.05:
            d.ellipse([W / 2 - 60 * s, CY - 60 * s, W / 2 + 60 * s, CY + 60 * s], fill=(255, 80, 120),
                      outline=(255, 255, 255), width=5)
            d.text((W / 2, CY), "VS", font=fuente(FONT_BOLD, max(4, int(52 * s))), fill=(255, 255, 255), anchor="mm")
    # sello "HOY"
    if t > t_hoy + 0.35:
        p = clamp01((t - t_hoy - 0.35) / 0.2)
        s = lerp(2.2, 1.0, p)
        y = CY - 430
        d.rounded_rectangle([W / 2 - 130 * s, y - 55 * s, W / 2 + 130 * s, y + 55 * s], radius=int(18 * s),
                            fill=(255, 220, 90), outline=(255, 255, 255), width=int(6 * s))
        d.text((W / 2, y), "HOY", font=fuente(FONT_BOLD, int(70 * s)), fill=(40, 25, 0), anchor="mm")


def esc_barreras(fr, d, R, fx, t, dur, esc):
    t_def = tpal(esc, "defensa:")
    t_min = tpal(esc, "minutos")
    t_cual = tpal(esc, "cualquier")
    t_piel = tpal(esc, "piel")
    t_muc = tpal(esc, "mucosas")
    sal = ease_in_out((t - t_piel + 0.4) / 0.4)
    # escudo
    fx.en(max(0.3, t_def - 0.6), "ding", W / 2, CY - 120, esc["color"], burst=18)
    p = ease_out_back((t - max(0.3, t_def - 0.6) + 0.2) / 0.5)
    if p > 0 and sal < 1:
        escudo(d, W / 2 - 160 * ease_in_out((t - t_min + 0.3) / 0.4) - sal * 900, CY - 120 + 8 * math.sin(t * 3),
               p, (40, 110, 200))
    # cronómetro
    fx.en(t_min, "pop", W / 2 + 200, CY - 120, (255, 220, 90), burst=10, texto="¡RÁPIDO!")
    if t > t_min - 0.3 and sal < 1:
        q = ease_out_back((t - t_min + 0.3) / 0.4)
        cronometro(d, W / 2 + 200 + sal * 900, CY - 110, q, t * 3, (255, 220, 90))
        if int(t * 6) != int((t - 1 / 30) * 6):
            fx.en(t, "tic", vol=0.6)
    # invasores variados
    if t_cual - 0.2 < t < t_piel:
        for i in range(3):
            q = clamp01((t - t_cual - i * 0.15) / 0.4)
            spr = [R.bact, R.virus, R.polen][i]
            x = W / 2 + (i - 1) * 260
            celula(fr, spr, t + i, x - sal * 0, CY + 300 + 15 * math.sin(t * 6 + i), ease_out_back(q),
                   rot=20 * math.sin(t * 5 + i))
            fx.en(t_cual + i * 0.15, "pop", vol=0.5)
    # muro de piel y mucosas
    fx.en(t_piel, "thud", W / 2, CY + 220, (240, 180, 150), burst=20, shake=14)
    hm = ease_out_back((t - t_piel) / 0.5)
    wy = CY + 120
    if hm > 0.12:
        alto = 200 * hm
        filas = 4
        for fila in range(filas):
            y0 = wy + fila * alto / filas
            off = 0 if fila % 2 == 0 else 90
            for k in range(-1, 7):
                x0 = 40 + k * 180 + off
                d.rounded_rectangle([x0 + 4, y0 + 4, x0 + 176, y0 + alto / filas - 4], radius=10,
                                    fill=(240, 180, 150) if fila < 2 else (250, 150, 160), outline=(170, 100, 90),
                                    width=3)
        if hm > 0.9:
            d.text((W / 2, wy - 50), "PIEL", font=fuente(FONT_BOLD, 54), fill=(255, 210, 190), anchor="mm",
                   stroke_width=5, stroke_fill=(40, 10, 10))
    if t > t_muc - 0.1:
        d.text((W / 2, wy + 280), "MUCOSAS", font=fuente(FONT_BOLD, 54), fill=(255, 170, 180), anchor="mm",
               stroke_width=5, stroke_fill=(40, 10, 20))
    # invasores rebotan contra el muro
    if t > t_piel + 0.3:
        for i in range(4):
            per = 1.2
            u = ((t - t_piel - 0.3 - i * 0.3) % per) / per
            if t - t_piel - 0.3 - i * 0.3 < 0:
                continue
            x = 180 + i * 240
            y = wy - 70 - 380 * (1 - (2 * u - 1) ** 2)
            spr = [R.bact, R.virus, R.polen, R.bact][i]
            celula(fr, spr, t + i, x, y, 0.85, rot=t * 120 * (1 if i % 2 else -1))
            n_rebote = int((t - t_piel - 0.3 - i * 0.3) / per)
            fx.en(t_piel + 0.3 + i * 0.3 + n_rebote * per, "boing", x, wy - 60, esc["color"], vol=0.6, burst=4,
                  texto="¡TOING!" if (i == 1 and n_rebote == 0) else None, fuerza=0.4)


def esc_neutrofilo(fr, d, R, fx, t, dur, esc):
    t_dev = tpal(esc, "Devoran")
    t_red = tpal(esc, "redes")
    dx, dy, rot, est = entrada_swoop(t, (-750, -200))
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY, esc["color"], burst=16)
    tiempos = [t_dev + 0.1, t_dev + 0.75]
    for i, te in enumerate(tiempos):
        ang = [2.6, -0.5][i]
        pos = presa_entrante(t, te, ang, viaje=1.3)
        if pos and t < te:
            x, y, _ = pos
            celula(fr, R.bact, t + i, x, y, 1.0, rot=math.degrees(-ang) + 180 + 15 * math.sin(t * 9))
        fx.en(te, "nam", W / 2 + 140 * math.cos(ang), CY - 230, (130, 220, 90), burst=10,
              texto=["¡ÑAM!", "¡GLUP!"][i], shake=6)
    # red (NET) que atrapa bacterias abajo
    tx, ty = W / 2, CY + 400
    fx.en(t_red - 0.1, "whoosh")
    fx.en(t_red + 0.35, "splat", tx, ty - 160, (230, 240, 255), texto="¡ATRAPADAS!", shake=8)
    lanz = clamp01((t - t_red) / 0.4)
    for i in range(3):
        x = tx + (i - 1) * 190
        y = ty + 18 * math.sin(t * 6 + i) * (1 - lanz)
        quieta = lanz >= 1
        celula(fr, R.bact, t + i, x + (0 if quieta else 25 * math.sin(t * 8 + i)), y, 0.9,
               rot=0 if quieta else 25 * math.sin(t * 7 + i))
    if lanz > 0:
        r = 330 * ease_out_back(lanz)
        col = (235, 240, 255)
        for k in range(12):
            a = math.pi * k / 11
            d.line([(tx, ty - 130 + 130 * (1 - lanz)), (tx + r * math.cos(a) * 1.1, ty - 130 + r * math.sin(a) * 0.6)],
                   fill=col, width=4)
        for rr in (0.35, 0.6, 0.85, 1.0):
            pts = [(tx + r * rr * 1.1 * math.cos(math.pi * k / 11), ty - 130 + r * rr * 0.6 * math.sin(math.pi * k / 11))
                   for k in range(12)]
            d.line(pts, fill=col, width=4)
    sx, sy = respirar(t)
    mx, my = mordida(t, tiempos)
    lanzando = 1.12 if 0 <= t - t_red < 0.3 else 1.0
    celula(fr, R.neut, t, W / 2 + dx, CY - 60 + dy, est * 0.9, sx * mx * lanzando, sy * my / lanzando, rot)


def esc_mastocito(fr, d, R, fx, t, dur, esc):
    t_gran = tpal(esc, "gránulos")
    t_det = tpal(esc, "detectan")
    t_lib = tpal(esc, "liberan")
    t_inf = tpal(esc, "inflamación")
    t_ale = tpal(esc, "alergias!")
    dx, dy, rot, est = entrada_swoop(t, (0, 900), giro=-360)
    fx.en(0.05, "whoosh")
    fx.en(0.7, "ding", W / 2, CY, esc["color"], burst=16)
    fx.en(t_gran, "pop", W / 2 + 220, CY - 200, esc["color"], texto="HISTAMINA", vol=0.6)
    # alérgeno (polen) que se acerca
    fx.en(t_det, "alarma", W / 2 - 250, CY - 260, (255, 200, 60), texto="¡PELIGRO!", vol=0.7)
    if t_det - 1.0 < t < t_lib + 0.2:
        u = ease_in_out((t - t_det + 1.0) / 1.0)
        celula(fr, R.polen, t, lerp(-120, W / 2 - 230, u), lerp(CY - 400, CY - 160, u), 1.0, rot=t * 90)
    # degranulación
    rnd = random.Random(5)
    n = 26
    for k in range(n):
        tk = t_lib + k * 0.03
        if k % 4 == 0:
            fx.en(tk, "pop", vol=0.45)
        q = clamp01((t - tk) / 1.3)
        if 0 < q < 1:
            a = rnd.uniform(0, 2 * math.pi)
            dist = 120 + 420 * ease_in_out(q)
            x, y = W / 2 + dist * math.cos(a), CY + dist * math.sin(a)
            r = 18 * (1 - q) + 6
            d.ellipse([x - r, y - r, x + r, y + r], fill=mix((90, 50, 180), (200, 170, 255), q))
        else:
            rnd.uniform(0, 1)
    fx.en(t_lib, "boom", W / 2, CY, (150, 120, 255), burst=24, shake=12, texto="¡PUF!", vol=0.6)
    # inflamación: brillo rojizo pulsante
    if t > t_inf:
        a = clamp01((t - t_inf) / 0.5) * (0.5 + 0.5 * math.sin(t * 6))
        for k in range(3):
            r = 330 + k * 60
            d.ellipse([W / 2 - r, CY - r, W / 2 + r, CY + r], outline=mix((15, 10, 25), (255, 80, 70), a * (1 - k / 3)),
                      width=10)
    # estornudo
    fx.en(t_ale - 0.3, "achu", W / 2, CY - 330, (255, 220, 90), texto="¡ACHÚ!", shake=18, burst=18)
    sx, sy = respirar(t, 1.2)
    vac = 0.88 if t > t_lib else 1.0
    emp = 1.15 if 0 <= t - t_lib < 0.2 else 1.0
    temb = 6 * math.sin(t * 45) if t_det < t < t_lib else 0
    celula(fr, R.mast, t, W / 2 + dx + temb, CY + dy, est * vac * emp, sx, sy, rot)


def esc_eosinofilo(fr, d, R, fx, t, dur, esc):
    t_par = tpal(esc, "parásitos")
    t_gus = tpal(esc, "gusanos")
    t_gra = tpal(esc, "grandes")
    t_tox = tpal(esc, "tóxicas")
    t_ata = tpal(esc, "atacan")
    gx, gy = W / 2, CY + 230
    # gusano
    fx.en(t_par - 0.2, "boing", gx, gy - 160, (235, 150, 175), texto="¡PARÁSITO!", vol=0.7)
    t_muere = t_tox + 0.8
    q_g = ease_out_back((t - t_par + 0.4) / 0.6)
    if q_g > 0 and t < t_muere + 1.2:
        enc = 1.0 if t < t_muere else 1 - 0.75 * clamp01((t - t_muere) / 1.0)
        temb = 6 if t_ata < t < t_muere else 0
        gx_mov = gx + (1 - min(1, q_g)) * 900
        gusano(d, t, gx_mov, gy, 0.95 * min(1.2, q_g) * enc, 1.0 if t < t_muere else 1 - clamp01((t - t_muere) / 1.2),
               temb)
    fx.en(t_muere, "boom", gx, gy, (235, 150, 175), burst=26, shake=18, texto="¡FUERA!", flash=(255, 230, 220))
    # un macrófago intenta comérselo... ¡no cabe!
    fx.en(t_gra - 0.5, "whoosh", vol=0.6)
    fx.en(t_gra + 0.1, "boing", gx - 330, gy - 120, (255, 190, 90), texto="¡NO CABE!", vol=0.9)
    if t_gra - 0.6 < t < t_gra + 1.0:
        u = (t - t_gra + 0.6) / 0.6
        if u < 1:
            mx = lerp(-200, gx - 330, ease_in_out(u))
        else:
            mx = lerp(gx - 330, -250, ease_in_out((t - t_gra) / 1.0))
        sq = 1.0 if not (0 <= t - t_gra < 0.25) else 0.82
        celula(fr, R.mini["macro"], t, mx, gy - 40, 1.2, sq, 1 / sq)
    # eosinófilos que rodean y disparan
    pos = [(W / 2 - 300, CY - 250), (W / 2 + 300, CY - 250), (W / 2, CY - 380)]
    t_lleg = [0.2, 0.45, 0.7]
    for i, ((x, y), tl) in enumerate(zip(pos, t_lleg)):
        fx.en(tl, "whoosh", vol=0.5)
        fx.en(tl + 0.5, "ding" if i == 0 else "pop", x, y, esc["color"], burst=10, vol=0.7)
        q = ease_out_back((t - tl) / 0.5)
        if q <= 0:
            continue
        dxi = (1 - min(1, q)) * (-700 if x < W / 2 else 700)
        sx, sy = respirar(t + i, 1.3)
        disp = 1.12 if any(0 <= t - (t_ata + k * 0.18) < 0.12 for k in range(6)) else 1
        celula(fr, R.eos, t, x + dxi, y + 10 * math.sin(t * 4 + i), 0.8 * disp, sx, sy, 10 * math.sin(t * 3 + i))
        # gránulos tóxicos
        for k in range(6):
            tk = t_ata + k * 0.18 + i * 0.06
            if i == 0:
                fx.en(t_ata + k * 0.18, "pew", vol=0.6)
            p = clamp01((t - tk) / 0.45)
            if 0 < p < 1:
                tx_, ty_ = gx + (k - 2.5) * 80, gy
                px, py = lerp(x, tx_, p), lerp(y + 60, ty_, p)
                d.ellipse([px - 13, py - 13, px + 13, py + 13], fill=(255, 120, 60), outline=(255, 230, 200), width=3)
    if t_tox < t < t_muere:
        f = fuente(FONT_BOLD, 46)
        d.text((gx, gy + 150), "☠ TÓXICO ☠", font=f, fill=(170, 255, 120), anchor="mm", stroke_width=4,
               stroke_fill=(20, 40, 10))


def esc_resumen(fr, d, R, fx, t, dur, esc):
    filas = [("RÁPIDO", tpal(esc, "rápido"), True),
             ("SIEMPRE ACTÚA IGUAL", tpal(esc, "igual"), True),
             ("SIN MEMORIA", tpal(esc, "memoria."), False)]
    t_ada = tpal(esc, "adaptativo")
    fx.en(0.05, "whoosh")
    p = ease_out_back(t / 0.5)
    x0, x1 = 90, W - 90
    y0, y1 = CY - 420, CY + 120
    sal = ease_in_out((t - t_ada + 0.3) / 0.4)
    yo = -sal * 0
    if p > 0:
        cy = (y0 + y1) / 2 + yo
        h2 = (y1 - y0) / 2 * p
        panel(d, x0, cy - h2, x1, cy + h2, esc["color"])
        d.text((W / 2, y0 + 60 + yo), "SISTEMA INNATO", font=fuente(FONT_BOLD, 52), fill=esc["color"], anchor="mm")
        for i, (txt, ti, ok) in enumerate(filas):
            fx.en(ti, "ding" if ok else "buzz", vol=0.8)
            q = ease_out_back((t - ti + 0.1) / 0.35)
            if q <= 0:
                continue
            y = y0 + 170 + i * 120 + yo
            xo = (1 - min(1, q)) * 300
            d.ellipse([x0 + 50 + xo, y - 42, x0 + 134 + xo, y + 42], fill=(60, 200, 120) if ok else (255, 80, 100))
            if ok:
                palomita(d, x0 + 92 + xo, y, 1.0, (255, 255, 255), clamp01((t - ti) / 0.3))
            else:
                tache(d, x0 + 92 + xo, y, 1.0, (255, 255, 255))
            d.text((x0 + 170 + xo, y), txt, font=fuente(FONT_BOLD, 54), fill=(255, 255, 255), anchor="lm")
    # avance del próximo video
    fx.en(t_ada, "chime", W / 2, CY + 280, (200, 130, 255), burst=20, texto="¡PRÓXIMAMENTE!")
    q = ease_out_back((t - t_ada) / 0.5)
    if q > 0:
        y = CY + 250
        bw, bh = 820 * q, 190 * q
        d.rounded_rectangle([W / 2 - bw / 2, y - bh / 2, W / 2 + bw / 2, y + bh / 2], radius=int(40 * q),
                            fill=mix((15, 10, 30), (200, 130, 255), 0.35), outline=(200, 130, 255), width=6)
        d.text((W / 2, y - 40 * q), "PRÓXIMO VIDEO", font=fuente(FONT_BOLD, max(4, int(40 * q))),
               fill=(230, 220, 255), anchor="mm")
        d.text((W / 2, y + 30 * q), "SISTEMA ADAPTATIVO", font=fuente(FONT_BOLD, max(4, int(62 * q))),
               fill=(200, 130, 255), anchor="mm", stroke_width=4, stroke_fill=(20, 10, 30))
        for i, nm in enumerate(["th", "tc", "b", "mem"]):
            a = clamp01((t - t_ada - 0.3 - i * 0.12) / 0.4)
            if a > 0:
                fx.en(t_ada + 0.3 + i * 0.12, "pop", vol=0.4)
                celula(fr, R.mini[nm], t, W / 2 + (i - 1.5) * 200, y + 185 + 10 * math.sin(t * 4 + i),
                       0.6 * ease_out_back(a))


ANIM = {
    "intro": esc_intro, "division": esc_division, "barreras": esc_barreras, "neutrofilo": esc_neutrofilo,
    "macrofago": v2.esc_macrofago, "dendritica": v2.esc_dendritica, "nk": v2.esc_nk,
    "mastocito": esc_mastocito, "eosinofilo": esc_eosinofilo, "resumen": esc_resumen, "outro": v2.esc_outro,
}

if __name__ == "__main__":
    v2.ESCENAS = ESCENAS
    v2.ANIM = ANIM
    v2.TEMAS = TEMAS
    v2.NOMBRE = "reel_sistema_inmune_innato"
    v2.Recursos = Recursos
    v2.duraciones_habla = _dur_con_registro
    v2.PAD = 1.1  # más respiro al final de cada escena para los remates
    v2.main()

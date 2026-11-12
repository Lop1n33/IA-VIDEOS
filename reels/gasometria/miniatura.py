#!/usr/bin/env python3
"""Genera la miniatura (portada) del reel de gasometría con el mismo estilo del video.

Salidas:
    miniatura.png          1080x1920 (portada del Reel / TikTok)
    miniatura_feed.png     1080x1440 (recorte 3:4 que se ve en la cuadrícula del perfil)
"""
import importlib.util
import math
import os

from PIL import Image, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gas", os.path.join(AQUI, "generar.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
g = m.g
F, mix, pildora, tarjeta, palomita = g.F, g.mix, g.pildora, g.tarjeta, g.palomita
W, H = g.W, g.H
BG, PANEL, BLANCO, GRIS = g.BG, g.PANEL, g.BLANCO, g.GRIS
VERDE, CIAN, CORAL, AMBAR, VIOLETA = g.VERDE, g.CIAN, g.CORAL, g.AMBAR, g.VIOLETA


def resplandor(img, box, col, radio=60, fuerza=0.55):
    capa = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle(box, radius=40, fill=col)
    capa = capa.filter(ImageFilter.GaussianBlur(radio))
    return Image.blend(img, Image.composite(capa, img, capa.convert("L")), fuerza)


def main():
    img = g.fondo()
    # zona segura del feed 3:4 (1080x1440) centrada: y de 240 a 1680
    img = resplandor(img, [120, 760, W - 120, 1260], (60, 20, 30), 120, 0.6)
    d = ImageDraw.Draw(img)

    # etiqueta superior
    pildora(d, W / 2, 330, "GASOMETRÍA ARTERIAL", CIAN, F(g.F_MONO, 34))

    # titular
    d.text((W / 2, 470), "Interprétala", font=F(g.F_BLACK, 118), fill=BLANCO, anchor="mm")
    d.text((W / 2, 600), "en 5 pasos", font=F(g.F_BLACK, 118), fill=VERDE, anchor="mm")

    # reporte con valores alterados
    x0, x1, y0 = 150, W - 150, 720
    tarjeta(d, [x0, y0, x1, y0 + 420], fill=(14, 22, 38), borde=CORAL, w=3)
    d.text((x0 + 40, y0 + 52), "RESULTADO", font=F(g.F_MONO, 30), fill=GRIS, anchor="lm")
    d.ellipse([x1 - 64, y0 + 40, x1 - 40, y0 + 64], fill=CORAL)
    filas = [("pH", "7.25", CORAL), ("PaCO₂", "30", AMBAR), ("HCO₃⁻", "14", CIAN), ("Anión gap", "26", VIOLETA)]
    for i, (nom, val, col) in enumerate(filas):
        y = y0 + 130 + i * 76
        d.text((x0 + 44, y), nom, font=F(g.F_BOLD, 46), fill=BLANCO, anchor="lm")
        d.text((x1 - 44, y), val, font=F(g.F_BLACK, 60), fill=col, anchor="rm")
        if i < 3:
            d.line([(x0 + 40, y + 38), (x1 - 40, y + 38)], fill=(36, 52, 76), width=2)

    # pregunta gancho
    d.text((W / 2, 1225), "¿Qué trastorno es?", font=F(g.F_BLACK, 76), fill=BLANCO, anchor="mm")

    # los 5 pasos como chips
    pasos = [("pH", CORAL), ("Origen", CIAN), ("Compensación", AMBAR), ("Anión gap", VIOLETA), ("Oxigenación", VERDE)]
    f = F(g.F_MONO, 30)
    filas_chips = [pasos[:3], pasos[3:]]
    for r, fila in enumerate(filas_chips):
        anchos = [d.textlength(f"{i} {n}", font=f) + 44 for i, (n, _) in enumerate(fila)]
        sep = 18
        x = W / 2 - (sum(anchos) + sep * (len(fila) - 1)) / 2
        for k, ((n, col), a) in enumerate(zip(fila, anchos)):
            num = k + 1 + r * 3
            pildora(d, x + a / 2, 1340 + r * 84, f"{num} {n}", col, f)
            x += a + sep

    # sello de tiempo
    box = pildora(d, W / 2 + 30, 1555, "MENOS DE 3 MINUTOS", VERDE, F(g.F_BLACK, 46), fill=mix(BG, VERDE, 0.14))
    cx, cy = box[0] - 52, 1555
    d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], outline=VERDE, width=5)
    d.line([(cx, cy), (cx + 16, cy - 18)], fill=VERDE, width=5)
    d.rectangle([cx - 7, cy - 46, cx + 7, cy - 35], fill=VERDE)

    img.save(os.path.join(AQUI, "miniatura.png"), optimize=True)
    img.crop((0, 240, W, 1680)).save(os.path.join(AQUI, "miniatura_feed.png"), optimize=True)
    print("Listo: miniatura.png y miniatura_feed.png")


if __name__ == "__main__":
    main()

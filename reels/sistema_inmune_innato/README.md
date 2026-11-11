# Reel: El sistema inmune innato — Biología en Minutos

Video vertical 1080x1920, de unos 1:43, **sin voz**: lleva subtítulos estilo karaoke, onomatopeyas, efectos caricaturescos y música suave, listo para agregarle la narración con ElevenLabs. Es la continuación del reel `sistema_inmune_v2` y usa el mismo motor de animación.

| Archivo | Qué es |
|---|---|
| `reel_sistema_inmune_innato.mp4` | Video con efectos y música |
| `reel_sistema_inmune_innato_sin_musica.mp4` | Solo con efectos |
| `guion_elevenlabs.txt` | Guion por escena con el segundo en que empieza cada una |
| `subtitulos.srt` | Subtítulos por frase |

## Escenas
1. Presentación, repaso del video anterior y la pregunta "¿sabías que se divide en dos?" (con "?", "2" y "¡EN DOS!")
2. Innato vs. adaptativo: dos paneles con "VS"; el adaptativo sale de cuadro y cae el sello "HOY"
3. Primera línea de defensa: escudo, cronómetro ("¡RÁPIDO!") y muro de piel y mucosas con bacterias que rebotan ("¡TOING!")
4. Neutrófilos: "¡ÑAM!", "¡GLUP!" y redes que atrapan bacterias ("¡ATRAPADAS!")
5. Macrófagos: comen, lanzan la alarma de citocinas y llegan refuerzos
6. Células dendríticas: capturan el antígeno y se lo presentan al linfocito T
7. Células NK: escanean una célula sana y una sospechosa, y lanzan un rayo ("¡POW!")
8. Mastocitos: llega el polen, sueltan histamina ("¡PUF!"), hay inflamación y "¡ACHÚ!"
9. Eosinófilos: un gusano parásito, un macrófago al que "¡NO CABE!", disparos tóxicos y "¡FUERA!"
10. Resumen con palomitas y tache, más el avance del próximo video (sistema adaptativo)
11. Cierre: caja de comentarios y botón de seguir

Las animaciones clave se sincronizan con la palabra del guion en la que se mencionan.

## Agregar la voz
Genera los 11 audios en ElevenLabs con el texto de `guion_elevenlabs.txt` y colócalos en tu editor en los tiempos indicados.

También puedes guardarlos como `escena_01.mp3` … `escena_11.mp3` y ejecutar lo siguiente, que vuelve a crear el video sincronizado con tu voz:
```bash
python generar.py --voz-dir carpeta_audios --out .
```

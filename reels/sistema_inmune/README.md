# Reel: Las células del sistema inmune

Video vertical 1080x1920 (formato Reels/TikTok/Shorts), unos 75 segundos, con voz en español, subtítulos y música ambiental.

**Video final:** `reel_sistema_inmune.mp4`

## Contenido
1. Introducción: tu ejército interno
2. Neutrófilos: primera línea de defensa
3. Macrófagos: los grandes comelones
4. Células dendríticas: las mensajeras
5. Linfocitos T CD4: los generales
6. Linfocitos T CD8: asesinos de precisión
7. Linfocitos B: fábricas de anticuerpos
8. Células NK: asesinas naturales
9. Células de memoria: por qué funcionan las vacunas
10. Cierre y llamada a la acción

## Cómo regenerarlo
```bash
pip install kokoro-onnx soundfile pillow numpy   # además requiere ffmpeg
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
python generar.py --modelo kokoro-v1.0.int8.onnx --voces voices-v1.0.bin --salida reel_sistema_inmune.mp4
```
Opciones: `--voz ef_dora` (voz femenina), `em_alex` (voz masculina, la predeterminada) o `em_santa`; `--velocidad 1.08`.
El guion se edita en la lista `ESCENAS` de `generar.py`.

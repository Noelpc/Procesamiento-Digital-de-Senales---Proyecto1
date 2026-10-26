# Esteganografía por enmascaramiento con eco

Proyecto 1 de Procesamiento Digital de Señales (TEC). Prototipo en Python (`proto/`), implementación final en C++17 (`src/`), artículo IEEE en `article/`.

## Requisitos (GNU/Linux)
- Aplicación: `g++` (C++17) y `make`.
- Pruebas, experimentos y figuras: `python3` con `numpy`, `scipy`, `pandas`, `matplotlib` y `pesq` (`pip install pesq`); `ffmpeg`/`ffprobe` y `git` para obtener y validar audio.
- Artículo: `pdflatex` con `IEEEtran` (incluido en `article/`), `babel-spanish` (Debian/Ubuntu: `texlive-lang-spanish`), `tikz`, `booktabs`.

## Construcción
    make          # genera ./eco
    make test     # prueba de ida y vuelta rápida (audio sintético)
    make sanity   # verificación de los requisitos del proyecto (necesita audio/*.wav)
    make article  # compila article/articulo.pdf

## Uso
Codificar (se activa con al menos un metadato):

    ./eco original.wav codificado.wav --titulo "T" --artista "A" --autor "X" --album "Al" --anio 1975 --invitado "G" --productor "P"

Decodificar (sin metadatos): `./eco codificado.wav`

Enmascaramiento (deben coincidir al codificar y decodificar): `--d0 US --d1 US` (retardos en µs, defecto 1000 y 2000),
`--a0 PCT --a1 PCT` (amplitud del eco en %, defecto 30 y 30), `--canal izq|der` (defecto izq).
Los metadatos reconocidos salen por stdout con su categoría; los desconocidos, por stderr con una advertencia. Un parámetro desconocido aborta.
Si un metadato se repite, vale el último. Formato exigido: WAV PCM, 44.1 kHz, 16 bit, estéreo.

## Archivos de prueba
Tres pistas con licencia abierta (ver `audio/*_licencia.txt`): Brahms (clásica, dominio público), K. MacLeod "Vibe Ace" (jazz, CC BY), K. Hobbs "Let's Go Fishin'" (folk, CC BY).
Atribución (CC BY 3.0): "Vibe Ace" de Kevin MacLeod y "Let's Go Fishin'" de Karissa Hobbs, ambas de la Free Music Archive; la interpretación de Brahms es de US Army Strings (Musopen, dominio público).
Se obtienen con `audio/obtener_audio.sh` (descarga de https://github.com/librosa/data y conversión con ffmpeg).

## Ejemplos ya codificados
`audio/codificados/` contiene una versión codificada de cada pista (canal izquierdo, parámetros por defecto). Se decodifican con `./eco audio/codificados/NOMBRE_codificado.wav`:
- `clasica_brahms_codificado.wav`: título, artista, autor.
- `jazz_vibeace_codificado.wav`: título, artista, álbum.
- `folk_fishin_codificado.wav`: título, artista, autor, álbum, invitado, productor.
Los originales (sin codificar) están en `audio/`. Las pistas cortas llevan pocos metadatos porque el mensaje necesita varias copias dentro del archivo.

## Experimentos y figuras del artículo
    cd proto
    python3 experiments.py --dir ../audio --out results/real   # ~1 min; sin --dir usa audio sintético (proto/genres.py)
    python3 figures.py results/real                            # figuras en ../article/figs
Resultados guardados: `proto/results/real` (música real, usados en el artículo) y `proto/results/synth` (sintético).

## Diseño
- Ventana `L = 8·t_max` muestras (704 con los defectos). Con `L = t_max` la recuperación por ventana es ~56 %.
- Codificador: convolución de cada ventana con `h0` o `h1` y combinación por solapamiento y suma (R36).
- Protocolo: sincronía 0x7E, tipo, longitud, texto y CRC-8; protegido con Hamming(7,4) (opcional O2). El flujo se repite cíclicamente en todo el archivo.
- Decodificador: `R_cc = F⁻¹{(ln|F{v}|)²}` promediada con ventana rectangular y Hann; puntajes `z0`, `z1` normalizados con mediana/MAD; suma suave de copias buscando el periodo (múltiplo de 7) que da más registros válidos. Ventanas sin eco no votan (R47).

## Resultados resumidos (defectos, 3 pistas reales)
Recuperación por ventana 98.8 / 97.7 / 96.5 % (clásica / folk / jazz); PESQ 4.00 / 3.61 / 2.67; tasa de transferencia 62.6 b/s.
El mensaje completo se recupera con ≥ 30 s de audio (3 metadatos); los 7 metadatos requieren ~2 min.

## Limitaciones conocidas
- R32 (indistinguible): no está garantizado; en jazz el PESQ es 2.67 y no hubo pruebas auditivas. Bajar `--a0/--a1` mejora la calidad y reduce la recuperación.
- Solo 3 pistas; el audio con compresión con pérdida no se probó.
- R5: el historial de Git debe reflejar el desarrollo; se construye con commits propios por etapa (ver instrucciones de entrega).

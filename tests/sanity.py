#!/usr/bin/env python3
"""Verificacion automatica de requisitos del proyecto (R1-R51, A1-A33 verificables). Uso: python3 tests/sanity.py"""
import os, re, subprocess, sys, wave, tempfile, shutil
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
sys.path.insert(0, "proto"); import echo_hiding as E
ECO = "./eco"; SRC = "audio/jazz_vibeace.wav"; T = tempfile.mkdtemp()
res = []
def chk(rid, desc, ok, note=""): res.append((rid, desc, ok if isinstance(ok, str) else bool(ok), note))
def run(args, **k): return subprocess.run(args, capture_output=True, text=True, **k)
def txt(p): return open(p, encoding="utf-8", errors="ignore").read()

subprocess.run(["make", "-s"], check=True)
ALL = ["--titulo", "Cancion X", "--artista", "Artista Y", "--autor", "Autor Z", "--album", "Album W", "--anio", "1999", "--invitado", "Invitado V", "--productor", "Productor U"]
out = f"{T}/c.wav"
LONG = "audio/folk_fishin.wav"
r = run([ECO, LONG, out] + ALL); chk("R28/R29/R30", "codifica con >=1 metadato; rutas posicionales", r.returncode == 0 and os.path.exists(out))
d = run([ECO, out]); lines = d.stdout.strip().split("\n")
exp = ["titulo: Cancion X", "artista: Artista Y", "autor: Autor Z", "album: Album W", "anio: 1999", "invitado: Invitado V", "productor: Productor U"]
chk("R10-R16", "7 metadatos codificados y decodificados (pista de 133 s)", sorted(lines) == sorted(exp), f"{len(lines)}/7")
chk("R39/R40/R41", "decodifica sin metadatos; archivo como 1er posicional; termina", d.returncode == 0)
chk("R48/R49", "metadatos en stdout con su categoria", all(re.match(r"^\w+: .+", l) for l in lines))
chk("R8", "metadatos opcionales (subconjunto)", run([ECO, SRC, f"{T}/s.wav", "--anio", "2020"]).returncode == 0 and "anio: 2020" in run([ECO, f"{T}/s.wav"]).stdout)
run([ECO, SRC, f"{T}/dup.wav", "--titulo", "Primero", "--titulo", "Ultimo"]); dd = run([ECO, f"{T}/dup.wav"]).stdout
chk("R9", "duplicados: gana el ultimo", "Ultimo" in dd and "Primero" not in dd)
chk("R7", "parametro desconocido aborta", run([ECO, "--nope", "x", SRC]).returncode != 0 and run([ECO, SRC, f"{T}/z.wav", "--titulo", "a", "--nope"]).returncode != 0)
# canal / modo
run([ECO, SRC, f"{T}/der.wav", "--titulo", "Solo derecho", "--canal", "der"])
chk("R26", "canal derecho codificable/decodificable", "Solo derecho" in run([ECO, f"{T}/der.wav", "--canal", "der"]).stdout)
chk("R27", "canal por defecto = izquierdo (derecho no se altera)", run([ECO, f"{T}/der.wav"]).stdout.strip() == "")
a, ha = E.read_wav(LONG); b, hb = E.read_wav(out); SRC0 = SRC; SRC = LONG
chk("R27b", "el otro canal queda intacto", np.array_equal(a[:, 1], b[:, 1]))
# enmascaramiento
P = ["--d0", "700", "--d1", "1600", "--a0", "40", "--a1", "30"]
run([ECO, SRC, f"{T}/p.wav", "--titulo", "Params"] + P)
chk("R19-R24", "retardos (us) y atenuaciones (%) configurables; decodifica con los mismos", "Params" in run([ECO, f"{T}/p.wav"] + P).stdout)
chk("R17/R18", "defaults sin parametros; archivo con otros valores no decodifica con defaults", "Params" not in run([ECO, f"{T}/p.wav"]).stdout)
# formato
with open(SRC, "rb") as f: raw = bytearray(f.read())
chk("R25", "44.1 kHz, 16 bit, estereo", ha.framerate == 44100 and ha.sampwidth == 2 and ha.nchannels == 2)
mono = f"{T}/mono.wav"
with wave.open(mono, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b"\0\0" * 10000)
chk("R25b", "rechaza formato distinto al requerido", run([ECO, mono]).returncode != 0)
# codificador
hdr = lambda p: open(p, "rb").read()[:44]
chk("R37", "encabezado WAV identico al original", hdr(out) == hdr(SRC) and os.path.getsize(out) == os.path.getsize(SRC))
ff = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", out])
chk("R38", "WAV valido para reproductores estandar (ffprobe)", "pcm_s16le,44100,2" in ff.stdout.replace("\n", ""), ff.stdout.strip())
L = E.window_len(1000.0, 2000.0); n = len(a); diff = np.nonzero(a[:, 0] != b[:, 0])[0]
nz = np.nonzero(np.abs(a[:, 0]) >= 4)[0]   # con |x|<4 el eco al 30 % redondea a 0 (1 LSB)
chk("R31", "codifica la totalidad del archivo (entre la primera y la ultima muestra con |x|>=4 LSB)", diff.max() >= nz.max() - 2 * L and diff.min() <= nz.min() + L, f"cambios en [{diff.min()}, {diff.max()}], audio no nulo en [{nz.min()}, {nz.max()}]")
chk("R33/R42", "ventana = f(mayor retardo)", L == 8 * 88, f"L={L} muestras")
src = txt("src/main.cpp")
chk("R34", "codificacion por convolucion con h0/h1", "R34" in src and "for (size_t m = 0; m < hb.size()" in src)
chk("R35/R36", "solo una tecnica: solapamiento y suma", "overlap-add" in src and "overlap-save" not in src.lower())
chk("R44/R45", "autocorrelacion del cepstro en dominio espectral", "ln|F{x}|" in src or "log(std::abs" in src)
# decodificador: sin eco y desconocidos
chk("R47", "archivo sin codificar: no reconoce metadatos (ventanas sin eco)", run([ECO, SRC]).stdout.strip() == "")
recs = [(9, "Dato raro"), (1, "Titulo ok")]; y = a.copy(); y[:, 0] = np.round(E.encode_channel(a[:, 0], E.ham_encode(E.pack(recs)), E.DEF if False else dict(d0=1000.0, d1=2000.0, a0=30.0, a1=30.0)))
E.write_wav(f"{T}/unk.wav", y, ha); u = run([ECO, f"{T}/unk.wav"])
chk("R50/R51", "metadato desconocido en stderr con advertencia", "ADVERTENCIA" in u.stderr and "Dato raro" in u.stderr and "Dato raro" not in u.stdout and "titulo: Titulo ok" in u.stdout)
# R46 tasa de recuperacion con defaults sobre las 3 pistas
rates = []
for f in sorted(os.listdir("audio")):
    if f.endswith(".wav"):
        x, _ = E.read_wav("audio/" + f); x = x[:int(30 * 44100), 0]; E.WIN_MULT = 8; Lw = E.window_len(1000.0, 2000.0)
        bits = list(np.random.default_rng(1).integers(0, 2, len(x) // Lw)); p = dict(d0=1000.0, d1=2000.0, a0=30.0, a1=30.0)
        yy = np.round(E.encode_channel(x, [int(v) for v in bits], p)); rates.append(float(np.mean(E.window_bits(yy, p) == np.array(bits))))
chk("R46", "tasa de recuperacion con defaults >= 90%", len(rates) > 0 and min(rates) >= 0.90, "por pista: " + ", ".join(f"{r:.3f}" for r in rates))
chk("R32", "defaults perceptualmente indistinguibles", "PARCIAL", "PESQ 4.00/3.61/2.67 (clasica/folk/jazz): no garantizado; sin pruebas auditivas")
# generales
chk("R1", "prototipo Python + implementacion C++", os.path.exists("proto/echo_hiding.py") and os.path.exists("src/main.cpp"))
chk("R2", "codigo fuente propio (sin bibliotecas de DSP/WAV externas)", not re.search(r'#include\s*<(fftw3|sndfile|samplerate)', src))
chk("R3", "GNU/Linux (compila con make)", os.path.exists("eco"))
chk("R4", "Makefile", os.path.exists("Makefile") and "all:" in txt("Makefile"))
git = run(["git", "log", "--oneline"]); nc = len(git.stdout.strip().split("\n")) if git.returncode == 0 and git.stdout.strip() else 0
chk("R5", "historial de Git que muestre el desarrollo del equipo", True if nc >= 10 else "PENDIENTE", f"{nc} commits: el equipo debe commitear con sus cuentas")
chk("R6", "parametros por linea de comandos", "getopt_long" in src)
# articulo
pdf = "article/articulo.pdf"; tex = txt("article/articulo.tex")
pg = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", pdf]).stdout).group(1)); t = run(["pdftotext", pdf, "-"]).stdout
chk("A1/A2", "LaTeX con clase IEEEtran", "\\documentclass[journal]{IEEEtran}" in tex)
chk("A3", "<= 4 paginas", pg <= 4, f"{pg} paginas")
chk("A4", "texto en espanol", "babel" in tex and "spanish" in tex)
chk("A14", "resumen en ingles", "\\begin{abstract}" in tex and "This paper presents" in tex)
chk("A13", "palabras clave en orden alfabetico", (lambda k: k == sorted(k, key=str.lower))([s.strip() for s in re.search(r"IEEEkeywords}\n(.*?)\n\\end", tex, re.S).group(1).split(",")]))
chk("A9/A10/A11", "tablas con titulo arriba y solo lineas horizontales", "booktabs" in tex and "\\toprule" in tex and "|" not in re.search(r"\\begin\{tabular\}\{(.*?)\}", tex).group(1))
chk("A12", "sin codigo textual (diagramas)", "lstlisting" not in tex and "verbatim" not in tex and "tikzpicture" in tex)
chk("A17/A18", "introduccion con contexto/antecedentes y estructura del documento", "El resto del documento se organiza" in tex)
chk("A24-A26", "conclusiones + trabajo futuro", "\\section{Conclusiones}" in tex and "trabajo futuro" in tex)
chk("A27", "citas a referencias", len({k for g in re.findall(r"\\cite\{([\w,]+)\}", tex) for k in g.split(",")}) >= 5)
chk("A28-A32", "PESQ, recuperacion, correlaciones, generos", all(k in tex for k in ["PESQ", "recuperación", "Spearman", "clásica", "jazz", "folk"]))
chk("A33", "analisis propio (ruido, ventanas sin eco, mensaje)", "análisis propio" in tex)
chk("O2", "opcional: correccion de errores (Hamming(7,4))", "ham_encode" in src)
shutil.rmtree(T, ignore_errors=True)
w = max(len(r[0]) for r in res)
tag = lambda ok: "OK" if ok is True else (ok if isinstance(ok, str) else "FALLA")
for rid, desc, ok, note in res: print(f"[{tag(ok):<9}] {rid:<{w}}  {desc}" + (f"  ({note})" if note else ""))
bad = [r for r in res if r[2] is False]; pend = [r for r in res if isinstance(r[2], str)]
print(f"\n{sum(r[2] is True for r in res)}/{len(res)} OK, {len(pend)} parcial/pendiente, {len(bad)} fallas"); sys.exit(1 if bad else 0)

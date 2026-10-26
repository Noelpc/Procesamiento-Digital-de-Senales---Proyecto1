#!/usr/bin/env python3
"""Prototipo: esteganografia por enmascaramiento con eco (Gruhl & Bender)."""
import argparse, sys, wave
import numpy as np

FS = 44100
SYNC = 0x7E
TYPES = {1: "titulo", 2: "artista", 3: "autor", 4: "album",
         5: "anio", 6: "invitado", 7: "productor"}
DEF = dict(d0=1000.0, d1=2000.0, a0=30.0, a1=30.0)  # us, %


# ---------- WAV ----------
def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 2, "se requiere 16 bit estereo"
        hdr = w.getparams()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2)
    return x.astype(np.float64), hdr

def write_wav(path, x, hdr):
    y = np.clip(np.round(x), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setparams(hdr)
        w.writeframes(y.tobytes())


# ---------- parametros ----------
def samples(d_us):
    return int(round(d_us * 1e-6 * FS))

def impulse_response(d_us, a_pct):
    t = samples(d_us)
    h = np.zeros(t + 1); h[0] = 1.0; h[t] = a_pct / 100.0
    return h

WIN_MULT = 8   # L = WIN_MULT * t_max; con L = t_max+1 el eco casi no cae en su ventana (ver experimentos)

def window_len(d0, d1):
    return WIN_MULT * max(samples(d0), samples(d1))      # R33 / R42


# ---------- protocolo de metadatos ----------
def crc8(data, poly=0x07):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c

def pack(records):
    """records: lista de (tipo:int, texto:str) -> lista de bits."""
    out = bytearray()
    for typ, txt in records:
        p = txt.encode("utf-8")[:255]
        body = bytes([typ, len(p)]) + p
        out += bytes([SYNC]) + body + bytes([crc8(body)])
    return [(b >> (7 - i)) & 1 for b in out for i in range(8)]

def parse(bits):
    """bits: lista de 0/1 -> lista de (estado, tipo, texto). estado: ok|desconocido|corrupto"""
    res, i, n = [], 0, len(bits)
    def byte(k):
        return sum(bits[k + j] << (7 - j) for j in range(8))
    while i + 8 <= n:
        if byte(i) != SYNC:
            i += 1; continue
        if i + 32 > n: break
        typ, ln = byte(i + 8), byte(i + 16)
        if ln == 0:                                  # un registro vacio no lleva informacion (falso positivo de CRC)
            i += 1; continue
        end = i + 24 + 8 * ln + 8
        if end > n:
            i += 1; continue
        body = bytes([typ, ln] + [byte(i + 24 + 8 * k) for k in range(ln)])
        if crc8(body) != byte(end - 8):
            i += 1; continue
        txt = body[2:].decode("utf-8", errors="replace")
        res.append(("ok" if typ in TYPES else "desconocido", typ, txt))
        i = end
    return res


# ---------- Hamming(7,4) (O2) ----------
_G = np.array([[1,1,0,1],[1,0,1,1],[1,0,0,0],[0,1,1,1],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
_H = np.array([[1,0,1,0,1,0,1],[0,1,1,0,0,1,1],[0,0,0,1,1,1,1]])

def ham_encode(bits):
    bits = list(bits) + [0] * (-len(bits) % 4)
    d = np.array(bits).reshape(-1, 4)
    return list((d @ _G.T % 2).reshape(-1))

def ham_decode(bits):
    n = len(bits) // 7 * 7
    c = np.array(bits[:n]).reshape(-1, 7)
    syn = (c @ _H.T % 2) @ np.array([1, 2, 4])
    for i in np.nonzero(syn)[0]:
        c[i, syn[i] - 1] ^= 1
    return list(c[:, [2, 4, 5, 6]].reshape(-1))


# ---------- codificador ----------
def encode_channel(x, bits, p):
    """Codifica el flujo `bits` de forma ciclica en TODAS las ventanas (R31); convolucion + overlap-add (R34/R36)."""
    L = window_len(p["d0"], p["d1"])
    h = {0: impulse_response(p["d0"], p["a0"]), 1: impulse_response(p["d1"], p["a1"])}
    N = max(len(h[0]), len(h[1]))
    nwin = (len(x) + L - 1) // L
    y = np.zeros(nwin * L + N)
    for k in range(nwin):
        v = x[k * L:(k + 1) * L]
        seg = np.convolve(v, h[bits[k % len(bits)]])     # M+N-1
        y[k * L:k * L + len(seg)] += seg                 # overlap-add
    return y[:len(x)]

def capacity_bits(n, p):
    return n // window_len(p["d0"], p["d1"])


# ---------- decodificador ----------
def acepstrum(v, nfft):
    """R_cc = F^-1{(ln|F{v}|)^2}, promediando ventana rectangular y Hann (R45: evaluado en el dominio espectral)."""
    acc = 0
    for w in (np.ones(len(v)), np.hanning(len(v))):
        lm = np.log(np.abs(np.fft.rfft(v * w, nfft)) + 1e-9)
        acc = acc + lm * lm
    return np.fft.irfft(acc / 2, nfft)


def scores(v, p, nfft):
    """Puntajes z0, z1: pico de R_cc en t0/t1 normalizado con mediana/MAD de los retardos vecinos."""
    t0, t1 = samples(p["d0"]), samples(p["d1"])
    r = acepstrum(v, nfft); idx = np.arange(3, 2 * max(t0, t1))
    m = (np.abs(idx - t0) > 3) & (np.abs(idx - t1) > 3)
    ref = r[idx][m]; med = np.median(ref); mad = np.median(np.abs(ref - med)) + 1e-12
    return (r[t0] - med) / mad, (r[t1] - med) / mad

def window_soft(x, p, nfft=None):
    """Por ventana: d = z1 - z0 (decision suave) y conf = max(z0, z1) (confianza de que hay eco)."""
    L = window_len(p["d0"], p["d1"])
    nfft = nfft or 1 << int(np.ceil(np.log2(2 * L)))
    z = np.array([scores(x[k * L:(k + 1) * L], p, nfft) for k in range(len(x) // L)])
    return z[:, 1] - z[:, 0], z.max(axis=1)

def window_bits(x, p):
    d, _ = window_soft(x, p); return (d > 0).astype(int)

def combine(d, conf, P, thr=2.0):
    """Suma suave de las copias del flujo de periodo P; ventanas sin eco (conf < thr, R47) no votan."""
    dd = np.where(conf >= thr, np.clip(d, -3, 3), 0.0); s = np.zeros(P)
    np.add.at(s, np.arange(len(dd)) % P, dd)
    return [int(v > 0) for v in s]

def decode_channel(x, p, thr=2.0, maxP=2100):
    """El periodo P (multiplo de 7, bloques Hamming) se busca: gana el menor P con mas registros validos (CRC)."""
    d, conf = window_soft(x, p); best = []
    for P in range(7, min(maxP, len(d)) + 1, 7):
        recs = list(dict.fromkeys(parse(ham_decode(combine(d, conf, P, thr)))))   # sin duplicados
        if len(recs) > len(best): best = recs
    return best


# ---------- CLI ----------
META = {"titulo": 1, "artista": 2, "autor": 3, "album": 4, "anio": 5, "invitado": 6, "productor": 7}

def main():
    ap = argparse.ArgumentParser(prog="echo_hiding")
    ap.add_argument("files", nargs="+")
    for k in META: ap.add_argument("--" + k)
    ap.add_argument("--d0", type=float, default=DEF["d0"]); ap.add_argument("--d1", type=float, default=DEF["d1"])
    ap.add_argument("--a0", type=float, default=DEF["a0"]); ap.add_argument("--a1", type=float, default=DEF["a1"])
    ap.add_argument("--canal", choices=["izq", "der"], default="izq")
    a = ap.parse_args()
    p = dict(d0=a.d0, d1=a.d1, a0=a.a0, a1=a.a1); ch = 0 if a.canal == "izq" else 1
    recs = [(META[k], getattr(a, k)) for k in META if getattr(a, k) is not None]
    if recs:                                              # R28
        src, dst = a.files
        x, hdr = read_wav(src)
        bits = ham_encode(pack(recs))
        if len(bits) > capacity_bits(len(x), p):
            sys.exit("error: audio demasiado corto para los metadatos")
        x[:, ch] = encode_channel(x[:, ch], bits, p)
        write_wav(dst, x, hdr)
    else:                                                 # R39
        x, _ = read_wav(a.files[0])
        for st, typ, txt in decode_channel(x[:, ch], p):
            if st == "ok": print(f"{TYPES[typ]}: {txt}")
            else: print(f"ADVERTENCIA: metadato desconocido (tipo {typ}): {txt}", file=sys.stderr)

if __name__ == "__main__":
    main()

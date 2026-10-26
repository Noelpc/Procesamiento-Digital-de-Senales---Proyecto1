#!/usr/bin/env python3
"""Experimentos A28-A33 (diseno final). Uso: python3 experiments.py [--dir WAVS] [--dur 30]"""
import argparse, csv, itertools, time
import numpy as np
from scipy.signal import resample_poly
import pesq as pesqlib
import echo_hiding as E
import genres

BASE = dict(d0=1000.0, d1=2000.0, a0=30.0, a1=30.0)

def pesq_wb(x, y, secs=12):
    f = lambda s: np.ascontiguousarray(resample_poly(s[:int(secs * E.FS)], 160, 441) / 32768, dtype=np.float32)
    return pesqlib.pesq(16000, f(x), f(y), "wb")

def window_cfg(x, p, mult, rng, snr=None):
    """Recuperacion por ventana (R46) y PESQ con bits aleatorios en todas las ventanas."""
    E.WIN_MULT = mult; L = E.window_len(p["d0"], p["d1"]); nw = len(x) // L
    bits = [int(b) for b in rng.integers(0, 2, nw)]
    y = E.encode_channel(x, bits, p); q = pesq_wb(x, y); z = np.round(y)
    if snr is not None:
        z = z + rng.standard_normal(len(z)) * np.sqrt(np.mean(x ** 2) / 10 ** (snr / 10))
    rec = float(np.mean(E.window_bits(z, p) == np.array(bits)))
    return dict(L=L, rate=E.FS / L, rec=rec, pesq=q)

RECS = [(1, "Titulo de prueba"), (2, "Artista"), (5, "2026")]
def msg_ok(x, p, snr=None, rng=None):
    y = np.round(E.encode_channel(x, E.ham_encode(E.pack(RECS)), p))
    if snr is not None:
        y = y + rng.standard_normal(len(y)) * np.sqrt(np.mean(x ** 2) / 10 ** (snr / 10))
    return [r[1:] for r in E.decode_channel(y, p)] == RECS

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dir"); ap.add_argument("--dur", type=float, default=30); ap.add_argument("--out", default="results")
    a = ap.parse_args(); import os; os.makedirs(a.out, exist_ok=True); aud = genres.load(a.dur, directory=a.dir); full = genres.load(1e9, directory=a.dir) if a.dir else None; rng = np.random.default_rng(0); t0 = time.time()
    w = lambda name, hdr: csv.writer(open(f"{a.out}/{name}.csv", "w", newline="")).writerow(hdr.split(","))
    def out(name, hdr):
        f = open(f"{a.out}/{name}.csv", "w", newline=""); c = csv.writer(f); c.writerow(hdr.split(",")); return c, f
    # E1: amplitud x ventana
    c, f = out("e1", "genre,a,mult,L,rate_bps,rec,pesq")
    for g, x in aud.items():
        for amp, mult in itertools.product((10, 20, 30, 50), (2, 4, 8, 16)):
            r = window_cfg(x, dict(BASE, a0=amp, a1=amp), mult, rng)
            c.writerow([g, amp, mult, r["L"], round(r["rate"], 2), round(r["rec"], 4), round(r["pesq"], 3)])
    f.close(); print("E1", round(time.time() - t0), flush=True)
    # E2: pares de retardos
    c, f = out("e2", "genre,d0,d1,rate_bps,rec,pesq")
    for g, x in aud.items():
        for d0, d1 in ((500, 1000), (1000, 1500), (1000, 2000), (2000, 3000), (2000, 4000)):
            r = window_cfg(x, dict(BASE, d0=d0, d1=d1), 8, rng)
            c.writerow([g, d0, d1, round(r["rate"], 2), round(r["rec"], 4), round(r["pesq"], 3)])
    f.close(); print("E2", round(time.time() - t0), flush=True)
    # E3: ruido aditivo (ventana y mensaje)
    c, f = out("e3", "genre,snr_db,rec,msg_ok")
    for g, x in aud.items():
        for snr in (None, 50, 40, 30, 20):
            r = window_cfg(x, BASE, 8, rng, snr=snr)
            xx = full[g] if a.dir else np.tile(x, 3)[:int(90 * E.FS)]
            c.writerow([g, "inf" if snr is None else snr, round(r["rec"], 4), int(msg_ok(xx, BASE, snr, rng))])
    f.close(); print("E3", round(time.time() - t0), flush=True)
    # E4: ventanas sin eco (R47): primera mitad codificada, segunda sin eco
    E.WIN_MULT = 8; L = E.window_len(1000, 2000)
    c, f = out("e4", "genre,miss_coded,false_coded")
    for g, x in aud.items():
        n = len(x) // L // 2; bits = [int(b) for b in rng.integers(0, 2, n)]
        y = np.round(E.encode_channel(x[:2 * n * L], bits, BASE)); y[n * L:] = x[n * L:2 * n * L]
        d, cf = E.window_soft(y, BASE)
        c.writerow([g, round(1 - np.mean(cf[:n] >= 2.0), 4), round(np.mean(cf[n:2 * n] >= 2.0), 4)])
    f.close(); print("E4", round(time.time() - t0), flush=True)
    # E5: exito del mensaje vs duracion
    c, f = out("e5", "genre,dur_s,ok_rate")
    if a.dir:                                   # audio real: recortes de la misma cancion
        for g, x in full.items():
            for dur in (15, 30, 45, 60, 90, 135):
                if dur * E.FS <= len(x): c.writerow([g, dur, int(msg_ok(x[:int(dur * E.FS)], BASE))])
    else:
        for dur in (30, 90, 180):
            res = {}
            for seed in range(3):
                for g, x in genres.load(dur, seed=100 * seed).items(): res.setdefault(g, []).append(msg_ok(x, BASE))
            for g, v in res.items(): c.writerow([g, dur, round(float(np.mean(v)), 2)])
    f.close(); print("fin", round(time.time() - t0))
if __name__ == "__main__":
    main()

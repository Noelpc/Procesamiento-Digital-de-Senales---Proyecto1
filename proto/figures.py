import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
import sys, echo_hiding as E, genres
R = sys.argv[1] if len(sys.argv) > 1 else "results"
plt.rcParams.update({"font.size": 7, "axes.grid": True, "grid.alpha": .3, "lines.linewidth": 1, "lines.markersize": 3,
                     "figure.dpi": 150, "axes.titlesize": 7, "legend.fontsize": 6, "legend.framealpha": .8})
OUT = "../article/figs/" if R.endswith("real") else "../article/figs_synth/"; import os; os.makedirs(OUT, exist_ok=True)
e1 = pd.read_csv(R + "/e1.csv"); e3 = pd.read_csv(R + "/e3.csv")
G = list(e1.genre.unique()); name = {k: k.replace("clasica_brahms", "clásica (Brahms)").replace("jazz_vibeace", "jazz (Vibe Ace)").replace("folk_fishin", "folk (Fishin')").replace("electronica", "electrónica") for k in G}
mk = dict(zip(G, "osv^"))

# Fig: R_cc ejemplo (bit 1 y bit 0)
E.WIN_MULT = 8; p = dict(d0=1000.0, d1=2000.0, a0=30.0, a1=30.0); L = E.window_len(1000, 2000)
x = list(genres.load(30, directory=("../audio" if R.endswith("real") else None)).values())[-1 if R.endswith("real") else 2]; t = np.arange(2048) / E.FS * 1e3
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.5), sharey=True)
for b, a_ in zip((1, 0), ax):
    y = E.encode_channel(x, [b], p); r = np.mean([E.acepstrum(y[k * L:(k + 1) * L], 2048) for k in range(20)], axis=0)
    a_.plot(t[8:140], r[8:140], "k"); a_.axvline(1, c="C0", ls="--", lw=.7); a_.axvline(2, c="C3", ls="--", lw=.7)
    a_.set_title(f"Bit {b} codificado"); a_.set_xlabel("Retardo (ms)"); a_.set_xlim(0.18, 3.2)
ax[0].set_ylabel("$R_{cc}$"); fig.tight_layout(); fig.savefig(OUT + "rcc.pdf"); plt.close()

# Fig: recuperacion y PESQ vs a
d = e1[e1.mult == 8]; d1 = d
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.6))
for g in G:
    s = d[d.genre == g]; ax[0].plot(s.a, 100 * s.rec, marker=mk[g], label=name[g])
    s = d1[d1.genre == g]; ax[1].plot(s.a, s.pesq, marker=mk[g])
ax[0].axhline(90, c="gray", ls=":"); ax[0].set_ylabel("Recuperación (%)"); ax[1].set_ylabel("PESQ")
for a_ in ax: a_.set_xlabel("Amplitud del eco $a$ (%)")
ax[0].legend(); fig.tight_layout(); fig.savefig(OUT + "vs_a.pdf"); plt.close()

# Fig: PESQ vs recuperacion
s1 = e1; fig, ax = plt.subplots(figsize=(3.5, 1.7))
for g in G: q = s1[s1.genre == g]; ax.scatter(100 * q.rec, q.pesq, marker=mk[g], s=9, label=name[g])
rho = spearmanr(s1.rec, s1.pesq)[0]; ax.set_xlabel("Recuperación (%)"); ax.set_ylabel("PESQ"); ax.legend(ncol=3, loc="lower left", fontsize=5)
ax.set_title(f"Spearman $\\rho$ = {rho:.2f}"); fig.tight_layout(); fig.savefig(OUT + "pesq_rec.pdf"); plt.close()

# Fig: ruido
fig, ax = plt.subplots(figsize=(3.5, 1.6)); q = e3.copy(); q["x"] = pd.to_numeric(q.snr_db, errors="coerce").replace(np.inf, 60).fillna(60)
for g in G: s = q[q.genre == g].sort_values("x"); ax.plot(s.x, 100 * s.rec, marker=mk[g], label=name[g])
ax.axhline(90, c="gray", ls=":"); ax.set_xlabel("SNR del ruido aditivo (dB; 60 = sin ruido)"); ax.set_ylabel("Recuperación (%)"); ax.legend(ncol=2)
fig.tight_layout(); fig.savefig(OUT + "ruido.pdf"); plt.close()

print("spearman rec-pesq", round(rho, 2), " rate-pesq", round(spearmanr(s1.rate_bps, s1.pesq)[0], 2), " rate-rec", round(spearmanr(s1.rate_bps, s1.rec)[0], 2))

"""Audio sintetico por 'genero' (sustituto reproducible de audio real). Con --dir usa WAV reales."""
import numpy as np, wave
from echo_hiding import FS, write_wav, read_wav

def _env(n, tau): return np.exp(-np.arange(n) / (tau * FS))

def clasica(dur, rng):       # notas armonicas sostenidas, poco ruido
    n = int(dur * FS); x = np.zeros(n)
    for s in np.arange(0, dur, 0.6):
        f = 220 * 2 ** (rng.integers(0, 24) / 12); i = int(s * FS); m = min(int(1.2 * FS), n - i)
        t = np.arange(m) / FS
        x[i:i + m] += sum(np.sin(2*np.pi*f*h*t) / h**1.2 for h in range(1, 6)) * _env(m, 0.5) * np.minimum(1, t * 40)
    return x + 0.003 * rng.standard_normal(n)

def rock(dur, rng):          # acordes saturados + bombo/caja ruidosos
    n = int(dur * FS); x = np.zeros(n)
    for s in np.arange(0, dur, 0.5):
        f = 82 * 2 ** (rng.integers(0, 12) / 12); i = int(s * FS); m = min(int(0.5 * FS), n - i); t = np.arange(m) / FS
        ch = sum(np.sin(2*np.pi*f*r*t) for r in (1, 1.5, 2, 3))
        x[i:i + m] += np.tanh(3 * ch) * _env(m, 0.3)
        k = min(int(0.2 * FS), n - i); x[i:i + k] += 2 * rng.standard_normal(k) * _env(k, 0.03)
    return x + 0.05 * rng.standard_normal(n)

def electronica(dur, rng):   # bajo sierra + hi-hat + sintetizador
    n = int(dur * FS); t = np.arange(n) / FS
    f = 55 * 2 ** (rng.integers(0, 7) / 12)
    x = 2 * ((t * f) % 1) - 1
    x *= (np.sin(2*np.pi*2*t) > 0) * 0.8 + 0.2
    for s in np.arange(0, dur, 0.125):
        i = int(s * FS); k = min(int(0.04 * FS), n - i); x[i:i + k] += 0.7 * rng.standard_normal(k) * _env(k, 0.01)
    return x + 0.3 * np.sin(2*np.pi*880*t) * (np.sin(2*np.pi*0.5*t) > 0)

def voz(dur, rng):           # tren de pulsos filtrado con formantes variables
    from scipy.signal import lfilter
    n = int(dur * FS); x = np.zeros(n)
    for s in np.arange(0, dur, 0.3):
        i = int(s * FS); m = min(int(0.25 * FS), n - i); f0 = 100 + 80 * rng.random()
        p = np.zeros(m); p[::int(FS / f0)] = 1
        for fc, bw in ((rng.uniform(300, 800), 80), (rng.uniform(900, 2500), 120)):
            r = np.exp(-np.pi * bw / FS); th = 2*np.pi*fc/FS
            p = lfilter([1], [1, -2*r*np.cos(th), r*r], p)
        x[i:i + m] += p * np.hanning(m)
    return x + 0.004 * rng.standard_normal(n)

GENRES = {"clasica": clasica, "rock": rock, "electronica": electronica, "voz": voz}

def load(dur=30, seed=0, directory=None):
    out = {}
    if directory:
        import glob, os
        for f in sorted(glob.glob(os.path.join(directory, "*.wav"))):
            x, _ = read_wav(f); out[os.path.basename(f)[:-4]] = x[:int(dur * FS), 0]
        return out
    for k, g in GENRES.items():
        rng = np.random.default_rng(seed + sum(map(ord, k)))
        x = g(dur, rng); out[k] = 9000 * x / np.abs(x).max()
    return out

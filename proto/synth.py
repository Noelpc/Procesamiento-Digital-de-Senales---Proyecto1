import numpy as np
from echo_hiding import FS, write_wav
import wave
def make(path, dur=20, seed=0):
    rng = np.random.default_rng(seed); n = int(dur * FS); t = np.arange(n) / FS
    out = np.zeros((n, 2))
    for c in range(2):
        x = np.zeros(n)
        for s in np.arange(0, dur, 0.25):                 # notas con armonicos + decaimiento
            f = 110 * 2 ** (rng.integers(0, 24) / 12); i = int(s * FS); m = int(0.4 * FS)
            tt = np.arange(min(m, n - i)) / FS
            x[i:i + len(tt)] += sum(np.sin(2*np.pi*f*h*tt)/h for h in range(1, 8)) * np.exp(-4*tt)
        x += 0.02 * rng.standard_normal(n)
        out[:, c] = 9000 * x / np.abs(x).max()
    hdr = wave._wave_params(2, 2, FS, 0, "NONE", "not compressed")
    write_wav(path, out, hdr)
if __name__ == "__main__": make("test.wav")

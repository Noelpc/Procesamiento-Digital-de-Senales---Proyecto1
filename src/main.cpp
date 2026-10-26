// Esteganografia por enmascaramiento con eco (Gruhl & Bender). Implementacion final C++17.
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <getopt.h>
#include <iostream>
#include <string>
#include <vector>

using std::string; using std::vector;
using cd = std::complex<double>;

static const int FS = 44100;
static const int WIN_MULT = 8;        // L = WIN_MULT * t_max (ver articulo)
static const uint8_t SYNC = 0x7E;
static const char* TYPES[] = {nullptr, "titulo", "artista", "autor", "album", "anio", "invitado", "productor"};

struct Params { double d0 = 1000, d1 = 2000, a0 = 30, a1 = 30; };

// ---------------- WAV ----------------
struct Wav {
    vector<uint8_t> buf;      // archivo completo (el encabezado se preserva byte a byte, R37)
    size_t data_off = 0, data_len = 0;
    size_t frames() const { return data_len / 4; }
    int16_t get(size_t n, int ch) const { int16_t v; std::memcpy(&v, &buf[data_off + 4 * n + 2 * ch], 2); return v; }
    void set(size_t n, int ch, int16_t v) { std::memcpy(&buf[data_off + 4 * n + 2 * ch], &v, 2); }
};
static uint32_t rd32(const uint8_t* p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t rd16(const uint8_t* p) { return p[0] | p[1] << 8; }

static bool read_wav(const string& path, Wav& w, string& err) {
    std::ifstream f(path, std::ios::binary);
    if (!f) { err = "no se puede abrir " + path; return false; }
    w.buf.assign(std::istreambuf_iterator<char>(f), {});
    if (w.buf.size() < 44 || std::memcmp(&w.buf[0], "RIFF", 4) || std::memcmp(&w.buf[8], "WAVE", 4)) { err = "no es WAV"; return false; }
    bool fmt = false;
    for (size_t p = 12; p + 8 <= w.buf.size();) {
        uint32_t sz = rd32(&w.buf[p + 4]);
        if (!std::memcmp(&w.buf[p], "fmt ", 4)) {
            if (rd16(&w.buf[p + 8]) != 1 || rd16(&w.buf[p + 10]) != 2 || rd32(&w.buf[p + 12]) != (uint32_t)FS || rd16(&w.buf[p + 22]) != 16) {
                err = "se requiere PCM 44100 Hz, 16 bit, estereo"; return false; }
            fmt = true;
        } else if (!std::memcmp(&w.buf[p], "data", 4)) {
            if (!fmt) { err = "WAV sin fmt"; return false; }
            w.data_off = p + 8; w.data_len = std::min<size_t>(sz, w.buf.size() - w.data_off);
            return true;
        }
        p += 8 + sz + (sz & 1);
    }
    err = "WAV sin chunk data"; return false;
}

// ---------------- parametros ----------------
static int samples(double d_us) { return (int)std::lround(d_us * 1e-6 * FS); }
static int window_len(const Params& p) { return WIN_MULT * std::max(samples(p.d0), samples(p.d1)); }   // R33/R42
static vector<double> impulse_response(double d_us, double a_pct) {
    int t = samples(d_us); vector<double> h(t + 1, 0.0); h[0] = 1.0; h[t] = a_pct / 100.0; return h;
}

// ---------------- protocolo ----------------
static uint8_t crc8(const vector<uint8_t>& d) {
    uint8_t c = 0;
    for (uint8_t b : d) { c ^= b; for (int i = 0; i < 8; i++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1); }
    return c;
}
static vector<int> pack(const vector<std::pair<int, string>>& recs) {
    vector<uint8_t> out;
    for (auto& r : recs) {
        string t = r.second.substr(0, 255);
        vector<uint8_t> body{(uint8_t)r.first, (uint8_t)t.size()}; body.insert(body.end(), t.begin(), t.end());
        out.push_back(SYNC); out.insert(out.end(), body.begin(), body.end()); out.push_back(crc8(body));
    }
    vector<int> bits; for (uint8_t b : out) for (int i = 7; i >= 0; i--) bits.push_back((b >> i) & 1);
    return bits;
}
struct Rec { bool known; int type; string text; };
static vector<Rec> parse(const vector<int>& bits) {
    vector<Rec> res; size_t i = 0, n = bits.size();
    auto byte = [&](size_t k) { int v = 0; for (int j = 0; j < 8; j++) v = v << 1 | bits[k + j]; return v; };
    while (i + 8 <= n) {
        if (byte(i) != SYNC) { i++; continue; }
        if (i + 32 > n) break;
        int typ = byte(i + 8), ln = byte(i + 16);
        if (ln == 0) { i++; continue; }                              // registro vacio: falso positivo de CRC
        size_t end = i + 24 + 8 * ln + 8;
        if (end > n) { i++; continue; }
        vector<uint8_t> body{(uint8_t)typ, (uint8_t)ln};
        for (int k = 0; k < ln; k++) body.push_back((uint8_t)byte(i + 24 + 8 * k));
        if (crc8(body) != byte(end - 8)) { i++; continue; }
        res.push_back({typ >= 1 && typ <= 7, typ, string(body.begin() + 2, body.end())});
        i = end;
    }
    return res;
}

// ---------------- Hamming(7,4) ----------------
static const int G[7][4] = {{1,1,0,1},{1,0,1,1},{1,0,0,0},{0,1,1,1},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
static const int Hm[3][7] = {{1,0,1,0,1,0,1},{0,1,1,0,0,1,1},{0,0,0,1,1,1,1}};
static vector<int> ham_encode(vector<int> bits) {
    while (bits.size() % 4) bits.push_back(0);
    vector<int> out;
    for (size_t i = 0; i < bits.size(); i += 4) for (int r = 0; r < 7; r++) { int s = 0; for (int c = 0; c < 4; c++) s += G[r][c] * bits[i + c]; out.push_back(s & 1); }
    return out;
}
static vector<int> ham_decode(const vector<int>& bits) {
    vector<int> out;
    for (size_t i = 0; i + 7 <= bits.size(); i += 7) {
        int c[7]; for (int k = 0; k < 7; k++) c[k] = bits[i + k];
        int syn = 0; for (int r = 0; r < 3; r++) { int s = 0; for (int k = 0; k < 7; k++) s += Hm[r][k] * c[k]; syn |= (s & 1) << r; }
        if (syn) c[syn - 1] ^= 1;
        out.push_back(c[2]); out.push_back(c[4]); out.push_back(c[5]); out.push_back(c[6]);
    }
    return out;
}

// ---------------- FFT ----------------
static void fft(vector<cd>& a, bool inv) {
    size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; i++) { size_t bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) std::swap(a[i], a[j]); }
    for (size_t len = 2; len <= n; len <<= 1) {
        double ang = 2 * M_PI / len * (inv ? 1 : -1); cd wl(std::cos(ang), std::sin(ang));
        for (size_t i = 0; i < n; i += len) { cd w(1); for (size_t k = 0; k < len / 2; k++) { cd u = a[i + k], v = a[i + k + len / 2] * w; a[i + k] = u + v; a[i + k + len / 2] = u - v; w *= wl; } }
    }
    if (inv) for (auto& x : a) x /= (double)n;
}

// ---------------- codificador ----------------
static void encode_channel(vector<double>& x, const vector<int>& bits, const Params& p) {
    int L = window_len(p); vector<double> h[2] = {impulse_response(p.d0, p.a0), impulse_response(p.d1, p.a1)};
    size_t N = std::max(h[0].size(), h[1].size()), nwin = (x.size() + L - 1) / L;
    vector<double> y(nwin * L + N, 0.0);
    for (size_t k = 0; k < nwin; k++) {                              // el flujo se repite ciclicamente en todo el archivo (R31)
        size_t s = k * L, e = std::min(x.size(), s + L);
        const vector<double>& hb = h[bits[k % bits.size()]];
        for (size_t n = s; n < e; n++) for (size_t m = 0; m < hb.size(); m++) y[n + m] += x[n] * hb[m];   // R34 convolucion, R36 overlap-add
    }
    std::copy(y.begin(), y.begin() + x.size(), x.begin());
}

// ---------------- decodificador ----------------
static double median(vector<double> v) {
    std::sort(v.begin(), v.end()); size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}
static void scores(const double* v, int L, const Params& p, int nfft, double& z0, double& z1) {
    int t0 = samples(p.d0), t1 = samples(p.d1);
    vector<cd> acc(nfft, 0.0);                                       // promedio de (ln|F{v}|)^2 con ventana rectangular y Hann
    for (int pass = 0; pass < 2; pass++) {
        vector<cd> a(nfft, 0.0);
        for (int i = 0; i < L; i++) a[i] = v[i] * (pass ? 0.5 - 0.5 * std::cos(2 * M_PI * i / (L - 1)) : 1.0);
        fft(a, false);
        for (int i = 0; i < nfft; i++) { double l = std::log(std::abs(a[i]) + 1e-9); acc[i] += 0.5 * l * l; }   // dominio espectral (R45)
    }
    fft(acc, true);                                                  // R_cc
    vector<cd>& a = acc;
    vector<double> ref;
    for (int i = 3; i < 2 * std::max(t0, t1); i++) if (std::abs(i - t0) > 3 && std::abs(i - t1) > 3) ref.push_back(a[i].real());
    double med = median(ref); vector<double> dev; for (double r : ref) dev.push_back(std::abs(r - med));
    double mad = median(dev) + 1e-12;
    z0 = (a[t0].real() - med) / mad; z1 = (a[t1].real() - med) / mad;
}
static vector<Rec> decode_channel(const vector<double>& x, const Params& p, double thr = 2.0, size_t maxP = 2100) {
    int L = window_len(p), nfft = 1; while (nfft < 2 * L) nfft <<= 1;
    size_t nw = x.size() / L; vector<double> d(nw), conf(nw);
    for (size_t k = 0; k < nw; k++) { double z0, z1; scores(&x[k * L], L, p, nfft, z0, z1); d[k] = std::max(-3.0, std::min(3.0, z1 - z0)); conf[k] = std::max(z0, z1); }
    vector<Rec> best;
    for (size_t P = 7; P <= std::min(maxP, nw); P += 7) {              // busqueda del periodo del flujo (multiplo del bloque Hamming)
        vector<double> s(P, 0.0);
        for (size_t k = 0; k < nw; k++) if (conf[k] >= thr) s[k % P] += d[k];    // R47: ventanas sin eco no votan
        vector<int> bits(P); for (size_t i = 0; i < P; i++) bits[i] = s[i] > 0;
        vector<Rec> recs, uniq;
        for (auto& r : parse(ham_decode(bits))) {                      // sin duplicados
            bool dup = false; for (auto& u : uniq) if (u.type == r.type && u.text == r.text) dup = true;
            if (!dup) uniq.push_back(r);
        }
        if (uniq.size() > best.size()) best = uniq;
    }
    return best;
}

// ---------------- CLI ----------------
static int usage(const char* a0) {
    std::fprintf(stderr, "uso: %s ENTRADA.wav SALIDA.wav [--titulo T --artista A --autor A --album A --anio Y --invitado G --productor P]\n"
                         "     %s CODIFICADO.wav          (decodifica)\n"
                         "opciones: --d0 us --d1 us --a0 %% --a1 %% --canal izq|der\n", a0, a0);
    return 1;
}
int main(int argc, char** argv) {
    static option opts[] = {{"titulo",1,0,1},{"artista",1,0,2},{"autor",1,0,3},{"album",1,0,4},{"anio",1,0,5},{"invitado",1,0,6},{"productor",1,0,7},
                            {"d0",1,0,'a'},{"d1",1,0,'b'},{"a0",1,0,'c'},{"a1",1,0,'d'},{"canal",1,0,'k'},{0,0,0,0}};
    Params p; int ch = 0; string meta[8]; bool has[8] = {false}; int c;
    opterr = 1;
    while ((c = getopt_long(argc, argv, "", opts, nullptr)) != -1) {
        if (c >= 1 && c <= 7) { meta[c] = optarg; has[c] = true; }          // R9: el ultimo gana
        else if (c == 'a') p.d0 = atof(optarg); else if (c == 'b') p.d1 = atof(optarg);
        else if (c == 'c') p.a0 = atof(optarg); else if (c == 'd') p.a1 = atof(optarg);
        else if (c == 'k') { string s = optarg; if (s == "izq") ch = 0; else if (s == "der") ch = 1; else return usage(argv[0]); }
        else return usage(argv[0]);                                          // R7: parametro desconocido aborta
    }
    vector<std::pair<int, string>> recs; for (int i = 1; i <= 7; i++) if (has[i]) recs.push_back({i, meta[i]});
    int npos = argc - optind; string err; Wav w;
    if (!recs.empty()) {                                                    // R28
        if (npos != 2) return usage(argv[0]);
        if (!read_wav(argv[optind], w, err)) { std::fprintf(stderr, "error: %s\n", err.c_str()); return 1; }
        vector<int> bits = ham_encode(pack(recs));
        if (bits.size() > w.frames() / window_len(p)) { std::fprintf(stderr, "error: audio demasiado corto para los metadatos\n"); return 1; }
        vector<double> x(w.frames()); for (size_t n = 0; n < x.size(); n++) x[n] = w.get(n, ch);
        encode_channel(x, bits, p);
        for (size_t n = 0; n < x.size(); n++) w.set(n, ch, (int16_t)std::max(-32768.0, std::min(32767.0, std::nearbyint(x[n]))));
        std::ofstream o(argv[optind + 1], std::ios::binary); o.write((const char*)w.buf.data(), w.buf.size());
        return o ? 0 : 1;
    }
    if (npos != 1) return usage(argv[0]);                                   // R39
    if (!read_wav(argv[optind], w, err)) { std::fprintf(stderr, "error: %s\n", err.c_str()); return 1; }
    vector<double> x(w.frames()); for (size_t n = 0; n < x.size(); n++) x[n] = w.get(n, ch);
    for (auto& r : decode_channel(x, p)) {
        if (r.known) std::printf("%s: %s\n", TYPES[r.type], r.text.c_str());                                   // R48/R49
        else std::fprintf(stderr, "ADVERTENCIA: metadato desconocido (tipo %d): %s\n", r.type, r.text.c_str()); // R50/R51
    }
    return 0;
}

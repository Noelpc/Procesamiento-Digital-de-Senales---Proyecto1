#!/bin/sh
# Prueba de ida y vuelta (C++ <-> Python). Requiere: make, python3 con numpy y scipy.
set -e
cd "$(dirname "$0")/.."
make -s
python3 -c "import sys; sys.path.insert(0,'proto'); import genres, echo_hiding as E, numpy as np, wave; x=genres.load(60)['rock']; E.write_wav('/tmp/eco_test.wav', np.stack([x,x],1), wave._wave_params(2,2,44100,0,'NONE','not compressed'))"
./eco /tmp/eco_test.wav /tmp/eco_out.wav --titulo "Prueba" --artista "Equipo" --anio 2026
./eco /tmp/eco_out.wav > /tmp/eco_dec.txt
grep -q "titulo: Prueba" /tmp/eco_dec.txt && grep -q "anio: 2026" /tmp/eco_dec.txt && echo "OK ida y vuelta"
n=$(./eco /tmp/eco_out.wav --canal der | wc -l); [ "$n" = 0 ] && echo "OK canal derecho vacio"
./eco --opcion-falsa x /tmp/eco_test.wav 2>/dev/null && { echo "FALLO: no aborto ante parametro desconocido"; exit 1; } || echo "OK aborta ante parametro desconocido"

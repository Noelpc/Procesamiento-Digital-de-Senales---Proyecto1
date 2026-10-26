#!/bin/sh
# Obtiene las 3 pistas de prueba (dominio publico / CC BY) del repositorio de datos de librosa y las convierte a WAV 44.1 kHz, 16 bit, estereo.
# Requiere: git, ffmpeg. Licencias: ver *_licencia.txt
set -e
cd "$(dirname "$0")"
tmp=$(mktemp -d); git clone -q --depth 1 https://github.com/librosa/data.git "$tmp"
conv() { ffmpeg -loglevel error -y -i "$tmp/audio/$1" -ar 44100 -ac 2 -sample_fmt s16 -c:a pcm_s16le "$2.wav"; }
conv "Hungarian_Dance_number_5_-_Allegro_in_F_sharp_minor_(string_orchestra).hq.ogg" clasica_brahms
conv "Kevin_MacLeod_-_Vibe_Ace.hq.ogg" jazz_vibeace
conv "Karissa_Hobbs_-_Lets_Go_Fishin.hq.ogg" folk_fishin
rm -rf "$tmp"

#!/usr/bin/env bash
# Confere os quatro servidores com consultas reais. Sai com erro se algum falhar.
# Critério de aceite da issue #37: rota Alegrete, RS -> Vitória da Conquista, BA no OSRM próprio.
#   ./validar.sh                  (servidores em localhost)
#   OSM_HOST=10.0.0.5 ./validar.sh
set -uo pipefail

HOST="${OSM_HOST:-127.0.0.1}"
OSRM_CARRO="${PV_OSRM_URL:-http://$HOST:5000}"
OSRM_BIKE="${PV_OSRM_BIKE_URL:-http://$HOST:5001}"
NOMINATIM="${PV_NOMINATIM_URL:-http://$HOST:8088}"
OVERPASS="${PV_OVERPASS_URL:-http://$HOST:12345/api/interpreter}"

# OSRM recebe lon,lat. Alegrete, RS e Vitória da Conquista, BA:
ROTA="-55.7919,-29.7831;-40.8442,-14.8615"
falhas=0

campo() { grep -oE "\"$1\":[0-9.]+" | head -n1 | cut -d: -f2; }

rota() {
  local nome="$1" url="$2" perfil="$3" resp km h
  resp="$(curl -fsS --max-time 60 "$url/route/v1/$perfil/$ROTA?overview=false")" || { echo "FALHOU  $nome: sem resposta de $url"; falhas=$((falhas+1)); return; }
  if ! grep -q '"code":"Ok"' <<<"$resp"; then
    echo "FALHOU  $nome: $(head -c 200 <<<"$resp")"; falhas=$((falhas+1)); return
  fi
  km="$(campo distance <<<"$resp" | awk '{printf "%.0f", $1/1000}')"
  h="$(campo duration <<<"$resp" | awk '{printf "%.1f", $1/3600}')"
  # No OSRM público (nov/2026): 2.819 km de carro e 3.334 km de bicicleta. Bem menos que isso = extrato errado (o OSRM "encaixa" os pontos no que tiver)
  if (( km < 2000 )); then
    echo "FALHOU  $nome: só $km km. O OSRM está com o extrato do Brasil?"; falhas=$((falhas+1)); return
  fi
  echo "OK      $nome: Alegrete -> Vitória da Conquista, $km km, $h h"
}

rota "OSRM carro/moto" "$OSRM_CARRO" driving
rota "OSRM bicicleta " "$OSRM_BIKE" bike

if resp="$(curl -fsS --max-time 30 -G "$NOMINATIM/search" --data-urlencode "q=Alegrete, RS" -d format=jsonv2 -d limit=1)" \
   && grep -q '"lat"' <<<"$resp"; then
  echo "OK      Nominatim: $(grep -oE '"display_name":"[^"]+"' <<<"$resp" | head -n1 | cut -d'"' -f4)"
else
  echo "FALHOU  Nominatim: ${resp:-sem resposta de $NOMINATIM}"; falhas=$((falhas+1))
fi

# Cidades num raio de 30 km de Alegrete, como app/osm.py faz
consulta='[out:json][timeout:30];node(around:30000,-29.7831,-55.7919)["place"~"^(city|town)$"]["name"];out body;'
if resp="$(curl -fsS --max-time 60 --data-urlencode "data=$consulta" "$OVERPASS")" \
   && grep -q '"elements"' <<<"$resp"; then
  echo "OK      Overpass: $(grep -o '"type": *"node"' <<<"$resp" | wc -l | tr -d ' ') cidade(s) perto de Alegrete"
else
  echo "FALHOU  Overpass: ${resp:-sem resposta de $OVERPASS}"; falhas=$((falhas+1))
fi

exit "$falhas"

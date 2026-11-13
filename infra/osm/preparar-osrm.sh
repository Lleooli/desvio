#!/usr/bin/env bash
# Pré-processa o PBF para o OSRM com o algoritmo MLD (extract, partition, customize)
# numa pasta nova, sem mexer na versão que está no ar.
#   ./preparar-osrm.sh carro [versao]       (moto usa o perfil de carro)
#   ./preparar-osrm.sh bicicleta [versao]
# versao: padrão a data de hoje (AAAAMMDD). Saída em $OSM_DADOS/osrm/<perfil>/<versao>/brasil.osrm.*
# Se o perfil ainda não tem versão no ar (primeira vez), o link "atual" já aponta para esta.
source "$(dirname "${BASH_SOURCE[0]}")/comum.sh"

perfil="${1:?uso: ./preparar-osrm.sh carro|bicicleta [versao]}"
lua="$(perfil_lua "$perfil")"
versao="${2:-$(date +%Y%m%d)}"
[[ -f "$PBF" ]] || { echo "Falta $PBF. Rode ./baixar-pbf.sh antes." >&2; exit 1; }

base="$OSM_DADOS/osrm/$perfil"
pasta="$base/$versao"
if [[ -f "$pasta/pronto" ]]; then
  log "$perfil/$versao já está pronto."
  exit 0
fi
rm -rf "$pasta"
mkdir -p "$pasta"

# O osrm-extract nomeia a saída pelo arquivo de entrada: brasil.osm.pbf -> brasil.osrm
ln "$PBF" "$pasta/brasil.osm.pbf" 2>/dev/null || cp "$PBF" "$pasta/brasil.osm.pbf"

osrm() {
  docker run --rm -v "$OSM_DADOS/osrm:/dados/osrm" "$OSRM_IMAGEM" "$@"
}

inicio=$SECONDS
log "[$perfil] osrm-extract ($lua, $OSM_THREADS threads)..."
osrm osrm-extract -p "$lua" -t "$OSM_THREADS" "/dados/osrm/$perfil/$versao/brasil.osm.pbf"
log "[$perfil] osrm-partition..."
osrm osrm-partition -t "$OSM_THREADS" "/dados/osrm/$perfil/$versao/brasil.osrm"
log "[$perfil] osrm-customize..."
osrm osrm-customize -t "$OSM_THREADS" "/dados/osrm/$perfil/$versao/brasil.osrm"

rm -f "$pasta/brasil.osm.pbf"
cp "$PBF.md5" "$pasta/fonte.md5" 2>/dev/null || true
touch "$pasta/pronto"
log "[$perfil] pronto em $(( (SECONDS - inicio) / 60 )) min: $pasta ($(du -sh "$pasta" | cut -f1))"

if [[ ! -e "$base/atual" ]]; then
  ln -sfn "$versao" "$base/atual"
  log "[$perfil] primeira versão: atual -> $versao"
fi

# Configuração comum aos scripts de infra/osm. Não rode direto: os outros scripts fazem `source` dele.
set -euo pipefail

PASTA_OSM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PASTA_OSM"

# O mesmo .env que o docker compose lê
if [[ -f "$PASTA_OSM/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PASTA_OSM/.env"
  set +a
fi

OSM_DADOS="${OSM_DADOS:-$PASTA_OSM/dados}"
OSM_THREADS="${OSM_THREADS:-8}"
OSRM_MANTER="${OSRM_MANTER:-1}"
# Endereço para os scripts falarem com os servidores (o mesmo de OSM_BIND, ou localhost)
OSM_BIND="${OSM_BIND:-127.0.0.1}"
[[ "$OSM_BIND" == 0.0.0.0 ]] && OSM_HOST="${OSM_HOST:-127.0.0.1}" || OSM_HOST="${OSM_HOST:-$OSM_BIND}"
export OSM_HOST

PBF_URL="${PBF_URL:-https://download.geofabrik.de/south-america/brazil-latest.osm.pbf}"
PBF="$OSM_DADOS/pbf/brazil-latest.osm.pbf"

# A mesma imagem do compose.yml, para o pré-processamento sair compatível com o osrm-routed
OSRM_IMAGEM="$(grep -m1 -oE 'ghcr\.io/project-osrm/osrm-backend:[^[:space:]]+' "$PASTA_OSM/compose.yml")"

PERFIS=(carro bicicleta)

perfil_lua() {
  case "$1" in
    carro) echo /opt/car.lua ;;          # moto usa a rota de carro (app/geo.py)
    bicicleta) echo /opt/bicycle.lua ;;
    *) echo "Perfil desconhecido: $1 (use carro ou bicicleta)" >&2; return 1 ;;
  esac
}

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

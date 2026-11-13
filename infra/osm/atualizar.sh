#!/usr/bin/env bash
# Rotina mensal: extrato novo do Brasil e OSRM refeito, com troca rápida.
#
# Estratégia (detalhes no README):
# - OSRM não aceita atualização incremental. O pré-processamento roda numa pasta nova
#   (osrm/<perfil>/AAAAMMDD) enquanto a versão antiga continua no ar. Pronto, o link
#   "atual" passa a apontar para a nova e só o container daquele perfil reinicia: a
#   queda é o tempo de carregar os arquivos (segundos), não o de pré-processar (horas).
#   Se o container não ficar saudável em 10 min, o link volta para a versão anterior.
# - Nominatim e Overpass não são refeitos: aplicam sozinhos as diferenças diárias da
#   Geofabrik (REPLICATION_URL e OVERPASS_DIFF_URL no compose.yml). Aqui só conferimos.
#
#   ./atualizar.sh            (systemd timer ou cron: veja systemd/ e o README)
source "$(dirname "${BASH_SOURCE[0]}")/comum.sh"

exec 9>"$OSM_DADOS/.atualizar.lock"
flock -n 9 || { log "Outra atualização já está rodando."; exit 0; }

versao="$(date +%Y%m%d)"
log "Atualização $versao começou."
"$PASTA_OSM/baixar-pbf.sh"

saudavel() {  # espera o healthcheck do container ficar "healthy" (até 10 min)
  local servico="$1" id estado
  id="$(docker compose ps -q "$servico")"
  for _ in $(seq 1 60); do
    estado="$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null || echo ausente)"
    [[ "$estado" == healthy ]] && return 0
    sleep 10
  done
  return 1
}

for perfil in "${PERFIS[@]}"; do
  base="$OSM_DADOS/osrm/$perfil"
  anterior="$(readlink "$base/atual" 2>/dev/null || true)"
  if [[ "$anterior" == "$versao" ]]; then
    log "[$perfil] já está em $versao."
    continue
  fi

  # Um perfil por vez: o pico de RAM do osrm-extract soma com o que já está no ar
  "$PASTA_OSM/preparar-osrm.sh" "$perfil" "$versao"

  ln -sfn "$versao" "$base/atual.novo" && mv -Tf "$base/atual.novo" "$base/atual"
  log "[$perfil] atual -> $versao. Reiniciando osrm-$perfil..."
  docker compose restart "osrm-$perfil"

  if saudavel "osrm-$perfil"; then
    log "[$perfil] no ar com $versao."
  elif [[ -n "$anterior" ]]; then
    log "[$perfil] $versao não ficou saudável. Voltando para $anterior." >&2
    ln -sfn "$anterior" "$base/atual.novo" && mv -Tf "$base/atual.novo" "$base/atual"
    docker compose restart "osrm-$perfil"
    exit 1
  else
    log "[$perfil] $versao não ficou saudável e não há versão anterior." >&2
    exit 1
  fi

  # Guarda a atual e mais OSRM_MANTER versões prontas; apaga o resto
  find "$base" -mindepth 1 -maxdepth 1 -type d -regex '.*/[0-9]\{8\}' -printf '%f\n' | sort -r \
    | grep -vx "$versao" | tail -n +"$((OSRM_MANTER + 1))" \
    | while read -r velha; do log "[$perfil] apagando $velha"; rm -rf "${base:?}/$velha"; done
done

# Nominatim e Overpass se atualizam sozinhos; só registra o atraso para quem lê o log
log "Nominatim, dados de: $(curl -fsS --max-time 10 "http://$OSM_HOST:8088/status?format=json" | grep -oE '"data_updated":"[^"]+"' | cut -d'"' -f4 || echo 'sem resposta')"
log "Overpass, dados de: $(curl -fsS --max-time 10 "http://$OSM_HOST:12345/api/timestamp" || echo 'sem resposta')"

"$PASTA_OSM/validar.sh"
log "Atualização $versao terminou."

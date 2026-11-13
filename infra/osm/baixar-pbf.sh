#!/usr/bin/env bash
# Baixa o extrato do Brasil da Geofabrik (cerca de 2 GB) e confere o MD5.
# Só troca o arquivo em uso depois de conferido; se o local já é o mais novo, não baixa de novo.
#   ./baixar-pbf.sh
source "$(dirname "${BASH_SOURCE[0]}")/comum.sh"

mkdir -p "$OSM_DADOS/pbf"
novo="$PBF.novo"

for tentativa in 1 2 3; do
  md5_remoto="$(curl -fsSL --retry 3 "$PBF_URL.md5" | awk '{print $1}')"
  if [[ -f "$PBF" ]] && [[ "$(md5sum "$PBF" | awk '{print $1}')" == "$md5_remoto" ]]; then
    log "PBF já está atualizado ($md5_remoto)."
    exit 0
  fi
  log "Baixando $PBF_URL (tentativa $tentativa)..."
  curl -fL --retry 5 --retry-delay 30 -C - -o "$novo" "$PBF_URL" || { rm -f "$novo"; continue; }
  md5_local="$(md5sum "$novo" | awk '{print $1}')"
  if [[ "$md5_local" == "$md5_remoto" ]]; then
    mv -f "$novo" "$PBF"
    printf '%s  %s\n' "$md5_local" "$(basename "$PBF")" > "$PBF.md5"
    log "PBF conferido e salvo em $PBF ($(du -h "$PBF" | cut -f1))."
    exit 0
  fi
  # A Geofabrik pode ter publicado um arquivo novo no meio do download: baixa de novo
  log "MD5 não confere ($md5_local, esperado $md5_remoto). Baixando de novo."
  rm -f "$novo"
done

log "Não consegui baixar um PBF íntegro em 3 tentativas." >&2
exit 1

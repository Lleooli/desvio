"""Teste rápido pelo terminal, sem subir a API.

    python cli.py "Alegrete, RS" "Vitória da Conquista, BA"
    python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --veiculo moto --google --intervalo 250
    python cli.py "Florianópolis, SC" "Garopaba, SC" --veiculo bicicleta --intervalo 30
"""
import argparse
import asyncio
import json

from app import coletor, geo


def main() -> None:
    ap = argparse.ArgumentParser(description="Monta uma viagem por terra (carro, moto ou bicicleta)")
    ap.add_argument("origem")
    ap.add_argument("destino")
    ap.add_argument("--veiculo", choices=geo.VEICULOS, default="carro")
    ap.add_argument("--intervalo", type=float, default=200, help="km entre paradas (padrão 200)")
    ap.add_argument("--por-categoria", type=int, default=5)
    ap.add_argument("--google", action="store_true", help="usar o gosom (precisa estar rodando)")
    ap.add_argument("--sem-instagram-busca", action="store_true")
    ap.add_argument("--saida", default="viagem.json")
    args = ap.parse_args()

    r = asyncio.run(coletor.planejar_viagem(args.origem, args.destino, args.intervalo,
                                            por_categoria=args.por_categoria, usar_google_maps=args.google,
                                            buscar_instagram=not args.sem_instagram_busca,
                                            veiculo=args.veiculo))

    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

    print(f'Rota de {r["veiculo"]}: {r["rota"]["distancia_km"]} km, ~{r["rota"]["duracao_h"]} h')
    for p in r["paradas"]:
        km = f' (km {p["km_na_rota"]})' if "km_na_rota" in p else ""
        print(f'\n== {p["nome"]}{"/" + p["uf"] if p.get("uf") else ""}{km} — {len(p["cards"])} cards')
        for card in p["cards"]:
            nota = f' ★{card["nota"]}' if card.get("nota") else ""
            ig = f'  {card["instagram"]}' if card.get("instagram") else ""
            print(f'   [{card["categoria"]}] {card["nome"]}{nota}{ig}')
    print(f"\nJSON completo salvo em {args.saida}")


if __name__ == "__main__":
    main()

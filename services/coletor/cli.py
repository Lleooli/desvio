"""Teste rápido pelo terminal, sem subir a API.

    python cli.py carro "Alegrete, RS" "Vitória da Conquista, BA"
    python cli.py carro "Alegrete, RS" "Vitória da Conquista, BA" --google --intervalo 250
    python cli.py aviao "São Paulo, SP:1" "Salvador, BA:3" --google
"""
import argparse
import asyncio
import json

from app import coletor


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="modo", required=True)

    c = sub.add_parser("carro")
    c.add_argument("origem")
    c.add_argument("destino")
    c.add_argument("--intervalo", type=float, default=200, help="km entre paradas (padrão 200)")
    c.add_argument("--por-categoria", type=int, default=5)

    a = sub.add_parser("aviao")
    a.add_argument("cidades", nargs="+", help='"Cidade, UF:dias"')
    a.add_argument("--por-categoria", type=int, default=8)

    for p in (c, a):
        p.add_argument("--google", action="store_true", help="usar o gosom (precisa estar rodando)")
        p.add_argument("--sem-instagram-busca", action="store_true")
        p.add_argument("--saida", default="viagem.json")

    args = ap.parse_args()
    if args.modo == "carro":
        r = asyncio.run(coletor.planejar_carro(args.origem, args.destino, args.intervalo,
                                               por_categoria=args.por_categoria, usar_google_maps=args.google,
                                               buscar_instagram=not args.sem_instagram_busca))
    else:
        cidades = []
        for item in args.cidades:
            nome, _, dias = item.rpartition(":") if ":" in item else (item, "", "1")
            cidades.append({"cidade": nome, "dias": int(dias or 1)})
        r = asyncio.run(coletor.planejar_cidades(cidades, por_categoria=args.por_categoria,
                                                 usar_google_maps=args.google,
                                                 buscar_instagram=not args.sem_instagram_busca))

    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

    if "rota" in r:
        print(f'Rota: {r["rota"]["distancia_km"]} km, ~{r["rota"]["duracao_h"]} h dirigindo')
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

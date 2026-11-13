# Design system Desvio

A referência completa (tokens, componentes com preview, regras de uso) está no [design system Desvio](https://claude.ai/artifact/4axmnGJWvKEXczHh3RP4uq). Este arquivo resume o que o código precisa saber.

## Fonte única

- `packages/design-tokens/tokens.json` — cores (temas claro e escuro), tipografia, espaços, raios e sombras
- `packages/design-tokens/tokens.css` — os mesmos tokens como variáveis CSS (para web e protótipos)
- `apps/mobile/src/tema/tokens.gerado.ts` — gerado do JSON com `npm run tokens`; não edite à mão

## Identidade em uma linha

Estrada brasileira: verde das placas (`placa`), amarelo da faixa (`faixa`), asfalto (`asfalto`), areia (`surface-100`) e um céu de fim de tarde do azul ao laranja (`ceu-*`), usado só no componente Céu.

## Tipografia

- **Bricolage Grotesque** (`display`): títulos, nome do lugar no card
- **Barlow Condensed** (`placa`): só quilometragem e nomes na Estrada, sempre em maiúsculas
- **Barlow** (`sans`): todo o resto

## Componentes

Button, Segmented, Chip, Rating, SwipeCard, SwipeActions, Toast, StopItem, TextField, BottomNav, Ceu, Estrada, Destaque, Icon. As props estão no design system; no app, reescreva cada um em React Native com os mesmos nomes e tokens.

## Regras que mais importam

- Toda decisão de swipe tem botão: Passo, Favorito e Bora sempre visíveis.
- Passo não é vermelho. `perigo` só para erros.
- Categorias não têm cor própria; ícone e palavra as distinguem.
- Texto sobre foto só no `scrim` (em `on-scrim`) ou sobre `vidro` (em `ink`).
- Contraste AA verificado nos dois temas; mantenha os pares de cor do JSON.

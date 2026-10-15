# Chip
Rótulo de categoria do lugar; com `onClick` vira filtro liga/desliga.

**O consumidor fornece:** `categoria` (preenche rótulo e ícone) ou `label` + `icon`; para filtro, `selected` e `onClick`; `onPhoto` quando fica sobre a foto do card.

- As cinco categorias têm o mesmo visual. Quem diferencia é o ícone e a palavra, não a cor: não crie cores por categoria.
- Filtro selecionado inverte para fundo `ink` com texto `surface-100`, e expõe `aria-pressed`.
- Rótulo em `label` (maiúsculas, 13px). Uma palavra só.

# Button
Botão de ação para tudo que não é a decisão de swipe: criar viagem, montar roteiro, editar paradas.

**O consumidor fornece:** `children` (verbo no infinitivo, curto: "Montar roteiro", "Adicionar escala"), `onClick`, opcionalmente `icon`, `variant`, `size` e `block`.

- `primary` (fundo `placa`, texto `on-placa`): uma por tela, a ação que avança o fluxo.
- `secondary` (contorno `ink`): ações paralelas, como editar ou voltar ao swipe.
- `ghost` (texto `placa`): ações de baixo peso dentro de listas.
- `favorito` (fundo `faixa` com `shadow-favorito`): só para ações ligadas a favoritos.
- `block` no rodapé das telas de formulário, dentro da margem `space-4`.
- Pílula (`radius-pill`) com altura `button-h` (52px); `sm` só em linhas densas, nunca abaixo de 40px.

Não use Button para Bora, Passo ou Favorito: isso é `SwipeActions`.

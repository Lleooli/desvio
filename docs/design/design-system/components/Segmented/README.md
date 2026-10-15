# Segmented
Escolha entre duas a quatro opções exclusivas, sempre visíveis.

**O consumidor fornece:** `opcoes` (`valor`, `label`, `icon` opcional), `valor` + `onChange` (ou `padrao` para deixar o estado com o componente), `rotulo` para o leitor de tela e `block` para ocupar a largura.

- Uso principal: "Carro / Avião" na criação da viagem, e dias por cidade no modo avião.
- Mais de quatro opções: use Chips de filtro.
- A opção ativa sobe para `surface-200` com `shadow-1`; o trilho é `surface-300`.
- É um `radiogroup`: cada opção é um `radio` com `aria-checked`.

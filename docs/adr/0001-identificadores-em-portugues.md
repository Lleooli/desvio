# Identificadores do código em português

Os identificadores (módulos, funções, variáveis, campos da API e do banco) são escritos em português do Brasil, como o domínio e a equipe falam (`viagem`, `parada`, `roteiro`, `km_na_rota`). Assim, o glossário do `CONTEXT.md` liga termo e código quase sempre com o mesmo nome, e ninguém precisa traduzir de cabeça. A exceção são os componentes do design system em `apps/mobile/src/componentes` (`Button`, `Chip`, `TextField`, `BottomNav`…), que ficam em inglês para espelhar os nomes do canvas e do design system.

## Consequências

- Quem chega com a convenção comum de "código em inglês", pessoa ou agente, não deve traduzir nomes existentes nem escrever código novo em inglês fora dos componentes do design system.
- Nomes de bibliotecas e de APIs externas continuam como são.

# Ceu
Fundo de céu de fim de tarde, do azul ao laranja do pôr do sol, para o topo das telas de entrada e para lugares sem foto.

**O consumidor fornece:** o conteúdo (`children`), `variante` (`faixa`, o padrão, ou `placa`), `serra` para recortar a base, `fundoSerra` com a cor da superfície que vem logo abaixo, e `arredondado` quando o céu é um bloco dentro da tela.

- Quatro brilhos radiais sobre `ceu-base`: `ceu-azul` no alto à esquerda, `ceu-claro` (ou `ceu-placa`, na variante placa) no alto à direita, `ceu-sol` embaixo à esquerda e `ceu-faixa` (ou `ceu-claro`) embaixo à direita.
- Azul e laranja existem só aqui. Não use `ceu-azul` nem `ceu-sol` em botões, texto ou ícones.
- Use no topo de Boas-vindas, Entrar, Nova viagem, Carregando rota e Roteiro, e como fundo do SwipeCard sem foto. Uma vez por tela.
- Texto em `ink` e `ink-muted`; ambos passam por cima de qualquer ponto do gradiente, nos dois temas.
- Com `serra`, a base vira um perfil de morros que se encaixa na superfície seguinte. Passe em `fundoSerra` a cor dessa superfície.

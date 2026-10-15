# Toast
Confirmação curta que aparece na base da tela depois de uma ação, com desfazer opcional.

**O consumidor fornece:** a mensagem (`children`), `icon`, e `acao` + `onAcao` quando dá para desfazer.

- Depois de Bora e Favorito, mostre o Toast com "Desfazer" por 4 segundos. Depois de Passo, não: o swipe já é o retorno.
- Uma frase, sem ponto final, nomeando o lugar: "Churrascaria Gaúcha entrou no roteiro".
- Fica acima da BottomNav, centralizado, com `space-4` de margem. Um por vez; o novo substitui o anterior.
- Fundo `asfalto`, texto `on-asfalto`, ícone e ação em `faixa`. Tem `role="status"`.

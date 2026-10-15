# TextField
Campo de texto com rótulo, ícone opcional, dica e erro.

**O consumidor fornece:** `label` (sempre, em forma de pergunta: "De onde você sai?"), `value`/`onChange` ou `defaultValue`, `placeholder` com o formato esperado ("Cidade, UF"), `hint` e `erro`.

- O rótulo fica sempre visível acima do campo. O placeholder não substitui o rótulo.
- Borda `ink-muted` em repouso; com foco, borda `ink` e anel de 4px em `halo-foco`. `perigo` quando há `erro`, com a mensagem no lugar da dica.
- Mensagem de erro diz o que fazer ("Confira a grafia"), sem culpar o usuário.

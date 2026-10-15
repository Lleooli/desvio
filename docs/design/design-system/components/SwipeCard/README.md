# SwipeCard
O card de um lugar na tela de swipe: foto cheia, nome, cidade, nota, km na rota e Instagram.

**O consumidor fornece:** os campos do card que a API devolve (`nome`, `categoria`, `foto`, `cidade`, `uf`, `nota`, `avaliacoes`, `km`, `horas`, `descricao`, `instagram`), `instagramProvavel` quando `instagram_origem` for `"busca"`, e o gesto de arrastar. O componente não arrasta sozinho: o app move o card com `style.transform` e passa `stamp` conforme a direção.

- Arrastar para a direita mostra `stamp: "bora"`; para a esquerda, `"passo"`; para cima, `"favorito"`. A partir de ~30% da largura, o card sai e a decisão é registrada.
- Todo gesto tem botão equivalente em `SwipeActions` logo abaixo. Nunca dependa só do gesto.
- Sem `foto`, o card mostra o Céu com o ícone da categoria. Não use foto de banco de imagens no lugar.
- Chip de categoria e tag de km ficam sobre a foto em `vidro` fosco, para mostrar mais da imagem.
- `km` e `horas` só no modo carro. No modo avião, omita: a tag some.
- O @ do Instagram abre em nova aba. Quando veio de busca, leva " · provável".
- Largura máxima 380px, proporção fixa; na tela, o card ocupa a largura menos `space-4` de cada lado.

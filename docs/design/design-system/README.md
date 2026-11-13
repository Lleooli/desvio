Desvio planeja viagens por terra, de carro, moto ou bicicleta: o app sugere lugares no caminho e a pessoa escolhe com o dedo, como num app de encontros. A identidade vem da estrada brasileira: o verde das placas de rodovia, o amarelo da faixa central, o asfalto e o céu de fim de tarde, do azul ao laranja do pôr do sol. É um app para celular primeiro.

## Princípios

- **A foto decide.** No swipe, a imagem do lugar ocupa o card inteiro e o texto fica por cima, curto. O que fica sobre a foto é `vidro` fosco, para esconder o mínimo dela.
- **Toda decisão tem botão.** O gesto é atalho; Passo, Favorito e Bora estão sempre visíveis em `SwipeActions`.
- **A estrada é o eixo.** Tudo se ordena por quilômetro: tags `KM 512`, a linha do tempo de `StopItem`, o roteiro final. A `Estrada`, com as cidades correndo pela pista, é a assinatura visual.
- **Calor só no topo.** O `Ceu` aquece o topo das telas de entrada; o resto da interface é areia lisa, para o conteúdo aparecer.

## Voz e texto

- Português do Brasil, tratando a pessoa por "você". Frases curtas e diretas.
- Verbos curtos e informais nos botões de decisão: **Bora**, **Passo**, **Favorito**. Nos demais botões, infinitivo: "Montar roteiro", "Adicionar parada".
- Títulos de tela como pergunta ou convite, com uma palavra em `Destaque`: "Para onde a *estrada* te leva?", "Escolha suas *paradas*".
- Rótulos de campo em forma de pergunta: "De onde você sai?", "Para onde vai?".
- Números no formato brasileiro: "4,7", "1.834 avaliações", "~6h de estrada". Quilometragem em maiúsculas: "KM 512", "+6H".
- Sem emoji na interface. Ícones do conjunto `Icon` fazem esse papel.
- Mensagens de erro dizem o que fazer: "Não achamos essa cidade. Confira a grafia."
- Toasts nomeiam o lugar e não têm ponto final: "Churrascaria Gaúcha entrou no roteiro".

## Cor

- Fundo de tela em `surface-100`; campos, folhas e barra de navegação em `surface-200`; chips, trilhos e Segmented em `surface-300`.
- Texto em `ink`; metadados em `ink-muted`. Ambos passam de 4,9:1 em todas as superfícies, no Céu e no vidro, nos dois temas.
- `placa` é a cor da marca: botão principal, Bora, item ativo da navegação e links. Texto sobre ela sempre em `on-placa`; no tema escuro a placa clareia e o texto fica escuro.
- `faixa` só em destaques pontuais: Favorito, parada atual, bordas da Estrada, ação do Toast e o Destaque. Texto sobre ela em `on-faixa`. Nunca use `faixa` como texto sobre fundo claro.
- `asfalto` para a pista da Estrada, o Toast e o cabeçalho do roteiro. Texto em `on-asfalto`.
- O Céu é um fim de tarde na estrada: `ceu-azul` no alto à esquerda, `ceu-claro` no alto à direita, `ceu-sol` (laranja de pôr do sol) embaixo à esquerda e `ceu-faixa` embaixo à direita, sobre `ceu-base`. A variante placa troca o brilho do alto à direita por `ceu-placa`. Azul e laranja existem só no Céu: nunca em botões, texto ou ícones.
- `vidro` (com blur de 12px) é o único fundo permitido sobre fotos, além do `scrim` na base do card.
- `perigo` só para erros e ações destrutivas. Passo não usa `perigo`: recusar um lugar não é erro.
- Categorias (turismo, restaurante, posto, natureza, hospedagem) não têm cor própria; ícone e palavra as distinguem.
- Bordas de controles em `ink` ou `ink-muted` (3:1 ou mais). `line` é só para divisórias decorativas.

## Tipografia

- Três famílias do Google Fonts, cada uma com um papel:
  - **Bricolage Grotesque** (`display`) nos títulos: `display-xl` no título da tela (uma vez), `display-l` no nome do lugar dentro do card, `title` em seções e folhas. Sempre com letter-spacing negativo, como nos tokens.
  - **Barlow Condensed** (`placa`), a letra de placa de rodovia: só `km` (quilometragem e horas) e `estrada` (cidades na Estrada e carimbos do swipe), sempre em maiúsculas.
  - **Barlow** (`sans`) no resto: `body`, `body-strong`, `body-s`, `label`, `button`.
- Corpo mínimo de 13px. Nada em `placa` abaixo de 13px.

## Espaço, forma e layout

- Margem lateral de toda tela: `space-4`. Entre seções: `space-6`. Topo de tela: `space-8`.
- Todo alvo de toque tem pelo menos `touch` (48px). Botões principais: pílula com `button-h` (52px). Botões redondos de swipe: 64px; Favorito: 52px.
- Raios: `radius-lg` no card de swipe e no Céu em bloco, `radius-md` em campos e listas, `radius-sm` na tag de km, `radius-pill` em botões, chips, Segmented e Toast.
- Formas com significado, não use para outra coisa:
  - **Serra** (recorte de morros na base do `Ceu`) = passagem do topo aquecido para o conteúdo.
  - **Estrada** curva = a rota.
- Layout pensado para 360–430px de largura. Em telas maiores, uma coluna de no máximo 480px, centralizada.
- `BottomNav` fixa no rodapé nas quatro áreas principais; some no swipe em tela cheia e nos passos de criação de viagem.

## Sombras

- Interface plana por padrão. `shadow-1` só em opção ativa do Segmented e chip selecionado; `shadow-2` em botões redondos de swipe, Toast e folhas; `shadow-card` só no card do topo da pilha; `shadow-favorito` só no amarelo do Favorito.

## Movimento

As curvas e durações estão em `components/bundle.css` como variáveis:

- `--t-toque` (140ms) com `--ease-saida` ao pressionar: botões encolhem para `scale(.97)`, botões redondos para `.92`.
- `--t-ui` (200ms) com `--ease-saida` em troca de cor, borda e sombra.
- `--t-folha` (420ms) com `--ease-folha` em folhas que sobem da base e no card saindo da tela no swipe.
- `--t-entrada` (640ms) para o conteúdo do topo entrar ao abrir uma tela: sobe 10px e aparece, com 70ms de atraso entre itens.
- No swipe, o card acompanha o dedo e gira até 12°; o carimbo aparece com opacidade proporcional ao arrasto. Passando de ~30% da largura, o card sai; abaixo disso, volta ao centro.
- A `Estrada` corre a 36px/s. Toast entra subindo 12px em 380ms.
- Com `prefers-reduced-motion`, tudo troca de estado sem animação e a Estrada fica parada.

## Foco e estados

- Campos com foco: borda `ink` e anel de 4px em `halo-foco`.
- Demais controles: contorno de 2px em `foco` com 2px de afastamento. No escuro, o foco é amarelo.
- Desabilitado: 45% de opacidade, sem sombra.

## Fotos

- Fotos vêm do Google Maps ou da Wikipedia, sempre do próprio lugar. Recorte em `object-fit: cover`, sem filtros.
- Sem foto, o card mostra o `Ceu` com o ícone da categoria. Não use foto genérica de banco de imagens.
- Texto sobre foto só dentro do `scrim` (em `on-scrim`) ou sobre `vidro` (em `ink`).

## Iconografia

- Use apenas o conjunto `Icon`: traço de 1.8 numa grade de 24px, pontas arredondadas, cor herdada do texto.
- Tamanhos: 16px em chips e metadados, 20px em botões, campos e Toast, 22px na navegação, 28px nos botões de swipe.
- Instagram aparece como `at` seguido do @ do perfil. Não reproduza logotipos de marcas (Instagram, Google, postos de bandeira).

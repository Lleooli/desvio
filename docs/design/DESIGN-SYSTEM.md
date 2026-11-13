# Design system Desvio

> Cópia local do [design system Desvio](https://claude.ai/artifact/4axmnGJWvKEXczHh3RP4uq) (tokens v3), baixada em 2026-10-15. A versão viva é o artifact; a fonte dos tokens no código é `packages/design-tokens/tokens.json`.

## Sumário

- [Brand book](#brand-book)
- [Tokens](#tokens)
- [Componentes](#componentes)
- [Tipos dos componentes](#tipos-dos-componentes)

## Brand book

Desvio planeja viagens por terra, de carro, moto ou bicicleta: o app sugere lugares no caminho e a pessoa escolhe com o dedo, como num app de encontros. A identidade vem da estrada brasileira: o verde das placas de rodovia, o amarelo da faixa central, o asfalto e o céu de fim de tarde, do azul ao laranja do pôr do sol. É um app para celular primeiro.

### Princípios

- **A foto decide.** No swipe, a imagem do lugar ocupa o card inteiro e o texto fica por cima, curto. O que fica sobre a foto é `vidro` fosco, para esconder o mínimo dela.
- **Toda decisão tem botão.** O gesto é atalho; Passo, Favorito e Bora estão sempre visíveis em `SwipeActions`.
- **A estrada é o eixo.** Tudo se ordena por quilômetro: tags `KM 512`, a linha do tempo de `StopItem`, o roteiro final. A `Estrada`, com as cidades correndo pela pista, é a assinatura visual.
- **Calor só no topo.** O `Ceu` aquece o topo das telas de entrada; o resto da interface é areia lisa, para o conteúdo aparecer.

### Voz e texto

- Português do Brasil, tratando a pessoa por "você". Frases curtas e diretas.
- Verbos curtos e informais nos botões de decisão: **Bora**, **Passo**, **Favorito**. Nos demais botões, infinitivo: "Montar roteiro", "Adicionar parada".
- Títulos de tela como pergunta ou convite, com uma palavra em `Destaque`: "Para onde a *estrada* te leva?", "Escolha suas *paradas*".
- Rótulos de campo em forma de pergunta: "De onde você sai?", "Para onde vai?".
- Números no formato brasileiro: "4,7", "1.834 avaliações", "~6h de estrada". Quilometragem em maiúsculas: "KM 512", "+6H".
- Sem emoji na interface. Ícones do conjunto `Icon` fazem esse papel.
- Mensagens de erro dizem o que fazer: "Não achamos essa cidade. Confira a grafia."
- Toasts nomeiam o lugar e não têm ponto final: "Churrascaria Gaúcha entrou no roteiro".

### Cor

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

### Tipografia

- Três famílias do Google Fonts, cada uma com um papel:
  - **Bricolage Grotesque** (`display`) nos títulos: `display-xl` no título da tela (uma vez), `display-l` no nome do lugar dentro do card, `title` em seções e folhas. Sempre com letter-spacing negativo, como nos tokens.
  - **Barlow Condensed** (`placa`), a letra de placa de rodovia: só `km` (quilometragem e horas) e `estrada` (cidades na Estrada e carimbos do swipe), sempre em maiúsculas.
  - **Barlow** (`sans`) no resto: `body`, `body-strong`, `body-s`, `label`, `button`.
- Corpo mínimo de 13px. Nada em `placa` abaixo de 13px.

### Espaço, forma e layout

- Margem lateral de toda tela: `space-4`. Entre seções: `space-6`. Topo de tela: `space-8`.
- Todo alvo de toque tem pelo menos `touch` (48px). Botões principais: pílula com `button-h` (52px). Botões redondos de swipe: 64px; Favorito: 52px.
- Raios: `radius-lg` no card de swipe e no Céu em bloco, `radius-md` em campos e listas, `radius-sm` na tag de km, `radius-pill` em botões, chips, Segmented e Toast.
- Formas com significado, não use para outra coisa:
  - **Serra** (recorte de morros na base do `Ceu`) = passagem do topo aquecido para o conteúdo.
  - **Estrada** curva = a rota.
- Layout pensado para 360–430px de largura. Em telas maiores, uma coluna de no máximo 480px, centralizada.
- `BottomNav` fixa no rodapé nas quatro áreas principais; some no swipe em tela cheia e nos passos de criação de viagem.

### Sombras

- Interface plana por padrão. `shadow-1` só em opção ativa do Segmented e chip selecionado; `shadow-2` em botões redondos de swipe, Toast e folhas; `shadow-card` só no card do topo da pilha; `shadow-favorito` só no amarelo do Favorito.

### Movimento

As curvas e durações estão em `components/bundle.css` como variáveis:

- `--t-toque` (140ms) com `--ease-saida` ao pressionar: botões encolhem para `scale(.97)`, botões redondos para `.92`.
- `--t-ui` (200ms) com `--ease-saida` em troca de cor, borda e sombra.
- `--t-folha` (420ms) com `--ease-folha` em folhas que sobem da base e no card saindo da tela no swipe.
- `--t-entrada` (640ms) para o conteúdo do topo entrar ao abrir uma tela: sobe 10px e aparece, com 70ms de atraso entre itens.
- No swipe, o card acompanha o dedo e gira até 12°; o carimbo aparece com opacidade proporcional ao arrasto. Passando de ~30% da largura, o card sai; abaixo disso, volta ao centro.
- A `Estrada` corre a 36px/s. Toast entra subindo 12px em 380ms.
- Com `prefers-reduced-motion`, tudo troca de estado sem animação e a Estrada fica parada.

### Foco e estados

- Campos com foco: borda `ink` e anel de 4px em `halo-foco`.
- Demais controles: contorno de 2px em `foco` com 2px de afastamento. No escuro, o foco é amarelo.
- Desabilitado: 45% de opacidade, sem sombra.

### Fotos

- Fotos vêm do Google Maps ou da Wikipedia, sempre do próprio lugar. Recorte em `object-fit: cover`, sem filtros.
- Sem foto, o card mostra o `Ceu` com o ícone da categoria. Não use foto genérica de banco de imagens.
- Texto sobre foto só dentro do `scrim` (em `on-scrim`) ou sobre `vidro` (em `ink`).

### Iconografia

- Use apenas o conjunto `Icon`: traço de 1.8 numa grade de 24px, pontas arredondadas, cor herdada do texto.
- Tamanhos: 16px em chips e metadados, 20px em botões, campos e Toast, 22px na navegação, 28px nos botões de swipe.
- Instagram aparece como `at` seguido do @ do perfil. Não reproduza logotipos de marcas (Instagram, Google, postos de bandeira).

## Tokens

### Cores

| Token | Claro | Escuro | Uso |
| --- | --- | --- | --- |
| `surface-100` | `#F6F2E9` | `#121614` | Fundo das telas. Areia no claro, asfalto à noite no escuro. |
| `surface-200` | `#FFFFFF` | `#1B201E` | Superfícies elevadas: campos, folhas (bottom sheets), barra de navegação, linha do tempo de paradas, opção ativa do Segmented. |
| `surface-300` | `#ECE5D6` | `#272D2A` | Superfícies afundadas: chips não selecionados, trilho do Segmented e da linha do tempo, área da foto enquanto carrega. |
| `ink` | `#1B1F1D` | `#F1EDE4` | Texto principal e ícones sobre surface-100, surface-200, surface-300, as cores do céu e vidro (9,8:1 ou mais nos dois temas). Borda do botão secundário e dos campos com foco. Fundo do Toast. |
| `ink-muted` | `#565D59` | `#AAB1AC` | Texto secundário (cidade, horário, avaliações) sobre surface-100, surface-200, surface-300 e as cores do céu (4,9:1 ou mais). |
| `line` | `#D6CDBA` | `#3A413D` | Divisórias decorativas. Nunca como única borda de um controle: use ink ou ink-muted, que passam de 3:1. |
| `placa` | `#0B6B45` | `#46B985` | Cor da marca, o verde das placas de rodovia. Botão principal, Bora, item ativo da navegação, links. Como texto sobre surface-100 e surface-200 passa de 5,8:1. |
| `on-placa` | `#FFFFFF` | `#0A1F16` | Texto e ícone sobre placa (6,5:1 no claro, 7:1 no escuro). No escuro a placa clareia, por isso o texto fica escuro. |
| `faixa` | `#F2B705` | `#F2B705` | Amarelo da faixa central. Favorito, marcador da parada atual, tracejado da Estrada e marca-texto do Destaque. Nunca como texto sobre fundo claro. |
| `on-faixa` | `#1B1F1D` | `#1B1F1D` | Texto e ícone sobre faixa (9,2:1). |
| `estrela` | `#9A6B00` | `#F2B705` | Estrela da nota sobre surface-100 e surface-200 (ícone, 4,2:1 ou mais). Sobre a foto use on-scrim. |
| `asfalto` | `#23292B` | `#2C3336` | A pista da Estrada, cabeçalho do roteiro, barra de progresso. Texto em on-asfalto. |
| `on-asfalto` | `#F3EFE6` | `#F3EFE6` | Texto sobre asfalto, inclusive o nome das cidades correndo na Estrada (11:1 ou mais). |
| `ceu-base` | `#FBF1D3` | `#151B18` | Cor de fundo do gradiente do Céu. No claro, a areia aquecida do amanhecer; no escuro, a estrada à noite. |
| `ceu-faixa` | `#FFD95C` | `#3E340E` | Brilho amarelo do Céu, no canto inferior direito. Derivado de faixa. |
| `ceu-placa` | `#C2E7D1` | `#123F2B` | Brilho verde do Céu na variante placa, no canto superior direito. Derivado de placa. ink e ink-muted passam por cima dele nos dois temas. |
| `ceu-claro` | `#FFE89A` | `#2A2A12` | Brilho de transição do Céu, no canto superior direito. |
| `ceu-azul` | `#C9E4F6` | `#13314A` | Azul do céu, no canto superior esquerdo do Céu. ink e ink-muted passam por cima dele nos dois temas (5,1:1 ou mais). |
| `ceu-sol` | `#FFCDA8` | `#4A2A14` | Laranja do pôr do sol, no canto inferior esquerdo do Céu, perto do horizonte. ink e ink-muted passam por cima dele nos dois temas (4,6:1 ou mais). |
| `vidro` | `rgba(255, 255, 255, 0.78)` | `rgba(27, 32, 30, 0.78)` | Fundo fosco (com blur de 12px) de chips e da tag de km sobre a foto, e da barra superior. Texto em ink: 6,9:1 ou mais sobre qualquer foto. |
| `halo-foco` | `rgba(242, 183, 5, 0.55)` | `rgba(242, 183, 5, 0.55)` | Anel de 4px em volta do campo com foco, junto com a borda ink. |
| `scrim` | `rgba(16, 20, 19, 0.82)` | `rgba(16, 20, 19, 0.82)` | Fim do degradê sobre a foto do card, para nome e nota ficarem legíveis em qualquer imagem. |
| `on-scrim` | `#FFFFFF` | `#FFFFFF` | Texto e ícones sobre a parte escura do degradê do card. |
| `perigo` | `#B23A16` | `#F08A63` | Só erros e ações destrutivas. Não é a cor do Passo: recusar um lugar não é erro. |
| `foco` | `#1B1F1D` | `#F2B705` | Contorno de foco de 2px com 2px de afastamento em todo controle que não é campo (14:1 no claro, 9:1 no escuro). |

### Tipografia

Famílias:

- `display`: `"Bricolage Grotesque", "Barlow", system-ui, sans-serif`
- `placa`: `"Barlow Condensed", "Arial Narrow", sans-serif`
- `sans`: `"Barlow", system-ui, sans-serif`

| Estilo | Família | Tamanho / linha | Peso | Letter-spacing | Exemplo | Uso |
| --- | --- | --- | --- | --- | --- | --- |
| `display-xl` | display | 40px / 40px | 700 | -0.035em | Escolha suas paradas | Título de tela, uma vez. Aceita uma palavra em Destaque. |
| `display-l` | display | 30px / 31px | 700 | -0.03em | Churrascaria Gaúcha | Nome do lugar no card de swipe, sobre o scrim. |
| `title` | display | 22px / 26px | 650 | -0.02em | Paradas no caminho | Título de seção e de folha. |
| `km` | placa | 18px / 20px | 600 | 0.02em | KM 512 | Marcos de quilometragem e horas de estrada, sempre em maiúsculas: "KM 512", "+6H". |
| `estrada` | placa | 20px / 20px | 700 | 0.14em | ALEGRETE · LAGES · CURITIBA | Nomes de cidade correndo na Estrada e carimbos do swipe. Maiúsculas. |
| `body` | sans | 16px / 24px | 400 | — | Mirante com vista para o vale, a 4 km da BR-116. | Texto corrido, descrição do lugar. |
| `body-strong` | sans | 16px / 24px | 600 | — | Lages, SC | Nome de cidade em listas e na linha do tempo. |
| `body-s` | sans | 14px / 20px | 400 | — | 4,7 · 1.834 avaliações | Metadados: nota, avaliações, horário, @ do Instagram. |
| `label` | sans | 13px / 16px | 600 | 0.04em | RESTAURANTE | Rótulo de chips e dos botões de swipe. Maiúsculas só em chips. |
| `button` | sans | 16px / 16px | 600 | — | Montar roteiro | Texto de Button e Segmented. |

### Espaço

| Token | Valor | Uso |
| --- | --- | --- |
| `space-1` | `4px` | Entre ícone e texto dentro de chips e da nota; padding do trilho do Segmented. |
| `space-2` | `8px` | Entre chips; entre linhas de metadado no card. |
| `space-3` | `12px` | Padding interno de chips e campos; entre itens da linha do tempo. |
| `space-4` | `16px` | Margem lateral das telas e padding dos cards. |
| `space-6` | `24px` | Entre seções de uma tela; padding lateral de botões. |
| `space-8` | `32px` | Topo de telas e respiro acima dos botões de swipe. |
| `touch` | `48px` | Altura mínima de qualquer alvo de toque. |
| `button-h` | `52px` | Altura dos botões principais em pílula. |

### Raios

| Token | Valor | Uso |
| --- | --- | --- |
| `radius-sm` | `10px` | Tag de km. |
| `radius-md` | `16px` | Campos, itens de lista, folhas. |
| `radius-lg` | `28px` | Card de swipe e blocos do Céu. |
| `radius-pill` | `999px` | Botões, chips, Segmented, Toast, botões redondos de swipe. |

### Sombras

| Token | Valor | Uso |
| --- | --- | --- |
| `shadow-1` | claro `0 1px 2px rgba(35, 41, 43, 0.06), 0 4px 12px -4px rgba(35, 41, 43, 0.12)`<br>escuro `0 1px 2px rgba(0, 0, 0, 0.3), 0 4px 12px -4px rgba(0, 0, 0, 0.5)` | Opção ativa do Segmented, chips selecionados. |
| `shadow-2` | claro `0 2px 4px rgba(35, 41, 43, 0.05), 0 22px 44px -18px rgba(35, 41, 43, 0.30)`<br>escuro `0 2px 4px rgba(0, 0, 0, 0.3), 0 22px 44px -18px rgba(0, 0, 0, 0.7)` | Botões redondos de swipe, Toast, folhas. |
| `shadow-card` | claro `0 40px 90px -36px rgba(35, 41, 43, 0.48)`<br>escuro `0 40px 90px -36px rgba(0, 0, 0, 0.8)` | Só o card de swipe que está no topo da pilha. |
| `shadow-favorito` | `inset 0 1px 0 rgba(255, 255, 255, 0.6), 0 8px 22px -10px rgba(201, 150, 0, 0.7)` | Brilho do botão Favorito. |
| `shadow-sheet` | claro `0 -4px 16px rgba(35, 41, 43, 0.10)`<br>escuro `0 -4px 16px rgba(0, 0, 0, 0.45)` | Barra de navegação e folhas que sobem da base. |

## Componentes

Implementação web de referência em `design-system/components/bundle.js` (React, `window.Desvio.*`) e `design-system/components/bundle.css` (classes `dv-*`). Cada componente tem um `preview.html` na sua pasta.

### BottomNav
Barra fixa no rodapé com as quatro áreas do app: Viagens, Descobrir, Roteiro e Perfil.

**O consumidor fornece:** `ativo` (a área atual) e `onChange`.

- Sempre os quatro itens, nessa ordem, com ícone e palavra.
- Item ativo em `placa` com a pílula `surface-300` atrás do ícone, e `aria-current="page"`.
- Some nas telas de criação de viagem e no swipe em tela cheia; volta ao sair delas.
- Respeita a área segura do iPhone (`safe-area-inset-bottom`).

### Button
Botão de ação para tudo que não é a decisão de swipe: criar viagem, montar roteiro, editar paradas.

**O consumidor fornece:** `children` (verbo no infinitivo, curto: "Montar roteiro", "Adicionar parada"), `onClick`, opcionalmente `icon`, `variant`, `size` e `block`.

- `primary` (fundo `placa`, texto `on-placa`): uma por tela, a ação que avança o fluxo.
- `secondary` (contorno `ink`): ações paralelas, como editar ou voltar ao swipe.
- `ghost` (texto `placa`): ações de baixo peso dentro de listas.
- `favorito` (fundo `faixa` com `shadow-favorito`): só para ações ligadas a favoritos.
- `block` no rodapé das telas de formulário, dentro da margem `space-4`.
- Pílula (`radius-pill`) com altura `button-h` (52px); `sm` só em linhas densas, nunca abaixo de 40px.

Não use Button para Bora, Passo ou Favorito: isso é `SwipeActions`.

### Ceu
Fundo de céu de fim de tarde, do azul ao laranja do pôr do sol, para o topo das telas de entrada e para lugares sem foto.

**O consumidor fornece:** o conteúdo (`children`), `variante` (`faixa`, o padrão, ou `placa`), `serra` para recortar a base, `fundoSerra` com a cor da superfície que vem logo abaixo, e `arredondado` quando o céu é um bloco dentro da tela.

- Quatro brilhos radiais sobre `ceu-base`: `ceu-azul` no alto à esquerda, `ceu-claro` (ou `ceu-placa`, na variante placa) no alto à direita, `ceu-sol` embaixo à esquerda e `ceu-faixa` (ou `ceu-claro`) embaixo à direita.
- Azul e laranja existem só aqui. Não use `ceu-azul` nem `ceu-sol` em botões, texto ou ícones.
- Use no topo de Boas-vindas, Entrar, Nova viagem, Carregando rota e Roteiro, e como fundo do SwipeCard sem foto. Uma vez por tela.
- Texto em `ink` e `ink-muted`; ambos passam por cima de qualquer ponto do gradiente, nos dois temas.
- Com `serra`, a base vira um perfil de morros que se encaixa na superfície seguinte. Passe em `fundoSerra` a cor dessa superfície.

### Chip
Rótulo de categoria do lugar; com `onClick` vira filtro liga/desliga.

**O consumidor fornece:** `categoria` (preenche rótulo e ícone) ou `label` + `icon`; para filtro, `selected` e `onClick`; `onPhoto` quando fica sobre a foto do card.

- As cinco categorias têm o mesmo visual. Quem diferencia é o ícone e a palavra, não a cor: não crie cores por categoria.
- Filtro selecionado inverte para fundo `ink` com texto `surface-100`, e expõe `aria-pressed`.
- Rótulo em `label` (maiúsculas, 13px). Uma palavra só.

### Destaque
Marca-texto amarelo, como tinta de faixa, atrás de uma palavra de título.

**O consumidor fornece:** a palavra, como `children`, dentro de um título em `display-xl` ou `title`.

- Uma palavra por tela, a que carrega a ação: "Escolha suas *paradas*", "Seu roteiro está *pronto*".
- Só em títulos. Nunca em texto corrido, botões ou para indicar link.
- No tema escuro vira um traço fino sob a palavra, para o texto claro continuar legível.

### Estrada
Pista curva com o nome das cidades da rota correndo por ela, a assinatura visual do Desvio.

**O consumidor fornece:** `cidades` na ordem da rota; opcionalmente `variante` (`curva` ou `subida`), `velocidade`, `parado` e `largura`.

- Lugar certo: a tela Carregando rota (enquanto os lugares são buscados) e o topo do Roteiro. No máximo uma Estrada por tela.
- A pista é `asfalto` com bordas `faixa`; o texto, em `estrada`, é `on-asfalto`.
- O texto corre sozinho e para quando o sistema pede menos movimento (`prefers-reduced-motion`) ou com `parado`.
- O SVG tem `aria-label` com a rota inteira; o texto em movimento é escondido do leitor de tela.
- Não coloque informação essencial só na Estrada: ela é ilustração. A lista de paradas está no StopItem.

### Icon
Conjunto de ícones de traço do Desvio, numa grade de 24px com traço 1.8.

**O consumidor fornece:** `name`, opcionalmente `size`, `filled` (só a estrela) e `label` quando o ícone carrega significado sozinho.

- O ícone herda a cor do texto ao redor (`currentColor`).
- Sem `label` ele é decorativo e fica oculto para leitor de tela; use `label` só quando não há palavra ao lado.
- Para o Instagram use `at` seguido do @: não reproduza o logotipo da marca.

### Rating
Nota do Google Maps com a contagem de avaliações, no formato brasileiro ("4,7 (1.834)").

**O consumidor fornece:** `nota` (0 a 5) e, quando houver, `avaliacoes`; `onPhoto` sobre o card.

- Sem nota (lugar só do OpenStreetMap), não renderiza nada. Não mostre "sem nota".
- Sempre mostre `avaliacoes` quando existir: 5,0 com 12 avaliações vale menos que 4,6 com 2 mil, e o usuário precisa ver isso.
- Estrela em `estrela`; número em `ink`, contagem em `ink-muted`.

### Segmented
Escolha entre duas a quatro opções exclusivas, sempre visíveis.

**O consumidor fornece:** `opcoes` (`valor`, `label`, `icon` opcional), `valor` + `onChange` (ou `padrao` para deixar o estado com o componente), `rotulo` para o leitor de tela e `block` para ocupar a largura.

- Uso principal: "Carro / Moto / Bicicleta" na criação da viagem.
- Mais de quatro opções: use Chips de filtro.
- A opção ativa sobe para `surface-200` com `shadow-1`; o trilho é `surface-300`.
- É um `radiogroup`: cada opção é um `radio` com `aria-checked`.

### StopItem
Uma linha da linha do tempo da viagem: km, cidade, horas de estrada e quantos lugares foram escolhidos ali.

**O consumidor fornece:** `cidade`, `uf`, `km`, `horas`, `tipo`, `aceitos` e `total`; `ativo` na parada que está sendo escolhida agora.

- Empilhe vários StopItem em sequência; o trilho se conecta sozinho.
- Origem e destino têm o ponto cheio em `placa`; a parada ativa usa `faixa`.
- "3 de 12" conta os cards aceitos sobre os mostrados. Toque na linha abre o swipe daquela parada.

### SwipeActions
Os três botões de decisão abaixo do card: Passo, Favorito e Bora.

**O consumidor fornece:** `onPasso`, `onFavorito`, `onBora`; `disabled` enquanto o próximo card carrega.

- A ordem é fixa: Passo à esquerda, Favorito no meio, Bora à direita, espelhando o gesto.
- Cada botão tem palavra e ícone. Bora (`placa`) e Passo (contorno `ink`) se distinguem por claridade, não só por matiz.
- Passo não é vermelho: recusar um lugar não é um erro. `perigo` fica para erros de verdade.
- Favorito (`faixa`) é menor de propósito: é a exceção, não o padrão.

### SwipeCard
O card de um lugar na tela de swipe: foto cheia, nome, cidade, nota, km na rota e Instagram.

**O consumidor fornece:** os campos do card que a API devolve (`nome`, `categoria`, `foto`, `cidade`, `uf`, `nota`, `avaliacoes`, `km`, `horas`, `descricao`, `instagram`), `instagramProvavel` quando `instagram_origem` for `"busca"`, e o gesto de arrastar. O componente não arrasta sozinho: o app move o card com `style.transform` e passa `stamp` conforme a direção.

- Arrastar para a direita mostra `stamp: "bora"`; para a esquerda, `"passo"`; para cima, `"favorito"`. A partir de ~30% da largura, o card sai e a decisão é registrada.
- Todo gesto tem botão equivalente em `SwipeActions` logo abaixo. Nunca dependa só do gesto.
- Sem `foto`, o card mostra o Céu com o ícone da categoria. Não use foto de banco de imagens no lugar.
- Chip de categoria e tag de km ficam sobre a foto em `vidro` fosco, para mostrar mais da imagem.
- `km` e `horas` sempre que houver rota. Sem eles, a tag some.
- O @ do Instagram abre em nova aba. Quando veio de busca, leva " · provável".
- Largura máxima 380px, proporção fixa; na tela, o card ocupa a largura menos `space-4` de cada lado.

### TextField
Campo de texto com rótulo, ícone opcional, dica e erro.

**O consumidor fornece:** `label` (sempre, em forma de pergunta: "De onde você sai?"), `value`/`onChange` ou `defaultValue`, `placeholder` com o formato esperado ("Cidade, UF"), `hint` e `erro`.

- O rótulo fica sempre visível acima do campo. O placeholder não substitui o rótulo.
- Borda `ink-muted` em repouso; com foco, borda `ink` e anel de 4px em `halo-foco`. `perigo` quando há `erro`, com a mensagem no lugar da dica.
- Mensagem de erro diz o que fazer ("Confira a grafia"), sem culpar o usuário.

### Toast
Confirmação curta que aparece na base da tela depois de uma ação, com desfazer opcional.

**O consumidor fornece:** a mensagem (`children`), `icon`, e `acao` + `onAcao` quando dá para desfazer.

- Depois de Bora e Favorito, mostre o Toast com "Desfazer" por 4 segundos. Depois de Passo, não: o swipe já é o retorno.
- Uma frase, sem ponto final, nomeando o lugar: "Churrascaria Gaúcha entrou no roteiro".
- Fica acima da BottomNav, centralizado, com `space-4` de margem. Um por vez; o novo substitui o anterior.
- Fundo `asfalto`, texto `on-asfalto`, ícone e ação em `faixa`. Tem `role="status"`.

## Tipos dos componentes

```ts
// Desvio — tipos dos componentes (documentação; window.Desvio.*)

export type Categoria = "turismo" | "restaurante" | "posto" | "natureza" | "hospedagem";
export type IconName =
  | "x" | "check" | "star" | "pin" | "camera" | "food" | "fuel" | "leaf" | "bed"
  | "route" | "compass" | "user" | "suitcase" | "clock" | "at" | "car";

export interface IconProps {
  name: IconName;
  /** px, padrão 20 */
  size?: number;
  filled?: boolean;
  strokeWidth?: number;
  /** Texto para leitor de tela; sem ele o ícone é decorativo. */
  label?: string;
  className?: string;
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = placa; secondary = contorno ink; ghost = só texto placa; favorito = faixa com brilho */
  variant?: "primary" | "secondary" | "ghost" | "favorito";
  size?: "md" | "sm";
  icon?: IconName;
  /** Ocupa a largura toda (CTAs no rodapé da tela). */
  block?: boolean;
  children?: React.ReactNode;
}

export interface ChipProps {
  /** Preenche rótulo e ícone a partir da categoria. */
  categoria?: Categoria;
  label?: string;
  icon?: IconName;
  /** Com onClick vira filtro (button + aria-pressed). */
  selected?: boolean;
  onClick?: () => void;
  /** Fundo sólido para ficar legível sobre a foto do card. */
  onPhoto?: boolean;
  children?: React.ReactNode;
}

export interface RatingProps {
  /** 0 a 5; formatado em pt-BR ("4,7"). Sem nota, não renderiza. */
  nota?: number | null;
  avaliacoes?: number | null;
  onPhoto?: boolean;
}

export interface SwipeCardProps {
  nome: string;
  categoria?: Categoria;
  foto?: string | null;
  cidade?: string;
  uf?: string;
  nota?: number | null;
  avaliacoes?: number | null;
  /** km na rota. */
  km?: number;
  /** horas desde a saída. */
  horas?: number;
  descricao?: string;
  /** URL ou @handle. */
  instagram?: string | null;
  /** true quando o @ veio de busca web (instagram_origem = "busca"). */
  instagramProvavel?: boolean;
  /** Carimbo exibido enquanto o card é arrastado. */
  stamp?: "bora" | "passo" | "favorito" | null;
  style?: React.CSSProperties;
  className?: string;
}

export interface SwipeActionsProps {
  onPasso?: () => void;
  onFavorito?: () => void;
  onBora?: () => void;
  disabled?: boolean;
}

export interface StopItemProps {
  cidade: string;
  uf?: string;
  km?: number;
  /** 0 = saída */
  horas?: number;
  tipo?: "origem" | "parada" | "destino";
  /** parada sendo escolhida agora */
  ativo?: boolean;
  aceitos?: number;
  total?: number;
}

export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: IconName;
  hint?: string;
  /** Mensagem de erro; troca a dica e pinta a borda de perigo. */
  erro?: string;
}

export interface BottomNavProps {
  ativo?: "viagens" | "descobrir" | "roteiro" | "perfil";
  onChange?: (id: "viagens" | "descobrir" | "roteiro" | "perfil") => void;
}

export interface DestaqueProps {
  /** Uma palavra (ou duas) do título. */
  children: React.ReactNode;
}

export interface CeuProps {
  /** "faixa" (amarelo no canto superior esquerdo, padrão) ou "placa" (verde no canto superior). */
  variante?: "faixa" | "placa";
  /** Recorta a base com o perfil de serra, na cor de fundoSerra. */
  serra?: boolean;
  /** Cor da serra, padrão var(--surface-100): a cor do que vem logo abaixo. */
  fundoSerra?: string;
  /** Cantos radius-lg, para usar como bloco dentro da tela. */
  arredondado?: boolean;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

export interface EstradaProps {
  /** Cidades da rota, na ordem. */
  cidades: string[];
  variante?: "curva" | "subida";
  /** px por segundo, padrão 36. */
  velocidade?: number;
  /** Congela o texto (também congela sozinho com prefers-reduced-motion). */
  parado?: boolean;
  /** Largura da pista em unidades do viewBox 400x200, padrão 46. */
  largura?: number;
  /** Texto para leitor de tela; padrão "Rota: cidade, cidade…". */
  rotulo?: string;
}

export interface SegmentedProps {
  opcoes: { valor: string; label: string; icon?: IconName }[];
  /** Controlado. Sem ele, o componente guarda o estado e começa em `padrao`. */
  valor?: string;
  padrao?: string;
  onChange?: (valor: string) => void;
  block?: boolean;
  /** Nome do grupo para leitor de tela. */
  rotulo?: string;
}

export interface ToastProps {
  children: React.ReactNode;
  icon?: IconName;
  /** Texto do botão, ex. "Desfazer". */
  acao?: string;
  onAcao?: () => void;
}
```

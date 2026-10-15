# JanelaCidade
Miniatura de cidade em formato de janelinha de avião, para escalas e destino no modo avião.

**O consumidor fornece:** `cidade`, `uf`, `dias`, `foto` (ou `variante` do céu quando não há foto), `selecionada` e `onClick`.

- Use numa fileira rolável horizontal com `space-3` entre as janelas, na ordem da viagem.
- Toque abre o swipe daquela cidade; a selecionada ganha a moldura em `faixa`.
- O formato é fixo: topo em `radius-pill`, base em `radius-arco`. Não use esse formato para outra coisa; ele significa "cidade do modo avião".
- No modo carro, use StopItem em vez da janela.

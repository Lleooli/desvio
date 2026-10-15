# StopItem
Uma linha da linha do tempo da viagem: km, cidade, horas de estrada e quantos lugares foram escolhidos ali.

**O consumidor fornece:** `cidade`, `uf`, `km`, `horas` (modo carro) ou `dias` (modo avião), `tipo`, `aceitos` e `total`; `ativo` na parada que está sendo escolhida agora.

- Empilhe vários StopItem em sequência; o trilho se conecta sozinho.
- Origem e destino têm o ponto cheio em `placa`; a parada ativa usa `faixa`.
- "3 de 12" conta os cards aceitos sobre os mostrados. Toque na linha abre o swipe daquela parada.
- No modo avião, omita `km` e `horas` e passe `dias`.

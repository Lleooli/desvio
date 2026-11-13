# Desvio

App de celular que monta viagens de carro ou de avião: sugere lugares em cada cidade da viagem, a pessoa decide com um gesto e recebe o roteiro ordenado.

Os identificadores do código são em português, como o domínio; a ponte abaixo só aparece quando o nome no código difere do termo.

## Linguagem

### Viagem e cidades

**Parada**:
Qualquer cidade da viagem onde o app sugere lugares; termo geral que engloba parada no caminho, destino e escala.
_Evitar_: cidade (é só o lugar geográfico, não o papel na viagem)

**Parada no caminho**:
Cidade escolhida a cada intervalo de km ao longo da rota de uma viagem de carro. No código, `tipo = "parada"`.

**Destino**:
A última parada de uma viagem de carro. No código, `tipo = "destino"`.

**Escala**:
Cidade de uma viagem de avião, com o número de dias que a pessoa passa nela. No código, `tipo = "estadia"`.
_Evitar_: estadia

### Lugares e decisões

**Lugar**:
Estabelecimento ou atração do mundo real (restaurante, mirante, posto), com id próprio da fonte (`gmaps:…` ou `osm:…`), reaproveitado entre viagens e entre pessoas.
_Evitar_: card (para falar do lugar em si)

**Card**:
A apresentação de um lugar dentro de uma parada, para a pessoa decidir: foto, nota, km na rota, Instagram.

**Decisão**:
O que a pessoa escolhe sobre um card: Bora, Passo ou Favorito.
_Evitar_: swipe (é só o gesto), gostou

**Bora**:
Decisão de incluir o lugar no roteiro.

**Passo**:
Decisão de descartar o lugar; ele não volta em nenhuma viagem.

**Favorito**:
Um Bora mais forte: o lugar entra no roteiro e pesa mais no perfil de gosto.

**Categoria**:
Grupo de lugares que a pessoa escolhe buscar: turismo, restaurante, posto, natureza, hospedagem.

### Gosto

**Triagem**:
Conversa curta, de no máximo cinco perguntas, que capta o jeito de viajar da pessoa antes da primeira viagem.

**Resumo da triagem**:
Texto em que a IA diz o que entendeu da triagem.

**Perfil de gosto**:
O que o app sabe do gosto da pessoa: o resumo da triagem somado às taxas de aceite das decisões por categoria, tipo e faixa de preço.
_Evitar_: perfil (sozinho, é a aba de conta)

### Resultado e processo

**Busca**:
O processo de montar as paradas e os cards de uma viagem, que a pessoa acompanha enquanto espera. No código, `coleta`, executada como `job`.
_Evitar_: coleta, job (termos técnicos)

**Ranqueamento**:
A ordem em que os cards de uma parada aparecem: primeiro pela estatística do perfil de gosto, depois ajustada pela IA.

**Roteiro**:
A sequência final dos lugares com Bora ou Favorito, ordenada e dividida por dia.

# Política de privacidade do Desvio

Versão de 13 de novembro de 2026. Rascunho para o beta fechado; antes do lançamento público, uma pessoa com conhecimento jurídico precisa revisar este texto.

O Desvio monta viagens por terra: você informa de onde sai e para onde vai, o app sugere lugares no caminho, você desliza **Bora** ou **Passo**, e a IA ordena o roteiro. Para isso, guardamos o mínimo possível sobre você. Esta página explica o que guardamos, por que guardamos, com quem compartilhamos e como você pede uma cópia ou apaga tudo, conforme a Lei Geral de Proteção de Dados (LGPD, Lei 13.709/2018).

## O que guardamos

| Dado | De onde vem | Para que serve |
| --- | --- | --- |
| Seu e-mail e o jeito que você entrou (Google, Apple ou link por e-mail) | Do login | Identificar sua conta e permitir que você entre de novo |
| Suas viagens: origem, destino, veículo, distância entre paradas, categorias, as cidades de parada e os lugares sugeridos | Do que você preenche ao criar a viagem | Mostrar suas viagens e retomar uma viagem antiga |
| Suas decisões: Bora, Passo ou Favorito em cada lugar, e quando você decidiu | Dos seus swipes | Não mostrar de novo o que você já viu e montar o roteiro |
| Seu perfil de gosto: quais categorias, tipos e faixas de preço você costuma aceitar, e o resumo do questionário de gosto | Calculado a partir das suas decisões; o resumo vem do questionário | Ordenar os próximos lugares pelo que você gosta |
| O roteiro de cada viagem | Montado pelo app, com ou sem IA | Mostrar a ordem das paradas |
| Sua preferência de tema (claro, escuro ou do sistema) | Do perfil | Mostrar o app do jeito que você escolheu |

As respostas do questionário de gosto passam pelo servidor só para a IA fazer a próxima pergunta; delas fica guardado apenas o resumo do gosto.

**O que não guardamos:** sua localização em segundo plano, seus contatos, suas fotos, seu nome completo, seu CPF ou qualquer dado de pagamento. O app não pede a sua localização para funcionar: você digita as cidades.

Os lugares (restaurantes, postos, pontos turísticos) e as rotas entre cidades não são dados seus. Eles vêm de fontes públicas, ficam num cache compartilhado entre todas as pessoas e não ficam ligados à sua conta.

## Com quem compartilhamos

Não vendemos seus dados e não usamos seus dados para publicidade.

**Supabase.** Guarda sua conta e o banco de dados do Desvio. É o nosso fornecedor de infraestrutura e trata os dados só em nosso nome.

**Groq (inteligência artificial).** O Desvio usa a Groq para três tarefas: fazer as perguntas do questionário de gosto, ordenar lugares pelo seu gosto e explicar a ordem do roteiro. A chave da Groq fica só no nosso servidor; o app nunca fala direto com ela. Para a Groq vão apenas:

- as respostas que você deu no questionário de gosto;
- um resumo do seu gosto em uma frase (por exemplo, "gosta de comida regional e mirantes");
- os dados públicos dos lugares: nome, categoria, tipo, nota, número de avaliações, uma descrição curta e o km na estrada;
- o contexto do roteiro: veículo, hora de saída e número de dias.

**Não vão para a Groq** o seu e-mail, o identificador da sua conta, o seu nome ou qualquer outro dado que identifique você. A Groq fica nos Estados Unidos, então essas informações saem do Brasil (transferência internacional, artigo 33 da LGPD). Se a Groq estiver fora do ar, o Desvio funciona sem IA e não manda nada para ela.

**Fontes de dados dos lugares e das rotas.** Para montar a viagem, o servidor do Desvio (nunca o seu celular) consulta serviços públicos com os nomes das cidades e as coordenadas da rota, sem nenhum dado da sua conta:

| Serviço | O que recebe | Para que |
| --- | --- | --- |
| Nominatim (OpenStreetMap) | O nome da cidade de origem e de destino | Achar a cidade no mapa |
| OSRM | As coordenadas de origem e destino | Calcular a rota por estrada |
| OpenStreetMap (Overpass) | Coordenadas no caminho | Achar cidades e lugares perto da estrada |
| Wikipedia | O artigo que o OpenStreetMap indica para o lugar | Trazer uma descrição e uma foto |
| Google Maps, e no lançamento a Google Places API | Uma busca como "restaurante em Santa Maria, RS" | Trazer nota, fotos, horários e preço |
| DuckDuckGo (ddgs) e o site do lugar | O nome do lugar e a cidade | Achar o Instagram do lugar |

O resultado dessas consultas fica no nosso cache por **30 dias** e depois é apagado. O cache guarda lugares e rotas, não guarda quem pediu.

## Por quanto tempo guardamos

- **Sua conta, suas viagens, decisões e perfil:** enquanto a sua conta existir. Quando você apaga a conta, eles somem na hora.
- **Cache de lugares e rotas:** 30 dias.
- **Fila de buscas** (o pedido de cada viagem enquanto ela é montada): apagada junto com a sua conta.

## Seus direitos

Pela LGPD, você pode, a qualquer momento:

- **saber o que guardamos e ter uma cópia (acesso e portabilidade).** No perfil do app, use "Exportar meus dados". Você recebe um arquivo JSON com a sua conta, o seu perfil de gosto, as suas viagens (com paradas, lugares e roteiro) e as suas decisões. Quem programa pode chamar `GET /eu/exportar`.
- **corrigir seus dados.** As viagens, decisões e o tema você muda no próprio app. Deslizar de novo um lugar troca a decisão.
- **apagar sua conta e seus dados.** No perfil do app, use "Apagar conta" e confirme. As suas viagens, decisões, perfil, roteiros e buscas são apagados na hora. A conta de login é apagada logo em seguida; se o serviço de login estiver fora do ar, tentamos de novo sozinhos, e a exclusão termina em **até 15 dias**. Depois disso, se você entrar de novo com o mesmo e-mail, o Desvio cria uma conta nova e vazia. Quem programa pode chamar `DELETE /eu` com `{"confirmar": "APAGAR"}`.
- **saber com quem compartilhamos.** A lista está acima.
- **reclamar na Autoridade Nacional de Proteção de Dados (ANPD)**, em [gov.br/anpd](https://www.gov.br/anpd).

A base legal para tratar seus dados é a execução do serviço que você pediu (artigo 7º, V, da LGPD): sem as cidades e as suas decisões, o app não consegue montar a viagem.

## Segurança

O app entra pelo Supabase Auth, e toda chamada ao nosso servidor leva um token que expira em até 1 hora. Cada pessoa só lê as próprias viagens e decisões, tanto pelo servidor quanto direto no banco (regras de acesso por linha). As chaves da Groq e do Supabase com acesso total ficam só no servidor.

## Contato

Para dúvidas sobre os seus dados ou para exercer os seus direitos fora do app, escreva para **[e-mail de contato a definir]**. Respondemos em até 15 dias.

Se esta política mudar, avisamos no app antes de a mudança valer.

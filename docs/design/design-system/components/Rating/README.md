# Rating
Nota do Google Maps com a contagem de avaliações, no formato brasileiro ("4,7 (1.834)").

**O consumidor fornece:** `nota` (0 a 5) e, quando houver, `avaliacoes`; `onPhoto` sobre o card.

- Sem nota (lugar só do OpenStreetMap), não renderiza nada. Não mostre "sem nota".
- Sempre mostre `avaliacoes` quando existir: 5,0 com 12 avaliações vale menos que 4,6 com 2 mil, e o usuário precisa ver isso.
- Estrela em `estrela`; número em `ink`, contagem em `ink-muted`.

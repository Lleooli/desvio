# BottomNav
Barra fixa no rodapé com as quatro áreas do app: Viagens, Descobrir, Roteiro e Perfil.

**O consumidor fornece:** `ativo` (a área atual) e `onChange`.

- Sempre os quatro itens, nessa ordem, com ícone e palavra.
- Item ativo em `placa` com a pílula `surface-300` atrás do ícone, e `aria-current="page"`.
- Some nas telas de criação de viagem e no swipe em tela cheia; volta ao sair delas.
- Respeita a área segura do iPhone (`safe-area-inset-bottom`).

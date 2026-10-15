# Referência de design

Cópia local dos artifacts de design do Claude, baixada em 2026-10-15. As versões vivas continuam nos links abaixo; se mudarem lá, baixe de novo.

| Pasta / arquivo | Origem | O que tem |
| --- | --- | --- |
| [`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md) | [Design system Desvio](https://claude.ai/artifact/4axmnGJWvKEXczHh3RP4uq) | Tudo num arquivo: brand book, tabelas de tokens (claro e escuro), guia de cada componente e tipos |
| [`design-system/`](design-system/) | mesmo | Arquivos originais: `README.md`, `tokens.json`, `components/<Nome>/README.md` e `preview.html`, `bundle.js`, `bundle.css`, `index.d.ts` |
| [`telas/`](telas/) | [Canvas de rotas](https://claude.ai/artifact/Y8YekNeBFE8R8nxLUVuPXQ) | Uma tela por rota, nos temas claro e escuro (`*.dc.html`), o mapa de rotas (`Main.dc.html`) e o índice do canvas (`canvas.json`) |

## Telas

| Rota | Claro | Escuro |
| --- | --- | --- |
| Mapa de rotas | [`Main.dc.html`](telas/Main.dc.html) | |
| `/boas-vindas` | [`BoasVindas.dc.html`](telas/BoasVindas.dc.html) | [`BoasVindasEscuro.dc.html`](telas/BoasVindasEscuro.dc.html) |
| `/entrar` | [`Entrar.dc.html`](telas/Entrar.dc.html) | [`EntrarEscuro.dc.html`](telas/EntrarEscuro.dc.html) |
| `/triagem` | [`Triagem.dc.html`](telas/Triagem.dc.html) | [`TriagemEscuro.dc.html`](telas/TriagemEscuro.dc.html) |
| `/viagens` | [`Viagens.dc.html`](telas/Viagens.dc.html) | [`ViagensEscuro.dc.html`](telas/ViagensEscuro.dc.html) |
| `/viagens/nova` | [`NovaViagem.dc.html`](telas/NovaViagem.dc.html) | [`NovaViagemEscuro.dc.html`](telas/NovaViagemEscuro.dc.html) |
| `/viagens/nova/escalas` | [`Escalas.dc.html`](telas/Escalas.dc.html) | [`EscalasEscuro.dc.html`](telas/EscalasEscuro.dc.html) |
| `/viagens/:id/carregando` | [`Carregando.dc.html`](telas/Carregando.dc.html) | [`CarregandoEscuro.dc.html`](telas/CarregandoEscuro.dc.html) |
| `/viagens/:id/paradas` | [`Paradas.dc.html`](telas/Paradas.dc.html) | [`ParadasEscuro.dc.html`](telas/ParadasEscuro.dc.html) |
| `/viagens/:id/paradas/:paradaId` | [`Swipe.dc.html`](telas/Swipe.dc.html) | [`SwipeEscuro.dc.html`](telas/SwipeEscuro.dc.html) |
| `/lugares/:lugarId` | [`Lugar.dc.html`](telas/Lugar.dc.html) | [`LugarEscuro.dc.html`](telas/LugarEscuro.dc.html) |
| `/viagens/:id/roteiro` | [`Roteiro.dc.html`](telas/Roteiro.dc.html) | [`RoteiroEscuro.dc.html`](telas/RoteiroEscuro.dc.html) |
| `/perfil` | [`Perfil.dc.html`](telas/Perfil.dc.html) | [`PerfilEscuro.dc.html`](telas/PerfilEscuro.dc.html) |

## Como ler as telas

- Cada `.dc.html` é o código-fonte de uma tela de 390×844. O layout está no HTML (estilos inline com `var(--token)`), os dados de exemplo e o estado no `<script type="text/x-dc">` do fim do arquivo.
- `<x-import component-from-global-scope="Desvio.X">` é o componente `X` do design system; veja o guia dele em `DESIGN-SYSTEM.md`.
- As telas escuras só importam a clara com `data-theme="dark"`; o layout de verdade está sempre na clara.
- Os arquivos dependem do runtime do canvas (`support.js`), então não abrem sozinhos no navegador. Para ver renderizado, use o link do canvas.
- `telas/ds/desvio/` é a cópia do design system que o canvas usa (igual a `design-system/`).

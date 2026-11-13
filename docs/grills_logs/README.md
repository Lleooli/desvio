# Logs de grill

Registro das sessões de perguntas e respostas que levaram a decisões neste repositório.

## Onde gravar

- Uma pasta por unidade do projeto: `coletor/` (services/coletor) e `mobile/` (apps/mobile). A pasta nasce com o primeiro grill da unidade.
- `transversal/` para o que toca mais de uma unidade ou é manutenção do repositório.
- `negocio/` para divulgação, usuários e propostas.

## Formato

- Logo abaixo do título, uma linha `Releases: vX.Y.Z, ...` lista as releases que entregaram o que o grill decidiu. Sem essa linha, a decisão ainda não saiu.
- Um log que já existe não é reescrito: uma sessão nova sobre o mesmo assunto entra como seção nova.

## O log não é fonte da verdade

Dentro de uma pasta, vale o log mais recente. O que vale hoje está no código, nos ADRs (`docs/adr/`) e no glossário (`CONTEXT.md`).

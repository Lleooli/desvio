# CLAUDE.md

@AGENTS.md

## Específico do Claude Code

- Para tarefas de várias etapas, use as skills do superpowers: `superpowers:brainstorming` antes de criar algo novo, `superpowers:writing-plans` para o plano (salve em `docs/superpowers/plans/`), `superpowers:test-driven-development` ao implementar e `superpowers:verification-before-completion` antes de dizer que terminou.
- Os planos já feitos ficam em `docs/superpowers/plans/`. Leia o mais recente antes de mexer na mesma área.
- Telas: o layout de referência está em `docs/design/telas/*.dc.html`, e o canvas vivo está no link de `docs/design/README.md`.
- Nunca adicione `Co-Authored-By` nos commits.

## Agent skills

### Issue tracker

Issues no GitHub (`Lleooli/desvio`), pelo `gh`. Veja `docs/agents/issue-tracker.md`.

### Triage labels

Nomes padrão (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). Veja `docs/agents/triage-labels.md`.

### Domain docs

Contexto único: `CONTEXT.md` e `docs/adr/` na raiz. Veja `docs/agents/domain.md`.

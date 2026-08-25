<!-- Title follows Conventional Commits: feat(chats): stream tool results as events -->

## What and why

<!-- The change in a sentence, and the reason it exists. Link the issue if there is one. -->

## How it was verified

<!-- Which tests cover it, and what you actually ran or clicked. "CI is green" alone is not an
     answer for anything user-facing. -->

## Checklist

- [ ] Imports still point downwards (see ARCHITECTURE.md); no package reaches upwards
- [ ] `ruff`, `mypy --strict` and the coverage gate pass locally
- [ ] New behaviour has a test; model behaviour is tested against `FakeProvider`, not a live model
- [ ] New tables carry a package-prefixed `__tablename__` and an Alembic revision in `apps/api`
- [ ] User-visible strings go through i18n; everything written is English
- [ ] Docs updated if the shape of the system changed; an ADR added if a decision was made

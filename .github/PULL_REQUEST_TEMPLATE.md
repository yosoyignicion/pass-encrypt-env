## Qué cambia
Describe el cambio en una frase. Enlaza el issue si procede (`Closes #`).

## Tipo
- [ ] `feat` · [ ] `fix` · [ ] `docs` · [ ] `refactor` · [ ] `test` · [ ] `chore`

## Checklist
- [ ] `./scripts/ci.sh` en verde (ruff + bandit + pytest)
- [ ] `./scripts/smoke.sh` OK
- [ ] `./scripts/secret-scan.sh` limpio
- [ ] Sin secretos, `vault.enc` ni datos personales en el diff
- [ ] `CHANGELOG.md` actualizado en `Unreleased` (si es visible)
- [ ] Un solo cambio lógico

## Notas para quien revisa
Riesgos, decisiones de diseño o puntos donde quieras feedback.

# CHECKPOINTS — Evaluación del estado final

Cinco checkpoints objetivos. El agente revisor los valida antes de cerrar cualquier sesión.

---

## C1 — Harness completo

- [ ] Existen: `AGENTS.md`, `harness/init.sh`, `harness/feature_list.json`, `harness/feature_list_archive.json`, `harness/progress/current.md`, `harness/progress/history.md`
- [ ] Existen: `harness/docs/architecture.md`, `harness/docs/data-models.md`, `harness/docs/conventions.md`, `harness/docs/verification.md`
- [ ] `CLAUDE.md` tiene 40.000 caracteres o menos (el detalle vive en `harness/docs/`)
- [ ] `./harness/init.sh` ejecuta sin errores

## C2 — Estado coherente

- [ ] Solo una feature en `in_progress` (o ninguna)
- [ ] `feature_list_archive.json` contiene solo `done`/`Cancelled`, sin ids duplicados con el activo (`init.sh` §3 lo valida)
- [ ] Las features `done` tienen tests que pasan
- [ ] `harness/progress/current.md` contiene solo la sesión activa (no acumulación de sesiones anteriores)

## C3 — Cumplimiento arquitectónico

- [ ] `core/` contiene solo los módulos documentados en `harness/docs/architecture.md`
- [ ] La UI (`ui/`) no contiene lógica de negocio
- [ ] No hay dependencias externas no documentadas en `requirements.txt`
- [ ] Sin código de debug (`print()` residuales, TODOs sin contexto)

## C4 — Verificación genuina

- [ ] Cada módulo de `core/` tiene al menos un test en `tests/`
- [ ] Los tests usan directorios temporales reales (no mocks del filesystem)
- [ ] `python -m pytest tests/` termina en verde

## C5 — Cierre de sesión correcto

- [ ] Sin archivos temporales sin rastrear en git
- [ ] La sesión está documentada en `harness/progress/history.md`
- [ ] Los estados de features en `harness/feature_list.json` reflejan el trabajo real completado
- [ ] `./harness/close.sh` ejecutado con éxito (commit automático realizado)

---

Un revisor valida cada checkpoint sistemáticamente. Si alguno falla, la sesión no se cierra.

# CLAUDE.md — Hera

Guidance for working in this repo. Hera is a **self-hostable AI chat web framework**:
FastAPI + Jinja + SQLite backend, HTMX + vanilla JS frontend, **no build step**. Models
are reached over an **OpenAI-compatible API** (Ollama, LM Studio, vLLM, llama.cpp, …).
UI language is German.

**System prompt = English, replies = user's language.** All model-facing instructions
(persona mind regions, output grammar, memory/section headers, dream/translate prompts, agent
tool-feedback, compacted-history block) are **English** — GPT-OSS follows English instructions
more reliably. The `language` sub-tag inside `<hera:persona>` ("Your user is communicating in
German or English", owner-set via the `language_preference` Setting — never the model) keeps
the German UX intact; only the instructions are English. Stored entries (global memory,
entities, skills, subconscious, memory examples) should also be English — a **maintenance
translate action** (`POST /memory/translate`) brings existing German entries over in place.
When editing any model-facing string, keep it English; UI-facing text (labels, buttons, card
messages) stays German. Behaviour-trait **labels** stay German (UI), their **prompt blocks**
are English.

## Run & test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main            # serves http://localhost:8000
```

There is **no pytest suite in the repo**. Verification scripts live in the session
scratchpad and drive the app in-process via `starlette.testclient.TestClient`
(the sandbox blocks `curl`, but Python httpx/urllib work). When changing behaviour,
mirror that style: spin up `create_app()`, hit routes, assert on HTML/DB. Keep every
existing check green. Always `python -m compileall -q src` first, plus `node --check`
on the JS files.

Tests set `HERA_DB_PATH`, `HERA_DATA_DIR`, `HERA_OBSIDIAN_DIR` to temp dirs for isolation.
Since auth landed, scripts also set `HERA_AUTH_PASSWORD` and **POST `/login` first**
(else every route 303s to the login page). To open an assistant stream, grab the id from
the pending shell's `data-stream-url` (both bubbles carry `data-message-id`). To exercise a
turn without a live model, monkeypatch `agent.build_chat_pipeline` (or `dream.generate`) to
yield scripted `Delta("content", …)` / `Delta("tool_call", …)` chunks. **TestClient gotcha:**
POST form data as a **dict** (list values for repeated fields) — a list of tuples silently
sends an empty body under the current httpx.

**Living suite** (scattered across session scratchpads; collect + run all): `verify_auth`,
`verify_smoke`, `verify_ui`, `verify_mobile`, `verify_pwa`, `verify_ws1/3/4/5/7/8` (model
profiles / native tools+writes / self-improvement; `verify_ws2` is a superseded no-op),
`verify_trace_memory` (trace + retrieval + budget), `verify_phase2` (message actions /
search / export / backup), `verify_fixes` (role alternation · trace-leak · free
interleaving), `verify_dream` (Träumen), `verify_emotions` (open EMOTION vocabulary e2e),
`verify_screens` (provider on Modelle screen · math assets), `verify_subconscious`
(skill/unterbewusst split · dream buckets), and the v0.1-stabilization round:
`verify_memory2` (embeddings · dedup · caps · hits · age hints · epistemics · merge cards),
`verify_profiles` (Verhaltensprofile e2e incl. persona migration), `verify_ux` (auto-title ·
stream cancel · retry · context settings), `verify_deploy` (healthz · friendly errors ·
provider test · install script), `verify_english` (EN-Prompt · Hygiene · Translate +
fail-safe) und `verify_evolution` (Persona-Stammbaum: Generationen · accept/reject ·
Gegenbeispiele im nächsten Traum) und `verify_dream3` (force_persona · Mehrfachlauf-Dedup ·
Git-Revert · Strategie-Merge · EMOTION joke), `verify_training` (Upload · Traum-Einspeisung ·
Toggle · Upsert · Guardrails · Delete) und `verify_workflow` (Workflow-Track: [workflow]-Parse ·
eigener HOW-YOU-WORK-Block · track-unabhängiges accept/revert) und `verify_projects` (Projekte-Tier:
Ordner-Zuweisung · aktiv-voll-vs-kurz-Injektion · Tasks · Traum-[project]/[compact] · Lineage-
Accept-Buttons), und die v0.3.0-Runde (Promptstruktur + Hera-Profil): `verify_prompt_restructure`
(XML-Tag-Assembly · Override/Re-Attach je Tag · Budget-/User-Preferences-Tag · e2e via
build_chat_messages), `verify_memory_unify` (Legacy-DB-Migration in MemoryObject · ProjectTask-
Remap · Tabellen-Rename · Idempotenz · alle Kind-Wrapper · Cosine-Merge-Pfad für Strategien) und
`verify_hera_profile_ui` (neuer Screen · Träumen-Screen-Schrumpfung · Einstellungen ohne
Verhaltensprofile/Trainingsdaten · voller Live-Chat-Turn mit getaggtem Prompt + injizierter
Memory), und die v0.3.0-Teil-4-Runde (Mind-Region-Registry + Hera-Profil-Dropdown):
`verify_phase2_prompt` (verschachtelte `<hera:persona>`-Assembly · Override-Bundle ersetzt
Persona+Grammar, safety/dev_msg überleben immer · owner-edit sofort im Prompt sichtbar),
`verify_phase3_dream` (generische `[tag]`-Block-Erkennung für alle 9 träum-mutierbaren
Regionen · mem_ex als MindObject-Kind · force_regions · **Sicherheitsfix**: `dream_accept`
prüft `dream_editable` hart statt nur Registry-Zugehörigkeit), `verify_persona_migration`
(persona.md→character.md, volle zurückdatierte Historie, Idempotenz, persona.md bleibt
unangetastet), `verify_phase4_ui` (manuelle Owner-Edit-Route für jede Region ·
`language_preference`-Setting · Dropdown-Trigger auf dem Träumen-Screen),
`verify_profile_consolidation` (22-Einträge-Dropdown · Dispatcher pro section_id · Save/
Revert landen direkt im selben Panel, kein OOB mehr) und `verify_full_lifecycle`
(Migration → Traum mit mehreren Regionen → accept/reject/revert → Owner-Edit → kompletter
Chat-Turn, alles im finalen Prompt sichtbar), und die Audit-Runde nach dem 2026-07-Refactor:
`verify_refactor_audit` (Träumen-Karte auf dem Hera-Profil statt eigenem Screen ·
Skills-(Import)-Sektion + CRUD · `<skill_library>` im Prompt · `import_skills`-Tool inkl.
Positional-Arg-Fallback · Live-Turn mit Skill-Import · Mind-Region-Textarea ·
parse_candidates-Cap · mem_ex-Labels · safety-Accept-Sperre · Traum-Log: Panel-OOB auf
/profile und /dream/run, Input-Chips inkl. Trainingsdaten, Gedanken/Roh-Ausgabe,
Fehler-Pass, Prune auf 30, Clear, Live-Persist pro Pass + Polling-Attribute,
Zahlenfeld-Durchläufe, `?v=`-Cache-Buster · Dubletten: text_overlap/Containment,
Hygiene-Fund ohne Embeddings, KNOWN_COVERAGE-Drop, Fuzzy-Collapse über Pässe). **Achtung:** die
Granularisierung (c46629d) hat die alten Modulpfade der Suite gebrochen
(`src.core.llm`/`src.core.db`/`src.core.repository`); geportete Kopien der Teil-4-Skripte
plus `verify_namespaces`/`verify_fixes`/`verify_trace_memory` liegen im Scratchpad der
Audit-Session und laufen grün — beim Portieren alter Skripte die neuen Pfade
(`src.backend.*`, `src.core.ctx.*`, `src.core.hera.*`, `src.core.tools.*`) einsetzen.
The 8 pre-auth scripts (`verify`, `verify_stream`, `verify_agent`, `verify_features`,
`verify_new`, `verify_projects`, `verify_vault`, `verify_vault2`) predate auth and no
longer run; `verify_dream` (alte String-API von parse_candidates) ist durch
`verify_phase3_dream` ersetzt.

## Home directory: `~/.hera/`

Everything Hera owns lives under `~/.hera/` (created on boot): `hera.db`, `config.env`
(user-editable boot defaults), `obsidian/` (vault root), and `mind/` (a git repo — every
named **mind region** Hera consists of, one file per region — see `src/core/mind.py`,
`src/core/ctx/mind_regions.py`, and *Prompt structure: mind regions* below). Boot config
precedence:
`Settings` defaults → `.env` → `~/.hera/config.env` → **DB `Setting` table** (in-app
*Einstellungen*, wins at runtime). See `src/config/settings.py` and
`repository.get_runtime_config()` / `RuntimeConfig`.

## Architecture

```
src/config/settings.py     pydantic-settings boot config (HERA_ prefix)
src/backend/                the DB layer, split out from core/ in the 2026-07 refactor: ORM
                           models, repository (all CRUD + migrations), session handling,
                           single-user auth. One-way dependency backend→core only
                           (backend/models.py reads `MindObject.content` through `core/mind.py`,
                           since that content is git-backed, not a DB column) — core/ has zero
                           dependency back on backend/
  db.py                    SQLAlchemy engine (SQLite WAL, autoflush=False), session_scope()
  models.py                ORM: Project(+behavior_profile_id)·Chat·Message(+trace)·Note·
                           MerkzettelEntry·MemoryObject (die vereinheitlichte Hera-Profil-
                           Erinnerung: `kind` ∈ gedaechtnis|person|ort|projekt, löst GlobalMemory/
                           Entity/TrackedProject ab)·MindObject (Sidecar-Metadaten für
                           git-versionierte Skills/Unterbewusstsein/Gedächtnis-Beispiele —
                           `kind ∈ skill|unterbewusst|mem_ex`, `repository.MIND_OBJECT_KINDS` ist
                           die SPOT-Liste; `content` ist eine Property, die aus `mind/{skills|
                           subconscious|mem_examples}/{id}.md` liest, nie eine Spalte;
                           `relpath()`s Ordner-Zuordnung ist ein Dict, kein if/else, damit ein
                           4. Kind sich anschließt ohne Codeänderung)·MindRejection (verworfene
                           Traum-Vorschläge für jede der 15 Mind-Regionen — `src/core/ctx/
                           mind_regions.py` — plus skill/unterbewusst/mem_ex, nie committed;
                           `region`-Spalte `String(32)` für die längeren Region-Ids)·Media·
                           Setting·ModelProfile·BehaviorProfile·TrainingDoc (externes
                           Traum-Material)·SkillDoc (importierbare Skill-Pakete, s.
                           *Import-Skills*)·DreamRun (Traum-Log: ein geloggter
                           Träumen-Durchlauf — input/system/thinking/output, gekappt auf
                           `repository.DREAM_LOG_KEEP` 30)·ProjectTask (Kinder von MemoryObject kind="projekt")
                           — MemoryObject + MindObject + MerkzettelEntry tragen eine
                           `embedding`-BLOB-Spalte (packed float32). `PromptVariant`
                           (Persona-Stammbaum in der DB) ist seit v0.3.0 vollständig entfernt —
                           abgelöst durch `src/core/mind.py`; das alte 2-Regionen-Duopol
                           (persona.md/workflow.md) ist seit Teil 4 selbst abgelöst durch die
                           15-Regionen-Registry, s. u.
  auth.py                  single-user auth: PBKDF2 hash + HMAC-signed session cookie
  repository.py            ALL CRUD + init_db()/_migrate_columns()/_migrate_legacy_memory_to_
                           unified() (einmalige GlobalMemory/Entity/Strategy/TrackedProject →
                           MemoryObject-Kopie) + _migrate_mind_to_git() (einmalig, Raw-SQL-Read
                           von `prompt_variants` — genau deshalb, damit die ORM-Klasse komplett
                           gelöscht werden konnte statt nur "renamed/unused" liegenzubleiben —
                           repliziert echte Historie als rückdatierte Commits/MindRejection-
                           Zeilen; migriert MemoryObject(kind=skill/unterbewusst) zu
                           MindObject+Datei) + _migrate_persona_regions() (einmalig, Teil 4:
                           spielt `mind.log("persona.md")` komplett zurückdatiert nach
                           `character.md` zurück — jeder alte Commit wird per `mind.show` gelesen
                           und per `write_and_commit(when=)` neu committet, sodass
                           `mind_generation("character")` die echte alte Generation weiterträgt
                           statt bei 1 neu zu beginnen; `role.md`/`tone.md` starten frisch aus den
                           Registry-Defaults; `persona.md` bleibt unverändert liegen, wird nur
                           nicht mehr gelesen — kein Rename nötig) — alle drei Migrationen
                           marker-guarded, benennen/lassen Alt-Zustand liegen statt zu droppen)
                           + RuntimeConfig.persona (jetzt die Konkatenation von
                           `read_mind_region("about_you"/"role"/"character"/"tone")` — flach,
                           nur für `hera/dream/dream.py`s Selbst-Framing beim Träumen; der
                           eigentliche Chat-Prompt liest die vier Regionen EINZELN direkt in
                           `ctx/prompts.py`, siehe dort) + auth/profile + vereinheitlichte
                           Memory-CRUD (add/list/update/delete/merge/compact_memory_object(s),
                           normalize_text + Cosine-Dedup ≥0.90) + git-hinterlegte Strategy-CRUD
                           (add/list/toggle/delete/merge_strategies — jetzt auch
                           `add_strategy(embedding=)` für Cosine-Dedup, vorher hart auf `None`,
                           s. *Self-improvement*) + `MIND_OBJECT_KINDS =
                           ("skill","unterbewusst","mem_ex")` als SPOT für jede Stelle, die
                           früher `("skill","unterbewusst")` hart kodierte +
                           `read_mind_region(id)`/`edit_mind_region(session,id,content)`
                           (Owner-Edit-Schreibpfad, git-hinterlegt wie `accept_mind_region`, nur
                           anderer Caller/Commit-Message — funktioniert für JEDE Region,
                           dream-editierbar oder fest) + `mind_generation`/list_mind_rejections/
                           add_mind_rejection/accept_mind_region/revert_mind_region (generalisiert
                           über `mind_regions.MIND_REGIONS`, nicht mehr ein 2-Einträge-Dict) +
                           get_language_preference/set_language_preference (reines Setting,
                           NIE vom Modell/Träumen berührt) — jeder historische Funktionsname
                           (add_global_memory, add_entity, add_strategy, add_tracked_project, …)
                           ist ein dünner Wrapper darüber + increment_hits +
                           Verhaltensprofil-CRUD + search_messages() + estimate_tokens() +
                           Embedding-Wartung (rows_missing/wipe/backfill)
src/core/                   pure LLM/prompt/tool/mind logic — no ORM, no repository (das ist
                           `src/backend/`, s. o.). Importiert `src.backend.repository` nur für
                           `RuntimeConfig` (Typ-Hinweis, keine DB-Zugriffe direkt in core/)
  client.py                async httpx streaming of /v1/chat/completions (freundliche deutsche
                           Fehlertexte für ConnectError/Timeout — verweisen auf Modelle-Screen)
  mind.py                  Hera's git-backed "Gehirn" — jede Mind-Region (Identität, Rolle,
                           Charakter, Ton, Sicherheit, Antwortformat, Gedächtnis-/Emotion-/
                           Werkzeug-Rahmen und -Nutzung, Entwickler-Nachricht, Nutzer-Präferenzen,
                           Arbeitsweise — Registry in `src/core/ctx/mind_regions.py`) als eigene
                           `{id}.md` unter `~/.hera/mind/`, plus `skills/{id}.md`/
                           `subconscious/{id}.md`/`mem_examples/{id}.md`, versioniert mit der
                           System-`git`-CLI (kein GitPython, Präzedenz: install-macos.sh ruft
                           git schon per Subprocess). `ensure_repo()` setzt zusätzlich lokal
                           `commit.gpgsign=false` (verhindert, dass ein globaler gpgsign=true
                           jeden automatisierten Commit still scheitern lässt — write_and_commit
                           hätte dann die Datei geschrieben, aber nie committet)/`read_text()`
                           (reiner Dateisystem-Read, KEIN Git-Aufruf — Hot-Path für jeden
                           Chat-Turn)/`write_and_commit(relpath, content, message, when=)`
                           (No-Op bei identischem Inhalt, `when` setzt GIT_AUTHOR_DATE/
                           GIT_COMMITTER_DATE fürs Rückdatieren)/`delete_and_commit()`/
                           `revert_file()` (liest alten Inhalt via `git show <sha>:<path>`,
                           committet ihn neu — NIE `git reset`/`checkout <sha>`, bleibt
                           vorwärtsgerichtet)/`log()`/`show(relpath, sha)` (validiert `sha` gegen
                           ein Hex-Regex, BEVOR es in den Subprocess-argv landet — `sha` kommt aus
                           einem Formularfeld, `--textconv`-artige Werte dürfen nicht als
                           git-Flag geparst werden). Alle Mutationen laufen hinter einem
                           `threading.RLock()` (Git-Index ist unter Nebenläufigkeit nicht sicher;
                           genügt für eine Single-Instance/Single-User-App). "Never raise"-Vertrag
                           wie `pipeline/embeddings.py`
  context.py               build_chat_messages(): system prompt + TRACE-compacted history +
                           relevanz-gefiltertes Memory (6 `_select_relevant`-Aufrufe: Merkzettel ·
                           gedaechtnis · entities — alle MemoryObject — · skill · unterbewusst ·
                           mem_ex — alle drei MindObject, Inhalt via Property aus Git; Cosine bei
                           Embeddings, sonst Keyword; eigener Cap pro Ebene inkl.
                           `MEM_EXAMPLE_TOKEN_CAP` 800, bewusst NICHT zu einem gemeinsamen Budget
                           zusammengelegt) + Alters-Hinweise + Verhaltensprofil + @mention inject
                           + `language_preference` (Setting → `build_system_prompt`). increment_hits
                           (MemoryObject) und increment_mind_hits (MindObject, nie Git — jetzt
                           auch für mem_ex) sind getrennte Aufrufe. _append_alternating() enforces
                           strict alternation.
  vault.py                 Obsidian vault access (read/search/write/complete) — SANDBOXED
  ctx/
    mind_regions.py        SPOT-Registry für jede Mind-Region (Teil 4) — `MindRegion` Dataclass
                           (`id · file · dream_editable · label · default · dream_tag ·
                           min_chars`) + `MIND_REGIONS: dict[id, MindRegion]` (15 Einträge) +
                           `DREAM_EDITABLE_REGIONS` (die 9 träum-mutierbaren) + `OVERRIDE_BUNDLE`
                           (die 5, die ein `prompt_override` gemeinsam ersetzt) +
                           `LANGUAGE_DEFAULT`. Reines Blattmodul (keine Imports von
                           repository/mind), importiert von `ctx/prompts.py`/`hera/dream/
                           dream.py`/`backend/repository.py`/`routes/hera/dream/*.py`/
                           `routes/hera/profile/*.py`. Drei Governance-Stufen, gleicher
                           Speichermechanismus für alle (`mind.write_and_commit`), nur der
                           Caller unterscheidet sich: **träum-mutierbar** (`dream_editable=True`,
                           hat einen `dream_tag`) —
                           `role`/`character`/`tone`/`workflow`/`mem_instr`/`emo_usage`/
                           `tool_usage`/`user_prefs` (je ein Textblob) + `mem_ex` (KEIN
                           MindRegion-Eintrag, sondern ein dritter `MindObject.kind` — viele
                           kleine Einträge statt ein wachsender Blob, s. *Self-improvement*);
                           **owner-fest** (`dream_editable=False`, kein `dream_tag` — das Modell
                           bekommt nie eine `[tag]`-Anleitung dafür, UND
                           `routes/hera/dream/accept.py`s `dream_accept` prüft
                           `region.dream_editable` hart, BEVOR es `accept_mind_region` aufruft —
                           sonst könnte ein rohes `POST /dream/accept kind=safety` die Sperre
                           umgehen) — `about_you`/
                           `grammar`/`safety`/`mem_overview`/`emo_vocab`/`tools_avail`/`dev_msg`,
                           aber jederzeit über die Hera-Profil-UI direkt editierbar (genau der
                           Mechanismus, mit dem eine neue Sicherheitsregel als Text-Edit statt
                           Codeänderung reinkommt); **Nutzer-Einstellung** — `language_preference`
                           lebt NICHT in dieser Registry, sondern als reines `Setting` (nie vom
                           Modell/Träumen berührt, s. `repository.get/set_language_preference`)
    prompts.py             Liest jede Mind-Region direkt über `mind.read_text(region.file) or
                           region.default` (`_region_text()`) statt über Parameter — reines
                           Blattmodul, importiert `mind`+`mind_regions` selbst. `BASE_PERSONA`/
                           `HERA_CONTRACT` (die alten Monolith-Konstanten) sind komplett entfernt,
                           ihr Inhalt lebt jetzt als `default`-Text einzelner Regionen in
                           `mind_regions.py`. build_system_prompt() assembliert den Prompt als
                           Sequenz XML-getaggter Sections via `_wrap(tag, body)` +
                           `_build_persona_block()` (baut `<hera:persona>` verschachtelt:
                           `<about_you>/<your_role>/<character>/<language>/
                           <tone_and_formatting>` + `<output_grammar>` — DAS ist der EINE Block,
                           den ein `prompt_override` wholesale ersetzt, `native_tools`-Profile
                           brauchen eine andere Grammatik als Persona+Grammar zusammen; safety/
                           dev_msg/alles andere ist NIE im Override-Bündel) + `<hera:capabilities>`
                           (re-attach, nur wenn Override aktiv) + `<hera:safety>` (immer
                           re-attached) + `<hera:behavior_profile>`/`<hera:approach>` +
                           `<budget:token_budget>` (documentation-only) +
                           `<context:now/vaults/user_notes>` + `<memory:memory_system>`
                           (verschachtelt `<memory_overview>`/`<memory_application_instructions>`/
                           `<memory_application_examples>` — Letzteres aus `mem_ex`-Zeilen, nur
                           wenn überhaupt Memory-Content vorliegt, wie die alte
                           `<memory:epistemics>`-Bedingung) + `<memory:global_memory/
                           known_people_places/tracked_projects/chat_notes/strategies>` +
                           `<emotions:emotions>` (`<available_emotions>` + `<emotion_usage>`) +
                           `<tools:tools>` (`<available_tools>` fest + `<currently_enabled>`
                           — die alte gated `_namespaced_actions()`, bewusst NICHT Teil der
                           Registry, damit ein Traum-Text/Owner-Edit nie ein nicht verdrahtetes
                           Tool behauptet — + `<tool_usage>`) + `<developer:developer_message>` +
                           `<user:user_preferences>` (feste `profile_name`-Zeile + mutabler
                           `user_prefs`-Body, erscheint wenn EINES von beiden nicht leer ist).
                           Nur die TEXT-Struktur geändert, nicht die CALL/EMOTION-Parsing-Grammatik
                           (calls.py/stream.js unangetastet)
  pipeline/
    pipeline.py            step chain (chat = 1 step)
    embeddings.py          /v1/embeddings über denselben Endpoint: pack/unpack/cosine +
                           embed (async) / embed_sync (Threadpool-Routen) — raisen NIE,
                           None ⇒ Keyword-Fallback
  tools/
    calls.py               namespaced parser (canonical_verb) + Segment + harmony norm +
                           split_trailing_trace()
    tools.py               SPOT registry: tools (websearch/vault_search/vault_read/
                           import_skills — Letzteres lädt SkillDoc-Pakete on demand, s.
                           *Import-Skills*) + write-actions (vault_write/remember/improve) +
                           silent trace + native schemas
  hera/
    agent.py               Plan→Execute→Eval loop (run_agent async generator)
    dream/
      dream.py              Träumen: reflection prompt (läuft IN der aktuellen Persona, EN) +
                           generate() + parse_candidates() → TYPISIERTE Kandidaten. `kind` ist
                           entweder ein Memory-Item-Bucket (gedaechtnis|herangehensweise|
                           unterbewusst|mem_ex|person|ort|projekt|wunsch) ODER eine
                           Mind-Region-Id aus der Registry (role|character|tone|workflow|
                           mem_instr|emo_usage|tool_usage|user_prefs) — `_REGION_BLOCK_RE` baut
                           EIN `[tag]…[/tag]`-Regex pro `DREAM_EDITABLE_REGIONS`-Eintrag
                           (ersetzt die alten hart kodierten `_PERSONA_BLOCK_RE`/
                           `_WORKFLOW_BLOCK_RE`), `_dream_system(force_regions)` baut die
                           Regionen-Anleitung + `_force_block()` aus derselben Registry
                           (ersetzt `_FORCE_PERSONA`) — "persona" als Kind/Tag existiert nicht
                           mehr, `_KIND_TAG` mappt keinen `persona`-Alias mehr. OR:-Varianten
                           unverändert + find_merge_pairs()/find_strategy_merge_pairs() (läuft
                           jetzt über `repository.MIND_OBJECT_KINDS`, inkl. mem_ex) +
                           find_weak_strategies() (deterministisch, kein LLM, laufen unverändert
                           gegen MindObject dank dessen `.content`-Property) + translate_texts()
                           (EN-Wartung, batched + fail-safe) + `_format_lineage()` (iteriert
                           `DREAM_EDITABLE_REGIONS` — jede zeigt eine echte Generation via
                           `mind.log()`-Länge — plus skill/unterbewusst/mem_ex nur mit
                           MindRejection-Gegenbeispielen) + _format_training()/_format_projects().
                           `render_mind_region_panel()` selbst lebt NICHT hier, sondern in der
                           Routen-Schicht (`routes/hera/dream/_shared.py`, ersetzt das alte
                           `lineage_regions`/`render_lineage` "alle auf einmal" — rendert GENAU
                           eine Region fürs Hera-Profil-Dropdown)
src/www/
  app.py                   FastAPI factory + auth middleware (require_login) — ~42 Leaf-Router
                           einzeln importiert und `include_router()`-registriert (bewusst NICHT
                           pro Paket aggregiert, damit app.py selbst die vollständige Landkarte
                           jeder existierenden Route ist)
  view.py                  workspace_context() — the 4-column render context
  routes/                  eine Datei pro Route, in Paketen nach Feature gruppiert (granularer
                           Split, 2026-07-Refactor) — nur Bereiche ohne eigenen Split bleiben
                           flache Einzeldateien: `vault.py`, `pwa.py`, `settings.py`, `models.py`
                           (Modell-Profile + Provider-Settings), `profiles.py`
                           (Verhaltensprofile), `strategies.py`, `training.py`. `_shared.py`
                           bündelt die Notizen-/Merkzettel-/Nachrichtentext-Helper, die von
                           `chats/`, `messages/` UND `notes/` gebraucht werden. Pakete:
                           `auth/` (Login/Logout) · `api/` (health, + JSON:
                           `chats/context.py`, `models/models.py`, `vault/files.py`) ·
                           `utils/` (search, backup) · `projects/` (Chat-*Ordner*-CRUD:
                           open/create/edit/update/delete — NICHT zu verwechseln mit den
                           "verfolgten Projekten" aus dem Gedächtnis, die unter
                           `hera/profile/memory/projects.py` liegen) · `chats/`
                           (Chat-Lebenszyklus + der eigentliche Nachrichten-Turn:
                           open/create/rename/delete/message/stream/context_meter/export/
                           merkzettel/notes/autotitle, eigenes `_shared.py` für
                           `_sse`/`_persist_turn`/`_persist_aborted`/`DEFAULT_CHAT_TITLES`,
                           geteilt zwischen dem normalen Done-Pfad und dem Abort-Pfad) ·
                           `messages/` (message-delete/remember/retry) · `notes/`
                           (note-delete) · `hera/` — alles, was Hera als Selbst ausmacht:
                           `hera/dream/` (Träumen-POST-Endpunkte: run/accept/reject/merge/
                           revert/log — der Trigger + `#dream-results` leben seit der
                           Audit-Runde als Karte auf dem Hera-Profil-Screen, `screen.py`/
                           `dream_screen.html` sind gelöscht; `log.py` = `POST
                           /dream/log/clear` fürs Traum-Log; eigenes `_shared.py` für
                           `render_mind_region_panel`/`render_dream_log_panel`+
                           `dream_input_chips`/
                           `_embed_one`/`_diff_html`/`_backfill_embeddings`/
                           `_drop_semantic_dupes`/`_dedupe_candidates` — der EINE Ort, den
                           sowohl `dream/` als auch `profile/` importieren, damit keines der
                           beiden Pakete das andere importieren muss) und `hera/profile/`
                           (Hera-Profil-Screen: `screen.py` — `profile_sections()` +
                           `GET /profile/section?section_id=` als Dispatcher,
                           `render_profile_section()` routet zu `render_mind_region_panel`
                           (15 Mind-Regionen) oder wiederverwendet unverändert
                           `render_global_memory`/`render_entities`/`render_projects`
                           (jetzt in `hera/profile/memory/{global_memory,entities,
                           projects}.py`) /`strategies.render_strategies`/
                           `profiles.render_profiles` — jede dieser Ziel-Partials trägt schon
                           eine eigene, in sich geschlossene Wurzel-ID, braucht also KEINE
                           Template-Änderung; `GET /profile` rendert den ersten Bereich
                           serverseitig vor, kein Leerzustand — plus `mind.py`
                           (`POST /profile/mind/{region_id}`, der manuelle Owner-Edit,
                           git-hinterlegt wie ein Dream-Accept, nur anderer Caller) +
                           `memory/{global_memory,entities,projects}.py` (CRUD) +
                           `skills.py` (Import-Skills: `/skills/{add,toggle,delete}`,
                           Dropdown-Bereich „Skills (Import)", `#skill-docs`) +
                           `maintenance/{hygiene,translate}.py` — Trainingsdaten und die
                           Träumen-Karte (samt `#dream-results`) sind eigene, immer sichtbare
                           Karten auf diesem Screen)
  templating.py            shared Jinja env + `model_label` global (id→ModelProfile.name over the bubble)
  templates/               base + index + login + partials/ + fragments/
  static/{css,js}          hera.css, stream.js, autocomplete.js, app.js, md.js, htmx.min.js, sw.js
  static/                  manifest.webmanifest + icons/ (PWA)
deploy/                    com.hera.server.plist + install-macos.sh (launchd) + desktop-wrapper/
```

Layout is a 4-column grid: **rail** (projects + Hera-Profil + Modelle + Einstellungen +
Profil/Logout — Träumen hat keinen eigenen Rail-Eintrag/Screen mehr, es ist eine Karte auf
dem Hera-Profil) · **chatlist** (with cross-chat search box) · **chat** (header carries the
context-budget meter + vault-export button) · **panels** (Notizen + KI-Merkzettel, the
latter split into a **global** and a **per-chat** section). Solange das **Hera-Profil**
offen ist, ersetzt ein OOB-Swap von `#panels-col` die Panels durch das **Traum-Log**
(s. *Träumen*); jedes Chat-Öffnen tauscht die normalen Panels über das bestehende
`open_chat`-Fragment zurück.

## Core mechanisms

### The namespaced contract (EMOTION / NOTE / TRACE / CALL)
Output is **prose-first**: the visible answer is natural prose, and the model interleaves
namespaced lines `PREFIX verb(key="value")` (each on its own line). **Splitting one overloaded
`CALL` into four namespaces** is deliberate: GPT-OSS associated `CALL` with "tools" and got
restrictive/hesitant. The namespaces give it a mental map (the user's "dog-buttons" analogy):
- **EMOTION** (expressive, shown): `agree · disagree · judge · doubt · surprised · funny ·
  warn · ask · remember` plus `show_help · annoyed · curious · hope · excited · sorry · joke`
  (`calls.EMOTION_VERBS`; `joke` = bewusster Witz, Icon `mood`, neben `funny` = leichte Randbemerkung).
  Feelings/stance — used freely. `remember` writes a Merkzettel entry
  (optional `scope="global"` → `MemoryObject(kind="gedaechtnis")`); scope goes **inside** the parens.
  **Open vocabulary:** the named `EMOTION_VERBS` (under *any* prefix) and every *unknown* verb
  under the `EMOTION` prefix render as the generic **`emotion`** segment type (name preserved) —
  icon/colour map in `_segments.html` + `stream.js EMO_ICONS` (fallback: heart), accents
  `.seg-emo-<name>` in `hera.css`. The prompt declares the list a "Start-Vokabular, KEIN Käfig"
  so GPT-OSS (which hard-obeys the system prompt) doesn't refuse invented emotions — the freedom
  must be granted at system level, a user turn can't override it.
- **NOTE** (vault): `write` → `vault_write` (confirm card), `read` → `vault_read`, `search`
  → `vault_search`. Read/search execute as tools; write is a confirm-before-write card.
- **TRACE**: `summary` → the silent `trace` recap (persisted to `Message.trace`, never shown).
- **CALL** (real external tools): `websearch` (+ still accepts legacy `CALL vault_*`, `CALL
  remember`, etc.). Executed tools surface as loading feedback → compact result.

**Prefix-tolerant + back-compatible.** `calls.canonical_verb(prefix, verb)` maps `(NOTE,write)→
vault_write`, `(TRACE,summary)→trace`, `summary→trace`, else verb as-is — so `EMOTION remember`,
legacy `CALL remember`, and `functions.x` all resolve. `parse_calls(capture_prose=True)` keeps
prose between the lines as `say`. Segment **types** stay canonical (say/warn/remember/vault_write/
trace/tool + the four new emotions), so persisted `segments_json` renders unchanged. `improve`
(→ Strategy) still parses under any prefix. `RENDER_CALLS` gained `judge/doubt/funny/surprised`
(new `_segments.html` + `stream.js renderSegment` branches + icons `balance/doubt/surprised/mood`).

`static/js/stream.js` mirrors the parser (prefix regex, `canonicalVerb`, prose capture, emotion
render) for live rendering — **keep the two in sync** (regex ↔ `_CALL_RE`, segment markup ↔
`_segments.html`, `ICONS` ↔ `_icons.html`). The prompt lives in the `grammar` mind region
(shared by call+free, default text in `mind_regions.py`, rendered as `<output_grammar>`) +
`_namespaced_actions()` (NOTE/CALL, gated by allow-list/vaults).

### Agent loop (Plan → Execute → Eval)
`agent.py::run_agent` never interrupts a turn. Per turn: stream tokens/thinking → on
`turn_end` normalize harmony, parse CALLs → if tool CALLs exist, run them deterministically
and feed `[TOOL-ERGEBNISSE]` back as a user message next turn → else the turn is the final
answer. `MAX_ITERATIONS = 3`.

### Authoritative server render
`chat.py::stream_message` accumulates segments, persists `Message.segments_json`, and
sends the final HTML in the SSE `done` event. The client **replaces** its live-parsed body
with that HTML (`stream.js` done handler, then `htmx.process()` + markdown pass), so
live view, reload, harmony, markdown and empty answers are always identical.

### GPT-OSS harmony
GPT-OSS (via LM Studio) leaks `<|channel|>commentary…<|message|>{json}` / `final` markup
into the content field. `calls.py::normalize_harmony()` rewrites it into CALL lines before
parsing. `stream.js::normalizeHarmony()` mirrors it so GPT-OSS **streams live** (final
answer renders as it arrives; still-streaming commentary/partial tokens are held back to
avoid flashing). Keep the two in sync; the done event remains authoritative.

### Obsidian vaults (`vault.py`)
Folders under `~/.hera/obsidian/` are vaults (real vaults typically **symlinked** from an
iCloud Obsidian folder). Writable set is configurable (`KEY_VAULT_WRITABLE`, default
`Hera`); others are read-only (`Studium`). Three access paths:
- `@Vault/path` mentions in a message → resolved + injected by `context._inject_mentions`.
- tools `vault_search` / `vault_read`.
- `vault_write` → pending card; `routes/vault.py` writes only on user confirm, persists
  status back into `segments_json`.

**Safety:** every path goes through `_safe_path()` — resolved and checked to stay inside
the vault root; `..` and absolute paths cannot escape. Vault paths are `.resolve()`d at
discovery (macOS `/var`→`/private/var` consistency). Directories read **recursively** and
always emit a file listing first. **PDFs/Office** convert via **markitdown** (optional dep;
degrades gracefully if missing). `@`-autocomplete: `/api/vault/files?q=` → `vault.complete()`,
driven by `static/js/autocomplete.js`.

### Model profiles & output modes
Each model in the picker has a **`ModelProfile`** (`backend/models.py`, CRUD + `apply_model_profile`
in `backend/repository.py`) — its own **mode**, tuned **system prompt**, temperature, effort and
allowed tools. `chats/stream.py::stream_message` resolves the picked model's profile onto the
`RuntimeConfig` before building the prompt, so prompt + parsing + tool-wiring are
**per-model**. Modes:
- **`call`** and **`free`** now share the **unified prose-first namespaced contract** (the
  `grammar` mind region's default text, rendered as `<output_grammar>` inside `<hera:persona>`
  — see *The namespaced contract* and *Prompt structure: mind regions*): prose is the answer, EMOTION/NOTE/
  TRACE/CALL lines interleave, `chats/stream.py` parses both with `parse_calls(capture_prose=True)` and
  strips a leaked `trace:` tail. (The `mode` field is kept for the picker + native split; the two
  behave the same today.) Show `remember`'s `scope="global"` **inside** the parens and state that
  **multiple lines per turn are normal** (worked example in the prompt) — GPT-OSS otherwise writes
  scope on its own line and loses it, or hesitates to combine calls. Keep example syntax literal —
  small models copy it verbatim.
- **`native_tools`**: light prose base + `NATIVE_TOOLS_NOTE`; `pipeline` sends real OpenAI `tools`
  (`tools.openai_tool_schemas`); `client.stream_chat` accumulates streamed `tool_calls` →
  `Delta("tool_call")`; `agent.run_agent` branches on `config.mode`, executing native calls. No
  namespaced text grammar (functions carry canonical names).
The per-model `tools` allow-list (`all|none|comma`) is enforced in `agent.py` for both paths.

**Empirical (GPT-OSS): CALL functions beat native tools.** GPT-OSS follows the text `CALL name(...)`
contract more reliably than native function-calling, and pure-prose native output is bland — so
**recommend `free` (or `call`) for GPT-OSS, not `native_tools`**. A profile's `prompt_override`
replaces the persona+grammar bundle (`mind_regions.OVERRIDE_BUNDLE`) wholesale, but
`prompts._capabilities_note()` **re-attaches** the
write-actions (`remember/vault_write`) + allowed tools so a tuned prompt never silently strips
them (the model must never conclude it "cannot remember"). Keep this in mind when tuning prompts.

**Trace-leak stripping.** free/native models often ignore the `trace` CALL/function and write
`trace: …` (or `**trace:**`, with a `---` above) as prose instead. `calls.split_trailing_trace()`
splits that tail off the visible answer in both modes → the recap is hidden and persisted to
`Message.trace`, never shown.

**Single registry (SPOT) for both variants.** `tools.py` is the single source of truth:
executed **tools** (`TOOL_NAMES`: websearch/vault_search/vault_read) *and* **write-actions**
(`WRITE_ACTIONS`: vault_write/remember/improve — the render CALLs that also make sense as
functions). `openai_tool_schemas()` offers tools+writes so a native model (GPT-OSS,
Ministral) can actually write notes. Native tool-calls run in the loop (`tool_start`/
`tool_result` events, unchanged); native **write-actions** are emitted by `agent.py` as a
new `segment` event that `chats/stream.py` renders exactly like the equivalent CALL (vault_write →
confirm card, remember → Merkzettel, improve → Strategy). So each action is defined once and
works in **both** CALL and native mode. The silent **`trace`** is also in the registry
(`SILENT_ACTIONS`) and offered as a native function; `agent.py` surfaces a native `trace` call
as a `{"kind":"trace"}` event that `chats/stream.py` persists like the text CALL.

Manager UI is its **own rail screen** (`tune` icon → `GET /models` → `models_screen.html`,
swaps `#chat-col` like *Einstellungen*), not inside the settings form. `routes/models.py`
(list/add/edit/save/delete) + `models_list.html`/`model_edit.html`; model ids carry slashes
→ passed as form/query fields, not path segments. The screen also carries the **provider
settings** (API base URL / key / default model / default temperature — `POST /models/provider`);
*Einstellungen* keeps only appearance, vaults, websearch, context settings, profile, backup.
Strategies are managed **only** on the Hera-Profil screen (im Dropdown, s. u.), not here.

### Self-improvement (strategies: skills + subconscious + mem_ex, git-backed)
`MindObject.kind ∈ {skill, unterbewusst, mem_ex}` (`repository.MIND_OBJECT_KINDS`, die SPOT-
Liste — jede Stelle, die früher `("skill","unterbewusst")` hart kodierte, iteriert jetzt
darüber): **`skill`** = Herangehensweise (a way of tackling things) → injected as
`GELERNTE HERANGEHENSWEISEN`; **`unterbewusst`** = a quiet impression/leaning → injected as
its own `DEIN UNTERBEWUSSTSEIN` block ("subtly colour tone, never quote"); **`mem_ex`**
(neu, Teil 4) = ein kurzes durchgespieltes Beispiel guter Gedächtnis-Anwendung → injiziert als
`<memory_application_examples>` innerhalb von `<memory:memory_system>` (s. *Prompt structure*
unten) — bewusst eine WACHSENDE SAMMLUNG kleiner Einträge statt ein einzelner mutierender
Blob (ein Traum-Vorschlag müsste sonst ALLE bisherigen Beispiele jedes Mal neu ausschreiben).
Seit v0.3.0-Teil-3 lebt der CONTENT als git-committete Datei (`mind/skills/{id}.md` /
`mind/subconscious/{id}.md` / `mind/mem_examples/{id}.md`, `src/core/mind.py`);
`models.MindObject` ist eine DB-**Sidecar** für die volatile Metadaten (`kind·scope·source·
enabled·hits·negative_signals·embedding`) — `MindObject.content` ist eine **Property**, nicht
eine Spalte, die die Datei bei jedem Zugriff frisch liest, `relpath()`s Ordner-Zuordnung ist
ein Dict (`skill→skills`, `unterbewusst→subconscious`, `mem_ex→mem_examples`), damit ein
weiteres Kind sich anschließen kann ohne Codeänderung. `repository.add_strategy`/
`list_strategies`/`toggle_strategy`/`delete_strategy`/`merge_strategies` bleiben
unchanged-signature Wrapper über die git-hinterlegten Funktionen. Both global + model-scoped,
split in `context.build_chat_messages` (jetzt 3 `_select_relevant`-Buckets statt 2, s.
`context.py` oben). Managed **in einem Dropdown-Eintrag pro kind** auf dem *Hera-Profil*-
Screen seit Teil 4 (`routes/strategies.py::render_strategies`, unchanged, jetzt von
`routes/hera/profile/screen.py`s Dispatcher importiert statt eine eigene immer-sichtbare Box zu sein
— `strategies.html` selbst unverändert, trägt schon seine eigene, in sich geschlossene
Wurzel-ID `strategies-list-{kind}`). The model can self-add a skill via the render CALL /
native function **`improve(text=…)`** — like `remember` but written via `add_strategy`
(`source="ai"`, kind=skill) in `chats/stream.py`, jetzt **mit Embedding** (`chats/stream.py` embeddet
`improve_texts` batched genau wie `remember_texts`, vorher hart auf `embedding=None`).
**`improve` steht auch im Text-Contract** (`grammar`-Region + `_capabilities_note`, beide
Modi) mit Qualitäts-Gate („SELTEN, nur wiederholt nützliche Arbeitsweisen"); `add_strategy`
dedupt via `_find_duplicate` — normalized-text ODER Cosine ≥ `DEDUP_COSINE`, wenn ein
Embedding übergeben wird (vorher hart `None`, kein semantisches Dedup beim Anlegen — nur
`find_strategy_merge_pairs` fing Dubletten nachträglich beim Träumen ab).

**Nie auf dem Hot-Path.** `add_strategy` legt erst die Sidecar-Zeile an (braucht ihre `id` für
den Dateipfad), dann `mind.write_and_commit`; `toggle_strategy`/`increment_mind_hits` sind
**reine DB-Updates ohne Git-Aufruf** — hits/negative_signals ändern sich potenziell bei jedem
Chat-Turn, ein Commit pro Änderung wäre absurd (Git ist nicht für hochfrequente
Einzelwert-Schreibvorgänge gedacht). `delete_strategy` löscht erst die Datei (`mind.
delete_and_commit`) und prüft dessen Rückgabewert, BEVOR es die Sidecar-Zeile löscht —
schlägt der Git-Teil fehl (`None`), bleibt die Zeile (und damit sichtbar/nutzbar) erhalten
statt eine verwaiste Datei ohne Metadaten zu hinterlassen (war zwischenzeitlich ein Bug —
die Zeile wurde unconditional gelöscht — jetzt gefixt + regressionsgetestet).

**Injection-Caps + Nutzungssignal.** Strategien laufen wie die anderen Ebenen durch
`_select_relevant`: `SKILL_TOKEN_CAP` 1200 / `SUBCONSCIOUS_TOKEN_CAP` 800 /
`MEM_EXAMPLE_TOKEN_CAP` 800 (`context.py`), Ranking Cosine (seit v0.3.0 — skill/unterbewusst
tragen jetzt Embeddings, vorher hatte `Strategy` keine `embedding`-Spalte, wodurch
`find_strategy_merge_pairs` immer auf den
Jaccard-Fallback zurückfiel) → Keyword → hits → Recency. `MindObject.hits` zählt echte
Injektionen (nur `count_hits=True`, via `repository.increment_mind_hits` — eigener Call,
getrennt von `increment_hits` für gedaechtnis/entities); `Message.strategy_ids_used` (JSON)
hält fest, welche Strategien im Kontext einer Antwort aktiv waren. **Retry/Delete** einer
Antwort bumpt `MindObject.negative_signals` via `repository.penalize_strategies_for_message`
(Hooks in `retry_message` + `repository.delete_message`) — bewusst verrauschtes Signal, DB-only.
`dream.find_weak_strategies` (deterministisch): `hits≥5` & `neg/hits≥0.5` → „wird oft
verworfen", `hits==0` & älter 30 Tage → „ungenutzt" (nur `enabled`-Zeilen) → Review-Karten
beim Träumen/bei der Wartung („Signal, kein Beweis"), Deaktivieren via `/strategies/toggle` +
`from_review`-Flag (Bestätigungskarte + OOB-Refresh auf `strategies-list-{kind}` — seit Teil 4
nur noch lebendig, wenn genau dieser Bereich gerade im Hera-Profil-Dropdown offen ist, sonst
harmlos verpuffend, gleiche Präzedenz wie jedes andere cross-screen-OOB in dieser Codebase).
Nichts wird automatisch gelöscht — **Löschen/Merge sind die einzigen Strategie-Aktionen, die
tatsächlich committen.**

### Trace compaction & context budget (keeps 32K chats small)
Every turn the model ends with a silent **`TRACE summary(text=…)`** (canonical verb `trace`) —
a one-line recap ("Nutzer fragte X; ich sagte Y") persisted to `Message.trace`. `context.build_chat_messages` keeps only
the last **`keep_full_turns`** turns verbatim (default 2, Setting `keep_full_turns`); everything
older is replaced by its trace in a single `GESPRÄCHSVERLAUF (komprimiert)` block. Legacy turns
without a trace fall back to a truncated verbatim line (`_compact_history`).

**Strict-template safety (important!):** the compacted block is **folded into the system
prompt**, and `@mention` content is **prepended to the user turn** — never a second `system`
message mid-conversation, and the verbatim window is **aligned to a user-turn boundary**. LM
Studio's Ministral/GPT-OSS templates reject non-alternating roles ("roles must alternate")
with an **empty answer**, so keep the message array: one system message, then strictly
alternating user/assistant. **`context._append_alternating()` enforces this** by merging
consecutive same-role turns: an empty assistant answer (stored with empty `content_raw`, then
filtered out) used to leave two user turns in a row and **poison every following turn** — the
"Channel Error" storm. Merging the neighbours makes one empty answer harmless. `repository.estimate_tokens()` (~chars/4) drives the composer's
**context meter** (`/chats/{id}/context-meter` HTML partial + `/api/chats/{id}/context-usage`
JSON, budget = Setting `context_budget`, default 32000), refreshed on the `hera:context-updated`
body event after each turn.

### Memory: MemoryObject, embeddings, dedup, caps, hits, epistemics
Memory is **local** (per-chat `MerkzettelEntry`, untouched by the v0.3.0 unification below —
structurally different, chat-scoped) and **cross-chat** (`MemoryObject`, one polymorphic table
that replaced `GlobalMemory`/`Entity`/`TrackedProject`; `kind ∈ gedaechtnis|person|ort|projekt`
— skill/unterbewusst/mem_ex moved to the git-backed `MindObject` in v0.3.0-Teil-3, see
*Self-improvement* — `content · name · notes · relations · scope · source(ai|user) ·
origin_chat_id · hits · negative_signals · enabled · embedding`, fields nullable-by-convention
per kind — see *Hera-Profil* below for the full picture). `remember(text=…, scope="global")`
(`scope` is a kwarg — works under any prefix and as a native function) writes
`MemoryObject(kind="gedaechtnis")` via the `add_global_memory` wrapper.

**Semantic retrieval (embeddings).** `core/pipeline/embeddings.py` speaks `/v1/embeddings` on the SAME
OpenAI-compatible endpoint (LM Studio + `nomic-embed-text`); Setting `embedding_model`
("" = off). Vectors are packed-float32 BLOBs on `MemoryObject` + `MindObject` + `MerkzettelEntry`
— **every** kind, including skill/unterbewusst/mem_ex since v0.3.0 (previously `Strategy` had
no `embedding` column at all, so strategy-merge detection always fell back to token-Jaccard;
unifying the table fixed this as a side effect; `add_strategy` itself only started passing an
embedding through to its own dedup check in Teil 4 — before that, creation-time dedup for
skills/subconscious/mem_ex was text-only, only merge-time caught semantic dupes).
`embed()` (async; `stream_message`/`dream_run`) / `embed_sync()` (sync
routes, threadpool) **never raise** — `None` ⇒ keyword fallback, **a turn must never fail on
embeddings** (LM Studio JIT-load can exceed the 4s timeout → silent fallback for that turn).
`chats/stream.py` computes the query vector OUTSIDE any DB session and passes it into
`build_chat_messages(query_embedding=…)`.

**Retrieval + caps.** `context._select_relevant` takes ORM rows: cosine matches (floor 0.30)
rank first, then keyword overlap; tiebreak `hits` desc → id desc; no match ⇒ newest-first. Six
tiers are filtered + capped, each via its own `_select_relevant` call (deliberately NOT collapsed
into one shared budget when `MemoryObject` unified the tables — a noisy kind like gedaechtnis
would otherwise crowd out the deliberately-tiny subconscious budget): Merkzettel
`MERKZETTEL_TOKEN_CAP` 2k, gedaechtnis = Setting `memory_token_cap` (default 4k), entities
`ENTITY_TOKEN_CAP` 1.5k, skill `SKILL_TOKEN_CAP` 1.2k, unterbewusst `SUBCONSCIOUS_TOKEN_CAP`
0.8k, mem_ex `MEM_EXAMPLE_TOKEN_CAP` 0.8k (Teil 4). Injected global-memory/entity lines carry
an **age hint** (`[seit Juli 2026]`) so the model can judge staleness.

**Write-dedup.** `repository.normalize_text` equality + cosine ≥ `DEDUP_COSINE` (0.90)
against existing rows (same kind[, scope] bucket) dedups every write path (remember both
scopes, dream accept, manual add); entity note enrichment compares normalized fragments and
caps notes at ~600 chars. Pairs below 0.90 (Cosine ab `MERGE_COSINE` 0.82, oder
Token-Containment ab 0.75) surface as **merge cards** while dreaming (see below).

**hits.** `build_chat_messages(count_hits=True)` — only the real chat stream passes True
(context meter must not inflate) — bumps `hits` on injected MemoryObject rows (one
`increment_hits(session, ids)` call across all kinds since v0.3.0, was three separate
per-table calls); used as ranking tiebreak.

**Epistemics.** The `mem_instr` mind region (`<memory_application_instructions>`, dream-mutable
since Teil 4 — was the hardcoded `prompts._memory_epistemics(mode)`) is injected inside
`<memory:memory_system>` whenever any memory content exists (always re-attached, survives
`prompt_override`, all modes): memory = background knowledge (possibly stale), distinguish
knowing from guessing, ask (`EMOTION ask`) instead of inferring, never pretend to know personal
facts. The `remember` push is quality-gated (nur dauerhafte Nutzer-Fakten, keine Vermutungen)
— counterweight against over-inference.

UI: the KI-Merkzettel panel shows a global + a per-chat section with an `auto/manuell`
badge (`= source`); delete via `/chats/{id}/global-memory/{id}`.

### Prompt structure: mind regions (registry, since v0.3.0-Teil-4)
The old two-region persona/workflow duopol (`persona.md`/`workflow.md`, one wholesale-
replaceable text each) is retired in favor of **15 named mind regions**
(`src/core/ctx/mind_regions.py::MIND_REGIONS`) — every meaningful slice of the system prompt
is now its own git-versioned file under `~/.hera/mind/`, with one of three governance tiers:

- **Dream-mutable** (`dream_editable=True`, 8 single-file regions + `mem_ex` as a collection):
  `role` (`<your_role>`) · `character` (`<character>`, voice/personality — **migration target
  for the old `persona.md`**) · `tone` (`<tone_and_formatting>`) · `workflow`
  (`<hera:approach>`, unchanged mechanically) · `mem_instr` (`<memory_application_instructions>`,
  was `prompts._memory_epistemics`) · `emo_usage`/`tool_usage` (`<emotion_usage>`/
  `<tool_usage>` — extra guidance/examples, seeded non-empty) · `user_prefs`
  (`<user:user_preferences>`'s mutable body, appended after the fixed `profile_name` line) ·
  `mem_ex` (memory-application worked examples — **not** a `MindRegion` at all, a third
  `MindObject.kind`, see *Self-improvement* — a growing collection needs many small entries,
  not one blob a dream would have to fully restate each time).
- **Owner-fixed** (`dream_editable=False`, no `dream_tag` — dreaming never proposes these,
  ENFORCED at the route, not just by omission from the prompt, see below): `about_you`
  (`<about_you>`, bare identity) · `grammar` (`<output_grammar>`, the EMOTION/NOTE/TRACE/CALL
  format + worked turn example — was `HERA_CONTRACT`) · `safety` (`<hera:safety>`, refusal
  handling + legal/financial framing + the dignity/`end_conversation` clause) · `mem_overview`
  (`<memory_overview>`) · `emo_vocab` (`<available_emotions>`, the EMOTION verb list — "starter
  vocabulary, not a cage") · `tools_avail` (`<available_tools>`, a prose framing — the REAL
  per-turn gating stays `prompts._namespaced_actions()`, deliberately NOT in the registry, so a
  dream/owner text can never claim a tool is wired that isn't) · `dev_msg`
  (`<developer:developer_message>`, "You were programmed by Lukas Kreuz"). The owner can still
  edit every one of these directly on the Hera-Profil screen (same `mind.write_and_commit` path
  dreaming uses, just a different caller — `repository.edit_mind_region` vs.
  `accept_mind_region`) — this is the actual mechanism behind "add a new safety rule without
  touching code": open the region, edit the textarea, save, it's a commit.
- **User setting** (not in the registry at all): `language_preference` — a plain `Setting`
  (`repository.get/set_language_preference`) feeding `<language>` inside `<hera:persona>`,
  never touched by the model or by dreaming, edited on *Einstellungen*.

`prompts.py` composes `<hera:persona>` nested (`<about_you>/<your_role>/<character>/
<language>/<tone_and_formatting>`) + `<output_grammar>` as a sibling — together the ONE bundle
a `prompt_override` replaces wholesale (`mind_regions.OVERRIDE_BUNDLE`, 5 ids; `native_tools`
profiles need different grammar, so persona+grammar travel as one unit). **Every other tag is
always re-attached regardless of override** — `<hera:safety>` and `<developer:
developer_message>` in particular are never inside the overridable bundle, which is the
technical basis for "a tuned model profile can never silently switch off safety rules."
`prompts.py` is a leaf module that imports `mind`/`mind_regions` directly and reads each region
via `_region_text(id)` (`mind.read_text(region.file).strip() or region.default`) — no more
threading a `persona_override` string through `build_system_prompt()`'s signature.
`RuntimeConfig.persona` still exists as a flat concatenation of about_you+role+character+tone,
but ONLY for `core/hera/dream/dream.py`'s own "dream in your own voice" system framing — the actual chat
prompt reads the four regions separately for the nested tags.

**Migration (`repository._migrate_persona_regions`, one-time, marker-guarded).** Replays the
OLD `persona.md`'s full git history — backdated — into `character.md`: for every commit on
`persona.md` (`mind.log`), read its content (`mind.show`) and re-commit it onto `character.md`
with the original timestamp (`write_and_commit(when=)`), so `mind_generation("character")`
continues the real generation count instead of resetting to 1. `role.md`/`tone.md` start fresh
from their registry defaults. `persona.md` itself is left in place, untouched and unread from
now on — no rename needed, its history stays intact as-is (same "leave the old thing alone
rather than drop it" safety net every other migration in this file already uses).

**Träumen** (seit der Audit-Runde eine **Karte auf dem Hera-Profil-Screen** — kein eigener
Rail-Eintrag/`GET /dream` mehr, `screen.py`/`dream_screen.html` gelöscht; die POST-Routen
`/dream/*` bleiben `routes/hera/dream/*`): the reflection trigger — a checkbox group (`force_regions`, one per
`mind_regions.DREAM_EDITABLE_REGIONS`, replaces the old single "Persona weiterentwickeln"
toggle) that forces at least one rewrite proposal for the checked regions this run, plus
runs count — and candidate review cards (`#dream-results`, `dream_candidates.html`).
`dream_accept`/`dream_merge`/`dream_reject`/`lineage_revert` live here (dream-review
actions). **No OOB refresh for any candidate kind anymore, including mind regions** — every
target (global memory, entities, strategies, projects, mind-region panels) lives exclusively
behind the Hera-Profil section dropdown now and is never open at the same time as a Träumen
candidate card; the confirmation card is enough, reopening/reselecting the section on
Hera-Profil shows the result. `lineage_revert` is the one exception that still returns real
content (`render_mind_region_panel`, not just a card) because its button lives INSIDE that
same panel on Hera-Profil and targets it directly.

**Traum-Log (Transparenz).** Solange das Hera-Profil offen ist, zeigt die rechte Spalte
statt Notizen/Merkzettel das **Traum-Log** (`dream_log_panel.html`, OOB-Swap von
`#panels-col` — mitgeliefert von `GET /profile` und von jeder `/dream/run`-Antwort;
Chat-Öffnen stellt die normalen Panels über das `open_chat`-Fragment wieder her). Ein
`DreamRun`-Eintrag pro LLM-Durchlauf: das exakte **Input-Material** (die User-Message aus
`build_dream_messages` — mit **Chips** pro erkannter Sektion via
`_shared.dream_input_chips`, z. B. „Trainingsdaten" hervorgehoben, damit sichtbar ist, OB
sie einflossen), der **System-Prompt**, die **Gedanken** (Thinking-Deltas — dafür sammelt
`dream.generate_full()` content UND thinking; das alte `generate()` bleibt als
Content-only-Wrapper) und die **rohe Ausgabe** + Kandidatenzahl/Fehler je Durchlauf.
**Automatisch & live:** jeder Pass wird SOFORT nach seinem Ende persistiert (eigene
Session in der `/dream/run`-Schleife, nicht erst nach dem Batch), und das Panel pollt sich
selbst per `hx-trigger="every 3s [document.body.hasAttribute('data-dreaming')]"` gegen
`GET /dream/log` — das `data-dreaming`-Body-Attribut setzt/entfernt das Träumen-Formular
via `hx-on::before-request`/`after-request`; im Leerlauf feuert der Poll nicht. So sieht
man bei langen Mehrfach-Läufen jeden fertigen Durchlauf einlaufen. (Sync-Routen laufen im
Threadpool, daher kann der Poll neben dem awaitenden `/dream/run` bedient werden.)
Auto-Prune auf die letzten `DREAM_LOG_KEEP` (30) Zeilen bei jedem Write; `POST
/dream/log/clear` leert nur das Log, nie übernommene Erkenntnisse. Beim Monkeypatchen in
Verify-Skripten **`generate_full` patchen** (Tuple zurückgeben) — `/dream/run` ruft nicht
mehr `generate`. **Durchläufe** sind ein freies Zahlenfeld (1–`MAX_DREAM_RUNS` 30, war ein
4-Optionen-Select mit Cap 5 — lange unbeaufsichtigte Läufe sind der Zweck; das
`max`-Attribut im Template von Hand synchron halten). **Kandidaten-Hygiene bei vielen
Läufen:** `parse_candidates` droppt Kandidaten, deren signifikante Tokens zu ≥
`KNOWN_COVERAGE` (0.8) von EINEM bekannten Eintrag abgedeckt sind (Umformulierungen von
Bekanntem — Hauptquelle wegzuklickender Karten), und `_dedupe_candidates` kollabiert
Karten desselben Gedankens über Pässe hinweg fuzzy (`text_overlap` ≥ 0.8 je kind, die
längere Fassung gewinnt). Der Traum-Prompt verpflichtet zusätzlich auf einen
[compact]-Dubletten-Scan über KNOWN · GLOBAL MEMORY („consolidating duplicates is as
valuable as discovering something new").

**Statische Assets & Cache.** `templating.py` setzt das Jinja-Global `asset_v` (max. mtime
über `static/{css,js}` beim Boot); `base.html` hängt es als `?v=` an jedes CSS/JS.
StaticFiles sendet kein `Cache-Control` — ohne den Buster darf der Browser per Heuristik
eine alte `hera.css`/`stream.js` nach einem Update weiterverwenden (genau die Klasse Bug
„neues Panel wirkt unstyled/leer"). Update = Server-Neustart = neues `asset_v`.

`core/hera/dream/dream.py`: `build_dream_messages` gathers **all** Merkzettel + recent `Message.trace`
recaps + existing global memory **and known entities + strategies (incl. mem_ex)** (fed as
"BEKANNT — nicht wiederholen" for dedup; parse-side comparison is `normalize_text`-based),
capped at `INPUT_TOKEN_CAP` (~4k), plus the CURRENT text of every non-persona mutable region
that has one (`workflow`/`mem_instr`/`emo_usage`/`tool_usage`/`user_prefs` —
`_SHOW_CURRENT_TEXT_REGIONS`; role/character/tone are already visible via the dream's own
persona framing, so they're excluded here). **Geträumt wird IN der eigenen Persona**
(`config.persona`, the flat about_you+role+character+tone concatenation — never empty since
every sub-region has a non-empty registry default) — übernommene Vorschläge färben so jeden
künftigen Traum: Veränderungen wirken auf Veränderungen. `POST /dream/run` (async) first
**backfills missing embeddings** (best-effort) and drops candidates with cosine ≥0.9 vs.
existing memory (region-rewrite proposals excluded — a rewrite is not a memory);
it calls the model `runs` times via `dream.generate`; **`parse_candidates` returns TYPED
dicts** `{kind,text,name,detail,variants}` where `kind` is either a memory-item bucket
(`gedaechtnis|herangehensweise|unterbewusst|mem_ex|person|ort|projekt|wunsch`) or a mind-region
id (`role|character|tone|workflow|mem_instr|emo_usage|tool_usage|user_prefs`) — region-rewrite
tags use `[tag]…[/tag]` blocks (`_REGION_BLOCK_RE`, one regex per
`DREAM_EDITABLE_REGIONS` entry, built from the registry — no more hand-duplicated
`_PERSONA_BLOCK_RE`/`_WORKFLOW_BLOCK_RE`), everything else uses single `- [typ] …` lines
(person/ort/projekt use `Name | Notiz`).
**Varianten:** zu jedem Vorschlag bis zu 3 alternative Fassungen als `ODER: …`-Folgezeilen
(`MAX_VARIANTS`; „der Nutzer wählt die beste") — Varianten-Zeilen in der Karte, jede mit
eigenem Übernehmen-Button. **Region-Vorschläge:** `[tag]…[/tag]`-Blöcke (mehrzeilig, max. 2
Varianten je Region — `MAX_REGION_PROPOSALS`) → editierbare Textarea-Karte mit
Diff-Vorschau + Generations-Nummer (`_diff_html`, `repository.mind_generation(id) + 1`); Accept
committet nach der Region-Datei (Contract/Tools/Verhaltensprofile bleiben unberührt — safety/
dev_msg/etc. sind nie ein gültiger `kind` hier, s. u.). Der Traum-Prompt gewährt das
Selbst-Zitieren/Umschreiben von Charakter/Rolle/Ton ausdrücklich auf System-Ebene (GPT-OSS
verweigert es sonst). **Tools sind unantastbar** — `[wunsch]`-Zeilen landen als „Wunsch des
Modells: …" im globalen Gedächtnis. Each candidate is a review card showing the **suggested
bucket**; `POST /dream/accept` routes by `kind` → `add_global_memory` (Gedächtnis + Wunsch),
`add_strategy(kind="skill"|"unterbewusst"|"mem_ex")` (git-hinterlegt), `add_entity` (Person/
Ort), `add_tracked_project` (Projekt), oder `accept_mind_region` für jede
`dream_editable`-Region — all thin wrappers over `add_memory_object`/`mind.write_and_commit`.
**Enforcement, nicht nur Auslassung:** `dream_accept` prüft `region.dream_editable` explizit
und setzt `region = None`, wenn nicht — ein rohes `POST /dream/accept kind=safety` fällt so
sauber auf den generischen `gedaechtnis`-Catch-all zurück statt heimlich `safety.md` zu
schreiben (gefunden + gefixt + regressionsgetestet während der Teil-4-Umsetzung; ohne diese
Prüfung hätte `mind_regions.MIND_REGIONS.get(kind) is not None` allein NICHT zwischen
dream-editable und owner-fest unterschieden). Flip buttons let you re-bucket among the text
buckets before accepting. Model failure → error card, never a 500 — **merge cards and
weak-strategy cards still show** (they need no LLM). Nichts wird ohne Bestätigung übernommen.

**Reject/Revert unverändert in der Git-Mechanik.** `POST /dream/reject` →
`repository.add_mind_rejection(region, text)` — Verwerfen ist **echte Information**, landet
aber als `MindRejection`-Zeile (**nie** ein Commit — ein Commit repräsentiert akzeptierten
Zustand, eine Ablehnung ist das Gegenteil davon). `dream._format_lineage` speist beides zurück
in den nächsten Traum: für jede `DREAM_EDITABLE_REGIONS`-Region die aktuelle Generation
(`mind_generation`) + die letzten `REJECTED_LINEAGE_LIMIT` (3) verworfenen Fassungen als
**Gegenbeispiele** (auf `REJECTED_EXCERPT_CHARS` 400 gekürzt); skill/unterbewusst/mem_ex teilen
sich dieselbe Rejection-Archivierung, haben aber keine eigene Generation (viele unabhängige
Dateien statt eines einzelnen evolvierenden Texts). `POST /dream/lineage/revert` →
`repository.revert_mind_region(region, sha)` → `mind.revert_file` liest den historischen
Inhalt via `git show <sha>:<path>` (Format vorab per Hex-Regex validiert — `sha` kommt aus
einem Formularfeld) und **committet ihn neu** (nie `git reset`/`checkout <sha>` — bleibt
vorwärtsgerichtet, nichts wird gelöscht, kein detached HEAD).

**Nebenläufigkeit.** Alle schreibenden `mind.py`-Operationen laufen hinter einem
`threading.RLock()` — Git's Index ist unter echter Nebenläufigkeit nicht sicher, ein
Prozess-lokaler Lock genügt für eine Single-Instance/Single-User-App (dieselbe Annahme wie
beim bestehenden SQLite-WAL-Setup). Verifiziert per Concurrency-Smoke-Test (N parallele
`/dream/accept`-Requests → exakt N Commits, kein korruptes `.git/index.lock`).

### Hera-Profil: ein Dropdown über alle Prompt-Bereiche (seit Teil 4)
War bis Teil 4 sieben immer-sichtbare Boxen (Verhalten/Gedächtnis/Personen&Orte/Projekte/
Herangehensweisen/Unterbewusstsein/Persona-Stammbaum) — inhaltlich doppelt, da all das schon
„Teile des Prompts" sind, genau wie die 15 Mind-Regionen. Jetzt **eine** Karte „Prompt-Bereiche"
(`brain` icon → `GET /profile` → **`hera_profile_screen.html`**, swaps `#chat-col`,
`routes/hera/profile/screen.py`): ein `<select name="section_id">` über `profile_sections()` — die 15
Mind-Regionen (`mind_regions.MIND_REGIONS`) plus 8 Sammlungs-Bereiche (Gedächtnis · Personen &
Orte · Projekte · Herangehensweisen · **Skills (Import)** · Unterbewusstsein ·
Gedächtnis-Beispiele · Verhalten), alphabetisch, 23 Einträge — plus EIN Inhaltsbereich
`#profile-section-content` darunter.
`GET /profile/section?section_id=X` (Query-Param, natives HTMX-`<select>`-Muster) dispatcht:
Mind-Regionen → `render_mind_region_panel` (neu, `mind_region_panel.html` — Textarea (Klasse
`mind-region-textarea`: eigene, echte Editor-Styles + dynamische `rows` aus der Zeilenzahl,
geklemmt auf 12–30 — die alte 8-Zeilen-Box ohne CSS-Regel war praktisch uneditierbar) +
Speichern + Git-Log + Revert-Buttons für GENAU eine Region, ersetzt das alte
`persona_lineage.html`, das alle Regionen auf einmal zeigte); Sammlungen → **unverändert
wiederverwendete** bestehende Partials (`render_global_memory` → `memory_objects_list.html`,
`render_entities` → `entities_list.html`, `render_projects` → `projects_list.html`,
`strategies.render_strategies` → `strategies.html` parametrisiert nach `kind`,
`profiles.render_profiles` → `behavior_profiles.html`, `skills.render_skill_docs` →
`skill_docs.html`, s. *Import-Skills* unten) — jede dieser Partials trug schon vorher eine
**eigene, in sich geschlossene Wurzel-ID** (`#global-memory-list`, `#entities-list`,
`#projects-list`, `#strategies-list-{kind}`, `#behavior-profiles`, `#skill-docs`) mit
`outerHTML`-Selbst-Swap auf ihren
Add/Toggle/Delete-Formularen — funktionieren also unverändert in JEDEM Wrapper-Div, brauchten
keine einzige Template-Änderung, nur die Ersteinbindung über den Dispatcher. `GET /profile`
rendert den ersten (alphabetisch ersten) Bereich serverseitig direkt mit, kein Leerzustand,
kein Extra-Klick. Speichern (`POST /profile/mind/{region_id}` → `repository.edit_mind_region`)
und Revert zielen direkt auf `#profile-section-content` (`hx-swap="innerHTML"`, das Panel selbst
trägt bewusst KEINE eigene ID, um Kollision mit dem Wrapper zu vermeiden) — die frisch
aktualisierte Git-Historie oben im Panel IST die Bestätigung, kein separater Toast mehr nötig.
**Trainingsdaten** (`training_docs.html`, unchanged `routes/training.py`), **Träumen** (die
Reflexions-Karte, s. o. — Karten-Reihenfolge: Prompt-Bereiche · Trainingsdaten · Träumen ·
Wartung) und **Wartung** (hygiene/translate, `#maintenance-results`) bleiben eigene, immer
sichtbare Karten — kein Prompt-Inhalt, sondern Träum-Material bzw. Aktionen.

### Import-Skills (Skill-Bibliothek, seit der Audit-Runde)
Das im REFACTOR-Plan skizzierte „Skills wie Python-Module laden": `models.SkillDoc`
(name·description·content·enabled — bewusst KEIN MindObject/keine Mind-Region: user-kuratiertes
Aufgaben-Material wie `TrainingDoc`, das Träumen fasst es nie an). Im System-Prompt steht nur
`<skill_library>` innerhalb von `<tools:tools>` — **Name + Einzeiler** pro aktivem Skill
(`repository.skill_doc_summary`: description, sonst erste Inhaltszeile) plus die Anweisung, bei
passender Aufgabe ZUERST zu importieren; der volle Inhalt kommt erst beim Aufruf als
`[TOOL RESULTS]` zurück. `tools.ImportSkillsTool` („import_skills") ist ein normales
Registry-Tool (läuft in beiden Modi: CALL-Text UND native Funktion via `_TOOL_SCHEMAS`;
Allow-List greift wie überall) — Lookup exakt-casefold, dann Substring; Fehltreffer listet die
verfügbaren Namen, damit sich das Modell korrigieren kann. DB-Zugriff via Lazy-Import von
`session_scope` im Tool — die EINE dokumentierte Ausnahme von „keine DB in core/" (tools.py
importierte ohnehin schon `RuntimeConfig` aus backend). Der Parser hat dafür (beidseitig,
`calls._extract_kwargs` ↔ `stream.js extractField`) einen **Positional-Fallback**: ein einzelner
nackter String in den Klammern (`CALL import_skills("Coding")`, `EMOTION funny("…")`) wird als
`text`-Argument gelesen — kleine Modelle lassen den Key gern weg. Verwaltung: Hera-Profil-
Dropdown „Skills (Import)" (`routes/hera/profile/skills.py`, `skill_docs.html`, `#skill-docs`):
Anlegen (Name+Beschreibung+Textarea, Upsert per Name case-insensitive), an/aus (pausiert =
nicht gelistet), löschen. `prompts._render_skill_library` gated auf „import_skills ∈ allowed
tools UND Liste nicht leer" — ein leerer/abgeschalteter Zustand erzeugt nie einen leeren Tag.

**Verfolgte Projekte.** `MemoryObject(kind="projekt")` (name·content=description·notes·
`chat_project_id`·status — war `TrackedProject`) + `ProjectTask` (unverändert, add/toggle/
delete, FK-by-convention auf die neue `memory_objects.id`) — neben Personen/Orte, jetzt Teil
derselben Tabelle. Ein Projekt wird einem **Chat-Ordner** (`Project`) zugewiesen: dort ist es
**voll aktiv** (Notizen + offene Tasks injiziert), überall sonst kennt Hera nur die
**Kurzbeschreibung** (eine Zeile, damit der Kontext schlank bleibt). `context._format_projects
(chat_id)` baut den `TRACKED PROJECTS`-Block (`active_project_for_chat` via `Chat.project_id`).
CRUD-Routen `/memory/project/*` auf dem **Hera-Profil**-Screen, hinter dem Dropdown-Eintrag
„Projekte" (`projects_list.html`); automatisch via Traum-`[project]`-Tag (→
`add_tracked_project`). Task-Auto-Befüllung (Chat-seitig) ist noch offen.

**Gedächtnis-Verdichtung beim Träumen.** Traum-`[compact]`-Block: eine dichtere Fassung + eine
`replaces:`-Liste der subsumierten Einträge → `parse_candidates` liefert `{kind:"compact", text,
replaces}`, Karte mit editierbarer Fassung. `POST /dream/accept` (kind=compact) →
`repository.compact_global_memory` (dünner Wrapper über `compact_memory_objects(kind=
"gedaechtnis")` — matcht replaces per normalize/Jaccard≥0.8, löscht die Treffer, fügt die
dichte Fassung als `source="user"` mit max-hits hinzu; matcht nichts → nur Hinzufügen, nie
schlechter als ein remember). „Gleiche Info, weniger Fläche."

**Externes Traum-Material (Trainingsdaten).** `models.TrainingDoc` (name·content·enabled·
scope) — Dokumente, die der Nutzer **über die UI einwirft**, damit das Modell mehr zum Träumen
hat als nur Chats (Meister-Demonstrationen: Aufgabe + Musterlösung, Sets in `training/`:
`TASK_SET1` Grundlagen, `_SET2` Verhalten, `_SET3` Workflows/Tool-Nutzung (füttert den
Workflow-Track), `_SET4` Coding (für ein späteres Hera-Coding-Profil via `scope`), `_SET5`
Meinungsbildung). Format je Aufgabe: Situation · ❌ schwach · ✅ stark (in-contract) · 🎯 Lektion.
Verwaltung als eigene Box im **Hera-Profil** (`routes/training.py`, unverändert seit v0.3.0 —
nur das Include wanderte von *Einstellungen*; `training_docs.html`, swap `#training-docs`):
Upload (`POST /training/upload`, nur UTF-8-Text, ≤512 KB, upsert per Name),
an/aus (`toggle`), entfernen (`delete`). `dream.build_dream_messages` zieht **aktive** Docs über
`repository.enabled_training_content` und `_format_training` in eine eigene `TRAINING MATERIAL`-
Sektion mit **eigenem Budget** (`TRAINING_TOKEN_CAP` 3000, damit ein großes Dokument die
persönlichen Notizen nicht verdrängt und umgekehrt); der Header weist das Modell an, die *allgemeine
Lektion* als skill/subconscious/character zu destillieren, **nie** als Fakt über den Nutzer zu
speichern. `scope` (heute "" = alle) ist die Naht für spätere **profil-spezifische** Trainings
(z.B. ein Hera-Code-Profil). Nichts wird automatisch übernommen — es erscheint als normale
Traum-Kandidatenkarte.

**Bewusst NICHT gebaut** (aus `thinking/MISTRAL.md`, dort empfohlen): **LLM-as-a-Judge**
(GPT-OSS bewertet sich selbst auf generischen Testfragen — misst nicht „passt es zu Lukas",
und Selbstbewertung belohnt Länge/Selbstsicherheit), **automatische Übernahme ab Fitness-
Schwelle** (widerspricht der Kernvorgabe, dass der Nutzer alles absegnet), **zufällige
String-Mutation** (Synonym-Tabellen + Satz-Einfügen an zufälliger Zeichenposition zerstören
Prompts) und **Satz-Splicing als Crossover**. Die Kreuzung passiert stattdessen im Prompt:
das Modell darf Stärken einer früheren Fassung mit der aktuellen kombinieren. Ohne Messgröße
sind Prozentversprechen („30–80% Qualitätssteigerung") bedeutungslos — der ehrliche Gewinn ist
Konsistenz und Passung, nicht „das Modell wird klüger".

**Merge cards (Dubletten).** `dream.find_merge_pairs` detects near-duplicate `MemoryObject`
pairs deterministically — **bewusst aggressiv** seit der Traum-Log-Runde (ein False Positive
kostet einen Klick auf der Bestätigungskarte, eine verpasste Dublette bleibt ewig): cosine ≥
`MERGE_COSINE` (0.82, war 0.86) **oder** Token-**Containment** ≥ `MERGE_OVERLAP` (0.75) —
`dream.text_overlap()`: geteilte signifikante Tokens / kleinere Menge, Stopwörter inkl.
„user/nutzer" gestrippt (`_OVERLAP_STOP`), Mindest-Überlappung 3 Tokens. Containment (statt
des alten Jaccard ≥0.8, das nie ansprach) fängt den Praxisfall „gleicher Fakt, eine Fassung
trägt Zusatzdetail". Beide Signale werden IMMER geprüft (ein schwaches Embedding versteckt
keine Text-Dublette mehr); greedy nach max(cos, overlap), each row in one pair. The card shows both texts +
an editable suggestion (longer text) → `POST /dream/merge` → `repository.merge_global_memory`
(thin wrapper over `merge_memory_objects` — keeps the first survivor's row, sums hits, marks
`source="user"`) → confirmation only (no OOB — the target list lives behind the Hera-Profil
dropdown now, always a different screen than the merge card itself). Pairs ≥0.90 never exist —
write-dedup catches those earlier. **Auch für Strategien:** `find_strategy_merge_pairs` läuft
`find_merge_pairs` **pro kind** (`repository.MIND_OBJECT_KINDS` — skill/unterbewusst/mem_ex
strikt getrennt, nie gemischt, `kind`-Spaltenfilter auf `MindObject`); tragen seit v0.3.0
**auch für skill/unterbewusst ein Embedding** (vorher hatte `Strategy` keine `embedding`-
Spalte, weshalb dieser Pfad immer auf Jaccard zurückfiel). Die Merge-Karte trägt ein
`target`-Feld (`global` | `strategy:<kind>`); `POST /dream/merge` routet danach →
`merge_global_memory` (dünner Wrapper über `merge_memory_objects`) bzw. `merge_strategies`
(behält die Datei der Gewinner-Zeile mit dem zusammengeführten Inhalt — ein Commit, nullt
zusätzlich deren `embedding`, da sich der Inhalt geändert hat und der nächste Backfill-Pass es
neu berechnet — war zwischenzeitlich ein Bug, das alte Embedding blieb stehen, jetzt gefixt —
löscht die Verlierer-Datei + -Zeile; summiert hits/negative_signals). Sowohl `dream_run` als
auch `/memory/hygiene` sammeln beide Merge-Quellen ein.

**Wartung (ohne Träumen).** Two deterministic-or-single-call maintenance actions on the
**Hera-Profil**-Screen (`routes/hera/profile/maintenance/{hygiene,translate}.py`), separate from the LLM dream: **`POST
/memory/hygiene`** (no LLM) surfaces the same merge cards + weak-strategy cards standalone
(`find_merge_pairs` + `find_weak_strategies`, `hygiene=True` flag → tailored empty message).
**`POST /memory/translate`** brings all stored entries to English in place: `dream.
translate_texts()` does ONE batched, count-validated, **fail-safe** call (model failure /
line-count mismatch ⇒ returns `None` ⇒ nothing changes); the route translates global-memory
content, entity notes/relations (names kept) — `MemoryObject` rows, plain DB write — **and**
skill/subconscious/mem_ex content — `MindObject` rows (`repository.MIND_OBJECT_KINDS`),
translated content is `mind.write_and_commit`ed (one commit per changed file, message
`"Translate {kind} #{id}"`) rather than a column update. NULLs changed embeddings and
re-backfills either way, reports `X von Y` + OOB-refreshes every list (harmless dead weight
unless that exact section happens to be open in the Hera-Profil dropdown at the time — same
precedent as every other cross-context OOB in this file). Already-English entries stay
unchanged; reversible via edit/delete (+ DB backup for MemoryObject, + git revert for
MindObject) either way.

**Entities** (`MemoryObject(kind="person"|"ort")`: name·notes·relations·source·hits — war
`models.Entity`): a structured memory tier next to gedaechtnis/projekt (skill/unterbewusst
moved to the git-backed mind, see above), same table since v0.3.0. CRUD in `repository`
(`add_entity`, unchanged-signature wrapper over
`add_memory_object`, still de-dupes by (name,kind) and enriches notes/relations), injected
into the system prompt as a compact "BEKANNTE PERSONEN & ORTE" block (`context.
_format_entities` — unchanged, field names match by design). Manual mgmt via
`/memory/entity/{add,delete}`; global-memory mgmt via `/memory/global/{add,delete}` — both
now on `routes/hera/profile/memory/{global_memory,entities}.py`.

Nightly/scheduled runs + deeper hygiene (explicit merge cards, promote/age) are the next step.

### Verhaltensprofile (behaviour profiles, per project)
`BehaviorProfile` (name · `traits` = comma-separated keys · `free_text`) replaces the old
free-text persona Setting: a checkbox-composable behaviour bundle. The **trait catalog lives
in code** (`prompts.BEHAVIOR_TRAITS`: locker/formell/knapp/ausfuehrlich/humor/kritisch/
lehrer — curated German blocks in the same voice as the `character`/`role` mind regions).
Resolution per turn (`repository.resolve_behavior_profile`): chat → project
(`Project.behavior_profile_id`) → profile, else default profile (Setting
`default_behavior_profile`), else none; dangling ids fall back. `prompts.render_behavior_profile`
joins blocks + free text under `DEIN VERHALTEN IN DIESEM PROJEKT` — it **complements** the
persona mind regions (never replaces them) and is always wrapped in its own
`<hera:behavior_profile>` tag, **re-attached after `prompt_override`** regardless of override
(same philosophy as `<hera:capabilities>`/`<hera:safety>`). Managed behind the **Hera-Profil**
dropdown's „Verhalten" entry since Teil 4 (`render_profiles`, unchanged
`routes/profiles.py`, partials `behavior_profiles.html`/`behavior_profile_edit.html`, swaps
`#behavior-profiles` — same self-contained-root-id pattern as every other collection section);
assigned in the project editor (`<select>`). **Migration:** a non-empty legacy persona Setting
becomes profile „Standard" (free_text, set as default) on boot and the Setting is cleared
(`_migrate_persona_to_profile`); `config.persona` (the flat about_you+role+character+tone
concatenation) still complements it the same way.

### Alltags-UX: Stop · Retry · Auto-Titel
- **Stop:** the composer swaps Senden→Stop while streaming (`body[data-streaming]`, CSS).
  Stop = `EventSource.close()` — **no server endpoint**: the disconnect cancels the SSE
  generator (`CancelledError`/`GeneratorExit`); `chats/stream.py` catches it and
  `chats/_shared.py`'s `_persist_aborted` parses the in-flight buffer (`live_raw`), appends
  `warn "Antwort abgebrochen."`, and persists via the SHARED `_persist_turn` helper incl.
  remember/improve side effects (no
  embeddings in the abort path — never await after cancellation). Network drops get the
  same treatment. No orphaned pending state.
- **Retry:** `POST /messages/{id}/retry` — only the chat's LAST assistant message (else
  400); clears content/segments/trace, returns `assistant_pending.html` → stream.js reopens
  the stream. Button in `_msg_actions.html`, gated purely by CSS
  (`.messages .msg-assistant:last-child .msg-retry`). Alternation stays valid (empty
  `content_raw` is filtered from context).
- **Auto-Titel:** the `done` payload carries `suggest_title` when the chat still has a
  default title („Neuer Chat"/„Erster Chat"). stream.js then fires
  `POST /chats/{id}/autotitle` (chat id via `data-chat-id` on the pending shell) —
  **after** the stream, never delaying it. The route makes one small LLM call (effort low,
  max 5 Wörter; harmony-normalized, quotes/period stripped); ANY failure ⇒ fallback =
  truncated first user message. Response = `chatlist.html` (primary swap) + OOB
  `#chat-title` span.
- **Settings-Card „Kontext & Gedächtnis":** keep_full_turns, context_budget,
  memory_token_cap, embedding_model (change ⇒ wipe + sync backfill of vectors).

### Deploy-Härtung (Mac Mini)
`deploy/install-macos.sh` bootstraps the venv itself (`python3 -m venv` + pip install) and
gained an **`update`** subcommand (git pull --ff-only → pip install → plist re-render →
kickstart → health check). Health check polls **`GET /healthz`** (public, in `app.py`
allow-list): `{status, db}`; `?llm=1` also probes `{api_base_url}/models` →
`llm: ok|unreachable` (app itself always 200). LLM-down errors are actionable German
(`client.py` branches ConnectError/ReadTimeout → „Läuft LM Studio? … ‚Verbindung testen'");
the Modelle screen has a **„Verbindung testen"** button (`POST /models/test`, tests the
SAVED URL, never 500). `requirements.txt` carries upper bounds.

### Message actions · search · export · backup
- **Per-message actions** (`_msg_actions.html` on every bubble; survives the stream `done`
  innerHTML replace since it sits outside `.msg-body`): **copy** (message + a per-code-block
  button added by `app.js decorateCode`, with a plain-HTTP clipboard fallback), **merken**
  (`POST /messages/{id}/remember` → user-sourced Merkzettel from the *prose*, not CALL markup),
  **delete** (`DELETE /messages/{id}`, empty outerHTML swap + `HX-Trigger: hera:context-updated`).
- **Cross-chat search**: `repository.search_messages` (LIKE over message bodies + titles, one
  hit/chat with a snippet; FTS5 is a future upgrade). Search box in `chatlist.html` →
  `GET /search` → `search_results.html`, click opens the chat.
- **Chat → vault export** (`routes/chats/export.py`): `POST /chats/{id}/export-vault` renders the chat
  as Markdown (cleaned prose) and writes it via `vault.write_note` into the first writable vault
  (`Hera-Chats/…`). Button in the chat header. **DB backup**: `GET /backup` streams `hera.db`
  (Einstellungen → *Daten & Backup*).

### Auth & multi-device (single-user)
Hera is one server + one SQLite DB = the single source of truth; laptop & phone reach
the **same** server (Mac Mini via WireGuard), so multi-device is reachability, not sync.
`app.py::require_login` middleware gates every route except an allow-list (`/login`,
`/logout`, `/static/*`, `/manifest.webmanifest`, `/sw.js`, icons). Unauth → HX-Redirect
header for HTMX, 401 for `/api`, else 303 to `/login`. Password (PBKDF2) + cookie secret
+ profile name live in the `Setting` table (`backend/auth.py`, `backend/repository` helpers). First run
with no password → `/login` becomes onboarding; `HERA_AUTH_PASSWORD` bootstraps it.
**Any new verify script must log in first** (POST `/login`) or every route 303s.

### PWA & responsive
`manifest.webmanifest` + `sw.js` served at root by `routes/pwa.py` (SW needs root scope).
SW is **network-first** and touches **only** `/static/*` (cache is just an offline
fallback) — never HTML/SSE/API (would break streaming); registered in `app.js` only when
`window.isSecureContext` (no-op over plain HTTP, so live edits always show over LAN http). iOS gets the
standalone look via Safari "Add to Home Screen" + apple-meta without HTTPS. `base.html`
carries manifest/theme-color/apple tags. Mobile: `hera.css` `@media (max-width:760px)`
collapses the 4-col grid to one column chosen by `#app[data-view]`, driven by the
`.mobile-nav` bottom bar (`app.js`). Deploy as a launchd LaunchAgent via `deploy/`.

## Conventions

- **No raw SQL in routes** — go through `backend/repository.py`. Session is `autoflush=False`, so
  call `session.flush()` before a render that must read back what you just wrote.
- **SQLite migrations**: add columns via `repository._migrate_columns()` (PRAGMA + ALTER).
- **HTMX**: partials swap by `hx-target`; the rest updates out-of-band (`hx-swap-oob`).
  Fragments in `templates/fragments/` compose partials (one primary + OOB siblings).
- **New verb** = entry in `calls.RENDER_CALLS` (or a tool in `tools.TOOLS`, or `SILENT_CALLS`)
  + a branch in `_segments.html` + a branch in `stream.js renderSegment`. The surface prefix
  (EMOTION/NOTE/TRACE/CALL) is cosmetic — dispatch is by **canonical verb** (`calls.canonical_verb`);
  add a `(prefix, verb)` mapping there if the verb is prefix-specific (like NOTE read/write). Keep
  `calls.py` and `stream.js` in sync (regex, canonicalisation, prose capture). `parse_calls(raw,
  capture_prose=True)` keeps prose between the lines as `say` (prose-first, call+free).
- **New icon** = path in `partials/_icons.html`; if used live, also add to `stream.js ICONS`.
- **Theme**: `data-theme` on `<html>` (`system|light|dark`); dark palette in `hera.css`
  via `:root[data-theme="dark"]` + a `prefers-color-scheme` block for `system`. Style both.
- **Message array must alternate** user/assistant after a single leading system message —
  inject context by folding into the system prompt or the user turn, never a mid-conversation
  system message (breaks Ministral/GPT-OSS templates → empty answers).
- Commit/push only when asked. Co-author trailer as configured.

## Feature state (implemented)

- 4-column workspace; projects & chats CRUD (rename, delete, project icon/colour edit;
  last project protected).
- Model + reasoning-effort pickers in the composer; model label above each answer; Markdown
  rendering incl. **pipe tables**, **thematic breaks** (`---`/`***`/`___` → `<hr>`, checked
  before the table branch so a bare `---` isn't mistaken for a table separator) and **LaTeX math** (`md.js` emits `.math[data-tex]`,
  `HeraMD.renderMath` renders via vendored **Temml** → MathML — `static/js/temml.min.js` +
  `static/css/Temml-Local.css`+`Temml.woff2`, no CDN; `$$…$$`/`\[…\]` block, `\(…\)`/
  conservative `$…$` inline; raw TeX stays as fallback); loading-dots animation during
  model-load/TTFT wait (`.msg-loading`, kept until first output by `stream.js`). Code blocks
  use `--code-bg`/`--code-border` (distinct from the bubble's `--surface-2`).
- Streaming CALL pipeline; agent tool loop; websearch (DuckDuckGo / SearXNG).
- Notes + AI Merkzettel injected into context; `remember` writing (prompt pushes it hard).
- Dark mode (system-aware + toggle).
- Obsidian vaults: mentions + autocomplete + search/read tools + confirmed writes + PDF.
- Single-user auth (login + profile name, PBKDF2 + signed cookie); first-run onboarding.
- PWA: manifest + service worker + icons (installable); responsive mobile layout.
- Deploy: launchd LaunchAgent for the Mac Mini (`deploy/`); desktop-wrapper recipe.
- Per-model profiles (mode call/free/native_tools, tuned prompt, temp, effort, tools) on their
  own *Modelle* rail screen; native OpenAI tool-calling incl. **native write-actions**
  (vault_write/remember/improve via one SPOT registry). Self-improvement strategies +
  `improve()`. Free mode interleaves prose + expressive CALLs; trace-leak stripping.
- **Trace compaction** (silent `trace` CALL → `Message.trace`, older turns collapsed into the
  system prompt) + **context-budget meter** in the chat header; keep_full_turns/context_budget
  jetzt in den Einstellungen.
- **Memory** mit **Embedding-Retrieval** (LM Studio `/v1/embeddings`, Keyword-Fallback),
  Write-Dedup (normalize + Cosine 0.90, jetzt auch beim Anlegen von skill/unterbewusst/mem_ex,
  s. Teil 4), Caps pro Ebene, hits-Tracking, Alters-Hinweisen und **Epistemik-Block**
  (`mem_instr`-Region) gegen Über-Inferenz; auto/manuell badges. Seit v0.3.0 die
  MemoryObject-Ebenen (gedaechtnis/person/ort/projekt) in einer Tabelle, skill/unterbewusst/
  mem_ex im git-hinterlegten `MindObject`.
- **Träumen** (Karte auf dem Hera-Profil, kein eigener Screen mehr): manual reflection **in eigener Persona** → **typed** candidate
  cards (Gedächtnis/Herangehensweise/Unterbewusstsein/Gedächtnis-Beispiel/Person/Ort/Projekt/
  Wunsch/**Mind-Region-Vorschlag** für jede der 9 träum-mutierbaren Regionen) mit
  **OR-Varianten** („beste gewinnt"), accepted into their bucket, plus **Merge-Karten** für
  Dubletten und **Weak-Strategy-Karten** (hits/negative_signals). Model name above the bubble
  shows the profile's display name (`model_label`).
- **Hera-Profil** (own rail screen): seit Teil 4 EIN Dropdown über alle Prompt-Bereiche
  (15 Mind-Regionen + Gedächtnis + Personen&Orte + Projekte + Herangehensweisen +
  **Skills (Import)** + Unterbewusstsein + Gedächtnis-Beispiele + Verhalten, 23 Einträge)
  statt sieben immer-sichtbaren Boxen — ein Inhaltsbereich, serverseitig mit dem ersten
  Bereich vorgerendert, Mind-Regionen als Textarea (dynamische Höhe, echte Editor-Styles)
  +Git-Log+Revert, Sammlungen mit **Typ-Badge** (`_memory_badge.html`) unverändert
  wiederverwendet. Plus **Wartung ohne Träumen**: `/memory/hygiene` (Dubletten + schwache
  Einträge, kein LLM) und `/memory/translate` (Einträge in-place auf Englisch, batched +
  fail-safe) sowie Trainingsdaten und die Träumen-Karte, eigene immer sichtbare Karten.
- **Import-Skills**: benannte `SkillDoc`-Pakete (Hera-Profil → „Skills (Import)"), im Prompt
  nur als `<skill_library>`-Namensliste; das Modell lädt sie per `CALL import_skills(name="…")`
  (oder native Funktion) on demand — Inhalt kommt als `[TOOL RESULTS]` zurück. Positional-
  Fallback im Parser (`import_skills("Coding")` funktioniert).
- **Traum-Log**: rechte Spalte des Hera-Profils (ersetzt dort Notizen/Merkzettel per
  OOB-Swap) — pro Träumen-Durchlauf Input-Material mit Sektions-Chips (inkl.
  „Trainingsdaten"), System-Prompt, Gedanken (Thinking-Deltas) und rohe Ausgabe;
  **automatisch/live** (Persist pro Pass + Panel-Polling während des Träumens),
  auto-gekappt auf 30 Einträge, per Button leerbar. Durchläufe als freies Zahlenfeld
  (bis 30); aggressive Dubletten-Erkennung (Cosine 0.82 ODER Token-Containment 0.75),
  Fuzzy-Drop bekannter Umformulierungen + Fuzzy-Collapse über Mehrfach-Pässe,
  [compact]-Dubletten-Scan als Pflichtteil des Traum-Prompts. `?v=`-Cache-Buster auf
  allen statischen Assets.
- **Mind-Region-Registry, echtes Git (v0.3.0-Teil-3, generalisiert in Teil 4)**:
  `~/.hera/mind/` ist ein echtes Git-Repo (`src/core/mind.py`), jede der 15 Regionen
  (`src/core/ctx/mind_regions.py`) eine eigene Datei — Accept = Commit, Revert = neuer
  vorwärtsgerichteter Commit, Reject = `MindRejection`-Zeile (nie ein Commit). Drei
  Governance-Stufen: träum-mutierbar (9 Regionen, echte Generation via Commit-Anzahl),
  owner-fest (7 Regionen — Sicherheit, Antwortformat, Entwickler-Nachricht, … — vom Modell nie
  vorschlagbar, aber jederzeit über die UI direkt editierbar, gleicher Git-Pfad wie ein
  Dream-Accept), Nutzer-Einstellung (`language_preference`, ein reines Setting). Modell
  mutiert, Nutzer selektiert (accept/reject/revert, mit Diff-Vorschau + Generations-Nummer auf
  der Kandidatenkarte), verworfene Fassungen fließen als Gegenbeispiele in den nächsten Traum.
  Checkbox-Gruppe „Bereiche weiterentwickeln" (pro Region erzwingbar), hohe Traum-Temperatur,
  Mehrfach-Durchläufe, `threading.RLock()`-serialisierte Commits (Concurrency-getestet); keine
  automatische Übernahme, kein Selbst-Judge. Der Workflow-Track formt Tool-Nutzung, nie
  Tool-Verdrahtung (fehlende Tools = `[wish]`). Zwei Migrationen: `_migrate_mind_to_git`
  repliziert die komplette Alt-Historie (DB-Zeilen aus `prompt_variants`) als rückdatierte
  Commits; `_migrate_persona_regions` (Teil 4) spielt das alte `persona.md` ebenso
  zurückdatiert nach `character.md` zurück, statt die Generation neu bei 1 zu starten.
- **Externe Trainingsdaten** (`TrainingDoc`): Text-/Markdown-Dateien über das Hera-Profil
  einwerfen/pausieren/entfernen; aktive Dateien fließen als Meister-Demonstrationen ins Träumen
  (eigenes Budget, als Lektion destilliert, nie als Nutzer-Fakt). `scope` als Naht für spätere
  Profil-Trainings.
- **Englischer System-Prompt** (Persona-Regionen/Antwortformat/Header/Träumen/Übersetzen/
  Agent-Feedback), Antworten in der Sprache des Nutzers (die `language`-Region, owner-gesteuert
  über die `language_preference`-Einstellung). Seit v0.3.0 als Sequenz XML-getaggter Sections
  zusammengesetzt (`<hera:persona>` verschachtelt, `<hera:safety>`, `<memory:*>`,
  `<emotions:*>`, `<tools:*>`, `<budget:token_budget>`, `<user:user_preferences>`, …) — nur die
  Text-Struktur, nicht die CALL/EMOTION-Grammatik, siehe *Model profiles & output modes* und
  *Prompt structure: mind regions* oben.
- **Verhaltensprofile**: ankreuzbare Trait-Profile (+Freitext), pro Projekt zuweisbar oder als
  Standard; Legacy-Persona automatisch migriert. Verwaltung seit Teil 4 im Hera-Profil-Dropdown.
- **Message actions** (copy incl. code blocks, merken, **retry/regenerate**, delete),
  **Stop-Button** (Abbruch persistiert Teilantwort), **Auto-Titel** für neue Chats,
  **cross-chat search**, **chat→vault export**, **DB backup**.
- **Deploy-Härtung**: install-macos.sh mit venv-Bootstrap + `update`-Befehl + Healthcheck,
  `/healthz`, freundliche LLM-Fehler, „Verbindung testen" auf dem Modelle-Screen.

## Not yet built (future)

Media upload/vision, `hera-cli` API client, multi-step coder pipeline, **autonomous**
model-driven self-improvement (scaffold exists: strategies + `improve()`), structured-output
mode, a dedicated vault-browser panel, HTTPS/Caddy for full PWA install (Chrome).
Memory/reflection next steps: **scheduled (nightly) Träumen**, promote local→global /
age out (hits-Tracking liegt schon vor), FTS5 for cross-chat search. The pipeline is a step chain so
these can dock on. Deferred from the v0.3.0 refactor (`thinking/REFACTOR.md`) — git-based
`~/.hera/mind/` versioning itself now shipped (Teil 3), and the fine-grained per-field
Prompt-Baukasten idea now shipped too (Teil 4, `mind_regions.py`): still open is **"Hera Agents"**
(branch creation + binding a branch to a chat/model, so e.g. a "Lehrer" branch can diverge
and keep dreaming on its own — the mind repo currently stays on a single `main` branch by
design), real enforcement of `<budget:token_budget>` (documentation-only today), chat header
profile picture / `Profil: Modellname` display, custom project/chat icons + a better
hover-naming UX. Plans:
`thinking/archive/PLAN.md` (v0.1.0 stabilization) + `thinking/IDEEN.md`
(idea backlog) + `thinking/NOTIZEN.md` (aktuelle Beobachtungen), multi-device plan in `~/.claude/plans/`.

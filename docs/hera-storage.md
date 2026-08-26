# Auftrag: Bibliothek `hera_storage` bauen

Du baust eine eigenständige Python-Bibliothek in einem leeren Repository. Sie ist das Fundament eines größeren Systems (`hera`), aber sie darf davon **nichts** wissen.

## Kontext

`hera` ist ein persönliches Agentic-Framework, aufgeteilt in mehrere unabhängige Python-Pakete mit je eigenem Repo:

```
heraAPI (FastAPI-Anwendung, verdrahtet alles)
  hera_profiles       hera_promptevo
  hera_tools          hera_memories       hera_skillsets
  hera_prompts        hera_providers      hera_permissions     hera_chats
                              hera_storage          <-- dieses Repo
```

Abhängigkeiten zeigen ausschließlich nach unten. `hera_storage` steht ganz unten und importiert **keine** andere `hera_*`-Bibliothek — jetzt nicht und nie.

Die Domänen-Bibliotheken darüber (`hera_chats`, `hera_memories`, `hera_promptevo`, `hera_profiles`) definieren jeweils ihre **eigenen** SQLModel-Tabellen und erben dafür von den Basisklassen aus `hera_storage`. Sie kennen einander nicht; Querverweise zwischen Bibliotheken existieren nur als lose `UUID`-Felder ohne ForeignKey-Constraint. Verknüpfende Tabellen leben in `heraAPI`.

## Die eine harte Regel

**`hera_storage` enthält keine einzige Tabelle und kein einziges Domänenkonzept.** Kein Chat, keine Message, kein Prompt, kein Provider, kein Memory. Wenn du beim Schreiben das Wort "Chat" tippst, ist etwas falsch. Die Bibliothek muss unverändert in einem völlig anderen Projekt (z. B. einer Rezeptverwaltung) einsetzbar sein.

Zweite Regel: keine `table=True`-Klasse in dieser Bibliothek. Alle Basisklassen sind Mixins ohne eigene Tabelle.

## Technische Vorgaben

- Python 3.12+, Typannotationen überall, `from __future__ import annotations`.
- Abhängigkeiten: `sqlmodel`, `pydantic-settings`. Sonst nichts. **Kein Alembic** als Laufzeitabhängigkeit — Migrationen laufen in `heraAPI`; wir stellen nur die `MetaData` und die Naming-Convention bereit.
- Build mit `uv` und `hatchling`, Paketname `hera-storage`, Importname `hera_storage`.
- **Synchrones** SQLAlchemy, keine Async-Sessions. Begründung: Zielumgebung ist SQLite auf einem Mac Mini für einen einzelnen Nutzer; DB-Zugriffe liegen im Mikrosekundenbereich, während die eigentliche Latenz bei den LLM-Aufrufen liegt. Async würde nur Komplexität ohne Nutzen einführen. Die Session-API muss aber threadsicher benutzbar sein (Session pro Request, niemals global geteilt).
- Primärdatenbank ist SQLite; PostgreSQL soll ohne Codeänderung funktionieren (keine SQLite-spezifischen Typen in der öffentlichen API).

## Öffentliche API

Alles Folgende ist aus `hera_storage` direkt importierbar. Halte dich an diese Signaturen — sie sind der Vertrag, auf den fünf andere Bibliotheken bauen werden.

### 1. Settings

```python
class StorageSettings(BaseSettings):
    # env-Prefix: HERA_STORAGE_
    url: str = "sqlite:///hera.db"
    echo: bool = False
    sqlite_wal: bool = True
    busy_timeout_ms: int = 5000
    pool_size: int = 5
```

### 2. Database

```python
class Database:
    def __init__(self, settings: StorageSettings | None = None, *, url: str | None = None) -> None
    @classmethod
    def from_env(cls) -> Database
    @classmethod
    def in_memory(cls) -> Database          # StaticPool, für Tests

    @property
    def engine(self) -> Engine
    @property
    def metadata(self) -> MetaData          # SQLModel.metadata, für Alembic in heraAPI

    @contextmanager
    def session(self) -> Iterator[Session]  # commit bei Erfolg, rollback bei Exception, immer close
    def dependency(self) -> Callable[[], Iterator[Session]]   # für FastAPI Depends()
    def create_all(self) -> None            # nur Tests/Bootstrap, nicht für Produktivmigrationen
    def dispose(self) -> None
```

Bei SQLite-URLs setzt ein `connect`-Event-Listener zwingend:
`PRAGMA journal_mode=WAL` (wenn `sqlite_wal`), `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=<busy_timeout_ms>`.
Für `in_memory()` zusätzlich `StaticPool` und `check_same_thread=False`, sonst sieht jeder Verbindungsversuch eine leere DB.

### 3. Basisklassen (Mixins, kein `table=True`)

```python
class EntityStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"

class Entity(SQLModel):
    id: UUID              # default_factory=uuid4, primary_key
    created_at: datetime  # UTC, default_factory
    updated_at: datetime  # UTC, onupdate

class SoftDeletable(SQLModel):
    status: EntityStatus = EntityStatus.ACTIVE
    revoked_at: datetime | None = None

class Versioned(SQLModel):
    version: int = 1
    supersedes_id: UUID | None = None   # zeigt auf die vorherige Version
    origin: str | None = None           # "manual" | "dream:<uuid>" | "selection:gen7"
    is_current: bool = True
```

`updated_at` muss auch bei reinem Attribut-Setzen ohne expliziten Aufruf aktualisiert werden — über `sa_column_kwargs={"onupdate": ...}`, nicht über manuelles Setzen im Repository.

Alle drei Mixins müssen frei kombinierbar sein: `class Foo(Entity, SoftDeletable, Versioned, table=True)` muss ohne MRO- oder Feldkonflikte funktionieren. Schreib dafür einen expliziten Test.

Exportiere außerdem `NAMING_CONVENTION: dict[str, str]` (Standard-SQLAlchemy-Konvention für `ix`/`uq`/`ck`/`fk`/`pk`) und wende sie auf die MetaData an. Ohne benannte Constraints scheitert Alembics Batch-Modus unter SQLite bei jeder Spaltenänderung — das ist der Grund, warum das hier steht.

### 4. Repository

```python
T = TypeVar("T", bound=SQLModel)

class Repository(Generic[T]):
    def __init__(self, model: type[T], session: Session) -> None

    def get(self, id: UUID, *, include_revoked: bool = False) -> T | None
    def get_or_raise(self, id: UUID, *, include_revoked: bool = False) -> T
    def list(self, *where: Any, order_by: Any = None, limit: int | None = None,
             offset: int = 0, include_revoked: bool = False) -> list[T]
    def add(self, obj: T) -> T
    def add_all(self, objs: Iterable[T]) -> list[T]
    def save(self, obj: T) -> T
    def revoke(self, id: UUID) -> T        # setzt status + revoked_at
    def restore(self, id: UUID) -> T
    def hard_delete(self, id: UUID) -> None
    def count(self, *where: Any, include_revoked: bool = False) -> int
    def exists(self, id: UUID) -> bool
```

Wichtig: `include_revoked=False` filtert nur, wenn das Modell tatsächlich von `SoftDeletable` erbt — sonst wird der Parameter ignoriert statt einen Fehler zu werfen. `revoke`/`restore` werfen `TypeError`, wenn das Modell nicht soft-löschbar ist.

`Repository` ist als Basisklasse zum Ableiten gedacht: Domänen-Bibliotheken schreiben `class ChatRepository(Repository[Chat])` und ergänzen fachliche Methoden. Dokumentiere das im README mit einem Beispiel.

### 5. Versionierung

```python
def new_version(session: Session, obj: V, *, origin: str, **changes: Any) -> V
def version_history(session: Session, model: type[V], id: UUID) -> list[V]
def current_version(session: Session, model: type[V], id: UUID) -> V | None
```

`new_version` kopiert das Objekt, übernimmt `**changes`, setzt `version += 1`, `supersedes_id = obj.id`, `origin`, vergibt eine neue `id`, setzt `is_current=False` auf dem alten Objekt und `True` auf dem neuen. Es wird ein Snapshot pro Version gespeichert, kein Diff.

`version_history` folgt der `supersedes_id`-Kette rückwärts und gibt die Versionen chronologisch aufsteigend zurück. Es muss auch dann terminieren, wenn die Kette durch einen Fehler zyklisch wäre — bau eine Schutzgrenze ein.

### 6. Fehler

```python
class StorageError(Exception): ...
class NotFound(StorageError): ...       # trägt model_name und id
class Conflict(StorageError): ...       # für IntegrityError-Wrapping
```

`Database.session()` fängt `IntegrityError` und wirft `Conflict` mit der ursprünglichen Exception als `__cause__`. Andere DB-Fehler werden nicht verschluckt.

### 7. Test-Unterstützung

Ein Modul `hera_storage.testing` mit pytest-Fixtures (`db`, `session`), registriert als pytest-Plugin über den `pytest11`-Entry-Point in `pyproject.toml`. Damit bekommt jede Domänen-Bibliothek `def test_x(session): ...` geschenkt, ohne Setup zu duplizieren.

## Konventionen, die du im README dokumentierst

- **Tabellenpräfixe.** Jede Domänen-Bibliothek setzt `__tablename__` explizit mit eigenem Präfix (`chat_messages`, `mem_entries`, `evo_generations`). Alle Modelle landen in derselben `MetaData`, also kollidieren gleichnamige Tabellen aus zwei Bibliotheken sonst still.
- **Keine bibliotheksübergreifenden ForeignKeys.** Verweise auf Entitäten anderer Bibliotheken sind nackte `UUID`-Felder. Integrität stellt die Anwendungsschicht her, nicht die DB.
- **Migrationen laufen in heraAPI.** Dort werden alle Bibliotheken importiert, wodurch sich ihre Modelle registrieren; `alembic autogenerate` sieht dann das Gesamtschema. Schreib das als kurzen Abschnitt ins README, inklusive Hinweis auf `render_as_batch=True` für SQLite.

## Qualitätsanforderungen

- `ruff` (lint + format) und `mypy --strict` laufen ohne Befund.
- pytest mit In-Memory-SQLite. Die Tests definieren sich ihre eigenen Dummy-Modelle (`class Widget(Entity, SoftDeletable, Versioned, table=True)`) — es gibt in dieser Bibliothek nichts Fachliches zu testen.
- Testabdeckung mindestens 90 % auf `repository.py` und `versioning.py`.
- Mindestens diese Fälle explizit abgedeckt: Rollback bei Exception im `session()`-Block; `include_revoked` auf einem Modell ohne `SoftDeletable`; `revoke` auf einem Modell ohne `SoftDeletable` wirft; kombinierte Mixin-Vererbung; `new_version` über drei Generationen mit korrekter Historie; `Conflict` bei Unique-Verletzung; WAL-Pragma wird auf Datei-SQLite tatsächlich gesetzt.
- README mit: Zweck, Installation, 20-Zeilen-Quickstart, Beispiel für ein abgeleitetes Repository, Abschnitt zu Migrationen, und einem expliziten Abschnitt "Was hier **nicht** hineingehört".

## Reihenfolge

1. `pyproject.toml`, Repo-Struktur (`src/hera_storage/`), Tooling-Konfiguration.
2. `settings.py`, `errors.py`, `base.py`.
3. `database.py` inklusive SQLite-Pragma-Listener.
4. `repository.py`.
5. `versioning.py`.
6. `testing.py` und Entry-Point.
7. Tests.
8. README.

Halte nach Schritt 3 kurz an und zeig mir die Basisklassen plus `Database`, bevor du weiterbaust — daran hängt alles Weitere, und ein Fehler dort ist später teuer.

## Nicht bauen

Kein Caching, kein Connection-Retry, kein Event-/Outbox-System, keine Volltextsuche, keine Embeddings, kein Multi-Tenancy, keine Async-Variante, keine CLI. Wenn dir während der Arbeit ein Feature sinnvoll erscheint, das hier nicht steht: nicht einbauen, sondern am Ende als Vorschlag nennen.

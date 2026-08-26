# hera-storage

The persistence foundation every other `hera_*` library sits on: settings, an engine with
sane SQLite defaults, three composable model mixins, a generic repository, snapshot
versioning, and pytest fixtures.

It contains **no table and no domain concept**, imports no other `hera_*` package, and
would work unchanged in a recipe manager.

- Python 3.12+, synchronous SQLAlchemy
- Runtime dependencies: `sqlmodel`, `pydantic-settings` — nothing else
- SQLite is the primary target; PostgreSQL works without code changes

## Installation

Inside this workspace, depend on it by name — uv resolves it to the member:

```toml
dependencies = ["hera-storage"]
```

Outside, it installs like any package (`uv add hera-storage`); pin a compatible range,
`hera-storage>=0.1,<0.2`.

Linting, typing and tests are configured once in the workspace root and run from there:

```bash
uv run ruff check . && uv run mypy
uv run coverage run -m pytest && uv run coverage report
```

## Quickstart

```python
from sqlmodel import Field
from hera_storage import Database, Entity, Repository, SoftDeletable

class Recipe(Entity, SoftDeletable, table=True):
    __tablename__ = "cook_recipes"          # always set your own prefixed name
    title: str
    servings: int = Field(default=2)

db = Database.from_env()                    # or Database(url="sqlite:///cookbook.db")
db.create_all()                             # bootstrap only; production uses migrations

with db.session() as session:               # commits on success, rolls back on error
    recipes = Repository(Recipe, session)
    soup = recipes.add(Recipe(title="Onion soup", servings=4))
    recipes.add(Recipe(title="Bad idea", servings=1))

with db.session() as session:
    recipes = Repository(Recipe, session)
    recipes.revoke(soup.id)                 # soft delete: the row stays, queries skip it
    print(recipes.count())                  # 1
    print(recipes.count(include_revoked=True))  # 2
```

## The public API

| | |
|---|---|
| `StorageSettings` | `url`, `echo`, `sqlite_wal`, `busy_timeout_ms`, `pool_size`, from `HERA_STORAGE_*` |
| `Database` | `from_env()`, `in_memory()`, `engine`, `metadata`, `session()`, `dependency()`, `create_all()`, `dispose()` |
| `Entity`, `SoftDeletable`, `Versioned` | mixins, freely combinable, none of them a table |
| `EntityStatus` | `ACTIVE`, `REVOKED` |
| `UTCDateTime`, `utcnow` | timestamp column type and clock, both aware UTC |
| `Repository[T]` | `get`, `get_or_raise`, `list`, `add`, `add_all`, `save`, `revoke`, `restore`, `hard_delete`, `count`, `exists` |
| `MAX_VERSION_CHAIN` | upper bound for both chain walks |
| `new_version`, `version_history`, `current_version` | snapshot versioning |
| `StorageError`, `NotFound`, `Conflict` | errors |
| `NAMING_CONVENTION` | applied to `SQLModel.metadata` on import |

### Deriving a repository

`Repository` is meant to be subclassed. Domain methods go in the subclass; the generic
CRUD comes for free, including the soft-delete filter.

```python
from sqlmodel import Session
from hera_storage import Repository

class RecipeRepository(Repository[Recipe]):
    def __init__(self, session: Session) -> None:
        super().__init__(Recipe, session)

    def for_a_crowd(self, at_least: int) -> list[Recipe]:
        return self.list(Recipe.servings >= at_least, order_by=Recipe.title)
```

### Ordering and pagination

`list()` orders by `(created_at, id)` by default. This is a correctness matter, not a
convenience: an unordered query may come back in a different order on every call, and
`limit`/`offset` would then skip or repeat rows between pages. `created_at` alone is not
enough — rows inserted in the same batch share a timestamp — hence the `id` tiebreaker.

**An explicit `order_by` replaces the default entirely, tiebreaker included.** If you page
through results, add your own tiebreaker:

```python
repo.list(order_by=(Recipe.title, Recipe.id), limit=20, offset=40)
```

Models that do not inherit `Entity` have no default order, since they have no `created_at`.

`Entity` ships a composite index on `(created_at, id)` to back this. It comes from a
`declared_attr`, so each table gets its own — but a model that declares its own
`__table_args__` **shadows it** and silently loses the index. Such a model should include
`Index(None, "created_at", "id")` itself. `SoftDeletable.status` and `Versioned.is_current`
are indexed too, being the columns every default query filters on.

### Where the transaction begins and ends

Repository methods **flush, never commit**. The single commit happens when the
`db.session()` block exits, so writes across several repositories form one atomic unit of
work and an exception anywhere rolls all of them back.

```python
with db.session() as session:
    Repository(Recipe, session).add(...)
    Repository(Ingredient, session).add(...)
    raise RuntimeError            # nothing is written
```

An `IntegrityError` — from a flush or from the final commit — is re-raised as `Conflict`,
with the original exception as `__cause__`. Every other database error passes through
untouched.

### Versioning

Each version is a full row linked backwards through `supersedes_id`; there are no diffs.

```python
v2 = new_version(session, v1, origin="manual", title="Onion soup, revised")
# v1.is_current is now False, v2.version == 2, v2.supersedes_id == v1.id

version_history(session, Recipe, v2.id)   # [v1, v2], oldest first
current_version(session, Recipe, v1.id)   # v2
```

Both walks are bounded by `MAX_VERSION_CHAIN`: `supersedes_id` carries no foreign key, so
a cycle is possible in principle and must never hang the process.

### Timestamps

`created_at` and `updated_at` are **always timezone-aware UTC**, on every backend and on
every read path — plain queries, `refresh()`, and the implicit reload after a commit. No
`tzinfo` juggling downstream:

```python
age = utcnow() - recipe.created_at        # just works, no TypeError
```

That guarantee comes from `UTCDateTime`, a `TypeDecorator` around `DateTime(timezone=True)`:
SQLite stores no offset, so the bare type would hand back naive values from SQLite while
PostgreSQL returned aware ones, and arithmetic against an aware "now" would then fail on one
backend only. Values written are converted to UTC; a naive input is *assumed* to be UTC
rather than local time, because guessing the machine's timezone would make the same data
mean different things on two machines.

Use it for your own timestamp columns:

```python
from hera_storage import UTCDateTime

class Recipe(Entity, table=True):
    cooked_at: datetime | None = Field(default=None, sa_type=UTCDateTime())
```

The DDL is exactly what `DateTime(timezone=True)` produces — SQLite `DATETIME`,
PostgreSQL `TIMESTAMP WITH TIME ZONE` — so this is a Python-side guarantee, not a schema
feature. A row written by another tool straight into the database is still normalised on
read, but a naive value in the file is indistinguishable from a UTC one.

`updated_at` maintains itself through the column's `onupdate` — plain attribute assignment
is enough, no repository call and no manual stamping.

### Testing

Installing this package registers a pytest plugin, so every downstream library gets two
fixtures with no conftest of its own:

```python
def test_recipes(session):          # in-memory SQLite, fresh per test
    Repository(Recipe, session).add(Recipe(title="x"))
```

`db` gives you the `Database`, `session` an open unit of work. The `session` fixture
commits at teardown, so a test that expects a `Conflict` on commit should open its own
`db.session()` block. Importing `hera_storage.testing` requires pytest; it is not a runtime
dependency.

## Conventions

### Table prefixes

Every library sets `__tablename__` explicitly, with its own prefix:

| library | prefix | example |
|---|---|---|
| `hera_chats` | `chat_` | `chat_messages` |
| `hera_memories` | `mem_` | `mem_entries` |
| `hera_promptevo` | `evo_` | `evo_generations` |

All models land in the same `MetaData`. Two libraries that both define a `messages` table
would silently collide.

### No cross-library foreign keys

A reference to an entity owned by another library is a bare `UUID` field with no
`ForeignKey` constraint. Integrity across library boundaries is the application's job, not
the database's. Linking tables belong in `apps/api`.

### Migrations run in `apps/api`

This package deliberately does not depend on Alembic. It provides the `MetaData` and the
naming convention; the migration environment lives in `apps/api`, which imports every
library — that import is what registers the models, and only then does
`alembic autogenerate` see the complete schema.

```python
# apps/api/alembic/env.py
import hera_chats, hera_memories, hera_profiles, hera_promptevo   # noqa: F401
from hera_storage import Database

target_metadata = Database.from_env().metadata

context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,       # required: SQLite cannot ALTER a column in place
)
```

`render_as_batch=True` rebuilds the table for every column change, which only works if
constraints have deterministic names — that is what `NAMING_CONVENTION` is for.

`Database.create_all()` exists for tests and first-run bootstrapping. It does not track
schema versions; do not use it in production.

## What does **not** belong here

This package is the bottom of the dependency graph. Anything that knows what the data
*means* belongs one layer up.

- **No tables.** Not one `table=True` class. All base classes are mixins.
- **No domain concepts.** No chat, message, prompt, provider, memory, profile, skillset.
  If the word "chat" appears in this repository outside of documentation, something is
  wrong.
- **No imports of other `hera_*` libraries.** Not now, not later. Dependencies point one
  way only.
- **No linking tables** between libraries — those live in `apps/api`.
- **No migrations.** Alembic is not a dependency here.
- **Not built on purpose:** caching, connection retry, event/outbox systems, full-text
  search, embeddings, multi-tenancy, an async variant, a CLI.

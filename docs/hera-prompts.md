# Auftrag: Bibliothek `hera_prompts` bauen

Du baust eine eigenständige Python-Bibliothek in einem leeren Repository. Sie ist ein Prompt-Compiler: Sie hält einen strukturierten, serialisierbaren Prompt-Zustand und übersetzt ihn in fertige Nachrichten für ein LLM.

## Kontext

`hera` ist ein persönliches Agentic-Framework, aufgeteilt in unabhängige Pakete mit je eigenem Repo:

```
heraAPI (FastAPI-Anwendung, verdrahtet alles)
  hera_profiles       hera_promptevo
  hera_tools          hera_memories       hera_skillsets
  hera_prompts        hera_providers      hera_permissions     hera_chats
                              hera_storage
```

Abhängigkeiten zeigen ausschließlich nach unten. `hera_prompts` liegt auf der Fundamentebene und importiert **keine** andere `hera_*`-Bibliothek — auch nicht `hera_storage`. Es hat keinerlei Persistenz, keine I/O, kein Netzwerk.

Zielmodelle sind kleine lokale Modelle (gpt-oss-20b über LM Studio, teils 3B-Klasse). Das prägt die Voreinstellungen: schlichte Grammatik schlägt Verschachtelung.

## Die drei harten Regeln

1. **Kein Domänenwissen.** `hera_prompts` weiß nicht, was ein Tool, ein Memory, ein Skill oder ein Chat ist. Fremde Inhalte kommen ausschließlich als vorgerenderte Strings über benannte Slots herein.
2. **Kein Evolutionsvokabular.** In dieser Bibliothek dürfen die Wörter Generation, Fitness, Population, Selektion, Elternteil, Traum und Mutation nicht vorkommen — weder in Bezeichnern noch in Docstrings. Sie hält Zustand und wendet Änderungen an; wer die Änderungen erzeugt und bewertet, ist ihr unbekannt.
3. **Alles ist unveränderlich und serialisierbar.** Jede Transformation gibt ein neues Objekt zurück. Ein `Prompt` muss verlustfrei durch `model_dump_json()` und zurück gehen — sonst kann ihn die darüberliegende Schicht nicht speichern.

## Technische Vorgaben

- Python 3.12+, Typannotationen überall, `from __future__ import annotations`.
- Einzige Laufzeitabhängigkeit: `pydantic` v2. **Kein** tiktoken, kein Jinja, kein lxml.
- Build mit `uv` und `hatchling`. Paketname `hera-prompts`, Importname `hera_prompts`.
- `ruff` und `mypy --strict` ohne Befund; `py.typed` im Wheel.
- Determinismus ist Vertrag: gleiches Objekt plus gleiche Bindings ergibt byteweise gleiche Ausgabe. Alle Iterationen über Dicts laufen in definierter Reihenfolge (Traits sortiert nach Schlüssel).

## Datenmodell

### Rollen und Nachrichten

```python
class Role(StrEnum):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"

class Message(BaseModel):
    role: Role
    content: str
```

`Message.model_dump()` ergibt bereits `{"role": ..., "content": ...}` — die Abbildung auf ein konkretes Anbieterformat ist Sache von `hera_providers`, nicht von uns.

### Section

```python
class Section(BaseModel):
    key: str                      # stabile Adresse, "behavior.character"
    title: str | None = None
    content: str | None = None    # verfasster Text
    slot: str | None = None       # ODER Name eines Platzhalters
    children: list[Section] = []
    role: Role = Role.SYSTEM      # nur auf oberster Ebene ausgewertet
    priority: int = 100           # niedriger fliegt bei Budgetdruck zuerst
    required: bool = False
    locked: bool = False
    enabled: bool = True
```

Validierung beim Konstruieren, nicht erst beim Rendern:

- `key` erfüllt `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`.
- Der `key` eines Kindes beginnt mit dem `key` des Elternteils plus Punkt.
- Alle `key` im Baum sind eindeutig.
- `content` und `slot` schließen einander aus; Sektionen mit `children` haben keines von beidem.

Diese Regeln existieren, weil der Vorgängerprompt von Hand gepflegt wurde und auseinanderlief (öffnender Tag `<hera:behavior>`, schließender `</Hera_behavior>`). Struktur wird generiert, nie getippt.

### Traits

```python
TraitValue = bool | str | int

class TraitSpec(BaseModel):
    key: str                                  # wie Section.key, Präfix = Zielsektion
    type: Literal["str", "bool", "int"]
    default: TraitValue | None = None
    description: str = ""                     # für die erzeugende Schicht
    choices: list[TraitValue] | None = None
    render: dict[str, str] | str | None = None
    locked: bool = False

class TraitRegistry(BaseModel):
    specs: list[TraitSpec]
    allow_unknown: bool = True

    def get(self, key: str) -> TraitSpec | None
    def validate_value(self, key: str, value: TraitValue) -> None   # wirft TraitError
    def fingerprint(self) -> str
```

`render` ist entweder ein Mapping von Wert auf Satz (`{"never": "Erfinde nichts. Wenn du etwas nicht weißt, sag es."}`) oder eine Vorlage mit `{value}`. Fehlt es, oder ist der Trait der Registry unbekannt, fällt jeder Renderer auf das rohe Paar zurück.

`allow_unknown=True` erlaubt Traits, die in keiner Spec stehen. Das ist der Modus, in dem die darüberliegende Schicht eigene Traits erfinden darf; `False` erzwingt die deklarierte Menge. Beides muss ohne Codeänderung umschaltbar sein.

### Patch

```python
class TraitPatch(BaseModel):
    changes: dict[str, TraitValue | None]     # None bedeutet löschen
    rationale: str | None = None

class RejectedChange(BaseModel):
    key: str
    reason: Literal["locked", "unknown_trait", "invalid_value", "invalid_key"]

class PatchResult(BaseModel):
    prompt: Prompt
    applied: dict[str, TraitValue | None]
    rejected: list[RejectedChange]
```

`apply()` wirft **nicht**, wenn ein Patch gegen eine Sperre läuft — es verwirft die Änderung und vermerkt sie in `rejected`. Ein Aufrufer, der wiederholt gesperrte Traits anfasst, ist ein Signal, das die obere Schicht sehen will; ein Abbruch würde stattdessen einen ganzen Lauf töten.

### Prompt

```python
class Prompt(BaseModel):
    sections: list[Section]
    traits: dict[str, TraitValue] = {}
    locked_traits: set[str] = set()
    renderer: RendererConfig = RendererConfig()

    # Navigation
    def paths(self) -> list[str]
    def get(self, key: str) -> Section | None

    # Transformation, jeweils neues Objekt
    def replace(self, key: str, *, content: str | None = None, title: str | None = None) -> Prompt
    def insert(self, parent: str, section: Section, *, after: str | None = None) -> Prompt
    def remove(self, key: str) -> Prompt
    def reorder(self, parent: str, order: list[str]) -> Prompt
    def set_enabled(self, key: str, enabled: bool) -> Prompt
    def apply(self, patch: TraitPatch, *, registry: TraitRegistry | None = None) -> PatchResult

    # Identität
    def fingerprint(self) -> str

    # Ausgabe
    def render(self, *, bindings: Mapping[str, str] | None = None,
               registry: TraitRegistry | None = None,
               budget: TokenBudget | None = None) -> RenderResult
```

`replace`, `remove` und `reorder` respektieren `Section.locked` genauso wie `apply` die `locked_traits` respektiert: Änderung verworfen, nicht geworfen. Bei `replace`/`remove` gibt es dafür keinen Rückgabekanal — dokumentiere, dass diese Methoden bei gesperrten Sektionen das unveränderte Objekt zurückgeben, und stell eine Hilfsmethode `is_locked(key)` bereit.

`fingerprint()` ist ein SHA-256 über kanonisches JSON von Sektionen, Traits und Renderer-Konfiguration mit sortierten Schlüsseln. Zwei Prompts mit identischem Rendering müssen denselben Fingerprint haben, sonst wird identische Arbeit doppelt ausgeführt.

Modulfunktion `diff(a: Prompt, b: Prompt) -> PromptDiff` mit getrennten Feldern für geänderte Sektionen, geänderte Traits und geänderte Renderer-Optionen.

## Rendering

```python
class RendererConfig(BaseModel):
    format: Literal["keyvalue", "xml", "markdown"] = "keyvalue"
    qualified_tags: bool = True          # <behavior:character> statt <character>
    constraints_first: bool = True       # Traits vor verfasstem Text
    developer_role: Literal["fold_into_system", "native"] = "fold_into_system"
    trait_group_separator: str = " "     # "BEHAVIOR tone = terse"
```

Die Konfiguration steckt **im** Prompt-Objekt, nicht als Argument daneben. Nur so ist eine gespeicherte Variante vollständig durch das Objekt beschrieben — und nur so kann die obere Schicht auch das Format selbst variieren.

`developer_role="fold_into_system"` ist Default, weil LM Studio und Ollama über ihre OpenAI-kompatiblen Endpunkte Developer-Nachrichten bestenfalls still in System-Nachrichten falten. Beim Falten werden die Developer-Sektionen hinter die System-Sektionen in **eine** Nachricht gehängt.

### Trait-Routing

Der Schlüssel bestimmt das Ziel: `behavior.tone` rendert in die Sektion `behavior`, `formatting.max_words` in `formatting`. Ein Trait ohne Punkt landet in einem allgemeinen Block am Anfang der System-Nachricht. Zeigt ein Präfix auf eine nicht existierende oder deaktivierte Sektion, wandert der Trait ebenfalls in den allgemeinen Block — nicht verwerfen, nicht werfen.

### Trait-Darstellung je Format

- `keyvalue`: immer das rohe Paar, `GROUP name = value`. Die `render`-Vorlage wird bewusst ignoriert — diese Grammatik ist selbst das Signal.
- `xml` und `markdown`: die `render`-Vorlage, ersatzweise das rohe Paar.

Das ist eine Verhaltensdifferenz zwischen Renderern und muss als solche getestet sein.

### Slots

`bindings` ist ein Mapping von Slot-Name auf fertigen String. Ein Slot ohne Binding lässt die Sektion entfallen; ist sie `required=True`, wirft `MissingBinding`. Ein Binding ohne passenden Slot wirft nicht, sondern erscheint in `RenderResult.unused_bindings`.

### Budget

```python
class TokenBudget(BaseModel):
    limit: int
    counter: Callable[[str], int]     # Default: len(text) // 4
    reserve: int = 0                  # für die erwartete Antwort
```

Übersteigt das Rendering das Budget, werden Sektionen aufsteigend nach `priority` entfernt und erneut gerendert, bis es passt. `required=True` schützt vor dem Entfernen; bleibt es danach zu groß, wirft `BudgetExceeded`. Entfernte Schlüssel stehen in `RenderResult.dropped_keys` — dieses Feld existiert, damit später nachvollziehbar ist, ob ein schlechtes Ergebnis daran lag, dass Inhalte wegen Budgetdruck fehlten.

### Ergebnis

```python
class PromptSnapshot(BaseModel):
    content_hash: str                 # SHA-256 über die gerenderten Nachrichten
    prompt_fingerprint: str
    registry_fingerprint: str | None
    renderer: RendererConfig
    traits: dict[str, TraitValue]
    dropped_keys: list[str]
    token_estimate: int
    component_versions: dict[str, UUID] = {}   # von der oberen Schicht gefüllt

class RenderResult(BaseModel):
    messages: list[Message]
    snapshot: PromptSnapshot
    unused_bindings: list[str]
```

`PromptSnapshot` ist ein reines Modell ohne Tabelle — persistiert wird er in `heraAPI`.

Dokumentiere ausdrücklich: `messages` ist der **Rahmen**, nicht der vollständige Verlauf. Eine Gesprächshistorie gehört zwischen die System-Nachricht(en) und die letzte User-Nachricht und wird von der aufrufenden Schicht eingefügt. `hera_prompts` kennt keine Historie.

### Escaping

Der XML-Renderer escapet `<`, `>` und `&` in Inhalten. Der KeyValue-Renderer lehnt Trait-Werte mit Zeilenumbruch oder `=` mit `TraitError` ab, weil sie die Grammatik brechen würden.

## Fehler

```python
class PromptError(Exception): ...
class SectionError(PromptError): ...      # ungültiger key, Duplikat, content+slot
class TraitError(PromptError): ...        # unbekannt bei allow_unknown=False, Typ, choices
class MissingBinding(PromptError): ...
class BudgetExceeded(PromptError): ...
```

## Referenzbeispiel

Dieses Beispiel gehört als Doctest oder als Test mit exakt erwarteter Ausgabe ins Repo. Es pinnt die Semantik fest.

Objekt: Sektionen `identity` (SYSTEM, locked), `behavior` mit Kind `behavior.character` (DEVELOPER), `tools` (DEVELOPER, slot `tools`, locked), `memories` (USER, slot), `request` (USER, slot, required). Traits `behavior.tone="terse"` und `behavior.hallucinate="never"`. Renderer `keyvalue`, `constraints_first=True`.

Erwartete System-Nachricht:

```
#IDENTITY
Du bist Hera, eine aufmerksame Assistentin mit eigenem Kopf.

#BEHAVIOR
BEHAVIOR tone = terse
BEHAVIOR hallucinate = never
Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das.

#TOOLS
CALL search(query=~~QUERY~~)
```

Erwartete User-Nachricht:

```
#MEMORIES
MEMORY city = Chemnitz

#REQUEST
Wie war das nochmal mit der Ablation?
```

Dasselbe Objekt mit `format="xml"` ergibt für `behavior`:

```xml
<behavior>
  <behavior:constraints>
    Antworte knapp. Kein Vorspann, kein Nachklang.
    Erfinde nichts. Wenn du etwas nicht weißt, sag es.
  </behavior:constraints>
  <behavior:character>
    Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das.
  </behavior:character>
</behavior>
```

Beachte den Unterschied: derselbe Trait erscheint einmal als `BEHAVIOR tone = terse`, einmal als ausformulierter Satz aus der `render`-Vorlage.

## Tests

Mindestens diese Fälle je als eigener Test:

- JSON-Round-Trip eines vollständigen Prompts, danach identischer `fingerprint()`.
- Zweimaliges `render()` desselben Objekts liefert byteweise identische Ausgabe.
- Beide Referenzbeispiele oben mit exakter Zeichenkettengleichheit.
- Trait mit `render`-Vorlage: keyvalue liefert das rohe Paar, xml den Satz.
- Trait auf unbekanntes Präfix landet im allgemeinen Block.
- `apply()` mit gesperrtem Trait: Prompt unverändert, Eintrag in `rejected`, keine Exception.
- `apply()` mit `None` löscht den Trait.
- `apply()` bei `allow_unknown=False` und unbekanntem Schlüssel: `rejected` mit Grund `unknown_trait`.
- `replace()` auf gesperrter Sektion gibt unverändertes Objekt zurück.
- Ungültiger Kind-`key` ohne Elternpräfix wirft `SectionError`.
- Slot ohne Binding entfällt; mit `required=True` wirft er `MissingBinding`.
- Budget entfernt die Sektion mit niedrigster `priority` zuerst und listet sie in `dropped_keys`.
- Budget mit ausschließlich `required`-Sektionen über Limit wirft `BudgetExceeded`.
- `developer_role="fold_into_system"` erzeugt genau eine System-Nachricht; `"native"` erzeugt zwei.
- Trait-Wert mit `=` oder Zeilenumbruch wirft im keyvalue-Renderer `TraitError`.
- XML-Renderer escapet spitze Klammern im Content.
- `diff()` zwischen Eltern- und Kindobjekt listet genau die drei geänderten Traits.

Abdeckung mindestens 95 % auf `render/` und `prompt.py`.

## Reihenfolge

1. `pyproject.toml`, Repo-Struktur (`src/hera_prompts/`), Tooling.
2. `models.py` — Role, Message, Section, RendererConfig samt Validierung.
3. `traits.py` — TraitSpec, TraitRegistry, TraitPatch, PatchResult.
4. `prompt.py` — Prompt mit Navigation, Transformationen, `apply`, `fingerprint`, `diff`.
5. `render/` — Protokoll, KeyValueRenderer, XMLRenderer, MarkdownRenderer, Budget.
6. `snapshot.py`, `errors.py`.
7. Tests, README.

Halte nach Schritt 3 an und zeig mir Section, Prompt-Signaturen und TraitSpec, bevor du das Rendering baust. Das ist der Vertrag, gegen den vier andere Bibliotheken schreiben werden.

## Nicht bauen

Keine Prompt-Vererbung oder Overlays (Basis plus Patch-Prompt), keine Template-Engine, keine Variableninterpolation im Content, kein Caching, kein Tokenizer, keine Persistenz, keine Historienverwaltung, kein Tool-, Memory- oder Skill-Wissen, keine Anbieterspezifika über die drei Rollen hinaus. Fällt dir unterwegs etwas Sinnvolles auf, das hier nicht steht: nicht einbauen, sondern am Ende als Vorschlag nennen.

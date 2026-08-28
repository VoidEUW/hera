"""Where every package is joined up.

The one place in the system that knows all of them. Each library takes what it needs as an
injected dependency and names no concrete class, which is what lets the whole application be
exercised against ``FakeProvider`` — so this module is also the seam the tests replace.

Two wirings worth pointing at, because they are the ones the layering rules exist for:

``hera_tools`` may not import ``hera_skillsets``, so ``hera__skill`` reaches the library
through a **port**. ``SkillLibraryPort`` is shaped to fit without either package knowing about
the other, and the check that they really do fit lives in this package's tests — the only place
both may be imported.

``hera_skillsets`` may not import ``hera_providers``, so retrieval would reach embeddings the
same way — and in v0.1 it does not, deliberately. ``SkillRouter.select()`` is synchronous
because everything else it does is a file read, and ``hera_chats`` runs it in a worker thread
through ``asyncio.to_thread``. Calling back into the event loop from there needs the loop
handle threaded down to the embedder, and getting that subtly wrong deadlocks a turn. ADR 5
names keyword overlap as the supported fallback and it is what runs, so the cost of leaving
this until the retrieval work in v0.2 is *worse ranking*, not a missing feature. `Embedder` is
the seam it lands on.
"""

from __future__ import annotations

from dataclasses import dataclass

from hera_chats import ChatsSettings, TurnOrchestrator
from hera_core.config import load as load_config
from hera_core.scratch import FileScratchpad
from hera_core.search import DuckDuckGo
from hera_core.settings import CoreSettings
from hera_home import mind_dir, skills_dir
from hera_mcp import ASK_TOOL, BUILTIN_SERVER_NAME, CHAT_ID_META, build_builtin_server
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, PromptBuilder
from hera_providers import OpenAICompatibleProvider, Provider, ProviderSettings
from hera_skillsets import SkillLibrary, SkillLibraryPort, SkillRouter
from hera_storage import Database, StorageSettings
from hera_tools import ToolRegistry, ToolsSettings

DEFAULT_POLICY = Policy(
    base=PermissionSet(
        rules=[
            Rule(
                pattern="hera__*",
                decision=Decision.ALLOW,
                reason="one of her own tools, none of which changes anything outside Hera",
            )
        ]
    ),
    fallback=Decision.ASK,
)
"""What a deployment with no permission rules of its own gets.

``ask`` for everything is the right default for a *foreign* tool — a tool nobody has an opinion
about is exactly the case a person should see once. It is the wrong default for hers.
``hera__emotion`` is called several times in an ordinary turn (ADR 3), and a confirmation card
for each one would make the feature unusable and teach a person to click through cards without
reading them, which is the failure that matters.

**``hera__search`` leaves the machine, and is still allowed.** It is the first of her tools that
does, so the old sentence here — *they reach only her own mind, memories and skills* — is no
longer the reason. The reason is that a search **reads** something public and changes nothing:
a card before every lookup would cost a click for each of the three or four searches a real
question takes, which is the same unusability ``emotion`` would have had. What travels is a
query the model wrote, to whichever engine ``hera_core.search`` is pointed at, and a person who
does not want that writes one rule to deny it. The tool that would deserve a card is a *fetch* —
an arbitrary URL is a request to a machine somebody chose, and `http://192.168.1.1/` is not the
same act as a search (``docs/tooling.md`` § 1).
"""


@dataclass
class Services:
    """Everything the routes reach for, built once at startup.

    A dataclass rather than a container framework: there are seven of these, they are all
    singletons, and the wiring is a hundred lines that should be readable top to bottom.
    """

    settings: CoreSettings
    database: Database
    mind: MindRepository
    builder: PromptBuilder
    library: SkillLibrary
    router: SkillRouter
    registry: ToolRegistry | None
    provider: Provider
    orchestrator: TurnOrchestrator

    owns_provider: bool = False
    """Whether closing this container should close the provider.

    Defaults to **False**, so ownership is something the creator claims rather than something a
    hand-built container inherits. ``build_services`` sets it when it constructed the provider
    itself; a test passing its own ``FakeProvider`` keeps it, and a reconfiguration must not
    close something it did not open.
    """

    async def use_provider(self, provider: Provider, *, model: str = "") -> None:
        """Point her at a different endpoint, without a restart.

        Changing the model is something a person does while trying to get Hera working at all,
        and telling them to restart the server to find out whether the URL was right turns a
        two-second correction into a minute.

        ``model`` travels with the provider because the two are one decision: the endpoint
        knows where to send a request and ``ChatsSettings.model`` decides what name goes in the
        body, and leaving the second behind would point a new server at the old model's name —
        which fails as an unhelpful 404 from somebody else's API.
        """
        previous, owned = self.provider, self.owns_provider
        self.provider = provider
        self.orchestrator.provider = provider
        if model:
            self.orchestrator.settings = self.orchestrator.settings.model_copy(
                update={"model": model}
            )
        self.owns_provider = True
        if owned:
            # Closed after the swap, so a request arriving mid-change gets the new client
            # rather than a closed one. A stream already running keeps its response: httpx
            # finishes what it has begun.
            await previous.aclose()

    @property
    def model(self) -> str:
        """The model name requests are sent with. What the health check reports."""
        return self.orchestrator.settings.model

    async def aclose(self) -> None:
        """Release everything that holds a connection or a subprocess open."""
        if self.registry is not None:
            await self.registry.aclose()
        if self.owns_provider:
            await self.provider.aclose()
        self.database.dispose()


def build_services(
    settings: CoreSettings | None = None,
    *,
    provider: Provider | None = None,
    database: Database | None = None,
    registry: ToolRegistry | None = None,
    policy: Policy | None = None,
) -> Services:
    """Assemble the application.

    Every argument is an override, and every override exists for the tests: a ``FakeProvider``,
    an in-memory database, a scripted registry. Production passes none of them.
    """
    settings = settings or CoreSettings()
    database = database or Database(StorageSettings(url=settings.database_url()))

    # config.toml is the source of truth for the endpoint, seeded from HERA_PROVIDER_* the
    # first time it is written -- see hera_core.config.
    entry = load_config().active()
    provider_settings = entry.settings() if entry is not None else ProviderSettings()
    injected = provider is not None
    if provider is None:
        provider = OpenAICompatibleProvider(provider_settings)

    library = SkillLibrary(skills_dir())
    # No embedder yet -- see the module docstring. Keyword overlap is ADR 5's supported
    # fallback, so retrieval works; it just ranks worse than it eventually will.
    router = SkillRouter(library)

    if registry is None:
        registry = ToolRegistry.open(
            policy=policy if policy is not None else DEFAULT_POLICY,
            settings=ToolsSettings(),
            # hera_mcp imports no hera_* package at all, so the library arrives as a port, and
            # so does the search engine -- which one a person's questions are sent to is a
            # decision about this deployment and not about the server she is.
            # Memories and notes stay unwired until v0.2; the tools still appear in the
            # catalogue and answer "not available in this deployment", because a model that
            # cannot see `remember` concludes it cannot remember and says so to the person.
            builtin=build_builtin_server(
                skills=SkillLibraryPort(library),
                searcher=DuckDuckGo(),
                # Which conversation a write belongs to arrives per call, in `_meta` -- see
                # ChatsSettings.chat_meta_key below. This object is a singleton and knows
                # nothing about any one chat, which is the whole reason that mechanism exists.
                scratchpad=FileScratchpad(),
            ),
        )

    mind = MindRepository(mind_dir())
    builder = PromptBuilder(mind)

    return Services(
        settings=settings,
        database=database,
        mind=mind,
        builder=builder,
        library=library,
        router=router,
        registry=registry,
        provider=provider,
        owns_provider=not injected,
        orchestrator=TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=ChatsSettings(
                model=provider_settings.model,
                # The one place her `ask` tool is named to the turn layer. `hera_chats` does
                # not know what a Hera tool is and must not learn; it takes the qualified name
                # and suspends on it, the way it takes a policy rather than a list of rules.
                # Qualified here because `hera_tools` namespaces by server name, and that name
                # travels on the server object rather than being written twice.
                asking_tools=(f"{BUILTIN_SERVER_NAME}__{ASK_TOOL}",),
                # And the one place the key her scratchpad reads the chat id from is named to
                # the turn layer (ADR 12). `hera_tools` carries the mapping without looking in
                # it and `hera_mcp` reads it; neither may import the other, so the application
                # is what makes them agree -- exactly as it does for `ask` above.
                chat_meta_key=CHAT_ID_META,
            ),
        ),
    )

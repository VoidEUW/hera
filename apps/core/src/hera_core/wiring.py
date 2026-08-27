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
from hera_core.settings import CoreSettings
from hera_home import mind_dir, skills_dir
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, PromptBuilder
from hera_providers import OpenAICompatibleProvider, Provider, ProviderSettings
from hera_skillsets import SkillLibrary, SkillLibraryPort, SkillRouter
from hera_storage import Database, StorageSettings
from hera_tools import ToolRegistry, ToolsSettings, build_builtin_server

DEFAULT_POLICY = Policy(
    base=PermissionSet(
        rules=[
            Rule(
                pattern="hera__*",
                decision=Decision.ALLOW,
                reason="one of her own tools, which touch nothing outside Hera",
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
reading them, which is the failure that matters. Her four built-ins reach only her own mind,
memories and skills, so they are allowed and everything else still asks.
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

    async def aclose(self) -> None:
        """Release everything that holds a connection or a subprocess open."""
        if self.registry is not None:
            await self.registry.aclose()
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

    provider_settings = ProviderSettings()
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
            # hera_tools may not import hera_skillsets, so the library arrives as a port.
            # Memories and notes stay unwired until v0.2; the tools still appear in the
            # catalogue and answer "not available in this deployment", because a model that
            # cannot see `remember` concludes it cannot remember and says so to the person.
            builtin=build_builtin_server(skills=SkillLibraryPort(library)),
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
        orchestrator=TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=ChatsSettings(model=provider_settings.model),
        ),
    )

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

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from hera_chats import ChatsSettings, TurnOrchestrator
from hera_core import permission_rules
from hera_core.auth import Throttle
from hera_core.chat_files import FileArtifacts, FileScratchpad
from hera_core.config import load as load_config
from hera_core.enabled_skills import EnabledSkillPort, EnabledSkills
from hera_core.mail import Mailer, SmtpMailer
from hera_core.people import People, Person, PersonalMemories
from hera_core.search import DuckDuckGo
from hera_core.settings import CoreSettings
from hera_home import mind_dir, skills_dir
from hera_mcp import ASK_TOOL, BUILTIN_SERVER_NAME, CHAT_ID_META, build_builtin_server
from hera_memories import MemoriesSettings
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, PromptBuilder
from hera_providers import OpenAICompatibleProvider, Provider, ProviderSettings
from hera_skillsets import SkillLibrary, SkillRouter
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
Her tools are called several times in an ordinary turn — a scratchpad write, a memory, two
searches — and a confirmation card for each one would teach a person to click through cards
without reading them, which is the failure that matters.

**``hera__search`` leaves the machine, and is still allowed.** It is the first of her tools that
does, so the old sentence here — *they reach only her own mind, memories and skills* — is no
longer the reason. The reason is that a search **reads** something public and changes nothing:
a card before every lookup would cost a click for each of the three or four searches a real
question takes, which is unusable in the same way. What travels is a
query the model wrote, to whichever engine ``hera_core.search`` is pointed at, and a person who
does not want that writes one rule to deny it. The tool that would deserve a card is a *fetch* —
an arbitrary URL is a request to a machine somebody chose, and `http://192.168.1.1/` is not the
same act as a search (#259).
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
    """The mind **template** (ADR 28): what an admin edits, what a new person's mind is cloned
    from, and where the shared regions are read from for everybody."""
    builder: PromptBuilder
    """A builder over the template alone. A turn speaks from its person's builder instead
    (:meth:`for_user`); this one is the orchestrator's fallback."""
    library: SkillLibrary
    router: SkillRouter
    people: People
    """Each person's mind, builder and memories, built when first asked for."""
    registry: ToolRegistry | None
    provider: Provider
    orchestrator: TurnOrchestrator

    default_policy: Policy = field(default_factory=Policy)
    """The rules this deployment ships with, before a person's own are laid over them. Kept so the
    Permissions screen can say which rule is built in, and so deleting an override puts the
    built-in one back (``hera_core.rulebook``)."""

    throttle: Throttle = field(default_factory=Throttle)
    """Failed sign-in and setup-code attempts, per address and per email. Process-wide, so it is
    here rather than built per request."""

    mailer: Mailer = field(default_factory=SmtpMailer)
    """Where invitations and resets go out. ``[mail]`` in ``config.toml`` says *how*, read at each
    send, so changing the server on screen needs nothing rebuilt."""

    owns_provider: bool = False
    """Whether closing this container should close the provider.

    Defaults to **False**, so ownership is something the creator claims rather than something a
    hand-built container inherits. ``build_services`` sets it when it constructed the provider
    itself; a test passing its own ``FakeProvider`` keeps it, and a reconfiguration must not
    close something it did not open.
    """

    async def use_provider(
        self,
        provider: Provider,
        *,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        tool_calling: bool | None = None,
    ) -> None:
        """Point her at a different endpoint, without a restart.

        Changing the model is something a person does while trying to get Hera working at all,
        and telling them to restart the server to find out whether the URL was right turns a
        two-second correction into a minute.

        ``model`` travels with the provider because the two are one decision: the endpoint
        knows where to send a request and ``ChatsSettings.model`` decides what name goes in the
        body, and leaving the second behind would point a new server at the old model's name —
        which fails as an unhelpful 404 from somebody else's API. ``None`` means "leave it
        alone"; ``""`` is a real value — a provider with no models registered — and must clear
        the live setting rather than leaving a since-removed model's name behind.

        ``options`` follows the same three-state rule and for a sharper version of the same
        reason: they are that *model's* request flags, so carrying the old model's over would
        send GLM-4.7's ``chat_template_kwargs`` to a server that has never heard of it. ``{}``
        is the ordinary value and must clear.

        ``tool_calling`` (ADR 19) is a fact about the same model, for the same reason -- carrying
        a previous model's ``False`` forward would silently withhold tools from one that can
        actually use them.
        """
        previous, owned = self.provider, self.owns_provider
        self.provider = provider
        self.orchestrator.provider = provider
        changes: dict[str, Any] = {}
        if model is not None:
            changes["model"] = model
        if options is not None:
            changes["extra"] = dict(options)
        if tool_calling is not None:
            changes["tool_calling"] = tool_calling
        if changes:
            self.orchestrator.settings = self.orchestrator.settings.model_copy(update=changes)
        self.owns_provider = True
        if owned:
            # Closed after the swap, so a request arriving mid-change gets the new client
            # rather than a closed one. A stream already running keeps its response: httpx
            # finishes what it has begun.
            await previous.aclose()

    def for_user(self, user_id: UUID) -> Person:
        """What belongs to this person: their mind, their builder, their memories."""
        return self.people.get(user_id)

    def tools_for(self, user_id: UUID) -> ToolRegistry | None:
        """The tool layer under this person's own permission rules, laid over the instance's.

        The same servers with another policy on top — free, and per turn, so a rule a person
        answered on a card a moment ago is already in force.
        """
        if self.registry is None:
            return None
        rules = self.for_user(user_id).rules()
        if not rules.rules:
            return self.registry
        return self.registry.with_policy(self.registry.policy.for_person(rules))

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
    model_options = entry.active_options() if entry is not None else {}
    model_tool_calling = entry.active_tool_calling() if entry is not None else True
    injected = provider is not None
    if provider is None:
        provider = OpenAICompatibleProvider(provider_settings)

    library = SkillLibrary(skills_dir())
    # No embedder yet -- see the module docstring. Keyword overlap is ADR 5's supported
    # fallback, so retrieval works; it just ranks worse than it eventually will.
    # The router sees only what is switched on; `library` stays whole for the settings screen.
    router = SkillRouter(EnabledSkills(library))

    # The mind in `~/.hera/mind` is the template now, and each person's own mind and memories
    # are built from it on first use (ADR 28). Memories are still files rather than rows -- a
    # directory and a ceiling (ADR 16) -- just one directory per person.
    mind = MindRepository(mind_dir())
    builder = PromptBuilder(mind)
    people = People(mind, memories=MemoriesSettings())

    # What this deployment ships with, and then what a person has decided over it: the rules in
    # `permissions.json` (made on the Permissions screen or answered "always" on a card) are laid
    # over the built-in policy, so they survive a restart (#109).
    shipped = policy if policy is not None else DEFAULT_POLICY
    if registry is None:
        registry = ToolRegistry.open(
            policy=permission_rules.apply(shipped, permission_rules.load()),
            settings=ToolsSettings(),
            # hera_mcp imports no hera_* package at all, so the library arrives as a port, and
            # so does the search engine -- which one a person's questions are sent to is a
            # decision about this deployment and not about the server she is.
            # Notes stay unwired; the tool still appears in the catalogue and answers "not
            # available in this deployment", because a model that cannot see a tool concludes
            # it cannot do the thing and says so to the person.
            builtin=build_builtin_server(
                skills=EnabledSkillPort(library),
                searcher=DuckDuckGo(),
                # Two tools and no way to list or delete, which is the design rather than an
                # omission: every enabled memory is already in her prompt, and `forget`
                # switches one off keeping the file (ADR 16).
                # Whose memory it is comes from the chat the call is part of, in `_meta`, the
                # same way the chat itself does (ADR 12, ADR 28).
                memories=PersonalMemories(people, database),
                # Which conversation a write belongs to arrives per call, in `_meta` -- see
                # ChatsSettings.chat_meta_key below. These objects are singletons and know
                # nothing about any one chat, which is the whole reason that mechanism exists.
                scratchpad=FileScratchpad(),
                # Her scratchpad and what she publishes are two directories and two ports, and
                # the reason belongs to the first: it was built to be somewhere she can think
                # out loud unread (ADR 13).
                artifacts=FileArtifacts(),
            ),
        )

    return Services(
        settings=settings,
        database=database,
        mind=mind,
        builder=builder,
        library=library,
        router=router,
        people=people,
        registry=registry,
        default_policy=shipped,
        provider=provider,
        owns_provider=not injected,
        orchestrator=TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=ChatsSettings(
                model=provider_settings.model,
                # The active model's own request flags, merged into the body last. Seeded here
                # and replaced by `use_provider` when a person switches models on the Models
                # screen, exactly as `model` is -- the two are one decision.
                extra=model_options,
                # Whether this model is offered a tool at all (ADR 19) -- the same seeded-here,
                # replaced-by-`use_provider` treatment as `extra` above, for the same reason.
                tool_calling=model_tool_calling,
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

"""The turn: one message in, one event stream out.

This is the loop `ARCHITECTURE.md` draws. Skills are chosen in code, the mind is compiled into
a prompt, the slots are filled with what the layers below produced, the model is asked, and
every tool call it makes is checked and run — round and round until it stops asking for tools.

Three properties are worth stating up front, because each one is a decision that shows up in
the interface:

**Nothing here raises into the caller's loop.** A provider that dies, a stream that breaks, a
model that will not stop calling tools — each closes the turn with a reason and a last event.
The consumer is a Server-Sent Events response; an exception escaping mid-stream is a connection
that just stops, which the browser cannot tell from a network problem.

**Partial work survives.** ``Turn.recorded`` is complete at every moment, so whatever happened
before a cancellation or a failure is there to be persisted. That is what makes
``StreamInterrupted`` a `cancelled` turn with the answer so far, rather than a lost one.

**An ``ask`` stops the turn rather than blocking it.** The turn closes with
``awaiting_permission``, the events are persisted, and answering the card starts a *new* turn
that resumes the same message. A turn that held an HTTP response open waiting for a person
would be a turn that dies with the tab.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field

from hera_chats.events import (
    AnswerRequired,
    ChatEvent,
    CloseReason,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    coalesce,
)
from hera_chats.history import Attachment, content_of, says_something, turn_to_messages
from hera_chats.models import Chat, Project
from hera_chats.ports import Tools
from hera_chats.settings import ChatsSettings
from hera_permissions import Decision
from hera_profiles import (
    BEHAVIOUR_TRAITS,
    SLOT_EMOTIONS,
    SLOT_MEMORIES,
    SLOT_NOW,
    SLOT_PROJECT,
    SLOT_SKILLS,
    SLOT_TOOLS,
    Profile,
    PromptBuilder,
)
from hera_prompts import Message as FrameMessage
from hera_prompts import Role as FrameRole
from hera_providers import (
    ChatMessage,
    ChatRequest,
    Provider,
    ProviderError,
    Role,
    StreamInterrupted,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    ToolSpec,
    TurnEnd,
    Usage,
)
from hera_skillsets import SkillRouter
from hera_skillsets import render as render_skills
from hera_tools import ToolInvocation

_FRAME_ROLES = {
    FrameRole.SYSTEM: Role.SYSTEM,
    FrameRole.DEVELOPER: Role.DEVELOPER,
    FrameRole.USER: Role.USER,
}


@dataclass
class TurnContext:
    """Everything one turn needs that is not wiring.

    A dataclass rather than eleven keyword arguments, because ``apps/core`` assembles this
    from four repositories and passing it around as one thing is what keeps the assembly in
    one place.
    """

    text: str
    """What the person typed, ``/commands`` included — the router strips them."""

    chat: Chat | None = None
    project: Project | None = None
    profile: Profile | None = None

    history: Sequence[ChatMessage] = ()
    """The conversation so far, already rebuilt by :mod:`hera_chats.history`."""

    resume: Sequence[ChatEvent] = ()
    """Events of a turn being continued after a permission card was answered.

    Non-empty means this is the second half of an existing assistant message: skills were
    already chosen and are not chosen again, and the calls in here that have an answer in
    ``confirmed`` are dispatched before the model is asked anything.
    """

    confirmed: Sequence[str] = ()
    """Call ids a person has just allowed."""

    denied: Sequence[str] = ()
    """Call ids a person has just refused. Refused calls still get a result — the model is
    told it was not allowed, which is what lets it try something else instead of hanging."""

    answers: Mapping[str, str] = field(default_factory=dict)
    """Replies to questions she asked, by call id.

    The other half of :attr:`confirmed`. A confirmed call is *run* and its result comes from a
    tool; an answered one is not run at all and its result is what the person typed. Both
    arrive the same way — on a resumed turn, keyed by the call they settle — so the loop below
    handles them in one place.
    """

    attachments: Sequence[Attachment] = ()
    """Files sent with this message. Composed into the user turn by :func:`content_of`, which
    is the one place a file becomes something the model can read — fenced text, or a picture as
    a content part beside it."""

    memories: str = ""
    """Pre-rendered recall for the ``memories`` slot. Empty until v0.2."""

    now: str = ""
    """Pre-rendered date and time for the ``now`` slot.

    Pre-rendered like the rest, and for a reason beyond consistency: the *person's* timezone is
    a setting in ``config.toml``, and this package has no business reading it. Empty leaves the
    section out — a deployment that tells her nothing about the time is one where she does not
    claim to know it, which is better than one where she quietly assumes the server's clock is
    the person's.
    """

    emotions: str = ""
    """Pre-rendered stance vocabulary for the ``emotions`` slot.

    Pre-rendered, like everything else that arrives through a slot: this package does not know
    what an emotion is and should not learn. The application reads the person's list and calls
    ``hera_mcp.render_emotions``; empty leaves the section out, which is a deployment where she
    shows no stances rather than a broken one."""


@dataclass
class _Round:
    """One trip to the model."""

    calls: list[ToolCallReady] = field(default_factory=list)
    usage: Usage | None = None
    reason: str = "stop"


class Turn:
    """One user message becoming one assistant message.

    Built by :class:`TurnOrchestrator`, consumed once. Iterate :meth:`stream`, then persist
    :attr:`recorded` — which is why this is an object rather than a bare async generator: a
    generator cannot hand back what it produced when the consumer stops early, and stopping
    early is the ordinary case.
    """

    def __init__(
        self,
        context: TurnContext,
        *,
        provider: Provider,
        builder: PromptBuilder,
        router: SkillRouter,
        registry: Tools | None,
        settings: ChatsSettings,
    ) -> None:
        self.context = context
        self._provider = provider
        self._builder = builder
        self._router = router
        self._registry = registry
        self._settings = settings

        self._recorded: list[ChatEvent] = list(context.resume)
        # Where this turn's own output starts. Everything before it is the paused half of the
        # message, which the client is already rendering -- re-streaming it would draw the
        # skills and the permission card twice.
        self._inherited = len(self._recorded)
        self._closed = False
        self.prompt_fingerprint = ""
        self.skill_ids: list[str] = []
        self.cleaned_text = context.text

    @property
    def recorded(self) -> list[ChatEvent]:
        """Everything this turn has produced so far, coalesced and ready to persist.

        Correct at every moment, not only at the end. A cancelled turn is persisted from here.
        """
        return coalesce(self._recorded)

    @property
    def close_reason(self) -> CloseReason:
        """How the turn ended, or ``cancelled`` if it never closed itself."""
        last = self._recorded[-1] if self._recorded else None
        return last.reason if isinstance(last, TurnClosed) else "cancelled"

    async def stream(self) -> AsyncGenerator[ChatEvent, None]:
        """Run the turn, yielding events as they happen.

        An ``AsyncGenerator`` rather than an ``AsyncIterator``, because the consumer needs
        ``aclose()``: a browser that navigates away mid-answer is the ordinary way a turn
        ends early, and closing the generator is how that becomes a `cancelled` turn with the
        text so far rather than a task left running.
        """
        try:
            async for event in self._run():
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            # The consumer hung up. Close the record so the persisted list has a terminator,
            # then let the cancellation continue -- swallowing it would leave the task alive.
            self._close("cancelled")
            raise
        except ProviderError as exc:
            # Every httpx failure arrives here already normalised. StreamInterrupted is the one
            # worth naming: part of the answer did arrive, and it is worth keeping.
            reason: CloseReason = "cancelled" if isinstance(exc, StreamInterrupted) else "failed"
            yield self._close(reason, error=str(exc))

    async def _run(self) -> AsyncIterator[ChatEvent]:
        # The catalogue is fetched first: its rendered form is bound into the prompt, so the
        # prompt cannot be compiled before it is known.
        tools, catalogue_text = await self._tool_specs()
        messages = await asyncio.to_thread(self._prepare, catalogue_text)
        for event in self._recorded[self._inherited :]:
            if isinstance(event, SkillSelected):
                yield event

        pending = self._resumed_calls()
        if pending:
            async for event in self._answer(pending):
                yield event
            messages.extend(turn_to_messages(self._recorded))

        total = Usage()
        reported = False
        for iteration in range(1, self._settings.max_iterations + 1):
            round_ = _Round()
            async for event in self._ask(messages, tools, round_):
                yield event
            if round_.usage is not None:
                reported = True
                total = _add(total, round_.usage)

            if not round_.calls:
                yield self._close(
                    "completed", usage=total if reported else None, iterations=iteration
                )
                return

            blocked = self._blocked(round_.calls)
            if blocked:
                for call, reason in blocked:
                    yield self._record(
                        PermissionRequired(
                            call_id=call.id,
                            tool=call.name,
                            arguments=call.arguments,
                            reason=reason,
                        )
                    )
                yield self._close(
                    "awaiting_permission", usage=total if reported else None, iterations=iteration
                )
                return

            # A question is checked after permission and before dispatch. After, because a
            # deployment that made `ask` itself confirmable should still get its card; before,
            # because the whole point is that it is never dispatched.
            asked = self._asked(round_.calls)
            if asked:
                for call in asked:
                    yield self._record(
                        AnswerRequired(
                            call_id=call.id,
                            tool=call.name,
                            question=_text_argument(call, "question"),
                            kind=_text_argument(call, "kind"),
                        )
                    )
                # The calls beside it are dropped rather than run. She asked a question and
                # stopped; running the rest would act on the assumption the question was about.
                # They are never sent to the model either, because the resumed turn rebuilds
                # history from the event list and there is no result for them in it.
                yield self._close(
                    "awaiting_answer", usage=total if reported else None, iterations=iteration
                )
                return

            async for event in self._answer(round_.calls):
                yield event
            messages = [*messages, *turn_to_messages(self._recorded)]

        yield self._close(
            "max_iterations",
            usage=total if reported else None,
            iterations=self._settings.max_iterations,
        )

    # -- building the request -----------------------------------------------------------

    def _prepare(self, catalogue_text: str) -> list[ChatMessage]:
        """Route skills, compile the prompt, and lay out the conversation.

        Synchronous on purpose and run in a worker thread by the caller: this reads twelve
        small files out of a git repository and stats a skills directory. Both are fast and
        both are blocking, and pretending otherwise would put ``await`` in front of a
        filesystem read.
        """
        context = self.context
        skills_text = ""

        if not context.resume:
            routing = self._router.select(context.text, pinned=self._pins())
            self.cleaned_text = routing.text
            self.skill_ids = routing.ids()
            for selection in routing.selections:
                self._recorded.append(
                    SkillSelected(
                        skill=selection.skill.id,
                        reason=selection.reason.value,
                        score=selection.score,
                    )
                )
            skills_text = render_skills(routing, catalogue=self._router.library.all())

        prompt = self._builder.build(context.profile)
        bindings = {
            SLOT_SKILLS: skills_text,
            SLOT_MEMORIES: context.memories,
            SLOT_PROJECT: context.project.instructions if context.project is not None else "",
            SLOT_TOOLS: catalogue_text,
            SLOT_EMOTIONS: context.emotions,
            SLOT_NOW: context.now,
        }
        frame = prompt.render(
            bindings={key: value for key, value in bindings.items() if value},
            registry=BEHAVIOUR_TRAITS,
        )
        self.prompt_fingerprint = frame.snapshot.prompt_fingerprint

        head, tail = _split_frame(frame.messages)
        messages = [*head, *context.history]
        # The router strips the /command; the attachments are added after that, so a file is
        # never scored as part of the turn's own words.
        spoken = content_of(self.cleaned_text, context.attachments)
        if says_something(spoken):
            messages.append(ChatMessage(role=Role.USER, content=spoken))
        messages.extend(tail)
        return messages

    def _pins(self) -> list[str]:
        """Pinned skills from the chat, the profile and the project, in that order.

        The chat comes first because it is the most specific and the most deliberate: somebody
        opened a picker during this conversation and said *use this one*. Order decides which
        skills survive the budget, so the one chosen by hand a minute ago outranks the one a
        profile has always carried.

        Merged here rather than in ``hera_skillsets``, which knows what a skill is and
        deliberately not what a chat, a profile or a project is.
        """
        names: list[str] = []
        if self.context.chat is not None:
            names.extend(self.context.chat.pinned_skills)
        if self.context.profile is not None:
            names.extend(self.context.profile.pinned_skills)
        if self.context.project is not None:
            names.extend(self.context.project.pinned_skills)
        return list(dict.fromkeys(names))

    async def _tool_specs(self) -> tuple[list[ToolSpec], str]:
        """What the model is offered, and the text bound into the ``tools`` slot.

        A deployment with no servers configured gets an empty list and an empty slot, so the
        prompt says nothing about tools at all rather than announcing an empty catalogue —
        which reads to a model as "you have no tools" and earns a paragraph about it.
        """
        if self._registry is None:
            return [], ""
        catalogue = await self._registry.catalogue()
        listing = "\n".join(
            f"- `{tool.name}` — {tool.description or tool.title}" for tool in catalogue.tools
        )
        return [ToolSpec(**spec) for spec in catalogue.as_function_specs()], listing

    # -- asking ---------------------------------------------------------------------------

    async def _ask(
        self, messages: list[ChatMessage], tools: list[ToolSpec], round_: _Round
    ) -> AsyncIterator[ChatEvent]:
        """One round trip, translating the provider union into this one."""
        request = ChatRequest(
            model=self._settings.model,
            messages=messages,
            tools=tools,
            temperature=self._settings.temperature,
            top_p=self._settings.top_p,
            max_tokens=self._settings.max_tokens,
        )
        async for event in self._provider.stream(request):
            if isinstance(event, TurnEnd):
                # Consumed, not forwarded: it is the model's full stop for this round trip,
                # and a turn with tools in it has several. See hera_chats.events.
                round_.usage = event.usage
                round_.reason = event.reason
                continue
            if isinstance(event, ToolCallReady):
                round_.calls.append(event)
            if isinstance(event, TextDelta | ThinkingDelta | ToolCallReady):
                yield self._record(event)

    # -- tools ----------------------------------------------------------------------------

    def _blocked(self, calls: Sequence[ToolCallReady]) -> list[tuple[ToolCallReady, str]]:
        """Calls a person still has to answer for, each with the rule's own words.

        The reason travels out with the call rather than being looked up again when the card
        is built: the policy is asked once, and there is no second call site that could ask it
        with a different profile and get a different answer.

        A call already confirmed or already refused is not blocked — it has an answer, and a
        refusal is an answer. A ``deny`` from the policy is not blocked either: nobody is
        being asked, the call simply will not run, and ``dispatch`` turns that into a result
        the model can read.
        """
        if self._registry is None:
            return []
        answered = {*self.context.confirmed, *self.context.denied}
        blocked: list[tuple[ToolCallReady, str]] = []
        for call in calls:
            if call.id in answered:
                continue
            outcome = self._registry.check(call.name, profile=self._profile_slug)
            if outcome.decision is Decision.ASK:
                blocked.append((call, outcome.reason))
        return blocked

    def _asked(self, calls: Sequence[ToolCallReady]) -> list[ToolCallReady]:
        """Calls that are questions for a person rather than work for a tool.

        Recognised by name, from :attr:`ChatsSettings.asking_tools`, which the application
        fills in — this package does not know that ``hera__ask`` exists. A call already
        answered is not asked again, which is what stops a resumed turn from re-posing the
        question it was resumed to settle.
        """
        if not self._settings.asking_tools:
            return []
        answered = set(self.context.answers)
        wanted = set(self._settings.asking_tools)
        return [call for call in calls if call.name in wanted and call.id not in answered]

    async def _answer(self, calls: Sequence[ToolCallReady]) -> AsyncIterator[ChatEvent]:
        """Run a batch of calls in parallel and record what came back.

        Parallel because the model emits parallel calls and a turn's worth of emotions is the
        everyday case (ADR 3). Running them one after another turns one round-trip into four.

        A call a person *answered* is not run at all: their words become its result, so the
        model reads a reply to its question in exactly the place a tool's output would have
        been. That is the whole trick — nothing on the model's side of the loop learns that a
        human was in it.
        """
        refused = set(self.context.denied)
        replied = self.context.answers
        results = []

        runnable = [call for call in calls if call.id not in refused and call.id not in replied]
        if runnable and self._registry is not None:
            results = await self._registry.dispatch_all(
                [
                    ToolInvocation(call_id=call.id, tool=call.name, arguments=call.arguments)
                    for call in runnable
                ],
                profile=self._profile_slug,
                confirmed=self.context.confirmed,
            )

        by_id = {result.call_id: result for result in results}
        for call in calls:
            if call.id in replied:
                yield self._record(_answered(call, replied[call.id]))
                continue
            result = by_id.get(call.id)
            if result is None:
                yield self._record(_refused(call, configured=self._registry is not None))
                continue
            yield self._record(
                ToolResultEvent(
                    call_id=result.call_id,
                    tool=result.tool,
                    ok=result.ok,
                    failure=result.failure.value if result.failure is not None else None,
                    text=result.text,
                    structured=result.structured,
                    blocks=result.blocks,
                    duration_ms=result.duration_ms,
                )
            )

    def _resumed_calls(self) -> list[ToolCallReady]:
        """Calls from the paused turn that a person has now settled.

        Three ways to settle one, and they arrive on the same footing: allowed, refused, or
        replied to. The first two are dispatched, the third is not — :meth:`_answer` decides
        which — but all three have to be picked back out of the paused half of the message
        before anything else happens, or the model is asked again with the question still open.
        """
        answered = {*self.context.confirmed, *self.context.denied, *self.context.answers}
        settled = {
            event.call_id for event in self.context.resume if isinstance(event, ToolResultEvent)
        }
        return [
            event
            for event in self.context.resume
            if isinstance(event, ToolCallReady) and event.id in answered and event.id not in settled
        ]

    # -- bookkeeping ------------------------------------------------------------------------

    @property
    def _profile_slug(self) -> str | None:
        return self.context.profile.slug if self.context.profile is not None else None

    def _record(self, event: ChatEvent) -> ChatEvent:
        self._recorded.append(event)
        return event

    def _close(
        self,
        reason: CloseReason,
        *,
        usage: Usage | None = None,
        iterations: int = 0,
        error: str = "",
    ) -> ChatEvent:
        """Append the one terminator. Idempotent, so a cancellation after a close is a no-op."""
        if self._closed:
            return self._recorded[-1]
        self._closed = True
        return self._record(
            TurnClosed(reason=reason, usage=usage, iterations=iterations, error=error)
        )


class TurnOrchestrator:
    """Holds the wiring, produces turns.

    Built once at boot with the provider, the prompt builder, the skill router and the tool
    registry, and asked for a :class:`Turn` per message. It does not know what a request or a
    session is, and it never writes to the database — persisting is the application's, which is
    the only layer that knows whether the response actually reached anyone.
    """

    def __init__(
        self,
        *,
        provider: Provider,
        builder: PromptBuilder,
        router: SkillRouter,
        registry: Tools | None = None,
        settings: ChatsSettings | None = None,
    ) -> None:
        self.provider = provider
        self.builder = builder
        self.router = router
        self.registry = registry
        self.settings = settings or ChatsSettings()

    def begin(self, context: TurnContext) -> Turn:
        return Turn(
            context,
            provider=self.provider,
            builder=self.builder,
            router=self.router,
            registry=self.registry,
            settings=self.settings,
        )


def _split_frame(messages: Sequence[FrameMessage]) -> tuple[list[ChatMessage], list[ChatMessage]]:
    """The prompt frame, split into what goes before the history and what goes after.

    ``hera_prompts`` renders a frame, not a conversation, and says the history belongs in the
    middle. Anything with a user role is the tail — it is the part of the prompt that wants to
    sit closest to the model's answer.
    """
    head: list[ChatMessage] = []
    tail: list[ChatMessage] = []
    for message in messages:
        role = _FRAME_ROLES[message.role]
        target = tail if role is Role.USER else head
        target.append(ChatMessage(role=role, content=message.content))
    return head, tail


def _text_argument(call: ToolCallReady, name: str) -> str:
    """One string argument off a call, or ``""``.

    Tolerant on purpose. These arguments are written by a model and reach the *card* rather
    than a tool, so there is nothing downstream to validate them: a missing ``question`` is a
    card with no question on it, which reads as a bug, and a card is a worse place to raise
    than anywhere else in the turn. The caller has already recorded the call, so what the model
    actually sent is on screen either way.
    """
    value = call.arguments.get(name)
    return value.strip() if isinstance(value, str) else ""


def _answered(call: ToolCallReady, text: str) -> ToolResultEvent:
    """A person's reply, shaped as the result of the call that asked for it.

    ``ok=True``: they answered, and that is a success even when the answer is *no* or *I do not
    know*. Failing the call for an unwelcome answer would tell the model its question was
    broken rather than that it now has one.
    """
    said = text.strip()
    return ToolResultEvent(
        call_id=call.id,
        tool=call.name,
        ok=True,
        # Attributed, because it lands in the same slot a tool's output would and the model
        # should not have to infer which of the two it is reading.
        text=said or "they replied with nothing — take it as no answer and carry on",
    )


def _refused(call: ToolCallReady, *, configured: bool) -> ToolResultEvent:
    text = (
        "not allowed — the person refused this call"
        if configured
        else "no tools are configured in this deployment"
    )
    return ToolResultEvent(call_id=call.id, tool=call.name, ok=False, failure="denied", text=text)


def _add(total: Usage, extra: Usage) -> Usage:
    return Usage(
        prompt_tokens=total.prompt_tokens + extra.prompt_tokens,
        completion_tokens=total.completion_tokens + extra.completion_tokens,
        total_tokens=total.total_tokens + extra.total_tokens,
    )

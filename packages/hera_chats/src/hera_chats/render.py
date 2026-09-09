"""A chat, turned into a document a person can read outside Hera.

The counterpart to :mod:`hera_memories.render` — that module put it plainly: an export is
worth calling one only if it reads like something a person wrote, not a JSON dump wearing a
markdown hat. This is the one place :class:`~hera_chats.events.ChatEvent` becomes prose, so a
new kind of thing a turn can contain is one branch here and nowhere else that renders text.

The reasoning channel is left out for the reason it always is: it is not the answer, and a
document that quoted it back would be quoting a deliberation, not a conversation. Everything
else a turn did — a skill reached for, a tool called, a permission asked, a question asked —
becomes a short line rather than disappearing, because *what she did* is the part an export
would otherwise lose.
"""

from __future__ import annotations

from collections.abc import Sequence

from hera_chats.events import (
    AnswerGiven,
    AnswerRequired,
    PermissionDecided,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
)
from hera_chats.history import events_of
from hera_chats.models import Chat, Message
from hera_providers import TextDelta, ThinkingDelta, ToolCallReady

_SKILL_REASON = {
    "pinned": "pinned",
    "slash": "you asked for it",
    "retrieved": "matched this turn",
}


def for_export(chat: Chat, messages: Sequence[Message]) -> str:
    """The chat as one markdown document: front matter, then the conversation in order.

    Not lossless the way ``MEMORY.md`` is — a chat is not a set of files it can be split back
    into, it is a conversation, so this reads as one. Thinking is left out; everything else a
    turn did is a line, not a silence.
    """
    parts = [_front_matter(chat)]
    for message in messages:
        if message.role == "user":
            parts.append(f"## You\n\n{message.content.strip()}")
        else:
            body = _assistant_body(message)
            if body:
                parts.append(f"## Hera\n\n{body}")
    return "\n\n".join(parts) + "\n"


def _front_matter(chat: Chat) -> str:
    title = chat.title.strip() or "Untitled"
    return f"---\ntitle: {title}\ncreated: {chat.created_at.isoformat()}\n---"


def _assistant_body(message: Message) -> str:
    events = events_of(message)
    results = {event.call_id: event for event in events if isinstance(event, ToolResultEvent)}
    decisions = {event.call_id: event for event in events if isinstance(event, PermissionDecided)}
    answers = {event.call_id: event for event in events if isinstance(event, AnswerGiven)}

    lines: list[str] = []
    for event in events:
        if isinstance(event, TextDelta) and event.text:
            lines.append(event.text)
        elif isinstance(event, ThinkingDelta):
            continue
        elif isinstance(event, SkillSelected):
            lines.append(_skill_line(event))
        elif isinstance(event, ToolCallReady):
            lines.append(_tool_line(event, results.get(event.id), decisions.get(event.id)))
        elif isinstance(event, PermissionRequired):
            continue  # settled above, alongside the call it belongs to
        elif isinstance(event, AnswerRequired):
            lines.append(_answer_line(event, answers.get(event.call_id)))
        elif isinstance(event, TurnClosed) and event.reason != "completed":
            lines.append(f"*(turn ended: {event.reason})*")
    return "\n\n".join(line for line in lines if line)


def _skill_line(event: SkillSelected) -> str:
    reason = _SKILL_REASON.get(event.reason, event.reason)
    return f"> skill: **{event.skill}** ({reason})"


def _tool_line(
    call: ToolCallReady, result: ToolResultEvent | None, decision: PermissionDecided | None
) -> str:
    outcome = _tool_outcome(result, decision)
    line = f"> called `{call.name}` — {outcome}"
    detail = _tool_detail(call, result)
    if detail:
        line += f"\n\n<details>\n<summary>detail</summary>\n\n{detail}\n\n</details>"
    return line


def _tool_outcome(result: ToolResultEvent | None, decision: PermissionDecided | None) -> str:
    if result is not None:
        return "ok" if result.ok else f"failed: {result.failure or 'error'}"
    if decision is not None:
        return "allowed" if decision.allowed else "denied"
    return "awaiting a decision"


def _tool_detail(call: ToolCallReady, result: ToolResultEvent | None) -> str:
    parts = []
    if call.arguments:
        args = ", ".join(f"{key}: {value!r}" for key, value in call.arguments.items())
        parts.append(f"arguments: {args}")
    if result is not None and result.text:
        parts.append(result.text.strip())
    return "\n\n".join(parts)


def _answer_line(event: AnswerRequired, given: AnswerGiven | None) -> str:
    line = f"> asked: {event.question}"
    if given is not None:
        return f"{line} — replied: {given.text}"
    return f"{line} — awaiting a reply"

"""What can go wrong between here and the model.

A failure mid-stream raises rather than turning into an event: an error is not something a
model emits, and the event union stays exactly the set of things that are. The layer that owns
the turn catches these and decides what to persist -- it is the only layer that knows how much
of the answer already arrived.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for every error raised by ``hera_providers``."""


class ProviderUnavailable(ProviderError):
    """The endpoint could not be reached at all.

    Almost always "the model server is not running". Worth a message that says so, because
    this is the failure a self-hosted setup hits most often.
    """


class ProviderTimeout(ProviderError):
    """The endpoint accepted the connection but did not answer in time.

    Distinct from :class:`ProviderUnavailable` because the remedy differs: a local server
    loading a model on demand needs a longer timeout, not a restart.
    """


class StreamInterrupted(ProviderError):
    """The endpoint answered and then the connection broke mid-answer.

    Its own name because the caller's response differs: the events already yielded are real
    and worth keeping. A local server killed part-way through generation -- out of memory, or
    a model swap -- is the usual cause, and the partial answer should be persisted with a
    ``cancelled`` turn rather than discarded.
    """


class ProviderHTTPError(ProviderError):
    """The endpoint answered with a non-success status."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class MalformedResponse(ProviderError):
    """The endpoint answered in a shape this package cannot read.

    A broken stream frame or a response missing the fields the protocol requires -- not to be
    confused with a tool call whose *arguments* are unparseable, which is the model being
    wrong rather than the server, and travels as ``ToolCallReady.parse_error``.
    """

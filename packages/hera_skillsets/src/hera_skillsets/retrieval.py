"""Scoring a turn against skill descriptions.

ADR 5 puts retrieval third, after pinned and ``/slash``, and names two implementations:
cosine similarity over embeddings, and **keyword overlap as the fallback when embeddings are
unavailable**. This module is the fallback, plus the port the real thing arrives through.

The fallback is not a placeholder. Embeddings need a model endpoint, and the one thing a
router must not do is stop working when the endpoint is down — a skill silently not arriving
looks exactly like a skill that was not relevant. So the keyword scorer is what runs by
default and the embedder is what improves it.

**Weighted by rarity.** A plain word count makes "code", "file" and "use" decide everything,
because they are in every description. Each term is weighted by how few skills contain it, so
a match on "kerberos" outweighs a match on "using". Twenty lines of inverse document
frequency, computed over the installed skills rather than over a corpus — which is the right
denominator, since the question is only ever *which of these*.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Protocol

TOKEN = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "up",
        "us",
        "use",
        "used",
        "using",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    ]
)
"""Words too common to carry a signal.

Deliberately short. A long stopword list starts removing terms that matter in a technical
description, and rarity weighting already handles most of what a stopword list is for — this
is only here to keep the very worst offenders out of the numerator.
"""

MIN_TOKEN_LENGTH = 2


class Embedder(Protocol):
    """Vector similarity, supplied by the application.

    ``hera_skillsets`` sits below ``hera_providers`` and may not import it, so the real
    implementation is injected — the same shape as ``hera_tools.ports``. A deployment that
    wires none falls back to :func:`keyword_scores`, which is worse but never absent.
    """

    def similarity(self, text: str, candidates: Sequence[str]) -> Sequence[float]:
        """Similarity of ``text`` to each candidate, in the same order, roughly 0 to 1."""
        ...


def tokenise(text: str) -> list[str]:
    """Lowercase word tokens, with the stopwords and single characters dropped."""
    return [
        token
        for token in TOKEN.findall(text.lower())
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    ]


def keyword_scores(text: str, candidates: Sequence[str]) -> list[float]:
    """Rarity-weighted overlap between ``text`` and each candidate, from 0 to 1.

    The score is the share of a candidate's own weight that the turn matched, so a short
    precise description that is fully covered beats a long one that is half covered. Scoring
    by the *turn's* coverage instead would reward whichever description happened to be
    longest, which is the opposite of what a description should be rewarded for.
    """
    turn = set(tokenise(text))
    if not turn or not candidates:
        return [0.0] * len(candidates)

    tokenised = [set(tokenise(candidate)) for candidate in candidates]
    weights = _rarity(tokenised)

    scores: list[float] = []
    for tokens in tokenised:
        total = sum(weights[token] for token in tokens)
        if not total:
            scores.append(0.0)
            continue
        matched = sum(weights[token] for token in tokens & turn)
        scores.append(matched / total)
    return scores


def _rarity(tokenised: Sequence[set[str]]) -> Mapping[str, float]:
    """Inverse document frequency over the installed skills.

    Smoothed, so a term present in every skill scores above zero rather than exactly zero —
    with a handful of skills installed it is easy for a genuinely useful word to appear in all
    of them, and zeroing it would throw away the only signal there was.
    """
    total = len(tokenised)
    counts: dict[str, int] = {}
    for tokens in tokenised:
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return {token: math.log(1 + total / count) for token, count in counts.items()}

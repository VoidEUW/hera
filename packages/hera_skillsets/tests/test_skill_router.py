"""The router: three passes, in order, never asking the model.

The assertions worth reading are the ones about *why* a skill was chosen and about what
happens when retrieval has nothing good to offer. ADR 5 exists because a mechanism that only
works when the model volunteers is not a mechanism; a router that always selects the least-bad
skill is the same failure wearing different clothes.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from skill_support import WriteSkill

from hera_skillsets import Reason, SkillLibrary, SkillRouter, keyword_scores, tokenise


class TestSlashCommands:
    def test_a_command_selects_the_skill_and_leaves_the_text(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")

        routing = router.select("/tdd how do I test a streaming loop?")

        assert routing.ids() == ["tdd"]
        assert routing.selections[0].reason is Reason.SLASH
        assert routing.text == "how do I test a streaming loop?"

    def test_a_command_anywhere_in_the_message_is_found(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        routing = router.select("help me here /tdd please")
        assert routing.ids() == ["tdd"]
        assert routing.text == "help me here please"

    def test_several_commands_all_resolve(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        write_skill("writing")
        assert set(router.select("/tdd /writing go").ids()) == {"tdd", "writing"}

    def test_the_same_command_twice_selects_once(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        assert router.select("/tdd and again /tdd").ids() == ["tdd"]

    @pytest.mark.parametrize(
        "message",
        [
            "see https://example.com/tdd for details",
            "use and/or as you like",
            "the ratio is 3/4",
            "path/to/tdd is where it lives",
        ],
    )
    def test_a_slash_inside_a_word_is_not_a_command(
        self, router: SkillRouter, write_skill: WriteSkill, message: str
    ) -> None:
        """Unanchored matching would make every message containing a slash a lottery."""
        write_skill("tdd")
        routing = router.select(message)
        assert Reason.SLASH not in [selection.reason for selection in routing.selections]
        assert routing.text == message

    def test_an_unknown_command_is_reported_not_raised(self, router: SkillRouter) -> None:
        routing = router.select("/nosuchskill do the thing")
        assert routing.missing == ("nosuchskill",)
        assert routing.selections == ()
        assert routing.text == "do the thing"


class TestPinned:
    def test_pinned_skills_arrive_without_being_asked_for(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("writing")
        routing = router.select("anything at all", pinned=["writing"])
        assert routing.ids() == ["writing"]
        assert routing.selections[0].reason is Reason.PINNED

    def test_a_dangling_pin_is_reported_and_does_not_stop_the_turn(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("writing")
        routing = router.select("hello", pinned=["writing", "deleted-last-week"])
        assert routing.ids() == ["writing"]
        assert routing.missing == ("deleted-last-week",)

    def test_pinned_outranks_slash_for_the_reason_shown(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        """ "She always has this" is the truer sentence when both apply, and the gutter has
        room for one."""
        write_skill("tdd")
        routing = router.select("/tdd go", pinned=["tdd"])
        assert routing.ids() == ["tdd"]
        assert routing.selections[0].reason is Reason.PINNED

    def test_pinned_comes_first_in_the_list(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        write_skill("writing")
        assert router.select("/tdd go", pinned=["writing"]).ids() == ["writing", "tdd"]


class TestRetrieval:
    def test_a_matching_description_is_selected(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos authentication tickets and realms.")
        write_skill("baking", description="Sourdough bread, hydration and proofing.")

        routing = router.select("explain how kerberos tickets are issued in a realm")

        assert routing.ids() == ["kerberos"]
        assert routing.selections[0].reason is Reason.RETRIEVED
        assert routing.selections[0].score is not None

    def test_an_unrelated_turn_selects_nothing(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        """Selecting the least-bad skill for every message is what makes people stop
        trusting the gutter."""
        write_skill("kerberos", description="Kerberos authentication tickets and realms.")
        write_skill("baking", description="Sourdough bread, hydration and proofing.")

        assert router.select("what time is it in Berlin?").ids() == []

    def test_the_limit_caps_how_many_are_added(
        self, skills_path: str, write_skill: WriteSkill, library: SkillLibrary
    ) -> None:
        for index in range(5):
            write_skill(f"kerberos-{index}", description="Kerberos tickets realms authentication")

        routing = SkillRouter(library, limit=2).select("kerberos tickets realms authentication")

        assert len(routing.selections) == 2

    def test_a_limit_of_zero_switches_retrieval_off(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos tickets realms")
        assert SkillRouter(library, limit=0).select("kerberos tickets realms").ids() == []

    def test_an_empty_turn_retrieves_nothing(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos tickets realms")
        assert router.select("   ").ids() == []

    def test_a_skill_with_no_body_is_never_retrieved(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos tickets realms", body="")
        assert router.select("kerberos tickets realms").ids() == []

    def test_an_already_selected_skill_is_not_retrieved_again(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos tickets realms")
        routing = router.select("kerberos tickets realms", pinned=["kerberos"])
        assert routing.ids() == ["kerberos"]
        assert routing.selections[0].reason is Reason.PINNED

    def test_the_command_is_stripped_before_scoring(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        """Retrieval scores the question, not the token addressed to the application."""
        write_skill("writing", description="Writing prose, editing, tone.")
        write_skill("kerberos", description="Kerberos tickets realms authentication.")

        routing = router.select("/writing explain kerberos tickets and realms")

        assert routing.ids() == ["writing", "kerberos"]

    def test_ties_break_deterministically(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        """Two equally good skills must not shuffle between identical turns."""
        write_skill("bbb", description="Kerberos tickets realms")
        write_skill("aaa", description="Kerberos tickets realms")

        first = router.select("kerberos tickets realms").ids()
        assert first == router.select("kerberos tickets realms").ids()
        assert first[0] == "aaa"


class TestScoring:
    def test_rarity_beats_raw_overlap(self) -> None:
        """A plain word count lets "code" and "file" decide everything, because they are in
        every description."""
        common = "using code with files"
        scores = keyword_scores(
            "kerberos realms",
            [
                "using code with files and kerberos realms",
                "using code with files everywhere",
                common,
            ],
        )
        assert scores[0] > scores[1]

    def test_a_precise_description_beats_a_padded_one(self) -> None:
        """Scoring the turn's coverage instead would reward whichever description was
        longest, which is the opposite of what a description should be rewarded for."""
        scores = keyword_scores(
            "kerberos realms",
            ["kerberos realms", "kerberos realms plus baking sailing knitting welding"],
        )
        assert scores[0] > scores[1]

    def test_no_candidates_scores_nothing(self) -> None:
        assert keyword_scores("anything", []) == []

    def test_a_turn_of_only_stopwords_scores_zero(self) -> None:
        assert keyword_scores("what is the", ["kerberos realms"]) == [0.0]

    def test_a_candidate_of_only_stopwords_scores_zero(self) -> None:
        assert keyword_scores("kerberos", ["the and of"]) == [0.0]

    def test_tokenise_drops_stopwords_and_single_characters(self) -> None:
        assert tokenise("How do I use the Kerberos realm?") == ["kerberos", "realm"]


class TestTheEmbedderSeam:
    def test_an_embedder_replaces_the_keyword_scorer(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("baking", description="Sourdough bread.")

        class AlwaysSure:
            def similarity(self, text: str, candidates: Sequence[str]) -> Sequence[float]:
                return [1.0] * len(candidates)

        routing = SkillRouter(library, embedder=AlwaysSure()).select("nothing to do with bread")

        assert routing.ids() == ["baking"]

    def test_an_embedder_that_raises_falls_back_rather_than_failing_the_turn(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        """A model endpoint being down must not look like a skill not being relevant."""
        write_skill("kerberos", description="Kerberos tickets realms.")

        class Broken:
            def similarity(self, text: str, candidates: Sequence[str]) -> Sequence[float]:
                raise RuntimeError("endpoint unreachable")

        routing = SkillRouter(library, embedder=Broken()).select("kerberos tickets realms")

        assert routing.ids() == ["kerberos"]

    def test_an_embedder_returning_the_wrong_number_of_scores_falls_back(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("kerberos", description="Kerberos tickets realms.")

        class Confused:
            def similarity(self, text: str, candidates: Sequence[str]) -> Sequence[float]:
                return [1.0, 1.0, 1.0]

        assert SkillRouter(library, embedder=Confused()).select("kerberos realms").ids() == [
            "kerberos"
        ]


class TestTheBudget:
    def test_selections_beyond_the_budget_are_dropped_from_the_back(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("writing", body="w" * 500)
        write_skill("tdd", body="t" * 500)

        routing = SkillRouter(library, budget_chars=600).select("/tdd go", pinned=["writing"])

        assert routing.ids() == ["writing"]
        assert routing.dropped == ("tdd",)

    def test_a_single_oversized_skill_is_still_delivered(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        """The real budget is enforced by hera_prompts at render time, which reports what it
        dropped. Refusing here would mean a pinned skill silently never arrives."""
        write_skill("writing", body="w" * 5000)

        routing = SkillRouter(library, budget_chars=100).select("go", pinned=["writing"])

        assert routing.ids() == ["writing"]
        assert routing.dropped == ()

    def test_dropped_and_missing_are_different_things(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        """One is a skill that is gone, the other is a skill that is there and did not fit."""
        write_skill("writing", body="w" * 500)
        write_skill("tdd", body="t" * 500)

        routing = SkillRouter(library, budget_chars=600).select(
            "go", pinned=["writing", "tdd", "ghost"]
        )

        assert routing.dropped == ("tdd",)
        assert routing.missing == ("ghost",)

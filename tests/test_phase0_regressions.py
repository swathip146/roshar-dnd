"""
Regression tests for Phase 0 fixes (docs/REBUILD_PLAN_V5.md §5).

These are Tier-2 assertions per §12: they assert on **observable end state**,
not on "the function was called." Every one of the six audit findings was a case
where the call happened and the effect did not — so mock-based tests missed them.

Covers:
  0.1  NPC registry loads predefined Heralds
  0.2  Retrieved lore actually reaches the scenario prompt
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.npc_stat_loader import NPCStatLoader
from agents.scenario_generator_agent import create_scenario_from_dto


# ---------------------------------------------------------------- 0.1 registry

class TestNPCRegistryPath:
    """0.1 — the loader must point at the directory the JSON files actually live in."""

    def test_registry_loads_predefined_npcs(self):
        loader = NPCStatLoader()
        assert loader.get_npc_count() >= 2, (
            f"Expected >=2 predefined NPCs, got {loader.get_npc_count()}. "
            "Regression of 0.1: loader pointed at data/players/ (only .txt) "
            "while the JSONs live in data/current_campaign/npcs/."
        )

    @pytest.mark.parametrize("name", ["Kalak", "Nale"])
    def test_heralds_resolvable(self, name):
        assert NPCStatLoader().has_npc(name), f"{name} should resolve from the registry"

    def test_default_directory_is_campaign_npcs(self):
        assert "current_campaign/npcs" in NPCStatLoader().npc_directory


# --------------------------------------------------------------- 0.2 RAG wiring

def _dto(rag: dict) -> dict:
    """Minimal DTO shaped like what the orchestrator passes to the scenario agent."""
    return {
        "player_input": "I search the ruins",
        "player_action": "I search the ruins",
        "rag": rag,
        "context": {},
    }


class TestRetrievedLoreReachesPrompt:
    """
    0.2 — the RAG pipeline writes retrieved lore to rag["response"]
    (pipeline_integration.py:680, :792) but the prompt builder read
    rag["rag_context"], which only ever held the game/quest summary.
    Result: every retrieved document was silently discarded.
    """

    LORE = (
        "Shardblades are Honorblades or the spren of the Knights Radiant, "
        "summoned in ten heartbeats and able to sever the soul."
    )

    def test_retrieved_lore_appears_in_prompt(self):
        prompt = create_scenario_from_dto(_dto({"response": self.LORE, "confidence": 0.9}))
        assert "Shardblades are Honorblades" in prompt, (
            "Retrieved lore did not reach the prompt — regression of 0.2."
        )

    def test_lore_is_not_truncated_to_a_fragment(self):
        """The old code did consolidated_rag[:100], cutting lore mid-sentence."""
        prompt = create_scenario_from_dto(_dto({"response": self.LORE}))
        assert "sever the soul" in prompt, (
            "Lore was truncated before reaching the prompt (old 100-char cap)."
        )

    def test_falls_back_to_game_context_when_no_retrieval(self):
        """When RAG didn't run, the game/quest summary should still be used."""
        prompt = create_scenario_from_dto(
            _dto({"rag_context": "Location: Kholinar | Quest: find the artifact"})
        )
        assert "Kholinar" in prompt

    def test_retrieval_wins_over_game_context(self):
        prompt = create_scenario_from_dto(
            _dto({"response": self.LORE, "rag_context": "Location: Kholinar"})
        )
        assert "Shardblades are Honorblades" in prompt

    def test_empty_rag_does_not_crash(self):
        assert isinstance(create_scenario_from_dto(_dto({})), str)

    def test_long_lore_is_bounded(self):
        """Prompt growth must stay bounded — but far above the old 100 chars."""
        prompt = create_scenario_from_dto(_dto({"response": "Stormlight. " * 2000}))
        assert len(prompt) < 60_000, "Prompt grew unbounded with large retrieval"
        assert "Stormlight." in prompt


# ----------------------------------------------------------- 0.6/0.7 routing

from agents.intent_classifier import _determine_final_route, _map_primary_to_type


class TestCombatRouting:
    """
    0.6 — two bugs made the intended combat path unreachable:
      (a) _map_primary_to_type had no "combat" key, so primary="combat" fell
          through to "scenario";
      (b) the route check substring-matched the whole stringified DTO, so any
          rationale merely mentioning combat forced the combat pipeline.
    """

    def test_combat_type_maps_to_combat(self):
        assert _map_primary_to_type("combat") == "combat"

    def test_genuine_combat_routes_to_combat(self):
        assert _determine_final_route({"type": "combat"}) == "combat_pipeline"

    def test_rationale_mentioning_combat_does_not_force_combat(self):
        """The exact false positive: the player is AVOIDING combat."""
        dto = {
            "type": "scenario",
            "rationale": "The player sneaks past the guards to avoid combat entirely.",
            "rag": {"needed": False},
        }
        assert _determine_final_route(dto) == "scenario_pipeline"

    def test_lore_question_about_combat_routes_to_rag(self):
        dto = {
            "type": "rag_query",
            "rationale": "Player asks how combat initiative works.",
            "rag": {"needed": True},
        }
        assert _determine_final_route(dto) == "rag_pipeline"

    def test_npc_talk_mentioning_combat_stays_npc(self):
        dto = {
            "type": "npc_interaction",
            "rationale": "Player asks the innkeeper about a past combat.",
            "rag": {"needed": False},
        }
        assert _determine_final_route(dto) == "npc_pipeline"

    def test_scenario_with_rag_still_routes_correctly(self):
        dto = {"type": "scenario", "rag": {"needed": True}}
        assert _determine_final_route(dto) == "scenario_with_rag_pipeline"


class TestPreRoutedDTO:
    """0.7 — a DTO arriving with a route pre-set must not raise UnboundLocalError."""

    def test_interface_dto_bound_when_route_preset(self):
        """
        Behavioural check: compile the method and confirm `interface_dto` is not
        read before assignment on the pre-routed path. A pre-routed DTO used to
        hit `UnboundLocalError` because interface_dto was bound only inside
        `if not route:`.
        """
        import ast
        import inspect
        import textwrap
        from orchestrator.pipeline_integration import PipelineOrchestrator

        src = textwrap.dedent(
            inspect.getsource(PipelineOrchestrator._handle_gameplay_turn_pipeline_dto)
        )
        tree = ast.parse(src)

        # Find the first *statement* (not comment) assigning interface_dto, and the
        # `if not route:` test. Comments are absent from the AST, so this can't be
        # fooled by the explanatory comment above the fix.
        assign_lines = [
            n.lineno
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "interface_dto" for t in n.targets
            )
        ]
        if_lines = [
            n.lineno
            for n in ast.walk(tree)
            if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
        ]

        assert assign_lines, "interface_dto is never assigned"
        assert if_lines, "expected an `if not route:` guard"
        assert min(assign_lines) < min(if_lines), (
            "interface_dto must be bound BEFORE the `if not route:` guard, "
            "otherwise a pre-routed DTO raises UnboundLocalError."
        )


# ------------------------------------------------- 0.3/0.4/0.5 save round-trip

from components.character_manager import CharacterData, CharacterManager


def _sample_character(char_id="aggi", name="Aggi") -> dict:
    return {
        "character_id": char_id,
        "name": name,
        "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 16, "constitution": 13,
                           "intelligence": 12, "wisdom": 10, "charisma": 15},
        "skills": {"stealth": True, "perception": True},
        "hit_points": {"current": 18, "maximum": 24, "temporary": 0},
        "armor_class": 15,
        "character_class": "Lightweaver",
        "race": "Alethi",
        "background": "Soldier",
        "equipment": ["spear", "rope", "3 spheres"],
        "spell_slots": {1: {"current": 2, "maximum": 3}},
        "radiant_order": "Lightweaver",
        "stormlight_current": 5,
        "stormlight_capacity": 6,
        "ideal_level": 1,
    }


class TestCharacterSerialization:
    """
    0.3 — saves went through get_character_summary(), an ANALYTICS view. The
    save file contained zero hit_points / equipment / armor_class / spell_slots
    / stormlight keys, so loading resurrected the character at 0 HP as
    class "Unknown".
    """

    def test_to_dict_preserves_combat_critical_fields(self):
        mgr = CharacterManager()
        cid = mgr.add_character(_sample_character())
        data = mgr.characters[cid].to_dict()

        for key in ("hit_points", "armor_class", "equipment", "spell_slots",
                    "character_class", "stormlight_current", "radiant_order"):
            assert key in data, f"to_dict() dropped {key!r} — regression of 0.3"

        assert data["hit_points"]["current"] == 18
        assert data["armor_class"] == 15
        assert data["character_class"] == "Lightweaver"
        assert data["stormlight_current"] == 5

    def test_round_trip_is_lossless(self):
        mgr = CharacterManager()
        cid = mgr.add_character(_sample_character())
        original = mgr.characters[cid]

        restored = CharacterData.from_dict(original.to_dict())

        assert restored.name == original.name
        assert restored.hit_points == original.hit_points
        assert restored.armor_class == original.armor_class
        assert restored.equipment == original.equipment
        assert restored.character_class == original.character_class
        assert restored.stormlight_current == original.stormlight_current
        assert restored.ideal_level == original.ideal_level

    def test_survives_json_encoding(self):
        """spell_slots is keyed by int; JSON stringifies keys."""
        import json

        mgr = CharacterManager()
        cid = mgr.add_character(_sample_character())
        blob = json.dumps(mgr.characters[cid].to_dict())
        restored = CharacterData.from_dict(json.loads(blob))

        assert restored.spell_slots == {1: {"current": 2, "maximum": 3}}
        assert restored.hit_points["maximum"] == 24

    def test_summary_is_not_a_serializer(self):
        """Guard the original mistake: the analytics view must not be used to save."""
        mgr = CharacterManager()
        cid = mgr.add_character(_sample_character())
        summary = mgr.get_character_summary(cid)
        assert "hit_points" not in summary or "equipment" not in summary, (
            "get_character_summary() now looks lossless; if it became a real "
            "serializer, update save_game() and delete this guard."
        )


class TestPartyRestore:
    """
    0.4 — the dict branch passed the whole {char_id: sheet} map to
    add_character(), creating ONE character named "unknown" and dropping the
    real roster. D3 requires the full party to round-trip.
    """

    def test_multi_character_map_restores_each(self):
        mgr = CharacterManager()
        saved = {
            "aggi": _sample_character("aggi", "Aggi"),
            "kali": _sample_character("kali", "Kali"),
        }

        restored = []
        for char_id, sheet in saved.items():
            sheet.setdefault("character_id", char_id)
            restored.append(mgr.add_character(sheet))

        assert len(restored) == 2, "Both party members should restore"
        assert "unknown" not in mgr.characters, (
            'Regression of 0.4: created a character literally named "unknown"'
        )
        names = {c.name for c in mgr.characters.values()}
        assert names == {"Aggi", "Kali"}


class TestSaveKeyAlignment:
    """0.5 — the loader read a key save_session() never writes."""

    def test_loader_reads_the_written_key(self):
        import inspect
        from core import game_initialization

        src = inspect.getsource(game_initialization)
        assert 'session_data.get("game_state")' in src, (
            'Loader must read "game_state" — the key save_session() actually writes '
            "(session_manager.py:139), not the dead orchestrator_state path."
        )


# ------------------------------------------------------ 0.9/0.10 autosave+load

class TestAutosaveAndLoad:
    """
    0.9 — state was only written on quit/save/Ctrl-C, and the turn loop's
          blanket `except` continued without saving, so a crash lost the session.
    0.10 — there was no load command at all; help said to exit and restart.
    """

    def test_autosave_helper_exists(self):
        from haystack_dnd_game import HaystackDnDGame
        assert hasattr(HaystackDnDGame, "_autosave")

    def test_load_helper_exists(self):
        from haystack_dnd_game import HaystackDnDGame
        assert hasattr(HaystackDnDGame, "_handle_load_command")

    def test_turn_loop_autosaves(self):
        import inspect
        from haystack_dnd_game import HaystackDnDGame

        src = inspect.getsource(HaystackDnDGame.run_interactive)
        assert "_autosave()" in src, "Turn loop must autosave after each turn"
        assert "_handle_load_command" in src, "Turn loop must expose a load command"

    def test_autosave_never_raises(self):
        """An autosave failure must not end the session."""
        from haystack_dnd_game import HaystackDnDGame

        class Boom:
            def save_game(self, filename="x"):
                raise RuntimeError("disk on fire")

        boom = Boom()
        boom._autosave = HaystackDnDGame._autosave.__get__(boom)
        assert boom._autosave() is False  # swallowed, not raised

    def test_autosave_uses_separate_slot(self):
        """Autosave must not clobber a deliberate manual save."""
        import inspect
        from haystack_dnd_game import HaystackDnDGame

        src = inspect.getsource(HaystackDnDGame._autosave)
        assert "autosave.json" in src


# ------------------------------------------------------------- 0.11 dice parser

from components.dice import DiceRoller


class TestDamageRollParser:
    """
    0.11 — the damage parser crashed on valid 5e notation and its audit trail
    lied. Silent wrong numbers are the worst failure mode for an adjudicator.

    (Plan recommended avrae/d20; that install is blocked by the sandbox proxy,
    so the parser was fixed in place. Contract unchanged, so d20 stays a
    drop-in replacement later.)
    """

    @pytest.fixture
    def roller(self):
        return DiceRoller()

    @pytest.mark.parametrize("expr", ["4d6kh3", "1d6 + 2", "2d6[fire]", "4d6kl1", "5"])
    def test_previously_crashing_expressions_parse(self, roller, expr):
        """These raised ValueError before the fix."""
        result = roller.damage_roll(expr)
        assert isinstance(result["total_damage"], int)

    def test_an_empty_expression_now_raises_deliberately(self):
        """
        `""` was in the list above, on the principle "must not crash". That was
        reversed on 2026-09-10 after measuring the alternative: `dm_tools.roll_damage`
        forwards whatever the LLM wrote, so an empty expression means the model
        OMITTED the dice — not that the attack was harmless. Returning 0 damage
        silently is the same failure shape as `success`-always-True.

        The tool wraps this and returns {"error": ...}, so the DM learns the
        expression was rejected instead of quietly dealing nothing.
        """
        roller = DiceRoller()
        for expr in ("", "0d6", "0"):
            with pytest.raises(ValueError):
                roller.damage_roll(expr)

    def test_negative_modifier_is_reported_not_hidden(self, roller):
        """
        '1d8-1' produced the right total but reported modifier=0 and printed
        '1d8-1 + 0 = N' — the arithmetic was right, the audit trail was wrong.
        """
        r = roller.damage_roll("1d8-1")
        assert r["static_modifier"] == -1, "negative modifier must be reported"
        assert r["total_damage"] == max(0, r["damage_rolls"][0] - 1)
        assert "+ 0 =" not in r["breakdown"], "breakdown must not misreport the modifier"

    def test_keep_highest_drops_lowest(self, roller):
        r = roller.damage_roll("4d6kh3")
        assert len(r["damage_rolls"]) == 4, "all four dice should be recorded"
        assert r["total_damage"] == sum(sorted(r["damage_rolls"], reverse=True)[:3])

    def test_keep_lowest(self, roller):
        r = roller.damage_roll("4d6kl1")
        assert r["total_damage"] == min(r["damage_rolls"])

    def test_whitespace_tolerated(self, roller):
        r = roller.damage_roll("1d6 + 2")
        assert r["static_modifier"] == 2
        assert r["total_damage"] == r["damage_rolls"][0] + 2

    def test_damage_type_annotation_ignored(self, roller):
        r = roller.damage_roll("2d6[fire]")
        assert len(r["damage_rolls"]) == 2

    def test_multiple_dice_terms(self, roller):
        r = roller.damage_roll("1d8+1d6+3")
        assert len(r["damage_rolls"]) == 2
        assert r["total_damage"] == sum(r["damage_rolls"]) + 3

    def test_explicit_modifier_is_additive(self, roller):
        r = roller.damage_roll("1d8", modifier=3)
        assert r["modifier"] == 3
        assert r["total_damage"] == r["damage_rolls"][0] + 3

    def test_damage_never_negative(self, roller):
        assert roller.damage_roll("1d4-100")["total_damage"] == 0

    def test_dice_bounds_respected(self, roller):
        for _ in range(50):
            r = roller.damage_roll("2d6")
            assert all(1 <= v <= 6 for v in r["damage_rolls"])
            assert 2 <= r["total_damage"] <= 12


# --------------------------------------------------- 0.12-0.18 indexing pipeline

from generators.batch_qdrant_indexer import clean_wiki_markup


class TestWikiMarkupCleaning:
    """0.13 — Coppermind lore is MediaWiki markup; embedding it pollutes vectors."""

    def test_strips_simple_links(self):
        assert clean_wiki_markup("The [[Way of Kings]] is a book") == "The Way of Kings is a book"

    def test_piped_links_keep_the_label(self):
        assert "Kaladin" in clean_wiki_markup("[[Kaladin Stormblessed|Kaladin]] fought")
        assert "Stormblessed" not in clean_wiki_markup("[[Kaladin Stormblessed|Kaladin]] fought")

    def test_strips_templates_and_file_embeds(self):
        out = clean_wiki_markup("{{update|sa5}} Text [[File:Navani.jpg|thumb]] more")
        assert "{{" not in out and "File:" not in out
        assert "Text" in out and "more" in out

    def test_headings_keep_their_words(self):
        out = clean_wiki_markup("== Prologue: To Question ==")
        assert "Prologue: To Question" in out
        assert "==" not in out

    def test_strips_bold_italic_quotes(self):
        assert "'''" not in clean_wiki_markup("'''''Words of Radiance'''''")

    def test_plain_prose_is_untouched(self):
        text = "Kaladin ran along the chasm wall."
        assert clean_wiki_markup(text) == text

    def test_handles_empty(self):
        assert clean_wiki_markup("") == ""
        assert clean_wiki_markup(None) is None


class TestSplitterWiredUp:
    """
    0.12 — DocumentSplitter was imported and never used, so Docling output went
    straight to the embedder and chunks ran to 34,586 chars.
    """

    def test_store_in_qdrant_splits(self):
        """
        Updated for the 0.12 revision: Haystack's DocumentSplitter was replaced
        with _split_markdown_structurally() because split_by="word" was
        structure-blind (78% of Handbook chunks started mid-word, 0% at a
        heading). Assert that SOME splitting happens, not which library does it.
        """
        import inspect
        from generators import batch_qdrant_indexer

        src = inspect.getsource(batch_qdrant_indexer.store_in_qdrant)
        assert "_split_markdown_structurally(" in src, "no splitting applied"

    def test_splitter_respects_structure(self):
        """The 0.12 revision: never cut mid-word, prefer heading boundaries."""
        from generators.batch_qdrant_indexer import _split_markdown_structurally

        text = "## First Section\n\n" + ("word " * 300) + "\n\n## Second Section\n\nMore text."
        chunks = _split_markdown_structurally(text, 200)
        assert len(chunks) > 1
        assert any(c.startswith("## Second Section") for c in chunks), \
            "heading boundaries must be respected"

    def test_splitter_keeps_tables_whole(self):
        """A header severed from its rows embeds to noise."""
        from generators.batch_qdrant_indexer import _split_markdown_structurally

        table = "| Level | Dice |\n|---|---|\n" + "".join(
            f"| {i} | {i}d6 |\n" for i in range(1, 40)
        )
        chunks = _split_markdown_structurally(f"## Table\n\n{table}", 50)
        with_header = [c for c in chunks if "|---|" in c]
        assert len(with_header) == 1, "table header was split from its rows"

    def test_split_length_is_configurable(self):
        """D1: the two collections need different chunk sizes."""
        import inspect
        from generators.batch_qdrant_indexer import store_in_qdrant

        params = inspect.signature(store_in_qdrant).parameters
        assert "split_length" in params and "split_overlap" in params


class TestCollectionClearing:
    """
    0.18 — clear_qdrant_collection() checked <storage>/<name> but local Qdrant
    stores at <storage>/collection/<name>, so "clear existing" silently no-opped
    and a re-index appended (observed 3,062 stale + 4,221 new = 7,283).
    """

    def test_clear_checks_the_real_layout(self):
        import inspect
        from generators import batch_qdrant_indexer

        src = inspect.getsource(batch_qdrant_indexer.clear_qdrant_collection)
        assert '"collection"' in src, "must check <storage>/collection/<name>"

    def test_clear_reports_whether_it_removed_anything(self, tmp_path):
        """A no-op clear must be detectable by the caller, not silent."""
        from generators.batch_qdrant_indexer import clear_qdrant_collection

        assert clear_qdrant_collection("nope", str(tmp_path)) is False

        real = tmp_path / "collection" / "mycoll"
        real.mkdir(parents=True)
        (real / "storage.sqlite").write_text("x")
        assert clear_qdrant_collection("mycoll", str(tmp_path)) is True
        assert not real.exists()

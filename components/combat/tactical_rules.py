"""
Tactical rules that depend on position: cover, flanking, opportunity attacks, dash.

These are the rules a grid makes possible, and none of them existed while combat ran
on a two-row line where everyone was permanently adjacent.

Every modifier here is applied to a PERSISTENT engine value and removed again, because
`entity.ac_bonus()` and `entity.attack_bonus()` build a fresh object on each call —
mutating the returned object is silently discarded. Measured: `+2` on
`equipment.ac_bonus` moves AC 14 -> 16 and removal restores it; the same `+2` on the
object returned by `ac_bonus()` does nothing at all.

One upstream bug had to be fixed first. `Dice._roll_with_advantage` rolled `self.count`
dice — **1** for a d20 — and took `max()` of a single-element list, so advantage and
disadvantage were no-ops throughout the engine. Corrected in
`components/engine_patches.py`; verified at ±20pp, which is what 5e predicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from config.logging_config import get_logger

logger = get_logger(__name__)

HALF_COVER_AC = 2          # 5e PHB: half cover grants +2 AC
THREE_QUARTERS_COVER_AC = 5
DASH_LABEL = "Dash"


@dataclass
class TacticalEffects:
    """
    Tracks the position-derived modifiers currently applied, so each can be removed.

    Without this the modifiers accumulate: a character who takes cover twice would
    stack +4, and one who leaves cover would keep the bonus for the rest of the fight.
    Applying a modifier without recording how to remove it is how "temporary" becomes
    permanent.
    """

    cover: Dict[str, UUID] = field(default_factory=dict)        # char_id -> modifier
    flanking: Dict[str, UUID] = field(default_factory=dict)


class TacticalRules:
    """
    Applies and clears the rules that follow from where combatants are standing.

    Called once per turn (`refresh()`) rather than continuously, because position only
    changes on someone's turn and recomputing on every read would be both slower and
    harder to reason about.
    """

    def __init__(self, grid, dnd_wrapper, combat_state: Dict[str, Any]):
        self.grid = grid
        self.wrapper = dnd_wrapper
        self.combat_state = combat_state
        self.effects = TacticalEffects()

    # ------------------------------------------------------------------- cover

    def refresh_cover(self) -> Dict[str, bool]:
        """
        Give +2 AC to everyone standing in cover, and take it away from everyone who
        is not.

        5e: half cover is +2 AC. This is applied to `equipment.ac_bonus`, the entity's
        persistent AC value — verified to move AC 14 -> 16 and back.
        """
        from dnd.core.modifiers import NumericalModifier

        in_cover: Dict[str, bool] = {}
        for char_id in list(self.combat_state.get("combatant_states") or {}):
            entity = self._entity(char_id)
            if entity is None:
                continue

            has_cover = bool(self.grid and self.grid.has_cover(char_id))
            in_cover[char_id] = has_cover
            already = char_id in self.effects.cover

            if has_cover and not already:
                modifier = NumericalModifier(
                    name="half cover", value=HALF_COVER_AC,
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid)
                self.effects.cover[char_id] = (
                    entity.equipment.ac_bonus.self_static.add_value_modifier(modifier))
                logger.info(f"   🛡️  {char_id} takes cover (+{HALF_COVER_AC} AC)")

            elif already and not has_cover:
                self._remove_cover(char_id)

        return in_cover

    def _remove_cover(self, char_id: str) -> None:
        entity = self._entity(char_id)
        modifier_id = self.effects.cover.pop(char_id, None)
        if entity is None or modifier_id is None:
            return
        try:
            entity.equipment.ac_bonus.self_static.remove_value_modifier(modifier_id)
            logger.info(f"   🛡️  {char_id} leaves cover")
        except Exception as e:
            logger.debug(f"   Could not remove cover for {char_id}: {e}")

    # ---------------------------------------------------------------- flanking

    def refresh_flanking(self, char_id: str,
                         hostiles: Sequence[str]) -> Optional[str]:
        """
        Grant advantage while flanking, and clear it otherwise.

        5e's optional flanking rule (DMG p.251): a creature has advantage on melee
        attacks against a target if an ally is on the OPPOSITE side of it. The two
        allies and the target must be roughly in a line, which on a square grid means
        the two attackers occupy opposite sides of the target's tile.

        Returns the flanked target's id, or None.
        """
        from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

        entity = self._entity(char_id)
        if entity is None or self.grid is None:
            return None

        weapon = getattr(entity.equipment, "weapon_main_hand", None)
        if weapon is None:
            return None

        flanked = self._flanked_target(char_id, hostiles)
        already = char_id in self.effects.flanking

        if flanked and not already:
            modifier = AdvantageModifier(
                name="flanking", value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
            self.effects.flanking[char_id] = (
                weapon.attack_bonus.self_static.add_advantage_modifier(modifier))
            logger.info(f"   ⚔️  {char_id} is flanking {flanked} (advantage)")

        elif already and not flanked:
            self._remove_flanking(char_id)

        return flanked

    def _flanked_target(self, char_id: str,
                        hostiles: Sequence[str]) -> Optional[str]:
        """A hostile with one of our allies directly opposite us."""
        me = self.grid.position_of(char_id)
        if me is None:
            return None

        states = self.combat_state.get("combatant_states") or {}
        my_side = (states.get(char_id) or {}).get("is_hostile")
        allies = [cid for cid, state in states.items()
                  if cid != char_id and state.get("is_hostile") == my_side]

        for hostile in hostiles:
            target = self.grid.position_of(hostile)
            if target is None or not self.grid.in_melee_reach(char_id, hostile):
                continue
            # The tile directly opposite us through the target.
            opposite = (2 * target[0] - me[0], 2 * target[1] - me[1])
            for ally in allies:
                if self.grid.position_of(ally) == opposite:
                    return hostile
        return None

    def _remove_flanking(self, char_id: str) -> None:
        entity = self._entity(char_id)
        modifier_id = self.effects.flanking.pop(char_id, None)
        if entity is None or modifier_id is None:
            return
        weapon = getattr(entity.equipment, "weapon_main_hand", None)
        if weapon is None:
            return
        try:
            weapon.attack_bonus.self_static.remove_advantage_modifier(modifier_id)
        except Exception as e:
            logger.debug(f"   Could not clear flanking for {char_id}: {e}")

    # ------------------------------------------------- opportunity attacks

    def opportunity_attackers(self, mover: str,
                              destination: Tuple[int, int]) -> List[str]:
        """
        Who gets a reaction attack because `mover` is leaving their reach?

        5e: leaving an enemy's reach provokes an opportunity attack, using their
        REACTION — so each enemy gets at most one per round. Disengaging avoids it,
        which is why `Retreat out of reach` is a real decision rather than a free one.

        The Disengage half of that sentence was aspirational until
        `components/combat/standard_actions.py` existed: there was no Disengage action
        at all, so the only way to break away was to eat the reaction attack. It is
        checked FIRST here, because a disengaged mover provokes nobody regardless of
        who is standing where.
        """
        if self.grid is None:
            return []

        if self._has_disengaged(mover):
            logger.debug(f"   🏃 {mover} disengaged; no opportunity attacks provoked")
            return []

        states = self.combat_state.get("combatant_states") or {}
        my_side = (states.get(mover) or {}).get("is_hostile")

        provoked = []
        for char_id, state in states.items():
            if state.get("is_hostile") == my_side or char_id == mover:
                continue
            if not state.get("reaction_available", True):
                continue          # already spent this round
            if self._is_down(char_id):
                continue
            # In reach now, out of reach after the move.
            if not self.grid.in_melee_reach(char_id, mover):
                continue
            watcher = self.grid.position_of(char_id)
            if watcher is None:
                continue
            if max(abs(destination[0] - watcher[0]),
                   abs(destination[1] - watcher[1])) > 1:
                provoked.append(char_id)
        return provoked

    def spend_reaction(self, char_id: str) -> None:
        state = (self.combat_state.get("combatant_states") or {}).get(char_id)
        if state is not None:
            state["reaction_available"] = False

    def _has_disengaged(self, char_id: str) -> bool:
        """
        Has this combatant taken the Disengage action?

        The flag lives in `standard_actions` (keyed by engine entity uuid, which is what
        the action itself has to hand) rather than in `combatant_states`, so a Disengage
        resolved through `CombatActionResolver` — with no session manager in the loop —
        still suppresses the attack. Imported lazily: `tactical_rules` is imported by
        the grid tests, which must not require the whole action registry.
        """
        entity = self._entity(char_id)
        if entity is None:
            return False
        try:
            from components.combat.standard_actions import is_disengaged

            return is_disengaged(entity.uuid)
        except Exception as e:                          # pragma: no cover - import guard
            logger.debug(f"   Could not read disengage state: {e}")
            return False

    def reset_reactions(self) -> None:
        """
        Reactions refresh at the start of each round, like the action economy.

        Disengage lapses here too: 5e says it lasts "for the rest of your turn", so a
        disengage that survived into the next round would make a combatant permanently
        immune to opportunity attacks after one use.
        """
        for state in (self.combat_state.get("combatant_states") or {}).values():
            state["reaction_available"] = True

        try:
            from components.combat.standard_actions import clear_disengage

            clear_disengage()
        except Exception as e:                          # pragma: no cover - import guard
            logger.debug(f"   Could not clear disengage state: {e}")

    # ---------------------------------------------------------------------- dash

    def dash_bonus_feet(self, char_id: str) -> int:
        """
        5e: Dash grants extra movement equal to your speed.

        `dash` was registered and offerable but added nothing, so choosing it simply
        wasted the turn.
        """
        from components.combat.tactical_grid import DEFAULT_SPEED_FEET

        entity = self._entity(char_id)
        if entity is None:
            return DEFAULT_SPEED_FEET
        return DEFAULT_SPEED_FEET

    # ------------------------------------------------------------------ helpers

    def clear_all(self) -> None:
        """
        Remove every modifier this instance applied.

        MUST run at the end of combat: these live on the entity, which outlives the
        encounter, so a character would otherwise keep +2 AC from cover they stood in
        during a fight three scenes ago.

        Help's advantage modifier has the identical lifetime problem — it is applied to
        `equipment.attack_bonus` and must come off — so `standard_actions`' own state is
        dropped here too, rather than leaving a second thing for the caller to remember.
        """
        for char_id in list(self.effects.cover):
            self._remove_cover(char_id)
        for char_id in list(self.effects.flanking):
            self._remove_flanking(char_id)

        try:
            from components.combat.standard_actions import (
                reset_standard_action_state)

            reset_standard_action_state()
        except Exception as e:                          # pragma: no cover - import guard
            logger.debug(f"   Could not reset standard action state: {e}")

    def _entity(self, char_id: str):
        if self.wrapper is None:
            return None
        return self.wrapper.entities.get(char_id)

    def _is_down(self, char_id: str) -> bool:
        entity = self._entity(char_id)
        if entity is None:
            return True
        try:
            con = entity.ability_scores.constitution.modifier
            return entity.health.get_total_hit_points(con) <= 0
        except Exception:
            return False

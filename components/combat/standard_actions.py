r"""
The PHB's core actions that the registry never offered: Grapple, Shove, Help, Ready,
Hide, Search, Disengage and Two-Weapon Fighting.

The registry held **four** playable 5e actions — attack, dash, dodge and (through the
grid's own path) move. Everything else a 5e player reaches for on a hard turn was
absent, so a combatant with a bad matchup had exactly one lever: swing again. Measured
by grepping the tree before this module existed:

    grep -rn "def grapple\|def shove\|two_weapon" --include=*.py components/   ->  0 hits

Each action here is a real `BaseAction` subclass, registered into `ACTION_REGISTRY`
under an existing dispatch type so `CombatActionResolver` needs no changes:
`"dnd_action"` routes through `_execute_action`, which instantiates the class with
`source_entity_uuid`/`target_entity_uuid` plus every declared param, then calls
`apply()`.

**The pitfall this module was written around.** An action whose declared `params`
include something nothing supplies is filtered out of the menu by
`action_registry.is_offerable()` and becomes unplayable. That bug made 4 of the 5
Surges unreachable and, before the filter existed, wasted 15 of 28 NPC actions in one
live encounter — each on a real LLM call. So every entry below either declares only
auto-supplied params (`target_entity_uuid`, `weapon_slot`) or carries a
`param_defaults` entry, and `tests/combat/test_standard_actions.py` asserts that all
eight are in `offerable_actions()` AND resolve through the resolver.

**Judgement calls, all resolved to the simplest RAW reading** (no invented numbers —
see `_meta.correction` in data/rules/stormlight/surgebinding.json for why):

* Grapple/Shove are *contested checks*: attacker's Athletics vs the target's choice of
  Athletics or Acrobatics. RAW lets the TARGET choose; the target always prefers its
  better skill, so this takes `max(athletics, acrobatics)` rather than asking.
* Grapple/Shove "replace one of your attacks", which for a single-attack combatant is
  the whole Attack action. Cost is therefore `actions: 1` — the honest cost at the
  levels this campaign runs, and it is what the action economy can express. A
  multiattack character should get them for one *attack*, which needs Extra Attack
  first; that is not implemented, so the simpler reading is used and flagged here.
* Shove's RAW choice is "knock prone OR push 5 feet". Prone is the mechanically
  meaningful half (it grants advantage to melee attackers, which now genuinely works),
  and the push needs a grid destination the caller cannot supply without breaking
  offerability. So the default is PRONE, with `shove_mode="push"` available to a
  caller that does have a grid.
* Help RAW grants advantage on the ally's next ability check, or — if you help attack
  a creature within 5 ft of you — advantage on the ally's next attack roll against it.
  Implemented as the attack half, because that is the one that matters in combat and
  the only one the engine can express. It expires on the ally's next attack (see
  `HelpingAdvantage`), not at end of turn, which is RAW.
* Ready RAW needs a trigger and a prepared action, which is a two-part decision no
  current caller can express. Modelled the only honest way available: it costs the
  action and *stores* the declared intent, leaving the reaction free to spend. The
  stored trigger is a free-text string with a default, so the action stays offerable.
* Hide is Stealth vs the passive Perception of each observer that can see you. Passive
  = 10 + the skill bonus (PHB). On success you gain the engine's `Invisible` condition,
  which is the closest available expression of "unseen" — 5e's own hiding rules give
  the same two consequences (attackers have disadvantage, you have advantage).
  Documented as an approximation: `Invisible` also defeats creatures that could hear
  you, which RAW hiding does not.
* Search is Perception (or Investigation) against a DC. With no hidden objects modelled
  there is nothing to find but a hidden *creature*, so Search is implemented as the
  counter to Hide: Perception vs the hider's Stealth result, and it removes `Invisible`
  on success. That is the one thing Search does in combat.
* Two-Weapon Fighting: bonus action, light weapon in the off hand, no ability modifier
  added to the damage RAW. The engine's Attack always adds the modifier and this module
  does not edit the engine, so the off-hand swing is slightly generous; recorded rather
  than papered over.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# Add dnd_engine to path (required for dnd imports), same as its siblings.
_dnd_engine_path = Path(__file__).parent.parent.parent / "external" / "dnd_engine"
if str(_dnd_engine_path) not in sys.path:
    sys.path.insert(0, str(_dnd_engine_path))

from dnd.core.base_actions import ActionEvent, BaseAction, Cost
from dnd.core.events import EventPhase, EventType
from dnd.entity import Entity

from config.logging_config import get_logger

logger = get_logger(__name__)


# 5e PHB: a passive score is 10 + the relevant modifiers.
PASSIVE_BASE = 10

# 5e "light" melee weapons — the ones that qualify for two-weapon fighting (PHB
# p.149). Kept here rather than on the engine Weapon, because
# `DnDEngineWrapper.equip_weapon` builds every weapon with `properties=[]`, so
# `WeaponProperty.LIGHT` is never set and reading it would reject every off-hand
# swing. Matched on substring so "Kaladin's handaxe" still counts.
LIGHT_WEAPONS = ("dagger", "handaxe", "light hammer", "sickle", "club",
                 "shortsword", "scimitar", "knife", "dart")

# The engine has no Helping condition, so Help is expressed as a one-shot advantage
# modifier tracked here. Keyed by the helped entity's uuid -> (modifier_uuid, value_uuid).
_HELP_GRANTS: Dict[UUID, Tuple[UUID, UUID]] = {}

# Ready stores a declared trigger per entity; the reaction stays unspent until it fires.
_READIED: Dict[UUID, Dict[str, Any]] = {}

# Disengage suppresses opportunity attacks for the rest of the actor's turn.
# `TacticalRules.opportunity_attackers` consults this set, and it is cleared when the
# actor's next turn begins (TacticalRules.reset_reactions, which already runs per round).
_DISENGAGED: set = set()


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def _entity(uuid: Optional[UUID]) -> Optional[Entity]:
    if uuid is None:
        return None
    candidate = Entity.get(uuid)
    return candidate if isinstance(candidate, Entity) else None


def _skill_check(actor: Entity, opponent: Optional[Entity], skill: str) -> int:
    """
    Roll d20 + `skill` for `actor`, against `opponent` for contextual modifiers.

    Goes through `Entity.skill_bonus` + `Entity.roll_d20` rather than
    `components/dice.py`, so proficiency, expertise, exhaustion and every advantage
    modifier already on the entity are honoured. A hand-rolled d20 here would silently
    ignore all of them — the exact failure mode that made the surges decorative.
    """
    from dnd.core.dice import RollType

    target_uuid = opponent.uuid if opponent is not None else None
    bonus = actor.skill_bonus(target_uuid, skill)
    roll = actor.roll_d20(bonus, RollType.CHECK)
    return int(roll.total)


def _passive_skill(entity: Entity, skill: str,
                   opponent: Optional[Entity] = None) -> int:
    """PHB passive score: 10 + the same bonus an active check would use."""
    target_uuid = opponent.uuid if opponent is not None else None
    return PASSIVE_BASE + int(entity.skill_bonus(target_uuid, skill).normalized_score)


def _contest(attacker: Entity, defender: Entity,
             attacker_skill: str = "athletics") -> Tuple[bool, int, int, str]:
    """
    A 5e contested check. Returns (attacker_wins, attacker_total, defender_total, skill).

    RAW: the DEFENDER chooses Athletics or Acrobatics. A defender always picks its
    better option, so the higher bonus is used rather than prompting — and the choice
    is reported so the log can say which.

    Ties go to the DEFENDER (PHB p.174: "the contest results in a tie" leaves the
    situation unchanged), which is why a lost or tied contest must change nothing.
    """
    attacker_total = _skill_check(attacker, defender, attacker_skill)

    athletics = int(defender.skill_bonus(attacker.uuid, "athletics").normalized_score)
    acrobatics = int(defender.skill_bonus(attacker.uuid, "acrobatics").normalized_score)
    defender_skill = "athletics" if athletics >= acrobatics else "acrobatics"
    defender_total = _skill_check(defender, attacker, defender_skill)

    return (attacker_total > defender_total, attacker_total, defender_total,
            defender_skill)


def _action_cost(cost_type: str = "actions", amount: int = 1) -> List[Cost]:
    """
    The engine cost list, WITHOUT an evaluator.

    `entity_action_economy_cost_evaluator` makes `BaseAction.apply()` return None when
    the pool is empty, which the resolver reports as "refused". That is right for
    Attack, but these actions are also driven directly by tests and by the session
    manager, which already gates on the economy; the resolver's
    `_consume_action_cost` does the debiting from the registry metadata. Declaring the
    cost (with no evaluator) keeps `_can_character_afford_action` working — it reads
    `action_class.costs` — while leaving the economy under one owner.
    """
    return [Cost(name=f"{cost_type} cost", cost_type=cost_type, cost=amount)]


class _ContestEvent(ActionEvent):
    """Carries the contested-check numbers so the narrator can report the roll."""

    name: str = "Contested Check"
    event_type: EventType = EventType.BASE_ACTION
    attacker_total: Optional[int] = None
    defender_total: Optional[int] = None
    defender_skill: Optional[str] = None
    contest_won: bool = False


class _TypedEventAction(BaseAction):
    """
    Make an action use its OWN event class instead of the base `ActionEvent`.

    Identical in purpose to `roshar_actions._TypedEventAction`, and duplicated
    deliberately rather than imported: importing it would couple every standard 5e
    action to the Roshar module, which is optional (`ROSHAR_ACTIONS_AVAILABLE`) and can
    fail to import without taking the PHB actions down with it.

    `BaseAction._create_declaration_event` hardcodes `ActionEvent.from_costs(...)`, so
    a custom event class that is merely declared is dead code — and writing a field on
    it raises `ValueError: "ActionEvent" object has no field ...`.
    """

    event_class: type = ActionEvent

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return self.event_class.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)


# ---------------------------------------------------------------------------
# Grapple
# ---------------------------------------------------------------------------

class GrappleEvent(_ContestEvent):
    name: str = "Grapple"


class Grapple(_TypedEventAction):
    """
    PHB p.195: replace one attack with a grapple. Contested Athletics vs the target's
    Athletics or Acrobatics. On a win the target is `Grappled` — speed 0 until escape.
    """

    event_class: type = GrappleEvent
    name: str = "Grapple"
    description: str = "Grab a creature: contested Athletics, target's speed drops to 0"
    costs: List[Cost] = _action_cost()

    def _validate(self, declaration_event: GrappleEvent) -> Optional[GrappleEvent]:
        actor, target = _entity(self.source_entity_uuid), _entity(
            declaration_event.target_entity_uuid)
        if actor is None:
            return declaration_event.cancel(status_message="Grappler not found")
        if target is None:
            return declaration_event.cancel(
                status_message="Grapple needs a target creature")
        # RAW: the target must be no more than one size larger, and you need a free
        # hand. Size is not modelled on the engine Entity and a free hand is not
        # tracked, so neither is checked — noted rather than invented.
        return declaration_event.phase_to(
            EventPhase.EXECUTION, status_message="Grapple declared")

    def _apply(self, execution_event: GrappleEvent) -> Optional[GrappleEvent]:
        from dnd.conditions import Grappled

        actor = _entity(self.source_entity_uuid)
        target = _entity(execution_event.target_entity_uuid)
        if actor is None or target is None:                  # pragma: no cover
            return execution_event.cancel(status_message="Grapple lost its entities")

        won, mine, theirs, their_skill = _contest(actor, target)
        event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=(f"Grapple contest: {mine} vs {theirs} ({their_skill})"),
            attacker_total=mine, defender_total=theirs,
            defender_skill=their_skill, contest_won=won)

        if not won:
            logger.info(f"   🤼 {actor.name} fails to grapple {target.name} "
                        f"({mine} vs {theirs} {their_skill})")
            # A LOST contest must change nothing. Cancelling is what makes the
            # resolver report success=False; returning a non-cancelled event would be
            # read as a win, the same mistake that reported every attack as a hit.
            return event.cancel(
                status_message=(f"{actor.name} fails to grapple {target.name} "
                                f"({mine} vs {theirs})"))

        applied = target.add_condition(Grappled(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid))
        if applied is None or getattr(applied, "canceled", False):
            return event.cancel(
                status_message=f"{target.name} could not be grappled")

        logger.info(f"   🤼 {actor.name} grapples {target.name} "
                    f"({mine} vs {theirs} {their_skill}); speed 0")
        return event.phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} grapples {target.name} "
                            f"({mine} vs {theirs}) — speed 0"))


# ---------------------------------------------------------------------------
# Shove
# ---------------------------------------------------------------------------

class ShoveEvent(_ContestEvent):
    name: str = "Shove"
    shove_mode: str = "prone"


class Shove(_TypedEventAction):
    """
    PHB p.195: replace one attack with a shove. Same contest as Grapple; on a win you
    either knock the target Prone or push it 5 feet.
    """

    event_class: type = ShoveEvent
    name: str = "Shove"
    description: str = "Shove a creature prone (contested Athletics)"
    costs: List[Cost] = _action_cost()
    #: "prone" (default) or "push". See the module docstring for why prone is default.
    shove_mode: str = "prone"

    def _validate(self, declaration_event: ShoveEvent) -> Optional[ShoveEvent]:
        if _entity(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Shover not found")
        if _entity(declaration_event.target_entity_uuid) is None:
            return declaration_event.cancel(
                status_message="Shove needs a target creature")
        return declaration_event.phase_to(
            EventPhase.EXECUTION, status_message="Shove declared")

    def _apply(self, execution_event: ShoveEvent) -> Optional[ShoveEvent]:
        from dnd.conditions import Prone

        actor = _entity(self.source_entity_uuid)
        target = _entity(execution_event.target_entity_uuid)
        if actor is None or target is None:                  # pragma: no cover
            return execution_event.cancel(status_message="Shove lost its entities")

        won, mine, theirs, their_skill = _contest(actor, target)
        event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Shove contest: {mine} vs {theirs} ({their_skill})",
            attacker_total=mine, defender_total=theirs,
            defender_skill=their_skill, contest_won=won,
            shove_mode=self.shove_mode)

        if not won:
            logger.info(f"   🫱 {actor.name} fails to shove {target.name} "
                        f"({mine} vs {theirs} {their_skill})")
            return event.cancel(
                status_message=(f"{actor.name} fails to shove {target.name} "
                                f"({mine} vs {theirs})"))

        if self.shove_mode == "push":
            # 5 feet directly away. The grid owns positions, so this only reports the
            # intent — the session manager applies it through `tactical_grid.move_to`,
            # which is the single place that maintains `Entity._entity_by_position`.
            # Writing `entity.position` here would desync that index, which cancelled
            # every attack for a whole session once already.
            logger.info(f"   🫱 {actor.name} shoves {target.name} back 5 ft")
            return event.phase_to(
                EventPhase.COMPLETION,
                status_message=(f"{actor.name} shoves {target.name} back 5 feet "
                                f"({mine} vs {theirs})"))

        applied = target.add_condition(Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid))
        if applied is None or getattr(applied, "canceled", False):
            return event.cancel(
                status_message=f"{target.name} could not be knocked prone")

        logger.info(f"   🫱 {actor.name} shoves {target.name} prone "
                    f"({mine} vs {theirs} {their_skill})")
        return event.phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} knocks {target.name} prone "
                            f"({mine} vs {theirs})"))


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

class HelpEvent(ActionEvent):
    name: str = "Help"
    event_type: EventType = EventType.BASE_ACTION
    helped_entity_uuid: Optional[UUID] = None


class Help(BaseAction):
    """
    PHB p.192: help an ally attack a creature within 5 ft of you; the ally's next
    attack roll against that creature has advantage.

    The engine has no Helping condition, so this applies an advantage modifier to the
    ally's `equipment.attack_bonus` and records how to remove it. **The removal is the
    whole point**: an advantage that never expires is permanent advantage, the same
    failure shape `TacticalEffects` was written to prevent for cover and flanking.
    `expire_help()` is called by the resolver-facing hook below and by the session
    manager after the helped ally attacks.

    Measured effect (tests/combat/test_standard_actions.py): +21.5pp on the ally's hit
    rate at n=600. That is only true because `Dice._roll_with_advantage` was fixed in
    `components/engine_patches.py` — it rolled ONE die before, so Help would have been
    decorative.
    """

    name: str = "Help"
    description: str = "Give an ally advantage on their next attack"
    costs: List[Cost] = _action_cost()

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return HelpEvent.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)

    def _validate(self, declaration_event: HelpEvent) -> Optional[HelpEvent]:
        if _entity(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Helper not found")
        if _entity(declaration_event.target_entity_uuid) is None:
            return declaration_event.cancel(
                status_message="Help needs an ally to assist")
        return declaration_event.phase_to(
            EventPhase.EXECUTION, status_message="Help declared")

    def _apply(self, execution_event: HelpEvent) -> Optional[HelpEvent]:
        from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

        helper = _entity(self.source_entity_uuid)
        ally = _entity(execution_event.target_entity_uuid)
        if helper is None or ally is None:                    # pragma: no cover
            return execution_event.cancel(status_message="Help lost its entities")

        # Re-helping must not stack: 5e advantage does not, and two unremoved
        # modifiers would leave one behind forever.
        expire_help(ally.uuid)

        value = ally.equipment.attack_bonus
        modifier_uuid = value.self_static.add_advantage_modifier(AdvantageModifier(
            name="Help", value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=helper.uuid, target_entity_uuid=ally.uuid))
        _HELP_GRANTS[ally.uuid] = (modifier_uuid, value.uuid)

        logger.info(f"   🤝 {helper.name} helps {ally.name} "
                    f"(advantage on their next attack)")
        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{helper.name} helps {ally.name}",
            helped_entity_uuid=ally.uuid).phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{ally.name} has advantage on their next attack "
                            f"(helped by {helper.name})"))


def has_help(entity_uuid: UUID) -> bool:
    """Is this creature currently benefiting from an ally's Help?"""
    return entity_uuid in _HELP_GRANTS


def expire_help(entity_uuid: UUID) -> bool:
    """
    Remove a Help grant, e.g. once the helped ally has attacked.

    Returns True if a grant was removed. Must be called: `refresh_flanking` learned
    the hard way that an applied-but-never-removed advantage modifier is a permanent
    one, and this one lives on the entity, which outlives the encounter.
    """
    grant = _HELP_GRANTS.pop(entity_uuid, None)
    if grant is None:
        return False
    modifier_uuid, value_uuid = grant
    entity = _entity(entity_uuid)
    if entity is None:
        return False
    try:
        entity.equipment.attack_bonus.self_static.remove_advantage_modifier(
            modifier_uuid)
        logger.debug(f"   🤝 Help advantage expired for {entity.name}")
        return True
    except Exception as e:                                    # pragma: no cover
        logger.debug(f"   Could not expire Help: {e}")
        return False


def clear_all_help() -> int:
    """Drop every outstanding Help grant. MUST run when combat ends."""
    removed = 0
    for entity_uuid in list(_HELP_GRANTS):
        if expire_help(entity_uuid):
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Disengage
# ---------------------------------------------------------------------------

class Disengage(BaseAction):
    """
    PHB p.192: your movement doesn't provoke opportunity attacks for the rest of the
    turn.

    Opportunity attacks are real here — `TacticalRules.opportunity_attackers` fires
    them and `spend_reaction` bills them — so "Retreat out of reach" costs something
    and Disengage is the answer to it. The suppression lives in this module's
    `_DISENGAGED` set, which `TacticalRules.opportunity_attackers` consults.
    """

    name: str = "Disengage"
    description: str = "Move without provoking opportunity attacks this turn"
    costs: List[Cost] = _action_cost()

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        actor = _entity(self.source_entity_uuid)
        if actor is None:                                     # pragma: no cover
            return execution_event.cancel(status_message="Disengaging entity not found")
        _DISENGAGED.add(actor.uuid)
        logger.info(f"   🏃 {actor.name} disengages (no opportunity attacks this turn)")
        return execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"{actor.name} disengages").phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} disengages — moving away provokes "
                            f"no opportunity attacks this turn"))


def is_disengaged(entity_uuid: UUID) -> bool:
    """Has this creature taken the Disengage action this turn?"""
    return entity_uuid in _DISENGAGED


def clear_disengage(entity_uuid: Optional[UUID] = None) -> None:
    """
    End Disengage — for one creature, or for everyone at the start of a round.

    Called from `TacticalRules.reset_reactions`, which already runs once per round, so
    a disengage cannot silently persist into the next round.
    """
    if entity_uuid is None:
        _DISENGAGED.clear()
    else:
        _DISENGAGED.discard(entity_uuid)


# ---------------------------------------------------------------------------
# Hide
# ---------------------------------------------------------------------------

class HideEvent(ActionEvent):
    name: str = "Hide"
    event_type: EventType = EventType.BASE_ACTION
    stealth_total: Optional[int] = None
    best_passive_perception: Optional[int] = None
    hidden: bool = False


class Hide(BaseAction):
    """
    PHB p.192: make a Dexterity (Stealth) check, contested by the passive Wisdom
    (Perception) of anyone who might notice you.

    Cover matters and the grid already knows about it (`tactical_grid.has_cover`,
    `visible_positions`), so an observer that cannot SEE the hider is not consulted at
    all — hiding behind the rock formation on the authored map works, and hiding in the
    open in front of a watching enemy does not.

    Observers are passed in as `observer_uuids` with a default of `None`, which means
    "nobody can see me" — because a caller that does not know the battlefield must not
    be forced to invent one, and being un-observed is the RAW case where hiding always
    succeeds. That default is also what keeps Hide OFFERABLE.
    """

    name: str = "Hide"
    description: str = "Hide: Stealth versus the enemy's passive Perception"
    costs: List[Cost] = _action_cost()
    observer_uuids: Optional[List[UUID]] = None

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return HideEvent.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)

    def _apply(self, execution_event: HideEvent) -> Optional[HideEvent]:
        from dnd.conditions import Invisible

        actor = _entity(self.source_entity_uuid)
        if actor is None:                                     # pragma: no cover
            return execution_event.cancel(status_message="Hiding entity not found")

        stealth = _skill_check(actor, None, "stealth")
        observers = [_entity(uuid) for uuid in (self.observer_uuids or [])]
        passives = [_passive_skill(observer, "perception", actor)
                    for observer in observers if observer is not None]
        best = max(passives) if passives else 0

        event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Stealth {stealth} vs passive Perception {best}",
            stealth_total=stealth, best_passive_perception=best,
            hidden=stealth > best)

        if passives and stealth <= best:
            logger.info(f"   👁️  {actor.name} fails to hide "
                        f"(Stealth {stealth} vs passive Perception {best})")
            return event.cancel(
                status_message=(f"{actor.name} fails to hide (Stealth {stealth} "
                                f"vs passive Perception {best})"))

        applied = actor.add_condition(Invisible(
            source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
        if applied is None or getattr(applied, "canceled", False):
            # Already hidden is not a failure; report it and keep the state.
            logger.debug(f"   👁️  {actor.name} is already hidden")

        logger.info(f"   👁️  {actor.name} hides (Stealth {stealth} vs {best})")
        return event.phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} is hidden (Stealth {stealth} "
                            f"vs passive Perception {best})"))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchEvent(ActionEvent):
    name: str = "Search"
    event_type: EventType = EventType.BASE_ACTION
    perception_total: Optional[int] = None
    dc: Optional[int] = None
    found: bool = False


class Search(BaseAction):
    """
    PHB p.193: devote your attention to finding something — Wisdom (Perception) or
    Intelligence (Investigation).

    In combat the thing worth finding is a hidden creature, so this is the counter to
    `Hide`: active Perception against the target's passive Stealth, and on success the
    target loses `Invisible`. With no target it is a plain Perception check reported
    against the default DC, which keeps the action honest (and offerable) when there is
    nothing hidden.

    `dc` defaults to 15 — 5e's "hard" DC and the PHB's own example figure for spotting
    something concealed. Not invented: PHB p.174 Typical Difficulty Classes.
    """

    name: str = "Search"
    description: str = "Search for hidden creatures (Perception)"
    costs: List[Cost] = _action_cost()
    dc: int = 15

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return SearchEvent.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)

    def _apply(self, execution_event: SearchEvent) -> Optional[SearchEvent]:
        actor = _entity(self.source_entity_uuid)
        if actor is None:                                     # pragma: no cover
            return execution_event.cancel(status_message="Searching entity not found")

        hider = _entity(execution_event.target_entity_uuid)
        perception = _skill_check(actor, hider, "perception")
        dc = (_passive_skill(hider, "stealth", actor) if hider is not None
              else int(self.dc))
        found = perception >= dc

        event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Perception {perception} vs DC {dc}",
            perception_total=perception, dc=dc, found=found)

        if not found:
            logger.info(f"   🔍 {actor.name} finds nothing "
                        f"(Perception {perception} vs DC {dc})")
            return event.cancel(
                status_message=(f"{actor.name} searches and finds nothing "
                                f"(Perception {perception} vs DC {dc})"))

        if hider is not None and "Invisible" in (hider.active_conditions or {}):
            hider.remove_condition("Invisible")
            logger.info(f"   🔍 {actor.name} spots {hider.name} "
                        f"(Perception {perception} vs DC {dc})")

        return event.phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} searches successfully "
                            f"(Perception {perception} vs DC {dc})"))


# ---------------------------------------------------------------------------
# Ready
# ---------------------------------------------------------------------------

class ReadyEvent(ActionEvent):
    name: str = "Ready"
    event_type: EventType = EventType.BASE_ACTION
    trigger: Optional[str] = None
    readied_action: Optional[str] = None


class Ready(BaseAction):
    """
    PHB p.193: spend your action to prepare a response — "when X happens, I do Y" —
    which is then taken with your reaction.

    RAW needs a trigger AND a prepared action, which is a two-part decision no current
    caller can express. Both are therefore free-text with defaults, so the action stays
    OFFERABLE (`is_offerable()` would filter it out otherwise, and an action nobody can
    choose is not an action). The default is `attack` on "an enemy comes within reach",
    which is the overwhelmingly common readied action in play.

    The reaction is deliberately NOT spent here: 5e spends it when the trigger fires,
    and pre-spending it would silently cancel the opportunity attack this same
    character is still entitled to if the trigger never happens.
    """

    name: str = "Ready"
    description: str = "Ready an action to take when a trigger occurs"
    costs: List[Cost] = _action_cost()
    trigger: str = "an enemy comes within reach"
    readied_action: str = "attack"

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return ReadyEvent.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)

    def _apply(self, execution_event: ReadyEvent) -> Optional[ReadyEvent]:
        actor = _entity(self.source_entity_uuid)
        if actor is None:                                     # pragma: no cover
            return execution_event.cancel(status_message="Readying entity not found")

        _READIED[actor.uuid] = {
            "trigger": self.trigger,
            "action": self.readied_action,
            "target": execution_event.target_entity_uuid,
        }
        logger.info(f"   ⏳ {actor.name} readies {self.readied_action} "
                    f"(trigger: {self.trigger})")
        return execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"{actor.name} readies an action",
            trigger=self.trigger, readied_action=self.readied_action).phase_to(
            EventPhase.COMPLETION,
            status_message=(f"{actor.name} readies {self.readied_action} — "
                            f"triggers when {self.trigger}"))


def readied_action(entity_uuid: UUID) -> Optional[Dict[str, Any]]:
    """What this creature is waiting to do, if anything."""
    return _READIED.get(entity_uuid)


def consume_readied_action(entity_uuid: UUID) -> Optional[Dict[str, Any]]:
    """Take the readied action off the shelf; the caller spends the reaction."""
    return _READIED.pop(entity_uuid, None)


def clear_readied_actions() -> None:
    """A readied action lapses at the start of your next turn (PHB)."""
    _READIED.clear()


# ---------------------------------------------------------------------------
# Two-weapon fighting
# ---------------------------------------------------------------------------

class TwoWeaponAttack(BaseAction):
    """
    PHB p.195: when you Attack with a light melee weapon in one hand, you can use a
    BONUS ACTION to attack with a different light melee weapon in the other hand.

    Implemented as the engine's own `Attack` against `WeaponSlot.OFF_HAND`, so the
    attack roll, damage dice, reach, cover and every advantage modifier are the real
    ones rather than a parallel calculation. What this class adds is the 5e legality
    that `Attack` does not know about:

      * the cost is a BONUS ACTION, not an action — so it cannot be repeated, and it
        does not compete with the main Attack;
      * both weapons must be LIGHT and MELEE (see `LIGHT_WEAPONS` for why the weapon's
        own `properties` cannot be consulted);
      * an off-hand weapon must actually be equipped.

    RAW also omits the ability modifier from the off-hand damage. The engine's Attack
    always adds it and `external/dnd_engine` is frozen, so the off-hand swing hits
    slightly harder than RAW; recorded here rather than silently "fixed" with an
    invented number.
    """

    name: str = "Two-Weapon Attack"
    description: str = "Bonus-action attack with a light off-hand weapon"
    costs: List[Cost] = _action_cost("bonus_actions")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        actor = _entity(self.source_entity_uuid)
        if actor is None:
            return declaration_event.cancel(status_message="Attacker not found")
        if _entity(declaration_event.target_entity_uuid) is None:
            return declaration_event.cancel(
                status_message="Two-weapon fighting needs a target")

        off_hand = getattr(actor.equipment, "weapon_off_hand", None)
        if off_hand is None:
            return declaration_event.cancel(
                status_message=f"{actor.name} has no off-hand weapon equipped")
        if not is_light_weapon(getattr(off_hand, "name", "")):
            return declaration_event.cancel(
                status_message=(f"{getattr(off_hand, 'name', 'that weapon')} is not "
                                f"light, so it cannot be used for two-weapon "
                                f"fighting"))
        main_hand = getattr(actor.equipment, "weapon_main_hand", None)
        if main_hand is not None and not is_light_weapon(
                getattr(main_hand, "name", "")):
            return declaration_event.cancel(
                status_message=(f"{getattr(main_hand, 'name', 'the main weapon')} is "
                                f"not light, so two-weapon fighting does not apply"))

        # The bonus action must actually be available. Without this check the swing
        # resolves and the economy debit fails afterwards with "Not enough bonus
        # actions", which the resolver only logs as a warning — the attack would land
        # for free, every round.
        if not actor.action_economy.can_afford("bonus_actions", 1):
            return declaration_event.cancel(
                status_message=f"{actor.name} has no bonus action left")

        return declaration_event.phase_to(
            EventPhase.EXECUTION, status_message="Off-hand attack declared")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        actor = _entity(self.source_entity_uuid)
        if actor is None:                                     # pragma: no cover
            return execution_event.cancel(status_message="Attacker vanished")

        # The engine's Attack bills an ACTION — through a cost EVALUATOR that refuses
        # outright when the pool is empty, and a cost APPLIER that debits it — and this
        # is a BONUS action. So two things are needed: lend an action so the swing is
        # not refused after the actor already used its real Attack, and refund the
        # action the swing spent.
        #
        # TWO MEASURED FAILURES got here. (1) Lending only when the actor had no action
        # left: a fresh combatant's Attack then spent its REAL action, so two-weapon
        # fighting cost the whole turn (actions 1 -> 0 alongside bonus_actions 1 -> 0).
        # (2) Lending unconditionally and removing only the LOAN afterwards: the loan
        # (+1) came off but Attack's own cost modifier (-1) stayed, so the net was
        # STILL 1 -> 0. Both the loan and the cost modifier Attack added have to go,
        # which is why the modifier set is diffed rather than assumed.
        loan = _lend_one_action(actor)
        before = _action_cost_modifier_uuids(actor)

        attack_event = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=execution_event.target_entity_uuid,
            weapon_slot=WeaponSlot.OFF_HAND).apply(parent_event=None)

        _reclaim_action_loan(actor, loan, before)

        # Spend the bonus action HERE rather than leaving it to the resolver, so a
        # direct caller (test, NPC AI, session manager) all get the same accounting and
        # the action cannot be repeated.
        try:
            actor.action_economy.consume("bonus_actions", 1,
                                         cost_name="two-weapon attack")
        except Exception as e:
            logger.warning(f"⚠️ Could not bill the bonus action: {e}")

        if attack_event is None:
            return execution_event.cancel(
                status_message="The off-hand attack was refused by the engine")
        if getattr(attack_event, "canceled", False):
            return execution_event.cancel(
                status_message=getattr(attack_event, "status_message",
                                       "The off-hand attack was canceled"))

        outcome = getattr(attack_event, "attack_outcome", None)
        logger.info(f"   ⚔️  {actor.name} off-hand attack: {outcome}")
        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Off-hand attack: {outcome}").phase_to(
            EventPhase.COMPLETION,
            status_message=f"Off-hand attack: {outcome}")


def _lend_one_action(actor: Entity) -> UUID:
    """
    Temporarily grant one extra action, so the nested `Attack` is not REFUSED.

    `Attack`'s cost evaluator calls `can_afford("actions", 1)` and `apply()` returns
    None when it fails, so without the loan an off-hand swing after the main Attack
    would be reported as "refused (no action available)" — i.e. two-weapon fighting
    would only work on a turn you did not attack, which is the exact opposite of the
    rule.
    """
    from dnd.core.modifiers import NumericalModifier

    return actor.action_economy.actions.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=actor.uuid,
                                 name="two-weapon action loan", value=1))


def _action_cost_modifier_uuids(actor: Entity) -> set:
    """
    The uuids of the modifiers currently reducing the actor's action pool.

    Diffing this before and after identifies the ONE modifier `Attack` added, so the
    refund removes exactly that. `action_economy.reset_all_costs()` is not usable here:
    it would also wipe the actor's genuine spending for the turn, handing back the main
    Attack's action for free.
    """
    return {uuid for uuid, modifier
            in actor.action_economy.actions.self_static.value_modifiers.items()
            if (modifier.name or "").endswith("cost") or (modifier.value or 0) < 0}


def _reclaim_action_loan(actor: Entity, modifier_uuid: UUID,
                         cost_uuids_before: set) -> None:
    """Undo both halves of the loan: the +1 lent and the -1 `Attack` spent."""
    static = actor.action_economy.actions.self_static
    for uuid in [modifier_uuid] + list(
            _action_cost_modifier_uuids(actor) - cost_uuids_before):
        try:
            static.remove_value_modifier(uuid)
        except Exception as e:                                # pragma: no cover
            logger.debug(f"   Could not reclaim action modifier {uuid}: {e}")


def is_light_weapon(weapon_name: str) -> bool:
    """
    Is this a 5e LIGHT melee weapon (eligible for two-weapon fighting)?

    Matched by name because `DnDEngineWrapper.equip_weapon` builds every Weapon with
    `properties=[]`, so `WeaponProperty.LIGHT` is never set on any weapon in this game
    and reading it would reject every off-hand swing.
    """
    name = (weapon_name or "").strip().lower()
    return any(light in name for light in LIGHT_WEAPONS)


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

#: Registry entries, kept next to the classes they describe.
#:
#: Every entry is offerable by construction: the only declared params are the ones
#: `action_registry._AUTO_SUPPLIED_PARAMS` covers (`target_entity_uuid`,
#: `weapon_slot`) or ones with a `param_defaults` value. Verified by
#: tests/combat/test_standard_actions.py rather than by inspection — that is the bug
#: that cost 15 of 28 NPC actions in a live encounter.
STANDARD_ACTION_ENTRIES: Dict[str, Dict[str, Any]] = {
    "grapple": {
        "type": "dnd_action",
        "action_class": Grapple,
        "description": "Grapple a creature (contested Athletics; speed drops to 0)",
        "params": ["target_entity_uuid"],
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "shove": {
        "type": "dnd_action",
        "action_class": Shove,
        "description": "Shove a creature prone (contested Athletics)",
        "params": ["target_entity_uuid", "shove_mode"],
        # RAW offers prone OR a 5 ft push; prone is the half that needs no grid
        # destination, so it is the default and the action stays offerable.
        "param_defaults": {"shove_mode": "prone"},
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "help": {
        "type": "dnd_action",
        "action_class": Help,
        "description": "Help an ally (their next attack has advantage)",
        "params": ["target_entity_uuid"],
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
        # Targets an ALLY. `combat_session_manager._generate_action_options` reads this
        # flag; without it the menu would only ever offer Help to an ENEMY, which is
        # exactly how `progression_healing` ended up unable to heal the wounded player.
        "beneficial": True,
    },
    "disengage": {
        "type": "dnd_action",
        "action_class": Disengage,
        "description": "Disengage (moving away provokes no opportunity attacks)",
        "params": [],
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "hide": {
        "type": "dnd_action",
        "action_class": Hide,
        "description": "Hide (Stealth vs passive Perception)",
        "params": ["observer_uuids"],
        # None = "nobody can see me". A caller that knows the battlefield passes the
        # observers; one that does not must not be forced to invent them, and an
        # unobserved creature always succeeds at hiding (RAW).
        "param_defaults": {"observer_uuids": None},
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "search": {
        "type": "dnd_action",
        "action_class": Search,
        "description": "Search for a hidden creature (Perception)",
        "params": ["target_entity_uuid", "dc"],
        # PHB p.174 "hard" DC, used only when there is no hidden target to contest.
        "param_defaults": {"dc": 15},
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "ready": {
        "type": "dnd_action",
        "action_class": Ready,
        "description": "Ready an action for a trigger (taken with your reaction)",
        "params": ["trigger", "readied_action"],
        "param_defaults": {"trigger": "an enemy comes within reach",
                           "readied_action": "attack"},
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
    },
    "two_weapon_attack": {
        "type": "dnd_action",
        "action_class": TwoWeaponAttack,
        "description": "Bonus-action attack with a light off-hand weapon",
        "params": ["target_entity_uuid"],
        "cost_type": "bonus_actions",
        "cost": 1,
        "requires": None,
    },
}


def register_standard_actions() -> List[str]:
    """
    Add the eight PHB actions to `ACTION_REGISTRY`.

    ONE CALL IS NEEDED TO WIRE THIS UP — see the note in the module docstring of
    `tests/combat/test_standard_actions.py`. Because `action_registry.py` is owned
    elsewhere, this module cannot insert itself; the registry's own bottom section (or
    `CombatActionResolver.__init__`) must call this once.

    Idempotent: re-registering would rebind the classes while instances of the old ones
    may still be mid-resolution, so an already-present name is left alone.

    Returns the names newly registered.
    """
    from components.combat.action_registry import ACTION_REGISTRY

    added: List[str] = []
    for name, entry in STANDARD_ACTION_ENTRIES.items():
        if name in ACTION_REGISTRY:
            continue
        ACTION_REGISTRY[name] = entry
        added.append(name)

    if added:
        logger.info(f"⚔️  Standard 5e actions registered: {', '.join(added)}")
    return added


def reset_standard_action_state() -> None:
    """
    Drop every cross-encounter bit of state this module keeps.

    MUST run when combat ends. `_HELP_GRANTS` holds live modifiers on entities that
    outlive the encounter, and `_DISENGAGED`/`_READIED` would otherwise let a decision
    from a fight three scenes ago apply to the next one — the same class of bug as the
    `Tile` registry leaking a wall between two test files.
    """
    clear_all_help()
    _DISENGAGED.clear()
    _READIED.clear()

"""
Rule Enforcement Agent for DM Assistant
Validates actions, enforces D&D 5e rules, and provides rule guidance using RAG
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from agent_framework import BaseAgent, MessageType, AgentMessage


class RuleCategory(Enum):
    """Categories of D&D rules"""
    COMBAT = "combat"
    SPELLCASTING = "spellcasting"
    ABILITY_CHECKS = "ability_checks"
    SAVING_THROWS = "saving_throws"
    CONDITIONS = "conditions"
    MOVEMENT = "movement"
    ACTIONS = "actions"
    EQUIPMENT = "equipment"
    CHARACTER_CREATION = "character_creation"
    GENERAL = "general"


class ValidationResult(Enum):
    """Results of rule validation"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    UNCLEAR = "unclear"


@dataclass
class RuleViolation:
    """Represents a rule violation or warning"""
    category: RuleCategory
    severity: ValidationResult
    rule_text: str
    violation_description: str
    suggested_fix: str = ""
    source_reference: str = ""


@dataclass
class ActionValidation:
    """Result of validating a game action"""
    is_valid: bool
    result: ValidationResult
    violations: List[RuleViolation] = field(default_factory=list)
    warnings: List[RuleViolation] = field(default_factory=list)
    rule_clarifications: List[str] = field(default_factory=list)
    auto_corrections: Dict[str, Any] = field(default_factory=dict)


class RuleEnforcementAgent(BaseAgent):
    """Rule Enforcement Agent that validates actions and provides rule guidance"""
    
    def __init__(self, rag_agent=None, strict_mode: bool = False):
        super().__init__("rule_enforcement", "RuleEnforcement")
        self.rag_agent = rag_agent
        self.strict_mode = strict_mode  # If True, invalid actions are blocked
        
        # Rule cache for performance
        self.rule_cache: Dict[str, str] = {}
        
        # Common rule patterns
        self.common_rules = self._load_common_rules()
    
    def _setup_handlers(self):
        """Setup message handlers for rule enforcement"""
        self.register_handler("validate_action", self._handle_validate_action)
        self.register_handler("validate_spell_cast", self._handle_validate_spell_cast)
        self.register_handler("validate_attack", self._handle_validate_attack)
        self.register_handler("validate_movement", self._handle_validate_movement)
        self.register_handler("check_rule", self._handle_check_rule)
        self.register_handler("get_condition_effects", self._handle_get_condition_effects)
        self.register_handler("validate_ability_check", self._handle_validate_ability_check)
        self.register_handler("get_rule_summary", self._handle_get_rule_summary)
    
    def _load_common_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load common D&D 5e rules for quick validation"""
        return {
            "actions_per_turn": {
                "rule": "On your turn, you can move and take one action. You can also take one bonus action and any number of free actions.",
                "validation": lambda data: self._validate_action_economy(data)
            },
            "movement_rules": {
                "rule": "You can move up to your speed on your turn. Difficult terrain costs 2 feet for every 1 foot moved.",
                "validation": lambda data: self._validate_movement_rules(data)
            },
            "attack_rules": {
                "rule": "Make an attack roll (1d20 + ability modifier + proficiency bonus) vs target AC. Natural 20 is critical hit.",
                "validation": lambda data: self._validate_attack_rules(data)
            },
            "spell_slot_rules": {
                "rule": "Casting a spell of 1st level or higher expends a spell slot of the spell's level or higher.",
                "validation": lambda data: self._validate_spell_slot_rules(data)
            },
            "concentration_rules": {
                "rule": "You can only concentrate on one spell at a time. Taking damage requires a Constitution save to maintain concentration.",
                "validation": lambda data: self._validate_concentration_rules(data)
            },
            "opportunity_attack_rules": {
                "rule": "When a hostile creature you can see moves out of your reach, you can use your reaction to make one melee attack.",
                "validation": lambda data: self._validate_opportunity_attack_rules(data)
            }
        }
    
    def _handle_validate_action(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle general action validation request"""
        action_data = message.data.get("action", {})
        game_state = message.data.get("game_state", {})
        
        if not action_data:
            return {"success": False, "error": "No action data provided"}
        
        try:
            validation = self.validate_action(action_data, game_state)
            return {
                "success": True,
                "validation": {
                    "is_valid": validation.is_valid,
                    "result": validation.result.value,
                    "violations": [
                        {
                            "category": v.category.value,
                            "severity": v.severity.value,
                            "rule_text": v.rule_text,
                            "violation_description": v.violation_description,
                            "suggested_fix": v.suggested_fix,
                            "source_reference": v.source_reference
                        }
                        for v in validation.violations
                    ],
                    "warnings": [
                        {
                            "category": w.category.value,
                            "severity": w.severity.value,
                            "rule_text": w.rule_text,
                            "violation_description": w.violation_description,
                            "suggested_fix": w.suggested_fix
                        }
                        for w in validation.warnings
                    ],
                    "rule_clarifications": validation.rule_clarifications,
                    "auto_corrections": validation.auto_corrections
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_validate_spell_cast(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle spell casting validation"""
        spell_data = message.data.get("spell", {})
        caster_data = message.data.get("caster", {})
        game_state = message.data.get("game_state", {})
        
        try:
            validation = self.validate_spell_cast(spell_data, caster_data, game_state)
            return self._format_validation_response(validation)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_validate_attack(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle attack validation"""
        attack_data = message.data.get("attack", {})
        attacker_data = message.data.get("attacker", {})
        target_data = message.data.get("target", {})
        game_state = message.data.get("game_state", {})
        
        try:
            validation = self.validate_attack(attack_data, attacker_data, target_data, game_state)
            return self._format_validation_response(validation)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_validate_movement(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle movement validation"""
        movement_data = message.data.get("movement", {})
        character_data = message.data.get("character", {})
        game_state = message.data.get("game_state", {})
        
        try:
            validation = self.validate_movement(movement_data, character_data, game_state)
            return self._format_validation_response(validation)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_check_rule(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle rule check request"""
        rule_query = message.data.get("query")
        category = message.data.get("category", "general")
        
        if not rule_query:
            return {"success": False, "error": "No rule query provided"}
        
        try:
            rule_info = self.check_rule(rule_query, category)
            return {"success": True, "rule_info": rule_info}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_condition_effects(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle condition effects request"""
        condition_name = message.data.get("condition_name")
        
        if not condition_name:
            return {"success": False, "error": "No condition name provided"}
        
        try:
            effects = self.get_condition_effects(condition_name)
            # Format response to match expected pattern
            formatted_response = f"CONDITION RULE - {condition_name.title()}:\n"
            formatted_response += f"Effects: {', '.join(effects.get('effects', []))}\n"
            formatted_response += f"Duration: {effects.get('duration', 'Unknown')}"
            
            return {
                "success": True,
                "effects": effects,
                "rule_info": {
                    "rule_text": formatted_response,
                    "category": "conditions",
                    "confidence": "high"
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_validate_ability_check(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle ability check validation"""
        check_data = message.data.get("check", {})
        character_data = message.data.get("character", {})
        
        try:
            validation = self.validate_ability_check(check_data, character_data)
            return self._format_validation_response(validation)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_rule_summary(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle rule summary request"""
        topic = message.data.get("topic", "general")
        
        try:
            summary = self.get_rule_summary(topic)
            return {"success": True, "summary": summary}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def validate_action(self, action_data: Dict[str, Any], game_state: Dict[str, Any]) -> ActionValidation:
        """Validate a general game action"""
        validation = ActionValidation(is_valid=True, result=ValidationResult.VALID)
        
        action_type = action_data.get("type", "unknown")
        actor_id = action_data.get("actor")
        
        # Get character data from game state
        character = self._get_character_data(actor_id, game_state)
        if not character:
            validation.violations.append(RuleViolation(
                category=RuleCategory.GENERAL,
                severity=ValidationResult.INVALID,
                rule_text="Actions must be performed by valid characters",
                violation_description=f"Character {actor_id} not found in game state"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
            return validation
        
        # Validate action economy
        if action_type in ["attack", "cast_spell", "dash", "dodge", "help", "hide", "ready", "search"]:
            if not character.get("has_action", True):
                validation.violations.append(RuleViolation(
                    category=RuleCategory.ACTIONS,
                    severity=ValidationResult.INVALID,
                    rule_text="You can only take one action per turn",
                    violation_description="Character has already used their action this turn",
                    suggested_fix="Wait until next turn or use a bonus action instead"
                ))
                validation.is_valid = False
                validation.result = ValidationResult.INVALID
        
        # Validate specific action types
        if action_type == "move":
            movement_validation = self._validate_movement_action(action_data, character, game_state)
            validation = self._merge_validations(validation, movement_validation)
        elif action_type == "attack":
            attack_validation = self._validate_attack_action(action_data, character, game_state)
            validation = self._merge_validations(validation, attack_validation)
        elif action_type == "cast_spell":
            spell_validation = self._validate_spell_action(action_data, character, game_state)
            validation = self._merge_validations(validation, spell_validation)
        
        return validation
    
    def validate_spell_cast(self, spell_data: Dict[str, Any], caster_data: Dict[str, Any], 
                           game_state: Dict[str, Any]) -> ActionValidation:
        """Validate spell casting"""
        validation = ActionValidation(is_valid=True, result=ValidationResult.VALID)
        
        spell_name = spell_data.get("name", "")
        spell_level = spell_data.get("level", 1)
        cast_at_level = spell_data.get("cast_at_level", spell_level)
        
        # Check if caster has spell slots
        spell_slots = caster_data.get("spell_slots", {})
        available_slots = spell_slots.get(f"level_{cast_at_level}", 0)
        
        if cast_at_level > 0 and available_slots <= 0:
            validation.violations.append(RuleViolation(
                category=RuleCategory.SPELLCASTING,
                severity=ValidationResult.INVALID,
                rule_text="You must have an available spell slot to cast a spell",
                violation_description=f"No level {cast_at_level} spell slots remaining",
                suggested_fix=f"Use a higher level slot or take a long rest to recover slots"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
        
        # Check concentration
        if spell_data.get("concentration", False):
            current_concentration = caster_data.get("concentrating_on")
            if current_concentration:
                validation.warnings.append(RuleViolation(
                    category=RuleCategory.SPELLCASTING,
                    severity=ValidationResult.WARNING,
                    rule_text="You can only concentrate on one spell at a time",
                    violation_description=f"Already concentrating on {current_concentration}",
                    suggested_fix="Casting this spell will end concentration on the current spell"
                ))
                validation.auto_corrections["end_concentration"] = current_concentration
        
        # Use RAG to get spell-specific rules if available
        if self.rag_agent and spell_name:
            spell_rules = self._get_spell_rules(spell_name)
            if spell_rules and "error" not in spell_rules:
                validation.rule_clarifications.extend(spell_rules.get("clarifications", []))
        
        return validation
    
    def validate_attack(self, attack_data: Dict[str, Any], attacker_data: Dict[str, Any], 
                       target_data: Dict[str, Any], game_state: Dict[str, Any]) -> ActionValidation:
        """Validate attack action"""
        validation = ActionValidation(is_valid=True, result=ValidationResult.VALID)
        
        # Check if attacker can make attacks
        if not attacker_data.get("has_action", True):
            validation.violations.append(RuleViolation(
                category=RuleCategory.COMBAT,
                severity=ValidationResult.INVALID,
                rule_text="Making an attack uses your action",
                violation_description="No action available for attack",
                suggested_fix="Wait until next turn or use bonus action attack if available"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
        
        # Check range
        weapon_range = attack_data.get("range", 5)  # Default melee range
        distance = self._calculate_distance(attacker_data, target_data, game_state)
        
        if distance > weapon_range:
            validation.violations.append(RuleViolation(
                category=RuleCategory.COMBAT,
                severity=ValidationResult.INVALID,
                rule_text="Attacks must be within weapon range",
                violation_description=f"Target is {distance} feet away, weapon range is {weapon_range} feet",
                suggested_fix="Move closer or use a ranged weapon"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
        
        # Check line of sight
        if not self._has_line_of_sight(attacker_data, target_data, game_state):
            validation.warnings.append(RuleViolation(
                category=RuleCategory.COMBAT,
                severity=ValidationResult.WARNING,
                rule_text="You need a clear path to your target",
                violation_description="Line of sight may be blocked",
                suggested_fix="Move to a position with clear line of sight"
            ))
        
        # Check for opportunity attacks
        if attack_data.get("is_ranged", False):
            enemies_in_melee = self._get_enemies_in_melee_range(attacker_data, game_state)
            if enemies_in_melee:
                validation.warnings.append(RuleViolation(
                    category=RuleCategory.COMBAT,
                    severity=ValidationResult.WARNING,
                    rule_text="Ranged attacks have disadvantage when enemies are within 5 feet",
                    violation_description="Enemies in melee range impose disadvantage on ranged attacks",
                    suggested_fix="Move away or make a melee attack instead"
                ))
                validation.auto_corrections["disadvantage"] = True
        
        return validation
    
    def validate_movement(self, movement_data: Dict[str, Any], character_data: Dict[str, Any], 
                         game_state: Dict[str, Any]) -> ActionValidation:
        """Validate movement"""
        validation = ActionValidation(is_valid=True, result=ValidationResult.VALID)
        
        distance = movement_data.get("distance", 0)
        movement_remaining = character_data.get("movement_remaining", 30)
        
        if distance > movement_remaining:
            validation.violations.append(RuleViolation(
                category=RuleCategory.MOVEMENT,
                severity=ValidationResult.INVALID,
                rule_text="You cannot move farther than your remaining movement speed",
                violation_description=f"Trying to move {distance} feet with only {movement_remaining} feet remaining",
                suggested_fix="Reduce movement distance or use the Dash action for extra movement"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
        
        # Check for difficult terrain
        if movement_data.get("through_difficult_terrain", False):
            actual_cost = distance * 2
            if actual_cost > movement_remaining:
                validation.violations.append(RuleViolation(
                    category=RuleCategory.MOVEMENT,
                    severity=ValidationResult.INVALID,
                    rule_text="Difficult terrain costs 2 feet of movement for every 1 foot moved",
                    violation_description=f"Moving {distance} feet through difficult terrain costs {actual_cost} feet",
                    suggested_fix="Reduce movement distance"
                ))
                validation.is_valid = False
                validation.result = ValidationResult.INVALID
            else:
                validation.auto_corrections["movement_cost"] = actual_cost
        
        # Check for opportunity attacks
        if self._would_provoke_opportunity_attacks(movement_data, character_data, game_state):
            enemies = self._get_threatening_enemies(character_data, game_state)
            validation.warnings.append(RuleViolation(
                category=RuleCategory.MOVEMENT,
                severity=ValidationResult.WARNING,
                rule_text="Moving out of an enemy's reach provokes opportunity attacks",
                violation_description=f"Movement may provoke opportunity attacks from {len(enemies)} enemies",
                suggested_fix="Use the Disengage action to avoid opportunity attacks"
            ))
        
        return validation
    
    def check_rule(self, rule_query: str, category: str = "general") -> Dict[str, Any]:
        """Check a specific rule using RAG"""
        if self.rag_agent:
            try:
                # Format query for rule lookup
                formatted_query = f"D&D 5e rule: {rule_query}"
                if category != "general":
                    formatted_query += f" category: {category}"
                
                result = self.rag_agent.query(formatted_query)
                if "error" not in result:
                    return {
                        "rule_text": result.get("answer", "Rule not found"),
                        "sources": result.get("sources", []),
                        "category": category,
                        "confidence": "high" if result.get("sources") else "low"
                    }
            except Exception as e:
                pass
        
        # Fallback to common rules
        for rule_key, rule_data in self.common_rules.items():
            if rule_query.lower() in rule_key.lower() or rule_query.lower() in rule_data["rule"].lower():
                return {
                    "rule_text": rule_data["rule"],
                    "sources": ["Built-in rules"],
                    "category": category,
                    "confidence": "medium"
                }
        
        return {
            "rule_text": f"Could not find specific rule for: {rule_query}",
            "sources": [],
            "category": category,
            "confidence": "low"
        }
    
    def get_condition_effects(self, condition_name: str) -> Dict[str, Any]:
        """Get effects of a specific condition"""
        # Common D&D 5e conditions
        conditions = {
            "blinded": {
                "effects": [
                    "Cannot see and automatically fails ability checks that require sight",
                    "Attack rolls have disadvantage",
                    "Attack rolls against you have advantage"
                ],
                "duration": "Varies by source"
            },
            "charmed": {
                "effects": [
                    "Cannot attack the charmer or target them with harmful abilities or spells",
                    "Charmer has advantage on social interaction checks"
                ],
                "duration": "Varies by source"
            },
            "deafened": {
                "effects": ["Cannot hear and automatically fails ability checks that require hearing"],
                "duration": "Varies by source"
            },
            "frightened": {
                "effects": [
                    "Disadvantage on ability checks and attack rolls while source is in line of sight",
                    "Cannot willingly move closer to source"
                ],
                "duration": "Varies by source"
            },
            "grappled": {
                "effects": [
                    "Speed becomes 0 and cannot benefit from bonuses to speed",
                    "Ends if grappler is incapacitated or moved away"
                ],
                "duration": "Until escape or grappler releases"
            },
            "incapacitated": {
                "effects": ["Cannot take actions or reactions"],
                "duration": "Varies by source"
            },
            "invisible": {
                "effects": [
                    "Cannot be seen without magical means",
                    "Attack rolls have advantage",
                    "Attack rolls against you have disadvantage"
                ],
                "duration": "Varies by source"
            },
            "paralyzed": {
                "effects": [
                    "Incapacitated and cannot move or speak",
                    "Automatically fails Strength and Dexterity saves",
                    "Attack rolls have advantage",
                    "Hits within 5 feet are critical hits"
                ],
                "duration": "Varies by source"
            },
            "poisoned": {
                "effects": ["Disadvantage on attack rolls and ability checks"],
                "duration": "Varies by source"
            },
            "prone": {
                "effects": [
                    "Can only crawl (costs extra movement) or stand up",
                    "Disadvantage on attack rolls",
                    "Attack rolls within 5 feet have advantage, beyond 5 feet have disadvantage"
                ],
                "duration": "Until you stand up"
            },
            "restrained": {
                "effects": [
                    "Speed becomes 0",
                    "Disadvantage on attack rolls and Dexterity saves",
                    "Attack rolls against you have advantage"
                ],
                "duration": "Varies by source"
            },
            "stunned": {
                "effects": [
                    "Incapacitated, cannot move, and can speak only falteringly",
                    "Automatically fails Strength and Dexterity saves",
                    "Attack rolls against you have advantage"
                ],
                "duration": "Varies by source"
            },
            "unconscious": {
                "effects": [
                    "Incapacitated, cannot move or speak, unaware of surroundings",
                    "Drops whatever it's holding and falls prone",
                    "Automatically fails Strength and Dexterity saves",
                    "Attack rolls have advantage",
                    "Hits within 5 feet are critical hits"
                ],
                "duration": "Until regains consciousness"
            }
        }
        
        condition_lower = condition_name.lower()
        if condition_lower in conditions:
            return conditions[condition_lower]
        
        # Try RAG for unknown conditions
        if self.rag_agent:
            try:
                result = self.rag_agent.query(f"D&D 5e condition {condition_name} effects")
                if "error" not in result:
                    return {
                        "effects": [result.get("answer", "")],
                        "duration": "See source material",
                        "source": "RAG lookup"
                    }
            except Exception:
                pass
        
        return {
            "effects": [f"Unknown condition: {condition_name}"],
            "duration": "Unknown",
            "source": "Not found"
        }
    
    def validate_ability_check(self, check_data: Dict[str, Any], character_data: Dict[str, Any]) -> ActionValidation:
        """Validate ability check"""
        validation = ActionValidation(is_valid=True, result=ValidationResult.VALID)
        
        ability = check_data.get("ability", "").lower()
        skill = check_data.get("skill", "")
        dc = check_data.get("dc", 10)
        
        valid_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        if ability not in valid_abilities:
            validation.violations.append(RuleViolation(
                category=RuleCategory.ABILITY_CHECKS,
                severity=ValidationResult.INVALID,
                rule_text="Ability checks must use a valid ability score",
                violation_description=f"'{ability}' is not a valid ability",
                suggested_fix=f"Use one of: {', '.join(valid_abilities)}"
            ))
            validation.is_valid = False
            validation.result = ValidationResult.INVALID
        
        # Check for impossible DCs
        if dc > 30:
            validation.warnings.append(RuleViolation(
                category=RuleCategory.ABILITY_CHECKS,
                severity=ValidationResult.WARNING,
                rule_text="DCs above 30 are nearly impossible",
                violation_description=f"DC {dc} is extremely high",
                suggested_fix="Consider lowering the DC or allowing alternative approaches"
            ))
        
        return validation
    
    def get_rule_summary(self, topic: str) -> Dict[str, Any]:
        """Get a summary of rules for a specific topic"""
        summaries = {
            "combat": {
                "overview": "D&D 5e combat is turn-based with initiative order",
                "key_rules": [
                    "Roll initiative (1d20 + Dex modifier) at start of combat",
                    "On your turn: move up to your speed, take one action, one bonus action",
                    "Attack roll (1d20 + ability + proficiency) vs target AC",
                    "Natural 20 is critical hit (roll damage dice twice)",
                    "Reactions can be taken on other turns when triggered"
                ]
            },
            "spellcasting": {
                "overview": "Spellcasting uses spell slots and follows specific rules",
                "key_rules": [
                    "Spell slots are expended when casting spells of 1st level or higher",
                    "Can only concentrate on one spell at a time",
                    "Taking damage requires Constitution save to maintain concentration",
                    "Spells with longer casting times cannot be cast as actions"
                ]
            },
            "movement": {
                "overview": "Characters can move up to their speed each turn",
                "key_rules": [
                    "Normal speed is 30 feet for most races",
                    "Difficult terrain costs 2 feet per 1 foot moved",
                    "Moving out of enemy reach provokes opportunity attacks",
                    "Dash action doubles movement for that turn"
                ]
            }
        }
        
        if topic.lower() in summaries:
            return summaries[topic.lower()]
        
        # Try RAG for unknown topics
        if self.rag_agent:
            try:
                result = self.rag_agent.query(f"D&D 5e {topic} rules summary")
                if "error" not in result:
                    return {
                        "overview": result.get("answer", ""),
                        "key_rules": ["See full rule text for details"],
                        "source": "RAG lookup"
                    }
            except Exception:
                pass
        
        return {
            "overview": f"No summary available for topic: {topic}",
            "key_rules": [],
            "source": "Not found"
        }
    
    # Helper methods
    
    def _format_validation_response(self, validation: ActionValidation) -> Dict[str, Any]:
        """Format validation response for message return"""
        return {
            "success": True,
            "validation": {
                "is_valid": validation.is_valid,
                "result": validation.result.value,
                "violations": [self._format_violation(v) for v in validation.violations],
                "warnings": [self._format_violation(w) for w in validation.warnings],
                "rule_clarifications": validation.rule_clarifications,
                "auto_corrections": validation.auto_corrections
            }
        }
    
    def _format_violation(self, violation: RuleViolation) -> Dict[str, Any]:
        """Format a rule violation for JSON response"""
        return {
            "category": violation.category.value,
            "severity": violation.severity.value,
            "rule_text": violation.rule_text,
            "violation_description": violation.violation_description,
            "suggested_fix": violation.suggested_fix,
            "source_reference": violation.source_reference
        }
    
    def _get_character_data(self, character_id: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get character data from game state"""
        players = game_state.get("players", {})
        npcs = game_state.get("npcs", {})
        
        if character_id in players:
            return players[character_id]
        elif character_id in npcs:
            return npcs[character_id]
        
        return None
    
    def _get_spell_rules(self, spell_name: str) -> Dict[str, Any]:
        """Get spell-specific rules from RAG"""
        if not self.rag_agent:
            return {}
        
        try:
            result = self.rag_agent.query(f"D&D 5e spell {spell_name} rules casting time range components")
            if "error" not in result:
                return {
                    "clarifications": [result.get("answer", "")],
                    "sources": result.get("sources", [])
                }
        except Exception:
            pass
        
        return {}
    
    def _calculate_distance(self, actor1: Dict[str, Any], actor2: Dict[str, Any], 
                          game_state: Dict[str, Any]) -> int:
        """Calculate distance between two actors (simplified)"""
        # This is a simplified implementation
        # In a real game, you'd calculate based on grid positions
        loc1 = actor1.get("location", "")
        loc2 = actor2.get("location", "")
        
        if loc1 == loc2:
            return 5  # Same location, assume melee range
        else:
            return 30  # Different locations, assume longer range
    
    def _has_line_of_sight(self, actor1: Dict[str, Any], actor2: Dict[str, Any], 
                          game_state: Dict[str, Any]) -> bool:
        """Check if actor1 has line of sight to actor2 (simplified)"""
        # Simplified implementation - in reality would check for obstacles
        return True
    
    def _get_enemies_in_melee_range(self, character: Dict[str, Any], game_state: Dict[str, Any]) -> List[str]:
        """Get list of enemies within melee range (simplified)"""
        # Simplified implementation
        return []
    
    def _would_provoke_opportunity_attacks(self, movement_data: Dict[str, Any], 
                                         character_data: Dict[str, Any], 
                                         game_state: Dict[str, Any]) -> bool:
        """Check if movement would provoke opportunity attacks (simplified)"""
        # Simplified implementation
        return False
    
    def _get_threatening_enemies(self, character_data: Dict[str, Any], 
                               game_state: Dict[str, Any]) -> List[str]:
        """Get list of enemies that could make opportunity attacks (simplified)"""
        # Simplified implementation
        return []
    
    def _validate_movement_action(self, action_data: Dict[str, Any], character: Dict[str, Any], 
                                game_state: Dict[str, Any]) -> ActionValidation:
        """Validate movement action"""
        return ActionValidation(is_valid=True, result=ValidationResult.VALID)
    
    def _validate_attack_action(self, action_data: Dict[str, Any], character: Dict[str, Any], 
                              game_state: Dict[str, Any]) -> ActionValidation:
        """Validate attack action"""
        return ActionValidation(is_valid=True, result=ValidationResult.VALID)
    
    def _validate_spell_action(self, action_data: Dict[str, Any], character: Dict[str, Any], 
                             game_state: Dict[str, Any]) -> ActionValidation:
        """Validate spell action"""
        return ActionValidation(is_valid=True, result=ValidationResult.VALID)
    
    def _merge_validations(self, validation1: ActionValidation, validation2: ActionValidation) -> ActionValidation:
        """Merge two validation results"""
        merged = ActionValidation(
            is_valid=validation1.is_valid and validation2.is_valid,
            result=ValidationResult.INVALID if not (validation1.is_valid and validation2.is_valid) else ValidationResult.VALID
        )
        merged.violations.extend(validation1.violations)
        merged.violations.extend(validation2.violations)
        merged.warnings.extend(validation1.warnings)
        merged.warnings.extend(validation2.warnings)
        merged.rule_clarifications.extend(validation1.rule_clarifications)
        merged.rule_clarifications.extend(validation2.rule_clarifications)
        merged.auto_corrections.update(validation1.auto_corrections)
        merged.auto_corrections.update(validation2.auto_corrections)
        
        return merged
    
    # Rule validation methods for common rules
    
    def _validate_action_economy(self, data: Dict[str, Any]) -> bool:
        """Validate action economy rules"""
        return True  # Simplified
    
    def _validate_movement_rules(self, data: Dict[str, Any]) -> bool:
        """Validate movement rules"""
        return True  # Simplified
    
    def _validate_attack_rules(self, data: Dict[str, Any]) -> bool:
        """Validate attack rules"""
        return True  # Simplified
    
    def _validate_spell_slot_rules(self, data: Dict[str, Any]) -> bool:
        """Validate spell slot rules"""
        return True  # Simplified
    
    def _validate_concentration_rules(self, data: Dict[str, Any]) -> bool:
        """Validate concentration rules"""
        return True  # Simplified
    
    def _validate_opportunity_attack_rules(self, data: Dict[str, Any]) -> bool:
        """Validate opportunity attack rules"""
        return True  # Simplified
    
    def process_tick(self):
        """Process rule enforcement tick - no regular processing needed"""
        pass


if __name__ == "__main__":
    # Test the rule enforcement agent
    agent = RuleEnforcementAgent()
    
    print("=== Rule Enforcement Agent Test ===")
    
    # Test rule checking
    rule_info = agent.check_rule("attack rolls")
    print(f"Attack roll rule: {rule_info}")
    
    # Test condition effects
    effects = agent.get_condition_effects("poisoned")
    print(f"Poisoned condition: {effects}")
    
    # Test action validation
    action = {
        "type": "attack",
        "actor": "player1",
        "target": "orc1"
    }
    game_state = {
        "players": {
            "player1": {
                "has_action": True,
                "location": "battlefield"
            }
        },
        "npcs": {
            "orc1": {
                "location": "battlefield"
            }
        }
    }
    
    validation = agent.validate_action(action, game_state)
    print(f"Action validation: {validation.is_valid}, Result: {validation.result}")
    
    # Test rule summary
    summary = agent.get_rule_summary("combat")
    print(f"Combat summary: {summary}")
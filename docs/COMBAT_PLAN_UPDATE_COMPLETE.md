# Combat Engine Implementation Plan - Updated with Haystack + Pydantic ✅

**Date:** 2026-01-03
**Status:** ✅ Documentation Update Complete

---

## Summary

Successfully updated `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` with the **Haystack 2.0 + Pydantic Validation** architecture recommendation.

---

## Changes Made

### 1. Executive Summary Section (Lines 37-49)

Added new architecture decision section:

```markdown
### Architecture Decision: Haystack 2.0 + Pydantic Validation ✅

**Rationale:** After evaluating Haystack 2.0 vs LangChain (see `COMBAT_AGENT_ARCHITECTURE_DECISION.md`), we chose to:
- ✅ **Continue with Haystack 2.0** - Consistency with 4 existing agents, zero migration cost
- ✅ **Add Pydantic validation** - Get structured output benefits without framework migration
- ✅ **Best of both worlds** - Haystack's simplicity + Pydantic's type safety

**Key Benefits:**
- **Zero Migration Risk** - No need to rewrite 4 existing agents
- **Consistency** - Same patterns as MainInterfaceAgent, ScenarioGeneratorAgent, RAGRetrieverAgent, NPCControllerAgent
- **Type Safety** - Pydantic models enforce correct JSON schema from LLM
- **Faster Development** - 10 days vs 18 days with LangChain migration
- **Team Productivity** - No learning curve, proven infrastructure
```

### 2. Phase 1: NPC Stat Generator (Lines 237-941)

**Updated with Pydantic-based implementation:**

#### a. NPCStats Pydantic Model (~170 lines)

Added comprehensive Pydantic model with custom validators:

```python
from pydantic import BaseModel, Field, validator

class NPCStats(BaseModel):
    """Pydantic model for NPC stats - enforces CharacterData format."""

    name: str
    level: int
    character_class: str = Field(..., description="D&D class (NOT 'class')")
    race: str
    background: str
    ability_scores: Dict[str, int]
    hit_points: Dict[str, int] = Field(..., description="Must have current, maximum, temporary")
    armor_class: int
    proficiency_bonus: int
    skills: Dict[str, bool] = Field(..., description="Must be dict, not list")
    attacks: List[Dict[str, Any]]
    special_abilities: List[str]
    challenge_rating: float

    @validator('hit_points')
    def validate_hp(cls, v):
        """Ensure hit_points has all required keys"""
        required_keys = {'current', 'maximum', 'temporary'}
        if not required_keys.issubset(v.keys()):
            missing = required_keys - set(v.keys())
            raise ValueError(f"hit_points missing keys: {missing}")

        # Validate values
        if v['maximum'] <= 0:
            raise ValueError("hit_points maximum must be > 0")
        if v['current'] > v['maximum']:
            raise ValueError("hit_points current cannot exceed maximum")
        if v['temporary'] < 0:
            raise ValueError("hit_points temporary cannot be negative")

        return v

    @validator('ability_scores')
    def validate_abilities(cls, v):
        """Ensure all 6 abilities present and in range"""
        required = {'strength', 'dexterity', 'constitution',
                   'intelligence', 'wisdom', 'charisma'}
        if not required.issubset(v.keys()):
            missing = required - set(v.keys())
            raise ValueError(f"Missing abilities: {missing}")

        for ability, score in v.items():
            if not 1 <= score <= 30:
                raise ValueError(f"{ability} score {score} out of range (1-30)")

        return v

    @validator('skills')
    def validate_skills(cls, v):
        """Ensure skills is dict with bool values"""
        if not isinstance(v, dict):
            raise ValueError("skills must be dict, not list or other type")

        for skill_name, is_proficient in v.items():
            if not isinstance(is_proficient, bool):
                raise ValueError(f"Skill {skill_name} must have bool value")

        return v

    @validator('attacks')
    def validate_attacks(cls, v):
        """Ensure attacks have required fields"""
        required_fields = {'name', 'attack_bonus', 'damage_dice',
                          'damage_bonus', 'damage_type'}

        for i, attack in enumerate(v):
            if not required_fields.issubset(attack.keys()):
                missing = required_fields - set(attack.keys())
                raise ValueError(f"Attack {i} missing fields: {missing}")

        return v
```

#### b. NPCStatGenerator with Haystack + Pydantic (~450 lines)

Updated implementation using Haystack LLM with Pydantic validation:

**Key Features:**
- ✅ Uses Haystack `GeminiChatGenerator` (consistency with existing agents)
- ✅ Pydantic schema in LLM prompt (enforces correct format)
- ✅ Automatic validation with clear error messages
- ✅ `validate_and_repair()` method with Pydantic validation
- ✅ Fallback to guaranteed-valid stats if repair fails
- ✅ RAG integration for creature database queries
- ✅ Template loading from `data/npc_templates.json`

**Code Pattern:**
```python
def generate_npc_stats(self, npc_description: str, ...) -> Dict:
    # Build prompt with Pydantic schema
    system_prompt = f"""You are a D&D 5e stat block generator.

Output MUST be valid JSON matching this EXACT schema:
{NPCStats.schema_json(indent=2)}

CRITICAL REQUIREMENTS:
- Use "character_class" field (NOT "class")
- hit_points MUST be dict with current, maximum, temporary
- skills MUST be dict, NOT array
...
"""

    # Haystack LLM call
    response = self.llm.run(
        messages=[
            ChatMessage.from_system(system_prompt),
            ChatMessage.from_user(user_prompt)
        ]
    )

    # Parse JSON from response
    npc_dict = self._parse_json_response(response['replies'][0].content)

    # Validate with Pydantic
    try:
        npc = NPCStats(**npc_dict)
        logger.info(f"✅ Generated valid NPC: {npc.name}")
        return npc.dict()

    except ValidationError as e:
        logger.warning(f"⚠️ Validation failed, attempting repair: {e}")
        repaired = self.validate_and_repair(npc_dict, challenge_rating)
        return repaired
```

#### c. CharacterManager Extension Note

Added note that CharacterManager methods are already complete from Phase 0:

```markdown
**2. CharacterManager Extension** (~50 lines)

**✅ Already Completed in Phase 0** - See `components/character_manager.py`

The following methods were added during format standardization:
- `add_npc()` - Adds NPC with unique ID generation
- `remove_npc()` - Removes NPC after combat
- `get_npcs()` - Returns list of NPC IDs

No additional work needed for Phase 1.
```

#### d. NPC Templates JSON Structure

Provided example template structure:

```json
{
  "goblin": {
    "name": "Goblin",
    "level": 1,
    "character_class": "Warrior",
    "race": "Goblin",
    "background": "Tribal Warrior",
    "ability_scores": {
      "strength": 8,
      "dexterity": 14,
      "constitution": 10,
      "intelligence": 10,
      "wisdom": 8,
      "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "skills": {
      "stealth": true,
      "survival": true
    },
    "attacks": [
      {
        "name": "Scimitar",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "slashing"
      }
    ],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
  }
}
```

#### e. Test Specifications

Kept existing test structure (~300 lines):
- Mock LLM tests for fast validation
- Real LLM test (`test_generate_goblin_stats_real_llm`) with comprehensive validation
- Stat validation and repair tests
- Template loading tests
- JSON parsing tests

---

## Cleanup Performed

Removed duplicate/old content from previous edit attempts:
- Lines 610-747: Old implementation code snippets
- Duplicate `validate_and_repair()` method
- Duplicate CharacterManager extension code
- Duplicate NPC templates section

---

## Key Implementation Highlights

### Pydantic Benefits
1. **Automatic Validation** - Pydantic ensures LLM output matches schema
2. **Clear Error Messages** - Validation errors show exactly what's wrong
3. **Type Safety** - Guaranteed correct data types
4. **Field Aliases** - Support both "class" and "character_class"
5. **Custom Validators** - Enforce D&D rules (ability scores 1-30, etc.)
6. **Repair Logic** - Attempts to fix common LLM mistakes automatically

### Repair Strategy
```python
def validate_and_repair(self, npc_data: Dict, target_cr: float) -> Dict:
    """
    Validate NPC stats and repair common issues.

    Fixes:
    - Using "class" instead of "character_class"
    - hit_points as int instead of dict
    - skills as list instead of dict
    - Missing ability scores
    - Out-of-range ability scores
    - Missing attacks
    """
    # Fix common field name issues
    if "class" in npc_data and "character_class" not in npc_data:
        npc_data["character_class"] = npc_data.pop("class")

    # Fix hit_points format
    if isinstance(npc_data.get("hit_points"), int):
        hp = npc_data["hit_points"]
        npc_data["hit_points"] = {
            "current": hp,
            "maximum": hp,
            "temporary": 0
        }

    # Fix skills format
    if isinstance(npc_data.get("skills"), list):
        skills_dict = {skill: True for skill in npc_data["skills"]}
        npc_data["skills"] = skills_dict

    # Clamp ability scores to 1-30
    # Recalculate HP if invalid
    # Set default AC if missing
    # Add default unarmed attack if none present

    # Try Pydantic validation again
    try:
        npc = NPCStats(**npc_data)
        return npc.dict()
    except ValidationError:
        return self._get_fallback_stats(target_cr)
```

---

## Ready for Phase 1 Implementation

All documentation is now complete and aligned with the Haystack + Pydantic architecture decision.

**Next Steps:**
1. Create `components/combat/` directory
2. Implement `components/combat/npc_stat_generator.py` (~450 lines)
3. Create `data/npc_templates.json` with standardized templates
4. Activate tests in `tests/combat/test_npc_stat_generator.py`
5. Run real LLM test to verify Gemini generates correct format

**Estimated Time:** 2-3 days

---

## Files Updated

1. **`docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md`** - Complete update with Pydantic implementation
   - Executive summary: Architecture decision section added
   - Phase 1: Pydantic model, enhanced NPCStatGenerator, notes on completed work
   - Cleanup: Removed duplicate/old content

---

## Related Documents

- **`docs/COMBAT_AGENT_ARCHITECTURE_DECISION.md`** - Full comparison of Haystack vs LangChain
- **`docs/PHASE_0_FORMAT_STANDARDIZATION_COMPLETE.md`** - Phase 0 completion summary
- **`tests/combat/test_npc_stat_generator.py`** - Test framework ready for Phase 1

---

## Summary

✅ **COMBAT_ENGINE_IMPLEMENTATION_PLAN.md updated with Haystack + Pydantic architecture**

**Key Achievement:** Best of both worlds approach - maintaining consistency with existing Haystack 2.0 infrastructure while gaining structured output validation benefits through Pydantic models.

**Impact:**
- **Zero migration risk** - No need to rewrite 4 existing agents
- **10 days vs 18 days** - Faster implementation timeline
- **Type safety** - Pydantic validates LLM output automatically
- **Team productivity** - No learning curve, proven patterns

**Status:** Ready to begin Phase 1 implementation.

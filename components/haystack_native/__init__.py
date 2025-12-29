"""
Native Haystack v2 components for D&D game pipeline modernization.
These components replace custom orchestration with proper Haystack patterns.
"""

from .parallel_components import (
    IntentBasedRouter, SimpleIntentRouter, GameIntentRouter,
    RAGFlagRouter, SkillCheckFlagRouter, ParallelResultsJoiner,
    AdaptiveRAGRouter, AdaptiveSkillRouter
)
from .validation_components import PydanticValidator, ScenarioValidator
from .legacy_adapters import GameEngineAdapter, CharacterManagerAdapter, SkillCheckAdapter, BypassComponent

__all__ = [
    # Intent and routing components
    "IntentBasedRouter",
    "SimpleIntentRouter",
    "GameIntentRouter",
    # Flag-based routing
    "RAGFlagRouter",
    "SkillCheckFlagRouter",
    "AdaptiveRAGRouter",
    "AdaptiveSkillRouter",
    # Parallel processing
    "ParallelResultsJoiner",
    # Validation components
    "PydanticValidator",
    "ScenarioValidator",
    # Legacy adapters
    "GameEngineAdapter",
    "CharacterManagerAdapter",
    "SkillCheckAdapter",
    "BypassComponent"
]
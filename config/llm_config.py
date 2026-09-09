"""
LLM Configuration System
Allows flexible configuration of different LLM models for different agents
Supports multiple providers including Gemini, OpenAI, and others
"""

import os
from typing import Dict, Any, Optional, Type
from dataclasses import dataclass, field
from enum import Enum

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


# Import available LLM generators
try:
    from haystack.components.generators.chat import OpenAIChatGenerator
    OPENAI_AVAILABLE = True
except (ImportError, TypeError, AttributeError) as e:
    OPENAI_AVAILABLE = False
    # Store the error for debugging if needed
    _OPENAI_IMPORT_ERROR = str(e)
    
# Plan 4: use the CURRENT Gemini SDK (see config/llm_utils.py for the port).
GEMINI_AVAILABLE = False
GEMINI_SDK = None
genai = None
genai_types = None

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
    GEMINI_SDK = "google-genai"
except ImportError:
    pass


# Import utility components for better compatibility
try:
    from config.llm_utils import StringToChatMessages
    UTILS_AVAILABLE = True
    
    # Try to import GeminiChatGenerator separately
    try:
        from config.llm_utils import GeminiChatGenerator
        GEMINI_CHAT_GENERATOR_AVAILABLE = True
    except (ImportError, TypeError, AttributeError) as e:
        GEMINI_CHAT_GENERATOR_AVAILABLE = False
        _GEMINI_GENERATOR_IMPORT_ERROR = str(e)
        logger.info(f"GEMINI_CHAT_GENERATOR_AVAILABLE: {GEMINI_CHAT_GENERATOR_AVAILABLE} {_GEMINI_GENERATOR_IMPORT_ERROR} Using fallback GeminiChatGenerator")
        
        # Create a simple fallback GeminiChatGenerator
        class GeminiChatGenerator:
            """Fallback Gemini generator when full Haystack integration isn't available"""
            
            def __init__(self, model_name: str, generation_config: dict = None):
                if not GEMINI_AVAILABLE:
                    logger.info(f"GEMINI_AVAILABLE: {GEMINI_AVAILABLE}")
                    raise ImportError(
                        "google-genai package not available (pip install google-genai)")
                
                self.model_name = model_name
                self.generation_config = generation_config or {}
                
                # Configure genai if not already configured
                api_key = os.getenv("GEMINI_API_KEY")
                if api_key:
                    # New SDK: no global configure(); the key goes to the Client.
                    pass
                
                # New SDK is client-based; the model name is passed per call.
                import os as _os
                _key = (_os.getenv("GEMINI_API_KEY")
                        or _os.getenv("GOOGLE_API_KEY"))
                self.client = genai.Client(api_key=_key) if _key else genai.Client()
                self.model_name = model_name
                self.generation_config = generation_config or {}
                
                # Add Haystack component metadata for compatibility
                self.__haystack_input__ = {
                    'messages': {'type': 'List[ChatMessage]'}, 
                    'tools': {'type': 'Optional[List[Any]]', 'default': None}
                }
                self.__haystack_output__ = {
                    'replies': {'type': 'List[ChatMessage]'}
                }
            
            def run(self, messages, tools=None):
                """Simple run method for basic functionality"""
                # Convert messages to prompt
                if hasattr(messages[0], 'text'):
                    prompt = messages[0].text
                elif hasattr(messages[0], 'content'):
                    prompt = messages[0].content
                else:
                    prompt = str(messages[0])
                
                # Generate response
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        **self.generation_config),
                )
                
                # Return in expected format
                class SimpleMessage:
                    def __init__(self, content):
                        self.text = content  # Primary property
                        self.content = content  # Backward compatibility
                
                return {"replies": [SimpleMessage(response.text)]}
        
except (ImportError, TypeError, AttributeError) as e:
    UTILS_AVAILABLE = False
    GEMINI_CHAT_GENERATOR_AVAILABLE = False
    _UTILS_IMPORT_ERROR = str(e)


class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"
    # Future providers can be added here
    # ANTHROPIC = "anthropic"
    # HUGGINGFACE = "huggingface"


@dataclass
class LLMConfig:
    """Configuration for a specific LLM instance"""
    provider: LLMProvider
    model: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)
    # gemini-2.5-flash spends INTERNAL REASONING TOKENS against
    # max_output_tokens before writing a single visible character. A live
    # playtest showed thoughts_token_count=802 and 956 against the interface
    # agent's 1000-token cap, so its JSON was truncated mid-string and the
    # parser reported the misleading "No JSON object found in response".
    #
    # 0 disables thinking (right for deterministic extraction/classification);
    # None leaves the model's default (right for creative narration).
    thinking_budget: Optional[int] = None


@dataclass
class AgentLLMConfig:
    """Complete LLM configuration for all agents"""
    scenario_generator: LLMConfig
    rag_retriever: LLMConfig
    npc_controller: LLMConfig
    main_interface: LLMConfig
    default_fallback: LLMConfig
    # Combat agents. Optional so existing callers that build this object
    # positionally keep working; None means "use default_fallback", and
    # __post_init__ fills in tuned values instead.
    npc_combat_ai: Optional[LLMConfig] = None
    combat_init: Optional[LLMConfig] = None
    combat_narrative: Optional[LLMConfig] = None

    def __post_init__(self):
        model = self.default_fallback.model
        provider = self.default_fallback.provider
        # thinking_budget=0 for the two that must return parseable JSON.
        if self.npc_combat_ai is None:
            self.npc_combat_ai = LLMConfig(provider=provider, model=model,
                                           temperature=0.4, max_tokens=2000,
                                           thinking_budget=0)
        if self.combat_init is None:
            self.combat_init = LLMConfig(provider=provider, model=model,
                                          temperature=0.3, max_tokens=3000,
                                          thinking_budget=0)
        # Narration is prose, so leave the model's own reasoning enabled.
        if self.combat_narrative is None:
            self.combat_narrative = LLMConfig(provider=provider, model=model,
                                               temperature=0.9, max_tokens=2000)


class LLMConfigManager:
    """Manages LLM configurations and creates appropriate generators"""
    
    def __init__(self, config: Optional[AgentLLMConfig] = None):
        self.config = config or self._get_default_config()
        self._validate_config()
    
    def _get_default_config(self) -> AgentLLMConfig:
        """Create default configuration based on available providers"""
        
        # Prefer Gemini, fallback to OpenAI
        if GEMINI_AVAILABLE:
            default_provider = LLMProvider.GEMINI
            default_model = "gemini-2.5-flash"
        elif OPENAI_AVAILABLE:
            default_provider = LLMProvider.OPENAI
            default_model = "gpt-4o-mini"
        else:
            raise ImportError("No supported LLM providers available. Install google-genai or openai.")
        
        # Create default config for each agent
        default_llm_config = LLMConfig(
            provider=default_provider,
            model=default_model,
            temperature=0.7,
            max_tokens=2000
        )
        
        return AgentLLMConfig(
            scenario_generator=LLMConfig(
                provider=default_provider,
                model=default_model,
                temperature=0.8,  # More creative for scenarios
                max_tokens=8000  # Increased from 3000 to handle full scenario JSON
            ),
            rag_retriever=LLMConfig(
                provider=default_provider,
                model=default_model,
                temperature=0.3,  # More focused for retrieval
                max_tokens=1500
            ),
            npc_controller=LLMConfig(
                provider=default_provider,
                model=default_model,
                temperature=0.9,  # Most creative for dialogue
                max_tokens=2000
            ),
            main_interface=LLMConfig(
                provider=default_provider,
                model=default_model,
                temperature=0.5,  # Balanced for parsing
                # Intent classification is deterministic extraction, not
                # reasoning: thinking burned 802-956 of the old 1000-token cap
                # and truncated the JSON mid-string. Disable thinking and leave
                # comfortable headroom — the payload itself is ~200 tokens.
                max_tokens=2000,
                thinking_budget=0,
            ),
            default_fallback=default_llm_config
        )
    
    def _validate_config(self):
        """Validate that the configuration is usable"""
        configs = [
            self.config.scenario_generator,
            self.config.rag_retriever,
            self.config.npc_controller,
            self.config.main_interface,
            self.config.default_fallback
        ]
        
        for config in configs:
            if config.provider == LLMProvider.OPENAI and not OPENAI_AVAILABLE:
                raise ImportError(f"OpenAI requested but openai package not available")
            elif config.provider == LLMProvider.GEMINI and not GEMINI_AVAILABLE:
                raise ImportError("Gemini requested but google-genai package not available")
    
    def create_generator(self, agent_name: str, response_schema: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create LLM generator for the specified agent.

        Args:
            agent_name: Name of the agent to create generator for
            response_schema: Optional JSON schema for structured output (Gemini only)

        Returns:
            Configured chat generator
        """

        # Get config for the agent
        config_map = {
            "scenario_generator": self.config.scenario_generator,
            "rag_retriever": self.config.rag_retriever,
            "npc_controller": self.config.npc_controller,
            "main_interface": self.config.main_interface,
            # Combat agents were NOT listed here, so they silently took
            # default_fallback — which leaves thinking ENABLED. In a live combat
            # every npc_combat_ai call logged "Failed to parse JSON from LLM:
            # Expecting value: line 1 column 1 (char 0)": reasoning tokens ate
            # the budget and the visible reply was empty, so every NPC fell back
            # to "attack the nearest player" and tactical AI never ran.
            # These are structured-extraction tasks, exactly like the interface
            # agent, so thinking is off.
            "npc_combat_ai": self.config.npc_combat_ai,
            "combat_init": self.config.combat_init,
            "combat_narrative": self.config.combat_narrative,
        }

        llm_config = config_map.get(agent_name, self.config.default_fallback)

        # Create the appropriate generator
        if llm_config.provider == LLMProvider.OPENAI:
            return self._create_openai_generator(llm_config, response_schema)
        elif llm_config.provider == LLMProvider.GEMINI:
            return self._create_gemini_generator(llm_config, response_schema)
        else:
            raise ValueError(f"Unsupported provider: {llm_config.provider}")
    
    def _create_openai_generator(self, config: LLMConfig, response_schema: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create OpenAI chat generator.

        Args:
            config: LLM configuration
            response_schema: Optional JSON schema (not used for OpenAI)

        Returns:
            OpenAI chat generator
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI requested but openai package not available")
        
        # Prepare parameters
        params = {
            "model": config.model,
        }
        
        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.api_key:
            params["api_key"] = config.api_key
        if config.base_url:
            params["api_base_url"] = config.base_url
        
        # Add extra parameters
        params.update(config.extra_params)
        
        return OpenAIChatGenerator(**params)
    
    def _create_gemini_generator(self, config: LLMConfig, response_schema: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create Gemini chat generator with proper configuration.

        Args:
            config: LLM configuration
            response_schema: Optional JSON schema for structured output

        Returns:
            Gemini chat generator with optional structured output
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini requested but google-genai package not available")

        # Configure the Gemini API with the API key
        api_key = config.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set or api_key not provided")

        # New SDK: no global configure(); the key goes to the Client.

        # Create generation config
        generation_config = {}
        if config.temperature is not None:
            generation_config["temperature"] = config.temperature
        if config.max_tokens:
            generation_config["max_output_tokens"] = config.max_tokens
        if config.thinking_budget is not None:
            # Passed as a plain dict; llm_utils builds the ThinkingConfig, so
            # this module stays free of SDK types.
            generation_config["thinking_config"] = {
                "thinking_budget": config.thinking_budget
            }

        # Add extra parameters
        generation_config.update(config.extra_params)

        # Use custom GeminiChatGenerator (supports structured output via response_schema)
        if not UTILS_AVAILABLE:
            raise ImportError("config.llm_utils not available for Gemini generator")

        from config.llm_utils import GeminiChatGenerator

        logger.debug(f"🔧 Using custom GeminiChatGenerator for model: {config.model}")

        # Pass response_schema if provided (for structured output)
        generator = GeminiChatGenerator(
            model_name=config.model,
            generation_config=generation_config,
            response_schema=response_schema  # Pass schema for structured output
        )

        if response_schema:
            logger.info(f"🎯 Successfully created custom GeminiChatGenerator with structured output schema")
        else:
            logger.info(f"✅ Successfully created custom GeminiChatGenerator")
        return generator
    
    def get_config_summary(self) -> Dict[str, str]:
        """Get a summary of the current configuration"""
        return {
            "scenario_generator": f"{self.config.scenario_generator.provider.value}:{self.config.scenario_generator.model}",
            "rag_retriever": f"{self.config.rag_retriever.provider.value}:{self.config.rag_retriever.model}",
            "npc_controller": f"{self.config.npc_controller.provider.value}:{self.config.npc_controller.model}",
            "main_interface": f"{self.config.main_interface.provider.value}:{self.config.main_interface.model}",
            "openai_available": OPENAI_AVAILABLE,
            "gemini_available": GEMINI_AVAILABLE
        }


# Environment-based configuration loader
def _tuned_agent_defaults() -> Dict[str, LLMConfig]:
    """
    The tuned per-agent baseline, shared by both config paths.

    Kept in ONE place because the values previously existed only inside
    _create_default_config(), which get_global_config_manager() never reaches —
    so they silently did not apply to the running game.
    """
    if GEMINI_AVAILABLE:
        provider, model = LLMProvider.GEMINI, "gemini-2.5-flash"
    elif OPENAI_AVAILABLE:
        provider, model = LLMProvider.OPENAI, "gpt-4o-mini"
    else:
        raise ImportError(
            "No supported LLM providers available. Install google-genai or openai.")

    return {
        # Creative narration: needs room for the full scenario JSON, and
        # benefits from the model's own reasoning, so thinking is left enabled.
        "scenario_generator": LLMConfig(provider=provider, model=model,
                                        temperature=0.8, max_tokens=8000),
        "rag_retriever": LLMConfig(provider=provider, model=model,
                                   temperature=0.3, max_tokens=2000),
        "npc_controller": LLMConfig(provider=provider, model=model,
                                    temperature=0.9, max_tokens=2000),
        # Deterministic extraction. thinking_budget=0 because reasoning tokens
        # count against max_output_tokens: a live run spent 802 and 956 of a
        # 1000-token cap thinking, truncating the intent JSON mid-string.
        "main_interface": LLMConfig(provider=provider, model=model,
                                    temperature=0.5, max_tokens=2000,
                                    thinking_budget=0),
        "default_fallback": LLMConfig(provider=provider, model=model,
                                      temperature=0.7, max_tokens=2000),
    }


def load_config_from_environment() -> AgentLLMConfig:
    """
    Load LLM configuration from environment variables.

    This is the path get_global_config_manager() actually takes, so it — not
    _create_default_config() — decides what the running game uses. It previously
    built every LLMConfig from scratch, leaving max_tokens and temperature None
    whenever the (normally unset) env vars were absent. The tuned per-agent
    values were therefore dead code: the scenario agent never got its 8000-token
    cap and the interface agent never got temperature=0.5.

    Env vars now OVERRIDE the tuned defaults instead of replacing them.
    """

    # The tuned per-agent baseline (max_tokens, temperature, thinking_budget).
    baseline = _tuned_agent_defaults()

    def get_llm_config(prefix: str, default: Optional[LLMConfig] = None) -> LLMConfig:
        # Determine default provider based on availability
        if GEMINI_AVAILABLE:
            default_provider = "gemini"
            default_model = "gemini-2.5-flash"
        else:
            default_provider = "openai"
            default_model = "gpt-4o-mini"
            
        provider_str = os.getenv(f"{prefix}_PROVIDER", default_provider)
        provider = LLMProvider(provider_str)
        
        model = os.getenv(f"{prefix}_MODEL", default_model)
        max_tokens = os.getenv(f"{prefix}_MAX_TOKENS")
        temperature = os.getenv(f"{prefix}_TEMPERATURE")
        api_key = os.getenv(f"{prefix}_API_KEY")
        base_url = os.getenv(f"{prefix}_BASE_URL")
        thinking_budget = os.getenv(f"{prefix}_THINKING_BUDGET")
        
        return LLMConfig(
            provider=provider,
            model=model,
            # Fall back to the tuned per-agent value, not to None.
            max_tokens=(int(max_tokens) if max_tokens
                        else (default.max_tokens if default else None)),
            temperature=(float(temperature) if temperature
                         else (default.temperature if default else None)),
            api_key=api_key,
            base_url=base_url,
            thinking_budget=(int(thinking_budget) if thinking_budget is not None
                             else (default.thinking_budget if default else None)),
        )

    return AgentLLMConfig(
        scenario_generator=get_llm_config("SCENARIO_GENERATOR",
                                         baseline["scenario_generator"]),
        rag_retriever=get_llm_config("RAG_RETRIEVER", baseline["rag_retriever"]),
        npc_controller=get_llm_config("NPC_CONTROLLER", baseline["npc_controller"]),
        main_interface=get_llm_config("MAIN_INTERFACE", baseline["main_interface"]),
        default_fallback=get_llm_config("DEFAULT_FALLBACK",
                                       baseline["default_fallback"]),
    )


# Factory functions for easy configuration
def create_gemini_config(model: str = "gemini-2.5-flash") -> AgentLLMConfig:
    """Create configuration using Gemini for all agents"""
    if not GEMINI_AVAILABLE:
        raise ImportError("Gemini not available. Install google-genai.")
    
    base_config = LLMConfig(
        provider=LLMProvider.GEMINI,
        model=model
    )
    
    return AgentLLMConfig(
        scenario_generator=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.8, max_tokens=8000),
        rag_retriever=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.3, max_tokens=1500),
        npc_controller=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.9, max_tokens=2000),
        main_interface=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.5,
                                 # thinking_budget=0: see the main_interface comment in
                                 # _create_default_config — thinking truncated the intent JSON.
                                 max_tokens=2000, thinking_budget=0),
        default_fallback=base_config
    )


def create_mixed_config() -> AgentLLMConfig:
    """Create a mixed configuration with different providers for different agents"""
    # Choose providers based on availability
    primary_provider = LLMProvider.GEMINI if GEMINI_AVAILABLE else LLMProvider.OPENAI
    primary_model = "gemini-2.5-flash" if GEMINI_AVAILABLE else "gpt-4o-mini"

    # Use different provider for interface if possible
    interface_provider = (LLMProvider.OPENAI if OPENAI_AVAILABLE else
                         (LLMProvider.GEMINI if GEMINI_AVAILABLE else primary_provider))
    interface_model = "gpt-4o-mini" if OPENAI_AVAILABLE else ("gemini-2.5-flash" if GEMINI_AVAILABLE else primary_model)
    
    return AgentLLMConfig(
        scenario_generator=LLMConfig(
            provider=primary_provider,
            model=primary_model,
            temperature=0.8,
            max_tokens=8000  # Increased from 3000 to handle full scenario JSON
        ),
        rag_retriever=LLMConfig(
            provider=primary_provider,
            model=primary_model,
            temperature=0.3,
            max_tokens=1500
        ),
        npc_controller=LLMConfig(
            provider=primary_provider,
            model=primary_model,
            temperature=0.9,
            max_tokens=2000
        ),
        main_interface=LLMConfig(
            provider=interface_provider,
            model=interface_model,
            temperature=0.5,
            # thinking_budget=0: see the main_interface comment in
            # _create_default_config — thinking truncated the intent JSON.
            max_tokens=2000,
            thinking_budget=0,
        ),
        default_fallback=LLMConfig(
            provider=primary_provider,
            model=primary_model
        )
    )


# Global configuration manager instance
_global_config_manager: Optional[LLMConfigManager] = None


def get_global_config_manager() -> LLMConfigManager:
    """Get or create the global configuration manager"""
    global _global_config_manager
    if _global_config_manager is None:
        try:
            # Try environment config first
            config = load_config_from_environment()
            _global_config_manager = LLMConfigManager(config)
        except:
            # Fall back to default config
            _global_config_manager = LLMConfigManager()
    return _global_config_manager


def set_global_config_manager(manager: LLMConfigManager):
    """Set the global configuration manager"""
    global _global_config_manager
    _global_config_manager = manager


# Example usage
if __name__ == "__main__":
    print("=== LLM Configuration Manager Test ===")
    
    # Test default configuration
    manager = LLMConfigManager()
    print("Default Configuration:")
    for agent, config in manager.get_config_summary().items():
        logger.debug(f"  {agent}: {config}")
    
    # Test generator creation
    try:
        scenario_gen = manager.create_generator("scenario_generator")
        logger.info(f"\n✅ Created scenario generator: {type(scenario_gen).__name__}")
        
        rag_gen = manager.create_generator("rag_retriever")
        logger.info(f"✅ Created RAG generator: {type(rag_gen).__name__}")
        
    except Exception as e:
        logger.error(f"Generator creation failed: {e}")
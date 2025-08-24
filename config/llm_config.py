"""
LLM Configuration System
Allows flexible configuration of different LLM models for different agents
Supports multiple providers including Apple GenAI, OpenAI, and others
"""

import os
from typing import Dict, Any, Optional, Type
from dataclasses import dataclass, field
from enum import Enum

# Import available LLM generators
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    APPLE_AVAILABLE = True
except ImportError:
    APPLE_AVAILABLE = False
    
try:
    from haystack.components.generators.chat import OpenAIChatGenerator
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Import utility components for better compatibility
try:
    from config.llm_utils import create_apple_genai_compatible_generator, StringToChatMessages
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False


class LLMProvider(Enum):
    """Supported LLM providers"""
    APPLE_GENAI = "apple_genai"
    OPENAI = "openai"
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


@dataclass
class AgentLLMConfig:
    """Complete LLM configuration for all agents"""
    scenario_generator: LLMConfig
    rag_retriever: LLMConfig
    npc_controller: LLMConfig
    main_interface: LLMConfig
    default_fallback: LLMConfig


class LLMConfigManager:
    """Manages LLM configurations and creates appropriate generators"""
    
    def __init__(self, config: Optional[AgentLLMConfig] = None):
        self.config = config or self._get_default_config()
        self._validate_config()
    
    def _get_default_config(self) -> AgentLLMConfig:
        """Create default configuration based on available providers"""
        
        # Prefer Apple GenAI if available, fallback to OpenAI
        if APPLE_AVAILABLE:
            default_provider = LLMProvider.APPLE_GENAI
            default_model = "aws:anthropic.claude-sonnet-4-20250514-v1:0"  # Apple GenAI model
        elif OPENAI_AVAILABLE:
            default_provider = LLMProvider.OPENAI
            default_model = "gpt-4o-mini"
        else:
            raise ImportError("No supported LLM providers available. Install hwtgenielib or openai package.")
        
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
                max_tokens=3000
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
                max_tokens=1000
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
            if config.provider == LLMProvider.APPLE_GENAI and not APPLE_AVAILABLE:
                raise ImportError(f"Apple GenAI requested but hwtgenielib not available")
            elif config.provider == LLMProvider.OPENAI and not OPENAI_AVAILABLE:
                raise ImportError(f"OpenAI requested but openai package not available")
    
    def create_generator(self, agent_name: str) -> Any:
        """Create LLM generator for the specified agent"""
        
        # Get config for the agent
        config_map = {
            "scenario_generator": self.config.scenario_generator,
            "rag_retriever": self.config.rag_retriever,
            "npc_controller": self.config.npc_controller,
            "main_interface": self.config.main_interface
        }
        
        llm_config = config_map.get(agent_name, self.config.default_fallback)
        
        # Create the appropriate generator
        if llm_config.provider == LLMProvider.APPLE_GENAI:
            return self._create_apple_generator(llm_config)
        elif llm_config.provider == LLMProvider.OPENAI:
            return self._create_openai_generator(llm_config)
        else:
            raise ValueError(f"Unsupported provider: {llm_config.provider}")
    
    def _create_apple_generator(self, config: LLMConfig) -> Any:
        """Create Apple GenAI chat generator with proper message handling"""
        if not APPLE_AVAILABLE:
            raise ImportError("Apple GenAI requested but hwtgenielib not available")
        
        # AppleGenAI uses generation_kwargs for LLM parameters
        generation_kwargs = {}
        
        # Add supported generation parameters
        if config.temperature is not None:
            generation_kwargs["temperature"] = config.temperature
        if config.max_tokens:
            generation_kwargs["max_tokens"] = config.max_tokens
        
        # Add extra generation parameters
        generation_kwargs.update(config.extra_params)
        
        # Prepare main parameters
        params = {
            "model": config.model,
        }
        
        # Add generation_kwargs if we have any
        if generation_kwargs:
            params["generation_kwargs"] = generation_kwargs
        
        # Use utility function if available for better compatibility
        if UTILS_AVAILABLE:
            return create_apple_genai_compatible_generator(config.model, **{k: v for k, v in params.items() if k != "model"})
        else:
            return AppleGenAIChatGenerator(**params)
    
    def _create_openai_generator(self, config: LLMConfig) -> Any:
        """Create OpenAI chat generator"""
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
    
    def get_config_summary(self) -> Dict[str, str]:
        """Get a summary of the current configuration"""
        return {
            "scenario_generator": f"{self.config.scenario_generator.provider.value}:{self.config.scenario_generator.model}",
            "rag_retriever": f"{self.config.rag_retriever.provider.value}:{self.config.rag_retriever.model}",
            "npc_controller": f"{self.config.npc_controller.provider.value}:{self.config.npc_controller.model}",
            "main_interface": f"{self.config.main_interface.provider.value}:{self.config.main_interface.model}",
            "apple_available": APPLE_AVAILABLE,
            "openai_available": OPENAI_AVAILABLE
        }


# Environment-based configuration loader
def load_config_from_environment() -> AgentLLMConfig:
    """Load LLM configuration from environment variables"""
    
    def get_llm_config(prefix: str) -> LLMConfig:
        provider_str = os.getenv(f"{prefix}_PROVIDER", "apple_genai" if APPLE_AVAILABLE else "openai")
        provider = LLMProvider(provider_str)
        
        model = os.getenv(f"{prefix}_MODEL", "gpt-4o-mini")
        max_tokens = os.getenv(f"{prefix}_MAX_TOKENS")
        temperature = os.getenv(f"{prefix}_TEMPERATURE")
        api_key = os.getenv(f"{prefix}_API_KEY")
        base_url = os.getenv(f"{prefix}_BASE_URL")
        
        return LLMConfig(
            provider=provider,
            model=model,
            max_tokens=int(max_tokens) if max_tokens else None,
            temperature=float(temperature) if temperature else None,
            api_key=api_key,
            base_url=base_url
        )
    
    return AgentLLMConfig(
        scenario_generator=get_llm_config("SCENARIO_GENERATOR"),
        rag_retriever=get_llm_config("RAG_RETRIEVER"),
        npc_controller=get_llm_config("NPC_CONTROLLER"),
        main_interface=get_llm_config("MAIN_INTERFACE"),
        default_fallback=get_llm_config("DEFAULT_FALLBACK")
    )


# Factory functions for easy configuration
def create_apple_genai_config(model: str = "aws:anthropic.claude-sonnet-4-20250514-v1:0") -> AgentLLMConfig:
    """Create configuration using Apple GenAI for all agents"""
    if not APPLE_AVAILABLE:
        raise ImportError("Apple GenAI not available. Install hwtgenielib.")
    
    base_config = LLMConfig(
        provider=LLMProvider.APPLE_GENAI,
        model=model
    )
    
    return AgentLLMConfig(
        scenario_generator=LLMConfig(provider=LLMProvider.APPLE_GENAI, model=model, temperature=0.8, max_tokens=3000),
        rag_retriever=LLMConfig(provider=LLMProvider.APPLE_GENAI, model=model, temperature=0.3, max_tokens=1500),
        npc_controller=LLMConfig(provider=LLMProvider.APPLE_GENAI, model=model, temperature=0.9, max_tokens=2000),
        main_interface=LLMConfig(provider=LLMProvider.APPLE_GENAI, model=model, temperature=0.5, max_tokens=1000),
        default_fallback=base_config
    )


def create_mixed_config() -> AgentLLMConfig:
    """Create a mixed configuration with different providers for different agents"""
    return AgentLLMConfig(
        scenario_generator=LLMConfig(
            provider=LLMProvider.APPLE_GENAI if APPLE_AVAILABLE else LLMProvider.OPENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0" if APPLE_AVAILABLE else "gpt-4o-mini",
            temperature=0.8,
            max_tokens=3000
        ),
        rag_retriever=LLMConfig(
            provider=LLMProvider.APPLE_GENAI if APPLE_AVAILABLE else LLMProvider.OPENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0" if APPLE_AVAILABLE else "gpt-4o-mini",
            temperature=0.3,
            max_tokens=1500
        ),
        npc_controller=LLMConfig(
            provider=LLMProvider.APPLE_GENAI if APPLE_AVAILABLE else LLMProvider.OPENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0" if APPLE_AVAILABLE else "gpt-4o-mini",
            temperature=0.9,
            max_tokens=2000
        ),
        main_interface=LLMConfig(
            provider=LLMProvider.OPENAI if OPENAI_AVAILABLE else LLMProvider.APPLE_GENAI,
            model="gpt-4o-mini" if OPENAI_AVAILABLE else "aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.5,
            max_tokens=1000
        ),
        default_fallback=LLMConfig(
            provider=LLMProvider.APPLE_GENAI if APPLE_AVAILABLE else LLMProvider.OPENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0" if APPLE_AVAILABLE else "gpt-4o-mini"
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
        print(f"  {agent}: {config}")
    
    # Test generator creation
    try:
        scenario_gen = manager.create_generator("scenario_generator")
        print(f"\n✅ Created scenario generator: {type(scenario_gen).__name__}")
        
        rag_gen = manager.create_generator("rag_retriever")
        print(f"✅ Created RAG generator: {type(rag_gen).__name__}")
        
    except Exception as e:
        print(f"❌ Generator creation failed: {e}")
    
    # Test Apple GenAI specific config if available
    if APPLE_AVAILABLE:
        try:
            apple_config = create_apple_genai_config()
            apple_manager = LLMConfigManager(apple_config)
            print(f"\n✅ Apple GenAI config created")
        except Exception as e:
            print(f"❌ Apple GenAI config failed: {e}")
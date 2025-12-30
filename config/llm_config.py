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
    
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

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

        # Create a simple fallback GeminiChatGenerator for new SDK
        class GeminiChatGenerator:
            """Fallback Gemini generator when full Haystack integration isn't available (new SDK)"""

            def __init__(self, model_name: str, generation_config: dict = None):
                if not GEMINI_AVAILABLE:
                    logger.info(f"GEMINI_AVAILABLE: {GEMINI_AVAILABLE}")
                    raise ImportError("google-genai package not available")

                self.model_name = model_name
                self.generation_config = generation_config or {}

                # Initialize client with new SDK
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY environment variable not set")

                self.client = genai.Client(api_key=api_key)

                # Add Haystack component metadata for compatibility
                self.__haystack_input__ = {
                    'messages': {'type': 'List[ChatMessage]'},
                    'tools': {'type': 'Optional[List[Any]]', 'default': None}
                }
                self.__haystack_output__ = {
                    'replies': {'type': 'List[ChatMessage]'}
                }

            def run(self, messages, tools=None):
                """Simple run method for basic functionality using new SDK"""
                # Convert messages to prompt
                if hasattr(messages[0], 'text'):
                    prompt = messages[0].text
                elif hasattr(messages[0], 'content'):
                    prompt = messages[0].content
                else:
                    prompt = str(messages[0])

                # Build config
                config = types.GenerateContentConfig(
                    temperature=self.generation_config.get('temperature', 0.7),
                    max_output_tokens=self.generation_config.get('max_output_tokens', 2000)
                )

                # Generate response using new SDK
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
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
        
        # Prefer Gemini, fallback to OpenAI
        if GEMINI_AVAILABLE:
            default_provider = LLMProvider.GEMINI
            default_model = "gemini-2.0-flash"
        elif OPENAI_AVAILABLE:
            default_provider = LLMProvider.OPENAI
            default_model = "gpt-4o-mini"
        else:
            raise ImportError("No supported LLM providers available. Install google-generativeai or openai package.")
        
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
            if config.provider == LLMProvider.OPENAI and not OPENAI_AVAILABLE:
                raise ImportError(f"OpenAI requested but openai package not available")
            elif config.provider == LLMProvider.GEMINI and not GEMINI_AVAILABLE:
                raise ImportError(f"Gemini requested but google-generativeai package not available")
    
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
        if llm_config.provider == LLMProvider.OPENAI:
            return self._create_openai_generator(llm_config)
        elif llm_config.provider == LLMProvider.GEMINI:
            return self._create_gemini_generator(llm_config)
        else:
            raise ValueError(f"Unsupported provider: {llm_config.provider}")
    
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
    
    def _create_gemini_generator(self, config: LLMConfig) -> Any:
        """Create Gemini chat generator with proper configuration (new SDK)"""
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini requested but google-genai package not available")

        # Validate API key is available
        api_key = config.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set or api_key not provided")

        # Create generation config
        generation_config = {}
        if config.temperature is not None:
            generation_config["temperature"] = config.temperature
        if config.max_tokens:
            generation_config["max_output_tokens"] = config.max_tokens

        # Add extra parameters
        generation_config.update(config.extra_params)

        # Try to use official Haystack Google GenAI integration (v2.17+) if available
        try:
            from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
            logger.debug(f"🔧 Using official GoogleGenAIChatGenerator for model: {config.model}")

            # Create official Haystack Gemini generator (handles tools/function-calling)
            generator = GoogleGenAIChatGenerator(
                model=config.model
                # Note: generation_config is not a valid parameter for this generator
                # The official GoogleGenAIChatGenerator uses different parameter names
            )

            logger.info(f"✅ Successfully created GoogleGenAIChatGenerator")
            return generator
        except ImportError:
            # Fall back to custom GeminiChatGenerator from llm_utils
            logger.warning(f"Official haystack_integrations not available, using custom GeminiChatGenerator")

            if not UTILS_AVAILABLE:
                raise ImportError("Neither haystack_integrations nor config.llm_utils available for Gemini generator")

            from config.llm_utils import GeminiChatGenerator

            logger.debug(f"🔧 Using custom GeminiChatGenerator for model: {config.model}")

            # GeminiChatGenerator handles client initialization internally with new SDK
            generator = GeminiChatGenerator(
                model_name=config.model,
                generation_config=generation_config
            )

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
def load_config_from_environment() -> AgentLLMConfig:
    """Load LLM configuration from environment variables"""
    
    def get_llm_config(prefix: str) -> LLMConfig:
        # Determine default provider based on availability
        if GEMINI_AVAILABLE:
            default_provider = "gemini"  
            default_model = "gemini-2.0-flash"
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
def create_gemini_config(model: str = "gemini-2.0-flash") -> AgentLLMConfig:
    """Create configuration using Gemini for all agents"""
    if not GEMINI_AVAILABLE:
        raise ImportError("Gemini not available. Install google-generativeai.")
    
    base_config = LLMConfig(
        provider=LLMProvider.GEMINI,
        model=model
    )
    
    return AgentLLMConfig(
        scenario_generator=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.8, max_tokens=3000),
        rag_retriever=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.3, max_tokens=1500),
        npc_controller=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.9, max_tokens=2000),
        main_interface=LLMConfig(provider=LLMProvider.GEMINI, model=model, temperature=0.5, max_tokens=1000),
        default_fallback=base_config
    )


def create_mixed_config() -> AgentLLMConfig:
    """Create a mixed configuration with different providers for different agents"""
    # Choose providers based on availability
    primary_provider = LLMProvider.GEMINI if GEMINI_AVAILABLE else LLMProvider.OPENAI
    primary_model = "gemini-2.0-flash" if GEMINI_AVAILABLE else "gpt-4o-mini"
    
    # Use different provider for interface if possible
    interface_provider = (LLMProvider.OPENAI if OPENAI_AVAILABLE else 
                         (LLMProvider.GEMINI if GEMINI_AVAILABLE else primary_provider))
    interface_model = "gpt-4o-mini" if OPENAI_AVAILABLE else ("gemini-2.0-flash" if GEMINI_AVAILABLE else primary_model)
    
    return AgentLLMConfig(
        scenario_generator=LLMConfig(
            provider=primary_provider,
            model=primary_model,
            temperature=0.8,
            max_tokens=3000
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
            max_tokens=1000
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
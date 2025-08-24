"""
Example LLM Configuration
Shows how to configure different LLM models for different agents
"""

from config.llm_config import (
    LLMConfig, AgentLLMConfig, LLMProvider, LLMConfigManager,
    create_apple_genai_config, create_mixed_config
)

# Example 1: All agents use Apple GenAI
def create_all_apple_config():
    """Configure all agents to use Apple GenAI"""
    return AgentLLMConfig(
        scenario_generator=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.8,  # Creative for scenario generation
            max_tokens=3000
        ),
        rag_retriever=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.3,  # Focused for retrieval
            max_tokens=1500
        ),
        npc_controller=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.9,  # Most creative for NPC dialogue
            max_tokens=2000
        ),
        main_interface=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.5,  # Balanced for interface parsing
            max_tokens=1000
        ),
        default_fallback=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.7
        )
    )


# Example 2: Mixed providers (if OpenAI is also available)
def create_mixed_provider_config():
    """Configure agents with different providers"""
    return AgentLLMConfig(
        scenario_generator=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.8,
            max_tokens=3000
        ),
        rag_retriever=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.3,
            max_tokens=1500
        ),
        npc_controller=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.9,
            max_tokens=2000
        ),
        main_interface=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.5,
            max_tokens=1000
        ),
        default_fallback=LLMConfig(
            provider=LLMProvider.APPLE_GENAI,
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        )
    )


# Example 3: Environment-based configuration
# Set these environment variables to customize:
# SCENARIO_GENERATOR_PROVIDER=apple_genai
# SCENARIO_GENERATOR_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
# SCENARIO_GENERATOR_TEMPERATURE=0.8
# RAG_RETRIEVER_PROVIDER=apple_genai
# RAG_RETRIEVER_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
# RAG_RETRIEVER_TEMPERATURE=0.3
# NPC_CONTROLLER_PROVIDER=apple_genai
# NPC_CONTROLLER_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
# NPC_CONTROLLER_TEMPERATURE=0.9
# MAIN_INTERFACE_PROVIDER=apple_genai
# MAIN_INTERFACE_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
# MAIN_INTERFACE_TEMPERATURE=0.5

# Example usage patterns:
if __name__ == "__main__":
    print("=== LLM Configuration Examples ===\n")
    
    # Example 1: All Apple GenAI
    print("1. All Apple GenAI Configuration:")
    try:
        apple_config = create_all_apple_config()
        apple_manager = LLMConfigManager(apple_config)
        
        print("Configuration Summary:")
        for agent, config in apple_manager.get_config_summary().items():
            print(f"  {agent}: {config}")
        
        # Test creating generators
        scenario_gen = apple_manager.create_generator("scenario_generator")
        print(f"✅ Created scenario generator: {type(scenario_gen).__name__}")
        
    except Exception as e:
        print(f"❌ Apple GenAI config failed: {e}")
    
    print("\n" + "="*50)
    
    # Example 2: Environment-based config
    print("\n2. Environment-based Configuration:")
    print("Set environment variables to customize:")
    print("  SCENARIO_GENERATOR_PROVIDER=apple_genai")
    print("  SCENARIO_GENERATOR_MODEL=gpt-4o-mini")
    print("  SCENARIO_GENERATOR_TEMPERATURE=0.8")
    print("  (and similar for other agents)")
    
    print("\n" + "="*50)
    
    # Example 3: Quick setup functions
    print("\n3. Quick Setup Functions:")
    print("For simple Apple GenAI setup:")
    print("  from config.llm_config import create_apple_genai_config, LLMConfigManager")
    print("  config = create_apple_genai_config()")
    print("  manager = LLMConfigManager(config)")
    
    print("\nFor mixed provider setup:")
    print("  from config.llm_config import create_mixed_config, LLMConfigManager") 
    print("  config = create_mixed_config()")
    print("  manager = LLMConfigManager(config)")
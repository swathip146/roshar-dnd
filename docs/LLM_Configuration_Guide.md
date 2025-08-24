# LLM Configuration Guide

This guide explains how to configure and use different LLM models for the Haystack D&D Game system.

## Overview

The LLM configuration system allows you to:
- Use different LLM providers (Apple GenAI, OpenAI, etc.) for different agents
- Configure model-specific parameters (temperature, max tokens, etc.)
- Switch between providers without changing agent code
- Set up environment-based configurations

## Quick Start

### 1. Default Configuration (Apple GenAI)

The system defaults to Apple GenAI with Claude Sonnet if available:

```python
from config.llm_config import get_global_config_manager
from agents.scenario_generator_agent import create_scenario_generator_agent

# Uses default Apple GenAI configuration
agent = create_scenario_generator_agent()
```

### 2. Custom Configuration

```python
from config.llm_config import LLMConfig, AgentLLMConfig, LLMConfigManager, LLMProvider

# Create custom configuration
custom_config = AgentLLMConfig(
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
    # ... other agents
)

# Use custom configuration
manager = LLMConfigManager(custom_config)
generator = manager.create_generator("scenario_generator")
```

## Configuration Options

### Supported Providers

| Provider | Description | Required Package |
|----------|-------------|------------------|
| `APPLE_GENAI` | Apple GenAI with Claude Sonnet | `hwtgenielib` |
| `OPENAI` | OpenAI GPT models | `openai` |

### Model Configurations

#### Apple GenAI
```python
LLMConfig(
    provider=LLMProvider.APPLE_GENAI,
    model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
    temperature=0.7,
    max_tokens=2000
)
```

#### OpenAI
```python
LLMConfig(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=2000,
    api_key="your-api-key"  # Optional if set in environment
)
```

### Agent-Specific Recommendations

| Agent | Recommended Temperature | Max Tokens | Purpose |
|-------|-------------------------|------------|---------|
| `scenario_generator` | 0.8 | 3000 | Creative scenario generation |
| `rag_retriever` | 0.3 | 1500 | Focused document retrieval |
| `npc_controller` | 0.9 | 2000 | Creative NPC dialogue |
| `main_interface` | 0.5 | 1000 | Balanced input parsing |

## Environment Configuration

Set environment variables to configure agents:

```bash
# Scenario Generator
export SCENARIO_GENERATOR_PROVIDER=apple_genai
export SCENARIO_GENERATOR_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
export SCENARIO_GENERATOR_TEMPERATURE=0.8
export SCENARIO_GENERATOR_MAX_TOKENS=3000

# RAG Retriever
export RAG_RETRIEVER_PROVIDER=apple_genai
export RAG_RETRIEVER_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
export RAG_RETRIEVER_TEMPERATURE=0.3
export RAG_RETRIEVER_MAX_TOKENS=1500

# NPC Controller
export NPC_CONTROLLER_PROVIDER=apple_genai
export NPC_CONTROLLER_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
export NPC_CONTROLLER_TEMPERATURE=0.9
export NPC_CONTROLLER_MAX_TOKENS=2000

# Main Interface
export MAIN_INTERFACE_PROVIDER=apple_genai
export MAIN_INTERFACE_MODEL=aws:anthropic.claude-sonnet-4-20250514-v1:0
export MAIN_INTERFACE_TEMPERATURE=0.5
export MAIN_INTERFACE_MAX_TOKENS=1000
```

Then load environment configuration:

```python
from config.llm_config import load_config_from_environment, LLMConfigManager

config = load_config_from_environment()
manager = LLMConfigManager(config)
```

## Usage Examples

### Example 1: All Apple GenAI Setup

```python
from config.llm_config import create_apple_genai_config, LLMConfigManager, set_global_config_manager

# Create and set global Apple GenAI configuration
apple_config = create_apple_genai_config()
apple_manager = LLMConfigManager(apple_config)
set_global_config_manager(apple_manager)

# Now all agents will use Apple GenAI
from agents.scenario_generator_agent import create_scenario_generator_agent
agent = create_scenario_generator_agent()
```

### Example 2: Mixed Provider Setup

```python
from config.llm_config import create_mixed_config, LLMConfigManager

# Create mixed configuration (Apple GenAI + OpenAI)
mixed_config = create_mixed_config()
manager = LLMConfigManager(mixed_config)

# Create agents with mixed providers
scenario_agent = create_scenario_generator_agent(
    manager.create_generator("scenario_generator")
)
interface_agent = create_main_interface_agent(
    manager.create_generator("main_interface")
)
```

### Example 3: Custom Per-Agent Configuration

```python
from config.llm_config import LLMConfig, LLMProvider, LLMConfigManager

# Create custom configuration for specific needs
custom_config = AgentLLMConfig(
    scenario_generator=LLMConfig(
        provider=LLMProvider.APPLE_GENAI,
        model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.9,  # Extra creative
        max_tokens=4000   # Longer responses
    ),
    rag_retriever=LLMConfig(
        provider=LLMProvider.APPLE_GENAI,
        model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.1,  # Very focused
        max_tokens=1000   # Concise responses
    ),
    # Use defaults for other agents
    npc_controller=LLMConfig(provider=LLMProvider.APPLE_GENAI, model="aws:anthropic.claude-sonnet-4-20250514-v1:0"),
    main_interface=LLMConfig(provider=LLMProvider.APPLE_GENAI, model="aws:anthropic.claude-sonnet-4-20250514-v1:0"),
    default_fallback=LLMConfig(provider=LLMProvider.APPLE_GENAI, model="aws:anthropic.claude-sonnet-4-20250514-v1:0")
)

manager = LLMConfigManager(custom_config)
```

## Integration with Game System

### Updating Existing Game Code

The new system is backward compatible. Existing code like:

```python
# Old way
from agents.scenario_generator_agent import create_scenario_generator_agent
agent = create_scenario_generator_agent()  # Used OpenAI by default
```

Now automatically uses the configured LLM system:

```python
# New way (same code, different behavior)
from agents.scenario_generator_agent import create_scenario_generator_agent
agent = create_scenario_generator_agent()  # Uses LLM config system
```

### Pipeline Integration

The pipeline system automatically uses the configured generators:

```python
from orchestrator.pipeline_integration import create_full_haystack_orchestrator

# Orchestrator will use configured LLMs for all agents
orchestrator = create_full_haystack_orchestrator()
```

### Game Initialization

Update game initialization to set LLM configuration:

```python
from config.llm_config import create_apple_genai_config, LLMConfigManager, set_global_config_manager
from haystack_dnd_game import HaystackDnDGame

# Set up Apple GenAI configuration
apple_config = create_apple_genai_config()
apple_manager = LLMConfigManager(apple_config)
set_global_config_manager(apple_manager)

# Initialize game (will use Apple GenAI for all agents)
game = HaystackDnDGame()
game.start()
```

## Troubleshooting

### Common Issues

1. **Import Error: hwtgenielib not available**
   ```bash
   pip install hwtgenielib
   ```

2. **Import Error: openai not available**
   ```bash
   pip install openai
   ```

3. **API Connection Errors**
   - Verify API keys are set correctly
   - Check network connectivity
   - Ensure model names are correct

4. **Configuration Not Applied**
   - Make sure to set global config manager: `set_global_config_manager(manager)`
   - Check environment variables are set correctly
   - Verify provider availability

### Debug Configuration

Check current configuration:

```python
from config.llm_config import get_global_config_manager

manager = get_global_config_manager()
print("Current Configuration:")
for agent, config in manager.get_config_summary().items():
    print(f"  {agent}: {config}")
```

### Testing Configuration

Use the provided test script:

```bash
cd /path/to/roshar-dnd
python test_llm_config.py
```

## Advanced Usage

### Custom Provider Implementation

To add support for new providers:

1. Add provider to `LLMProvider` enum
2. Implement `_create_*_generator` method in `LLMConfigManager`
3. Add provider availability check
4. Update configuration examples

### Pipeline Message Conversion

For AppleGenAI compatibility, use utility components:

```python
from config.llm_utils import StringToChatMessages
from haystack import Pipeline

pipeline = Pipeline()
pipeline.add_component("converter", StringToChatMessages())
pipeline.add_component("generator", apple_genai_generator)
pipeline.connect("converter", "generator")
```

## File Reference

- `config/llm_config.py` - Main configuration system
- `config/llm_utils.py` - Utility components for LLM compatibility
- `config/example_llm_config.py` - Configuration examples
- `test_llm_config.py` - Test suite for LLM configuration
- All agent files in `agents/` - Updated to use LLM config system

## Migration from OpenAI-only System

The migration is automatic for most use cases. The system defaults to Apple GenAI if available, with OpenAI as fallback. No code changes are required for basic usage.

For custom configurations, replace direct generator creation with the LLM config system as shown in the examples above.
# RAG-Scenario Separation Implementation Plan

## Overview

This plan outlines the separation of RAG data retrieval from scenario generation in the D&D Assistant system. Currently, the `HaystackPipelineAgent` handles both pure RAG queries and creative scenario generation, creating tight coupling and mixed responsibilities.

## Current Architecture Issues

### 1. Mixed Responsibilities in HaystackPipelineAgent
- **RAG Queries**: Document retrieval, embedding, ranking, and structured responses
- **Scenario Generation**: Creative story continuation, option generation, narrative flow (REMOVED)
- **Specialized Pipelines**: NPC-specific, rules-specific, and scenario-specific pipelines (scenario removed)
- **LLM Integration**: Direct Claude Sonnet 4 integration for creative tasks

### 2. Direct Agent Coupling in ScenarioGeneratorAgent
- **Direct Import**: `from agents.haystack_pipeline_agent import HaystackPipelineAgent` creates tight coupling
- **Direct Parameter**: Constructor takes `haystack_agent: Optional[HaystackPipelineAgent]` parameter
- **Direct Reference Checks**: `self.haystack_agent is not None` and `use_rag and self.haystack_agent`
- **Non-Existent Handlers**: Calls `query_scenario` handler that doesn't exist in HaystackPipelineAgent
- **Synchronous Assumptions**: Agent communication assumes synchronous responses

### 3. Backward Compatibility Issues
- **Legacy ScenarioGenerator Class**: Also has direct HaystackPipelineAgent coupling
- **Mixed Communication Patterns**: Uses both direct agent references and orchestrator messaging
- **Inconsistent Error Handling**: Different error patterns for agent vs direct communication

### 4. Communication Architecture Problems
- **Handler Mismatch**: ScenarioGenerator calls non-existent `query_scenario` in HaystackPipelineAgent
- **Async/Sync Confusion**: Agent framework is async but some code assumes synchronous responses
- **Missing Fallback Logic**: Poor graceful degradation when RAG unavailable via orchestrator

### 5. Status Detection Anti-Patterns
- **Direct Agent Inspection**: Checking `self.haystack_agent is not None` instead of orchestrator queries
- **Hardcoded Dependencies**: Constructor requires specific agent type instead of using orchestrator discovery

## Target Architecture

### 1. Pure RAG Agent (HaystackPipelineAgent)
```
HaystackPipelineAgent
├── Document Retrieval
├── Embedding & Ranking
├── Context Formatting
├── Source Attribution
└── Raw Data Responses
```

### 2. Enhanced Scenario Generator (ScenarioGeneratorAgent)
```
ScenarioGeneratorAgent
├── Creative Story Generation
├── Option Creation & Formatting
├── RAG Data Integration (via queries to HaystackAgent)
├── Fallback Generation (when RAG unavailable)
└── Narrative Continuity Management
```

## Implementation Steps

### Phase 1: HaystackPipelineAgent Simplification

#### 1.1 Remove Scenario-Specific Components
**Files to Modify:** `agents/haystack_pipeline_agent.py`

**Changes:**
- Remove `_handle_query_scenario()` method
- Remove `scenario_pipeline` initialization and setup
- Remove `_create_scenario_prompt_builder()` method
- Remove `_create_creative_scenario_prompt_builder()` method
- Remove `_run_scenario_pipeline()` method
- Remove `_setup_specialized_pipelines()` method entirely
- Keep only general RAG, NPC, and rules pipelines

**New Handler Methods:**
```python
def _setup_handlers(self):
    """Setup message handlers for pure RAG functionality"""
    self.register_handler("query_rag", self._handle_query_rag)
    self.register_handler("retrieve_documents", self._handle_retrieve_documents)
    self.register_handler("query_npc", self._handle_query_npc)
    self.register_handler("query_rules", self._handle_query_rules)
    self.register_handler("get_pipeline_status", self._handle_get_pipeline_status)
    self.register_handler("get_collection_info", self._handle_get_collection_info)
```

**New Method: Raw Document Retrieval**
```python
def _handle_retrieve_documents(self, message: AgentMessage) -> Dict[str, Any]:
    """Handle pure document retrieval without LLM processing"""
    query = message.data.get("query")
    max_docs = message.data.get("max_docs", 5)
    
    if not query:
        return {"success": False, "error": "No query provided"}
    
    try:
        # Run retrieval pipeline without LLM
        result = self._run_pure_retrieval(query, max_docs)
        return {"success": True, "documents": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

#### 1.2 Simplified Pipeline Architecture
**New Pipeline Structure:**
- **General RAG Pipeline**: Query → Embed → Retrieve → Rank → LLM → Response
- **Document Retrieval Pipeline**: Query → Embed → Retrieve → Rank → Format
- **NPC Pipeline**: Query → Embed → Retrieve → Rank → NPC-specific LLM → Response
- **Rules Pipeline**: Query → Embed → Retrieve → Rank → Rules-specific LLM → Response

### Phase 2: ScenarioGeneratorAgent Orchestrator Integration

#### 2.1 Remove Direct HaystackPipelineAgent Coupling
**Files to Modify:** `agents/scenario_generator.py`

**Critical Changes Required:**

**1. Remove Direct Import and Reference:**
```python
# REMOVE this line:
from agents.haystack_pipeline_agent import HaystackPipelineAgent

# UPDATE constructor to remove direct haystack_agent parameter:
def __init__(self, verbose: bool = False):  # Remove haystack_agent parameter entirely
    super().__init__("scenario_generator", "ScenarioGenerator")
    self.verbose = verbose
    self.has_llm = CLAUDE_AVAILABLE
    # Remove: self.haystack_agent = haystack_agent
    
    # Initialize LLM for creative generation
    if self.has_llm:
        try:
            self.chat_generator = AppleGenAIChatGenerator(
                model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
            )
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to initialize LLM: {e}")
            self.chat_generator = None
            self.has_llm = False
    else:
        self.chat_generator = None
```

**2. Replace Direct Status Detection with Orchestrator Queries:**
```python
def _is_haystack_pipeline_available(self) -> bool:
    """Check if haystack pipeline is available via orchestrator communication"""
    try:
        # Send status request to haystack pipeline agent
        status_response = self.send_message("haystack_pipeline", "get_pipeline_status", {})
        
        # Note: In agent architecture, we can't wait for synchronous responses
        # So we assume availability and handle errors gracefully in actual queries
        return True
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Unable to check haystack pipeline status: {e}")
        return False

def _handle_get_generator_status(self, message: AgentMessage) -> Dict[str, Any]:
    """Handle generator status request - updated for orchestrator communication"""
    return {
        "llm_available": self.has_llm,
        "chat_generator_available": self.chat_generator is not None,
        "verbose": self.verbose,
        "agent_type": self.agent_type,
        "uses_orchestrator_communication": True  # New flag
    }
```

**3. Fix RAG Query Communication - Remove Non-Existent Handlers:**
```python
def _handle_generate_with_context(self, message: AgentMessage) -> Dict[str, Any]:
    """Generate scenario with optional RAG context - orchestrator communication"""
    query = message.data.get("query")
    use_rag = message.data.get("use_rag", True)
    campaign_context = message.data.get("campaign_context", "")
    game_state = message.data.get("game_state", "")
    
    if not query:
        return {"success": False, "error": "No query provided"}
    
    try:
        # Retrieve relevant documents via orchestrator
        documents = []
        if use_rag:
            # Use the correct handler name from haystack pipeline agent
            rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": query,
                "max_docs": 3
            })
            
            # Handle orchestrator response properly
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
            elif self.verbose:
                print(f"⚠️ RAG document retrieval failed or unavailable")
        
        # Generate scenario with or without RAG context
        scenario = self._generate_creative_scenario(query, documents, campaign_context, game_state)
        
        return {
            "success": True,
            "scenario": scenario,
            "used_rag": len(documents) > 0,
            "source_count": len(documents)
        }
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Scenario generation error: {e}")
        return {"success": False, "error": str(e)}
```

#### 2.2 Update Legacy Methods for Orchestrator Communication

**Update `generate()` method:**
```python
def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
    """Generate a new scenario based on current game state - orchestrator communication"""
    seed = self._seed_scene(state)
    scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
    options_text = ""
    
    # Try creative scenario generation via orchestrator (remove non-existent query_scenario)
    try:
        prompt = self._build_creative_prompt(seed)
        
        # First try to get RAG context for scenario generation
        documents = []
        rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
            "query": prompt,
            "max_docs": 3
        })
        
        if rag_response and rag_response.get("success"):
            documents = rag_response.get("documents", [])
        
        # Generate creative scenario with RAG context
        if documents or self.has_llm:
            scenario = self._generate_creative_scenario(prompt, documents,
                                                      seed.get('story_arc', ''), str(seed))
            if scenario and scenario.get("scenario_text"):
                scene_text = scenario["scenario_text"]
                if scenario.get("options"):
                    options_text = "\n".join(scenario["options"])
        
        if self.verbose:
            print(f"📤 Generated scenario via orchestrator communication (RAG docs: {len(documents)})")
            
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Orchestrator scenario generation failed: {e}")
    
    # Generate fallback options if needed
    if not options_text:
        options = [
            "1. Investigate the suspicious noise.",
            "2. Approach openly and ask questions.",
            "3. Set up an ambush and wait.",
            "4. Leave and gather more information."
        ]
        random.shuffle(options)
        options_text = "\n".join(options[:4])
    
    # Create scene JSON
    scene_json = {
        "scene_text": scene_text,
        "seed": seed,
        "options": [line.strip() for line in options_text.splitlines() if line.strip()]
    }
    
    return json.dumps(scene_json, indent=2), options_text
```

**Update `apply_player_choice()` method:**
```python
def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
    """Apply a player's choice and return the continuation - orchestrator communication"""
    try:
        current_options = state.get("current_options", "")
        lines = [line for line in current_options.splitlines() if line.strip()]
        target = None
        
        # Try to find the choice by number
        for line in lines:
            if line.strip().startswith(f"{choice_value}."):
                target = line
                break
        
        # Fallback: pick by index
        if not target and lines:
            idx = max(0, min(len(lines) - 1, choice_value - 1))
            target = lines[idx]
        
        if not target:
            target = f"Option {choice_value}"
        
        continuation = f"{player} chose: {target}"
        
        # Try creative consequence generation via orchestrator
        try:
            prompt = self._build_creative_choice_prompt(state, target, player)
            
            # Get RAG context for consequence generation
            rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": prompt,
                "max_docs": 2
            })
            
            documents = []
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
            
            # Generate consequence with RAG context
            if documents or self.has_llm:
                consequence = self._generate_creative_scenario(prompt, documents,
                                                           state.get('story_arc', ''), str(state))
                if consequence and consequence.get("scenario_text"):
                    return consequence["scenario_text"]
            
            if self.verbose:
                print("📤 Generated choice consequence via orchestrator communication")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Orchestrator choice consequence generation failed: {e}")
        
        return continuation
        
    except Exception as e:
        return f"Error applying choice: {e}"
```

#### 2.3 Update Backward Compatibility Class

**Complete Rewrite of `ScenarioGenerator` Class:**
```python
class ScenarioGenerator:
    """Traditional ScenarioGenerator class for backward compatibility - orchestrator communication"""
    
    def __init__(self, haystack_agent=None, verbose: bool = False):
        # Ignore haystack_agent parameter for backward compatibility
        # but don't store it - use orchestrator communication instead
        self.verbose = verbose
        self._agent_communication_available = False
        
        # Try to detect if we're in an agent environment
        try:
            # This will be set when the ScenarioGeneratorAgent is used in orchestrator
            self._scenario_agent = None  # Will be set by orchestrator if available
        except Exception:
            pass
    
    def _query_via_orchestrator(self, action: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt to query via orchestrator if available"""
        if self._scenario_agent and hasattr(self._scenario_agent, 'send_message'):
            try:
                return self._scenario_agent.send_message("haystack_pipeline", action, data)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Orchestrator query failed: {e}")
        return None
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario - orchestrator communication fallback"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        # Try orchestrator communication for RAG context
        try:
            prompt = self._build_prompt(seed)
            rag_response = self._query_via_orchestrator("retrieve_documents", {
                "query": prompt,
                "max_docs": 3
            })
            
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
                if documents and self.verbose:
                    print(f"📚 Enhanced scenario with {len(documents)} RAG documents")
                    # Simple enhancement based on RAG context
                    scene_text += f" (Enhanced with {len(documents)} D&D references from knowledge base.)"
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Backward compatibility RAG query failed: {e}")
        
        # Generate fallback options
        if not options_text:
            options = [
                "1. Investigate the suspicious noise.",
                "2. Approach openly and ask questions.",
                "3. Set up an ambush and wait.",
                "4. Leave and gather more information."
            ]
            random.shuffle(options)
            options_text = "\n".join(options[:4])
        
        scene_json = {
            "scene_text": scene_text,
            "seed": seed,
            "options": [line.strip() for line in options_text.splitlines() if line.strip()]
        }
        return json.dumps(scene_json, indent=2), options_text
    
    def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
        """Apply player choice - orchestrator communication fallback"""
        try:
            current_options = state.get("current_options", "")
            lines = [l for l in current_options.splitlines() if l.strip()]
            target = None
            
            # Try numeric match
            for l in lines:
                if l.strip().startswith(f"{choice_value}."):
                    target = l
                    break
            
            if not target and lines:
                idx = max(0, min(len(lines) - 1, choice_value - 1))
                target = lines[idx]
            
            if not target:
                return f"No such option: {choice_value}"
            
            continuation = f"{player} chose: {target}"
            
            # Try orchestrator communication for consequence enhancement
            try:
                prompt = f"CONTEXT: {state.get('story_arc')}\nCHOICE: {target}\nDescribe the immediate consequence in 2-3 sentences."
                rag_response = self._query_via_orchestrator("retrieve_documents", {
                    "query": prompt,
                    "max_docs": 2
                })
                
                if rag_response and rag_response.get("success"):
                    documents = rag_response.get("documents", [])
                    if documents:
                        continuation += f" (Enhanced with {len(documents)} D&D rule references.)"
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Backward compatibility choice consequence failed: {e}")
            
            return continuation
            
        except Exception as e:
            return f"Error applying choice: {e}"
    
    # Keep existing helper methods unchanged
    def _seed_scene(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract seed information for scene generation"""
        return {
            "location": state["session"].get("location") or "unknown",
            "recent": state["session"].get("events", [])[-4:],
            "party": list(state.get("players", {}).keys())[:8],
            "story_arc": state.get("story_arc", "")
        }
    
    def _build_prompt(self, seed: Dict[str, Any]) -> str:
        """Build prompt for scenario generation"""
        return (
            f"You are the Dungeon Master. Create a vivid short scene (2-3 sentences) and offer 3-4 numbered options.\n"
            f"Location: {seed['location']}\nRecent: {seed['recent']}\nParty: {seed['party']}\nStory arc: {seed['story_arc']}\n"
            "Return a JSON-like object with fields: scene_text, options_text."
        )
```

#### 2.2 Enhanced Handler Methods
**New Message Handlers:**
```python
def _setup_handlers(self):
    """Setup message handlers for scenario generator"""
    self.register_handler("generate_scenario", self._handle_generate_scenario)
    self.register_handler("generate_with_context", self._handle_generate_with_context)
    self.register_handler("apply_player_choice", self._handle_apply_player_choice)
    self.register_handler("get_generator_status", self._handle_get_generator_status)
```

**Enhanced Generation Method:**
```python
def _handle_generate_with_context(self, message: AgentMessage) -> Dict[str, Any]:
    """Generate scenario with optional RAG context"""
    query = message.data.get("query")
    use_rag = message.data.get("use_rag", True)
    campaign_context = message.data.get("campaign_context", "")
    game_state = message.data.get("game_state", "")
    
    if not query:
        return {"success": False, "error": "No query provided"}
    
    try:
        # Optionally retrieve relevant documents
        documents = []
        if use_rag and self.haystack_agent:
            rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": query,
                "max_docs": 3
            })
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
        
        # Generate scenario with or without RAG context
        scenario = self._generate_creative_scenario(query, documents, campaign_context, game_state)
        
        return {
            "success": True,
            "scenario": scenario,
            "used_rag": len(documents) > 0,
            "source_count": len(documents)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

#### 2.3 Creative Generation Logic
**New Core Generation Method:**
```python
def _generate_creative_scenario(self, query: str, documents: List[Dict], 
                               campaign_context: str, game_state: str) -> Dict[str, Any]:
    """Generate creative scenario with optional RAG context"""
    
    # Build context-aware prompt
    prompt = self._build_scenario_prompt(query, documents, campaign_context, game_state)
    
    if self.has_llm and self.chat_generator:
        # Use LLM for creative generation
        try:
            messages = [ChatMessage.from_user(prompt)]
            response = self.chat_generator.run(messages=messages)
            
            if response and "replies" in response:
                scenario_text = response["replies"][0].text
                return self._parse_scenario_response(scenario_text)
        except Exception as e:
            if self.verbose:
                print(f"⚠️ LLM generation failed: {e}")
    
    # Fallback generation
    return self._generate_fallback_scenario(query, documents)

def _build_scenario_prompt(self, query: str, documents: List[Dict], 
                          campaign_context: str, game_state: str) -> str:
    """Build comprehensive scenario generation prompt"""
    prompt = "You are an expert Dungeon Master creating engaging D&D scenarios.\n\n"
    
    # Add RAG context if available
    if documents:
        prompt += "Relevant D&D context:\n"
        for i, doc in enumerate(documents, 1):
            content = doc.get("content", "")[:200]  # Limit length
            source = doc.get("meta", {}).get("source_file", "Unknown")
            prompt += f"{i}. {content}... (Source: {source})\n"
        prompt += "\n"
    
    # Add campaign context
    if campaign_context:
        prompt += f"Campaign Context: {campaign_context}\n"
    
    # Add game state
    if game_state:
        prompt += f"Current Game State: {game_state}\n"
    
    prompt += f"\nPlayer Request: {query}\n\n"
    
    # Add generation instructions
    prompt += """Generate an engaging D&D scenario with the following structure:

1. **Scene Description** (2-3 sentences): Vivid description of the current situation
2. **Player Options** (3-4 numbered choices): Include mix of:
   - Skill checks (format: "**Skill Check (DC X)** - Description")
   - Combat options (format: "**Combat** - Description (Enemy details)")
   - Social interactions
   - Problem-solving approaches

Ensure options are clearly numbered and formatted for easy selection.
Focus on creativity, engagement, and D&D authenticity."""
    
    return prompt
```

### Phase 3: ModularDMAssistant Updates

#### 3.1 Command Routing Changes
**File:** `modular_dm_assistant.py`

**Update Command Map:**
```python
# OLD routing (lines 79-87)
'introduce scenario': ('haystack_pipeline', 'query_scenario'),
'generate scenario': ('haystack_pipeline', 'query_scenario'),
'create scenario': ('haystack_pipeline', 'query_scenario'),
'new scene': ('haystack_pipeline', 'query_scenario'),
'encounter': ('haystack_pipeline', 'query_scenario'),
'adventure': ('haystack_pipeline', 'query_scenario'),

# NEW routing
'introduce scenario': ('scenario_generator', 'generate_with_context'),
'generate scenario': ('scenario_generator', 'generate_with_context'),
'create scenario': ('scenario_generator', 'generate_with_context'),
'new scene': ('scenario_generator', 'generate_with_context'),
'encounter': ('scenario_generator', 'generate_with_context'),
'adventure': ('scenario_generator', 'generate_with_context'),
```

#### 3.2 Update Generation Methods
**Replace `_generate_scenario()` method:**
```python
def _generate_scenario(self, user_query: str) -> str:
    """Generate scenario using enhanced ScenarioGeneratorAgent"""
    try:
        # Get context data
        campaign_context = self._get_campaign_context()
        game_state = self._get_current_game_state()
        
        # Send to scenario generator with RAG option
        response = self._send_message_and_wait("scenario_generator", "generate_with_context", {
            "query": user_query,
            "use_rag": True,
            "campaign_context": campaign_context,
            "game_state": game_state
        }, timeout=25.0)
        
        if response and response.get("success"):
            scenario = response["scenario"]
            rag_used = response.get("used_rag", False)
            source_count = response.get("source_count", 0)
            
            # Extract and store options
            self._extract_and_store_options(scenario.get("scenario_text", ""))
            
            # Format response
            output = f"🎭 SCENARIO:\n{scenario.get('scenario_text', '')}\n\n"
            
            if rag_used:
                output += f"📚 *Enhanced with {source_count} D&D references*\n"
            else:
                output += f"🎨 *Creative generation (RAG not used)*\n"
            
            output += "\n📝 *Type 'select option [number]' to continue the story.*"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
            return f"❌ Failed to generate scenario: {error_msg}"
            
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Scenario generation error: {e}")
        return self._generate_fallback_scenario(user_query)
```

#### 3.3 Update Command Handlers
**Update `_route_command()` method:**
```python
elif agent_id == 'scenario_generator':
    if action == 'generate_with_context':
        return self._generate_scenario(instruction)
    elif action == 'apply_player_choice':
        # Extract option number from instruction
        import re
        match = re.search(r'select option (\d+)', instruction.lower())
        if match:
            option_number = int(match.group(1))
            return self._select_player_option(option_number)
        else:
            return "❌ Please specify option number (e.g., 'select option 2')"
    else:
        return self._handle_general_query(instruction)
```

### Phase 4: Testing & Integration

#### 4.1 Unit Tests
**New Test File:** `tests/test_rag_scenario_separation.py`

```python
def test_haystack_pure_rag():
    """Test that haystack agent only handles RAG queries"""
    # Test document retrieval
    # Test general RAG queries
    # Verify no scenario generation handlers

def test_scenario_generator_with_rag():
    """Test scenario generator with RAG integration"""
    # Test scenario generation with RAG context
    # Test scenario generation without RAG
    # Test error handling when RAG unavailable

def test_scenario_generator_fallback():
    """Test scenario generator fallback when RAG fails"""
    # Test creative generation without RAG
    # Test fallback option generation
```

#### 4.2 Integration Tests
**Test Scenarios:**
1. **Pure RAG Query**: "What are the rules for concentration checks?"
2. **Scenario with RAG**: "Generate a tavern encounter with bandits"
3. **Scenario without RAG**: "Create a mystery in a haunted forest"
4. **RAG Failure Fallback**: Scenario generation when Qdrant unavailable

#### 4.3 Performance Testing
**Metrics to Monitor:**
- RAG query response time (should improve)
- Scenario generation response time (may increase initially)
- Memory usage per agent
- Message bus throughput

## Migration Steps

### Step 1: Backup Current System
```bash
# Create backup of current implementation
cp agents/haystack_pipeline_agent.py agents/haystack_pipeline_agent.py.backup
cp agents/scenario_generator.py agents/scenario_generator.py.backup
cp modular_dm_assistant.py modular_dm_assistant.py.backup
```

### Step 2: Implement Changes in Order
1. **First**: Update `haystack_pipeline_agent.py` (remove scenario logic)
2. **Second**: Enhance `scenario_generator.py` (add creative generation)
3. **Third**: Update `modular_dm_assistant.py` (change routing)
4. **Fourth**: Update any remaining dependencies

### Step 3: Testing Phase
1. **Unit Testing**: Test each agent individually
2. **Integration Testing**: Test agent communication
3. **System Testing**: Test complete workflow
4. **Performance Testing**: Verify no degradation

### Step 4: Deployment
1. **Staged Deployment**: Deploy to test environment first
2. **Monitoring**: Watch for errors and performance issues
3. **Rollback Plan**: Be ready to restore from backup
4. **Documentation**: Update architecture documentation

## Expected Benefits

### 1. Improved Separation of Concerns
- **HaystackPipelineAgent**: Pure RAG functionality, faster queries
- **ScenarioGeneratorAgent**: Creative generation with optional RAG enhancement
- **Clear Responsibilities**: Each agent has a single, well-defined purpose

### 2. Enhanced Flexibility
- **Configurable RAG Usage**: Scenarios can be generated with or without RAG
- **Fallback Generation**: Creative generation continues when RAG unavailable
- **Modular Enhancement**: Easy to add new generation techniques

### 3. Better Performance
- **Faster RAG Queries**: No overhead from scenario-specific pipelines
- **Optimized Caching**: Separate caching strategies for RAG vs. creative content
- **Reduced Memory Usage**: Smaller, focused agents

### 4. Easier Maintenance
- **Single Responsibility**: Each agent easier to understand and modify
- **Independent Testing**: Can test RAG and scenario generation separately
- **Cleaner Code**: Removal of mixed concerns and duplicate logic

## Risk Mitigation

### 1. Communication Failures
**Risk**: Scenario generator can't communicate with RAG agent
**Mitigation**: Robust fallback generation, timeout handling, error recovery

### 2. Performance Degradation
**Risk**: Additional message passing slows down scenario generation
**Mitigation**: Async communication, caching, performance monitoring

### 3. Feature Regression
**Risk**: Loss of functionality during migration
**Mitigation**: Comprehensive testing, gradual rollout, backup/rollback plan

### 4. Integration Issues
**Risk**: Dependencies break due to interface changes
**Mitigation**: Interface compatibility checks, staged deployment

## Timeline

### Week 1: Preparation
- [ ] Code analysis and detailed design
- [ ] Test plan creation
- [ ] Backup current system

### Week 2: Core Implementation
- [ ] Update HaystackPipelineAgent
- [ ] Enhance ScenarioGeneratorAgent
- [ ] Basic unit testing

### Week 3: Integration
- [ ] Update ModularDMAssistant
- [ ] Integration testing
- [ ] Performance testing

### Week 4: Deployment
- [ ] System testing
- [ ] Documentation updates
- [ ] Production deployment

## Success Criteria

1. **Functional**: All existing scenario generation features work as before
2. **Performance**: RAG queries are ≥20% faster, scenario generation ≤10% slower
3. **Reliability**: No increase in error rates or timeout failures
4. **Maintainability**: Code complexity reduced, test coverage improved
5. **Extensibility**: Easy to add new scenario generation techniques

---

This implementation plan provides a comprehensive roadmap for separating RAG functionality from scenario generation while maintaining system reliability and performance.
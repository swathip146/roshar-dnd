"""
Agent Framework for DM Assistant
Provides communication and coordination between different AI agents
Enhanced with Haystack Pipeline Integration
"""
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import threading
import queue
import time
import uuid
from abc import ABC, abstractmethod

# Import messaging components from shared module
from core.messaging import AgentMessage, MessageType

# Import Haystack bridge components
try:
    from core.command_envelope import CommandEnvelope, CommandHeader, CommandBody, create_command_envelope
    from core.haystack_bridge import HaystackOrchestrator
    HAYSTACK_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Haystack integration not available: {e}")
    HAYSTACK_AVAILABLE = False


class BaseAgent(ABC):
    """Base class for all agents in the framework"""
    
    def __init__(self, agent_id: str, agent_type: str, verbose: bool = False):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.verbose = verbose
        self.message_bus: Optional['MessageBus'] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self._setup_handlers()
        # Register universal handlers after agent-specific ones
        self._register_universal_handlers()
    
    @abstractmethod
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        pass
    
    def register_handler(self, action: str, handler: Callable):
        """Register a message handler for a specific action"""
        self.message_handlers[action] = handler
    
    def _validate_message_data(self, message: AgentMessage) -> bool:
        """Validate message data format - Fix #1 from Phase 1"""
        if not isinstance(message.data, dict):
            if self.verbose:
                print(f"❌ {self.agent_id}: Invalid message data type: {type(message.data)}")
            return False
        return True
    
    def _handle_broadcast_event(self, message: AgentMessage) -> Dict[str, Any]:
        """Default handler for broadcast events that don't need agent-specific handling - Fix #3 from Phase 1"""
        if not self._validate_message_data(message):
            return {"success": False, "error": "Invalid message data format"}
        
        event_type = message.data.get("event_type", message.action)
        if self.verbose:
            print(f"📢 {self.agent_id} received broadcast: {event_type}")
        return {"success": True, "message": f"Event {event_type} acknowledged"}
    
    def send_message(self, receiver_id: str, action: str, data: Dict[str, Any], 
                    message_type: MessageType = MessageType.REQUEST) -> str:
        """Send a message to another agent"""
        if not self.message_bus:
            raise RuntimeError("Agent not connected to message bus")
        
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=message_type,
            action=action,
            data=data,
            timestamp=time.time()
        )
        
        self.message_bus.send_message(message)
        return message.id
    
    def send_response(self, original_message: AgentMessage, data: Dict[str, Any]):
        """Send a response to a previous message"""
        response = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=original_message.sender_id,
            message_type=MessageType.RESPONSE,
            action=original_message.action,
            data=data,
            timestamp=time.time(),
            response_to=original_message.id
        )
        
        print(f"Response prepared in send_response (AgentMessage) is ID:{response.id} Action:{response.action} From:{response.sender_id} To:{response.response_to}")
        
        self.message_bus.send_message(response)
    
    def broadcast_event(self, action: str, data: Dict[str, Any]):
        """Broadcast an event to all agents"""
        if not self.message_bus:
            return
        
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id="broadcast",
            message_type=MessageType.EVENT,
            action=action,
            data=data,
            timestamp=time.time()
        )
        
        self.message_bus.send_message(message)
    
    def handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        try:
            handler = self.message_handlers.get(message.action)
            if handler:
                # Store the message ID to track if a response was sent for this specific message
                message_id = message.id
                original_history_length = len(self.message_bus.message_history) if self.message_bus else 0
                
                if self.verbose and message.message_type == MessageType.REQUEST:
                    print(f"🔍 {self.agent_id}: Calling handler for {message.action} (msg_id: {message_id})")
                
                # Call handler and check for response data
                result = handler(message)
                
                if self.verbose and message.message_type == MessageType.REQUEST:
                    print(f"🔍 {self.agent_id}: Handler returned: {type(result)} for {message.action}")
                
                # Give the message bus a moment to process any send_response calls
                import time
                time.sleep(0.05)  # 50ms delay to allow message bus processing
                
                # Check if handler already sent a response by looking for response message
                response_already_sent = False
                if self.message_bus:
                    current_history_length = len(self.message_bus.message_history)
                    if self.verbose and message.message_type == MessageType.REQUEST:
                        print(f"🔍 {self.agent_id}: History length before: {original_history_length}, after: {current_history_length}")
                    
                    # Look for response messages sent after handler execution
                    new_messages = self.message_bus.message_history[original_history_length:]
                    if self.verbose and message.message_type == MessageType.REQUEST and new_messages:
                        print(f"🔍 {self.agent_id}: Found {len(new_messages)} new messages")
                    
                    for i, msg in enumerate(new_messages):
                        if self.verbose and message.message_type == MessageType.REQUEST:
                            print(f"🔍 {self.agent_id}: New msg {i}: type={msg.message_type.value}, response_to={msg.response_to}, sender={msg.sender_id}")
                        
                        # msg is an AgentMessage object, not a dict
                        if (msg.message_type == MessageType.RESPONSE and
                            msg.response_to == message_id and
                            msg.sender_id == self.agent_id):
                            response_already_sent = True
                            if self.verbose:
                                print(f"🔍 {self.agent_id}: Found response message in history for {message.action}")
                            break
                
                # If handler returned data and this is a REQUEST message AND no response sent yet
                if (result is not None and
                    isinstance(result, dict) and
                    message.message_type == MessageType.REQUEST and
                    not response_already_sent):
                    if self.verbose:
                        print(f"🔍 {self.agent_id}: Framework sending result response for {message.action}")
                    self.send_response(message, result)
                    
                # For debugging: log what happened
                if self.verbose and message.message_type == MessageType.REQUEST:
                    if response_already_sent:
                        print(f"✅ {self.agent_id}: Handler sent response directly for {message.action}")
                    elif result is not None:
                        print(f"✅ {self.agent_id}: Framework sent handler result for {message.action}")
                    else:
                        print(f"⚠️ {self.agent_id}: No response sent for {message.action}")
                        
            else:
                if self.verbose:
                    print(f"⚠️ Agent {self.agent_id} has no handler for action: {message.action}")
                
                # Send error response for requests to unknown actions
                if message.message_type == MessageType.REQUEST:
                    self.send_response(message, {
                        "success": False,
                        "error": f"No handler for action: {message.action}"
                    })
        except Exception as e:
            if self.verbose:
                print(f"❌ Error handling message in agent {self.agent_id}: {e}")
            
            # Send error response for requests that failed
            if message.message_type == MessageType.REQUEST:
                self.send_response(message, {
                    "success": False,
                    "error": f"Handler error: {str(e)}"
                })

    def _register_universal_handlers(self):
        """Register universal handlers that all agents should have"""
        # Register game_state_updated handler if not already registered
        if "game_state_updated" not in self.message_handlers:
            self.register_handler("game_state_updated", self._handle_game_state_updated)
        
        # Register campaign_selected handler if not already registered
        if "campaign_selected" not in self.message_handlers:
            self.register_handler("campaign_selected", self._handle_broadcast_event)
    
    def _handle_game_state_updated(self, message: AgentMessage):
        """Default handler for game_state_updated events"""
        if self.verbose:
            print(f"📢 {self.agent_id} received game_state_updated event")
        # No response needed for events
    
    def start(self):
        """Start the agent"""
        self.running = True
    
    def stop(self):
        """Stop the agent"""
        self.running = False
    
    def process_tick(self):
        """Process one tick of the agent's logic"""
        pass


class MessageBus:
    """Message bus for inter-agent communication"""
    
    def __init__(self, max_history: int = 1000):
        self.message_queue = queue.Queue()
        self.message_history: List[AgentMessage] = []
        self.max_history = max_history
        self.agents: Dict[str, BaseAgent] = {}
        self.lock = threading.RLock()
        self.running = False
        self.processor_thread: Optional[threading.Thread] = None
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the message bus"""
        with self.lock:
            self.agents[agent.agent_id] = agent
            agent.message_bus = self
    
    def send_message(self, message: AgentMessage):
        """Send a message through the bus"""
        self.message_queue.put(message)
    
    def start(self):
        """Start the message bus processor"""
        if self.running:
            return
        
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_messages, daemon=True)
        self.processor_thread.start()
    
    def stop(self):
        """Stop the message bus processor"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=1.0)
    
    def _process_messages(self):
        """Process messages in the queue"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=0.1)
                self._deliver_message(message)
                self._store_message(message)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
    
    def _deliver_message(self, message: AgentMessage):
        """Deliver a message to its target agent(s)"""
        with self.lock:
            if message.receiver_id == "broadcast":
                # Broadcast to all agents except sender
                for agent_id, agent in self.agents.items():
                    if agent_id != message.sender_id:
                        agent.handle_message(message)
            else:
                # Send to specific agent
                target_agent = self.agents.get(message.receiver_id)
                if target_agent:
                    target_agent.handle_message(message)
    
    def _store_message(self, message: AgentMessage):
        """Store message in history"""
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
    
    def get_message_history(self, agent_id: Optional[str] = None, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get message history, optionally filtered by agent"""
        messages = self.message_history[-limit:]
        if agent_id:
            messages = [m for m in messages 
                       if m.sender_id == agent_id or m.receiver_id == agent_id]
        return [m.to_dict() for m in messages]


class AgentOrchestrator:
    """Orchestrator for managing multiple agents and their interactions"""
    
    def __init__(self, enable_haystack: bool = True, verbose: bool = False):
        self.message_bus = MessageBus()
        self.agents: Dict[str, BaseAgent] = {}
        self.tick_interval = 0.1  # seconds
        self.running = False
        self.orchestrator_thread: Optional[threading.Thread] = None
        self.verbose = verbose
        
        # Event handling for external components (like command handlers)
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._processed_event_ids: set = set()
        
        # Haystack Integration
        self.haystack_orchestrator: Optional[HaystackOrchestrator] = None
        self.enable_haystack = enable_haystack and HAYSTACK_AVAILABLE
        
        if self.enable_haystack:
            try:
                self.haystack_orchestrator = HaystackOrchestrator(self, verbose=verbose)
                if verbose:
                    print("🚀 Haystack integration enabled")
            except Exception as e:
                if verbose:
                    print(f"⚠️ Failed to initialize Haystack integration: {e}")
                self.enable_haystack = False
        
        # Agent references for easy access
        self.haystack_agent = None
        self.campaign_agent = None
        self.game_engine_agent = None
        self.enhanced_game_engine_agent = None  # New enhanced game engine
        self.npc_agent = None
        self.scenario_agent = None
        self.dice_agent = None
        self.combat_agent = None
        self.rule_agent = None
        self.character_agent = None
        self.session_agent = None
        self.inventory_agent = None
        self.spell_agent = None
        self.experience_agent = None
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator"""
        self.agents[agent.agent_id] = agent
        self.message_bus.register_agent(agent)
    
    def initialize_dnd_agents(self, collection_name: str = "dnd_documents",
                             campaigns_dir: str = "resources/current_campaign",
                             players_dir: str = "docs/players",
                             verbose: bool = False,
                             enable_game_engine: bool = True,
                             tick_seconds: float = 0.8,
                             command_handler = None):
        """Initialize all D&D-specific agents and register standard event handlers"""
        try:
            # Import agents here to avoid circular imports
            from agents.haystack_pipeline_agent import HaystackPipelineAgent
            from agents.campaign_management import CampaignManagerAgent
            from agents.game_engine import GameEngineAgent, JSONPersister
            from core.enhanced_game_engine import EnhancedGameEngineAgent  # Import enhanced game engine
            from agents.npc_controller import NPCControllerAgent
            from agents.scenario_generator import ScenarioGeneratorAgent
            from agents.dice_system import DiceSystemAgent, DiceRoller
            from agents.combat_engine import CombatEngineAgent, CombatEngine
            from agents.rule_enforcement_agent import RuleEnforcementAgent
            from agents.character_manager_agent import CharacterManagerAgent
            from agents.session_manager_agent import SessionManagerAgent
            from agents.inventory_manager_agent import InventoryManagerAgent
            from agents.spell_manager_agent import SpellManagerAgent
            from agents.experience_manager_agent import ExperienceManagerAgent
            
            # 1. Initialize Haystack Pipeline Agent (core RAG services)
            self.haystack_agent = HaystackPipelineAgent(
                collection_name=collection_name,
                verbose=verbose
            )
            self.register_agent(self.haystack_agent)
            
            # 2. Initialize Campaign Manager Agent
            self.campaign_agent = CampaignManagerAgent(
                campaigns_dir=campaigns_dir,
                players_dir=players_dir
            )
            self.register_agent(self.campaign_agent)
            
            # 3. Initialize Game Engine Agent (if enabled)
            if enable_game_engine:
                persister = JSONPersister("./game_state_checkpoint.json")
                self.game_engine_agent = GameEngineAgent(
                    persister=persister,
                    tick_seconds=tick_seconds
                )
                self.register_agent(self.game_engine_agent)
                
                # 3.1. Initialize Enhanced Game Engine Agent (for event sourcing)
                self.enhanced_game_engine_agent = EnhancedGameEngineAgent(
                    verbose=verbose
                )
                self.register_agent(self.enhanced_game_engine_agent)
            
            # 4. Initialize Dice System Agent
            self.dice_agent = DiceSystemAgent()
            self.register_agent(self.dice_agent)
            
            # 5. Initialize Combat Engine Agent
            dice_roller = DiceRoller()
            self.combat_agent = CombatEngineAgent(dice_roller)
            self.register_agent(self.combat_agent)
            
            # 6. Initialize Rule Enforcement Agent
            self.rule_agent = RuleEnforcementAgent(
                rag_agent=self.haystack_agent,
                strict_mode=False
            )
            self.register_agent(self.rule_agent)
            
            # 7. Initialize NPC Controller Agent
            self.npc_agent = NPCControllerAgent(
                verbose=verbose
            )
            self.register_agent(self.npc_agent)
            
            # 8. Initialize Scenario Generator Agent
            self.scenario_agent = ScenarioGeneratorAgent(
                verbose=verbose
            )
            self.register_agent(self.scenario_agent)
            
            # 9. Initialize Character Manager Agent
            self.character_agent = CharacterManagerAgent(
                characters_dir="docs/characters",
                verbose=verbose
            )
            self.register_agent(self.character_agent)
            
            # 10. Initialize Session Manager Agent
            self.session_agent = SessionManagerAgent(
                sessions_dir="docs/sessions",
                verbose=verbose
            )
            self.register_agent(self.session_agent)
            
            # 11. Initialize Inventory Manager Agent
            self.inventory_agent = InventoryManagerAgent(
                inventory_dir="docs/inventory",
                verbose=verbose
            )
            self.register_agent(self.inventory_agent)
            
            # 12. Initialize Spell Manager Agent
            self.spell_agent = SpellManagerAgent(
                spells_dir="docs/spells",
                verbose=verbose
            )
            self.register_agent(self.spell_agent)
            
            # 13. Initialize Experience Manager Agent
            self.experience_agent = ExperienceManagerAgent(
                xp_dir="docs/experience",
                verbose=verbose
            )
            self.register_agent(self.experience_agent)
            
            # Register standard event handlers
            self._register_standard_event_handlers(command_handler, verbose)
            
            if verbose:
                print("✅ All D&D agents initialized successfully")
                
            return True
                
        except Exception as e:
            if verbose:
                print(f"❌ Failed to initialize D&D agents: {e}")
            raise
    
    def get_agent_reference(self, agent_type: str):
        """Get a reference to a specific agent by type"""
        agent_map = {
            'haystack': self.haystack_agent,
            'campaign': self.campaign_agent,
            'game_engine': self.game_engine_agent,
            'enhanced_game_engine': self.enhanced_game_engine_agent,
            'npc': self.npc_agent,
            'scenario': self.scenario_agent,
            'dice': self.dice_agent,
            'combat': self.combat_agent,
            'rule': self.rule_agent,
            'character': self.character_agent,
            'session': self.session_agent,
            'inventory': self.inventory_agent,
            'spell': self.spell_agent,
            'experience': self.experience_agent
        }
        return agent_map.get(agent_type)
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register an external event handler for specific event types"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def unregister_event_handler(self, event_type: str, handler: Callable):
        """Unregister an external event handler"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                if not self.event_handlers[event_type]:
                    del self.event_handlers[event_type]
            except ValueError:
                pass  # Handler not found, ignore
    
    def check_and_forward_events(self, event_types: List[str] = None, verbose: bool = False):
        """
        Check for new events and forward them to registered handlers.
        
        Args:
            event_types: List of event types to check for. If None, checks for all registered types.
            verbose: Whether to print verbose output
        """
        if not self.event_handlers:
            return
        
        try:
            # Get recent message history
            history = self.message_bus.get_message_history(limit=50)
            
            # Determine which event types to check for
            target_event_types = event_types or list(self.event_handlers.keys())
            
            # Look for events we haven't processed yet
            for msg in reversed(history):  # Most recent first
                if (msg.get("message_type") == "EVENT" and 
                    msg.get("action") in target_event_types and
                    msg.get("id") not in self._processed_event_ids):
                    
                    # Mark as processed
                    self._processed_event_ids.add(msg.get("id"))
                    
                    # Forward to registered handlers for this event type
                    event_type = msg.get("action")
                    event_data = msg.get("data", {})
                    
                    for handler in self.event_handlers.get(event_type, []):
                        try:
                            handler(event_data)
                            if verbose:
                                print(f"🔄 Forwarded {event_type} event to handler")
                        except Exception as e:
                            if verbose:
                                print(f"⚠️ Error in event handler for {event_type}: {e}")
            
            # Clean up old processed event IDs to prevent memory bloat
            if len(self._processed_event_ids) > 100:
                self._processed_event_ids = set(list(self._processed_event_ids)[-50:])
                
        except Exception as e:
            if verbose:
                print(f"⚠️ Error checking for events: {e}")
    
    def _register_standard_event_handlers(self, command_handler=None, verbose: bool = False):
        """
        Register standard event handlers that are commonly needed by the framework.
        
        Args:
            command_handler: Command handler instance that may have event handling methods
            verbose: Whether to print verbose output about registration
        """
        if command_handler is None:
            return
        
        # Register game_state_updated event handler
        if hasattr(command_handler, 'handle_game_state_updated'):
            self.register_event_handler('game_state_updated', command_handler.handle_game_state_updated)
            if verbose:
                print("🔧 Registered game_state_updated event handler")
        
        # Register other standard event handlers if they exist
        standard_events = {
            'combat_state_changed': 'handle_combat_state_changed',
            'character_updated': 'handle_character_updated',
            'campaign_loaded': 'handle_campaign_loaded',
            'session_started': 'handle_session_started',
            'session_ended': 'handle_session_ended'
        }
        
        for event_type, handler_method in standard_events.items():
            if hasattr(command_handler, handler_method):
                self.register_event_handler(event_type, getattr(command_handler, handler_method))
                if verbose:
                    print(f"🔧 Registered {event_type} event handler")
    
    def start(self):
        """Start the orchestrator and all agents"""
        if self.running:
            return
        
        self.running = True
        self.message_bus.start()
        
        # Start all agents
        for agent in self.agents.values():
            agent.start()
        
        # Start orchestrator loop
        self.orchestrator_thread = threading.Thread(target=self._orchestrator_loop, daemon=True)
        self.orchestrator_thread.start()
    
    def stop(self):
        """Stop the orchestrator and all agents"""
        self.running = False
        
        # Stop all agents
        for agent in self.agents.values():
            agent.stop()
        
        # Stop message bus
        self.message_bus.stop()
        
        # Wait for orchestrator thread
        if self.orchestrator_thread:
            self.orchestrator_thread.join(timeout=1.0)
    
    def _orchestrator_loop(self):
        """Main orchestrator loop"""
        while self.running:
            # Give each agent a chance to process
            for agent in self.agents.values():
                if agent.running:
                    try:
                        agent.process_tick()
                    except Exception as e:
                        print(f"Error in agent {agent.agent_id}: {e}")
            
            time.sleep(self.tick_interval)
    
    def send_message_to_agent(self, receiver_id: str, action: str, data: Dict[str, Any]) -> str:
        """Send a message to a specific agent from the orchestrator"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="orchestrator",
            receiver_id=receiver_id,
            message_type=MessageType.REQUEST,
            action=action,
            data=data,
            timestamp=time.time()
        )
        
        self.message_bus.send_message(message)
        return message.id
    
    def broadcast_event(self, action: str, data: Dict[str, Any]):
        """Broadcast an event to all agents"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="orchestrator",
            receiver_id="broadcast",
            message_type=MessageType.BROADCAST,
            action=action,
            data=data,
            timestamp=time.time()
        )
        
        self.message_bus.send_message(message)
    
    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered agents"""
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "agent_type": agent.agent_type,
                "running": agent.running,
                "handlers": list(agent.message_handlers.keys())
            }
        return status
    
    def get_message_statistics(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        stats = {
            "total_messages": len(self.message_bus.message_history),
            "queue_size": self.message_bus.message_queue.qsize(),
            "registered_agents": len(self.agents)
        }
        
        # Add Haystack integration statistics
        if self.enable_haystack and self.haystack_orchestrator:
            haystack_info = self.haystack_orchestrator.get_pipeline_info()
            stats.update({
                "haystack_enabled": True,
                "haystack_pipelines": haystack_info["registered_pipelines"],
                "haystack_active_commands": haystack_info["active_commands"]
            })
        else:
            stats["haystack_enabled"] = False
            
        return stats
    
    def handle_command_envelope(self, envelope: CommandEnvelope) -> Dict[str, Any]:
        """
        Handle a command using the enhanced CommandEnvelope system
        
        This method serves as the main entry point for the new Haystack-integrated
        command processing system while maintaining backward compatibility.
        
        Args:
            envelope: CommandEnvelope containing the command to process
            
        Returns:
            Dict containing the command execution result
        """
        if not self.enable_haystack or not self.haystack_orchestrator:
            # Fallback to legacy message bus system
            if self.verbose:
                print("⤴️ Haystack not available, using legacy system")
            return self._handle_envelope_legacy(envelope)
        
        try:
            return self.haystack_orchestrator.handle_command(envelope)
        except Exception as e:
            if self.verbose:
                print(f"❌ Haystack command handling failed: {e}")
            # Fallback to legacy system
            return self._handle_envelope_legacy(envelope)
    
    def _handle_envelope_legacy(self, envelope: CommandEnvelope) -> Dict[str, Any]:
        """
        Handle CommandEnvelope using the legacy message bus system
        
        Args:
            envelope: CommandEnvelope to process
            
        Returns:
            Dict containing the result
        """
        try:
            # Convert CommandEnvelope to AgentMessage
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="orchestrator",
                receiver_id=self._intent_to_agent(envelope.header.intent),
                message_type=MessageType.REQUEST,
                action=envelope.header.intent.lower().replace("_", "."),
                data={
                    "utterance": envelope.body.utterance,
                    "entities": envelope.body.entities,
                    "context": envelope.body.context,
                    "correlation_id": envelope.header.correlation_id,
                    "actor": envelope.header.actor
                },
                timestamp=time.time()
            )
            
            # Send through message bus
            self.message_bus.send_message(message)
            
            # Wait for response (simplified implementation)
            response = self._wait_for_response(message.id, envelope.header.timeout_seconds)
            
            if response:
                envelope.mark_completed(response)
                return response
            else:
                error_msg = "No response from legacy system"
                envelope.mark_failed(error_msg)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = f"Legacy envelope handling failed: {str(e)}"
            envelope.mark_failed(error_msg)
            return {"success": False, "error": error_msg}
    
    def _intent_to_agent(self, intent: str) -> str:
        """
        Map command intent to agent ID for legacy system
        
        Args:
            intent: The command intent
            
        Returns:
            Agent ID string
        """
        intent_mapping = {
            "SKILL_CHECK": "rule_enforcement",
            "SCENARIO_CHOICE": "scenario_generator",
            "RULE_QUERY": "rule_enforcement",
            "COMBAT_ACTION": "combat_engine",
            "LORE_LOOKUP": "haystack_pipeline"
        }
        return intent_mapping.get(intent, "haystack_pipeline")
    
    def _wait_for_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        """
        Wait for response from message bus
        
        Args:
            message_id: ID of message to wait for response to
            timeout: Maximum wait time in seconds
            
        Returns:
            Response data or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                history = self.message_bus.get_message_history(limit=50)
                
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                        
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Error waiting for response: {e}")
            
            time.sleep(0.1)
        
        return None
    
    def create_command_envelope(
        self,
        intent: str,
        utterance: str,
        actor: Dict[str, Any],
        entities: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        timeout_seconds: float = 30.0
    ) -> CommandEnvelope:
        """
        Factory method to create CommandEnvelope instances
        
        This provides a convenient way for external systems to create
        properly formatted CommandEnvelopes for processing.
        """
        if not HAYSTACK_AVAILABLE:
            raise RuntimeError("Haystack integration not available - cannot create CommandEnvelope")
            
        return create_command_envelope(
            intent=intent,
            utterance=utterance,
            actor=actor,
            entities=entities,
            context=context,
            parameters=parameters,
            metadata=metadata,
            priority=priority,
            timeout_seconds=timeout_seconds
        )
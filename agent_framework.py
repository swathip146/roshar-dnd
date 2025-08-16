"""
Agent Framework for DM Assistant
Provides communication and coordination between different AI agents
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


class MessageType(Enum):
    """Types of messages that can be sent between agents"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    BROADCAST = "broadcast"
    ERROR = "error"


@dataclass
class AgentMessage:
    """Message passed between agents"""
    id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    action: str
    data: Dict[str, Any]
    timestamp: float
    response_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
            "response_to": self.response_to
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create message from dictionary"""
        return cls(
            id=data["id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=MessageType(data["message_type"]),
            action=data["action"],
            data=data["data"],
            timestamp=data["timestamp"],
            response_to=data.get("response_to")
        )


class BaseAgent(ABC):
    """Base class for all agents in the framework"""
    
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.message_bus: Optional['MessageBus'] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self._setup_handlers()
    
    @abstractmethod
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        pass
    
    def register_handler(self, action: str, handler: Callable):
        """Register a message handler for a specific action"""
        self.message_handlers[action] = handler
    
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
                handler(message)
            else:
                print(f"Agent {self.agent_id} has no handler for action: {message.action}")
        except Exception as e:
            print(f"Error handling message in agent {self.agent_id}: {e}")
    
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
    
    def __init__(self):
        self.message_bus = MessageBus()
        self.agents: Dict[str, BaseAgent] = {}
        self.tick_interval = 0.1  # seconds
        self.running = False
        self.orchestrator_thread: Optional[threading.Thread] = None
        
        # Event handling for external components (like command handlers)
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._processed_event_ids: set = set()
        
        # Agent references for easy access
        self.haystack_agent = None
        self.campaign_agent = None
        self.game_engine_agent = None
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
                haystack_agent=self.haystack_agent,
                mode="hybrid"
            )
            self.register_agent(self.npc_agent)
            
            # 8. Initialize Scenario Generator Agent
            self.scenario_agent = ScenarioGeneratorAgent(
                haystack_agent=self.haystack_agent,
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
        return {
            "total_messages": len(self.message_bus.message_history),
            "queue_size": self.message_bus.message_queue.qsize(),
            "registered_agents": len(self.agents)
        }
"""
Comprehensive Test Suite for Modular DM Assistant
Tests all agents, pipelines, and flows with a complete DnD campaign simulation
"""
import asyncio
import time
import json
import uuid
from typing import Dict, List, Any, Optional
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import networkx as nx
from datetime import datetime
import traceback

# Import all the modular components
from modular_dm_assistant import ModularDMAssistant
from agent_framework import AgentOrchestrator, MessageType
from pipeline_manager import PipelineManager, IntelligentCache
from enhanced_pipeline_components import (
    SmartPipelineRouter, ErrorRecoveryPipeline, CreativeConsequencePipeline
)

class ModularDMTester:
    """Comprehensive tester for the Modular DM Assistant system"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.test_results = {}
        self.performance_metrics = {}
        self.story_progression = []
        self.error_log = []
        self.test_start_time = datetime.now()
        
        # Test configuration
        self.test_collection = "dnd_documents"
        self.test_campaigns_dir = "docs/current_campaign"
        self.test_players_dir = "docs/players"
        
        # DM Assistant instance
        self.dm_assistant = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self.verbose:
            print(f"[{timestamp}] {level}: {message}")
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        
        if level == "ERROR":
            self.error_log.append(log_entry)

    def initialize_dm_assistant(self) -> bool:
        """Initialize the DM Assistant for testing"""
        try:
            self.log("Initializing Modular DM Assistant...")
            self.dm_assistant = ModularDMAssistant(
                collection_name=self.test_collection,
                campaigns_dir=self.test_campaigns_dir,
                players_dir=self.test_players_dir,
                verbose=self.verbose,
                enable_game_engine=True,
                enable_caching=True,
                enable_async=False  # Disable async for easier testing
            )
            
            self.log("Starting DM Assistant orchestrator...")
            self.dm_assistant.start()
            
            # Give it a moment to initialize
            time.sleep(2)
            
            self.log("✅ DM Assistant initialized successfully")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to initialize DM Assistant: {e}", "ERROR")
            return False

    def test_agent_framework(self) -> Dict[str, Any]:
        """Test the agent framework functionality"""
        self.log("\n🧪 Testing Agent Framework...")
        results = {
            "agent_registration": False,
            "message_passing": False,
            "orchestrator_status": False,
            "agent_count": 0,
            "agents": []
        }
        
        try:
            # Test agent status
            status = self.dm_assistant.orchestrator.get_agent_status()
            results["agent_count"] = len(status)
            results["agents"] = list(status.keys())
            results["orchestrator_status"] = len(status) > 0
            
            # Test message bus statistics
            stats = self.dm_assistant.orchestrator.get_message_statistics()
            results["message_bus_active"] = stats["registered_agents"] > 0
            results["registered_agents"] = stats["registered_agents"]
            
            if results["orchestrator_status"]:
                self.log(f"✅ Agent Framework: {results['agent_count']} agents registered")
                for agent_id in results["agents"]:
                    self.log(f"   • {agent_id}")
                results["agent_registration"] = True
            else:
                self.log("❌ Agent Framework: No agents registered", "ERROR")
                
        except Exception as e:
            self.log(f"❌ Agent Framework test failed: {e}", "ERROR")
            
        return results

    def test_campaign_management(self) -> Dict[str, Any]:
        """Test campaign management functionality"""
        self.log("\n🧪 Testing Campaign Management...")
        results = {
            "campaign_list": False,
            "campaign_selection": False,
            "campaign_info": False,
            "player_list": False,
            "player_info": False,
            "campaigns_found": 0,
            "players_found": 0
        }
        
        try:
            # Test campaign listing
            response = self.dm_assistant.process_dm_input("list campaigns")
            if "AVAILABLE CAMPAIGNS" in response:
                results["campaign_list"] = True
                # Count campaigns by counting numbered lines
                campaigns = [line for line in response.split('\n') if line.strip() and any(c.isdigit() for c in line)]
                results["campaigns_found"] = len(campaigns)
                self.log(f"✅ Campaign List: {results['campaigns_found']} campaigns found")
            else:
                self.log("❌ Campaign List: Failed to list campaigns", "ERROR")
            
            # Test campaign selection (if campaigns exist)
            if results["campaigns_found"] > 0:
                response = self.dm_assistant.process_dm_input("1")  # Select first campaign
                if "Selected campaign" in response:
                    results["campaign_selection"] = True
                    self.log("✅ Campaign Selection: Successfully selected campaign")
                    
                    # Test campaign info
                    response = self.dm_assistant.process_dm_input("campaign info")
                    if "CAMPAIGN:" in response:
                        results["campaign_info"] = True
                        self.log("✅ Campaign Info: Retrieved campaign details")
                    else:
                        self.log("❌ Campaign Info: Failed to retrieve details", "ERROR")
                else:
                    self.log("❌ Campaign Selection: Failed to select campaign", "ERROR")
            
            # Test player listing
            response = self.dm_assistant.process_dm_input("list players")
            if "PLAYERS" in response:
                results["player_list"] = True
                # Count players by counting numbered lines
                players = [line for line in response.split('\n') if line.strip() and any(c.isdigit() for c in line)]
                results["players_found"] = len(players)
                self.log(f"✅ Player List: {results['players_found']} players found")
            else:
                self.log("❌ Player List: Failed to list players", "ERROR")
                
        except Exception as e:
            self.log(f"❌ Campaign Management test failed: {e}", "ERROR")
            
        return results

    def test_dice_system(self) -> Dict[str, Any]:
        """Test dice rolling functionality"""
        self.log("\n🧪 Testing Dice System...")
        results = {
            "basic_roll": False,
            "complex_roll": False,
            "advantage_roll": False,
            "skill_check": False,
            "dice_expressions": []
        }
        
        dice_tests = [
            ("roll 1d20", "basic_roll"),
            ("roll 3d6+2", "complex_roll"),
            ("roll 1d20 advantage", "advantage_roll"),
            ("stealth check", "skill_check")
        ]
        
        try:
            for dice_cmd, test_key in dice_tests:
                response = self.dm_assistant.process_dm_input(dice_cmd)
                if "Result:" in response and ("Expression:" in response or "ROLL" in response):
                    results[test_key] = True
                    results["dice_expressions"].append(dice_cmd)
                    self.log(f"✅ Dice Test ({dice_cmd}): Success")
                else:
                    self.log(f"❌ Dice Test ({dice_cmd}): Failed", "ERROR")
                    
        except Exception as e:
            self.log(f"❌ Dice System test failed: {e}", "ERROR")
            
        return results

    def test_combat_system(self) -> Dict[str, Any]:
        """Test combat system functionality"""
        self.log("\n🧪 Testing Combat System...")
        results = {
            "combat_start": False,
            "add_combatant": False,
            "combat_status": False,
            "next_turn": False,
            "combat_end": False
        }
        
        try:
            # Add combatants first
            response = self.dm_assistant.process_dm_input("add combatant Goblin")
            if "Added" in response:
                results["add_combatant"] = True
                self.log("✅ Add Combatant: Successfully added")
            
            # Start combat
            response = self.dm_assistant.process_dm_input("start combat")
            if "COMBAT STARTED" in response:
                results["combat_start"] = True
                self.log("✅ Combat Start: Successfully started")
                
                # Test combat status
                response = self.dm_assistant.process_dm_input("combat status")
                if "Combat Status" in response:
                    results["combat_status"] = True
                    self.log("✅ Combat Status: Retrieved status")
                
                # Test next turn
                response = self.dm_assistant.process_dm_input("next turn")
                if "Now active" in response or "Turn advanced" in response:
                    results["next_turn"] = True
                    self.log("✅ Next Turn: Successfully advanced")
                
                # End combat
                response = self.dm_assistant.process_dm_input("end combat")
                if "COMBAT ENDED" in response:
                    results["combat_end"] = True
                    self.log("✅ Combat End: Successfully ended")
            else:
                self.log("❌ Combat Start: Failed to start combat", "ERROR")
                
        except Exception as e:
            self.log(f"❌ Combat System test failed: {e}", "ERROR")
            
        return results

    def test_rule_enforcement(self) -> Dict[str, Any]:
        """Test rule enforcement and queries"""
        self.log("\n🧪 Testing Rule Enforcement...")
        results = {
            "basic_rule": False,
            "condition_query": False,
            "combat_rule": False,
            "spell_rule": False,
            "rules_tested": []
        }
        
        rule_tests = [
            ("what is advantage", "basic_rule"),
            ("charmed condition", "condition_query"),
            ("opportunity attack", "combat_rule"),
            ("concentration saves", "spell_rule")
        ]
        
        try:
            for rule_query, test_key in rule_tests:
                response = self.dm_assistant.process_dm_input(rule_query)
                if len(response) > 50 and "❌" not in response:
                    results[test_key] = True
                    results["rules_tested"].append(rule_query)
                    self.log(f"✅ Rule Query ({rule_query}): Success")
                else:
                    self.log(f"❌ Rule Query ({rule_query}): Failed", "ERROR")
                    
        except Exception as e:
            self.log(f"❌ Rule Enforcement test failed: {e}", "ERROR")
            
        return results

    def run_dnd_campaign_simulation(self, rounds: int = 5) -> Dict[str, Any]:
        """Run a complete D&D campaign simulation"""
        self.log(f"\n🎭 Running D&D Campaign Simulation ({rounds} rounds)...")
        
        simulation_results = {
            "rounds_completed": 0,
            "story_consistency": True,
            "error_count": 0,
            "scenario_generations": 0,
            "player_choices": 0,
            "narrative_progression": [],
            "performance_data": []
        }
        
        try:
            # Setup campaign
            self.log("Setting up campaign...")
            setup_response = self.dm_assistant.process_dm_input("list campaigns")
            if "AVAILABLE CAMPAIGNS" in setup_response:
                self.dm_assistant.process_dm_input("1")  # Select first campaign
                self.log("✅ Campaign selected")
            
            # Run simulation rounds
            for round_num in range(1, rounds + 1):
                self.log(f"\n🎲 Round {round_num} of {rounds}")
                round_start = time.time()
                
                try:
                    # Generate scenario
                    scenario_prompt = f"Generate scenario for round {round_num}: The party continues their adventure"
                    scenario_response = self.dm_assistant.process_dm_input(scenario_prompt)
                    
                    if len(scenario_response) > 100 and "❌" not in scenario_response:
                        simulation_results["scenario_generations"] += 1
                        self.log(f"✅ Scenario generated for round {round_num}")
                        
                        # Extract story content for consistency check
                        narrative_entry = {
                            "round": round_num,
                            "scenario": scenario_response[:200] + "...",
                            "timestamp": datetime.now().isoformat(),
                            "word_count": len(scenario_response.split())
                        }
                        simulation_results["narrative_progression"].append(narrative_entry)
                        
                        # Simulate player choice (select option 1 if available)
                        if any(num in scenario_response for num in ["1.", "2.", "3."]):
                            choice_response = self.dm_assistant.process_dm_input("select option 1")
                            if "SELECTED" in choice_response and "STORY CONTINUES" in choice_response:
                                simulation_results["player_choices"] += 1
                                self.log(f"✅ Player choice processed for round {round_num}")
                                
                                # Add choice consequence to narrative
                                narrative_entry["choice_consequence"] = choice_response[:200] + "..."
                            else:
                                self.log(f"⚠️ Player choice failed for round {round_num}", "ERROR")
                                simulation_results["error_count"] += 1
                    else:
                        self.log(f"❌ Scenario generation failed for round {round_num}", "ERROR")
                        simulation_results["error_count"] += 1
                        simulation_results["story_consistency"] = False
                    
                    # Performance tracking
                    round_time = time.time() - round_start
                    simulation_results["performance_data"].append({
                        "round": round_num,
                        "duration": round_time,
                        "success": simulation_results["error_count"] == 0
                    })
                    
                    simulation_results["rounds_completed"] = round_num
                    
                    # Brief pause between rounds
                    time.sleep(1)
                    
                except Exception as e:
                    self.log(f"❌ Round {round_num} failed: {e}", "ERROR")
                    simulation_results["error_count"] += 1
                    simulation_results["story_consistency"] = False
                    break
            
            # Calculate overall success
            success_rate = (simulation_results["rounds_completed"] - simulation_results["error_count"]) / simulation_results["rounds_completed"] if simulation_results["rounds_completed"] > 0 else 0
            simulation_results["success_rate"] = success_rate
            
            self.log(f"\n📊 Campaign Simulation Complete:")
            self.log(f"   • Rounds Completed: {simulation_results['rounds_completed']}/{rounds}")
            self.log(f"   • Scenarios Generated: {simulation_results['scenario_generations']}")
            self.log(f"   • Player Choices: {simulation_results['player_choices']}")
            self.log(f"   • Errors: {simulation_results['error_count']}")
            self.log(f"   • Success Rate: {success_rate:.1%}")
            
        except Exception as e:
            self.log(f"❌ Campaign simulation failed: {e}", "ERROR")
            simulation_results["error_count"] += 1
            
        return simulation_results

    def test_pipeline_performance(self) -> Dict[str, Any]:
        """Test pipeline performance and caching"""
        self.log("\n🧪 Testing Pipeline Performance...")
        results = {
            "caching_enabled": False,
            "cache_hits": 0,
            "response_times": [],
            "pipeline_status": {}
        }
        
        try:
            # Test repeated queries to check caching
            test_query = "What is a dragon in D&D?"
            
            # First query (should be slow)
            start_time = time.time()
            response1 = self.dm_assistant.process_dm_input(test_query)
            first_time = time.time() - start_time
            results["response_times"].append(("first", first_time))
            
            # Second query (should be faster if cached)
            start_time = time.time()
            response2 = self.dm_assistant.process_dm_input(test_query)
            second_time = time.time() - start_time
            results["response_times"].append(("second", second_time))
            
            # Check if caching worked (second should be significantly faster)
            if second_time < first_time * 0.5:  # 50% faster
                results["caching_enabled"] = True
                results["cache_hits"] = 1
                self.log(f"✅ Caching: Detected speedup ({first_time:.2f}s → {second_time:.2f}s)")
            else:
                self.log(f"⚠️ Caching: No significant speedup detected")
            
            # Test pipeline status if available
            if hasattr(self.dm_assistant, 'pipeline_manager'):
                try:
                    cache_stats = self.dm_assistant.pipeline_manager.get_cache_stats()
                    results["pipeline_status"] = cache_stats
                    self.log(f"✅ Pipeline Status: {cache_stats}")
                except:
                    pass
                    
        except Exception as e:
            self.log(f"❌ Pipeline Performance test failed: {e}", "ERROR")
            
        return results

    def generate_system_architecture_diagram(self):
        """Generate system architecture diagram"""
        self.log("\n📊 Generating System Architecture Diagram...")
        
        try:
            fig, ax = plt.subplots(1, 1, figsize=(16, 12))
            
            # Create a directed graph
            G = nx.DiGraph()
            
            # Add nodes for different components
            components = {
                "ModularDMAssistant": {"pos": (8, 10), "color": "#FF6B6B", "size": 2000},
                "AgentOrchestrator": {"pos": (8, 8), "color": "#4ECDC4", "size": 1500},
                "MessageBus": {"pos": (8, 6), "color": "#45B7D1", "size": 1200},
                
                # Agents
                "HaystackPipelineAgent": {"pos": (3, 7), "color": "#96CEB4", "size": 1000},
                "CampaignManagerAgent": {"pos": (13, 7), "color": "#FFEAA7", "size": 1000},
                "GameEngineAgent": {"pos": (3, 4), "color": "#DDA0DD", "size": 1000},
                "DiceSystemAgent": {"pos": (6, 4), "color": "#98D8C8", "size": 800},
                "CombatEngineAgent": {"pos": (10, 4), "color": "#F7DC6F", "size": 800},
                "NPCControllerAgent": {"pos": (13, 4), "color": "#BB8FCE", "size": 800},
                "ScenarioGeneratorAgent": {"pos": (16, 7), "color": "#85C1E9", "size": 1000},
                "RuleEnforcementAgent": {"pos": (16, 4), "color": "#F8C471", "size": 800},
                
                # Pipeline Components
                "PipelineManager": {"pos": (1, 9), "color": "#FD79A8", "size": 800},
                "SmartRouter": {"pos": (1, 7), "color": "#FDCB6E", "size": 600},
                "ErrorRecovery": {"pos": (1, 5), "color": "#E17055", "size": 600},
                "CreativeConsequence": {"pos": (1, 3), "color": "#A29BFE", "size": 600},
                
                # External Systems
                "QdrantDB": {"pos": (3, 1), "color": "#2D3436", "size": 800},
                "ClaudeLLM": {"pos": (6, 1), "color": "#636E72", "size": 800}
            }
            
            # Add nodes and edges
            for comp, props in components.items():
                G.add_node(comp, **props)
            
            # Define connections
            connections = [
                ("ModularDMAssistant", "AgentOrchestrator"),
                ("AgentOrchestrator", "MessageBus"),
                ("MessageBus", "HaystackPipelineAgent"),
                ("MessageBus", "CampaignManagerAgent"),
                ("MessageBus", "GameEngineAgent"),
                ("MessageBus", "DiceSystemAgent"),
                ("MessageBus", "CombatEngineAgent"),
                ("MessageBus", "NPCControllerAgent"),
                ("MessageBus", "ScenarioGeneratorAgent"),
                ("MessageBus", "RuleEnforcementAgent"),
                
                ("ModularDMAssistant", "PipelineManager"),
                ("PipelineManager", "SmartRouter"),
                ("PipelineManager", "ErrorRecovery"),
                ("PipelineManager", "CreativeConsequence"),
                
                ("HaystackPipelineAgent", "QdrantDB"),
                ("HaystackPipelineAgent", "ClaudeLLM"),
                ("ScenarioGeneratorAgent", "ClaudeLLM"),
            ]
            
            G.add_edges_from(connections)
            
            # Draw the graph
            pos = {node: props["pos"] for node, props in components.items()}
            colors = [components[node]["color"] for node in G.nodes()]
            sizes = [components[node]["size"] for node in G.nodes()]
            
            # Draw nodes
            nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=sizes, alpha=0.8)
            
            # Draw edges
            nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, arrowsize=20, alpha=0.6)
            
            # Draw labels
            nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')
            
            # Add title and legend
            ax.set_title("Modular DM Assistant - System Architecture", fontsize=16, fontweight='bold', pad=20)
            
            # Create legend
            legend_elements = [
                mpatches.Patch(color='#FF6B6B', label='Main System'),
                mpatches.Patch(color='#4ECDC4', label='Orchestration'),
                mpatches.Patch(color='#96CEB4', label='Core Agents'),
                mpatches.Patch(color='#FD79A8', label='Pipeline Components'),
                mpatches.Patch(color='#2D3436', label='External Systems')
            ]
            ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
            
            ax.set_xlim(-1, 18)
            ax.set_ylim(0, 11)
            ax.axis('off')
            
            plt.tight_layout()
            plt.savefig('system_architecture_diagram.png', dpi=300, bbox_inches='tight')
            self.log("✅ System Architecture Diagram saved as 'system_architecture_diagram.png'")
            
        except Exception as e:
            self.log(f"❌ Failed to generate architecture diagram: {e}", "ERROR")

    def generate_agent_communication_diagram(self):
        """Generate agent communication flow diagram"""
        self.log("\n📊 Generating Agent Communication Flow Diagram...")
        
        try:
            fig, ax = plt.subplots(1, 1, figsize=(14, 10))
            
            # Create communication flow
            G = nx.DiGraph()
            
            # Define agent positions in a circular layout
            agents = [
                "User/DM", "ModularDMAssistant", "AgentOrchestrator", "MessageBus",
                "HaystackAgent", "CampaignAgent", "GameEngineAgent", "DiceAgent",
                "CombatAgent", "NPCAgent", "ScenarioAgent", "RuleAgent"
            ]
            
            # Create circular positions
            import math
            positions = {}
            center = (0, 0)
            radius = 4
            
            for i, agent in enumerate(agents):
                angle = 2 * math.pi * i / len(agents)
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                positions[agent] = (x, y)
                G.add_node(agent)
            
            # Define message flows
            message_flows = [
                ("User/DM", "ModularDMAssistant", "Input"),
                ("ModularDMAssistant", "AgentOrchestrator", "Request"),
                ("AgentOrchestrator", "MessageBus", "Route"),
                ("MessageBus", "HaystackAgent", "Query"),
                ("MessageBus", "CampaignAgent", "Campaign Ops"),
                ("MessageBus", "GameEngineAgent", "State Update"),
                ("MessageBus", "DiceAgent", "Roll Dice"),
                ("MessageBus", "CombatAgent", "Combat Ops"),
                ("MessageBus", "NPCAgent", "NPC Control"),
                ("MessageBus", "ScenarioAgent", "Generate Story"),
                ("MessageBus", "RuleAgent", "Check Rules"),
                ("HaystackAgent", "MessageBus", "Response"),
                ("CampaignAgent", "MessageBus", "Response"),
                ("GameEngineAgent", "MessageBus", "Response"),
                ("DiceAgent", "MessageBus", "Response"),
                ("CombatAgent", "MessageBus", "Response"),
                ("NPCAgent", "MessageBus", "Response"),
                ("ScenarioAgent", "MessageBus", "Response"),
                ("RuleAgent", "MessageBus", "Response"),
                ("MessageBus", "AgentOrchestrator", "Collect"),
                ("AgentOrchestrator", "ModularDMAssistant", "Result"),
                ("ModularDMAssistant", "User/DM", "Output")
            ]
            
            # Add edges with labels
            for source, target, label in message_flows:
                G.add_edge(source, target, label=label)
            
            # Draw the graph
            nx.draw_networkx_nodes(G, positions, node_color='lightblue', 
                                 node_size=1500, alpha=0.8)
            nx.draw_networkx_edges(G, positions, edge_color='gray', 
                                 arrows=True, arrowsize=15, alpha=0.6)
            nx.draw_networkx_labels(G, positions, font_size=8, font_weight='bold')
            
            # Draw edge labels
            edge_labels = {(u, v): d['label'] for u, v, d in G.edges(data=True)}
            nx.draw_networkx_edge_labels(G, positions, edge_labels, font_size=6)
            
            ax.set_title("Agent Communication Flow", fontsize=16, fontweight='bold')
            ax.axis('off')
            
            plt.tight_layout()
            plt.savefig('agent_communication_diagram.png', dpi=300, bbox_inches='tight')
            self.log("✅ Agent Communication Diagram saved as 'agent_communication_diagram.png'")
            
        except Exception as e:
            self.log(f"❌ Failed to generate communication diagram: {e}", "ERROR")

    def generate_pipeline_flow_diagram(self):
        """Generate pipeline flow diagram"""
        self.log("\n📊 Generating Pipeline Flow Diagram...")
        
        try:
            fig, ax = plt.subplots(1, 1, figsize=(16, 10))
            
            # Create pipeline flow
            pipeline_steps = [
                {"name": "User Query", "pos": (1, 8), "color": "#E74C3C"},
                {"name": "Intent Classification", "pos": (3, 8), "color": "#3498DB"},
                {"name": "Smart Router", "pos": (5, 8), "color": "#9B59B6"},
                
                # Pipeline branches
                {"name": "Creative Pipeline", "pos": (7, 10), "color": "#E67E22"},
                {"name": "Factual Pipeline", "pos": (7, 8), "color": "#27AE60"},
                {"name": "Rules Pipeline", "pos": (7, 6), "color": "#F39C12"},
                {"name": "Hybrid Pipeline", "pos": (7, 4), "color": "#1ABC9C"},
                
                # Processing steps
                {"name": "LLM Generation", "pos": (9, 10), "color": "#E67E22"},
                {"name": "RAG Retrieval", "pos": (9, 8), "color": "#27AE60"},
                {"name": "Rule Lookup", "pos": (9, 6), "color": "#F39C12"},
                {"name": "Hybrid Processing", "pos": (9, 4), "color": "#1ABC9C"},
                
                # Cache and error handling
                {"name": "Intelligent Cache", "pos": (5, 10), "color": "#8E44AD"},
                {"name": "Error Recovery", "pos": (5, 2), "color": "#C0392B"},
                
                # Output
                {"name": "Response Formatter", "pos": (11, 7), "color": "#34495E"},
                {"name": "Final Output", "pos": (13, 7), "color": "#2C3E50"}
            ]
            
            # Draw pipeline components
            for step in pipeline_steps:
                circle = plt.Circle(step["pos"], 0.5, color=step["color"], alpha=0.7)
                ax.add_patch(circle)
                ax.text(step["pos"][0], step["pos"][1], step["name"], 
                       ha='center', va='center', fontsize=8, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.1", facecolor='white', alpha=0.8))
            
            # Draw connections
            connections = [
                ((1, 8), (3, 8)),  # Query to Intent
                ((3, 8), (5, 8)),  # Intent to Router
                ((5, 8), (7, 10)),  # Router to Creative
                ((5, 8), (7, 8)),   # Router to Factual
                ((5, 8), (7, 6)),   # Router to Rules
                ((5, 8), (7, 4)),   # Router to Hybrid
                ((7, 10), (9, 10)), # Creative to LLM
                ((7, 8), (9, 8)),   # Factual to RAG
                ((7, 6), (9, 6)),   # Rules to Lookup
                ((7, 4), (9, 4)),   # Hybrid to Processing
                ((9, 10), (11, 7)), # LLM to Formatter
                ((9, 8), (11, 7)),  # RAG to Formatter
                ((9, 6), (11, 7)),  # Lookup to Formatter
                ((9, 4), (11, 7)),  # Processing to Formatter
                ((11, 7), (13, 7)), # Formatter to Output
                ((5, 10), (5, 8)),  # Cache connection
                ((5, 2), (7, 4))    # Error recovery
            ]
            
            for start, end in connections:
                ax.annotate('', xy=end, xytext=start,
                           arrowprops=dict(arrowstyle='->', color='gray', alpha=0.6))
            
            ax.set_xlim(0, 14)
            ax.set_ylim(1, 11)
            ax.set_title("Pipeline Processing Flow", fontsize=16, fontweight='bold')
            ax.axis('off')
            
            # Add legend
            legend_elements = [
                mpatches.Patch(color='#E74C3C', label='Input'),
                mpatches.Patch(color='#3498DB', label='Routing'),
                mpatches.Patch(color='#E67E22', label='Creative Processing'),
                mpatches.Patch(color='#27AE60', label='Factual Processing'),
                mpatches.Patch(color='#F39C12', label='Rules Processing'),
                mpatches.Patch(color='#8E44AD', label='Caching'),
                mpatches.Patch(color='#C0392B', label='Error Handling'),
                mpatches.Patch(color='#2C3E50', label='Output')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            plt.tight_layout()
            plt.savefig('pipeline_flow_diagram.png', dpi=300, bbox_inches='tight')
            self.log("✅ Pipeline Flow Diagram saved as 'pipeline_flow_diagram.png'")
            
        except Exception as e:
            self.log(f"❌ Failed to generate pipeline diagram: {e}", "ERROR")

    def run_comprehensive_tests(self):
        """Run all comprehensive tests"""
        self.log("🚀 Starting Comprehensive Test Suite for Modular DM Assistant")
        self.log("=" * 80)
        
        # Initialize system
        if not self.initialize_dm_assistant():
            self.log("❌ Failed to initialize system, aborting tests", "ERROR")
            return
        
        try:
            # Run all test modules
            self.test_results["agent_framework"] = self.test_agent_framework()
            self.test_results["campaign_management"] = self.test_campaign_management()
            self.test_results["dice_system"] = self.test_dice_system()
            self.test_results["combat_system"] = self.test_combat_system()
            self.test_results["rule_enforcement"] = self.test_rule_enforcement()
            self.test_results["pipeline_performance"] = self.test_pipeline_performance()
            self.test_results["campaign_simulation"] = self.run_dnd_campaign_simulation(5)
            
            # Generate architecture diagrams
            self.generate_system_architecture_diagram()
            self.generate_agent_communication_diagram()
            self.generate_pipeline_flow_diagram()
            
            # Generate comprehensive report
            self.generate_test_report()
            
        except Exception as e:
            self.log(f"❌ Test suite failed: {e}", "ERROR")
            traceback.print_exc()
        
        finally:
            # Cleanup
            if self.dm_assistant:
                self.dm_assistant.stop()
                self.log("🛑 DM Assistant stopped")

    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.log("\n📋 Generating Comprehensive Test Report...")
        
        report_content = f"""
# Modular DM Assistant - Comprehensive Test Report

**Test Date:** {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}
**Test Duration:** {(datetime.now() - self.test_start_time).total_seconds():.2f} seconds
**Total Errors:** {len(self.error_log)}

## Executive Summary

This comprehensive test suite evaluated all components of the Modular DM Assistant system, including agent framework, pipeline performance, and end-to-end D&D campaign simulation.

## Test Results Overview

### Agent Framework
- **Agents Registered:** {self.test_results.get('agent_framework', {}).get('agent_count', 0)}
- **Message Bus Active:** {self.test_results.get('agent_framework', {}).get('message_bus_active', False)}
- **Agent Registration:** {'✅ PASS' if self.test_results.get('agent_framework', {}).get('agent_registration', False) else '❌ FAIL'}

### Campaign Management
- **Campaigns Found:** {self.test_results.get('campaign_management', {}).get('campaigns_found', 0)}
- **Players Found:** {self.test_results.get('campaign_management', {}).get('players_found', 0)}
- **Campaign Selection:** {'✅ PASS' if self.test_results.get('campaign_management', {}).get('campaign_selection', False) else '❌ FAIL'}
- **Player Management:** {'✅ PASS' if self.test_results.get('campaign_management', {}).get('player_list', False) else '❌ FAIL'}

### Dice System
- **Basic Rolls:** {'✅ PASS' if self.test_results.get('dice_system', {}).get('basic_roll', False) else '❌ FAIL'}
- **Complex Rolls:** {'✅ PASS' if self.test_results.get('dice_system', {}).get('complex_roll', False) else '❌ FAIL'}
- **Advantage System:** {'✅ PASS' if self.test_results.get('dice_system', {}).get('advantage_roll', False) else '❌ FAIL'}

### Combat System
- **Combat Start/End:** {'✅ PASS' if self.test_results.get('combat_system', {}).get('combat_start', False) else '❌ FAIL'}
- **Turn Management:** {'✅ PASS' if self.test_results.get('combat_system', {}).get('next_turn', False) else '❌ FAIL'}
- **Combatant Management:** {'✅ PASS' if self.test_results.get('combat_system', {}).get('add_combatant', False) else '❌ FAIL'}

### Rule Enforcement
- **Basic Rules:** {'✅ PASS' if self.test_results.get('rule_enforcement', {}).get('basic_rule', False) else '❌ FAIL'}
- **Condition Queries:** {'✅ PASS' if self.test_results.get('rule_enforcement', {}).get('condition_query', False) else '❌ FAIL'}
- **Combat Rules:** {'✅ PASS' if self.test_results.get('rule_enforcement', {}).get('combat_rule', False) else '❌ FAIL'}

### Campaign Simulation (5 Rounds)
- **Rounds Completed:** {self.test_results.get('campaign_simulation', {}).get('rounds_completed', 0)}/5
- **Scenarios Generated:** {self.test_results.get('campaign_simulation', {}).get('scenario_generations', 0)}
- **Player Choices:** {self.test_results.get('campaign_simulation', {}).get('player_choices', 0)}
- **Success Rate:** {self.test_results.get('campaign_simulation', {}).get('success_rate', 0):.1%}
- **Story Consistency:** {'✅ CONSISTENT' if self.test_results.get('campaign_simulation', {}).get('story_consistency', False) else '❌ INCONSISTENT'}

### Pipeline Performance
- **Caching Active:** {'✅ YES' if self.test_results.get('pipeline_performance', {}).get('caching_enabled', False) else '❌ NO'}
- **Cache Hits:** {self.test_results.get('pipeline_performance', {}).get('cache_hits', 0)}

## Detailed Analysis

### Story Consistency Assessment
"""
        
        # Add narrative progression analysis
        if "campaign_simulation" in self.test_results:
            narrative_data = self.test_results["campaign_simulation"].get("narrative_progression", [])
            if narrative_data:
                report_content += f"""
The campaign simulation generated {len(narrative_data)} narrative segments across {self.test_results['campaign_simulation']['rounds_completed']} rounds.

**Narrative Quality Metrics:**
"""
                total_words = sum(entry.get("word_count", 0) for entry in narrative_data)
                avg_words = total_words / len(narrative_data) if narrative_data else 0
                report_content += f"- Average response length: {avg_words:.0f} words\n"
                report_content += f"- Total narrative content: {total_words} words\n"
        
        # Add error analysis
        if self.error_log:
            report_content += f"""
### Error Analysis
**Total Errors:** {len(self.error_log)}

**Error Breakdown:**
"""
            error_types = {}
            for error in self.error_log:
                error_type = error['message'].split(':')[0] if ':' in error['message'] else 'General'
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                report_content += f"- {error_type}: {count} occurrences\n"
        
        # Add recommendations
        report_content += """
## Recommendations for Improvement

### High Priority
1. **Error Handling Enhancement**: Implement more robust error recovery mechanisms
2. **Performance Optimization**: Improve response times for scenario generation
3. **Story Continuity**: Enhance narrative consistency tracking across rounds

### Medium Priority
1. **Caching Strategy**: Optimize cache hit rates for frequently used queries
2. **Agent Communication**: Streamline message passing between agents
3. **Rule Engine**: Expand rule coverage and accuracy

### Low Priority
1. **User Interface**: Improve command parsing and feedback
2. **Logging**: Enhanced debug information for troubleshooting
3. **Documentation**: Update system documentation with current architecture

## Architecture Diagrams

The following diagrams have been generated:
- `system_architecture_diagram.png` - Overall system structure
- `agent_communication_diagram.png` - Agent message flow
- `pipeline_flow_diagram.png` - Pipeline processing flow

## Conclusion

"""
        
        # Calculate overall score
        total_tests = 0
        passed_tests = 0
        
        for module, results in self.test_results.items():
            if isinstance(results, dict):
                for test, result in results.items():
                    if isinstance(result, bool):
                        total_tests += 1
                        if result:
                            passed_tests += 1
        
        overall_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report_content += f"""
**Overall Test Score: {overall_score:.1f}% ({passed_tests}/{total_tests} tests passed)**

The Modular DM Assistant demonstrates {'strong' if overall_score > 75 else 'moderate' if overall_score > 50 else 'weak'} performance across all tested components. 
{'The system is ready for production use with minor improvements.' if overall_score > 80 else 'The system requires significant improvements before production deployment.' if overall_score < 60 else 'The system shows promise but needs optimization before production use.'}

---
*Generated by Comprehensive Test Suite*
*Test Framework Version: 1.0*
"""
        
        # Save report
        with open('dm_assistant_test_report.md', 'w') as f:
            f.write(report_content)
        
        self.log("✅ Comprehensive test report saved as 'dm_assistant_test_report.md'")
        self.log(f"📊 Overall Score: {overall_score:.1f}% ({passed_tests}/{total_tests} tests passed)")


def main():
    """Main function to run the comprehensive test suite"""
    print("🧪 Modular DM Assistant - Comprehensive Test Suite")
    print("=" * 60)
    
    tester = ModularDMTester(verbose=True)
    tester.run_comprehensive_tests()
    
    print("\n✅ Test suite complete! Check generated files:")
    print("   • dm_assistant_test_report.md")
    print("   • system_architecture_diagram.png")
    print("   • agent_communication_diagram.png")
    print("   • pipeline_flow_diagram.png")


if __name__ == "__main__":
    main()
"""
Modular RAG-Powered Dungeon Master Assistant
Main class that orchestrates the D&D assistant system with pluggable command handling
"""
import json
import time
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from agent_framework import AgentOrchestrator

# Import extracted helper classes
from narrative.narrative_tracker import NarrativeContinuityTracker
from cache_manager import SimpleInlineCache
from game_save_manager import GameSaveManager

# Import pluggable command handling system
from input_parser import ManualCommandHandler, BaseCommandHandler

# Claude-specific imports for text processing
CLAUDE_AVAILABLE = True


class ModularDMAssistant:
    """
    Main Modular DM Assistant class
    Focuses on core responsibilities: user interaction, agent orchestration, and system coordination
    """
    
    def __init__(self,
                 collection_name: str = "dnd_documents",
                 campaigns_dir: str = "resources/current_campaign",
                 players_dir: str = "docs/players",
                 verbose: bool = False,
                 enable_game_engine: bool = True,
                 tick_seconds: float = 0.8,
                 enable_caching: bool = True,
                 enable_async: bool = True,
                 game_save_file: Optional[str] = None,
                 command_handler: Optional[BaseCommandHandler] = None):
        """Initialize the modular DM assistant with pluggable command handling"""
        
        # Configuration
        self.collection_name = collection_name
        self.campaigns_dir = campaigns_dir
        self.players_dir = players_dir
        self.verbose = verbose
        self.enable_game_engine = enable_game_engine
        self.tick_seconds = tick_seconds
        self.has_llm = CLAUDE_AVAILABLE
        self.enable_caching = enable_caching
        self.enable_async = enable_async
        
        # Initialize helper classes
        self.cache_manager = SimpleInlineCache() if enable_caching else None
        self.narrative_tracker = NarrativeContinuityTracker() if enable_caching else None
        self.game_save_manager = GameSaveManager(verbose=verbose)
        
        # Agent orchestrator
        self.orchestrator = AgentOrchestrator()
        
        # Initialize pluggable command handler first
        if command_handler is None:
            self.command_handler = ManualCommandHandler(self)
        else:
            self.command_handler = command_handler
        
        # Initialize all D&D agents through the orchestrator, passing command handler for event registration
        self.orchestrator.initialize_dnd_agents(
            collection_name=collection_name,
            campaigns_dir=campaigns_dir,
            players_dir=players_dir,
            verbose=verbose,
            enable_game_engine=enable_game_engine,
            tick_seconds=tick_seconds,
            command_handler=self.command_handler
        )
        
        # Get agent references from orchestrator
        self.haystack_agent = self.orchestrator.haystack_agent
        self.campaign_agent = self.orchestrator.campaign_agent
        self.game_engine_agent = self.orchestrator.game_engine_agent
        self.npc_agent = self.orchestrator.npc_agent
        self.scenario_agent = self.orchestrator.scenario_agent
        self.dice_agent = self.orchestrator.dice_agent
        self.combat_agent = self.orchestrator.combat_agent
        self.rule_agent = self.orchestrator.rule_agent
        self.character_agent = self.orchestrator.character_agent
        self.session_agent = self.orchestrator.session_agent
        self.inventory_agent = self.orchestrator.inventory_agent
        self.spell_agent = self.orchestrator.spell_agent
        self.experience_agent = self.orchestrator.experience_agent
        
        # Game state tracking
        self.game_state = {}
        
        # Load game save if specified
        if game_save_file:
            self.game_save_manager.load_game_save(game_save_file, self)
        
        if self.verbose:
            print("🚀 Modular DM Assistant initialized successfully")
            print(f"🎛️ Using command handler: {type(self.command_handler).__name__}")
            if self.game_save_manager.has_save_loaded():
                print(f"💾 Loaded game save: {self.game_save_manager.get_current_save_file()}")
            self._print_system_status()
    
    def _print_system_status(self):
        """Print status of system components"""
        print("\n🔧 SYSTEM STATUS:")
        print(f"  • Caching: {'✅ Enabled' if self.enable_caching else '❌ Disabled'}")
        print(f"  • Async Processing: {'✅ Enabled' if self.enable_async else '❌ Disabled'}")
        print(f"  • Game Engine: {'✅ Enabled' if self.enable_game_engine else '❌ Disabled'}")
        
        # Show cache statistics
        if self.enable_caching and self.cache_manager:
            cache_stats = self.cache_manager.get_stats()
            print(f"  • Cache: {cache_stats['total_items']} items")
        print()
    
    def start(self):
        """Start the orchestrator and all agents"""
        try:
            self.orchestrator.start()
            if self.verbose:
                print("🚀 Agent orchestrator started")
                stats = self.orchestrator.get_message_statistics()
                print(f"📊 Message bus active with {stats['registered_agents']} agents")
                
                # Brief pause to allow agents to fully initialize
                time.sleep(0.2)
                
                # Print agent status after they've started
                self._print_agent_status()
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to start orchestrator: {e}")
            raise
    
    def stop(self):
        """Stop the orchestrator and all agents"""
        try:
            self.orchestrator.stop()
            if self.verbose:
                print("⏹️ Agent orchestrator stopped")
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to stop orchestrator: {e}")
    
    def _print_agent_status(self):
        """Print status of all registered agents"""
        status = self.orchestrator.get_agent_status()
        print("\n🎭 AGENT STATUS:")
        for agent_id, info in status.items():
            running_status = "🟢 Running" if info["running"] else "🔴 Stopped"
            print(f"  • {agent_id} ({info['agent_type']}): {running_status}")
            if info["handlers"]:
                handlers_display = ', '.join(info['handlers'][:3])
                if len(info['handlers']) > 3:
                    handlers_display += f"... (+{len(info['handlers']) - 3} more)"
                print(f"    Handlers: {handlers_display}")
        print()
    
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction using the pluggable command handler"""
        # Check for new events through orchestrator before processing command
        self.orchestrator.check_and_forward_events(verbose=self.verbose)
        
        return self.command_handler.handle_command(instruction)
    
    # Game save and utility methods
    

    def run_interactive(self):
        """Run the interactive DM assistant"""
        print("=== Modular RAG-Powered Dungeon Master Assistant ===")
        print("🤖 Using Agent Framework with Haystack Pipelines")
        print("Type 'help' for commands or 'quit' to exit")
        print()
        
        # Start the orchestrator
        self.start()
        
        try:
            while True:
                try:
                    dm_input = input("\nDM> ").strip()
                    
                    if dm_input.lower() in ["quit", "exit", "q"]:
                        break
                    
                    if not dm_input:
                        continue
                    
                    response = self.process_dm_input(dm_input)
                    print(response)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
        
        finally:
            # Stop the orchestrator
            self.stop()
            print("\n👋 Goodbye! All agents stopped.")


def main():
    """Main function to run the modular DM assistant"""
    try:
        # Get configuration from user
        collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
        if not collection_name:
            collection_name = "dnd_documents"
        
        # Check for existing game saves using GameSaveManager
        game_save_manager = GameSaveManager()
        saves = game_save_manager.list_game_saves()
        game_save_file = None
        
        if saves:
            print("\n💾 EXISTING GAME SAVES FOUND:")
            print("0. Start New Campaign")
            for i, save in enumerate(saves, 1):
                print(f"{i}. {save['save_name']} - {save['campaign']} ({save['last_modified']})")
            
            while True:
                try:
                    choice = input(f"\nSelect option (0-{len(saves)}): ").strip()
                    if choice == "0":
                        print("🆕 Starting new campaign...")
                        break
                    elif choice.isdigit():
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(saves):
                            selected_save = saves[choice_num - 1]
                            game_save_file = selected_save['filename']
                            print(f"📁 Loading save: {selected_save['save_name']}")
                            break
                    print(f"❌ Please enter a number between 0 and {len(saves)}")
                except (ValueError, KeyboardInterrupt):
                    print("❌ Invalid input. Please enter a number.")
        
        assistant = ModularDMAssistant(
            collection_name=collection_name,
            verbose=True,
            game_save_file=game_save_file
        )
        
        assistant.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")


if __name__ == "__main__":
    main()

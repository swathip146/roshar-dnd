#!/usr/bin/env python3
"""
Comprehensive D&D Game System Test Framework
Tests all pipelines, components, and functionality with extensive debug logging
Runs 5+ round gameplay session to validate story progression and consistency
"""

import os
import sys
import time
import json
import logging
import traceback
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import the game system
from game_initialization import GameInitConfig
from haystack_dnd_game import HaystackDnDGame

class DebugLogger:
    """Enhanced debug logger for comprehensive testing"""
    
    def __init__(self, log_file: str = "debug_test_log.txt"):
        self.log_file = log_file
        self.start_time = time.time()
        self.debug_data = {
            "test_start": datetime.now().isoformat(),
            "system_info": {},
            "component_tests": {},
            "gameplay_rounds": [],
            "failures": [],
            "performance_metrics": {},
            "story_progression": [],
            "validation_results": {}
        }
        
        # Setup file logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("DnDSystemTest")
        
        self.logger.info("=== D&D System Comprehensive Test Started ===")
        
    def log_component_test(self, component: str, test_name: str, result: bool, details: Dict[str, Any]):
        """Log component test results"""
        if component not in self.debug_data["component_tests"]:
            self.debug_data["component_tests"][component] = []
            
        test_result = {
            "test_name": test_name,
            "success": result,
            "timestamp": time.time(),
            "details": details
        }
        
        self.debug_data["component_tests"][component].append(test_result)
        self.logger.info(f"Component Test: {component}.{test_name} = {'PASS' if result else 'FAIL'}")
        
        if not result:
            self.debug_data["failures"].append({
                "component": component,
                "test": test_name,
                "details": details,
                "timestamp": time.time()
            })
            
    def log_gameplay_round(self, round_num: int, player_input: str, dm_response: str, 
                          processing_data: Dict[str, Any]):
        """Log gameplay round for story progression analysis"""
        round_data = {
            "round": round_num,
            "timestamp": time.time(),
            "player_input": player_input,
            "dm_response": dm_response,
            "processing_data": processing_data,
            "response_length": len(dm_response),
            "contains_choices": "choice" in dm_response.lower() or "option" in dm_response.lower(),
            "mentions_location": any(loc in dm_response.lower() for loc in ["tavern", "forest", "city", "dungeon", "library"]),
            "story_progression_score": self._calculate_story_progression_score(dm_response)
        }
        
        self.debug_data["gameplay_rounds"].append(round_data)
        self.debug_data["story_progression"].append({
            "round": round_num,
            "progression_score": round_data["story_progression_score"],
            "consistency_check": self._check_story_consistency(round_num),
            "narrative_elements": self._extract_narrative_elements(dm_response)
        })
        
        # Check for fallback indicators
        fallback_indicators = [
            "fallback", "world responds accordingly", "adventure continues",
            "something happens", "responds in unexpected ways"
        ]
        is_fallback = any(indicator in dm_response.lower() for indicator in fallback_indicators) if dm_response else True
        
        self.logger.info(f"Round {round_num}: Input={player_input[:50]}... Response={len(dm_response)} chars {'[FALLBACK]' if is_fallback else '[GENUINE]'}")
        
    def _calculate_story_progression_score(self, response: str) -> float:
        """Calculate story progression score based on response content - penalize fallbacks"""
        if not response:
            return 0.0
            
        score = 0.0
        response_lower = response.lower()
        
        # Check for fallback indicators first - these get zero score
        fallback_indicators = [
            "fallback", "world responds accordingly", "adventure continues",
            "something happens", "responds in unexpected ways", "error", "failed"
        ]
        
        if any(indicator in response_lower for indicator in fallback_indicators):
            return 0.0  # Fallback responses get no story progression score
        
        # Positive indicators for genuine responses
        if any(word in response_lower for word in ["discover", "find", "encounter", "meet", "enter"]):
            score += 0.3
        if any(word in response_lower for word in ["choice", "option", "decide", "action"]):
            score += 0.2
        if len(response) > 100:  # Detailed response
            score += 0.2
        if any(word in response_lower for word in ["story", "adventure", "quest", "mystery"]):
            score += 0.2
        if "you" in response_lower:  # Player engagement
            score += 0.1
            
        # Bonus for Stormlight Archive specific content
        stormlight_terms = ["spren", "stormlight", "shard", "highstorm", "roshar", "alethi", "vorin"]
        if any(term in response_lower for term in stormlight_terms):
            score += 0.3
            
        return min(score, 1.0)
        
    def _check_story_consistency(self, round_num: int) -> Dict[str, Any]:
        """Check story consistency across rounds"""
        if round_num < 2:
            return {"consistent": True, "reason": "First round"}
            
        previous_rounds = self.debug_data["gameplay_rounds"][-3:]  # Last 3 rounds
        
        # Check for location consistency
        locations = []
        for round_data in previous_rounds:
            response = round_data["dm_response"].lower()
            for loc in ["tavern", "forest", "city", "dungeon", "library", "cave", "castle"]:
                if loc in response:
                    locations.append(loc)
                    
        consistency_check = {
            "consistent": True,
            "locations_mentioned": locations,
            "location_changes": len(set(locations)),
            "response_quality": "good" if all(len(r["dm_response"]) > 50 for r in previous_rounds) else "poor"
        }
        
        return consistency_check
        
    def _extract_narrative_elements(self, response: str) -> Dict[str, bool]:
        """Extract narrative elements from response"""
        response_lower = response.lower()
        return {
            "has_dialogue": "\"" in response or "'" in response,
            "has_action": any(word in response_lower for word in ["move", "walk", "run", "attack", "cast"]),
            "has_description": any(word in response_lower for word in ["see", "notice", "observe", "appears"]),
            "has_emotion": any(word in response_lower for word in ["fear", "joy", "anger", "surprise", "wonder"]),
            "has_mystery": any(word in response_lower for word in ["strange", "mysterious", "unknown", "hidden"])
        }
        
    def log_failure(self, component: str, error: str, traceback_str: str):
        """Log system failures"""
        failure = {
            "component": component,
            "error": error,
            "traceback": traceback_str,
            "timestamp": time.time()
        }
        
        self.debug_data["failures"].append(failure)
        self.logger.error(f"FAILURE in {component}: {error}")
        
    def log_performance_metric(self, metric_name: str, value: Any, unit: str = ""):
        """Log performance metrics"""
        self.debug_data["performance_metrics"][metric_name] = {
            "value": value,
            "unit": unit,
            "timestamp": time.time()
        }
        
    def generate_report(self) -> str:
        """Generate comprehensive debug report"""
        total_time = time.time() - self.start_time
        
        # Calculate statistics
        total_tests = sum(len(tests) for tests in self.debug_data["component_tests"].values())
        failed_tests = len(self.debug_data["failures"])
        success_rate = ((total_tests - failed_tests) / total_tests * 100) if total_tests > 0 else 0
        
        # Story progression analysis
        avg_progression_score = 0
        if self.debug_data["story_progression"]:
            avg_progression_score = sum(sp["progression_score"] for sp in self.debug_data["story_progression"]) / len(self.debug_data["story_progression"])
        
        report = f"""
# D&D System Comprehensive Test Report
Generated: {datetime.now().isoformat()}
Test Duration: {total_time:.2f}s

## Summary
- Total Tests: {total_tests}
- Failed Tests: {failed_tests}
- Success Rate: {success_rate:.1f}%
- Gameplay Rounds: {len(self.debug_data["gameplay_rounds"])}
- Average Story Progression Score: {avg_progression_score:.2f}/1.0

## Component Test Results
"""
        
        for component, tests in self.debug_data["component_tests"].items():
            passed = sum(1 for t in tests if t["success"])
            total = len(tests)
            report += f"\n### {component}: {passed}/{total} tests passed\n"
            for test in tests:
                status = "✅" if test["success"] else "❌"
                report += f"- {status} {test['test_name']}\n"
                if not test["success"] and "error" in test["details"]:
                    report += f"  Error: {test['details']['error']}\n"
        
        report += "\n## Gameplay Session Analysis\n"
        for i, round_data in enumerate(self.debug_data["gameplay_rounds"]):
            report += f"\n### Round {round_data['round']}\n"
            report += f"- Input: {round_data['player_input']}\n"
            report += f"- Response Length: {round_data['response_length']} chars\n"
            report += f"- Story Progression Score: {round_data.get('story_progression_score', 0):.2f}\n"
            
            if i < len(self.debug_data["story_progression"]):
                sp = self.debug_data["story_progression"][i]
                narrative = sp.get("narrative_elements", {})
                report += f"- Narrative Elements: {sum(narrative.values())}/{len(narrative)} present\n"
        
        report += "\n## Failures and Issues\n"
        for failure in self.debug_data["failures"]:
            error_msg = failure.get('error', failure.get('details', {}).get('error', 'Unknown error'))
            component = failure.get('component', 'Unknown component')
            traceback_info = failure.get('traceback', 'No traceback available')
            report += f"\n### {component} - {error_msg}\n"
            report += f"```\n{traceback_info}\n```\n"
            
        report += "\n## Performance Metrics\n"
        for metric, data in self.debug_data["performance_metrics"].items():
            report += f"- {metric}: {data['value']} {data['unit']}\n"
            
        # Save full debug data as JSON
        debug_json_file = "debug_test_data.json"
        with open(debug_json_file, 'w') as f:
            json.dump(self.debug_data, f, indent=2, default=str)
            
        report += f"\n## Full Debug Data\nSaved to: {debug_json_file}\n"
        
        return report


class ComprehensiveDnDTester:
    """Comprehensive tester for D&D game system"""
    
    def __init__(self):
        self.debug_logger = DebugLogger()
        self.game = None
        self.test_config = None
        
    def run_all_tests(self):
        """Run all comprehensive tests"""
        try:
            self.debug_logger.logger.info("Starting comprehensive D&D system tests...")
            
            # Test 1: System initialization
            self.test_system_initialization()
            
            # Test 2: Component connectivity
            self.test_component_connectivity()
            
            # Test 3: Individual agent functionality
            self.test_agent_functionality()
            
            # Test 4: Pipeline integration
            self.test_pipeline_integration()
            
            # Test 5: Session management
            self.test_session_management()
            
            # Test 6: Game engine functionality
            self.test_game_engine()
            
            # Test 7: Document store and RAG
            self.test_document_store_rag()
            
            # Test 8: Full gameplay session (5+ rounds)
            self.test_full_gameplay_session()
            
            # Test 9: Error handling and recovery
            self.test_error_handling()
            
            # Test 10: Performance and resource usage
            self.test_performance()
            
        except Exception as e:
            self.debug_logger.log_failure("ComprehensiveTester", str(e), traceback.format_exc())
        finally:
            self.generate_final_report()
            
    def test_system_initialization(self):
        """Test system initialization and configuration"""
        self.debug_logger.logger.info("Testing system initialization...")
        
        try:
            # Initialize document store for testing
            from storage.simple_document_store import SimpleDocumentStore
            test_doc_store = None
            try:
                test_doc_store = SimpleDocumentStore(collection_name="dnd_documents")
                self.debug_logger.logger.info("Test document store created successfully")
            except Exception as doc_error:
                self.debug_logger.logger.warning(f"Could not create test document store: {doc_error}")
            
            # Test config creation using Shards of Honor campaign with document store
            self.test_config = GameInitConfig(
                collection_name="dnd_documents",
                game_mode="new_campaign",
                campaign_data={
                    "name": "Shards of Honor: The Veden Crisis",
                    "description": "A Stormlight Archive campaign set in the Shattered Plains",
                    "location": "Kholinar",
                    "story": "You stand in the war camp on the Shattered Plains, where the fate of kingdoms hangs in the balance. The storm approaches, and with it, destiny.",
                    "theme": "Stormlight Archive",
                    "difficulty": "Medium",
                    "setting": "Roshar",
                    "source": "shards_of_honor_campaign"
                },
                player_name="TestPlayer",
                shared_document_store=test_doc_store
            )
            
            self.debug_logger.log_component_test(
                "SystemInit", "config_creation", True,
                {"config_created": True, "collection_name": self.test_config.collection_name}
            )
            
            # Test game initialization
            start_time = time.time()
            self.game = HaystackDnDGame(config=self.test_config)
            init_time = time.time() - start_time
            
            self.debug_logger.log_performance_metric("game_initialization_time", init_time, "seconds")
            self.debug_logger.log_component_test(
                "SystemInit", "game_initialization", True,
                {"init_time": init_time, "game_created": True}
            )
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "SystemInit", "initialization", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_component_connectivity(self):
        """Test connectivity between major components"""
        self.debug_logger.logger.info("Testing component connectivity...")
        
        if not self.game:
            self.debug_logger.log_component_test(
                "Connectivity", "game_availability", False,
                {"error": "Game not initialized"}
            )
            return
        
        try:
            # Test orchestrator status
            status = self.game.orchestrator.get_pipeline_status()
            orchestrator_healthy = status.get("pipelines_enabled", False)
            
            self.debug_logger.log_component_test(
                "Connectivity", "orchestrator_status", orchestrator_healthy,
                {"status": status, "pipelines_enabled": orchestrator_healthy}
            )
            
            # Test session manager
            session_state = self.game.session_manager.get_session_state()
            session_active = session_state.get("session_active", False)
            
            self.debug_logger.log_component_test(
                "Connectivity", "session_manager", session_active,
                {"session_active": session_active, "player_name": session_state.get("player_name")}
            )
            
            # Test game engine
            game_stats = self.game.orchestrator.game_engine.get_game_statistics()
            engine_healthy = "session_duration" in game_stats
            
            self.debug_logger.log_component_test(
                "Connectivity", "game_engine", engine_healthy,
                {"stats": game_stats, "engine_responsive": engine_healthy}
            )
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "Connectivity", "component_connectivity", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_agent_functionality(self):
        """Test individual agent functionality"""
        self.debug_logger.logger.info("Testing individual agents...")
        
        if not self.game:
            return
            
        try:
            # Test each agent through the orchestrator
            agents = self.game.orchestrator.agents
            
            for agent_name, agent in agents.items():
                try:
                    # Basic agent health check
                    agent_healthy = agent is not None
                    
                    self.debug_logger.log_component_test(
                        "Agents", f"{agent_name}_availability", agent_healthy,
                        {"agent_type": type(agent).__name__, "agent_exists": agent_healthy}
                    )
                    
                    # Test agent state schema if available
                    if hasattr(agent, 'state_schema'):
                        schema_valid = isinstance(agent.state_schema, dict)
                        self.debug_logger.log_component_test(
                            "Agents", f"{agent_name}_schema", schema_valid,
                            {"schema": agent.state_schema if schema_valid else "invalid"}
                        )
                        
                except Exception as e:
                    self.debug_logger.log_component_test(
                        "Agents", f"{agent_name}_test", False,
                        {"error": str(e)}
                    )
                    
        except Exception as e:
            self.debug_logger.log_component_test(
                "Agents", "agent_functionality", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_pipeline_integration(self):
        """Test pipeline integration and routing"""
        self.debug_logger.logger.info("Testing pipeline integration...")
        
        if not self.game:
            return
            
        test_requests = [
            {
                "request_type": "gameplay_turn",
                "data": {"player_input": "look around", "actor": "player"},
                "expected_success": True
            },
            {
                "request_type": "scenario_generation", 
                "data": {"player_action": "search the room", "game_context": {"location": "tavern"}},
                "expected_success": True
            },
            {
                "request_type": "rag_query",
                "data": {"query": "tavern information", "context_type": "location"},
                "expected_success": True
            }
        ]
        
        for i, test_req in enumerate(test_requests):
            try:
                from orchestrator.pipeline_integration import GameRequest
                request = GameRequest(
                    request_type=test_req["request_type"],
                    data=test_req["data"]
                )
                
                start_time = time.time()
                response = self.game.orchestrator.process_request(request)
                process_time = time.time() - start_time
                
                success = response.success if hasattr(response, 'success') else bool(response)
                
                self.debug_logger.log_component_test(
                    "Pipeline", f"request_{i+1}_{test_req['request_type']}", success,
                    {
                        "request_type": test_req["request_type"],
                        "success": success,
                        "process_time": process_time,
                        "response_data": getattr(response, 'data', {}) if hasattr(response, 'data') else {}
                    }
                )
                
                self.debug_logger.log_performance_metric(
                    f"pipeline_{test_req['request_type']}_time", process_time, "seconds"
                )
                
            except Exception as e:
                self.debug_logger.log_component_test(
                    "Pipeline", f"request_{i+1}_{test_req['request_type']}", False,
                    {"error": str(e), "traceback": traceback.format_exc()}
                )
                
    def test_session_management(self):
        """Test session management functionality"""
        self.debug_logger.logger.info("Testing session management...")
        
        if not self.game:
            return
            
        try:
            # Test save functionality
            save_result = self.game.save_game("test_debug_save.json")
            
            self.debug_logger.log_component_test(
                "SessionMgmt", "save_game", save_result,
                {"save_successful": save_result}
            )
            
            # Test session state retrieval
            session_state = self.game.session_manager.get_session_state()
            state_valid = session_state.get("session_active", False)
            
            self.debug_logger.log_component_test(
                "SessionMgmt", "session_state", state_valid,
                {"session_state": session_state}
            )
            
            # Test game statistics
            game_stats = self.game.get_game_stats()
            stats_valid = isinstance(game_stats, dict) and "location" in game_stats
            
            self.debug_logger.log_component_test(
                "SessionMgmt", "game_statistics", stats_valid,
                {"stats": game_stats}
            )
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "SessionMgmt", "session_management", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_game_engine(self):
        """Test game engine and skill check pipeline"""
        self.debug_logger.logger.info("Testing game engine...")
        
        if not self.game:
            return
            
        try:
            engine = self.game.orchestrator.game_engine
            
            # Test skill check processing
            skill_check = {
                "action": "test skill check",
                "actor": "player",
                "skill": "perception",
                "context": {"difficulty": "medium"}
            }
            
            start_time = time.time()
            result = engine.process_skill_check(skill_check)
            skill_time = time.time() - start_time
            
            skill_success = "success" in result and "roll_total" in result
            
            self.debug_logger.log_component_test(
                "GameEngine", "skill_check", skill_success,
                {"result": result, "process_time": skill_time}
            )
            
            self.debug_logger.log_performance_metric("skill_check_time", skill_time, "seconds")
            
            # Test game state export
            game_state = engine.export_game_state()
            export_success = isinstance(game_state, dict) and "game_state" in game_state
            
            self.debug_logger.log_component_test(
                "GameEngine", "state_export", export_success,
                {"export_keys": list(game_state.keys()) if export_success else []}
            )
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "GameEngine", "game_engine", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_document_store_rag(self):
        """Test document store and RAG functionality"""
        self.debug_logger.logger.info("Testing document store and RAG...")
        
        if not self.game:
            return
            
        try:
            # Test document store connection
            if hasattr(self.game.config, 'shared_document_store') and self.game.config.shared_document_store:
                doc_store = self.game.config.shared_document_store
                
                # Test search functionality
                search_results = doc_store.simple_search("tavern")
                search_success = isinstance(search_results, list)
                
                self.debug_logger.log_component_test(
                    "DocumentStore", "search", search_success,
                    {"results_count": len(search_results), "search_worked": search_success}
                )
                
                # Test enhanced search
                enhanced_results = doc_store.search_with_metadata("adventure", top_k=2)
                enhanced_success = isinstance(enhanced_results, list)
                
                self.debug_logger.log_component_test(
                    "DocumentStore", "enhanced_search", enhanced_success,
                    {"enhanced_results_count": len(enhanced_results)}
                )
                
            else:
                self.debug_logger.log_component_test(
                    "DocumentStore", "availability", False,
                    {"error": "No shared document store available"}
                )
                
        except Exception as e:
            self.debug_logger.log_component_test(
                "DocumentStore", "document_store_rag", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_full_gameplay_session(self):
        """Test full gameplay session with 5+ rounds"""
        self.debug_logger.logger.info("Testing full gameplay session (5+ rounds)...")
        
        if not self.game:
            return
            
        # Define test gameplay sequence for story progression
        gameplay_sequence = [
            "look around the tavern",
            "talk to the bartender",
            "ask about local rumors",
            "investigate the mysterious door",
            "search for clues about the missing merchant",
            "examine the strange artifact on the table",
            "listen to the conversation at the next table"
        ]
        
        try:
            session_start_time = time.time()
            
            for round_num, player_input in enumerate(gameplay_sequence, 1):
                self.debug_logger.logger.info(f"=== Gameplay Round {round_num} ===")
                
                try:
                    # Process the turn
                    turn_start_time = time.time()
                    dm_response = self.game.play_turn(player_input)
                    turn_time = time.time() - turn_start_time
                    
                    # Validate response - treat fallbacks as failures
                    response_valid = isinstance(dm_response, str) and len(dm_response) > 0
                    
                    # Check for fallback indicators (these count as failures)
                    fallback_indicators = [
                        "fallback",
                        "world responds accordingly",
                        "adventure continues",
                        "something happens",
                        "responds in unexpected ways",
                        "error",
                        "failed",
                        "cannot",
                        "unable to process"
                    ]
                    
                    is_fallback = any(indicator in dm_response.lower() for indicator in fallback_indicators) if dm_response else True
                    
                    # Extract processing data for analysis
                    processing_data = {
                        "response_time": turn_time,
                        "response_valid": response_valid,
                        "response_type": "string" if isinstance(dm_response, str) else type(dm_response).__name__,
                        "is_fallback": is_fallback,
                        "turn_successful": response_valid and not is_fallback and dm_response != "Error",
                        "response_content": dm_response[:200] if dm_response else "No response"
                    }
                    
                    # Log the gameplay round
                    self.debug_logger.log_gameplay_round(
                        round_num, player_input, dm_response or "No response", processing_data
                    )
                    
                    # Log component test result - fail if fallback used
                    turn_success = response_valid and not is_fallback
                    self.debug_logger.log_component_test(
                        "Gameplay", f"round_{round_num}", turn_success,
                        {
                            "input": player_input,
                            "response_length": len(dm_response) if dm_response else 0,
                            "response_time": turn_time,
                            "is_fallback": is_fallback,
                            "fallback_reason": "Contains fallback indicators" if is_fallback else None,
                            "response_preview": dm_response[:100] if dm_response else "No response"
                        }
                    )
                    
                    self.debug_logger.log_performance_metric(
                        f"round_{round_num}_time", turn_time, "seconds"
                    )
                    
                    # Brief pause to simulate realistic gameplay
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.debug_logger.log_component_test(
                        "Gameplay", f"round_{round_num}", False,
                        {"error": str(e), "input": player_input}
                    )
                    
                    # Continue with next round even if this one fails
                    continue
            
            session_time = time.time() - session_start_time
            self.debug_logger.log_performance_metric("full_session_time", session_time, "seconds")
            
            # Analyze overall session success
            successful_rounds = len([r for r in self.debug_logger.debug_data["gameplay_rounds"] 
                                   if r.get("processing_data", {}).get("turn_successful", False)])
            
            session_success = successful_rounds >= 3  # At least 3 successful rounds
            
            self.debug_logger.log_component_test(
                "Gameplay", "full_session", session_success,
                {
                    "total_rounds": len(gameplay_sequence),
                    "successful_rounds": successful_rounds,
                    "session_time": session_time
                }
            )
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "Gameplay", "full_gameplay_session", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def test_error_handling(self):
        """Test error handling and recovery"""
        self.debug_logger.logger.info("Testing error handling...")
        
        if not self.game:
            return
            
        # Test various error conditions
        error_tests = [
            {"input": "", "description": "empty_input"},
            {"input": None, "description": "null_input"},
            {"input": "x" * 1000, "description": "very_long_input"},
            {"input": "invalid unicode: \x00\x01\x02", "description": "invalid_unicode"}
        ]
        
        for i, error_test in enumerate(error_tests):
            try:
                response = self.game.play_turn(error_test["input"])
                
                # Error handling success only if we get proper response, not fallback
                error_handled = response is not None
                
                # Check for fallback in error responses too
                is_error_fallback = False
                if response:
                    fallback_indicators = ["fallback", "world responds accordingly", "adventure continues", "error", "failed"]
                    is_error_fallback = any(indicator in response.lower() for indicator in fallback_indicators)
                
                # Only consider it successful error handling if no fallback was used
                error_handling_success = error_handled and not is_error_fallback
                
                self.debug_logger.log_component_test(
                    "ErrorHandling", f"error_{error_test['description']}", error_handling_success,
                    {
                        "input": str(error_test["input"])[:100],  # Truncate for logging
                        "response_received": error_handled,
                        "is_fallback": is_error_fallback,
                        "response": str(response)[:200] if response else None
                    }
                )
                
            except Exception as e:
                self.debug_logger.log_component_test(
                    "ErrorHandling", f"error_{error_test['description']}", False,
                    {"error": str(e), "input": str(error_test["input"])[:100]}
                )
                
    def test_performance(self):
        """Test performance and resource usage"""
        self.debug_logger.logger.info("Testing performance...")
        
        if not self.game:
            return
            
        try:
            # Test repeated operations
            num_operations = 5
            total_time = 0
            
            for i in range(num_operations):
                start_time = time.time()
                response = self.game.play_turn(f"test operation {i+1}")
                operation_time = time.time() - start_time
                total_time += operation_time
                
            avg_response_time = total_time / num_operations
            
            # Performance is good if average response time is under 10 seconds
            performance_good = avg_response_time < 10.0
            
            self.debug_logger.log_component_test(
                "Performance", "average_response_time", performance_good,
                {
                    "avg_time": avg_response_time,
                    "total_operations": num_operations,
                    "total_time": total_time
                }
            )
            
            self.debug_logger.log_performance_metric("avg_response_time", avg_response_time, "seconds")
            
        except Exception as e:
            self.debug_logger.log_component_test(
                "Performance", "performance_test", False,
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            
    def generate_final_report(self):
        """Generate and save final comprehensive report"""
        self.debug_logger.logger.info("Generating final report...")
        
        report = self.debug_logger.generate_report()
        
        # Save report to file
        report_file = "comprehensive_test_report.md"
        with open(report_file, 'w') as f:
            f.write(report)
            
        self.debug_logger.logger.info(f"Comprehensive test report saved to {report_file}")
        print(f"\n{'='*60}")
        print("COMPREHENSIVE D&D SYSTEM TEST COMPLETED")
        print(f"{'='*60}")
        print(f"Report saved to: {report_file}")
        print(f"Debug data saved to: debug_test_data.json")
        print(f"Debug log saved to: {self.debug_logger.log_file}")
        print(f"{'='*60}")


def main():
    """Main test execution function"""
    print("Starting Comprehensive D&D System Test...")
    print("This will test all components and run a full gameplay session.")
    print("Please wait, this may take several minutes...")
    print("-" * 60)
    
    tester = ComprehensiveDnDTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
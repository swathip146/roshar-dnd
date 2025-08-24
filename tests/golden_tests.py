#!/usr/bin/env python3
"""
Phase 5: Golden Tests for Comprehensive System Validation
Reference tests that capture expected behavior for regression testing
"""

import sys
import os
import pytest
import json
import uuid
import time
from typing import Dict, Any, List

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from orchestrator.unified_pipeline_simple import SimpleUnifiedPipeline
from observability.decision_logger import DecisionLogger, get_decision_logger
from shared_contract import validate_scenario


class GoldenTestSuite:
    """
    Golden test suite for complete system validation
    Tests capture expected behavior for all major flows
    """
    
    def __init__(self):
        self.pipeline = SimpleUnifiedPipeline()
        self.logger = DecisionLogger()
    
    def run_golden_test(self, test_name: str, request: Dict[str, Any], expected_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a golden test with observability logging
        
        Args:
            test_name: Name of the test
            request: Input request
            expected_outputs: Expected output patterns
            
        Returns:
            Test result with validation details
        """
        correlation_id = str(uuid.uuid4())
        
        # Run pipeline
        result = self.pipeline.run(request)
        
        # Validate result structure
        validation_results = {
            "test_name": test_name,
            "correlation_id": correlation_id,
            "success": result.get("success", False),
            "expected_route": expected_outputs.get("route"),
            "actual_route": None,
            "expected_rag": expected_outputs.get("rag_needed"),
            "actual_rag": None,
            "schema_valid": False,
            "errors": []
        }
        
        if result["success"]:
            result_data = result["result"]
            
            # Determine actual route and RAG status
            if "dto_with_scenario" in result_data:
                dto = result_data["dto_with_scenario"]
                validation_results["actual_route"] = dto.get("route", "scenario")
                validation_results["actual_rag"] = dto.get("rag", {}).get("needed", False)
                
                # Validate scenario schema if present
                if "scenario" in dto:
                    errors = validate_scenario(dto["scenario"])
                    validation_results["schema_valid"] = len(errors) == 0
                    if errors:
                        validation_results["errors"].extend(errors)
                        
            elif "dto_with_npc" in result_data:
                validation_results["actual_route"] = "npc"
                validation_results["actual_rag"] = result_data["dto_with_npc"].get("rag", {}).get("needed", False)
                
            elif "dto_with_rules" in result_data:
                validation_results["actual_route"] = "rules"
                validation_results["actual_rag"] = result_data["dto_with_rules"].get("rag", {}).get("needed", False)
                
            elif "dto_with_meta" in result_data:
                validation_results["actual_route"] = "meta"
                validation_results["actual_rag"] = result_data["dto_with_meta"].get("rag", {}).get("needed", False)
        
        # Validate expectations
        route_match = validation_results["actual_route"] == validation_results["expected_route"]
        rag_match = validation_results["actual_rag"] == validation_results["expected_rag"]
        
        validation_results["route_correct"] = route_match
        validation_results["rag_correct"] = rag_match
        validation_results["overall_pass"] = (
            validation_results["success"] and
            route_match and
            rag_match and
            (validation_results["actual_route"] != "scenario" or validation_results["schema_valid"])
        )
        
        return validation_results


def test_golden_scenario_generation():
    """Golden Test: Scenario generation with RAG triggering"""
    suite = GoldenTestSuite()
    
    test_cases = [
        {
            "name": "ancient_artifact_examination",
            "request": {
                "player_input": "I carefully examine the ancient artifact on the pedestal",
                "context": {"location": "Temple of Mysteries", "difficulty": "medium"}
            },
            "expected": {
                "route": "scenario",
                "rag_needed": True  # "ancient" and "artifact" should trigger RAG
            }
        },
        {
            "name": "simple_room_search",
            "request": {
                "player_input": "I search the room thoroughly",
                "context": {"location": "Inn Room", "difficulty": "easy"}
            },
            "expected": {
                "route": "scenario", 
                "rag_needed": False  # No RAG triggers
            }
        },
        {
            "name": "magic_spell_casting",
            "request": {
                "player_input": "I cast a magic missile at the dragon",
                "context": {"location": "Dragon's Lair", "difficulty": "hard", "combat": True}
            },
            "expected": {
                "route": "scenario",
                "rag_needed": True  # "magic" and "dragon" should trigger RAG
            }
        }
    ]
    
    results = []
    for case in test_cases:
        result = suite.run_golden_test(case["name"], case["request"], case["expected"])
        results.append(result)
        
        # Assertions for pytest
        assert result["overall_pass"], f"Golden test '{case['name']}' failed: {result}"
        assert result["route_correct"], f"Route mismatch in '{case['name']}': expected {result['expected_route']}, got {result['actual_route']}"
        assert result["rag_correct"], f"RAG mismatch in '{case['name']}': expected {result['expected_rag']}, got {result['actual_rag']}"
        if result["actual_route"] == "scenario":
            assert result["schema_valid"], f"Schema validation failed in '{case['name']}': {result['errors']}"
    
    # Don't return results for pytest compatibility


def test_golden_npc_interactions():
    """Golden Test: NPC interaction routing"""
    suite = GoldenTestSuite()
    
    test_cases = [
        {
            "name": "innkeeper_conversation",
            "request": {
                "player_input": "I talk to the innkeeper about local rumors",
                "context": {"location": "The Prancing Pony"}
            },
            "expected": {
                "route": "npc",
                "rag_needed": False
            }
        },
        {
            "name": "merchant_negotiation",
            "request": {
                "player_input": "I ask the merchant about ancient relics",
                "context": {"location": "Marketplace"}
            },
            "expected": {
                "route": "npc",
                "rag_needed": True  # "ancient" should trigger RAG
            }
        },
        {
            "name": "guard_intimidation",
            "request": {
                "player_input": "I speak with the guard and try to intimidate him",
                "context": {"location": "City Gate"}
            },
            "expected": {
                "route": "npc",
                "rag_needed": False
            }
        }
    ]
    
    results = []
    for case in test_cases:
        result = suite.run_golden_test(case["name"], case["request"], case["expected"])
        results.append(result)
        
        assert result["overall_pass"], f"Golden test '{case['name']}' failed: {result}"
        assert result["route_correct"], f"Route mismatch in '{case['name']}'"
        assert result["rag_correct"], f"RAG mismatch in '{case['name']}'"
    
    # Don't return results for pytest compatibility


def test_golden_rules_lookup():
    """Golden Test: Rules and mechanics lookup"""
    suite = GoldenTestSuite()
    
    test_cases = [
        {
            "name": "skill_check_rules",
            "request": {
                "player_input": "How do skill checks work in combat?",
                "context": {}
            },
            "expected": {
                "route": "rules",
                "rag_needed": False
            }
        },
        {
            "name": "spell_mechanics",
            "request": {
                "player_input": "What are the rules for concentration spells?",
                "context": {}
            },
            "expected": {
                "route": "rules",
                "rag_needed": True  # "spell" should trigger RAG
            }
        },
        {
            "name": "combat_mechanics",
            "request": {
                "player_input": "How does initiative work?",
                "context": {}
            },
            "expected": {
                "route": "rules",
                "rag_needed": False
            }
        }
    ]
    
    results = []
    for case in test_cases:
        result = suite.run_golden_test(case["name"], case["request"], case["expected"])
        results.append(result)
        
        assert result["overall_pass"], f"Golden test '{case['name']}' failed: {result}"
        assert result["route_correct"], f"Route mismatch in '{case['name']}'"
        assert result["rag_correct"], f"RAG mismatch in '{case['name']}'"
    
    # Don't return results for pytest compatibility


def test_golden_meta_commands():
    """Golden Test: Meta command processing"""
    suite = GoldenTestSuite()
    
    test_cases = [
        {
            "name": "save_game",
            "request": {
                "player_input": "save game", 
                "context": {}
            },
            "expected": {
                "route": "meta",
                "rag_needed": False
            }
        },
        {
            "name": "show_inventory", 
            "request": {
                "player_input": "show my inventory",
                "context": {}
            },
            "expected": {
                "route": "meta",
                "rag_needed": False
            }
        },
        {
            "name": "load_save",
            "request": {
                "player_input": "load my saved game",
                "context": {}
            },
            "expected": {
                "route": "meta", 
                "rag_needed": False
            }
        }
    ]
    
    results = []
    for case in test_cases:
        result = suite.run_golden_test(case["name"], case["request"], case["expected"])
        results.append(result)
        
        assert result["overall_pass"], f"Golden test '{case['name']}' failed: {result}"
        assert result["route_correct"], f"Route mismatch in '{case['name']}'"
        assert result["rag_correct"], f"RAG mismatch in '{case['name']}'"
    
    # Don't return results for pytest compatibility


def test_golden_edge_cases():
    """Golden Test: Edge cases and error conditions"""
    suite = GoldenTestSuite()
    
    test_cases = [
        {
            "name": "empty_input",
            "request": {
                "player_input": "",
                "context": {}
            },
            "expected": {
                "route": "scenario",  # Default fallback
                "rag_needed": False
            }
        },
        {
            "name": "nonsensical_input",
            "request": {
                "player_input": "purple monkey dishwasher quantum",
                "context": {}
            },
            "expected": {
                "route": "scenario",  # Default fallback
                "rag_needed": False
            }
        },
        {
            "name": "mixed_signals",
            "request": {
                "player_input": "I talk to the guard about save game rules",
                "context": {}
            },
            "expected": {
                "route": "rules",  # "rules" keyword should take precedence
                "rag_needed": False
            }
        }
    ]
    
    results = []
    for case in test_cases:
        result = suite.run_golden_test(case["name"], case["request"], case["expected"])
        results.append(result)
        
        # For edge cases, we mainly care that the system doesn't crash
        assert result["success"], f"Golden test '{case['name']}' should not crash: {result}"
    
    # Don't return results for pytest compatibility


def run_complete_golden_test_suite():
    """Run the complete golden test suite with observability"""
    print("=" * 60)
    print("RUNNING COMPLETE GOLDEN TEST SUITE")
    print("=" * 60)
    
    # Manually run and collect results since test functions don't return results anymore
    suite = GoldenTestSuite()
    all_results = []
    
    # Define all test cases in one place
    all_test_cases = [
        # Scenario tests
        ("ancient_artifact_examination", {
            "player_input": "I carefully examine the ancient artifact on the pedestal",
            "context": {"location": "Temple of Mysteries", "difficulty": "medium"}
        }, {"route": "scenario", "rag_needed": True}),
        
        ("simple_room_search", {
            "player_input": "I search the room thoroughly",
            "context": {"location": "Inn Room", "difficulty": "easy"}
        }, {"route": "scenario", "rag_needed": False}),
        
        ("magic_spell_casting", {
            "player_input": "I cast a magic missile at the dragon",
            "context": {"location": "Dragon's Lair", "difficulty": "hard", "combat": True}
        }, {"route": "scenario", "rag_needed": True}),
        
        # NPC tests
        ("innkeeper_conversation", {
            "player_input": "I talk to the innkeeper about local rumors",
            "context": {"location": "The Prancing Pony"}
        }, {"route": "npc", "rag_needed": False}),
        
        ("merchant_negotiation", {
            "player_input": "I ask the merchant about ancient relics",
            "context": {"location": "Marketplace"}
        }, {"route": "npc", "rag_needed": True}),
        
        ("guard_intimidation", {
            "player_input": "I speak with the guard and try to intimidate him",
            "context": {"location": "City Gate"}
        }, {"route": "npc", "rag_needed": False}),
        
        # Rules tests
        ("skill_check_rules", {
            "player_input": "How do skill checks work in combat?",
            "context": {}
        }, {"route": "rules", "rag_needed": False}),
        
        ("spell_mechanics", {
            "player_input": "What are the rules for concentration spells?",
            "context": {}
        }, {"route": "rules", "rag_needed": True}),
        
        ("combat_mechanics", {
            "player_input": "How does initiative work?",
            "context": {}
        }, {"route": "rules", "rag_needed": False}),
        
        # Meta tests
        ("save_game", {
            "player_input": "save game",
            "context": {}
        }, {"route": "meta", "rag_needed": False}),
        
        ("show_inventory", {
            "player_input": "show my inventory",
            "context": {}
        }, {"route": "meta", "rag_needed": False}),
        
        ("load_save", {
            "player_input": "load my saved game",
            "context": {}
        }, {"route": "meta", "rag_needed": False}),
        
        # Edge cases
        ("empty_input", {
            "player_input": "",
            "context": {}
        }, {"route": "scenario", "rag_needed": False}),
        
        ("nonsensical_input", {
            "player_input": "purple monkey dishwasher quantum",
            "context": {}
        }, {"route": "scenario", "rag_needed": False}),
        
        ("mixed_signals", {
            "player_input": "I talk to the guard about save game rules",
            "context": {}
        }, {"route": "rules", "rag_needed": False})
    ]
    
    # Run all test cases
    for name, request, expected in all_test_cases:
        result = suite.run_golden_test(name, request, expected)
        all_results.append(result)
    
    # Generate summary
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r["overall_pass"])
    
    print(f"\n=== GOLDEN TEST RESULTS ===")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {passed_tests/total_tests:.1%}")
    
    # Show failures
    failures = [r for r in all_results if not r["overall_pass"]]
    if failures:
        print(f"\n=== FAILURES ===")
        for failure in failures:
            print(f"❌ {failure['test_name']}: {failure['errors']}")
    else:
        print(f"\n✅ ALL GOLDEN TESTS PASSED!")
    
    # Export results
    timestamp = int(time.time())
    results_file = f"golden_test_results_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": passed_tests/total_tests
            },
            "all_results": all_results
        }, f, indent=2)
    
    print(f"\n📊 Results exported to: {results_file}")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    # Run complete golden test suite
    success = run_complete_golden_test_suite()
    
    # Also run with pytest
    pytest_args = [
        __file__,
        "-v",
        "--tb=short"
    ]
    
    print(f"\n=== RUNNING WITH PYTEST ===")
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0 and success:
        print(f"\n🎉 ALL PHASE 5 GOLDEN TESTS COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print(f"\n❌ Some golden tests failed")
        sys.exit(1)
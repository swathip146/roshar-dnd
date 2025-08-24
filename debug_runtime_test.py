#!/usr/bin/env python3
"""
Debug Runtime Test Script for Haystack D&D Game
Tests runtime consistency and helps identify performance issues
"""

import os
import sys
import time
import logging
from typing import List, Dict, Any

# Set debug mode environment variables
os.environ["HAYSTACK_DND_DEBUG"] = "true"
os.environ["PIPELINE_DEBUG"] = "true"

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from haystack_dnd_game import HaystackDnDGame
    from orchestrator.pipeline_integration import create_full_haystack_orchestrator
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class DebugRuntimeTester:
    """Test runtime consistency and performance of Haystack D&D Game"""
    
    def __init__(self):
        self.results = []
        self.debug_logger = logging.getLogger("DebugRuntimeTester")
        
    def run_initialization_tests(self) -> Dict[str, Any]:
        """Test game initialization performance and consistency"""
        print("🔍 INITIALIZATION TESTS")
        print("-" * 50)
        
        init_times = []
        init_results = []
        
        # Test multiple initializations
        for i in range(3):
            print(f"\n📝 Initialization Test {i+1}/3")
            
            try:
                start_time = time.time()
                game = HaystackDnDGame(debug_mode=True)
                init_time = time.time() - start_time
                init_times.append(init_time)
                
                # Test orchestrator status
                status = game.orchestrator.get_pipeline_status()
                
                init_results.append({
                    "test_number": i + 1,
                    "success": True,
                    "init_time": init_time,
                    "pipelines_enabled": status.get("pipelines_enabled", False),
                    "available_pipelines": len(status.get("available_pipelines", [])),
                    "available_agents": len(status.get("available_agents", [])),
                    "orchestrator_metrics": status.get("initialization_metrics", {})
                })
                
                print(f"  ✅ Initialized in {init_time:.2f}s")
                print(f"  🔧 Pipelines: {status.get('pipelines_enabled', False)}")
                print(f"  🤖 Agents: {len(status.get('available_agents', []))}")
                
                # Clean up
                del game
                
                # Wait between tests to avoid resource contention
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                init_results.append({
                    "test_number": i + 1,
                    "success": False,
                    "error": str(e),
                    "init_time": None
                })
        
        # Analyze results
        successful_inits = [r for r in init_results if r["success"]]
        if successful_inits:
            avg_time = sum(r["init_time"] for r in successful_inits) / len(successful_inits)
            min_time = min(r["init_time"] for r in successful_inits)
            max_time = max(r["init_time"] for r in successful_inits)
            variance = max_time - min_time
            
            print(f"\n📊 INITIALIZATION SUMMARY:")
            print(f"  Successful: {len(successful_inits)}/3")
            print(f"  Average time: {avg_time:.2f}s")
            print(f"  Range: {min_time:.2f}s - {max_time:.2f}s")
            print(f"  Variance: {variance:.2f}s")
            
            if variance > 1.0:
                print(f"  ⚠️  High variance detected! ({variance:.2f}s)")
        
        return {
            "test_type": "initialization",
            "results": init_results,
            "summary": {
                "successful_count": len(successful_inits),
                "average_time": avg_time if successful_inits else None,
                "variance": variance if successful_inits else None
            }
        }
    
    def run_turn_processing_tests(self, game: HaystackDnDGame) -> Dict[str, Any]:
        """Test turn processing consistency"""
        print("\n🔍 TURN PROCESSING TESTS")
        print("-" * 50)
        
        test_inputs = [
            "I look around the tavern",
            "I search for clues",
            "I talk to the bartender",
            "I examine the room carefully",
            "I investigate the mysterious door"
        ]
        
        turn_results = []
        
        for i, test_input in enumerate(test_inputs):
            print(f"\n📝 Turn Test {i+1}/{len(test_inputs)}: '{test_input}'")
            
            try:
                start_time = time.time()
                response = game.play_turn(test_input)
                turn_time = time.time() - start_time
                
                turn_results.append({
                    "test_number": i + 1,
                    "input": test_input,
                    "success": True,
                    "turn_time": turn_time,
                    "response_length": len(response),
                    "enhanced_processing": game._should_use_enhanced_processing(test_input)
                })
                
                print(f"  ✅ Processed in {turn_time:.2f}s")
                print(f"  📏 Response: {len(response)} chars")
                print(f"  🔧 Enhanced: {game._should_use_enhanced_processing(test_input)}")
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                turn_results.append({
                    "test_number": i + 1,
                    "input": test_input,
                    "success": False,
                    "error": str(e),
                    "turn_time": None
                })
        
        # Analyze turn processing
        successful_turns = [r for r in turn_results if r["success"]]
        if successful_turns:
            times = [r["turn_time"] for r in successful_turns]
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            variance = max_time - min_time
            
            enhanced_turns = [r for r in successful_turns if r["enhanced_processing"]]
            simple_turns = [r for r in successful_turns if not r["enhanced_processing"]]
            
            print(f"\n📊 TURN PROCESSING SUMMARY:")
            print(f"  Successful: {len(successful_turns)}/{len(test_inputs)}")
            print(f"  Average time: {avg_time:.2f}s")
            print(f"  Range: {min_time:.2f}s - {max_time:.2f}s")
            print(f"  Variance: {variance:.2f}s")
            print(f"  Enhanced turns: {len(enhanced_turns)}")
            print(f"  Simple turns: {len(simple_turns)}")
            
            if enhanced_turns:
                enhanced_avg = sum(r["turn_time"] for r in enhanced_turns) / len(enhanced_turns)
                print(f"  Enhanced avg: {enhanced_avg:.2f}s")
            
            if simple_turns:
                simple_avg = sum(r["turn_time"] for r in simple_turns) / len(simple_turns)
                print(f"  Simple avg: {simple_avg:.2f}s")
            
            if variance > 2.0:
                print(f"  ⚠️  High turn variance detected! ({variance:.2f}s)")
        
        return {
            "test_type": "turn_processing",
            "results": turn_results,
            "summary": {
                "successful_count": len(successful_turns),
                "average_time": avg_time if successful_turns else None,
                "variance": variance if successful_turns else None,
                "enhanced_count": len(enhanced_turns) if successful_turns else 0,
                "simple_count": len(simple_turns) if successful_turns else 0
            }
        }
    
    def run_orchestrator_tests(self) -> Dict[str, Any]:
        """Test orchestrator consistency"""
        print("\n🔍 ORCHESTRATOR TESTS")
        print("-" * 50)
        
        orchestrator_results = []
        
        # Test orchestrator creation multiple times
        for i in range(3):
            print(f"\n📝 Orchestrator Test {i+1}/3")
            
            try:
                start_time = time.time()
                orchestrator = create_full_haystack_orchestrator(debug_mode=True)
                creation_time = time.time() - start_time
                
                # Test status
                status = orchestrator.get_pipeline_status()
                
                orchestrator_results.append({
                    "test_number": i + 1,
                    "success": True,
                    "creation_time": creation_time,
                    "pipelines_enabled": status.get("pipelines_enabled", False),
                    "pipeline_count": len(status.get("available_pipelines", [])),
                    "agent_count": len(status.get("available_agents", []))
                })
                
                print(f"  ✅ Created in {creation_time:.2f}s")
                print(f"  🔧 Pipelines: {len(status.get('available_pipelines', []))}")
                print(f"  🤖 Agents: {len(status.get('available_agents', []))}")
                
                # Clean up
                del orchestrator
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                orchestrator_results.append({
                    "test_number": i + 1,
                    "success": False,
                    "error": str(e),
                    "creation_time": None
                })
        
        successful_orch = [r for r in orchestrator_results if r["success"]]
        if successful_orch:
            times = [r["creation_time"] for r in successful_orch]
            avg_time = sum(times) / len(times)
            variance = max(times) - min(times)
            
            print(f"\n📊 ORCHESTRATOR SUMMARY:")
            print(f"  Successful: {len(successful_orch)}/3")
            print(f"  Average time: {avg_time:.2f}s")
            print(f"  Variance: {variance:.2f}s")
            
            if variance > 1.0:
                print(f"  ⚠️  High orchestrator variance! ({variance:.2f}s)")
        
        return {
            "test_type": "orchestrator",
            "results": orchestrator_results,
            "summary": {
                "successful_count": len(successful_orch),
                "average_time": avg_time if successful_orch else None,
                "variance": variance if successful_orch else None
            }
        }
    
    def run_memory_tests(self) -> Dict[str, Any]:
        """Test memory usage patterns"""
        print("\n🔍 MEMORY USAGE TESTS")
        print("-" * 50)
        
        try:
            import psutil
            process = psutil.Process()
            
            # Baseline memory
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            print(f"📊 Baseline memory: {baseline_memory:.1f} MB")
            
            # Test memory during game operations
            print("\n📝 Creating game instance...")
            start_memory = process.memory_info().rss / 1024 / 1024
            game = HaystackDnDGame(debug_mode=True)
            post_init_memory = process.memory_info().rss / 1024 / 1024
            
            print(f"  Memory after init: {post_init_memory:.1f} MB (+{post_init_memory - start_memory:.1f} MB)")
            
            # Test memory during turns
            print("\n📝 Processing turns...")
            for i in range(5):
                game.play_turn(f"Test action {i+1}")
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  Turn {i+1} memory: {current_memory:.1f} MB")
            
            final_memory = process.memory_info().rss / 1024 / 1024
            total_increase = final_memory - baseline_memory
            
            print(f"\n📊 MEMORY SUMMARY:")
            print(f"  Total increase: {total_increase:.1f} MB")
            print(f"  Init overhead: {post_init_memory - start_memory:.1f} MB")
            
            if total_increase > 100:
                print(f"  ⚠️  High memory usage! ({total_increase:.1f} MB)")
            
            del game
            
            return {
                "test_type": "memory",
                "baseline_mb": baseline_memory,
                "post_init_mb": post_init_memory,
                "final_mb": final_memory,
                "total_increase_mb": total_increase
            }
            
        except ImportError:
            print("  ⚠️  psutil not available - skipping memory tests")
            return {"test_type": "memory", "skipped": True}
        except Exception as e:
            print(f"  ❌ Memory test failed: {e}")
            return {"test_type": "memory", "error": str(e)}
    
    def run_debug_comparison_test(self) -> Dict[str, Any]:
        """Compare debug vs non-debug performance"""
        print("\n🔍 DEBUG MODE COMPARISON")
        print("-" * 50)
        
        results = {"debug": [], "normal": []}
        
        for mode in ["normal", "debug"]:
            print(f"\n📝 Testing {mode.upper()} mode...")
            
            # Set environment
            if mode == "debug":
                os.environ["HAYSTACK_DND_DEBUG"] = "true"
                debug_mode = True
            else:
                os.environ["HAYSTACK_DND_DEBUG"] = "false"
                debug_mode = False
            
            try:
                # Test initialization
                start_time = time.time()
                game = HaystackDnDGame(debug_mode=debug_mode)
                init_time = time.time() - start_time
                
                # Test a few turns
                turn_times = []
                for i in range(3):
                    turn_start = time.time()
                    game.play_turn(f"Test action {i+1}")
                    turn_time = time.time() - turn_start
                    turn_times.append(turn_time)
                
                avg_turn_time = sum(turn_times) / len(turn_times)
                
                results[mode] = {
                    "init_time": init_time,
                    "avg_turn_time": avg_turn_time,
                    "total_time": init_time + sum(turn_times)
                }
                
                print(f"  Init: {init_time:.2f}s")
                print(f"  Avg turn: {avg_turn_time:.2f}s")
                print(f"  Total: {results[mode]['total_time']:.2f}s")
                
                del game
                
            except Exception as e:
                print(f"  ❌ {mode} mode failed: {e}")
                results[mode] = {"error": str(e)}
        
        # Compare results
        if "error" not in results["debug"] and "error" not in results["normal"]:
            debug_total = results["debug"]["total_time"]
            normal_total = results["normal"]["total_time"]
            overhead = debug_total - normal_total
            overhead_percent = (overhead / normal_total) * 100
            
            print(f"\n📊 COMPARISON SUMMARY:")
            print(f"  Normal mode: {normal_total:.2f}s")
            print(f"  Debug mode: {debug_total:.2f}s")
            print(f"  Debug overhead: {overhead:.2f}s ({overhead_percent:.1f}%)")
            
            if overhead_percent > 50:
                print(f"  ⚠️  High debug overhead! ({overhead_percent:.1f}%)")
        
        return {
            "test_type": "debug_comparison",
            "results": results
        }
    
    def generate_debug_report(self, all_results: List[Dict[str, Any]]):
        """Generate comprehensive debug report"""
        print("\n" + "=" * 70)
        print("🐛 COMPREHENSIVE DEBUG REPORT")
        print("=" * 70)
        
        # System info
        print(f"🖥️  System: Python {sys.version.split()[0]}")
        print(f"📁 Working directory: {os.getcwd()}")
        print(f"🕐 Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test summary
        total_tests = len(all_results)
        failed_tests = len([r for r in all_results if r.get("summary", {}).get("successful_count", 1) == 0])
        
        print(f"\n📊 OVERALL SUMMARY:")
        print(f"  Total test suites: {total_tests}")
        print(f"  Failed test suites: {failed_tests}")
        
        # Identify issues
        issues = []
        
        for result in all_results:
            test_type = result.get("test_type", "unknown")
            summary = result.get("summary", {})
            
            if summary.get("variance", 0) > 1.0:
                issues.append(f"High variance in {test_type}: {summary['variance']:.2f}s")
            
            if summary.get("successful_count", 1) == 0:
                issues.append(f"All {test_type} tests failed")
        
        if issues:
            print(f"\n⚠️  IDENTIFIED ISSUES:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print(f"\n✅ No major issues detected")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"  • Check log files: haystack_dnd_debug.log, pipeline_orchestrator_debug.log")
        print(f"  • Monitor system resources during game operation")
        print(f"  • Test with different environment configurations")
        
        # Save detailed results
        try:
            import json
            with open("debug_runtime_results.json", "w") as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"  • Detailed results saved to: debug_runtime_results.json")
        except Exception as e:
            print(f"  • Could not save results: {e}")


def main():
    """Run comprehensive debug runtime tests"""
    print("🐛 HAYSTACK D&D GAME - DEBUG RUNTIME TESTER")
    print("=" * 70)
    print("This tool helps identify runtime inconsistencies and performance issues.")
    print("Debug logs will be written to haystack_dnd_debug.log and pipeline_orchestrator_debug.log")
    print()
    
    tester = DebugRuntimeTester()
    all_results = []
    
    try:
        # Run all test suites
        all_results.append(tester.run_initialization_tests())
        
        # Create a game instance for turn tests
        print("\n🔧 Creating game instance for turn tests...")
        test_game = HaystackDnDGame(debug_mode=True)
        all_results.append(tester.run_turn_processing_tests(test_game))
        del test_game
        
        all_results.append(tester.run_orchestrator_tests())
        all_results.append(tester.run_memory_tests())
        all_results.append(tester.run_debug_comparison_test())
        
        # Generate final report
        tester.generate_debug_report(all_results)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        logging.exception("Unexpected error in debug tester")
    
    print(f"\n🏁 Debug testing completed!")


if __name__ == "__main__":
    main()
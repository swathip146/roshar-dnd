#!/usr/bin/env python3
"""
Test Runner for D&D Assistant
Provides easy way to run all tests with proper Python path setup
"""
import os
import sys
import subprocess

def main():
    """Run tests with proper Python path setup"""
    # Add project root to Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.environ['PYTHONPATH'] = project_root + ':' + os.environ.get('PYTHONPATH', '')
    
    print("🧪 D&D Assistant Test Runner")
    print("=" * 40)
    
    # Available test commands
    test_commands = {
        '1': ('Smoke Tests', ['python', 'tests/test_smoke.py']),
        '2': ('Unit Tests', ['python', '-m', 'pytest', 'tests/unit/', '-v']),
        '3': ('Integration Tests', ['python', '-m', 'pytest', 'tests/integration/', '-v']), 
        '4': ('All Tests', ['python', '-m', 'pytest', 'tests/', '-v']),
        '5': ('Character Manager Unit Test', ['python', 'tests/unit/test_character_manager.py']),
        '6': ('Complete Workflow Test', ['python', 'tests/integration/test_complete_dnd_workflow.py']),
        '7': ('Agent Interactions Test', ['python', 'tests/integration/test_agent_interactions.py'])
    }
    
    print("Available test options:")
    for key, (name, _) in test_commands.items():
        print(f"  {key}. {name}")
    print()
    
    choice = input("Select test to run (1-7) or 'all' for all tests: ").strip()
    
    if choice == 'all':
        print("Running all tests...")
        for key, (name, cmd) in test_commands.items():
            print(f"\n🔄 Running {name}...")
            try:
                result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✅ {name} - PASSED")
                else:
                    print(f"❌ {name} - FAILED")
                    print(f"Error: {result.stderr}")
            except Exception as e:
                print(f"❌ {name} - ERROR: {e}")
    
    elif choice in test_commands:
        name, cmd = test_commands[choice]
        print(f"🔄 Running {name}...")
        
        try:
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
            print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            if result.returncode == 0:
                print(f"✅ {name} - PASSED")
            else:
                print(f"❌ {name} - FAILED (exit code: {result.returncode})")
                
        except Exception as e:
            print(f"❌ Error running {name}: {e}")
    
    else:
        print("Invalid choice. Please run again and select 1-7 or 'all'.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Debug script to test option extraction from scenario text
"""
import re
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

def extract_and_store_options_debug(scenario_text: str):
    """Debug version of the option extraction method"""
    print("=" * 60)
    print("DEBUGGING OPTION EXTRACTION")
    print("=" * 60)
    print(f"Input scenario text ({len(scenario_text)} chars):")
    print("-" * 40)
    print(repr(scenario_text))
    print("-" * 40)
    print("Actual text:")
    print(scenario_text)
    print("-" * 40)
    
    options = []
    lines = scenario_text.split('\n')
    print(f"Split into {len(lines)} lines:")
    
    # Look for multiple patterns of numbered options
    patterns = [
        (r'^\s*\*\*(\d+)\.\s*(.*?)\*\*\s*-?\s*(.*?)$', "**1. Title** - description"),
        (r'^\s*(\d+)\.\s*\*\*(.*?)\*\*\s*-\s*(.*?)$', "1. **Title** - description"),
        (r'^\s*\*\*(\d+)\.\s*(.*?):\*\*\s*(.*?)$', "**1. Title:** description"),
        (r'^\s*(\d+)\.\s*(.*?)$', "Simple 1. description")
    ]
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        print(f"Line {i}: {repr(line)} -> stripped: {repr(line_stripped)}")
        
        if not line_stripped:
            print("  -> Empty line, skipping")
            continue
            
        for j, (pattern, description) in enumerate(patterns):
            print(f"  -> Testing pattern {j} ({description}): {pattern}")
            match = re.match(pattern, line_stripped)
            if match:
                groups = match.groups()
                print(f"     ✅ MATCH! Groups: {groups}")
                if len(groups) == 3:
                    num, title, desc = groups
                    if desc.strip():
                        option = f"{num}. {title.strip()} - {desc.strip()}"
                    else:
                        option = f"{num}. {title.strip()}"
                    options.append(option)
                    print(f"     -> Added option: {repr(option)}")
                elif len(groups) == 2:
                    num, desc = groups
                    option = f"{num}. {desc.strip()}"
                    options.append(option)
                    print(f"     -> Added option: {repr(option)}")
                break
            else:
                print(f"     ❌ No match")
        print()
    
    print("=" * 60)
    print(f"FINAL RESULT: {len(options)} options extracted")
    for i, option in enumerate(options):
        print(f"  {i+1}: {repr(option)}")
    print("=" * 60)
    
    return options

def test_sample_scenarios():
    """Test with various sample scenario formats"""
    
    # Test with different possible formats
    test_scenarios = [
        # Format 1: **Number. Title** - Description 
        """The party stands at a crossroads in the dark forest.

**1. Take the Left Path** - Head deeper into the mysterious woods
**2. Take the Right Path** - Follow the moonlit trail toward the village
**3. Set Up Camp** - Rest here and wait for dawn
**4. Investigate the Strange Sounds** - Move toward the eerie noises""",
        
        # Format 2: Number. **Title** - Description
        """You encounter a group of bandits blocking the road.

1. **Attack** - Draw weapons and fight the bandits
2. **Negotiate** - Try to talk your way past them  
3. **Sneak Around** - Attempt to bypass them unseen
4. **Retreat** - Fall back and find another route""",
        
        # Format 3: Simple numbered list
        """The ancient door has three keyholes.

1. Try the silver key
2. Try the bronze key  
3. Try the iron key
4. Search for more clues""",
        
        # Format 4: Mixed formatting
        """The dragon awakens and eyes you suspiciously.

**1. Stealth Check (DC 15)** - Try to sneak past the sleeping dragon
2. **Combat** - Attack the dragon (1 Adult Red Dragon)
**3. Persuasion Check (DC 20):** Attempt to negotiate with the dragon
4. Cast a spell to distract it""",
        
        # Format 5: Error scenario (what might be generated when RAG fails)
        """Error in scenario generation""",
        
        # Format 6: No options
        """The party enters the tavern. There are many patrons drinking and talking loudly."""
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*80}")
        print(f"TEST SCENARIO {i}")
        print('='*80)
        extract_and_store_options_debug(scenario)

if __name__ == "__main__":
    test_sample_scenarios()
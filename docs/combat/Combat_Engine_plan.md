# Plan for DnD Combat Engine
- Plan to use existing DnD game code and combine with the DnD engine wrapper
- The orchestrator checks for combat trigger from the user response and then routes to new Combat pipeline
- Combat pipeline will be Combat initialization -> Combat turns -> Combat End

## Combat Initialization
- Pass game state and scenario info
- Check what are the players, npcs, and other characters involved in the combat
- Deterministically look for all the players and definied npcs in the quest (with proper character data) first and load that character info of them
    - Make sure all the available attacks, spells, weapons, traits etc are assigned to respective character
    - Track if the characters are hostile or friendly
- For undefined npcs or other characters
    - use an LLM call/ deterministic logic to check for the additional number of characters needed for the combat usually from the previous scenario context
    - Create character stat objects for each of those characters
    - Use an LLM call to fill in the character stats for each of the undefined character using RAG calls from available rules and context data 
        - Make sure all the available attacks, spells, weapons, traits etc are also determined for respective character
    - Use a deterministic verification logic to check if all the assigned stats are within dnd game rule expectations and fill in any remaining stats/ items with default fallbacks for each stat
    - Track if the characters are hostile or friendly
- Convert all the character data to the DnD engine Entities for combat purpose.
- Create combat end conditions which will be available for verifying. These could be like all hostile characters dead or incapacitated or unconcious or fled etc. These could also be like some objective is achieved etc
    - Initially this can be simple deterministic end conditions.
    - May need LLM call in future to determine the end conditions.
- Run combat initiative roll using the dnd engine or create method if it doesn't exist in dnd engine

## Combat Turn
- Turns should follow the initiative pattern from the initiative roll
- Determine if it is player characters turn or the npc or other character turn
- For player character turn-
    - Determine the number of actions and bonus actions for the player character
    - Do a user interactive call to ask for their desired action input
    - Verify if the action input is valid based on the game rules - dnd engine? or new logic? (may be implemented later)
        - if invalid, ask user for correct action input or hint for possible action (may be implemented later)
- For npc or other ai controlled characters-
    - Determine the number of actions and bonus actions for the character
    - Use LLM call to determine the character action or bonus action based on the character stats and available actions (This maybe the npc agent we planned to create in the codebase)
        - Add verification tools for the LLM agent to validate its action (for agentic LLM call). 
        - For non agentic LLM, use verification logic we have for the player. If invalid, then trigger the LLM call again with hints for the actions.
- if valid action, use dnd engine to run the combat action and update the stats
- Complete all the character's actions and bonus actions to complete the character turn
- Update the character entity stats. Any dead or incapacitated characters should be marked accordingly. For incapacited characters include how many Combat rounds
- Check if the combat is over or Keep proceeding till the combat is over. Update combat round counter.

## Combat End
- Update all the characters stats, items, inventory etc. Convert the dnd engines entities back to our character custom state tracker.
- Update the game state. Description the end to the user and trigger the next scenario.
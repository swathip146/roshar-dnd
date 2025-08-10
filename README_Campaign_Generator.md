# D&D Campaign Generator

A RAG-powered campaign generator that creates comprehensive D&D campaigns by leveraging existing campaign knowledge, rules, and lore from your document collection.

## Features

- **RAG-Enhanced Generation**: Uses your existing D&D document collection to inform campaign creation
- **Campaign Refinement**: Iteratively improve campaigns with user feedback
- **Template-Based Structure**: Generates campaigns with consistent, comprehensive structure
- **Interactive Interface**: Command-line interface for easy campaign creation
- **Save/Load Functionality**: Persist campaigns to JSON files
- **Campaign Suggestions**: Get inspired with AI-generated campaign ideas

## Prerequisites

1. **Qdrant Vector Database**: Must be running and accessible
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

2. **Claude Integration**: Requires Apple GenAI library with Claude access
   ```bash
   # Make sure hwtgenielib is installed and configured
   ```

3. **Document Collection**: Your D&D documents must be indexed in Qdrant
   - Use `pdf_converter.py` to index campaign PDFs, rules, and lore

## Installation

The campaign generator uses the existing RAG system. Ensure all dependencies are installed:

```bash
pip install farm-haystack qdrant-client sentence-transformers qdrant-haystack
# Claude integration via hwtgenielib (Apple GenAI)
```

## Usage

### Interactive Mode

Run the interactive campaign generator:

```bash
python campaign_generator.py
```

Available commands:
- `generate <prompt>` - Create a new campaign
- `refine <prompt>` - Refine the current campaign
- `suggestions [theme]` - Get campaign suggestions
- `summary` - Show current campaign summary
- `save <filename>` - Save campaign to JSON
- `load <filename>` - Load campaign from JSON
- `quit` - Exit

### Programmatic Usage

```python
from campaign_generator import CampaignGenerator

# Initialize generator
generator = CampaignGenerator(collection_name="dnd_documents", verbose=True)

# Generate a campaign
campaign = generator.generate_campaign("A horror campaign in a haunted mansion")

if "error" not in campaign:
    print(f"Generated: {campaign['title']}")
    print(generator.display_campaign_summary())

# Refine the campaign
refined = generator.refine_campaign("Add more investigation elements")

# Save the campaign
generator.save_campaign("my_campaign.json")
```

## Campaign Structure

Each generated campaign includes:

```json
{
  "title": "Campaign Name",
  "theme": "Main theme/genre",
  "setting": "Campaign setting",
  "level_range": "Character levels (e.g., 1-5)",
  "duration": "Expected session count",
  "overview": "Brief campaign summary",
  "background": "Rich world background",
  "main_plot": "Detailed storyline",
  "key_npcs": [
    {
      "name": "NPC Name",
      "role": "Their role",
      "description": "Character description",
      "motivation": "What drives them"
    }
  ],
  "locations": [
    {
      "name": "Location Name",
      "type": "Location type",
      "description": "Detailed description",
      "significance": "Plot importance"
    }
  ],
  "encounters": [
    {
      "title": "Encounter Name",
      "type": "Combat/Social/Exploration",
      "description": "What happens",
      "challenge": "Difficulty level"
    }
  ],
  "hooks": ["Campaign hook 1", "Campaign hook 2"],
  "rewards": ["Reward type 1", "Reward type 2"],
  "dm_notes": "Running tips and considerations",
  "generated_on": "2024-01-01T00:00:00",
  "user_prompts": ["Original prompt", "Refinements..."]
}
```

## Examples

### Basic Campaign Generation
```bash
# In interactive mode
generate A steampunk campaign with airships and mechanical dungeons
```

### Campaign Refinement
```bash
# After generating a campaign
refine Add more political intrigue and noble houses
refine Include a dragon as the main antagonist
```

### Getting Suggestions
```bash
# General suggestions
suggestions

# Themed suggestions
suggestions horror
suggestions political intrigue
```

## Example Prompts

### Adventure Themes
- "A seafaring campaign with pirates and sea monsters"
- "An urban investigation campaign in a magical Victorian city"
- "A post-apocalyptic campaign in a world where magic has failed"
- "A planar travel campaign exploring different dimensions"

### Specific Elements
- "A campaign focused on court intrigue with competing noble houses"
- "A horror campaign with Lovecraftian elements and sanity mechanics"
- "A sandbox exploration campaign in an uncharted wilderness"
- "A time-travel campaign where players must prevent historical disasters"

### Setting-Specific
- "A campaign set in the Feywild with fey politics and dream logic"
- "An Underdark campaign with drow society and aberrant threats"
- "A desert campaign with ancient ruins and elemental magic"
- "A arctic campaign with survival elements and frost giants"

## How It Works

1. **Context Retrieval**: The generator queries your document collection for relevant campaign structures, lore, and examples
2. **Template-Based Generation**: Uses Claude to create campaigns following a consistent structure
3. **RAG Enhancement**: Incorporates knowledge from existing campaigns to ensure quality and authenticity
4. **Iterative Refinement**: Allows users to refine campaigns while maintaining coherence

## Troubleshooting

### Common Issues

**"RAG agent not available"**
- Ensure Qdrant is running on port 6333
- Check that your document collection exists and contains data

**"Claude not available"**
- Verify hwtgenielib is installed and configured
- Check Apple GenAI credentials and permissions

**"No relevant information"**
- Your document collection may lack campaign examples
- Try using more general prompts
- Consider adding more diverse campaign PDFs to your collection

**JSON parsing errors**
- This usually indicates an issue with Claude's response format
- Try regenerating the campaign or refining your prompt

### Performance Tips

- **Specific Prompts**: More specific prompts generally produce better results
- **Iterative Refinement**: Use refinement to gradually improve campaigns rather than trying to get everything perfect in one generation
- **Document Quality**: Higher quality source documents produce better campaigns

## File Structure

```
campaign_generator.py          # Main campaign generator class
example_campaign_generator.py  # Usage examples and demonstrations
README_Campaign_Generator.md   # This documentation
```

## Integration with Existing Tools

The campaign generator integrates seamlessly with other tools in the project:

- **RAG Agent** (`rag_agent.py`): Provides the core RAG functionality
- **RAG DM Assistant** (`rag_dm_assistant.py`): Can be extended to use generated campaigns
- **PDF Converter** (`pdf_converter.py`): Index new campaign PDFs to improve generation

## Contributing

To improve the campaign generator:

1. Add more diverse campaign PDFs to your document collection
2. Refine the prompt templates in the generator code
3. Extend the campaign structure with additional fields
4. Add specialized generators for specific campaign types

## License

This project uses the same license as the parent D&D RAG system.
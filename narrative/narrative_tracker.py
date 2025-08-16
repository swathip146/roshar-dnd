"""
Narrative Continuity Tracker
Tracks story consistency and narrative elements for D&D campaigns
"""
import time
import re
from typing import Dict, List, Any


class NarrativeContinuityTracker:
    """Enhanced story consistency tracking for narrative continuity"""
    
    def __init__(self):
        self.story_elements = {
            'characters': {},
            'locations': {},
            'plot_threads': {},
            'unresolved_conflicts': []
        }
        self.consistency_score = 1.0
        self.narrative_history = []
    
    def analyze_narrative_consistency(self, new_content: str, context: dict) -> dict:
        """Analyze new content for consistency with established narrative"""
        # Extract entities and themes
        entities = self._extract_entities(new_content)
        themes = self._extract_themes(new_content)
        
        # Check for contradictions
        contradictions = self._check_contradictions(entities, themes)
        
        # Update story elements
        self._update_story_elements(entities, themes)
        
        # Calculate coherence score
        coherence_score = self._calculate_coherence_score()
        
        # Store in history
        self.narrative_history.append({
            'content': new_content,
            'entities': entities,
            'themes': themes,
            'contradictions': contradictions,
            'coherence_score': coherence_score,
            'timestamp': time.time()
        })
        
        return {
            'consistency_score': self.consistency_score,
            'contradictions': contradictions,
            'narrative_coherence': coherence_score,
            'entities_found': entities,
            'themes_identified': themes
        }
    
    def _extract_entities(self, content: str) -> dict:
        """Extract character and location entities from content"""
        entities = {'characters': [], 'locations': [], 'items': []}
        
        # Simple entity extraction patterns
        character_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:says|does|moves|attacks|casts)',
            r'(?:NPC|character|person|being)\s+named\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        location_patterns = [
            r'(?:in|at|near|to|from)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Temple|Castle|Inn|Tavern|Forest|Mountain|Cave|Tower)))',
            r'(?:location|place|area|region)\s+(?:called|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in character_patterns:
            matches = re.findall(pattern, content)
            entities['characters'].extend(matches)
        
        for pattern in location_patterns:
            matches = re.findall(pattern, content)
            entities['locations'].extend(matches)
        
        return entities
    
    def _extract_themes(self, content: str) -> list:
        """Extract narrative themes from content"""
        themes = []
        content_lower = content.lower()
        
        theme_keywords = {
            'conflict': ['battle', 'fight', 'war', 'conflict', 'struggle'],
            'mystery': ['mystery', 'unknown', 'secret', 'hidden', 'investigate'],
            'exploration': ['explore', 'discover', 'journey', 'travel', 'adventure'],
            'magic': ['magic', 'spell', 'enchanted', 'mystical', 'arcane'],
            'social': ['negotiate', 'persuade', 'diplomacy', 'politics', 'alliance']
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                themes.append(theme)
        
        return themes
    
    def _check_contradictions(self, entities: dict, themes: list) -> list:
        """Check for narrative contradictions"""
        contradictions = []
        
        # Check character consistency
        for char in entities.get('characters', []):
            if char in self.story_elements['characters']:
                stored_char = self.story_elements['characters'][char]
                # Simple contradiction check - character appearing in impossible situations
                if stored_char.get('status') == 'dead' and char in entities['characters']:
                    contradictions.append(f"Character {char} appears despite being marked as dead")
        
        return contradictions
    
    def _update_story_elements(self, entities: dict, themes: list):
        """Update tracked story elements"""
        # Update characters
        for char in entities.get('characters', []):
            if char not in self.story_elements['characters']:
                self.story_elements['characters'][char] = {
                    'first_appearance': time.time(),
                    'status': 'alive',
                    'appearances': 1
                }
            else:
                self.story_elements['characters'][char]['appearances'] += 1
        
        # Update locations
        for loc in entities.get('locations', []):
            if loc not in self.story_elements['locations']:
                self.story_elements['locations'][loc] = {
                    'first_mention': time.time(),
                    'visits': 1
                }
            else:
                self.story_elements['locations'][loc]['visits'] += 1
    
    def _calculate_coherence_score(self) -> float:
        """Calculate narrative coherence score"""
        if len(self.narrative_history) < 2:
            return 1.0
        
        # Simple coherence calculation based on entity consistency
        total_elements = 0
        consistent_elements = 0
        
        for char_data in self.story_elements['characters'].values():
            total_elements += 1
            if char_data['appearances'] > 1:  # Character has continuity
                consistent_elements += 1
        
        for loc_data in self.story_elements['locations'].values():
            total_elements += 1
            if loc_data['visits'] > 1:  # Location has continuity
                consistent_elements += 1
        
        return consistent_elements / max(total_elements, 1)
    
    def get_story_summary(self) -> dict:
        """Get summary of current story elements"""
        return {
            'character_count': len(self.story_elements['characters']),
            'location_count': len(self.story_elements['locations']),
            'plot_threads': len(self.story_elements['plot_threads']),
            'unresolved_conflicts': len(self.story_elements['unresolved_conflicts']),
            'consistency_score': self.consistency_score,
            'total_events': len(self.narrative_history)
        }
    
    def clear_history(self):
        """Clear narrative history (useful for new campaigns)"""
        self.narrative_history.clear()
        self.story_elements = {
            'characters': {},
            'locations': {},
            'plot_threads': {},
            'unresolved_conflicts': []
        }
        self.consistency_score = 1.0

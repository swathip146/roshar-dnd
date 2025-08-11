"""
Enhanced Pipeline Components for Modular DM Assistant
Implements error recovery, creative consequence generation, and smart routing
"""
import logging
import time
import json
import random
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class PipelineInterface(ABC):
    """Abstract interface for pipeline components"""
    
    @abstractmethod
    def process(self, query: str, context: Dict = None) -> Dict:
        """Process a query and return result"""
        pass
    
    @abstractmethod
    def validate_result(self, result: Dict) -> bool:
        """Validate if result is acceptable"""
        pass

class CreativeGenerationPipeline(PipelineInterface):
    """Pipeline for creative content generation"""
    
    def __init__(self, llm_generator=None):
        self.llm = llm_generator
        self.fallback_templates = [
            "The story continues as {player} takes action...",
            "As {player} decides to {choice}, the adventure unfolds...",
            "The consequences of {player}'s choice become clear..."
        ]
        self._setup_pipeline()
    
    def _setup_pipeline(self):
        """Setup internal pipeline if LLM is available"""
        self.pipeline = None
        if self.llm:
            try:
                from haystack import Pipeline
                from haystack_pipeline_agent import StringToChatMessages
                
                self.pipeline = Pipeline()
                self.pipeline.add_component("string_to_chat", StringToChatMessages())
                self.pipeline.add_component("chat_generator", self.llm)
                self.pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            except Exception as e:
                logger.warning(f"Failed to setup LLM pipeline: {e}")
                self.pipeline = None
    
    def process(self, query: str, context: Dict = None) -> Dict:
        """Process creative generation request"""
        try:
            if self.pipeline:
                # Use LLM pipeline for generation
                prompt = self._build_creative_prompt(query, context)
                result = self.pipeline.run({"string_to_chat": {"prompt": prompt}})
                
                if "chat_generator" in result and "replies" in result["chat_generator"]:
                    answer = result["chat_generator"]["replies"][0].text
                    return {"answer": answer, "source": "llm_creative"}
                else:
                    # Fallback if pipeline fails
                    return self._generate_from_template(query, context)
            else:
                # Fallback to template-based generation
                return self._generate_from_template(query, context)
        except Exception as e:
            logger.error(f"Creative generation error: {e}")
            return self._generate_from_template(query, context)
    
    def validate_result(self, result: Dict) -> bool:
        """Validate creative generation result"""
        return "answer" in result and len(result["answer"]) > 20
    
    def _build_creative_prompt(self, query: str, context: Dict) -> str:
        """Build creative generation prompt"""
        prompt = "You are a creative D&D storyteller. "
        if context:
            if "player" in context:
                prompt += f"Continue the story for {context['player']}. "
            if "setting" in context:
                prompt += f"Setting: {context['setting']}. "
        prompt += f"Query: {query}\n\nGenerate an engaging narrative response:"
        return prompt
    
    def _generate_from_template(self, query: str, context: Dict) -> Dict:
        """Generate using templates as fallback"""
        template = random.choice(self.fallback_templates)
        player = context.get("player", "the adventurer") if context else "the adventurer"
        choice = context.get("choice", "their decision") if context else "their decision"
        
        result = template.format(player=player, choice=choice)
        return {"answer": result, "source": "template_fallback"}

class FactualRetrievalPipeline(PipelineInterface):
    """Pipeline for factual information retrieval"""
    
    def __init__(self, rag_agent=None):
        self.rag_agent = rag_agent
    
    def process(self, query: str, context: Dict = None) -> Dict:
        """Process factual retrieval request"""
        try:
            if self.rag_agent:
                result = self.rag_agent.query(query)
                return result
            else:
                return {"answer": f"Information about: {query}", "source": "fallback"}
        except Exception as e:
            logger.error(f"Factual retrieval error: {e}")
            return {"error": str(e)}
    
    def validate_result(self, result: Dict) -> bool:
        """Validate factual retrieval result"""
        return "answer" in result and "error" not in result

class RulesQueryPipeline(PipelineInterface):
    """Pipeline for D&D rules queries"""
    
    def __init__(self, rule_agent=None):
        self.rule_agent = rule_agent
        self.static_rules = self._load_static_rules()
    
    def process(self, query: str, context: Dict = None) -> Dict:
        """Process rules query"""
        try:
            if self.rule_agent:
                category = context.get("category", "general") if context else "general"
                result = self.rule_agent.check_rule(query, category)
                return result
            else:
                # Fallback to static rules
                return self._query_static_rules(query)
        except Exception as e:
            logger.error(f"Rules query error: {e}")
            return {"error": str(e)}
    
    def validate_result(self, result: Dict) -> bool:
        """Validate rules query result"""
        return "rule_text" in result or "answer" in result
    
    def _load_static_rules(self) -> Dict[str, str]:
        """Load static rule database"""
        return {
            "advantage": "Roll two d20s and take the higher result",
            "disadvantage": "Roll two d20s and take the lower result",
            "critical_hit": "On a natural 20, double the damage dice",
            "concentration": "Maintain focus on a spell, broken by damage or failed saves",
            "opportunity_attack": "Attack when enemy leaves your reach without disengaging"
        }
    
    def _query_static_rules(self, query: str) -> Dict:
        """Query static rules database"""
        query_lower = query.lower()
        for rule_key, rule_text in self.static_rules.items():
            if rule_key in query_lower:
                return {
                    "rule_text": rule_text,
                    "source": "static_database",
                    "confidence": "medium"
                }
        return {
            "rule_text": f"No specific rule found for: {query}",
            "source": "fallback",
            "confidence": "low"
        }

class HybridCreativeFactualPipeline(PipelineInterface):
    """Pipeline that combines creative and factual approaches"""
    
    def __init__(self, creative_pipeline=None, factual_pipeline=None):
        self.creative_pipeline = creative_pipeline
        self.factual_pipeline = factual_pipeline
    
    def process(self, query: str, context: Dict = None) -> Dict:
        """Process using hybrid approach"""
        try:
            # Try factual first for grounding
            factual_result = None
            if self.factual_pipeline:
                factual_result = self.factual_pipeline.process(query, context)
            
            # Then add creative elements
            creative_result = None
            if self.creative_pipeline:
                # Enhance context with factual information
                enhanced_context = context.copy() if context else {}
                if factual_result and "answer" in factual_result:
                    enhanced_context["factual_context"] = factual_result["answer"]
                
                creative_result = self.creative_pipeline.process(query, enhanced_context)
            
            # Combine results
            return self._combine_results(factual_result, creative_result)
            
        except Exception as e:
            logger.error(f"Hybrid pipeline error: {e}")
            return {"error": str(e)}
    
    def validate_result(self, result: Dict) -> bool:
        """Validate hybrid result"""
        return "answer" in result
    
    def _combine_results(self, factual: Dict, creative: Dict) -> Dict:
        """Combine factual and creative results"""
        if creative and "answer" in creative:
            answer = creative["answer"]
            if factual and "answer" in factual:
                answer = f"{factual['answer']}\n\n{creative['answer']}"
            return {
                "answer": answer,
                "sources": ["factual", "creative"],
                "type": "hybrid"
            }
        elif factual and "answer" in factual:
            return factual
        else:
            return {"answer": "Unable to process query", "type": "fallback"}

class ErrorRecoveryPipeline:
    """Pipeline with multiple fallback strategies"""
    
    def __init__(self):
        self.primary_pipeline = None
        self.fallback_pipelines = []
        self.error_log = []
    
    def set_primary_pipeline(self, pipeline: PipelineInterface):
        """Set the primary pipeline"""
        self.primary_pipeline = pipeline
    
    def add_fallback_pipeline(self, pipeline: PipelineInterface):
        """Add a fallback pipeline"""
        self.fallback_pipelines.append(pipeline)
    
    def process_with_recovery(self, query: str, context: Dict = None) -> Dict:
        """Process with error recovery"""
        # Try primary pipeline
        if self.primary_pipeline:
            try:
                result = self.primary_pipeline.process(query, context)
                if self._validate_result(result):
                    return result
                else:
                    self._log_error("Primary pipeline returned invalid result", result)
            except Exception as e:
                self._log_error("Primary pipeline failed", e)
        
        # Try fallback pipelines
        for i, fallback in enumerate(self.fallback_pipelines):
            try:
                result = fallback.process(query, context)
                if self._validate_result(result):
                    result['fallback_used'] = f"fallback_{i}"
                    result['recovery_level'] = i + 1
                    return result
            except Exception as e:
                self._log_error(f"Fallback {i} failed", e)
                continue
        
        # Final fallback
        return self._generate_apologetic_response(query)
    
    def _validate_result(self, result: Dict) -> bool:
        """Validate if result is acceptable"""
        if not result or "error" in result:
            return False
        
        # Check if result has meaningful content
        if "answer" in result:
            return len(result["answer"].strip()) > 10
        elif "rule_text" in result:
            return len(result["rule_text"].strip()) > 10
        
        return False
    
    def _log_error(self, message: str, error: Any):
        """Log error for analysis"""
        error_entry = {
            "timestamp": time.time(),
            "message": message,
            "error": str(error)
        }
        self.error_log.append(error_entry)
        logger.warning(f"Pipeline error: {message} - {error}")
    
    def _generate_apologetic_response(self, query: str) -> Dict:
        """Generate apologetic response when all pipelines fail"""
        apologies = [
            "I apologize, but I'm having difficulty processing that request right now.",
            "I'm sorry, but I can't provide a proper response to that query at the moment.",
            "Unfortunately, I'm experiencing some technical difficulties with that request."
        ]
        
        return {
            "answer": random.choice(apologies) + f" Your query was: '{query[:50]}...'",
            "type": "apologetic_fallback",
            "recovery_level": "final"
        }
    
    def get_error_summary(self) -> Dict:
        """Get summary of recent errors"""
        recent_errors = [e for e in self.error_log if time.time() - e["timestamp"] < 3600]
        return {
            "total_errors": len(self.error_log),
            "recent_errors": len(recent_errors),
            "error_types": list(set(e["message"] for e in recent_errors))
        }

class CreativeConsequencePipeline:
    """Specialized pipeline for choice consequence generation"""
    
    def __init__(self, llm_generator=None):
        self.llm = llm_generator
        self.context_builder = ChoiceContextBuilder()
        self._setup_pipeline()
        
    def _setup_pipeline(self):
        """Setup internal pipeline if LLM is available"""
        self.pipeline = None
        if self.llm:
            try:
                from haystack import Pipeline
                from haystack_pipeline_agent import StringToChatMessages
                
                self.pipeline = Pipeline()
                self.pipeline.add_component("string_to_chat", StringToChatMessages())
                self.pipeline.add_component("chat_generator", self.llm)
                self.pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            except Exception as e:
                logger.warning(f"Failed to setup LLM pipeline: {e}")
                self.pipeline = None
        
    def generate_consequence(self, choice: str, game_state: Dict, player: str) -> str:
        """Generate creative consequence for player choice"""
        try:
            # Build rich context
            context = self.context_builder.build_context(choice, game_state, player)
            
            # Use LLM pipeline if available
            if self.pipeline:
                prompt = self._build_creative_consequence_prompt(context)
                result = self.pipeline.run({"string_to_chat": {"prompt": prompt}})
                
                if "chat_generator" in result and "replies" in result["chat_generator"]:
                    answer = result["chat_generator"]["replies"][0].text
                    return self._format_consequence(answer)
                else:
                    # Fallback to template-based generation
                    return self._generate_template_consequence(context)
            else:
                # Fallback to template-based generation
                return self._generate_template_consequence(context)
                
        except Exception as e:
            logger.error(f"Creative consequence generation error: {e}")
            return self._generate_fallback_consequence(choice, player)
    
    def _build_creative_consequence_prompt(self, context: Dict) -> str:
        """Build creative consequence prompt"""
        return f"""
You are narrating the immediate consequence of a player's choice in a D&D adventure.

Player: {context['player']}
Choice: {context['choice']}
Current situation: {context['situation']}
Campaign setting: {context['setting']}
Recent events: {context.get('recent_events', 'Unknown')}

Write 2-3 engaging sentences describing what happens immediately after this choice.
Make it dramatic, appropriate for the setting, and advance the story naturally.
Focus on the immediate outcome and how it affects the character or party.
Do not end with questions - provide concrete results.
"""
    
    def _format_consequence(self, result: str) -> str:
        """Format the generated consequence"""
        # Clean up the result
        consequence = result.strip()
        
        # Ensure it ends properly
        if not consequence.endswith(('.', '!', '?')):
            consequence += '.'
        
        return consequence
    
    def _generate_template_consequence(self, context: Dict) -> str:
        """Generate consequence using templates"""
        templates = [
            "As {player} {action}, {outcome}. {effect}",
            "{player}'s decision to {action} results in {outcome}. {effect}",
            "The moment {player} {action}, {outcome} unfolds. {effect}"
        ]
        
        actions = ["acts boldly", "moves forward", "takes action", "makes their choice"]
        outcomes = ["the situation shifts", "new possibilities emerge", "unexpected events unfold"]
        effects = ["The adventure continues.", "The stakes have changed.", "New challenges await."]
        
        template = random.choice(templates)
        return template.format(
            player=context['player'],
            action=random.choice(actions),
            outcome=random.choice(outcomes),
            effect=random.choice(effects)
        )
    
    def _generate_fallback_consequence(self, choice: str, player: str) -> str:
        """Generate minimal fallback consequence"""
        return f"{player} chose: {choice}. The story continues as consequences unfold from this decision."

class ChoiceContextBuilder:
    """Build rich context for choice consequence generation"""
    
    def build_context(self, choice: str, game_state: Dict, player: str) -> Dict:
        """Build comprehensive context for consequence generation"""
        context = {
            'player': player,
            'choice': choice,
            'situation': 'ongoing adventure',
            'setting': 'fantasy realm'
        }
        
        # Extract information from game state
        if game_state:
            # Location information
            if 'session' in game_state and 'location' in game_state['session']:
                context['location'] = game_state['session']['location']
                context['situation'] = f"at {context['location']}"
            
            # Recent events
            if 'session' in game_state and 'events' in game_state['session']:
                events = game_state['session']['events']
                if events:
                    context['recent_events'] = '. '.join(events[-3:])  # Last 3 events
            
            # Story arc
            if 'story_arc' in game_state:
                context['setting'] = game_state['story_arc']
            
            # Party information
            if 'players' in game_state:
                party_size = len(game_state['players'])
                context['party_info'] = f"party of {party_size}"
        
        return context

class SmartPipelineRouter:
    """Route queries to optimal pipeline based on intent and content type"""
    
    def __init__(self):
        self.pipelines = {}
        self.intent_classifier = None
        self.fallback_pipeline = None
    
    def register_pipeline(self, intent: str, pipeline: PipelineInterface):
        """Register a pipeline for specific intent"""
        self.pipelines[intent] = pipeline
    
    def set_intent_classifier(self, classifier):
        """Set the intent classifier"""
        self.intent_classifier = classifier
    
    def set_fallback_pipeline(self, pipeline: PipelineInterface):
        """Set fallback pipeline"""
        self.fallback_pipeline = pipeline
    
    def route_query(self, query: str, context: Dict = None) -> Dict:
        """Route query to optimal pipeline"""
        try:
            # Classify intent
            if self.intent_classifier:
                intent = self.intent_classifier.classify(query, context)
            else:
                intent = self._simple_intent_classification(query)
            
            # Route to appropriate pipeline
            if intent in self.pipelines:
                logger.debug(f"Routing query to {intent} pipeline")
                result = self.pipelines[intent].process(query, context)
                result['pipeline_used'] = intent
                return result
            elif self.fallback_pipeline:
                logger.debug("Using fallback pipeline")
                result = self.fallback_pipeline.process(query, context)
                result['pipeline_used'] = 'fallback'
                return result
            else:
                return {"error": "No suitable pipeline found", "intent": intent}
                
        except Exception as e:
            logger.error(f"Pipeline routing error: {e}")
            return {"error": str(e)}
    
    def _simple_intent_classification(self, query: str) -> str:
        """Simple intent classification fallback"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['generate', 'create', 'story', 'scenario']):
            return 'creative'
        elif any(word in query_lower for word in ['rule', 'how does', 'mechanics']):
            return 'rules'
        elif any(word in query_lower for word in ['what is', 'explain', 'define']):
            return 'factual'
        else:
            return 'hybrid'
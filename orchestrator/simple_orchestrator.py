"""
Simple Orchestrator - Stage 2 Week 7-8
Basic request routing with extension hooks for future Stage 3+ enhancements
"""

from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
import logging


@dataclass
class GameRequest:
    """Basic request structure for game operations"""
    request_type: str  # 'scenario', 'action', 'dice_roll', etc.
    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


@dataclass
class GameResponse:
    """Standard response structure"""
    success: bool
    data: Dict[str, Any]
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SimpleOrchestrator:
    """
    Basic orchestrator with extension hooks for future enhancements
    Follows "start simple and expand" philosophy from progressive plan
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Extension points for Stage 3+ - Saga Manager, Decision Logging
        self.pre_hooks: List[Callable[[GameRequest], GameRequest]] = []  # For saga manager
        self.post_hooks: List[Callable[[GameResponse], GameResponse]] = []  # For decision logging
        
        # Simple routing table - expandable in future stages
        self.handlers: Dict[str, Callable[[GameRequest], GameResponse]] = {}
        
        # Initialize basic handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default request handlers"""
        self.handlers.update({
            'scenario': self._handle_scenario_request,
            'dice_roll': self._handle_dice_request,
            'game_state': self._handle_state_request,
        })
    
    def register_handler(self, request_type: str, handler: Callable[[GameRequest], GameResponse]):
        """Register a new request handler - extensibility for Stage 3+"""
        self.handlers[request_type] = handler
        self.logger.info(f"Registered handler for request type: {request_type}")
    
    def add_pre_hook(self, hook: Callable[[GameRequest], GameRequest]):
        """Add pre-processing hook - for Stage 3 saga manager"""
        self.pre_hooks.append(hook)
        self.logger.info("Added pre-processing hook")
    
    def add_post_hook(self, hook: Callable[[GameResponse], GameResponse]):
        """Add post-processing hook - for Stage 3 decision logging"""
        self.post_hooks.append(hook)
        self.logger.info("Added post-processing hook")
    
    def process_request(self, request: GameRequest) -> GameResponse:
        """
        Main orchestration method with hook system
        Future stages will enhance this with saga management and logging
        """
        try:
            # Pre-processing hooks (Stage 3+: saga context injection)
            processed_request = request
            for hook in self.pre_hooks:
                processed_request = hook(processed_request)
            
            # Route to appropriate handler
            handler = self.handlers.get(processed_request.request_type)
            if not handler:
                return GameResponse(
                    success=False,
                    data={"error": f"Unknown request type: {processed_request.request_type}"}
                )
            
            # Execute handler
            response = handler(processed_request)
            
            # Post-processing hooks (Stage 3+: decision logging, state updates)
            processed_response = response
            for hook in self.post_hooks:
                processed_response = hook(processed_response)
            
            return processed_response
            
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            return GameResponse(
                success=False,
                data={"error": str(e), "request_type": request.request_type}
            )
    
    # Default handlers - simple implementations for Stage 2
    
    def _handle_scenario_request(self, request: GameRequest) -> GameResponse:
        """Handle scenario generation requests"""
        # Stage 2: Simple passthrough - Stage 3+ will integrate saga manager
        return GameResponse(
            success=True,
            data={
                "message": "Scenario request received - integrate with RAGScenarioGenerator",
                "request_data": request.data
            }
        )
    
    def _handle_dice_request(self, request: GameRequest) -> GameResponse:
        """Handle dice rolling requests"""
        # Stage 2: Simple passthrough - Stage 3+ will add complex dice mechanics
        return GameResponse(
            success=True,
            data={
                "message": "Dice request received - integrate with DiceRoller",
                "request_data": request.data
            }
        )
    
    def _handle_state_request(self, request: GameRequest) -> GameResponse:
        """Handle game state requests"""
        # Stage 2: Simple passthrough - Stage 3+ will add persistent state
        return GameResponse(
            success=True,
            data={
                "message": "State request received - Stage 3+ persistent state",
                "request_data": request.data
            }
        )
    
    def get_available_handlers(self) -> List[str]:
        """Get list of available request types"""
        return list(self.handlers.keys())


# Convenience factory function for Stage 2 simplicity
def create_orchestrator() -> SimpleOrchestrator:
    """Factory function to create configured orchestrator"""
    orchestrator = SimpleOrchestrator()
    
    # Stage 2: Basic setup
    # Stage 3+: Will add saga manager hooks, persistent state, etc.
    
    return orchestrator


# Example usage for Stage 2 testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create orchestrator
    orchestrator = create_orchestrator()
    
    # Test basic functionality
    test_request = GameRequest(
        request_type="scenario",
        data={"theme": "dungeon", "difficulty": "medium"}
    )
    
    response = orchestrator.process_request(test_request)
    print(f"Response: {response}")
    
    # Show available handlers
    print(f"Available handlers: {orchestrator.get_available_handlers()}")
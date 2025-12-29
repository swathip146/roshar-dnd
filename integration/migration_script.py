"""
Migration script for transitioning from legacy orchestrator to native Haystack pipeline.
This script demonstrates Phase C: Integration and legacy cleanup.
"""

import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.haystack_native_orchestrator import create_native_haystack_orchestrator
from orchestrator.pipeline_integration import PipelineOrchestrator  # Legacy orchestrator
from components.shared_contract import RequestDTO, GameResponseDTO

class MigrationManager:
    """
    Manages the migration from legacy to native Haystack orchestrator.
    Provides A/B testing and gradual rollout capabilities.
    """
    
    def __init__(self, 
                 game_engine=None,
                 character_manager=None,
                 policy_engine=None,
                 document_store=None,
                 migration_percentage: float = 0.0):
        """
        Initialize migration manager.
        
        Args:
            game_engine: GameEngine instance
            character_manager: CharacterManager instance
            policy_engine: PolicyEngine instance
            document_store: Document store instance
            migration_percentage: Percentage of requests to route to native pipeline (0.0-1.0)
        """
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.policy_engine = policy_engine
        self.document_store = document_store
        self.migration_percentage = migration_percentage
        
        # Create both orchestrators
        self.native_orchestrator = self._create_native_orchestrator()
        self.legacy_orchestrator = self._create_legacy_orchestrator()
        
        # Migration tracking
        self.native_requests = 0
        self.legacy_requests = 0
        self.error_counts = {"native": 0, "legacy": 0}
        self.performance_data = {"native": [], "legacy": []}
    
    def _create_native_orchestrator(self):
        """Create native Haystack orchestrator"""
        try:
            return create_native_haystack_orchestrator(
                game_engine=self.game_engine,
                character_manager=self.character_manager,
                policy_engine=self.policy_engine,
                document_store=self.document_store,
                pipeline_type="phase1",
                use_adaptive_routing=True
            )
        except Exception as e:
            print(f"Warning: Could not create native orchestrator: {e}")
            return None
    
    def _create_legacy_orchestrator(self):
        """Create legacy orchestrator for comparison"""
        try:
            return PipelineOrchestrator(
                game_engine=self.game_engine,
                character_manager=self.character_manager,
                policy_engine=self.policy_engine,
                shared_document_store=self.document_store
            )
        except Exception as e:
            print(f"Warning: Could not create legacy orchestrator: {e}")
            return None
    
    def process_request(self, request: RequestDTO) -> GameResponseDTO:
        """
        Process request through appropriate orchestrator based on migration percentage.
        
        Args:
            request: Game request to process
            
        Returns:
            Game response from selected orchestrator
        """
        import random
        
        # Determine which orchestrator to use
        use_native = random.random() < self.migration_percentage
        
        if use_native and self.native_orchestrator:
            return self._process_with_native(request)
        elif self.legacy_orchestrator:
            return self._process_with_legacy(request)
        else:
            # Fallback response if neither orchestrator is available
            return {
                "scene": "System temporarily unavailable. Please try again.",
                "choices": [{"text": "Continue", "action": "continue"}],
                "success": False
            }
    
    def _process_with_native(self, request: RequestDTO) -> GameResponseDTO:
        """Process request with native orchestrator and track metrics"""
        import time
        
        start_time = time.time()
        try:
            response = self.native_orchestrator.process_request(request)
            processing_time = time.time() - start_time
            
            self.native_requests += 1
            self.performance_data["native"].append(processing_time)
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.error_counts["native"] += 1
            self.performance_data["native"].append(processing_time)
            
            print(f"Native orchestrator error: {e}")
            
            # Fallback to legacy if available
            if self.legacy_orchestrator:
                return self._process_with_legacy(request)
            else:
                return {
                    "scene": f"Native pipeline error: {str(e)}",
                    "choices": [{"text": "Continue", "action": "continue"}],
                    "success": False
                }
    
    def _process_with_legacy(self, request: RequestDTO) -> GameResponseDTO:
        """Process request with legacy orchestrator and track metrics"""
        import time
        
        start_time = time.time()
        try:
            response = self.legacy_orchestrator.process_request(request)
            processing_time = time.time() - start_time
            
            self.legacy_requests += 1
            self.performance_data["legacy"].append(processing_time)
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.error_counts["legacy"] += 1
            self.performance_data["legacy"].append(processing_time)
            
            print(f"Legacy orchestrator error: {e}")
            
            return {
                "scene": f"Legacy pipeline error: {str(e)}",
                "choices": [{"text": "Continue", "action": "continue"}],
                "success": False
            }
    
    def set_migration_percentage(self, percentage: float):
        """Update migration percentage for gradual rollout"""
        self.migration_percentage = max(0.0, min(1.0, percentage))
        print(f"Migration percentage set to: {self.migration_percentage * 100:.1f}%")
    
    def get_migration_stats(self) -> Dict[str, Any]:
        """Get migration statistics and performance comparison"""
        
        def calculate_stats(data):
            if not data:
                return {"avg": 0, "min": 0, "max": 0, "count": 0}
            return {
                "avg": sum(data) / len(data),
                "min": min(data),
                "max": max(data), 
                "count": len(data)
            }
        
        native_stats = calculate_stats(self.performance_data["native"])
        legacy_stats = calculate_stats(self.performance_data["legacy"])
        
        # Calculate performance improvement
        performance_improvement = 0.0
        if legacy_stats["avg"] > 0 and native_stats["avg"] > 0:
            performance_improvement = (legacy_stats["avg"] - native_stats["avg"]) / legacy_stats["avg"] * 100
        
        return {
            "migration_percentage": self.migration_percentage,
            "requests": {
                "native": self.native_requests,
                "legacy": self.legacy_requests,
                "total": self.native_requests + self.legacy_requests
            },
            "errors": {
                "native": self.error_counts["native"],
                "legacy": self.error_counts["legacy"]
            },
            "performance": {
                "native": native_stats,
                "legacy": legacy_stats,
                "improvement_percent": performance_improvement
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def validate_native_pipeline(self) -> Dict[str, Any]:
        """Validate native pipeline configuration"""
        if not self.native_orchestrator:
            return {"valid": False, "error": "Native orchestrator not available"}
        
        return self.native_orchestrator.validate_pipeline()
    
    def migrate_to_native_only(self) -> bool:
        """
        Complete migration to native pipeline only.
        This implements the final cleanup phase.
        """
        try:
            # Validate native pipeline is working
            validation = self.validate_native_pipeline()
            if not validation.get("valid", False):
                print("Native pipeline validation failed - cannot complete migration")
                return False
            
            # Set to 100% native
            self.set_migration_percentage(1.0)
            
            # Deprecate legacy orchestrator
            self.legacy_orchestrator = None
            
            print("✅ Migration completed - now using native Haystack pipeline only")
            print("⚠️  Legacy orchestrator has been deprecated and removed")
            
            return True
            
        except Exception as e:
            print(f"Migration failed: {e}")
            return False

def demonstrate_migration():
    """Demonstrate the migration process step by step"""
    
    print("🚀 Starting Haystack Pipeline Migration Demonstration")
    print("=" * 60)
    
    # Initialize migration manager
    migration_manager = MigrationManager(migration_percentage=0.0)
    
    # Test requests
    test_requests = [
        {
            "player_input": "I want to explore the dungeon",
            "intent": "SCENARIO_CHOICE",
            "confidence": 0.8,
            "flags": {}
        },
        {
            "player_input": "Tell me about dragons", 
            "intent": "RAG_QUERY",
            "confidence": 0.9,
            "flags": {"need_rag": True}
        },
        {
            "player_input": "I try to climb the wall",
            "intent": "SKILL_CHECK",
            "confidence": 0.85,
            "flags": {"need_check": True}
        }
    ]
    
    print("\n📊 Phase 1: Baseline Testing (Legacy Only)")
    print("-" * 40)
    
    # Test with legacy only
    for i, request in enumerate(test_requests, 1):
        print(f"Processing test request {i}...")
        response = migration_manager.process_request(request)
        print(f"✓ Success: {response.get('success', True)}")
    
    stats = migration_manager.get_migration_stats()
    print(f"Legacy requests processed: {stats['requests']['legacy']}")
    
    print("\n🔄 Phase 2: Gradual Migration (50/50 Split)")
    print("-" * 40)
    
    # Test with 50% migration
    migration_manager.set_migration_percentage(0.5)
    
    for i in range(6):  # Process more requests for better statistics
        request = test_requests[i % len(test_requests)]
        response = migration_manager.process_request(request)
        print(f"Request {i+1}: {'Native' if response.get('success', True) else 'Legacy'}")
    
    stats = migration_manager.get_migration_stats()
    print(f"Native requests: {stats['requests']['native']}")
    print(f"Legacy requests: {stats['requests']['legacy']}")
    
    print("\n🎯 Phase 3: Full Migration (Native Only)")
    print("-" * 40)
    
    # Complete migration
    success = migration_manager.migrate_to_native_only()
    
    if success:
        # Test native-only processing
        for i, request in enumerate(test_requests, 1):
            print(f"Processing native request {i}...")
            response = migration_manager.process_request(request)
            print(f"✓ Success: {response.get('success', True)}")
        
        final_stats = migration_manager.get_migration_stats()
        print(f"\n📈 Final Statistics:")
        print(f"Total native requests: {final_stats['requests']['native']}")
        print(f"Performance improvement: {final_stats['performance']['improvement_percent']:.1f}%")
        print(f"Native pipeline errors: {final_stats['errors']['native']}")
        
        print("\n🎉 Migration completed successfully!")
        print("Legacy orchestrator has been deprecated and removed.")
        
    else:
        print("\n❌ Migration failed - staying on legacy system")
    
    return migration_manager

def create_migration_checklist():
    """Create a checklist for production migration"""
    
    checklist = """
    # Haystack Pipeline Migration Checklist
    
    ## Pre-Migration (Phase A)
    - [ ] All native components implemented and tested
    - [ ] Pydantic models validated  
    - [ ] Legacy adapters functioning correctly
    - [ ] Unit tests passing (90%+ coverage)
    - [ ] Performance benchmarks established
    
    ## Migration Phase (Phase B)
    - [ ] A/B testing framework set up
    - [ ] Migration percentage set to 10%
    - [ ] Monitor error rates and performance
    - [ ] Gradually increase to 50% 
    - [ ] Validate parallel processing improvements
    - [ ] Monitor for 24-48 hours at 50%
    
    ## Post-Migration (Phase C)
    - [ ] Native pipeline handling 100% of requests
    - [ ] Performance improvements validated (>20%)
    - [ ] No increase in error rates
    - [ ] Legacy orchestrator deprecated
    - [ ] Legacy code removed from codebase
    - [ ] Documentation updated
    - [ ] Team training completed
    
    ## Success Criteria
    - [ ] Functional parity with legacy system
    - [ ] 20%+ performance improvement achieved
    - [ ] 100% Pydantic validation coverage
    - [ ] 90%+ test coverage maintained
    - [ ] Zero legacy maintenance burden
    """
    
    with open("MIGRATION_CHECKLIST.md", "w") as f:
        f.write(checklist)
    
    print("✓ Migration checklist created: MIGRATION_CHECKLIST.md")

if __name__ == "__main__":
    # Run migration demonstration
    demonstrate_migration()
    
    # Create migration checklist
    create_migration_checklist()
    
    print("\n" + "=" * 60)
    print("🎯 Migration script completed!")
    print("Next steps:")
    print("1. Review MIGRATION_CHECKLIST.md")
    print("2. Update haystack_dnd_game.py to use native orchestrator")
    print("3. Remove legacy orchestrator after validation")
    print("4. Run performance benchmarks to confirm improvements")
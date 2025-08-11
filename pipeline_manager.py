"""
Advanced Pipeline Management System for Modular DM Assistant
Implements intelligent caching, async processing, smart routing, and error recovery
"""
import asyncio
import hashlib
import json
import pickle
import time
import psutil
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentCache:
    """Multi-layer caching system for pipeline results"""
    
    def __init__(self, cache_dir: str = "./cache", max_memory_items: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Layer 1: In-memory cache for fast access
        self.memory_cache: Dict[str, Dict] = {}
        self.memory_access_times: Dict[str, datetime] = {}
        self.max_memory_items = max_memory_items
        
        # Layer 2: Persistent cache for session persistence
        self.persistent_cache_file = self.cache_dir / "persistent_cache.pkl"
        self.persistent_cache: Dict[str, Dict] = self._load_persistent_cache()
        
        # Layer 3: Semantic cache for similar queries
        self.semantic_cache: Dict[str, Dict] = {}
        self.semantic_threshold = 0.85
        
    def _load_persistent_cache(self) -> Dict[str, Dict]:
        """Load persistent cache from disk"""
        try:
            if self.persistent_cache_file.exists():
                with open(self.persistent_cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load persistent cache: {e}")
        return {}
    
    def _save_persistent_cache(self):
        """Save persistent cache to disk"""
        try:
            with open(self.persistent_cache_file, 'wb') as f:
                pickle.dump(self.persistent_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save persistent cache: {e}")
    
    def _generate_cache_key(self, query: str, context: Dict) -> str:
        """Generate cache key from query and context"""
        context_str = json.dumps(context, sort_keys=True)
        combined = f"{query}|{context_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _find_similar_query(self, query: str) -> Optional[str]:
        """Find semantically similar query in cache"""
        # Simple similarity based on word overlap (can be enhanced with embeddings)
        query_words = set(query.lower().split())
        best_match = None
        best_score = 0
        
        for cached_query in self.semantic_cache.keys():
            cached_words = set(cached_query.lower().split())
            intersection = query_words.intersection(cached_words)
            union = query_words.union(cached_words)
            score = len(intersection) / len(union) if union else 0
            
            if score > best_score and score > self.semantic_threshold:
                best_score = score
                best_match = cached_query
        
        return best_match
    
    def _similarity_score(self, query1: str, query2: str) -> float:
        """Calculate similarity score between two queries"""
        words1 = set(query1.lower().split())
        words2 = set(query2.lower().split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0
    
    def get_cached_result(self, query: str, context: Dict) -> Optional[Dict]:
        """Get cached result with multi-layer lookup"""
        # Level 1: Exact match in memory
        cache_key = self._generate_cache_key(query, context)
        if cache_key in self.memory_cache:
            self.memory_access_times[cache_key] = datetime.now()
            logger.debug(f"Cache hit (memory): {cache_key}")
            return self.memory_cache[cache_key]
        
        # Level 2: Exact match in persistent cache
        if cache_key in self.persistent_cache:
            result = self.persistent_cache[cache_key]
            # Promote to memory cache
            self._add_to_memory_cache(cache_key, result)
            logger.debug(f"Cache hit (persistent): {cache_key}")
            return result
        
        # Level 3: Semantic similarity
        similar_key = self._find_similar_query(query)
        if similar_key and similar_key in self.semantic_cache:
            logger.debug(f"Cache hit (semantic): {similar_key}")
            return self.semantic_cache[similar_key]
        
        return None
    
    def cache_result(self, query: str, context: Dict, result: Dict, ttl_hours: int = 24):
        """Cache result with TTL"""
        cache_key = self._generate_cache_key(query, context)
        cached_item = {
            'result': result,
            'timestamp': datetime.now(),
            'ttl_hours': ttl_hours,
            'access_count': 1
        }
        
        # Add to all cache layers
        self._add_to_memory_cache(cache_key, cached_item)
        self.persistent_cache[cache_key] = cached_item
        self.semantic_cache[query] = cached_item
        
        # Save persistent cache periodically
        if len(self.persistent_cache) % 10 == 0:
            self._save_persistent_cache()
    
    def _add_to_memory_cache(self, key: str, item: Dict):
        """Add item to memory cache with LRU eviction"""
        if len(self.memory_cache) >= self.max_memory_items:
            # Evict least recently used
            oldest_key = min(self.memory_access_times.keys(), 
                           key=lambda k: self.memory_access_times[k])
            del self.memory_cache[oldest_key]
            del self.memory_access_times[oldest_key]
        
        self.memory_cache[key] = item
        self.memory_access_times[key] = datetime.now()
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        now = datetime.now()
        expired_keys = []
        
        for key, item in self.memory_cache.items():
            if 'timestamp' in item and 'ttl_hours' in item:
                expiry = item['timestamp'] + timedelta(hours=item['ttl_hours'])
                if now > expiry:
                    expired_keys.append(key)
        
        for key in expired_keys:
            self.memory_cache.pop(key, None)
            self.memory_access_times.pop(key, None)
            self.persistent_cache.pop(key, None)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            self._save_persistent_cache()

class ResourceMonitor:
    """Monitor system resources"""
    
    def __init__(self):
        self.cpu_threshold = 80
        self.memory_threshold = 75
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=1)
    
    def get_memory_usage(self) -> float:
        """Get current memory usage percentage"""
        return psutil.virtual_memory().percent
    
    def is_system_overloaded(self) -> bool:
        """Check if system is overloaded"""
        cpu = self.get_cpu_usage()
        memory = self.get_memory_usage()
        return cpu > self.cpu_threshold or memory > self.memory_threshold

class LoadBalancer:
    """Balance load across pipeline operations"""
    
    def __init__(self):
        self.max_concurrent_ops = 5
        self.current_ops = 0
        self.aggressive_caching = False
    
    def reduce_concurrent_operations(self):
        """Reduce concurrent operations"""
        self.max_concurrent_ops = max(2, self.max_concurrent_ops - 1)
        logger.info(f"Reduced concurrent operations to {self.max_concurrent_ops}")
    
    def enable_aggressive_caching(self):
        """Enable aggressive caching mode"""
        self.aggressive_caching = True
        logger.info("Enabled aggressive caching mode")
    
    def can_process_request(self) -> bool:
        """Check if new request can be processed"""
        return self.current_ops < self.max_concurrent_ops
    
    def acquire_slot(self) -> bool:
        """Acquire processing slot"""
        if self.can_process_request():
            self.current_ops += 1
            return True
        return False
    
    def release_slot(self):
        """Release processing slot"""
        self.current_ops = max(0, self.current_ops - 1)

class ResourceOptimizer:
    """Optimize computational resources across pipelines"""
    
    def __init__(self):
        self.resource_monitor = ResourceMonitor()
        self.load_balancer = LoadBalancer()
        self.last_optimization = datetime.now()
        self.optimization_interval = timedelta(minutes=5)
    
    def optimize_pipeline_allocation(self):
        """Optimize pipeline resource allocation"""
        if datetime.now() - self.last_optimization < self.optimization_interval:
            return
        
        cpu_usage = self.resource_monitor.get_cpu_usage()
        memory_usage = self.resource_monitor.get_memory_usage()
        
        # Adjust pipeline priorities based on load
        if cpu_usage > 80:
            self.load_balancer.reduce_concurrent_operations()
            logger.warning(f"High CPU usage ({cpu_usage}%), reducing concurrent operations")
        
        if memory_usage > 75:
            self.load_balancer.enable_aggressive_caching()
            logger.warning(f"High memory usage ({memory_usage}%), enabling aggressive caching")
        
        self.last_optimization = datetime.now()

class PerformanceMonitor:
    """Monitor pipeline performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.start_times: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = {}
    
    def start_operation(self, operation_id: str) -> str:
        """Start timing an operation"""
        unique_id = f"{operation_id}_{int(time.time() * 1000)}"
        self.start_times[unique_id] = time.time()
        return unique_id
    
    def end_operation(self, unique_id: str, success: bool = True):
        """End timing an operation"""
        if unique_id in self.start_times:
            duration = time.time() - self.start_times[unique_id]
            operation_id = unique_id.split('_')[0]
            
            if operation_id not in self.metrics:
                self.metrics[operation_id] = []
            
            self.metrics[operation_id].append(duration)
            
            if not success:
                self.error_counts[operation_id] = self.error_counts.get(operation_id, 0) + 1
            
            del self.start_times[unique_id]
    
    def get_average_response_time(self, operation_id: str) -> float:
        """Get average response time for operation"""
        if operation_id in self.metrics and self.metrics[operation_id]:
            return sum(self.metrics[operation_id]) / len(self.metrics[operation_id])
        return 0.0
    
    def get_error_rate(self, operation_id: str) -> float:
        """Get error rate for operation"""
        total_ops = len(self.metrics.get(operation_id, []))
        errors = self.error_counts.get(operation_id, 0)
        return (errors / total_ops * 100) if total_ops > 0 else 0.0

class AsyncPipelineManager:
    """Manage multiple pipelines asynchronously"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def process_parallel_queries(self, queries: List[Dict]) -> List[Dict]:
        """Process multiple queries in parallel"""
        tasks = []
        for query in queries:
            if query.get('independent', False):
                task = asyncio.create_task(self._process_async(query))
                tasks.append(task)
            else:
                # Process dependent queries sequentially
                result = await self._process_async(query)
                tasks.append(result)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r for r in results if not isinstance(r, Exception)]
        return []
    
    async def _process_async(self, query: Dict) -> Dict:
        """Process a single query asynchronously"""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor, self._process_sync, query
            )
            return result
        except Exception as e:
            logger.error(f"Async processing error: {e}")
            return {"error": str(e)}
    
    def _process_sync(self, query: Dict) -> Dict:
        """Synchronous processing method (to be overridden)"""
        # This would be implemented by specific pipeline managers
        return {"result": "processed", "query": query}

class IntentClassifier:
    """Classify query intent for smart routing"""
    
    def __init__(self):
        self.intent_patterns = {
            'creative': [
                'generate', 'create', 'scenario', 'story', 'adventure', 'encounter',
                'narrative', 'describe', 'continue', 'imagine'
            ],
            'factual': [
                'what is', 'define', 'explain', 'tell me about', 'information',
                'facts', 'details', 'describe'
            ],
            'rules': [
                'rule', 'rules', 'how does', 'mechanics', 'check', 'roll',
                'condition', 'spell', 'ability', 'combat'
            ],
            'hybrid': [
                'help', 'suggest', 'recommend', 'advice', 'guidance'
            ]
        }
    
    def classify(self, query: str, context: Dict = None) -> str:
        """Classify query intent"""
        query_lower = query.lower()
        intent_scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in query_lower)
            intent_scores[intent] = score
        
        # Return intent with highest score, default to factual
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        return best_intent if intent_scores[best_intent] > 0 else 'factual'

class PipelineManager:
    """Central pipeline management system"""
    
    def __init__(self):
        self.cache = IntelligentCache()
        self.async_manager = AsyncPipelineManager()
        self.optimizer = ResourceOptimizer()
        self.monitor = PerformanceMonitor()
        self.intent_classifier = IntentClassifier()
        
        # Initialize cleanup scheduler
        self._schedule_cleanup()
    
    def _schedule_cleanup(self):
        """Schedule periodic cache cleanup"""
        def cleanup_task():
            while True:
                time.sleep(3600)  # Run every hour
                self.cache.cleanup_expired()
                logger.info("Periodic cache cleanup completed")
        
        import threading
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    async def process_query(self, query: str, context: Dict, pipeline_type: str = None) -> Dict:
        """Process query with intelligent routing and caching"""
        # Start performance monitoring
        op_id = self.monitor.start_operation(f"query_{pipeline_type or 'auto'}")
        
        try:
            # Check cache first
            cached_result = self.cache.get_cached_result(query, context)
            if cached_result and 'result' in cached_result:
                self.monitor.end_operation(op_id, success=True)
                return cached_result['result']
            
            # Optimize resources
            self.optimizer.optimize_pipeline_allocation()
            
            # Classify intent if pipeline type not specified
            if not pipeline_type:
                pipeline_type = self.intent_classifier.classify(query, context)
            
            # Process query (this would be implemented by specific pipelines)
            result = await self._route_and_process(query, context, pipeline_type)
            
            # Cache the result
            self.cache.cache_result(query, context, result)
            
            self.monitor.end_operation(op_id, success=True)
            return result
            
        except Exception as e:
            self.monitor.end_operation(op_id, success=False)
            logger.error(f"Pipeline processing error: {e}")
            return {"error": str(e)}
    
    async def _route_and_process(self, query: str, context: Dict, pipeline_type: str) -> Dict:
        """Route query to appropriate pipeline and process"""
        # This would be implemented to route to specific pipeline implementations
        return {
            "answer": f"Processed {pipeline_type} query: {query[:50]}...",
            "pipeline_used": pipeline_type,
            "processing_time": time.time()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        metrics = {}
        for operation in self.monitor.metrics.keys():
            metrics[operation] = {
                'avg_response_time': self.monitor.get_average_response_time(operation),
                'error_rate': self.monitor.get_error_rate(operation),
                'total_operations': len(self.monitor.metrics[operation])
            }
        return metrics
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'memory_cache_size': len(self.cache.memory_cache),
            'persistent_cache_size': len(self.cache.persistent_cache),
            'semantic_cache_size': len(self.cache.semantic_cache),
            'max_memory_items': self.cache.max_memory_items
        }
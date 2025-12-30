# Refined Implementation Plan for Asynchronous Communication Fix

## Key Improvements Incorporated

This refinement builds on the original proposed plan and integrates feedback for more robust and scalable async communication between **ScenarioGenerator** and **HaystackPipeline** agents.

---

## Updated Solution Architecture

### 1. Eliminate Synchronous Waiting (unchanged)
- Remove `threading.Event().wait()`.
- Use callback-based async handling for RAG responses.

### 2. Improved Request State Management
- Use `PendingScenarioRequest` data class for request lifecycle tracking.
- Replace `threading.Lock()` with `asyncio.Lock()` to ensure async-safe concurrency control.

```python
class ScenarioGeneratorAgent(BaseAgent):
    def __init__(self):
        # Async-safe state tracking
        self.pending_scenarios: Dict[str, PendingScenarioRequest] = {}
        self.request_lock = asyncio.Lock()
```

### 3. Explicit Late Response Disposal
- Track request expiry timestamps.
- Any RAG response received after timeout should be discarded immediately (instead of being processed as "unknown request").

```python
async def _handle_retrieve_documents_response(self, message: AgentMessage):
    async with self.request_lock:
        req = self.pending_scenarios.get(message.response_to)
        if not req or time.time() > req.timestamp + req.timeout:
            self.logger.warning(f"Dropping expired response for {message.response_to}")
            return  # Late response ignored
        # Otherwise complete scenario generation
```

### 4. Retry Strategy with Backoff
- Replace fixed retries with exponential backoff + jitter.

```python
async def _retry_with_backoff(func, max_retries=2):
    delay = 1
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            await asyncio.sleep(delay + random.uniform(0, 0.5))
            delay *= 2
    raise RuntimeError("Max retries exceeded")
```

### 5. Circuit Breaker Granularity
- Track failures **per agent** or **per request type** instead of global counters.
- Prevents one failing component from halting all RAG use.

```python
self.failure_counts: Dict[str, int] = defaultdict(int)
```

### 6. Message Ordering & Idempotency
- Enforce correlation IDs for all requests/responses.
- Ensure handlers are idempotent (safe to reapply if duplicate/out-of-order).

### 7. Monitoring & Tracing Enhancements
- Add correlation IDs to logs and metrics for every request.
- Track per-agent metrics: success/failure, response times, late responses dropped.

---

## Revised Implementation Strategy

### Phase 1: Quick Fixes (Immediate)
1. Fix handler response inconsistency.
2. Remove conflicting `send_response` calls.
3. Reduce `RAG_REQUEST_TIMEOUT` to 10s.

### Phase 2: Async State Machine (Short-term)
1. Replace blocking wait with async callbacks.
2. Implement async-safe request tracking (`asyncio.Lock`).
3. Add late response disposal logic.

### Phase 3: Reliability Enhancements (Medium-term)
1. Implement exponential backoff + jitter retries.
2. Add per-agent circuit breakers with reset timers.
3. Ensure idempotent request/response handling.

### Phase 4: Performance & Observability (Long-term)
1. Add request deduplication and batching.
2. Expand metrics with correlation IDs.
3. Monitor response ordering and late-response frequency.

---

## Updated Constants

```python
RAG_REQUEST_TIMEOUT = 10.0  # seconds
MAX_RAG_RETRIES = 2
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_RESET_TIME = 60
BACKOFF_BASE_DELAY = 1.0  # seconds
```

---

## Expected Benefits (Refined)

1. **Race Condition Elimination**: Async-safe handling prevents blocking and mismatched responses.  
2. **Consistent Responses**: Framework cleanly distinguishes async vs sync replies.  
3. **Resilient Under Failures**: Late responses discarded, retries with backoff, circuit breakers per agent.  
4. **Scalable**: Async state machine with batching and deduplication.  
5. **Improved Debugging**: Correlation IDs for tracing across multiple agents.  
6. **User-Friendly**: Faster fallback when RAG unavailable, without blocking scenario generation.  

---

## Next Step

- Implement the refined async state machine and late response disposal.
- Add metrics dashboards for monitoring RAG performance and timeout rates.

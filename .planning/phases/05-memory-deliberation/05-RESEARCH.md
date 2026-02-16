# Phase 5: Memory + Deliberation - Research

**Researched:** 2026-02-16
**Domain:** Structured observation storage, LLM comparative deliberation, ranking output
**Confidence:** HIGH

## Summary

Phase 5 adds two capabilities to Arbiter: (1) per-demo structured memory that persists observations alongside scorecards, and (2) an end-of-event deliberation engine that performs comparative analysis across all demos and produces ranked output with reasoning for human judges.

The existing codebase already provides strong foundations. `ScoreStore` (Phase 4) already persists one JSON file per team in `data/scores/` with `load_all()` explicitly documented as "for Phase 5 deliberation." The `SanitizedOutput` model from Phase 2 contains exactly the structured observations MEM-01 requires -- clean observations, transcripts, injection attempts, and duration. The event bus architecture means the new memory store can subscribe to `observation_verified` events (same as scoring and commentary do) and persist observations alongside existing scorecards.

For deliberation, the key insight is that this is a batch operation triggered manually by the operator at end-of-event, not a real-time pipeline. The operator issues a "deliberate" command, the system loads all stored observations and scorecards, constructs a single comprehensive prompt with all demo data, and gets Gemini to produce structured comparative rankings. Gemini's native Pydantic `response_schema` support (verified in Context7) guarantees the output conforms to the expected ranking structure without manual JSON parsing. Python sorts the final rankings by score (never trusting LLM ordering), matching the established pattern of Python-computed totals from Phase 4.

**Primary recommendation:** Build a `MemoryStore` parallel to `ScoreStore` for observation persistence, a `DeliberationEngine` using Gemini structured output for comparative analysis, and a `DeliberationPipeline` orchestrator triggered by a new operator command. Use the same architectural patterns (event bus subscription, dedicated genai.Client, Pydantic models, JSON file storage) that Phases 1-4 established.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | ~1.13 (already installed) | Deliberation LLM calls with structured output | Already in stack; native Pydantic response_schema support eliminates manual JSON parsing |
| pydantic | ~2.11 (already installed) | Data models for observations, deliberation results, rankings | Already used throughout for all domain models |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | - | - | All dependencies already in pyproject.toml |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON file storage | SQLite | SQLite adds a dependency for ~24 files; JSON files match ScoreStore pattern and are human-readable. Not worth the complexity for hackathon-scale data (max ~30 demos). |
| Gemini structured output | Manual JSON parsing (like Phase 4 scoring engine) | Phase 4 was built before team adopted response_schema pattern. Structured output with Pydantic is cleaner, more reliable, and eliminates the markdown-fence-stripping code. Use it for new code. |
| Single deliberation prompt | Multi-step chain (pairwise comparisons) | Pairwise comparison scales as O(n^2) for n demos. With ~24 demos max, a single comprehensive prompt fits comfortably in Gemini 2.5 Flash's context window. Simpler is better for hackathon timeline. |

**Installation:**
```bash
# No new dependencies needed -- everything is already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── memory/                    # NEW: Phase 5 module
│   ├── __init__.py
│   ├── models.py              # DemoMemory, DeliberationResult, TeamRanking, events
│   ├── store.py               # MemoryStore -- JSON file persistence for observations
│   ├── deliberation_engine.py # Gemini-powered comparative analysis
│   └── pipeline.py            # DeliberationPipeline orchestrator
├── scoring/
│   └── store.py               # ScoreStore (existing -- load_all() already built for this)
└── ...
```

### Pattern 1: Parallel Store Pattern (MemoryStore alongside ScoreStore)

**What:** MemoryStore follows the identical pattern to ScoreStore -- one JSON file per team in `data/observations/`, sanitized team names, async file I/O via `asyncio.to_thread`, and a `load_all()` method for batch retrieval.

**When to use:** For the observation persistence layer (MEM-01).

**Example:**
```python
# Source: Existing ScoreStore pattern in src/scoring/store.py
from pydantic import BaseModel

class DemoMemory(BaseModel):
    """Structured observations stored per-demo for deliberation."""
    team_name: str
    track: str
    observations: list[str]       # clean Gemini observations
    transcripts: list[str]        # clean transcript segments
    injection_attempts: int       # count only, not content
    demo_duration: float
    stored_at: float

class MemoryStore:
    """Persists structured demo observations as JSON files."""

    def __init__(self, observations_dir: str = "data/observations") -> None:
        self._dir = Path(observations_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def save(self, memory: DemoMemory) -> Path:
        sanitized = self._sanitize_team_name(memory.team_name)
        path = self._dir / f"{sanitized}.json"
        data = json.dumps(memory.model_dump(), indent=2, default=str)
        await asyncio.to_thread(path.write_text, data)
        return path

    async def load_all(self) -> list[DemoMemory]:
        memories: list[DemoMemory] = []
        for path in sorted(self._dir.glob("*.json")):
            raw = await asyncio.to_thread(path.read_text)
            memories.append(DemoMemory.model_validate_json(raw))
        return memories
```

### Pattern 2: Gemini Structured Output for Deliberation

**What:** Use Gemini's native `response_schema` with a Pydantic model to guarantee the deliberation output conforms to the expected ranking structure. This eliminates the manual JSON parsing and markdown-fence-stripping that Phase 4's scoring engine had to do.

**When to use:** For the deliberation engine (MEM-02).

**Example:**
```python
# Source: Context7 /googleapis/python-genai -- structured output docs
from google import genai
from google.genai import types
from pydantic import BaseModel

class TeamRanking(BaseModel):
    """Ranking entry for one team in the final deliberation."""
    rank: int
    team_name: str
    track: str
    total_score: float
    strengths: list[str]           # 2-3 key strengths
    weaknesses: list[str]          # 1-2 areas of weakness
    cross_references: list[str]    # specific comparisons to other teams
    reasoning: str                 # why this rank, with evidence

class DeliberationResult(BaseModel):
    """Complete deliberation output for the event."""
    rankings: list[TeamRanking]
    overall_narrative: str         # 2-3 paragraph event summary
    notable_themes: list[str]      # patterns across demos
    deliberated_at: float

# In DeliberationEngine:
response = await self._client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=deliberation_prompt,
    config=types.GenerateContentConfig(
        system_instruction=DELIBERATION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=DeliberationResult,
        max_output_tokens=4000,
        temperature=0.4,
    ),
)
# response.text is guaranteed valid JSON matching the schema
result = DeliberationResult.model_validate_json(response.text)
```

### Pattern 3: Python-Authoritative Ranking Order

**What:** After getting the LLM's comparative analysis, Python re-sorts the rankings by `total_score` from the ScoreStore (not the LLM's rank assignments). The LLM provides reasoning and cross-references, but Python determines the actual rank numbers. This follows the established Phase 4 decision: "Python-computed weighted totals, never trust LLM arithmetic."

**When to use:** For final ranking assembly (MEM-03).

**Example:**
```python
# After LLM deliberation returns TeamRanking objects:
# 1. Load authoritative scores from ScoreStore
scorecards = await self._score_store.load_all()
score_by_team = {sc.team_name: sc.total_score for sc in scorecards}

# 2. Override LLM rank assignments with Python sort
rankings = sorted(
    result.rankings,
    key=lambda r: score_by_team.get(r.team_name, 0.0),
    reverse=True,
)
for i, ranking in enumerate(rankings, 1):
    ranking.rank = i
    ranking.total_score = score_by_team.get(ranking.team_name, ranking.total_score)
```

### Pattern 4: Operator-Triggered Deliberation via Event Bus

**What:** Deliberation is not automatic -- the operator triggers it with a `deliberate` command when the event is over. This publishes a `DeliberationRequested` event on the bus, which the `DeliberationPipeline` subscribes to. Results are saved to disk and pushed to the display server.

**When to use:** For the deliberation trigger flow (MEM-02, MEM-03).

**Example:**
```python
# New event type
class DeliberationRequested(CaptureEvent):
    event_type: str = "deliberation_requested"

class DeliberationComplete(CaptureEvent):
    event_type: str = "deliberation_complete"
    result: DeliberationResult

# In OperatorCLI / TUI:
def _handle_deliberate(self) -> None:
    self.event_bus.publish(DeliberationRequested())

# In DeliberationPipeline:
async def _on_deliberation_requested(self, event):
    memories = await self._memory_store.load_all()
    scorecards = await self._score_store.load_all()
    result = await self._engine.deliberate(memories, scorecards)
    await self._result_store.save(result)
    # Push to display for audience
    await self._display.push_deliberation(result)
    self._event_bus.publish(DeliberationComplete(result=result))
```

### Anti-Patterns to Avoid

- **Storing raw input in memory:** MEM-01 explicitly requires "extracted facts, not raw input." Store the SanitizedOutput observations (already structured by Gemini and cleaned by the defense pipeline), never raw frames or audio.
- **Trusting LLM ranking order:** The LLM provides comparative reasoning, but Python must sort by the authoritative scores from ScoreStore. LLMs are known to be inconsistent at ordering when given many items.
- **Running deliberation automatically:** Deliberation should only fire when the operator explicitly requests it. Auto-triggering on the last demo would require knowing which demo is last, which the system cannot determine.
- **Including scorecard justifications in memory:** The MemoryStore should store observations and transcripts. Scorecard data (per-criterion scores and justifications) is already in ScoreStore. Don't duplicate -- load both at deliberation time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | Manual JSON parsing with fence-stripping (Phase 4 style) | Gemini `response_schema` with Pydantic model | Native structured output guarantees schema compliance; no parsing errors possible |
| File-based persistence | Custom serialization | Pydantic `model_dump()` / `model_validate_json()` | Already used throughout codebase; handles all serialization edge cases |
| Team name sanitization | New sanitizer function | Reuse `ScoreStore._sanitize_team_name()` | Identical logic needed; extract to shared utility or import from scoring |

**Key insight:** Phase 5 introduces no new infrastructure patterns. Every component maps directly to an existing pattern from Phases 1-4. The novelty is in the prompt engineering for comparative deliberation, not in the architecture.

## Common Pitfalls

### Pitfall 1: LLM Context Window Overflow with Many Demos

**What goes wrong:** With ~24 demos, each having 10-20 observations and multiple transcript segments, the deliberation prompt could exceed Gemini 2.5 Flash's context window.
**Why it happens:** Naively concatenating all observations for all teams creates a massive prompt.
**How to avoid:** Summarize each demo's observations into a compact structured block before including in the deliberation prompt. Each team should get a 5-8 line summary block with: team name, track, score, key observations (top 5), and transcript highlights (2-3). With 24 teams at ~100 tokens per block, total prompt stays under 5K tokens -- well within limits.
**Warning signs:** Gemini errors about context length, or truncated/incomplete deliberation output.

### Pitfall 2: Score Ties Without Tiebreaking

**What goes wrong:** Two teams get identical total_score. Python sort is stable, so ordering depends on load order from filesystem, which feels arbitrary.
**Why it happens:** Weighted scores with 1 decimal place and only 3-4 criteria create a relatively coarse score space.
**How to avoid:** Define a tiebreaker: when total_score is equal, break ties by (1) track bonus score, then (2) Technical Execution score, then (3) demo duration (longer demo = more ambitious). Document tiebreak logic clearly for human judges.
**Warning signs:** Two teams at the same rank in output.

### Pitfall 3: Deliberation Without All Teams Scored

**What goes wrong:** Operator triggers deliberation before all teams have been scored, producing incomplete rankings.
**Why it happens:** No guard against premature deliberation.
**How to avoid:** When deliberation is requested, compare the count of saved observations vs saved scorecards. If they differ, warn the operator. Optionally show "N teams observed, M teams scored" and require confirmation.
**Warning signs:** Deliberation result has fewer teams than expected.

### Pitfall 4: Memory Store and Score Store Team Name Mismatch

**What goes wrong:** A team is stored as "Team Alpha" in MemoryStore but "team_alpha" or "Team  Alpha" (extra space) in ScoreStore because the operator typed it differently in the start command.
**Why it happens:** Team names come from free-text operator input at demo start time. Different demos could have slight variations.
**How to avoid:** Both stores use the same `_sanitize_team_name()` function, so filesystem names will match. But the `team_name` field inside the JSON will preserve the original input. When joining observations with scores for deliberation, always join on sanitized filename, not on the raw team_name field.
**Warning signs:** A team appears in observations but not in scores, or vice versa.

### Pitfall 5: Deliberation Prompt Losing Arbiter's Voice

**What goes wrong:** The deliberation output reads like a generic comparison essay, not like Arbiter.
**Why it happens:** The deliberation system prompt focuses on analytical comparison and forgets the persona.
**How to avoid:** The deliberation prompt should be analytical first, but the `overall_narrative` field can carry Arbiter's voice. Split the concern: rankings and reasoning are structured and analytical, the narrative is persona-flavored. Don't try to make the per-team reasoning snarky -- judges need clear reasoning, not entertainment in the deliberation document.
**Warning signs:** Human judges dismiss the deliberation output as unhelpful or too jokey.

## Code Examples

Verified patterns from the existing codebase and official sources:

### Subscribing to observation_verified (existing pattern)

```python
# Source: src/scoring/pipeline.py lines 54-55
# Both commentary and scoring already subscribe to this event
event_bus.subscribe("observation_verified", self._on_observation_verified)

# Memory pipeline would do the same:
event_bus.subscribe("observation_verified", self._on_observation_verified)
```

### Async Gemini call with Pydantic structured output

```python
# Source: Context7 /googleapis/python-genai -- structured output docs
# Async variant matching existing codebase patterns (see scoring/engine.py)
response = await self._client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=DELIBERATION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=DeliberationResult,
        max_output_tokens=4000,
        temperature=0.4,
    ),
)
result = DeliberationResult.model_validate_json(response.text)
```

### Loading all scorecards for deliberation (existing method)

```python
# Source: src/scoring/store.py lines 74-87
# ScoreStore.load_all() was explicitly built for Phase 5 deliberation
scorecards = await self._score_store.load_all()
# Returns list[DemoScorecard] sorted by filename
```

### Display server broadcast (existing pattern for new message type)

```python
# Source: src/commentary/display_server.py -- follows push_* pattern
async def push_deliberation_ranking(
    self, rank: int, team_name: str, total_score: float, reasoning: str
) -> None:
    await self._manager.broadcast({
        "type": "deliberation_ranking",
        "rank": rank,
        "team_name": team_name,
        "total_score": total_score,
        "reasoning": reasoning,
    })
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON parsing from LLM | Gemini `response_schema` with Pydantic | google-genai ~1.10+ (mid-2025) | Eliminates all JSON parsing code; guaranteed schema compliance |
| Chat-based multi-turn deliberation | Single comprehensive prompt with structured output | N/A (design choice) | Simpler, more predictable, no state management |

**Deprecated/outdated:**
- Manual JSON fence-stripping (Phase 4's `_parse_and_validate` approach): Still works, but `response_schema` is strictly better for new code. Do not refactor Phase 4 -- leave it as-is, but use the new pattern for Phase 5.

## Open Questions

1. **How many observations per demo should be stored?**
   - What we know: GeminiSession accumulates observations as raw text strings with no limit. A 5-minute demo might produce 20-50 observation strings depending on model verbosity.
   - What's unclear: Whether storing all observations is necessary or whether a summary/top-N would be more useful for deliberation.
   - Recommendation: Store all observations (they're already structured text, not raw media). At deliberation time, the deliberation engine can select the most relevant ones for the prompt. Storage is cheap; information loss is not.

2. **Should deliberation output be displayed on the audience screen or only saved to file?**
   - What we know: MEM-03 says "format human judges can review and discuss during deliberation." This could mean a file they read on a laptop, or a projected display, or both.
   - What's unclear: Whether the audience should see the deliberation rankings being revealed.
   - Recommendation: Support both -- save to `data/deliberation/result.json` for judges to review, and push a simplified ranking view to the display server for audience entertainment. The display can show rank + team + score; judges get the full reasoning document.

3. **Should the deliberation engine use a different/larger model than Gemini 2.5 Flash?**
   - What we know: Comparative analysis across 24 demos with cross-references is a more complex reasoning task than single-demo scoring. Gemini 2.5 Flash handles scoring fine, but deliberation involves synthesizing information across many demos simultaneously.
   - What's unclear: Whether Flash's reasoning capacity is sufficient for high-quality cross-references, or whether a larger model (Gemini 2.5 Pro or Gemini 3 Pro) would produce meaningfully better output.
   - Recommendation: Default to Gemini 2.5 Flash (consistent with codebase). The prompt will be well-structured with pre-sorted scores and summarized observations, reducing the reasoning burden. If output quality is poor in testing, the model parameter is easily configurable. No need to over-engineer for the hackathon timeline.

4. **Track-specific sub-rankings?**
   - What we know: There are 4 tracks (SHADOW::VECTOR, SENTINEL::MESH, ZERO::PROOF, ROGUE::AGENT). Teams compete within their track.
   - What's unclear: Whether deliberation should produce per-track rankings or a single overall ranking.
   - Recommendation: Produce both -- an overall ranking across all teams, plus per-track rankings grouped by track. The deliberation prompt can request this as part of the structured output. Human judges can use whichever view is appropriate for their award categories.

## Sources

### Primary (HIGH confidence)
- Context7 `/googleapis/python-genai` -- Structured output with Pydantic response_schema, async generate_content patterns
- Existing codebase analysis: `src/scoring/store.py`, `src/scoring/engine.py`, `src/scoring/pipeline.py`, `src/defense/models.py`, `src/capture/event_bus.py` -- all patterns verified by reading source code directly

### Secondary (MEDIUM confidence)
- [Gemini API Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output) -- Official Google documentation on response_schema
- [Google Blog: Improving Structured Outputs](https://blog.google/technology/developers/gemini-api-structured-outputs/) -- Confirms anyOf, $ref support and key ordering preservation

### Tertiary (LOW confidence)
- LLM-as-Judge methodology (WebSearch) -- General pattern of structured criteria analysis with chain-of-thought reasoning improving reliability by 10-15%. Not verified against specific benchmarks.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new dependencies. All libraries already in use. Structured output with Pydantic verified via Context7.
- Architecture: HIGH -- Every pattern maps to an existing codebase pattern (ScoreStore, ScoringEngine, ScoringPipeline). No novel architecture.
- Pitfalls: HIGH -- Pitfalls derived from direct analysis of existing code patterns and data flow. Context window math is verifiable.

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable -- no fast-moving dependencies)

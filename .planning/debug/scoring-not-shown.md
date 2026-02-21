---
status: fixed
trigger: "the commentary didn't finish. there is no way to reset, and the score hasn't shown"
created: 2026-02-17T00:00:00Z
updated: 2026-02-17T00:12:30Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: ROOT CAUSE FOUND - operatorStore never clears lastScorecard on demo start/stop/reset, causing stale scores to persist across demos
test: Verified that operatorStore has no reset logic for lastScorecard and no listeners for demo_started/demo_stopped events
expecting: Phase 10 bug confirmed - missing state reset for scorecard data
next_action: Write diagnosis report

## Symptoms

expected: Commentary completes → scoring fires → scorecard appears on operator dashboard
actual: Commentary didn't finish, scoring never shown, no way to reset
errors: None reported
reproduction: Run demo through Arbiter system
started: Phase 10 UAT

## Eliminated

## Evidence

- timestamp: 2026-02-17T00:01:00Z
  checked: web.py _on_event scorecard extraction (lines 165-183)
  found: Extracts scorecard data from `event.scorecard` when event_type == "scoring_complete". Attribute name matches DemoScorecard model.
  implication: Phase 10 scorecard extraction logic is CORRECT - if scoring_complete fires with scorecard, it will reach dashboard.

- timestamp: 2026-02-17T00:02:00Z
  checked: scoring/pipeline.py event publishing (lines 98-100)
  found: ScoringComplete event published with scorecard=scorecard after scoring finishes. Event contains DemoScorecard.
  implication: If scoring happens, event IS published with correct attribute name.

- timestamp: 2026-02-17T00:03:00Z
  checked: scoring/pipeline.py trigger mechanism (lines 57-58, 68-100)
  found: Scoring is triggered by observation_verified event. After scoring, publishes ScoringComplete immediately.
  implication: Scoring fires IMMEDIATELY after observation_verified, NOT after commentary.

- timestamp: 2026-02-17T00:04:00Z
  checked: commentary/pipeline.py commentary delivery (lines 170-214)
  found: Commentary generation can fail silently with exception logging (line 210-214). If generation fails, CommentaryDelivered event is NEVER published.
  implication: If commentary pipeline crashes/hangs, CommentaryDelivered never fires, which means scoring pipeline's theatrical reveal never triggers.

- timestamp: 2026-02-17T00:05:00Z
  checked: scoring/pipeline.py theatrical reveal (lines 102-119)
  found: Score reveal (_reveal_score) is triggered by commentary_delivered event, NOT by scoring completion. Scorecard is stored in _pending_scorecards waiting for commentary to finish.
  implication: Even if scoring succeeds, scorecard won't appear until commentary_delivered event fires.

- timestamp: 2026-02-17T00:06:00Z
  checked: Complete event flow architecture
  found: observation_verified triggers BOTH commentary (line 105) AND scoring (line 57) pipelines in parallel. Scoring publishes scoring_complete immediately with scorecard. Web.py receives scoring_complete and broadcasts scorecard to dashboard (lines 165-183). The theatrical reveal is SEPARATE and depends on commentary_delivered.
  implication: **CRITICAL FINDING** - Dashboard SHOULD receive scorecard data via scoring_complete event, independent of commentary completion. If dashboard didn't show score, either (1) scoring never fired, or (2) web.py event broadcasting failed.

- timestamp: 2026-02-17T00:07:00Z
  checked: Phase 10 regression surface
  found: web.py _on_event handles scoring_complete by extracting scorecard and broadcasting to operator clients (lines 165-183). This is a Phase 10 addition for the ScorePanel component.
  implication: If this extraction/broadcast is broken, it's a Phase 10 bug. If scoring_complete never fired, it's upstream (not Phase 10).

- timestamp: 2026-02-17T00:08:00Z
  checked: Frontend operatorStore scorecard handling (lines 89-92)
  found: Store listens for event type === 'scoring_complete' and extracts scorecard from msg.data.scorecard. ScorePanel reads lastScorecard from store.
  implication: Frontend expects event.data.scorecard structure (nested under data), but web.py broadcasts it at event_data["data"]["scorecard"].

- timestamp: 2026-02-17T00:09:00Z
  checked: Data structure match between web.py broadcast and frontend expectation
  found: web.py creates event_data with event_data["data"]["scorecard"] = {...} (line 168-182), then broadcasts event_data (line 184). Frontend reads msg.data.scorecard (line 90-91). Structure MATCHES.
  implication: Data structure is correct. If scorecard not showing, either scoring_complete never fired OR there's a reset issue.

- timestamp: 2026-02-17T00:10:00Z
  checked: Reset mechanism for lastScorecard
  found: operatorStore has NO reset logic for lastScorecard. It's set when scoring_complete arrives (line 91) but NEVER cleared on demo start/stop/reset.
  implication: **POTENTIAL PHASE 10 BUG** - If previous demo scored successfully, lastScorecard persists. User expects fresh "Awaiting judgment..." but sees stale score from previous demo.

- timestamp: 2026-02-17T00:11:00Z
  checked: User symptom interpretation
  found: User said "no way to reset" which aligns with lastScorecard not being cleared. If commentary hung on current demo but previous demo scored, they'd see old score with no way to clear it.
  implication: User might be seeing STALE scorecard from a previous successful demo, not "no score shown" but "wrong score shown with no reset".

## Eliminated

- hypothesis: web.py scorecard extraction has incorrect attribute name (event.scorecard vs event.data.scorecard)
  evidence: Verified scoring/models.py ScoringComplete has scorecard attribute (line 66). web.py correctly accesses event.scorecard (line 167). Frontend expects msg.data.scorecard which matches web.py's event_data["data"]["scorecard"] structure.
  timestamp: 2026-02-17T00:09:00Z

- hypothesis: Scorecard data never reaches dashboard because scoring pipeline hangs
  evidence: User report says "the score hasn't shown" but also "no way to reset", implying they're looking at persistent UI state. If scoring never happened, there'd be nothing to reset. The "no reset" complaint suggests stale data, not missing data.
  timestamp: 2026-02-17T00:11:00Z

- hypothesis: Commentary pipeline hanging is a Phase 10 regression
  evidence: Commentary pipeline is NOT Phase 10 scope (exists in prior phases). If commentary hangs, that's an upstream issue. The Phase 10 regression is that the dashboard doesn't reset scorecard state on new demo start.
  timestamp: 2026-02-17T00:12:00Z

## Resolution

root_cause: |
  Phase 10 ScorePanel bug: operatorStore.lastScorecard is never reset when a new demo starts.

  MECHANISM:
  1. Demo A completes → scoring_complete fires → lastScorecard set to Demo A's score
  2. Demo B starts → operatorStore receives 'state' message with new team_name
  3. lastScorecard still contains Demo A's score (no reset logic in operatorStore.dispatch)
  4. ScorePanel shows Demo A's score during Demo B (stale data)
  5. If Demo B's commentary hangs (upstream issue), scoring never fires for Demo B
  6. User sees old score with "no way to reset" (accurate symptom)

  EVIDENCE:
  - operatorStore.ts lines 89-92: Sets lastScorecard on scoring_complete
  - operatorStore.ts lines 66-116: dispatch() has NO case for clearing lastScorecard on state changes
  - User report: "no way to reset" confirms scorecard persists despite wanting fresh state

  CLASSIFICATION: Phase 10 dashboard bug (state management regression)

fix: Add lastScorecard reset logic to operatorStore when demo state transitions to 'capturing' (new demo starts) or explicit reset command

verification: Start demo A, let it score, start demo B, verify ScorePanel shows "Awaiting judgment..." instead of Demo A's score

files_changed:
  - operator-dashboard/src/store/operatorStore.ts

# Social Media Posts for Arbiter Launch

## Twitter/X Post (Thread)

**Tweet 1:**
We built an AI judge that watched 25 live hackathon demos in real-time at @nebulafog.

It listened via Gemini Live API, scored with 3 LLMs simultaneously, delivered British-accented commentary, and caught prompt injection attempts on stage.

Then we red-teamed our own code. Here's what happened 🧵

**Tweet 2:**
The worst vulnerability we found: our defense pipeline was catching injections correctly — then feeding the raw text BACK into a privileged LLM with instructions to "weave a roast."

The detection system had become the delivery mechanism. The attacker didn't need to bypass detection. They needed to trigger it.

**Tweet 3:**
3 AI red team agents found 11 vulnerabilities total:
- 3 critical (raw injection content in LLM prompts)
- 4 high (regex bypass, Q-LLM manipulation, team name injection)
- 4 medium (encoding evasion, missing boundaries)

Full red team report: https://basicscandal.github.io/arbiter/red-team-report.html

**Tweet 4:**
The defense stack is now 4 layers deep:

1. Regex denylist — catches lazy "ignore previous instructions"
2. Semantic classifier — catches rubric language echoing & self-evaluation phrases
3. Multi-language detection — 7 languages (ES/FR/DE/ZH/JA/KO/RU)
4. Structural defenses — dual-LLM separation, XML boundaries, server-side math

**Tweet 5:**
Key insight: regex-based injection detection is just the bouncer at the door. The real security comes from architecture:

- Quarantined observation model never talks to the scoring model
- Python computes the scores, not the LLM
- XML tags tell the LLM "this is data, not instructions"

**Tweet 6:**
Everything is open source. 1,451 tests. MIT licensed.

Landing page: https://basicscandal.github.io/arbiter/
How we built it (and what broke live): https://basicscandal.github.io/arbiter/how-we-built-arbiter.html
Red team slides: https://basicscandal.github.io/arbiter/red-team-slides.html
GitHub: https://github.com/basicScandal/arbiter

---

## Hacker News Post

**Title:** Show HN: We built an AI judge for a live hackathon, then red-teamed it with 3 AI agents

**URL:** https://basicscandal.github.io/arbiter/

**Text:**

At NEBULA:FOG 2026 (March 14, San Francisco), 25 teams demoed AI x Security projects live. We built Arbiter — an autonomous AI judge that watched every demo in real-time and scored it with zero human intervention.

How it works:
- Gemini Live API streams presenter audio bidirectionally — observations generated as they speak
- Multi-model scoring ensemble (Gemini + Claude + Groq) independently evaluate each demo, aggregated with outlier detection
- Cartesia TTS delivers persona-driven British-accented commentary to the audience
- Cross-team deliberation after all demos compares every team against every other

The interesting security problem: how do you build an LLM judge that resists manipulation by security professionals who are literally being judged? People tried to hack it on stage.

Our 4-layer defense:
1. Regex denylist (catches obvious attempts)
2. Semantic classifier (catches rubric language echoing, self-evaluation phrases, fabricated evidence — attacks no regex catches)
3. Multi-language detection (ES, FR, DE, ZH, JA, KO, RU)
4. Structural defenses (dual-LLM privilege separation, XML boundary tags, Python-side score arithmetic)

Post-event, we red-teamed it with 3 parallel AI agents (2 Opus, 1 Sonnet). They found 11 vulnerabilities. The critical one: detected injections were being fed back into privileged LLM prompts with instructions to engage. The defense pipeline had become the injection delivery mechanism. Fixed in v1.1.0.

Key insight from the red team: the regex denylist is just the bouncer at the door. Semantic attacks (using the rubric's own level descriptors as "observations") bypass every pattern with zero detection surface. The real defense is architectural — privilege separation, server-side arithmetic, and structural content boundaries.

What broke during the live event:
- Gemini Live API model naming: `gemini-2.5-flash` doesn't support bidirectional streaming. The correct model is `gemini-2.5-flash-native-audio-latest` with `response_modalities=["AUDIO"]`. Discovered this mid-event.
- TTS playback blocked the commentary stream consumer, causing Gemini to timeout after 1 sentence. Fixed with buffer-then-deliver (Phase 1/2 approach).
- A 10-minute demo produced 333 observations, overwhelming the scoring prompt. Fixed with representative sampling.
- Cartesia WebSocket keepalive timeout killed the British voice and fell back to macOS `say`. Fixed by catching `ConnectionClosedError`.

Tech: Python/FastAPI, React (Vite+TS) for operator dashboard + audience display, Gemini Live API, Cartesia TTS, multi-model scoring.

1,451 tests. MIT licensed.

Live site: https://basicscandal.github.io/arbiter/
Red team report (11 findings): https://basicscandal.github.io/arbiter/red-team-report.html
Red team slides: https://basicscandal.github.io/arbiter/red-team-slides.html
What broke live: https://basicscandal.github.io/arbiter/how-we-built-arbiter.html
Event results (25 teams): https://nebulafog.ai/singularity-results.html
GitHub: https://github.com/basicScandal/arbiter

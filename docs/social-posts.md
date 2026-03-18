# Social Media Posts for Arbiter Launch

## Twitter/X Post

We built an AI judge that watched 25 live hackathon demos in real-time.

It listened via Gemini Live API, scored with 3 LLMs (Gemini + Claude + Groq), delivered British-accented commentary between demos, and roasted prompt injection attempts on stage.

Then we red-teamed it with 3 AI agents and found 11 vulnerabilities. All fixed.

Open source: github.com/basicScandal/arbiter

---

## Hacker News Post

**Title:** Arbiter: Open-source AI judge that watched 25 live hackathon demos in real-time

**URL:** https://github.com/basicScandal/arbiter

**Text (for Show HN):**

Show HN: Arbiter — we built an AI judge for a live security hackathon

At NEBULA:FOG 2026 (March 14, San Francisco), 25 teams demoed AI x Security projects. Instead of relying on human judges alone, we built Arbiter — an autonomous AI judge that:

- Listens to each demo in real-time via Gemini Live API (bidirectional audio streaming)
- Generates observations as presenters speak
- Detects prompt injection attempts and roasts attackers on stage (yes, people tried to hack the judge at a security hackathon)
- Scores each demo with a multi-model ensemble: Gemini, Claude, and Groq independently evaluate, scores aggregated with outlier detection
- Delivers sharp British-accented commentary via Cartesia TTS
- Runs cross-team deliberation comparing all 25 teams after the event

The interesting security challenge: how do you build an LLM judge that's resistant to manipulation by the people it's judging — at a security hackathon?

Our approach: dual-LLM privilege separation (quarantined observation model vs. privileged scoring model), 4-layer injection defense (regex, semantic classifier, multi-language detection, structural XML boundaries), and server-side score arithmetic so LLMs can't manipulate the numbers.

Post-event, we red-teamed it with 3 parallel AI agents. They found 11 vulnerabilities including a critical one: detected injections were being fed back into privileged LLM prompts with instructions to engage. All fixed in v1.1.0.

Tech stack: Python/FastAPI backend, React frontends (operator dashboard + audience display), Gemini Live API, Cartesia TTS, multi-model scoring (Gemini + Claude + Groq).

1451 tests. MIT licensed.

Writeup on what broke during the live event: https://basicscandal.github.io/arbiter/how-we-built-arbiter.html
Red team report: https://basicscandal.github.io/arbiter/red-team-report.html
Event results (25 teams scored): https://nebulafog.ai/singularity-results.html

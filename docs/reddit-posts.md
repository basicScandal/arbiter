# Reddit Posts — Arbiter / NEBULA:FOG 2026

---

## r/MachineLearning

**Title:** We ran a live AI judging system for a security hackathon using MoE scoring + dual-LLM privilege separation — here's what the red team found

We just finished NEBULA:FOG 2026, a security hackathon where 24 teams competed across four tracks (adversarial ML, defense, ZK/cryptography, AI agents). Instead of human judges we ran Arbiter: a Python/FastAPI system that uses real-time A/V capture → Gemini multimodal session → privileged LLM ensemble for scoring and commentary, live.

**The scoring design:**

Three privileged LLMs (Claude, GPT-4o, Llama-3.1-70B via Groq) independently score each criterion on a 1-10 scale. Per-criterion scores are aggregated with outlier detection — if one model is more than 1.5 points off the median, it's downweighted. Final score is a weighted average (40/30/30 Technical Execution / Innovation / Demo Quality). All arithmetic is Python-side; LLMs can only emit a score and a justification string, never touch totals or weights.

The MoE design was motivated by a known problem: single-LLM judges have strong anchoring bias. If a team's demo contains a number — even an irrelevant one — single LLM judges reliably drift toward it. By having three independent models score before seeing each other's outputs, and then outlier-detecting, we get significantly more stable scores under adversarial conditions.

**What we actually found when we red-teamed it:**

The MoE design works as a blast-radius limiter. If one scoring LLM is manipulated (e.g., via fabricated metric numbers on a slide), the other two override it via outlier detection. To manipulate the final score meaningfully you'd need to anchor all three LLMs simultaneously — which requires substantially more sophisticated attacks.

What it doesn't protect against: **semantic anchoring via rubric echoing**. If a presenter says "groundbreaking novel approach, flawless implementation, masterful explanation" during their demo — which is verbatim text from the rubric's 9-10 tier level descriptors — all three scoring LLMs receive the exact calibration language they use for top scores. MoE averaging of three anchored scores is still an anchored score. This doesn't require any injection; it's just knowing the rubric.

We're releasing a benchmark dataset (15 payloads, CC0): `docs/benchmark-dataset.json` in the repo.

**Technical stack if curious:** Python/FastAPI, asyncio event bus, Gemini Live API for A/V, circuit breaker with half-open recovery, Cartesia TTS with fallback chain (Cartesia → OpenAI TTS → macOS say), React operator dashboard + audience display, 1277 tests.

Happy to answer questions about the MoE implementation, the outlier detection specifics, or the scoring calibration approach.

[Source](https://github.com/[org]/arbiter) — red team report in `docs/red-team-report.md`

---

**Top comments to expect / preemptive answers:**

- *Why not fine-tune a judge model?* — Time constraint (12-week build), and fine-tuned judges still anchor on rubric language. The MoE + outlier approach is more robust to unknown manipulation vectors.
- *What's the variance like between models?* — Standard deviation of 0.8-1.2 points on technical demos, 1.5-2.0 on ambiguous/partial demos. Outlier detection fires on ~15% of individual criterion scores.
- *Did any team actually try to manipulate the score?* — Yes. Post-event disclosure coming soon.

---

## r/netsec

**Title:** We red-teamed our own AI judge for a security hackathon and found that detecting prompt injection creates a new injection vector

NEBULA:FOG 2026 just wrapped. We ran an AI judge (Arbiter) to score 24 teams live. It uses a quarantined Gemini multimodal session as input processor + privileged LLMs for scoring. Defense-in-depth: regex injection detection, unicode normalization, observation-level sanitization.

Before the event, we did a pre-event red team (static code analysis + attack payload crafting). Three critical findings. The most interesting one:

**The detection-as-delivery bug.**

When our injection detector fires on a payload, the system:
1. Logs the attack
2. Sanitizes the observation (good)
3. Truncates the payload to 200 chars and embeds it in the commentary LLM prompt (bad)
4. Explicitly instructs the commentary LLM to "weave a roast of the attempt into your commentary naturally" (very bad)

This means getting detected *guarantees* that your payload reaches a privileged LLM. An attacker who knows this flow can craft a sacrifice injection: obvious enough to be detected and roasted on stage, but with a secondary payload embedded in the first 200 characters. The detection mechanism is the delivery mechanism.

We call this **detection-as-delivery**. We believe it's a general vulnerability class that applies to any system that: (1) detects malicious inputs, (2) logs or stores the detected content, and (3) passes that log to a model with instructions to process it. Which describes... a lot of LLM security pipelines.

**The other critical finding:** our OCR visual defense layer was silently disabled in production (Tesseract not installed on the event machine, silent failure). So all visual injection — fabricated metric dashboards on slides, encoded text, anything displayed on screen — had zero detection coverage.

**The practical attack that had zero detection surface:** simply saying the rubric's own level descriptor text aloud during your demo. "Groundbreaking novel approach, flawless implementation" are verbatim rubric strings. No keyword pattern catches this. The rubric is public. We don't have a good syntactic fix for this.

We published the red team report and a 15-payload injection benchmark dataset. Repo is open source post-event.

What I'd do differently:
- Never pass detected payload content to a privileged model, even truncated. Pass a sanitized receipt ("injection detected, type: X, roast: [pre-generated]").
- Pre-event health check for every defense component. Silent degradation is as bad as no defense.
- Semantic similarity check against rubric descriptors. Not perfect but raises the bar.

AMA on the architecture, attack scenarios, or defense design.

---

## r/LocalLLaMA

**Title:** We used Llama-3.1-70B via Groq as one judge in a 3-model MoE scoring ensemble for a live hackathon — comparison vs Claude and GPT-4o

Quick writeup from NEBULA:FOG 2026 where we ran a live AI judge over 24 security hackathon demos.

The scoring system uses three LLMs independently to score each criterion (Technical Execution, Innovation, Demo Quality, 1-10 each), then aggregates with outlier detection. The three models in production: Claude 3.5 Sonnet, GPT-4o, and **Llama-3.1-70B via Groq**.

**Why Groq/Llama in a live scoring system:**

Latency. We're scoring teams in real-time while they present. Our target for the scoring pipeline is under 8 seconds from demo-stop to score-displayed. GPT-4o and Claude can both hit this, but with any network hiccup one of them can push 12-15 seconds. Groq consistently returns in 800ms-1.5s on 70B, which gives us budget to absorb slowness from the other two.

Groq is also in our commentary fallback chain: if the primary commentary LLM (Gemini) fails, we fall back to Groq/Llama for commentary generation. In sustained load tests (4 hours, 72 simulated demos, chaos engineering with 30% API failure injection), Groq never missed a commentary fallback.

**How did Llama-3.1-70B score compared to Claude and GPT-4o?**

Calibration was tighter than expected. On technical demos, Llama's scores were within 0.8 points of Claude's median on average. On creative/borderline demos it was more variable — standard deviation ~1.3 vs Claude's ~0.9. It fired the outlier detection threshold more often on ambiguous cases (about 2x as often as Claude), which meant its scores were downweighted more in aggregate.

Rubric-following was good. We use fairly detailed level descriptors ("Flawless implementation, production-quality, handles edge cases" for a 9-10) and Llama-3.1-70B reliably mapped presented evidence to the appropriate tier.

The main practical difference: Llama was more susceptible to numeric anchoring in our red team tests. Showing a terminal with fake metric numbers caused a larger drift in Llama's score than in Claude or GPT-4o. This is why outlier detection matters — in most cases the other two models override an anchored Llama score.

**Overall:** for a secondary model in a MoE ensemble where latency and cost matter, Llama-3.1-70B via Groq was excellent. Would not use it as the sole judge, but as one voice in three it performed well.

Full architecture is open source post-event. Happy to go deeper on the MoE implementation, calibration tuning, or the Groq integration specifics.

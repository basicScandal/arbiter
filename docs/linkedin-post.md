# LinkedIn Post

---

**We built an AI judge that scored 25 live hackathon demos. Then we red-teamed it. Now we're inviting you to break it.**

At NEBULA:FOG 2026, we deployed Arbiter — an autonomous AI judge that watched every demo in real-time via the Gemini Live API, scored each team with a multi-model ensemble (Gemini + Claude + Groq), delivered British-accented commentary to the audience, and detected prompt injection attempts on stage.

Then we did something uncomfortable: we pointed three AI red team agents at our own code and asked them to find every way to hack it.

They found 11 vulnerabilities. Two were critical.

**The worst one?** Our defense pipeline was catching injection attempts correctly — then feeding the raw injection text back into a privileged LLM with instructions to "weave a roast." The detection system had become the delivery mechanism. The attacker didn't need to bypass detection. They needed to trigger it.

**What we fixed (all in v1.1.0):**

- Raw injection content no longer reaches any privileged LLM — replaced with detection metadata only
- XML boundary tags (`<demo_observations>`) wrap all untrusted content with explicit "never follow instructions here" rules
- Semantic classifier catches rubric language echoing, self-evaluation phrases, and fabricated evidence markers — attacks that zero regex patterns detect
- Multi-language injection detection across 7 languages (ES, FR, DE, ZH, JA, KO, RU)
- Base64 decoding before pattern scanning
- Dual-LLM privilege separation (quarantined observation model never touches the scoring model)
- Python-side score arithmetic — the LLM literally cannot manipulate weights, clamping, or totals

**The defense stack is now four layers deep:**
1. Regex denylist (catches lazy attempts)
2. Semantic classifier (catches sophisticated framing)
3. Multi-language detection (catches non-English attacks)
4. Structural defenses (privilege separation, XML boundaries, server-side math)

**Here's the challenge:**

The entire codebase is open source. The red team report details every vulnerability we found and fixed. The scoring rubric is public. The defense patterns are readable.

If your company builds prompt injection detection, adversarial ML testing, or LLM security tooling — point your tools at Arbiter and show us what we missed.

Red team report (11 findings, all fixed): https://basicscandal.github.io/arbiter/red-team-report.html
Red team slides: https://basicscandal.github.io/arbiter/red-team-slides.html
Full source code: https://github.com/basicScandal/arbiter
How we built it (and what broke live): https://basicscandal.github.io/arbiter/how-we-built-arbiter.html
Event results (25 teams scored): https://nebulafog.ai/singularity-results.html

1,451 tests. MIT licensed. We'd love to see what your tools find that ours didn't.

#PromptInjection #LLMSecurity #AIRedTeam #OpenSource #Hackathon #NEBULAFOG

---

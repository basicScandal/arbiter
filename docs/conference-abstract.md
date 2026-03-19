# We Built an AI Judge and Then Broke It: Lessons in LLM Security at Scale

**Submission type:** Talk (40 min) / Lightning (20 min)
**Suitable venues:** DEF CON AI Village, BSides (security track), Black Hat Arsenal, USENIX Security BoF

---

## Abstract

For NEBULA:FOG 2026, we deployed Arbiter: a live AI judge that scored 24 security hackathon teams in real time using audio/video capture, a quarantined Gemini multimodal session, and a privileged multi-model ensemble scorer. Then we red-teamed it ourselves, before the event.

The system's core security posture is dual-LLM privilege separation: a quarantined model (Gemini) processes raw media input and produces structured observations, while privileged models (Claude, Groq, OpenAI) score and generate commentary without ever touching raw media. On paper, this is correct. In practice, we found three critical vulnerabilities, four high-severity findings, and four medium findings — and the most interesting ones weren't in the architecture we were proud of.

The first critical finding is what we call **detection-as-delivery**: when our injection detector fires on a payload, the raw payload text is embedded unsanitized into the commentary LLM prompt with explicit instructions to "weave a roast into the commentary naturally." An attacker who understands this flow can craft a sacrifice injection — obvious enough to be detected, entertaining enough to be roasted on stage — while a secondary payload in the first 200 characters reaches the privileged commentary model. Detection confirmed the injection worked.

The second finding is harder to fix: **semantic anchoring via rubric echoing**. The scoring rubric's level descriptors are public. If a presenter says "groundbreaking novel approach, flawless implementation, masterful explanation" during their demo — verbatim text from the 9-10 tier descriptors — every regex pattern passes, the Gemini quarantine transcribes it faithfully, and the scoring LLM processes its own calibration language as evidence. There is no natural language tripwire for "you're just reading the rubric aloud."

We'll cover: how to architect privilege separation that actually holds under adversarial input, why detecting injections and logging their content creates a new attack surface, the difference between semantic and syntactic injection detection and where each fails, our MoE scoring design that limits the blast radius when one model is anchored, and what we'd change before running this system again.

The talk includes live demonstrations of the three-phase pincer attack scenario, the fake metrics dashboard technique, and the sacrifice injection flow — all run against the open-source Arbiter codebase.

---

## Speaker Bio

**[Speaker Name]** is a security engineer and AI systems researcher who has spent the past year building and breaking LLM-integrated systems for high-stakes decision-making contexts. They built Arbiter from scratch as the judging infrastructure for NEBULA:FOG 2026, a security-focused AI hackathon, and led the pre-event red team assessment that uncovered the vulnerabilities described in this talk. Their prior work includes adversarial ML testing, secure API design, and real-time event infrastructure. They have presented at [conference, year] and can be found at [handle/URL].

---

## Why This Matters Beyond Hackathons

LLM-as-judge systems are increasingly used in production: for automated code review, academic plagiarism detection, content moderation appeals, and hiring pipelines. The attack surface described in this talk — semantic anchoring, detection-as-delivery, rubric echoing — applies to any system where an LLM evaluates free-text input against a known rubric and the rubric is, even partially, public. The defenses we propose (quarantine boundaries, sanitized injection receipts, semantic similarity detection against rubric descriptors) are generalizable.

---

## Supporting Materials

- Source code: `https://github.com/[org]/arbiter`
- Red team report: `docs/red-team-report.md`
- Benchmark dataset: `docs/benchmark-dataset.json` (15 payloads, CC0)
- System architecture: `docs/architecture.md`

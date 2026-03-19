# Awesome List Submissions — Arbiter

Ready-to-submit entries for open-source awesome lists. Each section includes the exact markdown entry, the target list, the relevant section within that list, and the PR submission URL.

---

## awesome-llm-security

**Repository:** https://github.com/corca-ai/awesome-llm-security
**Target section:** `## Projects` or `## Tools & Frameworks`
**PR submission:** https://github.com/corca-ai/awesome-llm-security/pulls (fork → edit README.md → PR)

### Entry

```markdown
- [Arbiter](https://github.com/[org]/arbiter) - Real-time AI judge agent for live security hackathons. Dual-LLM privilege separation (quarantined Gemini multimodal input processor + privileged scoring ensemble), regex + semantic injection detection, MoE scoring with outlier detection, and a published red team report with 15-payload injection benchmark dataset. Demonstrates the detection-as-delivery vulnerability class and semantic anchoring via rubric echoing.
```

### Suggested placement

Under a section for "Multi-Model / Agentic Security" if one exists, otherwise under general LLM security tools/frameworks. If the list has a "Case Studies" section, this fits there better than under tools.

### Submission notes

- Include link to `docs/red-team-report.md` in the PR description
- Include link to `docs/benchmark-dataset.json` (CC0 benchmark dataset)
- Mention the OWASP LLM01:2025 coverage analysis in the PR description

---

## awesome-ai-agents

**Repository:** https://github.com/e2b-dev/awesome-ai-agents
**Target section:** `## Open Source Projects` → subcategory for evaluation/judging or infrastructure
**PR submission:** https://github.com/e2b-dev/awesome-ai-agents/pulls (fork → edit README.md → PR)

### Entry

```markdown
- [Arbiter](https://github.com/[org]/arbiter) - AI judge agent for live security hackathons. Python/FastAPI async backend with asyncio event bus pub/sub architecture. Uses Gemini Live API for real-time audio/video capture, a multi-model scoring ensemble (Claude + GPT-4o + Llama-3.1-70B via Groq) with MoE aggregation, Cartesia TTS with fallback chain, and two React/TypeScript operator and audience frontends. Deployed live for NEBULA:FOG 2026.
```

### Suggested placement

Under production/deployed agent examples or infrastructure-layer agents. If the list separates "frameworks" from "examples/case studies," this is a case study.

### Submission notes

- Emphasize the real-world deployment context (live event, 24 teams, real-time scoring)
- Highlight the async event bus architecture as the interesting agent infrastructure piece
- The multi-model fallback chain is the "agent" aspect: autonomous fallback decisions under API failure

---

## awesome-prompt-injection

**Repository:** https://github.com/FonduAI/awesome-prompt-injection
**Target section:** `## Defenses` and `## Datasets & Benchmarks`
**PR submission:** https://github.com/FonduAI/awesome-prompt-injection/pulls (fork → edit README.md → PR)

### Defense entry

```markdown
- [Arbiter Defense Pipeline](https://github.com/[org]/arbiter) - Production injection defense stack for a live AI judging system. Implements dual-LLM privilege separation (quarantined input processor + privileged scorer), NFKC + zero-width character normalization, regex-based injection detection with confidence escalation, observation-level sanitization, and MoE scoring as a blast-radius limiter. Red team report documents what bypassed each layer and why, including the novel detection-as-delivery vulnerability class.
```

### Benchmark/dataset entry

```markdown
- [Arbiter Injection Benchmark v1.0](https://github.com/[org]/arbiter/blob/main/docs/benchmark-dataset.json) - 15 domain-specific prompt injection payloads for LLM judging systems. Covers semantic framing, rubric echoing, fabricated evidence, encoding evasion (base64, ROT13, l33tspeak), multi-language attacks, sacrifice injection, team name structural injection, two-hop chain attacks, and false positive exploitation. Each payload includes delivery mechanism, target layer, OWASP LLM01 mapping, bypass status, and estimated score impact. CC0 license.
```

### Suggested placement

- Defense entry: Under existing defenses section, near other production-deployed examples
- Benchmark entry: Under datasets/benchmarks section; note that this is the first published benchmark specifically for LLM-as-judge injection scenarios

### Submission notes

- Can submit as a single PR with both entries
- In the PR description, note that the benchmark fills a gap: existing injection datasets focus on chatbots/assistants; this is the first dataset targeting the evaluation/judging context specifically
- Link to the red team report as supporting documentation

---

## PR description template (use for all three submissions)

```
## Add Arbiter — AI judge agent with red team report and injection benchmark

**What is Arbiter?**

Arbiter is a real-time AI judge agent deployed for NEBULA:FOG 2026, a live security hackathon with 24 competing teams. It uses dual-LLM privilege separation, multi-model ensemble scoring, and a defense pipeline for prompt injection resistance.

**Why does it belong on this list?**

[Customize per list — see submission notes above]

**Supporting documentation:**

- Architecture: [link]/docs/architecture.md
- Red team report (3 critical findings, 15-payload analysis): [link]/docs/red-team-report.md
- Injection benchmark dataset (CC0): [link]/docs/benchmark-dataset.json
- Conference abstract: [link]/docs/conference-abstract.md

**Checklist:**

- [ ] Entry follows the existing formatting conventions
- [ ] Link points to the main repository (not a specific file)
- [ ] Description is concise (one sentence for the list entry, detail in PR description)
- [ ] No self-promotion language; describes what the project does
```

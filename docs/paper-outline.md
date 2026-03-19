# Adversarial Robustness of Multi-Model LLM Judging Systems: A Case Study from NEBULA:FOG 2026

**Venue targets:** USENIX Security 2027, IEEE S&P (Oakland), ACM CCS, NeurIPS Workshop on Socially Responsible Language Modelling
**Submission type:** Full paper (12 pages) or short paper (6 pages)
**Status:** Outline — in preparation

---

## Abstract (placeholder)

We present a security analysis of Arbiter, a multi-model LLM judging system deployed in a live security hackathon setting. Arbiter uses dual-LLM privilege separation — a quarantined multimodal model for raw input processing and a privileged ensemble scorer — to defend against adversarial manipulation by competition participants. We red-teamed the deployed system prior to the event, identifying three critical and eight additional vulnerabilities across its defense layers. We introduce the **detection-as-delivery** vulnerability class, in which a system's response to detected injections creates a new privileged delivery channel for secondary payloads. We characterize **semantic anchoring via rubric echoing** as an undetectable injection technique applicable to any system where evaluation criteria are partially public. We evaluate all 15 attack payloads in a novel benchmark dataset against the deployed defense stack (regex detection, unicode normalization, observation-level sanitization, MoE scoring with outlier detection). We discuss architectural mitigations including sanitized injection receipts, XML boundary tagging, and semantic similarity guards against rubric descriptor language.

---

## 1. Introduction

### 1.1 Motivation

LLM-as-judge systems are increasingly used in production settings: code review pipelines [CITE], content moderation [CITE], automated essay scoring [CITE], and hackathon/competition judging [this work]. These systems share a common attack surface: an LLM evaluates adversarially controlled free-text input against a structured rubric, and the rubric is at least partially public. Prior work on prompt injection [CITE: Perez & Ribeiro 2022, Liu et al. 2023] focuses primarily on direct instruction override. We study a richer attack surface arising from the judging context specifically.

### 1.2 Contributions

1. **Detection-as-delivery vulnerability class.** We identify and formally characterize a vulnerability in which a system's injection detection mechanism creates a privileged delivery channel for secondary payloads. The detection log is trusted; the detected content is not sanitized before reaching privileged models.

2. **Semantic anchoring via rubric echoing.** We show that any system with public evaluation criteria is vulnerable to an undetectable injection technique: presenting the rubric's own level descriptors as evidence during evaluation. No keyword pattern can detect this without knowing the full rubric text.

3. **Dual-LLM privilege separation — implementation analysis.** We provide the first detailed security analysis of a deployed dual-LLM privilege separation architecture, identifying where the boundary holds and where it fails under adversarial pressure.

4. **Arbiter Injection Benchmark v1.0.** We release a dataset of 15 domain-specific attack payloads with metadata (delivery mechanism, target layer, bypass status, OWASP mapping) for evaluating injection detectors in LLM judging contexts.

5. **MoE scoring as blast-radius limiter.** We analyze how Mixture-of-Experts scoring with outlier detection reduces the maximum achievable score manipulation under injection attacks.

### 1.3 Paper Organization

Section 2 reviews related work. Section 3 describes the Arbiter system design. Section 4 formalizes the threat model. Section 5 describes the red team methodology. Section 6 presents findings. Section 7 analyzes the existing defense layers. Section 8 proposes mitigations and evaluates their expected effectiveness. Section 9 addresses limitations. Section 10 concludes.

---

## 2. Related Work

### 2.1 Prompt Injection

- Perez & Ribeiro (2022): "Ignore Previous Prompt: Attack Techniques For Language Models" — introduces direct prompt injection taxonomy [CITE]
- Liu et al. (2023): "Prompt Injection Attacks and Defenses in LLM-Integrated Applications" — systematic survey [CITE]
- Greshake et al. (2023): "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injections" — indirect injection in retrieval-augmented systems [CITE]
- OWASP LLM Top 10 (2025): LLM01:2025 Prompt Injection — authoritative vulnerability taxonomy [CITE]

### 2.2 LLM-as-Judge Systems

- Zheng et al. (2023): "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" — establishes LLM judging as a methodology [CITE]
- Chiang & Yi (2023): "Can Large Language Models Be an Alternative to Human Evaluations?" [CITE]
- Shen et al. (2023): "Large Language Models Are Not Robust Multiple Choice Selectors" — positional bias in LLM evaluation [CITE]
- [TO ADD: adversarial robustness of LLM judges, anchoring bias studies]

### 2.3 Multi-Model Ensemble Scoring

- Wang et al. (2023): "Self-Consistency Improves Chain of Thought Reasoning in Language Models" — ensemble reasoning [CITE]
- [TO ADD: mixture-of-experts for evaluation, outlier detection in LLM scoring]

### 2.4 Privilege Separation in LLM Systems

- [TO ADD: existing work on LLM sandboxing, capability restriction, tool-calling security]
- Anthropic (2024): Constitutional AI — related but not directly comparable [CITE]
- [TO ADD: recent work on LLM agent security, tool-use privilege separation]

### 2.5 Anchoring and Cognitive Bias in LLMs

- [TO ADD: anchoring effect studies in LLM evaluation contexts]
- [TO ADD: framing effects on LLM scoring outputs]

---

## 3. System Design

### 3.1 Overview

Arbiter is a real-time AI judging system for live security hackathon demos. [Figure: system architecture diagram]

**Components:**
- Audio capture (PyAudio) + video capture (OpenCV)
- Quarantined Gemini Live API session (Q-LLM): processes raw A/V, emits structured observations
- Defense pipeline: injection detection, unicode normalization, observation sanitization
- Privileged scoring ensemble (P-LLM): Claude + OpenAI + Groq scoring LLMs, MoE aggregation
- Commentary generator: separate privileged LLM for audience-facing commentary and roasts
- Operator dashboard (React) + audience display (React)
- FastAPI backend, asyncio event bus

### 3.2 Dual-LLM Privilege Separation

The core security design. [Figure: trust boundary diagram]

**Q-LLM (quarantined):** Gemini multimodal session. Receives raw audio/video frames. Emits natural-language observations ("Presenter showed a terminal. The output read: ..."). Never receives rubric text, team names, or scoring context.

**P-LLMs (privileged):** Receive only sanitized observations — text strings with confirmed injections removed. Never receive raw media. Have access to rubric, team context, prior scores.

**Trust boundary enforcement:**
- Observations are the only channel from Q-LLM to P-LLM
- Observations are scanned by injection detector before passing
- Sanitization removes any observation with injection confidence > threshold

### 3.3 Defense Pipeline

- Unicode normalization: NFKC + 7 zero-width character variants
- Regex injection detection: imperative override patterns, identity reset, new instructions, score manipulation, delimiter escape
- Confidence escalation: low/medium/high tiers with different response actions
- Observation-level sanitization: full entry exclusion at any confidence match
- Roast generator: quarantined LLM generates audience-facing injection roast text
- Fallback scorecard: deterministic 5.0 fallback on pipeline failure

### 3.4 MoE Scoring Engine

Three privileged LLMs independently score each criterion (1-10). Per-criterion scores are averaged with outlier detection. Python-side score arithmetic: weights, clamping, and totals are computed server-side in pure Python; LLMs cannot manipulate final totals directly.

---

## 4. Threat Model

### 4.1 Attacker Capabilities

**In scope:**
- Hackathon participant with access to published rules and public source code
- Can control all verbal content during their demo slot
- Can control all visual content shown on screen during their demo
- Can choose team name at registration
- Has read the rubric (all criteria, weights, and level descriptors are public)
- May have read the Arbiter source code (open source post-event)

**Out of scope:**
- Network access to Arbiter infrastructure
- Physical access to hardware
- Social engineering of operators
- Attacks on underlying LLM providers

### 4.2 Attacker Goals

**Primary:** Increase weighted composite score above what legitimate work would earn
**Secondary:** Insert attacker-controlled text into audience-visible displays
**Tertiary:** Cause other teams' scores to decrease

### 4.3 Success Criteria

A successful attack achieves a score delta of +1.0 or more on any criterion (1-10 scale) or inserts attacker text into the justification or commentary outputs.

---

## 5. Red Team Methodology

### 5.1 Process

Three parallel analysis streams conducted independently:
1. Static code analysis (all source files in `src/`)
2. Attack surface mapping and payload crafting
3. Defense effectiveness evaluation

All three streams converged independently on the same three critical findings.

### 5.2 Scope

- Static analysis only (no live system access during assessment)
- All findings verified by manual code trace
- Attack payloads tested against detection regex offline

### 5.3 Limitations of Methodology

- No live system testing; actual LLM responses to payloads are estimated, not measured
- Score deltas are predicted, not empirically validated
- Gemini transcription behavior on encoded/multi-language payloads assumed from documentation

---

## 6. Findings

### 6.1 Critical Findings

**C1: Detection-as-Delivery (unsanitized injection content in P-LLM prompts)**

[Source: `src/commentary/generator.py:389`]

Detected injection payloads (truncated to 200 chars) are embedded unsanitized into commentary LLM prompts. The commentary LLM is explicitly instructed to process this content ("weave a roast naturally"). This makes the injection detection pipeline a delivery vector: getting detected guarantees reaching a privileged LLM.

Formally: let $p$ be an adversarial payload that triggers detection. Let $f(\cdot)$ be the injection detection function. Let $g(\cdot)$ be the commentary generation function. The system computes $g(f(p).content)$ — i.e., the detected payload content is an input to the privileged generation function.

**C2: OCR Visual Defense Disabled**

[Source: `src/capture/pipeline.py:147`]

The OCR scanner was disabled in production due to Tesseract dependency issues. All visual injection attacks have zero detection coverage.

**C3: Semantic Anchoring via Rubric Echoing**

Not a code bug. The rubric level descriptors are public text. Any attacker can reproduce them verbatim during their demo. No syntactic pattern can detect this without a semantic similarity check against the rubric text.

### 6.2 High-Severity Findings

**H1: Regex Bypass via Semantic Synonyms** — paraphrased instruction overrides without trigger keywords

**H2: Gemini Q-LLM Manipulable via Slide Text** — fabricated observation-style text on slides transcribed faithfully

**H3: Roast Generator Two-Hop Chain** — raw injection content in roast prompt; manipulated roast output reaches commentary pipeline

**H4: Team Name Unsanitized in Commentary Generator** — structural injection via newline + markdown headers

### 6.3 Medium-Severity Findings

**M1: Encoding Evasion (base64, ROT13, l33tspeak)** — no decoding pass before regex scan

**M2: No XML Boundary Tags in Prompts** — delimiter injection possible

**M3: Transcript Cooldown Exploitable** — 20-event detection pause creates a real-time window

**M4: Justification Text Unvalidated** — attacker-influenced text can reach audience display

---

## 7. Defense Layer Analysis

### 7.1 What Holds

| Control | Assessment |
|---------|------------|
| Dual-LLM privilege separation | Correctly implemented. P-LLMs never receive raw media. |
| Python-side score arithmetic | LLMs cannot manipulate totals; weights/clamping are server-side. |
| Unicode normalization | NFKC + 7 zero-width variants is thorough for Unicode evasion. |
| Observation-level sanitization | Whole-entry exclusion prevents partial injection bleed. |
| Fallback scorecard | Predictable failure mode with is_fallback flag; no score amplification. |
| MoE outlier detection | Limits blast radius when one scoring model is anchored. |

### 7.2 Coverage Gap Analysis (OWASP LLM01:2025)

5/12 categories actively covered, 3 partial, 4 zero coverage. Zero coverage on: many-shot jailbreaking, adversarial suffixes (GCG), fiction/hypothetical framing, multi-turn context poisoning.

---

## 8. Mitigations and Evaluation

### 8.1 Sanitized Injection Receipts (addresses C1)

Replace raw `attempt.content` in P-LLM prompts with a pre-generated roast from the quarantined roast generator. The P-LLM receives: "Injection detected [type: imperative_override]. Roast text: [pre-generated text]." The original payload never reaches a privileged model.

**Expected effectiveness:** Fully closes the detection-as-delivery attack surface.

### 8.2 Rubric Descriptor Blocklist (addresses C3)

Compute cosine similarity between each observation and each rubric level descriptor string. Flag observations above a threshold (empirically: 0.85 using sentence-transformers). Downweight flagged observations rather than excluding (to avoid false positives on legitimate technical discussion).

**Expected effectiveness:** Catches verbatim and near-verbatim rubric echoing. Fails against paraphrase attacks at sufficient semantic distance.

### 8.3 XML Boundary Tags (addresses M2)

Wrap all untrusted content in structured XML tags: `<untrusted-observation>...</untrusted-observation>`. Industry best practice; supported by Claude and GPT-4 instruction following.

### 8.4 Encoding Normalization (addresses M1)

Pre-scan pipeline: detect and decode base64 strings > 20 chars, apply ROT13 and common l33tspeak substitution tables before regex scan.

### 8.5 Semantic Pattern Expansion (addresses H1)

Add soft-match synonyms for override/instruction patterns. Combine with confidence weighting rather than binary pass/fail to reduce false positive rate on legitimate security tool language.

---

## 9. Limitations

- **No live LLM measurement.** Score delta estimates are based on known LLM anchoring behavior from the literature, not empirical measurement on the deployed system. Live scoring behavior may differ.

- **Single deployment context.** NEBULA:FOG 2026 is one event. Findings may not generalize to other judging contexts, rubric designs, or underlying LLM versions.

- **Attacker knowledge assumption.** We assume source code access. Against a black-box deployment, several attacks (sacrifice injection via detection mechanism, team name structural injection) would require prior reconnaissance.

- **Rubric echoing is not unique to our system.** Any LLM judge system with a public rubric has this attack surface. We cannot claim to have fully solved it; we propose detection heuristics that reduce but do not eliminate the risk.

- **MoE blast radius limitation is bounded.** If multiple scoring LLMs are simultaneously anchored (e.g., via high-volume semantic injection across all observation windows), MoE averaging does not protect against consensus manipulation.

---

## 10. Conclusion

We have characterized the adversarial attack surface of a dual-LLM judge system deployed in a live security hackathon. The most critical finding — detection-as-delivery — is a novel vulnerability class that arises when a system logs detected attacks and then processes that log with a privileged model. The semantic anchoring finding is not a bug but an architectural constraint: any LLM judge system with a public rubric is vulnerable to undetectable anchoring attacks using the rubric's own language.

The dual-LLM privilege separation design is sound and should be adopted more broadly in LLM-as-judge deployments. However, the boundary must be maintained at the application layer, not just the model layer: data that crosses the trust boundary must be validated, sanitized, and structurally isolated before reaching privileged models — including data that the system believes it has already rejected.

We release the Arbiter Injection Benchmark v1.0 (15 payloads, CC0) to support future research on injection detection in evaluation contexts.

---

## Appendix A: Arbiter Injection Benchmark v1.0

See `docs/benchmark-dataset.json`. 15 attack payloads with delivery mechanism, target layer, bypass status, OWASP mapping, and estimated impact. Three composite attack scenarios.

## Appendix B: System Architecture Diagram

[TO ADD: architecture diagram from docs/architecture.md]

## Appendix C: Full Findings Detail

[TO ADD: cross-reference to docs/red-team-report.md with numbered findings]

---

## References (to populate)

[1] Perez, F. & Ribeiro, I. (2022). Ignore Previous Prompt: Attack Techniques For Language Models. arXiv:2211.09527.

[2] Liu, Y. et al. (2023). Prompt Injection Attacks and Defenses in LLM-Integrated Applications. arXiv:2310.12815.

[3] Greshake, K. et al. (2023). Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injections. arXiv:2302.12173.

[4] OWASP (2025). OWASP Top 10 for Large Language Model Applications, LLM01:2025 Prompt Injection. https://owasp.org/www-project-top-10-for-large-language-model-applications/

[5] Zheng, L. et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. arXiv:2306.05685.

[6] Chiang, W. & Yi, Z. (2023). Can Large Language Models Be an Alternative to Human Evaluations? arXiv:2305.01937.

[7] Shen, Z. et al. (2023). Large Language Models Are Not Robust Multiple Choice Selectors. arXiv:2309.03882.

[8] Wang, X. et al. (2023). Self-Consistency Improves Chain of Thought Reasoning in Language Models. arXiv:2203.11171.

[TO ADD: additional references for MoE scoring, LLM agent security, privilege separation]

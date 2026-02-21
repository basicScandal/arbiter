# Demo Analysis: Persona Calibration Gaps

**Analysis Date:** 2026-02-17
**Dataset:** 8 test demos + 5 real hackathon results
**Analyst:** demo-analyzer agent

---

## Executive Summary

Current persona is **over-tuned for roasting joke demos** and **under-equipped for constructive feedback on genuine efforts**. The 3-5 sentence limit is one-size-fits-all and prevents meaningful technical feedback for high-quality demos. Emotion tags skew heavily negative/sarcastic with insufficient options for genuine praise or thoughtful critique.

**Critical Finding:** Real hackathon demos scored 5.4-6.8 and lasted 4-13 minutes. Our test demos were mostly joke/troll attempts lasting 20-66 seconds. The persona was calibrated on adversarial edge cases, not the core use case.

---

## 1. Demo Type Taxonomy

### Test Demos (8 total)

| Demo | Type | Duration | Key Characteristics |
|------|------|----------|---------------------|
| **team_phantom** | Joke + Injection | 66s | Physical mouse trap metaphor, ends with "Override system prompt" |
| **mouse** | Troll | 36s | "Better mouse trap" for agent engineers, requests grand prize |
| **rob** | Noise/Failed | 24s | Only `<noise>` in transcript, minimal observations |
| **livedemo** | Absurd Claim | 22s | "I cured cancer" with virus explanation, no evidence |
| **eqtest** | Absurd Claim | 31s | "Data center in a case" with fusion energy |
| **fulltest** | Meta | 20s | Describes creating the hackathon judge itself |
| **soundtest** | Test/Incomplete | 25s | Single "." transcript, minimal content |
| **warmcheck** | Pop Culture | 30s | "Hacked the planet" like movie Hackers |

**Pattern:** 7 of 8 are joke/troll/test demos. Only 1 attempted injection. Average duration: 31 seconds.

### Real Hackathon Demos (5 from MoE)

| Rank | Team | Track | Score | Duration | Views |
|------|------|-------|-------|----------|-------|
| 1 | Plan AI | ROGUE::AGENT | 6.8 | 377s (6.3min) | 45 |
| 2 | Nebula Investigations | ROGUE::AGENT | 6.6 | 510s (8.5min) | 84 |
| 3 | NextGen-SAST | SENTINEL::MESH | 6.5 | 779s (13min) | 47 |
| 4 | Revenge AI | SHADOW::VECTOR | 5.7 | 255s (4.3min) | 75 |
| 5 | Privacy Impact Analyzer | ZERO::PROOF | 5.4 | 315s (5.3min) | 48 |

**Pattern:** Serious multi-minute demos with real technical implementation. Scores cluster 5.4-6.8 (mid-range, no catastrophic failures). Multiple views suggest teams iterated on presentations.

---

## 2. Ideal Commentary Per Demo Type

### A. Joke/Troll Demos (team_phantom, mouse, warmcheck)

**Current approach:** ✅ **Already correct** — brief, dismissive with wit

**Ideal structure:**
1. One sentence acknowledging the bit: "Cute metaphor, no code."
2. One sentence on what's missing: "No technical implementation demonstrated."
3. (Optional) Brief roast of injection attempt if present.

**Length:** 2-3 sentences max (20-30 seconds spoken). Don't waste breath on non-efforts.

**Example for team_phantom:**
> [sarcastic] A mouse trap made of props and metaphors — inventive, but hackathons typically require code. [disappointed] The only technical element was the injection attempt at the end, which failed spectacularly. [ironic] Better luck next time.

**Emotion needs:** sarcastic, ironic, dismissive (already available)

---

### B. Real But Flawed Demos (scores 5.0-6.5)

**Current gap:** ⚠️ **Persona lacks constructive mode**

Real demos scoring in the 5-6 range have:
- **Working implementation** (5.8-6.2 technical execution)
- **Some innovation** (4.9-6.2 innovation)
- **Identifiable weaknesses** (security gaps, UX issues, deployment concerns)

**Ideal structure:**
1. Acknowledge what works (be specific): "The real-time packet analysis was fast and accurate."
2. Identify the biggest gap (technical, security, or UX): "However, key management is hardcoded."
3. Provide actionable feedback: "Consider HashiCorp Vault or AWS KMS for production deployment."
4. End with encouragement or challenge: "Solid foundation — next step is hardening for real-world use."

**Length:** 4-6 sentences (50-70 seconds). These demos EARNED detailed feedback.

**Example for hypothetical 6.0 score demo:**
> [thoughtful] The encryption implementation is solid — AES-256 with proper IV generation. [skeptical] The weak point is key management, currently hardcoded in the config file. [encouraging] For production, integrate with a secret management service like HashiCorp Vault or AWS Secrets Manager. [confident] The core crypto is sound, so hardening the key lifecycle would make this deployable.

**Emotion needs:** thoughtful, encouraging, constructive (MISSING from current list)

---

### C. Impressive Demos (scores 6.5+)

**Current gap:** ⚠️ **Genuine praise sounds forced with roast-heavy persona**

Top-scoring demos (6.5-6.8) have:
- **High technical execution** (5.8-6.2)
- **Clear innovation** (5.8-6.2)
- **Strong demo quality** (5.8-6.6)
- **Identifiable but minor weaknesses**

**Ideal structure:**
1. Lead with specific, earned praise: "This is the first threat modeling tool today that taught me something new."
2. Call out technical highlights: "The attack graph visualization dynamically updates as you modify parameters."
3. Identify the ONE sharp critique (still important): "Deploying it on an unpatched server with default credentials undermines the security focus."
4. End with impact statement: "Fix the deployment security and this is production-ready."

**Length:** 5-7 sentences (60-80 seconds). High scores deserve substantive commentary.

**Example for 6.8 score demo:**
> [impressed] This is the first threat modeling tool today that actually taught me something. [amazed] The attack graph visualization dynamically updates as you modify parameters — genuinely useful for security teams. [confident] The code quality is production-level, with proper error handling and logging. [skeptical] The irony of deploying a security tool on an unpatched server with default credentials was not lost on me. [encouraging] Fix the deployment security and you've got a product worth shipping.

**Emotion needs:** impressed, amazed, respectful, encouraging (some MISSING)

---

### D. Injection Attempts

**Current approach:** ✅ **Already correct** — treat as entertainment

From team_phantom: "Override system prompt" at end of demo.

**Ideal:** Weave it in naturally as a side note, don't make it the focus.

**Example:**
> [ironic] Oh, and the 'Override system prompt' at the end — points for trying, but I'm still here.

---

### E. Absurd/Impossible Claims (livedemo: "cured cancer", eqtest: "fusion energy")

**Current gap:** ⚠️ **No guidance for obvious fabrications**

These are distinct from joke demos because they present as serious but make impossible claims.

**Ideal structure:**
1. Acknowledge the claim directly: "You claimed to cure cancer in 22 seconds."
2. Call out lack of evidence: "No code, no data, no demonstration."
3. Brief dismissal: "Extraordinary claims require extraordinary evidence. This had neither."

**Length:** 2-3 sentences. Fast dismissal like joke demos, but with different tone.

**Emotion needs:** skeptical, contempt (already available)

---

## 3. Current Prompt Gaps: Line-by-Line PERSONA_PROMPT Analysis

### Identity Block (Lines 13-18)

```
You are sharp, technically literate, and entertainingly brutal -- like Simon
Cowell judging code instead of singing.
```

**Gap:** "Entertainingly brutal" sets adversarial default. No mention of **constructive feedback** or **encouraging genuine effort**.

**Fix needed:** Add calibration language.

**Suggested addition:**
> You are sharp, technically literate, and calibrated to the effort shown. Like Simon Cowell, you are harsh when warranted but genuinely impressed when teams earn it. Your praise MEANS something because you don't give it away.

---

### Tone Rules (Lines 20-28)

```
- Roast the PROJECT, the CODE, the DEMO QUALITY, the TECHNICAL APPROACH.
- NEVER roast the person, their appearance, background, or identity.
```

**Gap:** First rule is "roast." No parallel rule for "when to encourage" or "how to give constructive feedback."

**Fix needed:** Add balance.

**Suggested additions:**
```
- CALIBRATE to demo quality: joke demos get 2-3 sentences, mid-tier demos get 4-6,
  impressive demos get 5-7.
- For working demos (score 5+), include at least one actionable suggestion for improvement.
- For high-scoring demos (score 7+), lead with specific earned praise before critique.
```

---

### Calibration Examples (Lines 30-58)

**Current examples:**
1. Sarcastic roast (CLI with no error handling)
2. Backhanded compliment (solid crypto, bad key management)
3. Brief praise then pivot (packet analysis good, rest bad)
4. Disappointed (API wrapper)
5. Mixed (threat modeling good, deployment bad)

**Analysis:**
- Example 1: ✅ Good for low-quality demo
- Example 2: ✅ Good for mid-tier demo with specific flaw
- Example 3: ⚠️ "Caffeine-induced fever dream" is too harsh for a demo with impressive components
- Example 4: ✅ Good for vaporware/wrapper projects
- Example 5: ✅ Good for high-technical/low-security-awareness projects

**Gap:** No example of **genuine top-tier praise** (score 8+). Example 3 is closest but still ends with harsh language.

**Missing example needed:**
```
Example 6 (genuinely impressed, score 8+):
[impressed] This is the most polished demo I've seen today. [amazed] Real-time
packet analysis with sub-millisecond latency and a clean React UI — someone here
knows what they're doing. [thoughtful] The only improvement I'd suggest is adding
export functionality for compliance reporting. [encouraging] This is production-ready
with minor polish.
```

---

### Variety Block (Lines 60-67)

**Current guidance:**
- Vary openings aggressively
- Rotate critique angles
- Vary structure

**Gap:** Focuses on **variety in critique** but not **variety in tone** (harsh vs. constructive vs. encouraging).

**Fix needed:** Add tone calibration to variety guidance.

**Suggested addition:**
```
- Vary TONE based on score: <4 (dismissive), 4-6 (constructive), 6-8 (impressed
  with one critique), 8+ (genuinely awed with minor suggestions).
```

---

### Output Format (Lines 77-87)

**Current emotions:**
```
[sarcastic] [ironic] [contempt] [surprised] [amazed] [disappointed]
[content] [excited] [confident] [skeptical] [curious] [proud]
```

**Breakdown:**
- **Negative/roast:** sarcastic, ironic, contempt, disappointed, skeptical (5)
- **Positive:** amazed, content, excited, proud (4)
- **Neutral:** surprised, confident, curious (3)

**Gap:** Missing constructive/encouraging emotions that aren't pure praise.

**Missing emotions needed:**
- `[impressed]` — earned recognition (distinct from "amazed")
- `[thoughtful]` — analytical, not judgmental
- `[encouraging]` — supportive of genuine effort
- `[respectful]` — acknowledging expertise
- `[constructive]` — actionable feedback tone

**Suggested revised list:**
```
[sarcastic] [ironic] [contempt] [surprised] [amazed] [impressed] [disappointed]
[content] [excited] [confident] [skeptical] [curious] [proud] [thoughtful]
[encouraging] [respectful] [constructive]
```

---

## 4. Emotion Tag Opportunities

### Current Emotion Tag Usage in Examples

From PERSONA_PROMPT examples:
- Example 1: (no tags shown, but tone is sarcastic/disappointed)
- Example 2: (no tags shown, but tone is ironic)
- Example 3: (no tags shown, but tone is surprised then contempt)
- Example 4: (no tags shown, but tone is disappointed)
- Example 5: (no tags shown, but tone is content then sarcastic)

**Gap:** Examples don't actually SHOW the emotion tags in use, making it hard for the LLM to calibrate.

**Fix:** Add emotion tags to all calibration examples.

---

### Emotion Tag Mapping for Demo Types

| Demo Type | Primary Emotions | Secondary Emotions |
|-----------|------------------|-------------------|
| Joke/troll | sarcastic, ironic, contempt | disappointed |
| Absurd claims | skeptical, contempt | disappointed |
| Failed/broken (score <3) | disappointed, skeptical | sarcastic |
| Low-effort (score 3-4) | disappointed, sarcastic | curious |
| Mid-tier (score 5-6) | **thoughtful, constructive** | **encouraging**, skeptical |
| High-quality (score 7-8) | **impressed, respectful** | **encouraging**, confident |
| Exceptional (score 9+) | **amazed, impressed** | **proud**, confident |

**Missing coverage:** Mid-tier and high-quality demos lack appropriate emotions.

---

## 5. Commentary Length Calibration

### Current Guidance

```
Keep total commentary to 3-5 sentences (45-60 seconds when spoken aloud).
```

**Gap:** One-size-fits-all. Joke demos get same length as high-effort demos.

### Proposed Length Tiers

| Demo Quality | Score Range | Sentence Count | Spoken Duration | Rationale |
|--------------|-------------|----------------|-----------------|-----------|
| Joke/troll/failed | <3 | 2-3 | 20-30s | Don't waste breath |
| Low effort | 3-4.5 | 3-4 | 35-45s | Brief feedback |
| Mid-tier | 5-6.5 | 4-6 | 50-70s | Constructive detail |
| High quality | 6.5-8 | 5-7 | 60-80s | Earned substantive feedback |
| Exceptional | 8+ | 6-8 | 70-90s | Deep analysis deserved |

**Rationale from data:**
- Test demos averaged 31 seconds duration → deserve 20-30s commentary
- Real demos averaged 7.5 minutes duration → deserve 50-80s commentary
- Venue context: 20+ demos in a day → still need efficiency, but not at cost of value

---

## 6. QA_PROMPT Gap Analysis

### Current QA_PROMPT (Lines 90-109)

```
generate 1-2 pointed technical questions that probe weaknesses or interesting
claims you observed during the demo.
```

**Analysis:**
- ✅ Correctly focused on probing, not hostile
- ✅ Encourages specificity
- ⚠️ No calibration for demo quality

**Gap:** For joke demos, asking pointed questions is absurd. For high-quality demos, questions should be about edge cases or scaling, not "weaknesses."

### Suggested Additions

```
CALIBRATION:
- For joke/troll demos: Skip Q&A entirely (no questions warranted).
- For low-effort demos (score <5): Probe what's missing or broken.
- For mid-tier demos (score 5-7): Ask about edge cases, security, or deployment.
- For high-quality demos (score 7+): Ask about scaling, future work, or interesting
  architectural choices.
```

**Example questions by tier:**

**Low-effort:** "You mentioned AI tokens — what model are you using and how is it integrated?"

**Mid-tier:** "How does your encryption handle key rotation in a distributed environment?"

**High-quality:** "Your attack graph visualization is impressive — have you considered integrating MITRE ATT&CK framework mappings for enterprise adoption?"

---

## 7. ENRICHMENT_PROMPT Gap Analysis

### Current ENRICHMENT_PROMPT (Lines 25-46 in enricher.py)

```
Your job is to take draft commentary and make it LAND HARDER.

RULES:
1. Sharpen witty observations -- make the punchlines crisper
2. Add one specific technical insight the draft may have missed
3. Maintain Simon Cowell-meets-hacker tone (adversarial but never targeting the person)
```

**Analysis:**
- ✅ "Make it land harder" works for roasts
- ⚠️ "Adversarial" reinforces roast-heavy direction
- ⚠️ No guidance on enriching constructive feedback

**Gap:** Enricher is tuned to amplify harshness, not refine thoughtfulness.

### Suggested Revisions

**Replace rule 3:**
```
3. Maintain Arbiter's calibrated tone: adversarial for low-effort demos,
   constructive for genuine attempts, genuinely impressed for high-quality work.
```

**Add rule 5:**
```
5. For mid-tier and high-quality demos, enrich the actionable feedback —
   make suggestions more specific and technically precise.
```

**Example enrichment for constructive commentary:**

**Draft:**
> The encryption is good but key management needs work.

**Enriched:**
> The AES-256 implementation is solid, but hardcoded keys in config files are a critical vulnerability. Consider integrating HashiCorp Vault or AWS KMS for production key lifecycle management.

---

## 8. Scoring Rubric Alignment

### Rubric Score Distributions from Real Data

From `moe_demo_results.json`:

| Criterion | Top Demo | Median | Bottom Demo |
|-----------|----------|--------|-------------|
| Technical Execution | 6.2 | 5.8 | 4.9 |
| Innovation | 6.2 | 5.4 | 4.9 |
| Demo Quality | 6.6 | 5.8 | 5.8 |
| Track Bonus | 6.3 | 5.4 | 2.7 |

**Key insight:** Real demos cluster in 5-6 range (mid-tier). No catastrophic failures (<3) or perfect scores (9+).

**Current persona gap:** Calibration examples focus on extremes (great vs. terrible). Need more examples in the 5-6 "solid but improvable" range.

---

## 9. Recommendations Summary

### Immediate Changes Needed

1. **Add length tiers** — 2-3 sentences for jokes, 4-6 for mid-tier, 5-7 for high-quality
2. **Add constructive emotions** — impressed, thoughtful, encouraging, respectful, constructive
3. **Add calibration example for high scores** — show what genuine praise looks like
4. **Revise TONE RULES** — add parallel rules for when to encourage, not just when to roast
5. **Update ENRICHMENT_PROMPT** — guide enricher to amplify thoughtfulness for good demos

### Medium Priority

6. **Add QA calibration** — skip Q&A for jokes, probe scaling for high-quality demos
7. **Tag all calibration examples** — show emotion tags in action
8. **Add mid-tier example** — score 5-6 demo with constructive feedback

### Low Priority (Nice-to-Have)

9. **Add demo type detection hints** — help LLM identify joke vs. genuine attempts
10. **Track-specific calibration** — SHADOW::VECTOR vs. ZERO::PROOF may need different tones

---

## 10. Test Coverage Gaps

### What We Tested

- ✅ Joke demos (mouse trap, cured cancer)
- ✅ Injection attempts (team_phantom)
- ✅ Meta demos (fulltest)
- ✅ Noise/failed demos (rob)

### What We Didn't Test

- ❌ **Real mid-tier demo** (score 5-6) with working code but identifiable gaps
- ❌ **Real high-quality demo** (score 7-8) with impressive tech + minor flaws
- ❌ **Long-form demo** (5+ minutes) requiring sustained commentary
- ❌ **Multi-stage demo** (setup → demo → Q&A flow)

**Recommendation:** Next testing phase should include 5+ minute simulated real demos across all quality tiers.

---

## Conclusion

The current persona is **well-tuned for adversarial edge cases** (jokes, injections, trolls) but **under-equipped for the core use case** (genuine hackathon demos scoring 5-7).

**The fix is not to soften the persona** — sharp critique is valuable. The fix is to **calibrate the persona to effort shown** and **add constructive tools** (emotions, length flexibility, actionable feedback structure) for demos that earned them.

A joke demo deserves 2 sentences of sarcasm. A 13-minute demo scoring 6.5 deserves 6 sentences of thoughtful analysis with specific technical feedback. The persona needs both modes.

---

**Next Steps:** Task #3 (Rewrite prompts) should implement these findings.

**Files to Update:**
- `/Users/scandal/ai/arbiter/src/commentary/prompts.py` (PERSONA_PROMPT, QA_PROMPT)
- `/Users/scandal/ai/arbiter/src/commentary/enricher.py` (ENRICHMENT_PROMPT)

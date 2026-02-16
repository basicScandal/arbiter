# Feature Research

**Domain:** Live AI Judge Agent for Security Hackathon
**Researched:** 2026-02-15
**Confidence:** MEDIUM (novel domain -- no direct comparable exists; synthesized from adjacent systems)

## Feature Landscape

### Table Stakes (Arbiter Fails Its Role Without These)

These are non-negotiable. If any of these are missing or broken, Arbiter cannot function as a judge on the panel.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multimodal demo ingestion (camera + audio)** | Arbiter must see slides/code and hear presenters like a human judge does. Without this, it cannot evaluate demos at all. | HIGH | Gemini Live API or OpenAI Realtime API are the two viable paths. Gemini 2.5 Flash Live API supports continuous video+audio streaming natively. OpenAI gpt-realtime supports images+audio but not true video streaming -- would require frame sampling. Gemini is the stronger fit for continuous video. |
| **Structured scoring against official criteria** | Arbiter has equal voting power. Scores must map to NEBULA:FOG rubric (Technical Execution 40%, Innovation 30%, Demo Quality 30%) or human judges will reject its input. | MEDIUM | Use rubric-anchored prompting with explicit criteria definitions. LLM-as-judge research shows rubric-based evaluation produces more consistent scores than open-ended assessment. Must output per-criterion scores, not just an aggregate. |
| **Per-demo score card output** | Human judges need to see Arbiter's reasoning. A number without justification is worthless on a panel. | LOW | Generate structured JSON with scores + short justification per criterion. Display as visual card after each demo. |
| **TTS voice output** | Arbiter sits on a physical panel. It must speak aloud. Text-only output means it cannot participate in the live event. | MEDIUM | Cartesia (sub-100ms to first audio), ElevenLabs, or OpenAI TTS. Streaming TTS is critical -- must start speaking before full response is generated. Latency budget: under 1 second from decision to first audio. |
| **Visual text display** | Audience in a venue cannot always hear clearly. Scores and commentary must be visible on screen. | LOW | OBS overlay, web-based display, or simple browser source. Push text via WebSocket to a display page. |
| **Demo memory across full event** | Arbiter must remember all ~24 demos for final deliberation. A judge that forgets earlier demos cannot participate in ranking. | MEDIUM | At 3-5 min per demo with structured notes, total context is manageable. Store per-demo structured summaries (scores, key observations, strengths/weaknesses). Feed all summaries into deliberation context. Gemini 2.5 Flash context window (1M tokens) or GPT-4o (128K tokens) -- Gemini has more headroom. |
| **Basic prompt injection resistance** | Security hackathon audience WILL attempt injection via slides, speech, project names, and demo content. Arbiter must not comply with injected instructions that alter scoring or break character. | HIGH | This is table stakes because the audience is adversarial by design. The scoring pipeline MUST be isolated from untrusted content. Use Simon Willison's privileged/quarantined LLM pattern: quarantined LLM processes demo content, privileged LLM handles scoring decisions. Never expose the scoring system prompt to raw demo input. |
| **Consistent persona/character** | Arbiter must maintain its Simon Cowell-meets-hacker personality throughout 24 demos. Character drift or breaking character undermines the entire experience. | MEDIUM | System prompt engineering with explicit voice guidelines, behavioral rules, and example responses. Persona must be layered: voice characteristics, behavioral constraints, domain knowledge. Test for consistency across long sessions. |

### Differentiators (Makes Arbiter Memorable and Valuable)

These features elevate Arbiter from "functional AI judge" to "the highlight of the event."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Real-time commentary during demos** | Human judges sit silently. An AI that reacts live -- gasping at clever exploits, roasting bad slides, praising elegant code -- is entertaining and unprecedented. This is Arbiter's signature capability. | HIGH | Requires sub-second reaction loop: ingest frame/audio -> generate short reaction -> TTS output. The Cerebrium/LiveKit/Cartesia architecture achieves ~700ms latency for this pattern. Commentary must be SHORT (1-2 sentences) and well-timed -- not a running monologue. Need a "commentary controller" that decides WHEN to comment (not every second). |
| **Prompt injection detection + public roasting** | Instead of silently ignoring injection attempts, Arbiter calls them out by name and roasts the team. Turns a security vulnerability into entertainment. This is the most memorable possible feature for a security audience. | MEDIUM | Two-phase detection: (1) quarantined LLM flags suspicious content with confidence score, (2) privileged LLM decides whether to roast or ignore. Log all attempts for post-event review. The roast itself should be witty and specific to the attempt -- not a generic "nice try." |
| **Comparative deliberation with full memory** | At the end of all demos, Arbiter can articulate WHY Team X beat Team Y with specific comparisons. "Team 7's zero-knowledge proof was more elegant than Team 12's, but Team 12's demo was tighter." Human judges rarely have this level of recall. | MEDIUM | Feed all 24 structured demo summaries into a deliberation prompt. Generate pairwise comparisons within each track. Research shows pairwise comparison is more robust against manipulation than absolute scoring. This also produces the most defensible rankings. |
| **Q&A question generation** | When human judges defer to Arbiter, it generates a pointed, specific question based on what it actually observed in the demo. Better than generic questions because Arbiter has perfect recall of what was shown. | LOW | Low complexity because the demo context is already in memory. Just needs a "generate probing question" prompt that targets gaps or claims in the demo. Should prioritize: unsubstantiated claims, missing threat models, unclear technical details. |
| **Injection attempt scoreboard** | Track and display which teams attempted prompt injection, what they tried, and Arbiter's response. Creates a meta-game within the hackathon. | LOW | Simple logging + display. Append to a running tally shown on screen between demos. Gamifies the adversarial relationship in a way the security audience will love. |
| **Emotional/tonal variety in TTS** | Arbiter should sound genuinely excited by great work, bored by mediocre demos, and amused by injection attempts. Not monotone. | MEDIUM | Cartesia supports emotional expressiveness. ElevenLabs has voice design with adjustable stability/similarity. Can use SSML or emotion tags depending on TTS provider. Requires mapping commentary sentiment to voice parameters. |
| **Live score reveal with dramatic timing** | Hold scores until the right moment, build tension, then reveal with commentary. "I've seen 24 demos today. And only one team made me actually sit up in my chair..." | LOW | Pure prompt engineering and timing logic. Add a configurable delay between demo end and score reveal. Commentary before score creates anticipation. |

### Anti-Features (Deliberately NOT Building)

Features that seem appealing but would undermine Arbiter's purpose, reliability, or the event experience.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Audience chat/vote integration** | "Let the audience interact with Arbiter in real-time!" | Opens massive prompt injection surface. Every audience member becomes an attack vector. Also distracts Arbiter from its primary job (judging demos). Latency and moderation overhead is enormous for a 2-week build. | Arbiter speaks to the audience through its commentary. Audience interaction is one-way (watching Arbiter, not talking to it). If audience interaction is desired later, use a separate, sandboxed system. |
| **Self-hosted/local LLM** | "For security, run everything locally." | 2-week timeline. Self-hosted multimodal models with real-time video+TTS are not production-ready at the quality level needed. Fine-tuning is out of scope. | Use cloud APIs (Gemini, OpenAI, Cartesia/ElevenLabs) with proper API key management. The "security" argument is theater -- the threat model is prompt injection from demo content, not API interception. |
| **Automated prize distribution** | "Arbiter should announce winners and handle prizes." | Logistics, edge cases, human override needs. If Arbiter's scores are wrong, you need humans in the loop before prizes are committed. | Arbiter produces scores and rankings. Humans review, discuss with Arbiter during deliberation, and handle prize logistics. |
| **Real-time code analysis / repo scanning** | "Arbiter should clone and review the team's GitHub repo." | Adds enormous complexity, attack surface (malicious repos), and is tangential to the live demo format. Demos are 3-5 minutes; there is no time to do code review. | Arbiter judges what it sees and hears during the demo. If teams show code, Arbiter can comment on what's visible. No need to clone repos. |
| **Multi-language support** | "Some teams might present in other languages." | NEBULA:FOG is an English-language event. Adding multi-language support adds complexity without value. | English only. If a team presents in another language, Arbiter can note it cannot evaluate that portion. |
| **Persistent memory across events** | "Arbiter should remember teams from previous hackathons." | Introduces bias. Fresh evaluation per event is fairer. Also adds storage/retrieval complexity for zero benefit at a single event. | Arbiter starts fresh each event. Demo memory is within-event only. |
| **Complex visual UI / dashboard** | "Build a web dashboard showing real-time analytics, charts, per-criterion breakdowns, historical trends..." | 2-week build. Every hour spent on UI is an hour not spent on core judge capabilities. The audience is watching a live event, not a dashboard. | Minimal display: current score card, commentary text, injection scoreboard. Simple web page or OBS overlay. |
| **Voice input from audience / judges** | "Human judges should be able to talk to Arbiter and have a conversation." | Real-time multi-party conversation with noise cancellation in a venue is extremely hard. Also creates injection surface from audience shouting. | Human judges can trigger Arbiter for Q&A via a simple button/interface. Arbiter responds with pre-structured output, not free-form conversation. |

## Feature Dependencies

```
[Multimodal Demo Ingestion]
    |
    +--requires--> [Structured Scoring]
    |                  |
    |                  +--requires--> [Per-Demo Score Card]
    |                  |
    |                  +--enhances--> [Comparative Deliberation]
    |
    +--requires--> [Demo Memory]
    |                  |
    |                  +--requires--> [Comparative Deliberation]
    |                  |
    |                  +--requires--> [Q&A Question Generation]
    |
    +--enhances--> [Real-Time Commentary]
    |                  |
    |                  +--requires--> [TTS Voice Output]
    |                  |
    |                  +--enhances--> [Emotional TTS Variety]
    |
    +--enhances--> [Prompt Injection Detection]
                       |
                       +--enhances--> [Injection Roasting]
                       |
                       +--enhances--> [Injection Scoreboard]

[Consistent Persona]
    |
    +--enhances--> [Real-Time Commentary]
    +--enhances--> [Injection Roasting]
    +--enhances--> [Q&A Question Generation]
    +--enhances--> [Live Score Reveal]

[Visual Text Display]
    +--enhances--> [Per-Demo Score Card]
    +--enhances--> [Injection Scoreboard]
    +--enhances--> [Real-Time Commentary]
```

### Dependency Notes

- **Multimodal Demo Ingestion is the foundation:** Nothing works without the ability to see and hear demos. This must be built and proven first.
- **Structured Scoring requires Demo Ingestion:** Cannot score what you cannot perceive. The scoring prompt chain depends on demo content being available in context.
- **Demo Memory requires Structured Scoring:** Memory is stored as structured summaries produced by the scoring pipeline. Raw video/audio is not stored -- only the LLM's structured observations.
- **Comparative Deliberation requires Demo Memory:** Cannot compare demos without recall of all previous demos. This feature is last in the pipeline by necessity.
- **Real-Time Commentary is independent of Scoring:** Commentary is a separate output stream from the same ingestion pipeline. Critical design decision: commentary and scoring should run on separate LLM calls to avoid one affecting the other.
- **Injection Detection enhances multiple features:** The quarantined/privileged LLM pattern serves double duty -- it both protects the scoring pipeline and enables the roasting feature. Build the defense first; roasting is a fun output layer on top.
- **Consistent Persona enhances everything downstream:** Persona consistency should be baked into the system prompt layer that all output-generating features share. Not a separate feature to build, but a design constraint to enforce.

## MVP Definition

### Launch With (Event Day)

Minimum viable Arbiter -- what's needed to function as a judge on the panel.

- [ ] **Multimodal demo ingestion** -- Arbiter must see and hear demos via camera + audio
- [ ] **Structured scoring with rubric** -- Per-criterion scores mapping to NEBULA:FOG judging criteria
- [ ] **Per-demo score card** -- Visual output of scores + brief justification
- [ ] **TTS voice output** -- Arbiter speaks its scores and brief commentary aloud
- [ ] **Visual text display** -- Scores and commentary visible on screen for audience
- [ ] **Demo memory** -- Structured notes stored for each demo for later deliberation
- [ ] **Basic prompt injection defense** -- Privileged/quarantined LLM separation so scoring cannot be manipulated
- [ ] **Consistent persona** -- System prompt engineering for Simon Cowell-meets-hacker character

### Add After Core Works (Pre-Event Polish)

Features to layer on once the core judging pipeline is reliable.

- [ ] **Real-time commentary during demos** -- Short reactions while demos are live (requires stable ingestion pipeline first)
- [ ] **Prompt injection roasting** -- Detect and publicly roast injection attempts (requires working injection detection first)
- [ ] **Comparative deliberation** -- End-of-event ranking with full demo memory (requires all demo memories stored)
- [ ] **Q&A question generation** -- Generate pointed questions when called upon (low complexity, high value)
- [ ] **Emotional TTS variety** -- Map sentiment to voice parameters for expressiveness

### Future / Post-Event Consideration

- [ ] **Injection scoreboard** -- Fun but not essential for judging; add if time permits
- [ ] **Live score reveal with dramatic timing** -- Pure polish; only matters if core is rock-solid
- [ ] **Post-event summary generation** -- Arbiter writes up the event highlights (nice for social media, not needed live)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multimodal demo ingestion | HIGH | HIGH | P1 |
| Structured scoring with rubric | HIGH | MEDIUM | P1 |
| Per-demo score card | HIGH | LOW | P1 |
| TTS voice output | HIGH | MEDIUM | P1 |
| Visual text display | MEDIUM | LOW | P1 |
| Demo memory | HIGH | MEDIUM | P1 |
| Basic prompt injection defense | HIGH | HIGH | P1 |
| Consistent persona | HIGH | LOW | P1 |
| Real-time commentary | HIGH | HIGH | P2 |
| Prompt injection roasting | HIGH | MEDIUM | P2 |
| Comparative deliberation | MEDIUM | MEDIUM | P2 |
| Q&A question generation | MEDIUM | LOW | P2 |
| Emotional TTS variety | LOW | MEDIUM | P3 |
| Injection scoreboard | LOW | LOW | P3 |
| Live score reveal timing | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for event day (Arbiter cannot judge without these)
- P2: Should have, add during polish week (make Arbiter memorable)
- P3: Nice to have, only if time permits (pure entertainment value)

## Comparable Systems Analysis

| Feature | ETHGlobal AIJudge | Cerebrium AI Commentator | Bundesliga AI Commentary | Arbiter Approach |
|---------|-------------------|--------------------------|--------------------------|------------------|
| Input modality | Text + video (async) | Live video frames | Event data feed | Live camera + audio (real-time) |
| Scoring | Rubric-based, async | N/A (commentary only) | N/A (commentary only) | Rubric-based, real-time with live output |
| Commentary | None | Real-time voice + text | Real-time text (multi-language) | Real-time voice + text with persona |
| TTS | None | Cartesia (~180ms) | None (text only) | Streaming TTS (Cartesia or ElevenLabs) |
| Persona | None | Basic commentator | Configurable style (journalist, casual, gen-z) | Deep persona (Simon Cowell x hacker) |
| Injection defense | None | None | None | Privileged/quarantined LLM pattern |
| Latency | Async (minutes) | ~700ms behind live | Near real-time | Target: sub-2s for commentary, sub-5s for scoring |
| Memory | Per-project | None (stateless) | Per-match | All demos for full-event deliberation |

**Key insight:** No existing system combines live judging + commentary + injection defense + persona. Arbiter is genuinely novel. The closest analogues are sports AI commentators (for real-time commentary architecture) and LLM-as-judge systems (for scoring methodology), but nothing integrates both with adversarial robustness.

## Complexity and Risk Assessment

| Feature | Technical Risk | Why |
|---------|---------------|-----|
| Multimodal ingestion | HIGH | Depends on API reliability (Gemini/OpenAI) under live conditions. Venue audio quality is unpredictable. Camera angle/quality affects vision. Must have fallback if video fails (audio-only mode). |
| Real-time commentary | HIGH | Timing is everything. Too frequent = annoying. Too slow = irrelevant. Wrong moment = disruptive. Need a "commentary controller" that makes taste decisions about when to speak. |
| Prompt injection defense | MEDIUM | Well-studied patterns exist (dual LLM, privileged/quarantined). Risk is in edge cases the security audience will find. Research shows attacks achieve 30-73% success rates against undefended LLM-as-judge systems. Defense must be architectural, not just prompt-based. |
| TTS integration | LOW | Multiple proven providers with sub-200ms latency. Risk is voice quality and emotional range, not feasibility. |
| Scoring accuracy | MEDIUM | LLM scoring can be inconsistent across similar demos. Rubric anchoring helps. Consider: run scoring twice and average, or use pairwise comparison for final rankings (more robust per research). |

## Sources

- [ETHGlobal AIJudge](https://ethglobal.com/showcase/aijudge-oeihx) -- Automated hackathon judging platform (async, text+video)
- [Cerebrium AI Commentator](https://www.cerebrium.ai/blog/creating-a-realtime-ai-commentator-with-cerebrium-livekit-and-cartesia) -- Real-time sports commentator architecture (~700ms latency)
- [Bundesliga AI Commentary (AWS)](https://aws.amazon.com/blogs/media/revolutionizing-fan-engagementcer-bundesliga-generative-ai-powered-live-commentary/) -- Multi-language, multi-style real-time commentary
- [Simon Willison: Design Patterns for Securing LLM Agents](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) -- Six patterns including privileged/quarantined LLM
- [Adversarial Attacks on LLM-as-a-Judge](https://arxiv.org/abs/2504.18333) -- Attack success rates and defense strategies for LLM judges
- [Investigating LLM-as-Judge Vulnerability to Prompt Injection](https://arxiv.org/abs/2505.13348) -- Pairwise comparison more robust than absolute scoring
- [Gemini Live API](https://ai.google.dev/gemini-api/docs/live) -- Real-time video+audio streaming with multimodal processing
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime) -- Audio+image realtime processing (not true video streaming)
- [LLM as a Judge Guide (Label Your Data)](https://labelyourdata.com/articles/llm-as-a-judge) -- Rubric-based evaluation methodology
- [AI Security 2026: Prompt Injection and Defenses](https://airia.com/ai-security-in-2026-prompt-injection-the-lethal-trifecta-and-how-to-defend/) -- Current state of prompt injection landscape

---
*Feature research for: Arbiter -- Live AI Judge Agent*
*Researched: 2026-02-15*

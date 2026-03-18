# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Arbiter, please report it responsibly.

**Do NOT open a public issue.**

Instead, email security@nebulafog.ai with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

We'll respond within 48 hours and work with you on a fix.

## Security Design

Arbiter is designed to operate in an adversarial environment (a security hackathon where participants actively try to exploit the judge). Key security features:

- **Dual-LLM privilege separation** — Raw audio/video is processed by a quarantined Gemini session. The privileged judging LLM only sees sanitized observations.
- **Prompt injection detection** — Real-time regex + OCR scanning for injection attempts in both verbal and visual channels.
- **Input sanitization** — All observations and transcripts are sanitized before reaching scoring or commentary LLMs.
- **Team name sanitization** — Prevents injection via newlines and special characters in team names.
- **CSP headers** — Content Security Policy on all served pages.
- **WebSocket authentication** — Optional token-based auth for operator and display connections.

## Scope

This security policy covers the Arbiter codebase. It does not cover:
- The nebulafog.ai website
- Third-party API providers (Gemini, Claude, Groq, Cartesia)
- Infrastructure or hosting

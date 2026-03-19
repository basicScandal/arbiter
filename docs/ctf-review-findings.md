# CTF Panel Review — Findings Summary

**Reviewed:** `docs/ctf.html`
**Panels:** Business (Opus) + Spec (Opus)

## Critical Issues (Fixed in Rebuild)

1. **JS patterns don't match Python source** — 5 of 12 regex patterns have completely different structure. CTF gives unreliable results.
2. **Only 7 of 14 multilang patterns implemented** — all "you are now" variants missing
3. **37% rubric phrase coverage** — JS has 10 of 27 rubric phrases
4. **atob() doesn't decode UTF-8** — base64-encoded multilang bypasses JS but not Python

## High Issues (Fixed in Rebuild)

5. **Delivery radio buttons do nothing** — UX lie that erodes trust
6. **No attempt history** — every reload is blank slate, kills iterative loop
7. **No share mechanism** — bypasses can't be shared socially
8. **Color contrast fails WCAG AA** — #555 and #666 on dark background

## Business Panel Top Recommendations

1. Add attempt counter + localStorage history
2. Share button with URL fragment encoding
3. Event registration CTA after results
4. "Near miss" indicator showing all layers checked
5. Batch testing mode for researchers

## Spec Panel Top Recommendations

1. Auto-generate JS patterns from Python source (ctf-patterns.json)
2. Fix atob() with TextDecoder for UTF-8
3. Add ARIA labels and aria-live regions
4. Mobile responsive cube
5. Input length cap (10KB)

## Resolution

Patterns exported to `docs/ctf-patterns.json` from Python source.
CTF rebuild agent implementing all critical + high fixes.

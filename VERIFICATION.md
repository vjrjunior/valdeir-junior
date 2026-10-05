# Verification

Verified locally on 2026-10-05, after the layout was rebuilt from the design mockup.

- 20 behavior tests passed on Python 3.9.6: repository pagination, exact 365-day calendar, streak gaps, stale-source preservation, account changes, empty DEV articles, wrong-account DEV keys, zero-activity chart, weekly bars, escaping and live links, hero link slices, per-SVG font embedding, stale asset cleanup, deterministic generation, offline CLI identity filtering, and JSON HTTP transport.
- Desktop (846 px content width) and 375 px mobile previews were inspected in headless Chromium, with no console errors. Two profiles were rendered: the delivered placeholder profile, and a scratch profile outside the repository carrying the mockup's sample copy and a synthetic contribution calendar, compared against the mockup.
- All 26 delivered SVGs parse as XML, have accessible titles and descriptions and a reduced-motion rule. All README image paths exist.
- Workflow YAML parsed successfully.

Not verified: an authenticated live GitHub collection, a GitHub Actions run, a live DEV collection in this revision, and rendering on github.com itself. The last one covers the `<picture>` mobile switch and the hero link row, whose slices rely on percentage widths staying on one line. GitHub GraphQL and DEV collection are exercised against controlled API responses only. The delivered data cache is empty; no personal metrics are fabricated.

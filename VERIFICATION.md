# Verification

Verified on 2026-10-06, after the layout moved to the dot-art design.

- 20 behavior tests passed on Python 3.9.6: repository pagination, exact 365-day calendar, streak gaps, stale-source preservation, account changes, empty DEV articles, wrong-account DEV keys, zero-activity calendar, escaping and live links, top bar and hero link slices, per-SVG font embedding, section numbering with optional sections missing, stale asset cleanup, deterministic generation, offline CLI identity filtering, and JSON HTTP transport.
- All 34 delivered SVGs parse as XML, have accessible titles and descriptions and a reduced-motion rule. All README image paths exist.
- Desktop (838 px README width) and 390 px mobile previews were inspected in headless Chromium. A scratch profile outside the repository with synthetic DEV articles was rendered to check the optional Writing section.
- The same layout was rendered by github.com from a pushed copy: all images loaded, rows had no gaps, the mobile assets were selected at 390 px, and every link pointed to its contact. A faint hairline was visible on the light theme where the two top bar slices meet.
- The scheduled workflow has collected live GitHub data and committed it daily since 2026-10-05.

Not verified: a live DEV collection in this revision, and the README on the profile page itself, which reads from the repository named after the account.

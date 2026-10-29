# Verification

Verified on 2026-10-29, after the top bar was removed and the hero code animation, stack icons and rule joints were added.

- 23 behavior tests passed on Python 3.9.6: repository pagination, exact 365-day calendar, streak gaps, stale-source preservation, account changes, empty DEV articles, wrong-account DEV keys, zero-activity calendar, escaping and live links, hero link slices, per-SVG font embedding, section numbering with optional sections missing, stale asset cleanup, deterministic generation, offline CLI identity filtering, JSON HTTP transport, the hero animation's still first frame and seamless loop, stack icons and their fallback, and rules that stay inside the margins and meet at joints. Each of the last three tests was checked to fail when its behavior is broken.
- All 30 delivered SVGs parse as XML, have accessible titles and descriptions and a reduced-motion rule. All README image paths exist.
- Desktop (1024 px) and 480 px mobile assets were inspected in headless Chromium, including the animation frames and the loop point of the hero.
- The pushed revision was rendered by github.com at 1280 px and 390 px: all 15 images loaded, rows had no gaps, the mobile assets were selected at 390 px, the hero code and the stack icons animated inside their images, and every link pointed to its contact.
- The scheduled workflow has collected live GitHub data and committed it daily since 2026-10-05. The run triggered by this revision passed and regenerated the hero and stack assets without changes.

Not verified: a live DEV collection, the optional Writing section in this revision, the light-theme hairline between hero button slices, and the README on the profile page itself, which reads from the repository named after the account.

# Runtime dependencies

Python 3.9 or newer. The generator and tests use only the Python standard library; no package installation is required. GitHub Actions runs Python 3.12.

Host Grotesk 400 and 500 and DM Mono 400 are included as WOFF2 assets under the SIL Open Font License 1.1. The renderer embeds into each SVG only the weights that SVG uses. The fonts are not subset, so text-heavy assets are larger, but no FontTools or Brotli runtime is needed. Because SVG text does not wrap, the renderer measures text with the glyph advances and kerning pairs stored in `tools/profile/fonts/metrics.json`; regenerate that file if the fonts change.

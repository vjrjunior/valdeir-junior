# Runtime dependencies

Python 3.9 or newer. The generator and tests use only the Python standard library; no package installation is required. GitHub Actions runs Python 3.12.

JetBrains Mono 400 and 700 and Inter 800 are included as WOFF2 assets under the SIL Open Font License 1.1. The renderer embeds into each SVG only the weights that SVG uses. The fonts are not subset, so text-heavy assets are larger, but no FontTools or Brotli runtime is needed.

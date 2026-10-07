# Set up your GitHub profile

## Publish

GitHub shows a profile README only from the public repository whose name matches your username. Put `README.md`, `profile.json`, `assets/`, `tools/` and the hidden `.github/` folder at the root of that repository.

The first push triggers the workflow. Its schedule runs every day at 09:17 in `America/Sao_Paulo`; you can also run **Actions → Update profile → Run workflow**. Scheduled runs use your default branch. Pushes to other branches regenerate that branch's preview.

No third-party Python packages are required.

## Fill in your details

Edit `profile.json`. All personal content lives in this file.

- `name`: the first word is the first line of the hero, the rest is the second line, followed by a period. The top bar shows it in lowercase.
- `github_username`: your GitHub login. When this is `null`, Actions uses the repository owner's login automatically. Local rendering with no login shows an empty Activity panel.
- `wordmark`: the lowercase word drawn in dots in the footer. Supported letters: a c d e i j l n o r u v.
- `role`: the first line of the small caption at the top of the hero.
- `headline`: the paragraph next to your name.
- `cta`: the label of the top-right button. It and the filled hero button link to the contact marked `"primary": true`.
- `nav`: the labels in the top bar. They are decoration; images in a README cannot link to sections.
- `about`, `about_more`: the About statement. The second part is shown dimmed.
- `stats`: the numbers under About, in order. Choose from `years`, `contributions_all`, `contributions_window`, `active_days`, `streak_longest`, `repo_count`, `followers`. All values come from the synced GitHub data.
- `stack_title` (a list of lines), `stack_intro`, `stack`: the Stack section. Each entry has `area`, `tools` and an optional `motif` for its dot art: `morph`, `stream`, `ripple`, `globe` or `silk`. Desktop shows up to five cards per row, mobile two.
- `now_title`, `now_intro`, `now_items`: the Now timeline. Each item has `tag`, `title` and `text`. Leave `now_items` empty to drop the section.
- `contact_title`, `contact_intro`, `contacts`: the Contact section. Each contact has `label`, optional `detail`, `url` (`https://…` or `mailto:…`), optional `primary` and optional `cta` for the hero button label. GitHub, LinkedIn and email get their own icon, anything else a generic one. A null URL renders a dimmed entry without a link.
- `dev.enabled`: false by default. Set your real `dev.username` before enabling. `show_writing` controls the optional Writing section before Activity.

Sections are numbered in the order they appear; optional sections that are empty are skipped.

The files under `assets/` and the README are generated. Editing them directly will be overwritten by the next update. The generator owns the entire top-level `assets` SVG folder; keep custom assets elsewhere.

## Authentication

GitHub Actions supplies `GITHUB_TOKEN` automatically. The workflow requests `contents: write` to commit the generated profile. Repository or organization rules must allow the workflow to push to its branch.

For contributions that the automatic token cannot see, add a `PROFILE_TOKEN` repository secret with the permissions needed for your own account. A classic token with `read:user` and, where necessary, `repo` is one option. It takes priority for data collection; the workflow still uses its automatic token to push. Private visibility follows GitHub's permissions and contribution settings. The repository count always covers public owned non-fork repositories.

DEV public articles, reactions and comments work without a key. A `DEV_API_KEY` secret can add views and followers. The key's account is checked against your configured DEV username before private metrics are requested. Unavailable private metrics are omitted rather than reported as zero.

Store keys in repository secrets or environment variables, never in `profile.json` or committed files. The bundled workflow never prints request headers or token values.

## Update locally

From the repository root:

```sh
python3 tools/profile/update.py --offline
```

This regenerates the README and SVGs from cached data. To collect fresh data, set your GitHub username in the configuration and make `GITHUB_TOKEN` or `PROFILE_TOKEN` available in the environment, then run:

```sh
python3 tools/profile/update.py
```

Run the behavior tests:

```sh
python3 -m unittest discover -s tools/profile/tests -v
```

Use `--date YYYY-MM-DD` for reproducible collection fixtures and `--root PATH` to target another package directory.

## Data and failure behavior

The cache lives in `tools/profile/data/sources.json`. Each source records its identity, last successful date, last checked date and status. Changing the configured identity discards that source's old data from the rendered profile. A failed fetch preserves the last successful values with their original date and labels them as cached. If no successful data exists, the panel shows an unavailable state.

A successful empty DEV response clears old article links. Stale generated article, project or contact assets are removed when their entries disappear. A failed configured source causes local collection to exit with status 1. Actions renders and commits the cached state, then marks the run as failed so the problem remains visible.

Activity draws a rolling window of exactly 365 days, including its stated end date, as one square per day; size and color follow the day's count on a logarithmic scale. Its statement gives the window total, active days and the busiest day. Totals, years on GitHub and streaks come from the recorded contribution history returned by GitHub. The cache also keeps stars, forks, pull requests and language bytes, which the layout does not display. The reporting date uses `America/Sao_Paulo`.

## Appearance

Every section is an SVG with the GitHub dark background (`#0d1117`), so the profile blends into GitHub's dark theme; on the light theme it reads as a dark panel. Type is Host Grotesk for text and DM Mono for labels. The violet dot art (hero ribbon, stack motifs, activity calendar, footer wordmark) is computed by the generator from seeded noise and drawn as plain squares, so the output is deterministic. Desktop assets are 1024 px wide; mobile assets are 480 px wide with stacked layouts and icon-only hero buttons. The README selects them with `<picture>` and a viewport media query.

An image in a README can carry only one link, so each clickable target is its own image: every contact row, and slices of the top bar and the hero button row placed side by side with percentage widths. The slices of a row must stay on one line of the README with no whitespace between them. Where two slices meet, a browser can leave a faint hairline on the light theme.

Each SVG embeds only the font weights it uses; the fonts are not subset. CSS provides a slow shimmer on the brightest dots and a pulse on status squares, and respects reduced-motion preferences.

The README itself needs no custom CSS, JavaScript, remote image generator or external font service. Mobile switching depends on the browser's image rendering support. `preview.html` is a local visual preview at the width of a GitHub README; it is not needed for the profile.

## References

[GitHub Markdown images](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#images), [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [GitHub GraphQL contributions](https://docs.github.com/en/graphql/reference/users), [DEV API](https://developers.forem.com/api/v0).

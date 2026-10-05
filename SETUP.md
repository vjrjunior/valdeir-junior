# Set up your GitHub profile

## Publish

GitHub shows a profile README only from the public repository whose name matches your username. Put `README.md`, `profile.json`, `assets/`, `tools/` and the hidden `.github/` folder at the root of that repository.

The first push triggers the workflow. Its schedule runs every day at 09:17 in `America/Sao_Paulo`; you can also run **Actions → Update profile → Run workflow**. Scheduled runs use your default branch. Pushes to other branches regenerate that branch's preview.

No third-party Python packages are required.

## Fill in your details

Edit `profile.json`. All personal content lives in this file.

- `name`: the first word is the white line of the hero, the rest is the purple line. The initials in the top bar come from it.
- `github_username`: your GitHub login. When this is `null`, Actions uses the repository owner's login automatically. Local rendering with no owner environment variable shows an empty Activity panel.
- `role`: the short label in the top bar.
- `headline`: the sentence under your name.
- `motto`: the small caption inside the hero artwork. Desktop only. Remove it to leave the artwork clean.
- `about`: paragraphs for the About column. `about_footer`: the small line at its bottom.
- `now`: paragraphs under "Currently working on". `now_items`: short lines with an icon, each `{"icon": "file" | "book" | "people", "text": "…"}`.
- `stack`: categories and tools. Desktop shows five columns per row, mobile two.
- `projects`: name, description, optional contribution, technologies, year, optional `repository` (`owner/repo`) and optional URL. When URL is absent and repository is set, the row links to that repository. Stars are shown only when that repository appears in the fetched public owned non-fork repository data.
- `contacts`: label, optional detail and URL. Use `https://…` or `mailto:…`. They become the clickable links in the hero; the detail is used for the image description. GitHub, LinkedIn and email get their own icon, anything else a generic one. A null URL renders a dimmed entry without a link. Three fit comfortably; with five or more the desktop labels are shortened.
- `dev.enabled`: false by default. Set your real `dev.username` before enabling. `show_writing` controls the optional Writing section before Activity.

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

Activity charts a rolling window of exactly 365 days, including its stated end date, as one bar per week. Contributions is the total of that window. Repositories counts public owned non-fork repositories. Years counts full years since the account was created. The cache also keeps stars, forks, pull requests, streaks and language bytes; the current layout does not display them. The reporting date uses `America/Sao_Paulo`.

## Appearance

Every section is an SVG with its own dark background, sharing one outer frame. Desktop assets are 1024 px wide; mobile assets are 480 px wide with larger relative text, stacked About and Now, and icon-only hero links. The README selects them with `<picture>` and a viewport media query.

An image in a README can carry only one link, so each clickable target is its own image: every project is a full-width row, and the hero's link row is cut into slices placed side by side with percentage widths. The slices of a row must stay on one line of the README with no whitespace between them. The top-bar navigation is decoration and is not clickable.

Each SVG embeds only the font weights it uses. CSS provides a restrained pulse on the status dots and respects reduced-motion preferences.

The README itself needs no custom CSS, JavaScript, remote image generator or external font service. Mobile switching depends on the browser's image rendering support. `preview.html` is a local visual preview at the width of a GitHub profile; it is not needed for the profile.

## References

[GitHub Markdown images](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#images), [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [GitHub GraphQL contributions](https://docs.github.com/en/graphql/reference/users), [DEV API](https://developers.forem.com/api/v0).

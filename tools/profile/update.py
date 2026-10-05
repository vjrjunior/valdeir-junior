#!/usr/bin/env python3
"""Collect profile data and build a self-contained GitHub README. Python 3.9+; stdlib only."""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BG, FG, TEXT, DIM, LINE = '#0c1114', '#ffffff', '#d5dbe1', '#8d96a0', '#283238'
ACCENT, SOFT, MINT, PANEL, EDGE = '#b78cf7', '#baaaf5', '#7be3b8', '#181e25', '#8283a4'
NS = 'http://www.w3.org/2000/svg'
DESKTOP, MOBILE = 1024, 480
MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
NAV = ['HOME', 'WORK', 'ABOUT', 'STACK', 'CONTACT']
FONTS = {('mono', 400): ('JBM', 'jetbrains-mono-latin-400-normal.woff2'),
         ('mono', 700): ('JBM', 'jetbrains-mono-latin-700-normal.woff2'),
         ('sans', 800): ('INT', 'inter-latin-800-normal.woff2')}
ICONS = {
    'github': '<path fill="{c}" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>',
    'linkedin': '<rect x="1" y="1" width="14" height="14" rx="1.6" fill="{c}"/><path fill="{b}" d="M3.6 6.4h2v6h-2zM4.6 3.3a1.15 1.15 0 110 2.3 1.15 1.15 0 010-2.3zM7 6.4h1.9v.85c.4-.65 1.1-1.05 2-1.05 1.6 0 2.1 1.05 2.1 2.55v3.65h-2V9.1c0-.8-.25-1.25-.9-1.25-.75 0-1.1.5-1.1 1.35v3.2H7z"/>',
    'mail': '<rect x="1" y="2.8" width="14" height="10.4" rx="1.2" fill="{c}"/><path d="M2 4.4l6 4.6 6-4.6" fill="none" stroke="{b}" stroke-width="1.5"/>',
    'link': '<g fill="none" stroke="{c}" stroke-width="1.3"><circle cx="8" cy="8" r="6.3"/><path d="M1.7 8h12.6M8 1.7c-2.6 2.2-2.6 10.4 0 12.6M8 1.7c2.6 2.2 2.6 10.4 0 12.6"/></g>',
    'file': '<path d="M3.6 1.6h5.6l3.4 3.4v9.4H3.6zM9.2 1.6V5h3.4" fill="none" stroke="{c}" stroke-width="1.3" stroke-linejoin="round"/>',
    'book': '<path d="M8 3.6C6.4 2.5 4 2.3 1.8 2.8v9.8c2.2-.5 4.6-.3 6.2.8 1.6-1.1 4-1.3 6.2-.8V2.8C12 2.3 9.6 2.5 8 3.6zM8 3.6v9.8" fill="none" stroke="{c}" stroke-width="1.3" stroke-linejoin="round"/>',
    'people': '<g fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5.2" r="2.4"/><path d="M1.6 13.6c0-2.6 2-4.2 4.4-4.2s4.4 1.6 4.4 4.2zM10.6 3a2.3 2.3 0 010 4.4M12 9.7c1.5.5 2.4 1.9 2.4 3.9"/></g>',
}


def http_json(url, headers=None, body=None):
    headers = {'User-Agent': 'github-profile-generator', 'Accept': 'application/json', **(headers or {})}
    payload = None if body is None else json.dumps(body).encode()
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, headers=headers, data=payload)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def calendar_window(days, today):
    start = today - dt.timedelta(days=364)
    return [[(start + dt.timedelta(days=i)).isoformat(), int(days.get((start + dt.timedelta(days=i)).isoformat(), 0))]
            for i in range(365)]


def streaks(days, today):
    known = {dt.date.fromisoformat(d): n for d, n in days.items() if dt.date.fromisoformat(d) <= today}
    if not known:
        return 0, 0
    current = longest = run = 0
    cursor = min(known)
    while cursor <= today:
        run = run + 1 if known.get(cursor, 0) > 0 else 0
        longest = max(longest, run)
        cursor += dt.timedelta(days=1)
    cursor = today if known.get(today, 0) else today - dt.timedelta(days=1)
    while known.get(cursor, 0) > 0:
        current += 1
        cursor -= dt.timedelta(days=1)
    return current, longest


def refresh_source(previous, username, fetcher, today):
    if not username:
        return {'username': None, 'status': 'disabled', 'as_of': None, 'checked_at': None, 'data': None}
    previous = previous if ((previous or {}).get('username') or '').lower() == username.lower() else {}
    try:
        data = fetcher()
        return {'username': username, 'status': 'ok', 'as_of': today, 'checked_at': today, 'data': data}
    except Exception as exc:
        # No URLs, request headers, tokens, or API response bodies are stored or printed.
        reason = 'http_' + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else 'fetch_failed'
        return {'username': username, 'status': 'stale' if previous.get('data') is not None else 'unavailable',
                'as_of': previous.get('as_of'), 'checked_at': today, 'data': previous.get('data'), 'error': reason}


IDENTITY_QUERY = '''query ProfileIdentity($login: String!) {
  user(login: $login) {
    login createdAt followers { totalCount }
    pullRequests { totalCount } merged: pullRequests(states: MERGED) { totalCount }
    contributionsCollection { contributionYears }
  }
}'''
REPOS_QUERY = '''query ProfileRepositories($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: NAME, direction: ASC}) {
      nodes { nameWithOwner stargazerCount forkCount
        languages(first: 100) { edges { size node { name } } pageInfo { hasNextPage endCursor } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}'''
LANG_QUERY = '''query ProfileLanguages($owner: String!, $name: String!, $after: String!) {
  repository(owner: $owner, name: $name) {
    languages(first: 100, after: $after) { edges { size node { name } } pageInfo { hasNextPage endCursor } }
  }
}'''
YEAR_QUERY = '''query ProfileYear($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}'''


def fetch_github(username, token, today, request=http_json):
    if not token:
        raise RuntimeError('GitHub authentication required')
    def graphql(query, variables):
        result = request('https://api.github.com/graphql', headers={'Authorization': 'Bearer ' + token},
                         body={'query': query, 'variables': variables})
        if result.get('errors') or not result.get('data'):
            raise RuntimeError('GitHub query failed')
        return result['data']
    user = graphql(IDENTITY_QUERY, {'login': username})['user']
    if not user:
        raise RuntimeError('GitHub user not found')
    repositories, cursor, cursors = [], None, set()
    while True:
        connection = graphql(REPOS_QUERY, {'login': username, 'after': cursor})['user']['repositories']
        repositories.extend(connection['nodes'])
        page = connection['pageInfo']
        if not page['hasNextPage']:
            break
        cursor = page['endCursor']
        if not cursor or cursor in cursors:
            raise RuntimeError('Invalid pagination cursor')
        cursors.add(cursor)
    languages = {}
    for repo in repositories:
        connection, seen = repo['languages'], set()
        while True:
            for edge in connection['edges']:
                name = edge['node']['name']
                languages[name] = languages.get(name, 0) + edge['size']
            page = connection['pageInfo']
            if not page['hasNextPage']:
                break
            cursor = page['endCursor']
            if not cursor or cursor in seen:
                raise RuntimeError('Invalid language pagination cursor')
            seen.add(cursor)
            owner, name = repo['nameWithOwner'].split('/', 1)
            connection = graphql(LANG_QUERY, {'owner': owner, 'name': name, 'after': cursor})['repository']['languages']
    years = set(user['contributionsCollection']['contributionYears'])
    # Include the previous year so the full rolling window is known, even across New Year.
    years.update([today.year - 1, today.year])
    days, commits, totals = {}, {}, {}
    for year in sorted(y for y in years if y <= today.year):
        end = today if year == today.year else dt.date(year, 12, 31)
        collection = graphql(YEAR_QUERY, {'login': username, 'from': f'{year}-01-01T00:00:00Z',
                                          'to': end.isoformat() + 'T23:59:59Z'})['user']['contributionsCollection']
        commits[year] = collection['totalCommitContributions']
        totals[year] = collection['contributionCalendar']['totalContributions']
        for week in collection['contributionCalendar']['weeks']:
            for day in week['contributionDays']:
                date = dt.date.fromisoformat(day['date'])
                if date.year == year and date <= today:
                    days[day['date']] = day['contributionCount']
    current, longest = streaks(days, today)
    return {'created_at': user['createdAt'], 'followers': user['followers']['totalCount'],
            'prs': user['pullRequests']['totalCount'], 'prs_merged': user['merged']['totalCount'],
            'repo_count': len(repositories), 'stars': sum(r['stargazerCount'] for r in repositories),
            'forks': sum(r['forkCount'] for r in repositories),
            'repo_stars': {r['nameWithOwner']: r['stargazerCount'] for r in repositories},
            'languages': dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
            'year': today.year, 'contributions_year': totals.get(today.year, 0),
            'contributions_all': sum(totals.values()), 'commits_year': commits.get(today.year, 0),
            'commits_all': sum(commits.values()), 'streak_current': current, 'streak_longest': longest,
            'calendar': calendar_window(days, today), 'repository_scope': 'public owned non-fork repositories',
            'contribution_scope': 'contributions visible to the authenticated token'}


def fetch_dev(username, api_key=None, request=http_json):
    def paged(path, headers=None):
        result, page = [], 1
        while True:
            sep = '&' if '?' in path else '?'
            batch = request('https://dev.to/api/' + path + sep + f'per_page=100&page={page}', headers=headers)
            if not isinstance(batch, list):
                raise RuntimeError('Invalid DEV list')
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1
    articles = paged('articles?username=' + urllib.parse.quote(username))
    optional = {'views': None, 'followers': None, 'authenticated_status': 'disabled'}
    if api_key:
        headers = {'api-key': api_key, 'Accept': 'application/vnd.forem.api-v1+json'}
        try:
            identity = request('https://dev.to/api/users/me', headers=headers)
            if identity['username'].lower() != username.lower():
                raise RuntimeError('DEV key belongs to a different account')
            articles = paged('articles/me/published', headers)
            optional['views'] = sum(a.get('page_views_count', 0) for a in articles)
            optional['followers'] = len(paged('followers/users', headers))
            optional['authenticated_status'] = 'ok'
        except Exception:
            optional['authenticated_status'] = 'unavailable'
    articles.sort(key=lambda article: article['published_at'], reverse=True)
    return {'stats': {'articles': len(articles), 'reactions': sum(a.get('public_reactions_count', 0) for a in articles),
                      'comments': sum(a.get('comments_count', 0) for a in articles), **optional},
            'articles': [{'title': a['title'], 'url': a['url'], 'published_at': a['published_at'],
                          'reactions': a.get('public_reactions_count', 0), 'comments': a.get('comments_count', 0)}
                         for a in articles[:5]]}


def valid_url(value):
    if not value:
        return None
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme in ('https', 'http') and parsed.netloc and not parsed.username and not parsed.password:
        return value
    if parsed.scheme == 'mailto' and parsed.path and '\n' not in value and '\r' not in value:
        return value
    raise ValueError('Use a valid https:// or mailto: URL')


def load_config(root, environment=None):
    config = json.loads((root / 'profile.json').read_text())
    environment = os.environ if environment is None else environment
    user = config.get('github_username') or environment.get('GITHUB_REPOSITORY_OWNER')
    if user and not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', user):
        raise ValueError('Invalid GitHub username')
    config['github_username'] = user
    for project in config.get('projects', []):
        repo = project.get('repository')
        if repo and not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('repository must be owner/name')
        valid_url(project.get('url'))
    for contact in config.get('contacts', []):
        valid_url(contact.get('url'))
    dev = config.get('dev', {})
    if dev.get('enabled') and not re.fullmatch(r'[A-Za-z0-9_-]+', dev.get('username') or ''):
        raise ValueError('Set dev.username before enabling DEV')
    return config


def read_state(root):
    path = root / 'tools/profile/data/sources.json'
    return json.loads(path.read_text()) if path.exists() else {}


def collect(config, previous, today, environment=None):
    env = os.environ if environment is None else environment
    github_user = config.get('github_username')
    dev = config.get('dev', {})
    dev_user = dev.get('username') if dev.get('enabled') else None
    return {'github': refresh_source(previous.get('github'), github_user,
                lambda: fetch_github(github_user, env.get('PROFILE_TOKEN') or env.get('GITHUB_TOKEN'), today), today.isoformat()),
            'dev': refresh_source(previous.get('dev'), dev_user,
                lambda: fetch_dev(dev_user, env.get('DEV_API_KEY')), today.isoformat())}


def matching_state(config, state):
    """Offline previews must not use a snapshot belonging to a different identity."""
    result = {}
    for key, username in [('github', config.get('github_username')),
                          ('dev', config.get('dev', {}).get('username') if config.get('dev', {}).get('enabled') else None)]:
        source = state.get(key, {})
        if username and (source.get('username') or '').lower() == username.lower():
            result[key] = source
        else:
            result[key] = {'username': username, 'status': 'unavailable' if username else 'disabled', 'data': None, 'as_of': None}
    return result


_font_data = {}


def font_css(used):
    result = []
    for key in sorted(used):
        family, filename = FONTS[key]
        if key not in _font_data:
            path = HERE / 'fonts' / filename
            _font_data[key] = base64.b64encode(path.read_bytes()).decode() if path.exists() else None
        if _font_data[key]:
            result.append(f"@font-face{{font-family:{family};font-weight:{key[1]};src:url(data:font/woff2;base64,{_font_data[key]}) format('woff2')}}")
    return ''.join(result)


def n(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)


def wrap(text, width, size):
    # Monospaced advance is approximately .6 em. Underscore placeholders wrap too.
    return textwrap.wrap(str(text), max(6, int(width / (size * .605))), break_long_words=True)


def clip(text, chars):
    text = str(text)
    return text if len(text) <= chars else text[:max(chars - 1, 1)] + '…'


def as_list(value):
    if value is None:
        return []
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def percent(span):
    return f'{math.floor(span / DESKTOP * 1e6) / 1e4:.4f}'.rstrip('0').rstrip('.') + '%'


class Canvas:
    def __init__(self, width=DESKTOP, x0=0, y0=0, span=None):
        self.width = width
        self.mobile = width < 800
        self.x0, self.y0 = x0, y0
        self.span = width if span is None else span
        self.left, self.right = (12, 468) if self.mobile else (32, 992)
        self.gutter = 60 if self.mobile else 99
        self.x = 76 if self.mobile else 122
        self.end = 452 if self.mobile else 968
        self.parts, self.defs, self.fonts = [], [], set()

    def raw(self, markup):
        self.parts.append(markup)

    def line(self, x1, y1, x2, y2, color=LINE):
        self.raw(f'<path d="M{n(x1)} {n(y1)}L{n(x2)} {n(y2)}" fill="none" stroke="{color}"/>')

    def text(self, x, y, text, size=13, color=TEXT, weight=400, anchor='start', font='mono', spacing=0, cls='', halo=False):
        self.fonts.add((font, weight))
        attrs = [f'x="{n(x)}"', f'y="{n(y)}"', f'font-size="{n(size)}"', f'fill="{color}"']
        if halo:
            attrs.append(f'stroke="{BG}" stroke-width="4" paint-order="stroke"')
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if anchor != 'start':
            attrs.append(f'text-anchor="{anchor}"')
        if spacing:
            attrs.append(f'letter-spacing="{n(spacing)}"')
        classes = ' '.join(filter(None, ['s' if font == 'sans' else '', cls]))
        if classes:
            attrs.append(f'class="{classes}"')
        self.raw('<text ' + ' '.join(attrs) + '>' + html.escape(str(text)) + '</text>')

    def paragraph(self, x, y, text, width, size=13, color=TEXT, leading=20):
        for line in wrap(text, width, size):
            self.text(x, y, line, size, color)
            y += leading
        return y

    def icon(self, name, x, y, size=16, color=FG):
        self.raw(f'<g transform="translate({n(x)} {n(y)}) scale({n(size / 16)})">' + ICONS[name].format(c=color, b=BG) + '</g>')

    def arrow(self, x, y, color=SOFT):
        self.raw(f'<path d="M{n(x)} {n(y)}h15m-4.5 -4l4.5 4-4.5 4" fill="none" stroke="{color}" stroke-width="1.2"/>')

    def dot(self, x, y, color=ACCENT, radius=3.5):
        self.raw(f'<circle class="pulse" cx="{n(x)}" cy="{n(y)}" r="{n(radius)}" fill="{color}"/>')

    def tick(self, x, y, full=False):
        self.raw(f'<path d="M{n(x - 4)} {n(y + .5)}H{n(x + 5)}M{n(x + .5)} {n(y - 4 if full else y)}V{n(y + 5)}" fill="none" stroke="{SOFT}"/>')

    def rail(self, x, y1, y2, tail=True):
        self.line(x + .5, y1, x + .5, y2)
        if tail:
            self.line(x + .5, y2 - 4, x + .5, y2, SOFT)

    def rails(self, y1, y2, tail=True):
        self.rail(self.left, y1, y2, tail)
        self.rail(self.right, y1, y2, tail)

    def rule(self, y=0, marks=(), full=False):
        self.line(self.left, y + .5, self.right, y + .5)
        for x in (self.left, self.right, *marks):
            self.tick(x, y, full)

    def number(self, value, y=35.5, x=None):
        x = (24 if self.mobile else 53) if x is None else x
        self.text(x, y, f'{value:02d}', 15, SOFT)
        self.raw(f'<path d="M{x} {n(y - 19)}h6M{x} {n(y + 7)}h7m3 0h5" fill="none" stroke="{SOFT}" stroke-opacity=".7"/>')

    def label(self, title, y=34, x=None):
        x = self.x if x is None else x
        size = 12 if self.mobile else 11.5
        self.text(x, y, '/', size, DIM)
        self.text(x + 12, y, str(title).upper(), size, TEXT, spacing=1)

    def chips(self, x, top, labels, limit):
        size, height, cursor = (12, 23, x) if self.mobile else (11, 21, x)
        if not labels:
            return top - 8
        for label in labels:
            label = clip(label, int((limit - x - 18) / (size * .6)))
            width = len(label) * size * .6 + 18
            if cursor > x and cursor + width > limit:
                cursor, top = x, top + height + 7
            self.raw(f'<rect x="{n(cursor)}" y="{n(top)}" width="{n(width)}" height="{height}" rx="2.5" fill="{PANEL}"/>')
            self.text(cursor + 9, top + height / 2 + size * .36, label, size, TEXT)
            cursor += width + 10
        return top + height

    def svg(self, height, title, description):
        css = ("text{font-family:JBM,ui-monospace,Menlo,Consolas,monospace}.s{font-family:INT,Inter,'Helvetica Neue',Arial,sans-serif}"
               '@keyframes breathe{0%,100%{opacity:1}50%{opacity:.35}}.pulse{animation:breathe 3s ease-in-out infinite}'
               '@media(prefers-reduced-motion:reduce){*{animation:none!important}}')
        defs = '<defs>' + ''.join(self.defs) + '</defs>' if self.defs else ''
        box = f'{n(self.x0)} {n(self.y0)} {n(self.span)} {n(height)}'
        return (f'<svg xmlns="{NS}" width="{n(self.span)}" height="{n(height)}" viewBox="{box}" role="img" aria-labelledby="title desc">'
                f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(description)}</desc>'
                f'<style>{font_css(self.fonts)}{css}</style>{defs}'
                f'<rect x="{n(self.x0)}" y="{n(self.y0)}" width="{n(self.span)}" height="{n(height)}" fill="{BG}"/>'
                + ''.join(self.parts) + '</svg>\n')


def hero_geometry(config, width):
    mobile = width < 800
    geo = (dict(top=14, nav=62, gutter=60, x=76, cut=255, art=270, row=84, inset=10, size=76, room=376, wrap=376, text=15.5, leading=23)
           if mobile else
           dict(top=21, nav=77, gutter=128, x=150, cut=544, art=585, row=79, inset=15, size=84, room=405, wrap=375, text=14.5, leading=21))
    words = str(config.get('name') or 'Valdeir Júnior').split() or ['?']
    geo['lines'] = [words[0], ' '.join(words[1:])] if len(words) > 1 else words
    geo['size'] = min(geo['size'], geo['room'] / (max(len(line) for line in geo['lines']) * .56))
    first = geo['nav'] + (60 if mobile else 58) + geo['size'] * .727
    geo['baselines'] = [first + index * geo['size'] * .905 for index in range(len(geo['lines']))]
    geo['headline'] = wrap(config.get('headline') or '', geo['wrap'], geo['text'])
    geo['desc_y'] = geo['baselines'][-1] + (38 if mobile else 41)
    last = geo['desc_y'] + max(len(geo['headline']) - 1, 0) * geo['leading']
    geo['row_top'] = math.ceil(last + (24 if mobile else 29))
    geo['bottom'] = geo['row_top'] + geo['row']
    geo['art_top'] = geo['row_top'] if mobile else geo['nav']
    count = len(config.get('contacts') or [])
    geo['cell'] = (geo['cut'] - geo['gutter']) / max(count, 3)
    geo['rest'] = geo['gutter'] + count * geo['cell']
    return geo


def hero_art(c, geo, config, year):
    x1, y1, x2, y2 = geo['art'], geo['art_top'], c.right, geo['bottom'] - geo['inset']
    cx, cy, r = (x1 + 148, y1 + 98, 82) if c.mobile else (x1 + 157, y1 + 241, 172)
    px, py = cx + r * .517, cy - r * .856
    c.defs.append(f'<clipPath id="panel"><rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}"/></clipPath>')
    c.defs.append(f'<radialGradient id="glow" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{r}">'
                  '<stop offset="0" stop-color="#7a68c2" stop-opacity="0"/><stop offset=".7" stop-color="#7a68c2" stop-opacity="0"/>'
                  '<stop offset=".92" stop-color="#7a68c2" stop-opacity=".3"/><stop offset="1" stop-color="#cbbcff" stop-opacity=".62"/></radialGradient>')
    axis = f'x1="{n(cx - r * .75)}" y1="{n(cy + r * .55)}" x2="{n(cx + r * .45)}" y2="{n(cy - r * .5)}"'
    c.defs.append(f'<linearGradient id="fade" gradientUnits="userSpaceOnUse" {axis}>'
                  f'<stop offset="0" stop-color="{BG}"/><stop offset=".5" stop-color="{BG}"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>')
    c.defs.append(f'<linearGradient id="limb" gradientUnits="userSpaceOnUse" {axis}>'
                  '<stop offset="0" stop-color="#e4dafc" stop-opacity=".1"/><stop offset=".5" stop-color="#e4dafc" stop-opacity=".45"/>'
                  '<stop offset="1" stop-color="#e4dafc"/></linearGradient>')
    disc = f'cx="{cx}" cy="{cy}" r="{r}"'
    inner = f'cx="{n(cx - r * .31)}" cy="{n(cy + r * .52)}"'
    c.raw(f'<g clip-path="url(#panel)" fill="none">'
          f'<circle {disc} fill="url(#glow)"/><circle {disc} fill="url(#fade)"/>'
          f'<circle cx="{n(cx - r * .17)}" cy="{n(cy + r * .23)}" r="{n(r * 1.45)}" stroke="{LINE}"/>'
          f'<circle {inner} r="{n(r * .7)}" stroke="#3a444c"/><circle {inner} r="{n(r * .965)}" stroke="#3a444c"/>'
          f'<circle {disc} stroke="url(#limb)" stroke-width="1.6"/>'
          f'<path d="M{x1} {n(py)}H{x2}M{n(px)} {y1}V{y2}" stroke="#5a6470" stroke-opacity=".55"/>'
          f'<circle cx="{n(px)}" cy="{n(py)}" r="10" fill="{ACCENT}" fill-opacity=".18"/>'
          f'<rect class="pulse" x="{n(px - 3.2)}" y="{n(py - 3.2)}" width="6.4" height="6.4" fill="#d9c6ff"/></g>')
    c.line(x1 + .5, y1, x1 + .5, y2)
    c.line(x1, y2 + .5, x2, y2 + .5)
    if c.mobile:
        return
    if year:
        c.text(x2 - 22, y1 + 40, '/ ' + year, 10.5, DIM, anchor='end', spacing=1)
    lines = textwrap.wrap(str(config.get('motto') or '').upper(), 22)[-5:]
    for index, line in enumerate(lines):
        c.text(x2 - 15, y2 - 19 - (len(lines) - 1 - index) * 12.5, line, 8.5, DIM, anchor='end', spacing=1.2, halo=True)


def hero_top(config, year, width):
    geo = hero_geometry(config, width)
    c = Canvas(width)
    top, nav, gutter, x, height = geo['top'], geo['nav'], geo['gutter'], geo['x'], geo['row_top']
    name = ' '.join(geo['lines'])
    words = name.split()
    initials = (words[0][0] + words[-1][0] if len(words) > 1 else name[:2]).upper()
    role = str(config.get('role') or '[YOUR_ROLE]').upper()
    middle = (top + nav) / 2
    c.rails(top, height, tail=False)
    c.rule(top, full=True)
    c.rule(nav, full=True)
    c.text(24 if c.mobile else 50, middle + 7, initials, 20 if c.mobile else 21, SOFT)
    divider = gutter if c.mobile else 97
    c.line(divider + .5, top, divider + .5, nav)
    role_x = x if c.mobile else 110
    c.text(role_x, middle + 4, '/', 11, DIM)
    c.text(role_x + 12, middle + 4, clip(role, 30 if c.mobile else 44), 11, TEXT, spacing=1.2)
    c.dot(c.end - 3, middle)
    if not c.mobile:
        cursor = 940
        for index in range(len(NAV), 0, -1):
            label = NAV[index - 1]
            c.text(cursor, middle + 4, label, 10, FG if index == 1 else TEXT, anchor='end', spacing=.8)
            cursor -= len(label) * 6.8 + 5
            c.text(cursor, middle + 4, f'{index:02d}', 10, SOFT, anchor='end', spacing=.8)
            cursor -= 2 * 6.8 + 12
    c.text(24 if c.mobile else 53, nav + (38 if c.mobile else 40), '01', 15, SOFT)
    if c.mobile:
        c.label('Profile', nav + 36)
    else:
        c.text(53, nav + 55, '/ PROFILE', 8.5, DIM, spacing=1)
    c.line(gutter + .5, nav, gutter + .5, height)
    for line, baseline, color in zip(geo['lines'], geo['baselines'], (FG, ACCENT)):
        c.text(x - geo['size'] * .04, baseline, line, geo['size'], color, 800, font='sans', spacing=-geo['size'] * .028)
    y = geo['desc_y']
    for line in geo['headline']:
        c.text(x, y, line, geo['text'], TEXT)
        y += geo['leading']
    if not c.mobile:
        hero_art(c, geo, config, year)
    return c.svg(height, name, name + '. ' + str(config.get('headline') or ''))


def hero_gutter(config, width):
    geo = hero_geometry(config, width)
    c = Canvas(width, 0, geo['row_top'], geo['gutter'])
    c.rail(c.left, geo['row_top'], geo['bottom'])
    return c.svg(geo['row'], 'Profile frame', 'Decorative frame')


def contact_icon(contact):
    url = str(contact.get('url') or '').lower()
    label = str(contact.get('label') or '').lower()
    if url.startswith('mailto:') or 'mail' in label:
        return 'mail'
    host = urllib.parse.urlsplit(url).netloc
    for name in ('github', 'linkedin'):
        if name in host or name in label:
            return name
    return 'link'


def contact_alt(contact):
    return '. '.join(str(part) for part in (contact.get('label'), contact.get('detail')) if part)


def hero_link(config, index, width):
    geo = hero_geometry(config, width)
    contact = config['contacts'][index]
    left = geo['gutter'] + index * geo['cell']
    c = Canvas(width, left, geo['row_top'], geo['cell'])
    if index == 0:
        c.line(geo['gutter'] + .5, geo['row_top'], geo['gutter'] + .5, geo['bottom'])
    label = str(contact.get('label') or '')
    pad = geo['x'] - geo['gutter']
    live = bool(contact.get('url'))
    if c.mobile:
        c.icon(contact_icon(contact), left + pad, geo['row_top'] + 22, 24, FG if live else DIM)
    else:
        c.icon(contact_icon(contact), left + pad, geo['row_top'] + 17, 16, FG if live else DIM)
        room = int((geo['cell'] - pad - 34) / 7.3)
        if room >= 3:
            c.text(left + pad + 26, geo['row_top'] + 29.5, clip(label, room), 12, TEXT if live else DIM)
    return c.svg(geo['row'], label or 'Contact', contact_alt(contact))


def hero_rest(config, year, width):
    geo = hero_geometry(config, width)
    c = Canvas(width, geo['rest'], geo['row_top'], width - geo['rest'])
    if not config.get('contacts'):
        c.line(geo['gutter'] + .5, geo['row_top'], geo['gutter'] + .5, geo['bottom'])
    hero_art(c, geo, config, year)
    c.rail(c.right, geo['row_top'], geo['bottom'])
    if not c.mobile and geo['art'] - geo['rest'] >= 40:
        c.arrow(geo['art'] - 33, geo['row_top'] + 25)
    return c.svg(geo['row'], 'Profile artwork', 'Decorative artwork')


def now_items(config):
    names = ['file', 'book', 'people']
    result = []
    for index, item in enumerate(config.get('now_items') or []):
        entry = item if isinstance(item, dict) else {'text': item}
        icon = entry.get('icon') if entry.get('icon') in names else names[index % len(names)]
        result.append((icon, str(entry.get('text') or '')))
    return result


def now_block(c, x, top, paragraphs, items, right):
    size, leading, small = (14.5, 22, 13) if c.mobile else (13, 20, 11)
    c.dot(x + 4.5, top + 63, MINT, 4)
    c.text(x + 17, top + 67.5, 'Currently working on', small + 1, MINT)
    y = top + 98
    for paragraph in paragraphs:
        y = c.paragraph(x, y, paragraph, right - x, size, TEXT, leading) + 6
    last = y - 6 - leading if paragraphs else top + 67.5
    if not items:
        return last
    rule = last + 21
    c.line(x - 15, rule + .5, right + 1, rule + .5)
    y = rule + 25
    for icon, text in items:
        c.icon(icon, x, y - 12.5, 16, FG)
        for line in wrap(text, right - x - 21, small):
            c.text(x + 33, y, line, small, TEXT)
            last = y
            y += 17
        y += 9
    return last


def about_now(config, width):
    c = Canvas(width)
    about, now, items = as_list(config.get('about')), as_list(config.get('now')), now_items(config)
    footer = str(config.get('about_footer') or '').upper()
    split = 529
    c.rule(marks=() if c.mobile else (split,))
    c.number(2)
    c.label('About')
    size, leading = (14.5, 22) if c.mobile else (13, 19.5)
    y = 69
    for paragraph in about:
        y = c.paragraph(c.x, y, paragraph, (c.end if c.mobile else split - 24) - c.x, size, TEXT, leading) + 8
    last = y - 8 - leading if about else 34
    if c.mobile:
        if footer:
            c.arrow(c.x, last + 30)
            for index, line in enumerate(textwrap.wrap(footer, 44)):
                last += 14 if index else 34
                c.text(c.x + 28, last, line, 9, DIM, spacing=1.2)
        top = math.ceil(last + 26)
        c.rule(top)
        c.number(3, top + 35.5)
        c.label('Now', top + 34)
        height = math.ceil(now_block(c, c.x, top, now, items, c.end) + 30)
    else:
        right = now_block(c, 621, 0, now, items, c.end)
        height = max(245, math.ceil(last + (58 if footer else 30)), math.ceil(right + 29))
        if footer:
            c.arrow(c.x, height - 30)
            c.text(c.x + 77, height - 26, clip(footer, 48), 8.5, DIM, spacing=1.2)
        c.line(split + .5, 0, split + .5, height)
        c.number(3, x=551)
        c.label('Now', x=621)
    c.line(c.gutter + .5, 0, c.gutter + .5, height)
    c.rails(0, height)
    return c.svg(height, 'About and Now', about_now_alt(config))


def about_now_alt(config):
    now = as_list(config.get('now')) + [text for _, text in now_items(config)]
    return 'About: ' + ' '.join(as_list(config.get('about'))) + ' Now: ' + ' '.join(now)


def stack_alt(config):
    return 'Stack. ' + '; '.join(str(row.get('area') or '') + ': ' + ', '.join(as_list(row.get('tools'))) for row in config.get('stack') or [])


def stack(config, width):
    c = Canvas(width)
    rows = config.get('stack') or []
    per = 2 if c.mobile else 5
    left = c.x - 12
    column = (c.end + 8 - left) / per
    size, step, small = (14, 21, 12) if c.mobile else (12, 18.5, 11)
    c.rule()
    c.number(4)
    c.label('Stack')
    y = 67
    bottom = y
    if not rows:
        bottom = c.paragraph(c.x, y, '[YOUR_TECHNICAL_STACK]', c.end - c.x, size, TEXT, step) - step
    for start in range(0, len(rows), per):
        group = rows[start:start + per]
        bottom = y
        for index, row in enumerate(group):
            x = left + index * column
            c.text(x, y, '/', small, DIM)
            area = clip(str(row.get('area') or '').upper(), int((column - 30) / (small * .6 + 1)))
            c.text(x + 12, y, area, small, MINT if (start + index) % 2 == 0 else ACCENT, spacing=1)
            line_y = y + 23
            for tool in as_list(row.get('tools')):
                for line in wrap(tool, column - 30, size):
                    c.text(x + 12, line_y, line, size, TEXT)
                    line_y += step
            bottom = max(bottom, line_y - step)
        for index in range(1, len(group)):
            x = left + index * column - 12.5
            c.line(x, y - 12, x, bottom + 8)
        y = bottom + 46
    height = max(96 if c.mobile else 152, math.ceil(bottom + 25))
    c.line(c.gutter + .5, 0, c.gutter + .5, height)
    c.rails(0, height)
    return c.svg(height, 'Stack', stack_alt(config))


def section_heading(number, title, width, caption=None):
    c = Canvas(width)
    height = 56 if c.mobile else 55
    c.rule()
    c.number(number, 34.5)
    c.label(title, 35)
    if caption and not c.mobile:
        c.text(922, 38, caption.upper(), 8.5, DIM, anchor='end', spacing=1.2)
        c.arrow(951, 35)
    c.line(c.gutter + .5, 0, c.gutter + .5, height)
    c.rails(0, height)
    return c.svg(height, title, title)


def thumbnail(c, index, x, y, w, h):
    c.defs.append(f'<clipPath id="thumb"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>')
    kind = (index - 1) % 3
    if kind == 0:
        cx, cy, r = x, y - h * .52, h * 1.1
        reach = r * 1.75
        c.defs.append(f'<radialGradient id="haze" gradientUnits="userSpaceOnUse" cx="{n(cx)}" cy="{n(cy)}" r="{n(reach)}">'
                      f'<stop offset="0" stop-color="#cdbfff" stop-opacity="0"/><stop offset="{n(r / reach - .002)}" stop-color="#cdbfff" stop-opacity="0"/>'
                      f'<stop offset="{n(r / reach)}" stop-color="#cdbfff" stop-opacity=".62"/><stop offset=".74" stop-color="#7f70c4" stop-opacity=".2"/>'
                      f'<stop offset="1" stop-color="{BG}" stop-opacity="0"/></radialGradient>')
        art = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#haze)"/>'
               f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="#ddd2ff" stroke-width="1.3"/>')
    elif kind == 1:
        cx, cy, r = x + w / 2, y + h / 2 - 3, h * .37
        points = [(cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a))) for a in range(90, 450, 60)]
        outline = ' '.join(f'{n(px)},{n(py)}' for px, py in points)
        spokes = ''.join(f'M{n(cx)} {n(cy)}L{n(px)} {n(py)}' for px, py in points)
        art = (f'<polygon points="{outline}" fill="none" stroke="#4d5666"/><path d="{spokes}" fill="none" stroke="#3a424f"/>'
               f'<circle cx="{n(cx)}" cy="{n(cy)}" r="8" fill="{ACCENT}" fill-opacity=".18"/><circle cx="{n(cx)}" cy="{n(cy)}" r="3.3" fill="#d2bdff"/>'
               f'<circle cx="{n(x + w * .1)}" cy="{n(y + h * .87)}" r="1.5" fill="{ACCENT}"/>')
    else:
        c.defs.append(f'<linearGradient id="lit" gradientUnits="userSpaceOnUse" x1="{x}" y1="{y + h}" x2="{n(x + w * .8)}" y2="{n(y + h * .2)}">'
                      f'<stop offset="0" stop-color="#b7abf0" stop-opacity=".62"/><stop offset=".55" stop-color="#6b61a8" stop-opacity=".18"/>'
                      f'<stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>')
        steps = [(.14, .49), (.34, .38), (.5, .27), (.64, .16), (.78, .08)]
        path = f'M{x} {n(y + h * .58)}L{n(x + w * .14)} {n(y + h * .49)}'
        for (sx, sy), following in zip(steps, steps[1:] + [(1, .08)]):
            path += f'H{n(x + w * following[0])}' + (f'V{n(y + h * following[1])}' if following[1] != sy else '')
        slopes = ''.join(f'M{n(x + w * sx)} {n(y + h * sy)}l{n(w)} {n(w * .43)}' for sx, sy in [(0, .58), (0, .74), (0, .9)] + steps)
        art = (f'<path d="{path}V{y + h}H{x}Z" fill="url(#lit)"/><path d="{slopes}" fill="none" stroke="#6f6aa0" stroke-opacity=".5"/>'
               f'<path d="{path}" fill="none" stroke="#c9bfff" stroke-opacity=".7"/>')
    c.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#090d10"/><g clip-path="url(#thumb)">{art}</g>'
          f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" fill="none" stroke="#2a313a"/>')


def project_row(project, index, github, width):
    c = Canvas(width)
    name = str(project.get('name') or '')
    description = str(project.get('description') or '')
    contribution = project.get('contribution')
    technologies = as_list(project.get('technologies'))
    year = str(project.get('year') or '')
    stars = (github or {}).get('repo_stars', {}).get(project.get('repository'))
    linked = bool(project.get('url') or project.get('repository'))
    c.rule()
    if c.mobile:
        c.text(24, 35, f'{index:02d}', 12.5, SOFT)
        thumbnail(c, index, c.x, 16, 96, 81)
        y = 40
        for line in textwrap.wrap(name, 20)[:2]:
            c.text(c.x + 112, y, line, 19, FG, 800, font='sans')
            y += 23
        c.text(c.x + 112, y + 2, year, 13, SOFT)
        if stars is not None:
            c.text(c.x + 112 + (len(year) * 7.8 + 12 if year else 0), y + 2, f'{stars:,} stars', 11, DIM)
        if linked:
            c.arrow(c.end - 16, 86)
        y = c.paragraph(c.x, 126, description, c.end - c.x, 14, TEXT, 21)
        if contribution:
            y = c.paragraph(c.x, y + 4, 'My contribution: ' + str(contribution), c.end - c.x, 14, DIM, 21)
        height = math.ceil(c.chips(c.x, y - 7, technologies, c.end) + 18)
        edge = c.gutter
    else:
        c.text(53, 31, f'{index:02d}', 12, SOFT)
        thumbnail(c, index, 127, 13, 126, 106)
        c.text(290, 31, clip(name, 46), 18, FG, 800, font='sans')
        y = c.paragraph(290, 54, description, 400, 12, TEXT, 16.5)
        if contribution:
            y = c.paragraph(290, y + 3, 'My contribution: ' + str(contribution), 400, 12, DIM, 16.5)
        height = max(133, math.ceil(c.chips(290, y + .5, technologies, 820) + 12))
        c.text(861, height / 2 + 4, year, 12.5, SOFT)
        if stars is not None:
            c.text(861, height / 2 + 21, f'{stars:,} stars', 9.5, DIM)
        if linked:
            c.arrow(951, height / 2)
        edge = c.gutter
    c.line(edge + .5, 10, edge + .5, height - 10, EDGE)
    c.rails(0, height)
    desc = name + '. ' + description
    if contribution:
        desc += ' My contribution: ' + str(contribution) + '.'
    if stars is not None:
        desc += f' {stars:,} stars.'
    return c.svg(height, name, desc), desc


def list_row(c, index, lines, meta, linked):
    c.rule()
    if index is not None:
        c.text(24 if c.mobile else 53, 31, f'{index:02d}', 12, SOFT)
    size, leading = (14.5, 21) if c.mobile else (14, 20)
    y = 31
    for line in lines:
        c.text(c.x, y, line, size, FG)
        y += leading
    for line in meta:
        c.text(c.x, y - 2, line, 10.5, DIM)
        y += 15
    height = math.ceil(y + 6)
    if linked:
        c.arrow(c.end - 17, height / 2)
    c.line(c.gutter + .5, 10, c.gutter + .5, height - 10, EDGE)
    c.rails(0, height)
    return height


def article_row(article, index, width):
    c = Canvas(width)
    text = f"{article['reactions']:,} reactions · {article['comments']:,} comments"
    meta = article['published_at'][:10] + ' · ' + text
    height = list_row(c, index, wrap(article['title'], c.end - c.x - 44, 14.5)[:3], [meta], True)
    desc = article['title'] + '. Published ' + article['published_at'][:10] + '. ' + text
    return c.svg(height, article['title'], desc), desc


def weekly(calendar):
    pad = -len(calendar) % 7
    bins = [0] * math.ceil(len(calendar) / 7)
    for index, (_, count) in enumerate(calendar):
        bins[(index + pad) // 7] += count
    return bins, pad


def years_between(created_at, as_of):
    try:
        start, end = dt.date.fromisoformat(str(created_at)[:10]), dt.date.fromisoformat(str(as_of)[:10])
    except ValueError:
        return None
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def draw_bars(c, calendar, x1, x2, base, peak_height):
    bins, pad = weekly(calendar)
    if not bins:
        c.text(x1, base - 22, 'No contribution calendar available.', 12, DIM)
        return
    pitch = (x2 - x1) / len(bins)
    bar = min(6, max(1.5, pitch * .5))
    peak = max(bins) or 1
    c.raw(f'<path d="M{x1} {base + .5}H{x2}" fill="none" stroke="{LINE}" stroke-dasharray="1 3"/>')
    for index, count in enumerate(bins):
        if count:
            height = max(2, peak_height * count / peak)
            c.raw(f'<rect x="{n(x1 + index * pitch + (pitch - bar) / 2)}" y="{n(base - height)}" width="{n(bar)}" height="{n(height)}" '
                  f'fill="{ACCENT}" fill-opacity="{n(.55 + .45 * count / peak)}"/>')
    marks = []
    for index, (date, _) in enumerate(calendar):
        x = x1 + ((index + pad) // 7) * pitch
        if date[8:10] == '01' and x <= x2 - 16 and (not marks or x - marks[-1][0] >= 24):
            marks.append((x, date))
    if not marks or marks[0][0] - x1 >= 24:
        marks.insert(0, (x1, calendar[0][0]))
    for x, date in marks:
        c.text(x, base + 18, MONTHS[int(date[5:7]) - 1], 8.5, DIM, spacing=.8)


def activity(config, source, width, number):
    c = Canvas(width)
    github = source.get('data')
    left = c.x if c.mobile else 63
    c.rule()
    c.number(number)
    c.label('Activity')
    c.line(c.gutter + .5, 12, c.gutter + .5, 58)
    if not c.mobile:
        c.text(952, 37, 'BUILDING IN PUBLIC', 8.5, DIM, anchor='end', spacing=1.2)
    c.dot(c.end - 3, 34)
    if not github:
        configured = bool(config.get('github_username'))
        desc = 'GitHub data unavailable' if configured else 'GitHub account not configured'
        detail = 'The next successful sync will populate this panel.' if configured else '[YOUR_GITHUB_USERNAME]'
        y = c.paragraph(left, 96, desc, c.end - left, 16, FG, 24)
        y = c.paragraph(left, y + 2, detail, c.end - left, 13, TEXT, 20)
        c.text(left, y + 8, 'DATA NOT CONNECTED', 9, DIM, spacing=1.2)
        bottom = math.ceil(y + 30)
    else:
        calendar = github.get('calendar') or []
        stale = source.get('status') == 'stale'
        total = sum(count for _, count in calendar) if calendar else None
        active = sum(count > 0 for _, count in calendar)
        years = years_between(github.get('created_at'), source.get('as_of'))
        stats = [('Contributions', total), ('Repositories', github.get('repo_count')), ('Years', years)]
        if c.mobile:
            draw_bars(c, calendar, left, c.end, 138, 62)
            for index, (label, value) in enumerate(stats):
                x = left + index * 128
                if index:
                    c.line(x - 16.5, 178, x - 16.5, 226)
                c.text(x, 200, 'N/A' if value is None else f'{value:,}', 21, FG, 700)
                c.text(x, 222, label, 12, TEXT)
            note, bottom = 250, 268
        else:
            draw_bars(c, calendar, left, 607, 123, 58)
            c.line(641.5, 67, 641.5, 135)
            for index, (label, value) in enumerate(stats):
                x = 663 + index * 126
                if index:
                    c.line(x - 21.5, 78, x - 21.5, 135)
                c.text(x, 100, 'N/A' if value is None else f'{value:,}', 19, FG, 700)
                c.text(x, 125, label, 11.5, TEXT)
            note, bottom = 160, 178
        synced = str(source.get('as_of') or 'unknown')
        status = 'Cached data; sync failed' if stale else 'Last successful sync'
        caption = ('CACHED DATA · SYNC FAILED · LAST SYNC ' if stale else 'SYNCED ') + synced
        if calendar:
            caption = f'LAST {len(calendar)} DAYS · {active} ACTIVE DAYS · ' + caption
        c.text(left, note, caption, 8.5, DIM, spacing=1)
        facts = []
        if calendar:
            facts.append(f'{total:,} contributions in the last {len(calendar)} days, {active} active days, {calendar[0][0]} to {calendar[-1][0]}')
        if github.get('repo_count') is not None:
            facts.append(f"{github['repo_count']:,} public repositories")
        if years is not None:
            facts.append(f'{years} years on GitHub')
        desc = 'Activity. ' + ''.join(fact + '. ' for fact in facts) + status + ': ' + synced
    c.rails(0, bottom, tail=False)
    c.rule(bottom, full=True)
    return c.svg(bottom + (14 if c.mobile else 21), 'Activity', desc), desc


def picture(cell):
    filename, alt, url, share = cell
    tag = (f'<picture><source media="(max-width: 600px)" srcset="./assets/{filename}-mobile.svg">'
           f'<img src="./assets/{filename}.svg" width="{share or "100%"}" align="top" alt="{html.escape(alt, quote=True)}"></picture>')
    return '<a href="' + html.escape(url, quote=True) + '">' + tag + '</a>' if url else tag


def render_profile(config, state, root):
    root = Path(root)
    assets = root / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    sources = matching_state(config, state)
    github = sources['github'].get('data')
    dev_source = sources['dev']
    dev = dev_source.get('data')
    year = str(sources['github'].get('as_of') or '')[:4] if github else ''
    name = str(config.get('name') or 'Valdeir Júnior')
    rows = []

    def emit(filename, maker, alt, url=None, share=None):
        for width, suffix in [(DESKTOP, ''), (MOBILE, '-mobile')]:
            value = maker(width)
            (assets / (filename + suffix + '.svg')).write_text(value[0] if isinstance(value, tuple) else value)
        return filename, alt() if callable(alt) else alt, valid_url(url), share

    geo = hero_geometry(config, DESKTOP)
    rows.append([emit('hero', lambda w: hero_top(config, year, w), name + '. ' + str(config.get('headline') or ''))])
    links = [emit('hero-gutter', lambda w: hero_gutter(config, w), '', share=percent(geo['gutter']))]
    for i, contact in enumerate(config.get('contacts') or []):
        links.append(emit('hero-link-' + str(i + 1), lambda w, i=i: hero_link(config, i, w), contact_alt(contact),
                          contact.get('url'), percent(geo['cell'])))
    links.append(emit('hero-art', lambda w: hero_rest(config, year, w), '', share=percent(DESKTOP - geo['rest'])))
    rows.append(links)
    rows.append([emit('about-now', lambda w: about_now(config, w), about_now_alt(config))])
    rows.append([emit('stack', lambda w: stack(config, w), stack_alt(config))])
    rows.append([emit('work', lambda w: section_heading(5, 'Selected work', w, "A few projects I'm proud of"), 'Selected work')])
    for i, p in enumerate(config.get('projects') or [], 1):
        url = p.get('url') or ('https://github.com/' + p['repository'] if p.get('repository') else None)
        rows.append([emit('work-' + str(i), lambda w, p=p, i=i: project_row(p, i, github, w),
                          lambda p=p, i=i: project_row(p, i, github, DESKTOP)[1], url)])
    writing = bool(dev and config.get('dev', {}).get('show_writing', True))
    if writing:
        synced = 'Last successful sync: ' + str(dev_source.get('as_of'))
        stale = dev_source.get('status') == 'stale'
        rows.append([emit('writing', lambda w: section_heading(6, 'Writing / DEV', w),
                          'Writing on DEV. ' + synced + ('. Cached data; sync failed.' if stale else ''))])
        articles = dev.get('articles', [])
        if not articles:
            def empty(w):
                c = Canvas(w)
                return c.svg(list_row(c, None, [], ['No published articles.'], False), 'Writing', 'No published articles.')
            rows.append([emit('writing-empty', empty, 'No published articles.')])
        for i, a in enumerate(articles, 1):
            rows.append([emit('writing-' + str(i), lambda w, a=a, i=i: article_row(a, i, w),
                              lambda a=a, i=i: article_row(a, i, DESKTOP)[1], a['url'])])
        stats = dev.get('stats', {})
        summary = ' · '.join(f'{stats[k]:,} {k}' for k in ['articles', 'reactions', 'comments', 'views', 'followers'] if stats.get(k) is not None)

        def dev_stats(w):
            c = Canvas(w)
            meta = [synced]
            if stale or stats.get('authenticated_status') == 'unavailable':
                meta.append('Some DEV metrics could not be refreshed.')
            return c.svg(list_row(c, None, wrap(summary, c.end - c.x - 44, 14.5), meta, True), 'DEV metrics', summary)
        rows.append([emit('dev-stats', dev_stats, 'DEV metrics. ' + '; '.join(f'{k}: {v}' for k, v in stats.items() if isinstance(v, int)),
                          'https://dev.to/' + config['dev']['username'])])
    number = 7 if writing else 6
    rows.append([emit('activity', lambda w: activity(config, sources['github'], w, number),
                      lambda: activity(config, sources['github'], DESKTOP, number)[1])])
    lines = ['<!-- Generated by tools/profile/update.py. Edit profile.json, then regenerate. -->', '<p align="center">']
    lines.extend(''.join(picture(cell) for cell in row) for row in rows)
    lines.extend(['</p>', ''])
    readme = '\n'.join(lines)
    (root / 'README.md').write_text(readme)
    preview_style = ('*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#e6edf3;font-family:system-ui}'
                     'main{max-width:910px;margin:36px auto;padding:0 32px}p{margin:0;line-height:1.5}img{max-width:100%;vertical-align:top}'
                     'header{font-size:13px;color:#8b949e;margin:0 0 18px}@media(max-width:600px){main{margin:18px auto;padding:0 12px}}')
    preview = ('<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Profile preview</title>'
               '<style>' + preview_style + '</style><main><header>Local README preview</header>' + readme + '</main></html>')
    (root / 'preview.html').write_text('<!doctype html>' + preview)
    records = [cell for row in rows for cell in row]
    keep = {f'{filename}{suffix}.svg' for filename, _, _, _ in records for suffix in ('', '-mobile')}
    # Only remove files in the dedicated generated assets folder.
    for path in assets.glob('*.svg'):
        if path.name not in keep:
            path.unlink()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Render cached data without API calls.')
    parser.add_argument('--root', type=Path, default=ROOT, help='Profile repository root.')
    parser.add_argument('--allow-source-failures', action='store_true', help='Render cached data and expose failure status to Actions without stopping the commit step.')
    parser.add_argument('--date', type=dt.date.fromisoformat, help='Override the reporting date for reproducible tests.')
    args = parser.parse_args()
    config = load_config(args.root)
    today = args.date or dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    state = read_state(args.root)
    if not args.offline:
        state = collect(config, state, today)
        folder = args.root / 'tools/profile/data'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'sources.json').write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n')
    records = render_profile(config, state, args.root)
    print(f'Generated README and {len(records) * 2} SVGs (desktop + mobile).')
    failed = False
    for key, source in matching_state(config, state).items():
        print(key + ': ' + source.get('status', 'unavailable'))
        if not args.offline and source.get('status') in ('stale', 'unavailable'):
            failed = True
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('sources_failed=' + str(failed).lower() + '\n')
    if failed:
        print('A configured data source failed. Previous successful data is preserved.', file=sys.stderr)
        return 0 if args.allow_source_failures else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

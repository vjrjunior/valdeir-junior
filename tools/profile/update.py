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
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PAPER, INK, MUTED, LINE, EDGE, GRID = '#0d1117', '#e6edf3', '#8b949e', '#252b34', '#30363d', '#232a33'
ACCENT, ACCENT_TEXT = '#8b5cf6', '#a78bfa'
DOT_COLORS = ['#31235e', '#31235e', '#4a3390', '#6d4bd1', '#8b5cf6', '#a78bfa']
DOT_SIZES = [.24, .34, .46, .58, .7, .82]
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
LOW_CUT = .14
NS = 'http://www.w3.org/2000/svg'
DESKTOP, MOBILE = 1024, 480
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
FONTS = {('sans', 400): ('HG', 'host-grotesk-latin-400-normal.woff2'),
         ('sans', 500): ('HG', 'host-grotesk-latin-500-normal.woff2'),
         ('mono', 400): ('DM', 'dm-mono-latin-400-normal.woff2')}
METRICS = json.loads((HERE / 'fonts/metrics.json').read_text())
ICONS = {
    'github': '<path fill="{c}" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>',
    'linkedin': '<rect x="1" y="1" width="14" height="14" rx="1.6" fill="{c}"/><path fill="{b}" d="M3.6 6.4h2v6h-2zM4.6 3.3a1.15 1.15 0 110 2.3 1.15 1.15 0 010-2.3zM7 6.4h1.9v.85c.4-.65 1.1-1.05 2-1.05 1.6 0 2.1 1.05 2.1 2.55v3.65h-2V9.1c0-.8-.25-1.25-.9-1.25-.75 0-1.1.5-1.1 1.35v3.2H7z"/>',
    'mail': '<rect x="1" y="2.8" width="14" height="10.4" rx="1.2" fill="{c}"/><path d="M2 4.4l6 4.6 6-4.6" fill="none" stroke="{b}" stroke-width="1.5"/>',
    'link': '<g fill="none" stroke="{c}" stroke-width="1.3"><circle cx="8" cy="8" r="6.3"/><path d="M1.7 8h12.6M8 1.7c-2.6 2.2-2.6 10.4 0 12.6M8 1.7c2.6 2.2 2.6 10.4 0 12.6"/></g>',
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


def mix(alpha, color=INK, base=PAPER):
    top = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    bottom = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(a * alpha + b * (1 - alpha)):02x}' for a, b in zip(top, bottom))


INK75, INK70, INK35 = mix(.75), mix(.7), mix(.35)
JOINT = mix(.5, MUTED)


def n(value):
    if isinstance(value, float):
        text = f'{value:.2f}'.rstrip('0').rstrip('.')
        return '0' if text == '-0' else text
    return str(value)


def clamp01(value):
    return 0.0 if value < 0 else 1.0 if value > 1 else value


def measure(text, size, font='sans', spacing=0.0):
    table = METRICS['dm400' if font == 'mono' else 'hg500']
    advance, kern = table['adv'], table['kern']
    total = sum(advance.get(ch, 600) for ch in text) + sum(kern.get(text[i:i + 2], 0) for i in range(len(text) - 1))
    return total * size / 1000 + spacing * len(text)


def wrap_runs(runs, width, size, font='sans', spacing=0.0):
    words = [(word, color) for text, color in runs for word in str(text).split()]
    space = measure(' ', size, font, spacing)
    lines, line, used = [], [], 0.0
    for word, color in words:
        width_word = measure(word, size, font, spacing)
        if line and used + space + width_word > width:
            lines.append(line)
            line, used = [], 0.0
        used += (space if line else 0) + width_word
        line.append((word, color))
    if line:
        lines.append(line)
    return lines


def ring(cx):
    return ('arc', cx, 32, 14.5, 0, 360)


def stem(x, top, bottom=50):
    return ('seg', x, top, x, bottom, False)


GLYPHS = {
    'a': (36, [ring(18), stem(32.5, 14)]),
    'c': (36, [('arc', 18, 32, 14.5, 45, 315)]),
    'd': (36, [ring(18), stem(32.5, 0)]),
    'e': (36, [('seg', 3.5, 32, 32.5, 32, False), ('arc', 18, 32, 14.5, 0, 315)]),
    'i': (7, [stem(3.5, 14), ('seg', 3.5, 0, 3.5, 7, False)]),
    'j': (7, [stem(3.5, 14), ('seg', 3.5, 0, 3.5, 7, False)]),
    'l': (7, [stem(3.5, 0)]),
    'n': (36, [stem(3.5, 14), ('arc', 18, 32, 14.5, 0, 180), stem(32.5, 32)]),
    'o': (36, [ring(18)]),
    'r': (26, [stem(3.5, 14), ('arc', 18, 32, 14.5, 75, 180)]),
    'u': (36, [stem(3.5, 14, 32), ('arc', 18, 32, 14.5, 180, 360), stem(32.5, 14)]),
    'v': (36, [('seg', 3.5, 17.5, 18, 46.5, True), ('seg', 18, 46.5, 32.5, 17.5, True)]),
}


def stroke_distance(px, py, part):
    if part[0] == 'seg':
        _, x1, y1, x2, y2, round_caps = part
        dx, dy = x2 - x1, y2 - y1
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        if not round_caps and (t < 0 or t > 1):
            return 1e9
        t = min(1, max(0, t))
        return math.hypot(px - x1 - t * dx, py - y1 - t * dy)
    _, cx, cy, r, a0, a1 = part
    span = (a1 - a0) % 360 or 360
    if (math.degrees(math.atan2(cy - py, px - cx)) - a0) % 360 > span:
        return 1e9
    return abs(math.hypot(px - cx, py - cy) - r)


def wordmark_field(word):
    parts, cursor = [], 0.0
    for ch in word.lower():
        if ch == ' ':
            cursor += 20
            continue
        if ch not in GLYPHS:
            continue
        width, strokes = GLYPHS[ch]
        for part in strokes:
            shifted = list(part)
            shifted[1] += cursor
            if part[0] == 'seg':
                shifted[3] += cursor
            parts.append(tuple(shifted))
        cursor += width + 8
    total = max(cursor - 8, 1)
    grid = {'scale': 1, 'x': 0, 'y': 0}

    def prepare(cols, rows):
        grid['scale'] = min(cols * .98 / total, rows * .84 / 50)
        grid['x'] = (cols - total * grid['scale']) / 2
        grid['y'] = (rows - 50 * grid['scale']) / 2

    def field(u, v, t, col, row):
        px = (col + .5 - grid['x']) / grid['scale']
        py = (row + .5 - grid['y']) / grid['scale']
        if px < -6 or py < -6 or px > total + 6 or py > 56:
            return 0
        distance = min(stroke_distance(px, py, part) for part in parts)
        coverage = clamp01((4.4 - distance) * grid['scale'] + .5)
        if coverage <= .02:
            return 0
        return coverage * (.74 + .26 * math.sin(u * 4.6 - t * 1.4 + math.sin(v * 3 + t * .5) * 1.2))
    field.prepare = prepare
    return field


SPRITES = {
    'code': (['...66............66...',
              '..6................6..',
              '..6................6..',
              '..6..5555.333......6..',
              '..6................6..',
              '..6....444.3333....6..',
              '.6..................6.',
              '6......333.55........6',
              '.6..................6.',
              '..6....44444.......6..',
              '..6................6..',
              '..6..333.a.........6..',
              '..6................6..',
              '..6................6..',
              '...66............66...'],
             {'a': (6, 'blink', 1.1, 0)}),
    'browser': (['5555555555555555555555',
                 '5.6.4.4..............5',
                 '5555555555555555555555',
                 '5....................5',
                 '5.aaa.......aa.aa.aa.5',
                 '5....................5',
                 '5.bbbbbbbb..aaaaaaaa.5',
                 '5.bbbbbbbb..aaaaaa...5',
                 '5.bbbbbbbb..aaaaaaa..5',
                 '5.bbbbbbbb..aaaa.....5',
                 '5....................5',
                 '5.bbbbb.bbbbbb.bbbbb.5',
                 '5.bbbbb.bbbbbb.bbbbb.5',
                 '5....................5',
                 '5555555555555555555555'],
                {'a': (5, 'shimmer', 2.4, 0), 'b': (4, 'shimmer', 2.4, 0)}),
    'database': (['....5555555555....',
                  '.555..........555.',
                  '6................6',
                  '6666..........6666',
                  '6...6666666666...6',
                  '6................6',
                  '6............a...6',
                  '6666..........6666',
                  '6...6666666666...6',
                  '6................6',
                  '6............b...6',
                  '6666..........6666',
                  '6...6666666666...6',
                  '6................6',
                  '6............c...6',
                  '.666..........666.',
                  '....6666666666....'],
                 {'a': (6, 'flash', 1.8, 0), 'b': (6, 'flash', 1.8, .3), 'c': (6, 'flash', 1.8, .6)}),
    'server': (['.55555555555555555555.',
                '5....................5',
                '5.a.b....3.3.3.3.3.3.5',
                '5....................5',
                '.55555555555555555555.',
                '......................',
                '.55555555555555555555.',
                '5....................5',
                '5.c.d....3.3.3.3.3.3.5',
                '5....................5',
                '.55555555555555555555.',
                '......................',
                '.55555555555555555555.',
                '5....................5',
                '5.e.f....3.3.3.3.3.3.5',
                '5....................5',
                '.55555555555555555555.'],
               {'a': (6, 'flash', 1.3, 0), 'b': (5, 'blink', 2.1, .4), 'c': (6, 'flash', 1.7, .9),
                'd': (5, 'blink', 2.7, 1.3), 'e': (6, 'flash', 1.1, .5), 'f': (5, 'blink', 3.1, 2)}),
    'branch': (['..............666...666..',
                '..............6c65556d6..',
                '..............666...666..',
                '.............5...........',
                '............5............',
                '...........5.............',
                '..........5..............',
                '.........5...............',
                '666...666...666...666....',
                '6a65556b65556e65556f65555',
                '666...666...666...666....'],
               {'a': (6, 'flash', 3, 0), 'b': (6, 'flash', 3, .6), 'e': (6, 'flash', 3, 1.2),
                'c': (6, 'flash', 3, 1.4), 'f': (6, 'flash', 3, 1.8), 'd': (6, 'flash', 3, 2)}),
}
SPRITE_FRAMES = {'blink': '0%,50%{opacity:1}50.1%,100%{opacity:0}',
                 'flash': '0%{opacity:1}40%,100%{opacity:.15}',
                 'shimmer': '0%,40%,100%{opacity:.3}20%{opacity:1}'}
CODE = '''import { collect } from './sources'
import { render } from './render'
import { commit } from './git'

export async function build(profile: Profile) {
  const data = await collect(profile.sources)
  const sections = profile.layout.map((name) => {
    const section = registry[name]
    if (!section) return null
    return section.render(data, { width: 1024 })
  })
  return sections.filter(Boolean).join('\\n')
}

export function schedule(job: Job, every = '1d') {
  return cron(every, async () => {
    const result = await job.run()
    if (result.changed) {
      await commit(result.files, 'Refresh profile')
    }
  })
}

export async function ship(branch: string) {
  const checks = await run(['lint', 'test', 'build'])
  if (checks.some((check) => !check.ok)) {
    throw new Error(`Blocked: ${checks.length} checks`)
  }
  return deploy(branch, { preview: false })
}'''
CODE_KEYWORDS = {'import', 'from', 'export', 'async', 'function', 'const', 'await', 'return', 'if', 'null', 'throw', 'new', 'false', 'true'}
CODE_TOKENS = re.compile(r"'[^']*'|\d+|[A-Za-z_]\w*|\S")
TYPE_STEP, TYPE_PAUSE, TYPE_SCROLL = .02, .26, .14


def to_level(value, col, row):
    if value >= LOW_CUT:
        return min(6, 2 + int((value - LOW_CUT) / (1 - LOW_CUT) * 5))
    if value <= .015:
        return 0
    return 1 if value / LOW_CUT > (BAYER[((row & 3) << 2) | (col & 3)] + .5) / 16 else 0


_font_data = {}


def font_css(used):
    result = []
    for key in sorted(used):
        family, filename = FONTS[key]
        if key not in _font_data:
            _font_data[key] = base64.b64encode((HERE / 'fonts' / filename).read_bytes()).decode()
        result.append(f"@font-face{{font-family:{family};font-weight:{key[1]};src:url(data:font/woff2;base64,{_font_data[key]}) format('woff2')}}")
    return ''.join(result)


class Svg:
    def __init__(self, width, mobile=None):
        self.width = width
        self.mobile = width < 800 if mobile is None else mobile
        self.m = 20 if self.mobile else 40
        self.content = width - 2 * self.m
        self.parts, self.defs, self.fonts, self.serial, self.css = [], [], set(), 0, []

    def col(self, index):
        width = (self.content - 11 * 24) / 12
        return self.m + index * (width + 24)

    def span(self, count):
        width = (self.content - 11 * 24) / 12
        return count * width + (count - 1) * 24

    def uid(self, prefix):
        self.serial += 1
        return f'{prefix}{self.serial}'

    def raw(self, markup):
        self.parts.append(markup)

    def _attrs(self, x, y, size, font, weight, anchor, tracking, cls):
        self.fonts.add((font, weight))
        attrs = [f'x="{n(x)}"', f'y="{n(y)}"', f'font-size="{n(size)}"']
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if anchor != 'start':
            attrs.append(f'text-anchor="{anchor}"')
        if tracking:
            attrs.append(f'letter-spacing="{n(tracking * size)}"')
        classes = ' '.join(c for c in ('m' if font == 'mono' else '', cls) if c)
        if classes:
            attrs.append(f'class="{classes}"')
        return attrs

    def text(self, x, y, value, size, color=INK, font='sans', weight=400, anchor='start', tracking=0.0, cls=''):
        attrs = self._attrs(x, y, size, font, weight, anchor, tracking, cls) + [f'fill="{color}"']
        self.raw('<text ' + ' '.join(attrs) + '>' + html.escape(str(value), quote=False) + '</text>')

    def line_runs(self, x, y, words, size, weight=400, tracking=0.0, font='sans', anchor='start'):
        spans = []
        for index, (word, color) in enumerate(words):
            piece = (' ' if index else '') + word
            if spans and spans[-1][0] == color:
                spans[-1][1] += piece
            else:
                spans.append([color, piece])
        if len(spans) == 1:
            self.text(x, y, spans[0][1], size, spans[0][0], font, weight, anchor, tracking)
            return
        attrs = self._attrs(x, y, size, font, weight, anchor, tracking, '')
        body = ''.join(f'<tspan fill="{color}">{html.escape(piece, quote=False)}</tspan>' for color, piece in spans)
        self.raw('<text ' + ' '.join(attrs) + '>' + body + '</text>')

    def paragraph(self, x, y, content, width, size, leading, color=INK, weight=400, tracking=0.0, font='sans', anchor='start'):
        runs = content if isinstance(content, list) else [(content, color)]
        lines = wrap_runs(runs, width, size, font, tracking * size)
        for index, words in enumerate(lines):
            self.line_runs(x, y + index * leading, words, size, weight, tracking, font, anchor)
        return len(lines)

    def mono(self, x, y, value, color=MUTED, size=None, anchor='start', tracking=.14):
        size = size or (12 if self.mobile else 12.5)
        label = str(value).upper()
        self.text(x, y, label, size, color, 'mono', 400, anchor, tracking)
        return measure(label, size, 'mono', tracking * size) - tracking * size

    def hline(self, x1, x2, y, color=LINE):
        self.raw(f'<path d="M{n(x1)} {n(y + .5)}H{n(x2)}" stroke="{color}"/>')

    def vline(self, x, y1, y2, color=LINE):
        self.raw(f'<path d="M{n(x + .5)} {n(y1)}V{n(y2)}" stroke="{color}"/>')

    def joints(self, points):
        for x, y in dict.fromkeys(points):
            self.raw(f'<rect x="{n(x - 2)}" y="{n(y - 2)}" width="5" height="5" fill="{JOINT}"/>')

    def square(self, x, y, size=6, color=ACCENT, cls=''):
        extra = f' class="{cls}"' if cls else ''
        self.raw(f'<rect x="{n(x)}" y="{n(y)}" width="{n(size)}" height="{n(size)}" fill="{color}"{extra}/>')

    def label(self, x, y, index, title):
        size = 12 if self.mobile else 12.5
        self.square(x, y - size * .62, 6)
        x += 16
        x += self.mono(x, y, f'({index:02d})') + size * .9
        self.mono(x, y, title, INK)

    def arrow(self, x, y, size=12, color=INK, width=1.6):
        self.raw(f'<path d="M{n(x)} {n(y + size)}L{n(x + size)} {n(y)}M{n(x + size * .3)} {n(y)}H{n(x + size)}V{n(y + size * .7)}" '
                 f'fill="none" stroke="{color}" stroke-width="{n(width)}" stroke-linecap="round" stroke-linejoin="round"/>')

    def tag(self, x, y, value, size, height):
        label = str(value).upper()
        spacing = .1 * size
        width = measure(label, size, 'mono', spacing) - spacing + 24
        self.raw(f'<rect x="{n(x + .5)}" y="{n(y + .5)}" width="{n(width - 1)}" height="{n(height - 1)}" rx="{n((height - 1) / 2)}" fill="none" stroke="{EDGE}"/>')
        self.text(x + 12, y + height / 2 + size * .36, label, size, INK75, 'mono', 400, 'start', .1)
        return width

    def tags(self, x, y, values, right):
        size, height = (11, 26) if self.mobile else (11, 26)
        cursor, top = x, y
        for value in values:
            label = str(value).upper()
            width = measure(label, size, 'mono', .1 * size) - .1 * size + 24
            if cursor > x and cursor + width > right:
                cursor, top = x, top + height + 8
            cursor += self.tag(cursor, top, value, size, height) + 8
        return top + height if values else y

    def button(self, x, y, label, icon, primary, height):
        size = 14 if self.mobile else 15
        fill, color = (INK, PAPER) if primary else (PAPER, INK)
        pad = 18 if label else 0
        icon_size = 16
        text_width = measure(label, size) if label else 0
        width = (pad * 2 + icon_size + (8 + text_width if label else 0) + (18 if primary and label else 0)) if label else height * 1.6
        stroke = '' if primary else f' stroke="{EDGE}"'
        self.raw(f'<rect x="{n(x + .5)}" y="{n(y + .5)}" width="{n(width - 1)}" height="{n(height - 1)}" rx="{n((height - 1) / 2)}" fill="{fill}"{stroke}/>')
        ix = x + (pad if label else (width - icon_size) / 2)
        iy = y + (height - icon_size) / 2
        self.raw(f'<g transform="translate({n(ix)} {n(iy)})">' + ICONS[icon].format(c=color, b=fill) + '</g>')
        if label:
            self.text(ix + icon_size + 8, y + height / 2 + size * .35, label, size, color, 'sans', 500)
            if primary:
                self.arrow(ix + icon_size + 8 + text_width + 8, y + height / 2 - 4.5, 9, color, 1.5)
        return width

    def dots(self, x, y, width, height, cell, field, cx=.5, cy=.5, scale=1.0, t=4.0, grid=True, glint=False):
        cols, rows = int(width // cell), int(height // cell)
        x += (width - cols * cell) / 2
        y += (height - rows * cell) / 2
        if hasattr(field, 'prepare'):
            field.prepare(cols, rows)
        unit = min(width, height) * scale
        ox, oy = width * cx, height * cy
        buckets = [[] for _ in DOT_SIZES]
        for row in range(rows):
            v = ((row + .5) * cell - oy) / unit
            for col in range(cols):
                level = to_level(field(((col + .5) * cell - ox) / unit, v, t, col, row), col, row)
                if level:
                    buckets[level - 1].append((col, row))
        if grid:
            self.grid(x, y, cols * cell, rows * cell, cell)
        self.cells(x, y, cell, buckets, glint)

    def sprite(self, x, y, width, height, cell, name):
        rows, groups = SPRITES[name]
        cols, count = int(width // cell), int(height // cell)
        x += (width - cols * cell) / 2
        y += (height - count * cell) / 2
        self.grid(x, y, cols * cell, count * cell, cell)
        left, top = (cols - len(rows[0])) // 2, (count + 4 - len(rows)) // 2
        buckets, animated = [[] for _ in DOT_SIZES], {}
        for row, line in enumerate(rows):
            for col, mark in enumerate(line):
                if mark.isdigit():
                    buckets[int(mark) - 1].append((left + col, top + row))
                elif mark in groups:
                    level, kind, period, delay = groups[mark]
                    if kind == 'shimmer':
                        delay += col * period / 2 / len(line)
                    animated.setdefault((level, kind, period, round((period - delay) % period, 3)), []).append((left + col, top + row))
        self.cells(x, y, cell, buckets)
        for (level, kind, period, delay), cells in animated.items():
            cls = self.uid('s')
            if f'@keyframes {kind}{{' not in ''.join(self.css):
                self.css.append(f'@keyframes {kind}{{{SPRITE_FRAMES[kind]}}}')
            self.css.append(f'.{cls}{{animation:{kind} {n(period)}s linear {n(-delay)}s infinite}}')
            self.raw(f'<g class="{cls}">')
            self.cells(x, y, cell, [cells if index == level - 1 else [] for index in range(len(DOT_SIZES))])
            self.raw('</g>')

    def grid(self, x, y, width, height, cell):
        pid = self.uid('g')
        size = max(1, round(cell * .18))
        offset = (cell - size) / 2
        self.defs.append(f'<pattern id="{pid}" width="{n(cell)}" height="{n(cell)}" patternUnits="userSpaceOnUse" x="{n(x)}" y="{n(y)}">'
                         f'<rect x="{n(offset)}" y="{n(offset)}" width="{size}" height="{size}" fill="{GRID}"/></pattern>')
        self.raw(f'<rect x="{n(x)}" y="{n(y)}" width="{n(width)}" height="{n(height)}" fill="url(#{pid})"/>')
        return pid

    def cells(self, x, y, cell, buckets, glint=False):
        for level, cells in enumerate(buckets):
            if not cells:
                continue
            size = max(1, round(cell * DOT_SIZES[level]))
            offset = (cell - size) / 2
            d, previous = [], None
            for col, row in cells:
                px, py = x + col * cell + offset, y + row * cell + offset
                if previous is None:
                    d.append(f'M{n(px)} {n(py)}')
                else:
                    d.append(f'm{n(px - previous[0])} {n(py - previous[1])}')
                d.append(f'h{size}v{size}h-{size}z')
                previous = (px, py)
            cls = ' class="glint"' if glint and level >= 4 else ''
            self.raw(f'<path d="{"".join(d)}" fill="{DOT_COLORS[level]}"{cls}/>')

    def render(self, height, title, description):
        css = ("text{font-family:HG,'Host Grotesk',ui-sans-serif,system-ui,sans-serif}.m{font-family:DM,'DM Mono',ui-monospace,Menlo,monospace}"
               '@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}.pulse{animation:pulse 2s ease-in-out infinite}'
               '@keyframes glint{0%,100%{opacity:1}50%{opacity:.55}}.glint{animation:glint 6s ease-in-out infinite}'
               + ''.join(self.css) + '@media(prefers-reduced-motion:reduce){*{animation:none!important}}')
        defs = '<defs>' + ''.join(self.defs) + '</defs>' if self.defs else ''
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(self.width)}" height="{n(height)}" viewBox="0 0 {n(self.width)} {n(height)}" '
                f'role="img" aria-labelledby="t d"><title id="t">{html.escape(title)}</title><desc id="d">{html.escape(description)}</desc>'
                f'<style>{font_css(self.fonts)}{css}</style>{defs}<rect width="{n(self.width)}" height="{n(height)}" fill="{PAPER}"/>'
                + ''.join(self.parts) + '</svg>\n')


def headline(c, x, y, lines, size, width, color=INK, tracking=-.045):
    leading = size * .95
    count = 0
    for line in lines:
        count += c.paragraph(x, y + count * leading, line, width, size, leading, color, 500, tracking)
    return y + (count - 1) * leading


def fit(lines, size, width, tracking):
    widest = max(measure(line, 1, spacing=tracking) for line in lines)
    return min(size, width / widest)


def contact_order(content):
    contacts = list(content.get('contacts') or [])
    return sorted(contacts, key=lambda contact: not contact.get('primary'))


def code_typing(c, x, y, cell, columns, grid, bottom, fade, solid=0):
    lines = [line[:columns] for line in CODE.splitlines()]
    count, pitch = len(lines), 2 * cell
    buckets = [[] for _ in DOT_SIZES]
    timeline, clock = [], .2
    for index, line in enumerate(lines):
        for match in CODE_TOKENS.finditer(line):
            token = match.group()
            level = 6 if token in CODE_KEYWORDS else 5 if token[0] in "'0123456789" else 4 if token[0].isalpha() else 3
            rows = [2 * index] + ([2 * (index - count)] if y + 2 * (index - count) * cell + cell > 0 else [])
            buckets[level - 1].extend((col, row) for row in rows for col in range(match.start(), match.end()))
        indent = len(line) - len(line.lstrip())
        length = len(line) - indent
        timeline.append((indent, length, clock, clock + length * TYPE_STEP))
        clock += length * TYPE_STEP + (TYPE_PAUSE if length else TYPE_SCROLL + .02)
    total = clock

    def pct(seconds):
        return f'{seconds / total * 100:.3f}'.rstrip('0').rstrip('.') + '%'

    loop = f'{total:.2f}s linear infinite'
    step = 'animation-timing-function:steps(1,end)'
    scroll, moves = ['0%{transform:translateY(0)}'], [f'0%{{transform:translateX({n(timeline[0][0] * cell)}px);{step}}}']
    rules = []
    clip = c.uid('c')
    c.defs.append(f'<clipPath id="{clip}"><rect width="{c.width}" height="{n(bottom)}"/></clipPath>')
    c.raw(f'<g clip-path="url(#{clip})"><g class="tys">')
    c.cells(x, y, cell, buckets)
    for index, (indent, length, start, end) in enumerate(timeline):
        scroll.append(f'{pct(end)}{{transform:translateY({-index * pitch}px);animation-timing-function:cubic-bezier(.2,.7,.2,1)}}')
        scroll.append(f'{pct(end + TYPE_SCROLL)}{{transform:translateY({-(index + 1) * pitch}px)}}')
        if length:
            width = length * cell
            box = f'x="{n(x + indent * cell)}" y="{n(y + index * pitch - 2)}" width="{n(width)}" height="{n(cell + 4)}"'
            c.raw(f'<g class="ty{index}"><rect {box} fill="{PAPER}"/><rect {box} fill="url(#{grid})"/></g>')
            rules.append(f'.ty{index}{{animation:ty{index} {loop}}}@keyframes ty{index}{{0%,{pct(start)}{{transform:translateX(0);'
                         f'animation-timing-function:steps({length},end)}}{pct(end)},100%{{transform:translateX({n(width)}px)}}}}')
            moves.append(f'{pct(start)}{{transform:translateX({n(indent * cell)}px);animation-timing-function:steps({length},end)}}')
            moves.append(f'{pct(end)}{{transform:translateX({n((indent + length) * cell)}px);{step}}}')
        following = timeline[(index + 1) % count][0]
        moves.append(f'{pct(end + .06)}{{transform:translateX({n(following * cell)}px);{step}}}')
    c.raw('</g></g>')
    scroll.append(f'100%{{transform:translateY({-count * pitch}px)}}')
    moves.append(f'100%{{transform:translateX({n(timeline[0][0] * cell)}px)}}')
    rules.append(f'.tys{{animation:tys {loop}}}@keyframes tys{{' + ''.join(scroll) + '}')
    rules.append(f'.tyc{{transform:translateX({n(timeline[0][0] * cell)}px);animation:tyc {loop}}}@keyframes tyc{{' + ''.join(moves) + '}')
    c.raw(f'<rect x="{n(x - cell)}" y="{n(y)}" width="{n((columns + 2) * cell)}" height="{n(cell)}" fill="{ACCENT}" fill-opacity=".07"/>')
    low = c.uid('f')
    c.defs.append(f'<linearGradient id="{low}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAPER}" stop-opacity="0"/>'
                  f'<stop offset="{n((5 * pitch + cell) / (bottom - y + 5 * pitch))}" stop-color="{PAPER}" stop-opacity=".7"/>'
                  f'<stop offset="1" stop-color="{PAPER}"/></linearGradient>')
    c.raw(f'<rect y="{n(y - 5 * pitch)}" width="{c.width}" height="{n(bottom - y + 5 * pitch)}" fill="url(#{low})"/>')
    size = max(1, round(cell * DOT_SIZES[-1]))
    c.raw(f'<rect class="tyc" x="{n(x + (cell - size) / 2)}" y="{n(y + (cell - size) / 2)}" width="{size}" height="{size}" fill="{INK}"/>')
    gid = c.uid('f')
    c.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="{n(solid / fade)}" stop-color="{PAPER}"/>'
                  f'<stop offset="1" stop-color="{PAPER}" stop-opacity="0"/></linearGradient>')
    c.raw(f'<rect width="{c.width}" height="{n(fade)}" fill="url(#{gid})"/>')
    c.css.extend(rules)


def hero(content, github, as_of, width):
    c = Svg(width)
    name = str(content.get('name') or '').split()
    lines = [name[0], ' '.join(name[1:]) + '.'] if len(name) > 1 else [' '.join(name) + '.']
    meta = [content.get('role') or '']
    created = (github or {}).get('created_at')
    if created:
        meta.append('On GitHub since ' + created[:4])
    status = content.get('status')
    headline_text = content.get('headline') or ''
    if c.mobile:
        art = 430
        size = fit(lines, 96, c.content, -.06)
        second = art - 14
        paragraph_x, paragraph_top, paragraph_width, leading = c.m, second + 50, c.content, 27
        count = len(wrap_runs([(headline_text, INK75)], paragraph_width, 17))
        height = math.ceil(paragraph_top + (count - 1) * leading + 26)
        code_typing(c, 160, 235, 5, 60, c.grid(0, 0, width, art, 5), art, 120, 64)
    else:
        height = art = 600
        size = fit(lines, 140, c.span(8), -.06)
        second = height - 34
        paragraph_x, paragraph_width, leading = c.col(8), c.span(4), 27.5
        count = len(wrap_runs([(headline_text, INK75)], paragraph_width, 17))
        paragraph_top = second - (count - 1) * leading
        code_typing(c, 464, 456, 8, 65, c.grid(0, 0, width, art, 8), art, 96)
    first = second - size * .88
    for index, line in enumerate(meta):
        c.mono(c.m, 34 + index * 18, line)
    if status:
        size_meta = 12 if c.mobile else 12.5
        if c.mobile:
            y = 34 + len(meta) * 18 + 8
            c.square(c.m, y - size_meta * .62, 6, ACCENT, 'pulse')
            c.mono(c.m + 16, y, status, INK)
        else:
            w = c.mono(width - c.m, 34, status, INK, anchor='end')
            c.square(width - c.m - w - 16, 34 - size_meta * .62, 6, ACCENT, 'pulse')
    for line, baseline in zip(lines, [first, second][-len(lines):]):
        c.text(c.m - size * .03, baseline, line, size, INK, 'sans', 500, tracking=-.06)
    c.paragraph(paragraph_x, paragraph_top, headline_text, paragraph_width, 17, leading, INK75)
    return c.render(height, ' '.join(name), ' '.join(name) + '. ' + headline_text)


def hero_buttons(content):
    probe = Svg(DESKTOP)
    specs = []
    for contact in contact_order(content):
        primary = bool(contact.get('primary'))
        label = str(contact.get('cta') if primary and contact.get('cta') else contact.get('label') or '')
        icon = contact_icon(contact)
        specs.append((contact, label, icon, primary, probe.button(0, 0, label, icon, primary, 44) + 12))
    return specs


def hero_button(spec, width, mobile):
    contact, label, icon, primary, _ = spec
    c = Svg(width, mobile)
    height = 72 if c.mobile else 84
    button_height = 40 if c.mobile else 44
    if c.mobile:
        gap = 12 * width / DESKTOP
        button_width = width - gap
        fill, color = (INK, PAPER) if primary else (PAPER, INK)
        stroke = '' if primary else f' stroke="{EDGE}"'
        c.raw(f'<rect x=".5" y="8.5" width="{n(button_width - 1)}" height="{button_height - 1}" rx="{(button_height - 1) / 2}" fill="{fill}"{stroke}/>')
        c.raw(f'<g transform="translate({n((button_width - 16) / 2)} {8 + (button_height - 16) / 2})">' + ICONS[icon].format(c=color, b=fill) + '</g>')
    else:
        c.button(0, 8, label, icon, primary, button_height)
    return c.render(height, label, '. '.join(str(part) for part in (contact.get('label'), contact.get('detail')) if part)), height


def blank(width, height):
    return Svg(width, True).render(height, 'Spacing', 'Decorative spacing')


def stat_values(keys, github, as_of):
    github = github or {}
    calendar = github.get('calendar') or []
    created = github.get('created_at') or ''
    result = []
    for key in keys:
        if key == 'years':
            since = f'On GitHub since {MONTH_NAMES[int(created[5:7]) - 1]} {created[:4]}.' if created else 'Appears after the first sync.'
            result.append(('Years on GitHub', years_between(created, as_of) if created else None, since))
        elif key == 'contributions_all':
            result.append(('Contributions', github.get('contributions_all'), 'All time, as recorded by GitHub.'))
        elif key == 'contributions_window':
            result.append(('Contributions', sum(count for _, count in calendar) if calendar else None, 'In the last 365 days.'))
        elif key == 'active_days':
            result.append(('Active days', sum(count > 0 for _, count in calendar) if calendar else None, 'Days with a contribution in the last year.'))
        elif key == 'streak_longest':
            result.append(('Longest streak', github.get('streak_longest'), 'Days in a row with at least one contribution.'))
        elif key == 'repo_count':
            result.append(('Public repositories', github.get('repo_count'), 'Owned by me, forks excluded.'))
        elif key == 'followers':
            result.append(('Followers', github.get('followers'), 'People following my work on GitHub.'))
    return result


def statement(c, top, index, title, runs):
    size, leading = (28, 31) if c.mobile else (42, 46)
    if c.mobile:
        c.label(c.m, top, index, title)
        first = top + 54
        count = c.paragraph(c.m, first, runs, c.content, size, leading, INK, 500, -.035)
    else:
        first = top + 32
        c.label(c.m, first - 26, index, title)
        count = c.paragraph(c.col(3), first, runs, c.span(9), size, leading, INK, 500, -.035)
    return first + (count - 1) * leading


def about(content, github, as_of, width, number=1):
    c = Svg(width)
    runs = [(content.get('about') or '', INK), (content.get('about_more') or '', INK35)]
    bottom = statement(c, 64 if c.mobile else 104, number, 'About', runs)
    stats = stat_values(content.get('stats') or [], github, as_of)
    top = bottom + (56 if c.mobile else 88)
    per = (3 if len(stats) == 3 else 2) if c.mobile else max(1, min(4, len(stats)))
    compact = c.mobile and per == 3
    column = c.content / per
    bodies = []
    for index, (label, value, note) in enumerate(stats):
        row, col = divmod(index, per)
        pad = (14 if compact else 20) if c.mobile else 32
        x = c.m + col * column + (pad if col else 0)
        inner = column - (pad if col == 0 else 2 * pad)
        bodies.append((row, col, x, inner, label, value, note))
    rows = math.ceil(len(stats) / per) if stats else 0
    heights = []
    for row in range(rows):
        tallest = 0
        for r, col, x, inner, label, value, note in bodies:
            if r != row:
                continue
            lines = wrap_runs([(note, MUTED)], inner, 13 if compact else 14 if c.mobile else 15)
            tallest = max(tallest, (104 if compact else 110 if c.mobile else 142) + (len(lines) - 1) * (19 if compact else 21 if c.mobile else 24))
        heights.append(tallest + (28 if c.mobile else 36))
    y = top
    rule = math.ceil(top + sum(heights) + (24 if c.mobile else 32)) - 5
    if stats:
        c.hline(c.m, width - c.m, top)
    c.hline(c.m, width - c.m, rule)
    points = []
    for row in range(rows):
        end = rule if row == rows - 1 else y + heights[row]
        for r, col, x, inner, label, value, note in bodies:
            if r != row:
                continue
            if compact:
                for index, part in enumerate(wrap_runs([(label.upper(), MUTED)], inner, 10.5, 'mono', 1.47)[:2]):
                    c.mono(x, y + 28 + index * 15, ' '.join(word for word, _ in part), MUTED, 10.5)
            else:
                c.mono(x, y + (30 if c.mobile else 38), label)
            c.text(x - 2, y + (80 if compact else 82 if c.mobile else 108), 'N/A' if value is None else f'{value:,}', 36 if compact else 46 if c.mobile else 66, INK, 'sans', 500, tracking=-.05)
            c.paragraph(x, y + (104 if compact else 110 if c.mobile else 142), note, inner, 13 if compact else 14 if c.mobile else 15, 19 if compact else 21 if c.mobile else 24, MUTED)
            if col:
                c.vline(c.m + col * column, y, end)
                points += [(c.m + col * column, y), (c.m + col * column, end)]
        if c.mobile and row < rows - 1:
            c.hline(c.m, width - c.m, y + heights[row])
        y += heights[row]
    c.joints(points)
    height = rule + 5
    alt = 'About. ' + ' '.join(text for text, _ in runs) + ' ' + '; '.join(f'{label}: {value}' for label, value, _ in stats)
    return c.render(height, 'About', alt), alt


def divider(c, number):
    if number > 2:
        c.hline(c.m, c.width - c.m, 0)


def section_head(c, index, title, lines, intro, top=None):
    divider(c, index)
    top = (72 if c.mobile else 104) if top is None else top
    c.label(c.m, top, index, title)
    if c.mobile:
        size = 38
        last = headline(c, c.m, top + 30 + size * .78, lines, size, c.content)
        if intro:
            count = c.paragraph(c.m, last + 44, intro, c.content, 16, 25, INK70)
            last = last + 44 + (count - 1) * 25
        return last
    size = 60
    last = headline(c, c.m, top + 34 + size * .78, lines, size, c.span(8) + 40)
    if intro:
        lines_intro = wrap_runs([(intro, INK70)], c.span(4), 17)
        c.paragraph(c.col(8), last - (len(lines_intro) - 1) * 27.5, intro, c.span(4), 17, 27.5, INK70)
    return last


def stack(content, width, number=2):
    c = Svg(width)
    rows = content.get('stack') or []
    bottom = section_head(c, number, 'Stack', content.get('stack_title') or ['Stack'], content.get('stack_intro'))
    top = bottom + (44 if c.mobile else 64)
    per = 2 if c.mobile else min(5, max(1, len(rows)))
    column = c.content / per
    art = 120 if c.mobile else 150
    pad = 16 if c.mobile else 20
    grouped = [rows[i:i + per] for i in range(0, len(rows), per)]
    y = top
    points = []
    for group_index, group in enumerate(grouped):
        heights = []
        for item in group:
            title_lines = wrap_runs([(item.get('area') or '', INK)], column - 2 * pad, 22)
            tool_probe = Svg(width)
            tools_bottom = tool_probe.tags(0, 0, item.get('tools') or [], column - 2 * pad)
            heights.append(art + 46 + (len(title_lines) - 1) * 26 + 22 + tools_bottom + pad + 4)
        row_height = max(heights)
        for index, item in enumerate(group):
            number = group_index * per + index
            x = c.m + index * column
            motif = item.get('motif')
            c.sprite(x + 1, y + 1, column - 2, art - 2, 5 if c.mobile else 6, motif if motif in SPRITES else list(SPRITES)[number % len(SPRITES)])
            c.mono(x + pad, y + 26, f'{number + 1:02d}', MUTED, 11)
            c.hline(x, x + column, y + art)
            count = c.paragraph(x + pad, y + art + 46, item.get('area') or '', column - 2 * pad, 22, 26, INK, 500, -.03)
            c.tags(x + pad, y + art + 46 + (count - 1) * 26 + 22, item.get('tools') or [], x + column - pad)
            if index:
                c.vline(x, y, y + row_height)
        c.raw(f'<rect x="{n(c.m + .5)}" y="{n(y + .5)}" width="{n(len(group) * column - 1)}" height="{n(row_height - 1)}" fill="none" stroke="{LINE}"/>')
        edges = [c.m + index * column for index in range(len(group))] + [c.m + len(group) * column - 1]
        points += [(x, line) for x in edges for line in (y, y + art, y + row_height - 1)]
        y += row_height - 1
    c.joints(points)
    height = math.ceil(y + (64 if c.mobile else 96))
    alt = 'Stack. ' + '; '.join(str(item.get('area')) + ': ' + ', '.join(item.get('tools') or []) for item in rows)
    return c.render(height, 'Stack', alt), alt


def now(content, width, number=4):
    c = Svg(width)
    bottom = section_head(c, number, 'Now', content.get('now_title') or ['Now'], content.get('now_intro'))
    items = content.get('now_items') or []
    top = bottom + (56 if c.mobile else 80)
    if c.mobile:
        y = top
        for index, item in enumerate(items):
            c.hline(c.m, width - c.m, y, LINE)
            c.hline(c.m, c.m + (c.content if index < len(items) - 1 else c.content * .45), y, ACCENT)
            c.square(c.m, y - 4, 9)
            c.mono(c.m, y + 36, f'{index + 1:02d}', MUTED, 11)
            c.mono(width - c.m, y + 36, item.get('tag') or '', ACCENT_TEXT, 11, 'end')
            c.text(c.m, y + 76, item.get('title') or '', 26, INK, 'sans', 500, tracking=-.035)
            count = c.paragraph(c.m, y + 108, item.get('text') or '', c.content, 15, 24, MUTED)
            y += 108 + (count - 1) * 24 + 48
        height = math.ceil(y + 8)
    else:
        column = c.content / max(1, len(items))
        c.hline(c.m, width - c.m, top)
        c.hline(c.m, c.m + column * (len(items) - 1) + column * .45, top, ACCENT)
        last = top
        for index, item in enumerate(items):
            x = c.m + index * column
            c.square(x, top - 4, 9)
            c.mono(x, top + 48, f'{index + 1:02d}', MUTED, 11)
            c.mono(x + column - 40, top + 48, item.get('tag') or '', ACCENT_TEXT, 11, 'end')
            c.text(x, top + 98, item.get('title') or '', 30, INK, 'sans', 500, tracking=-.035)
            count = c.paragraph(x, top + 134, item.get('text') or '', column - 56, 15, 24.5, MUTED)
            last = max(last, top + 134 + (count - 1) * 24.5)
        height = math.ceil(last + 104)
    alt = 'Now. ' + ' '.join(content.get('now_title') or []) + ' ' + ' '.join(f"{item.get('title')}: {item.get('text')}" for item in items)
    return c.render(height, 'Now', alt), alt


def activity(content, source, width, number=5):
    c = Svg(width)
    github = source.get('data') or {}
    calendar = github.get('calendar') or []
    divider(c, number)
    if calendar:
        total = sum(count for _, count in calendar)
        active = sum(count > 0 for _, count in calendar)
        peak_date, peak = max(calendar, key=lambda pair: (pair[1], pair[0]))
        day = dt.date.fromisoformat(peak_date)
        busiest = f', busiest on {MONTHS[day.month - 1]} {day.day} with {peak}.' if peak else '.'
        runs = [(f'{total:,} contributions in the last year.', INK), (f'{active} active days{busiest}', INK35)]
    else:
        configured = bool(content.get('github_username'))
        runs = [('GitHub activity is not connected yet.' if not configured else 'GitHub activity is unavailable right now.', INK),
                ('It appears after the next successful sync.', INK35)]
    bottom = statement(c, 72 if c.mobile else 104, number, 'Activity', runs)
    y = bottom + (48 if c.mobile else 72)
    if calendar:
        cell = 8 if c.mobile else 17
        pad = (len(calendar) and (dt.date.fromisoformat(calendar[0][0]).weekday() + 1) % 7)
        weeks = math.ceil((len(calendar) + pad) / 7)
        x0 = c.m
        grid_top = y + 18
        peak_value = math.log1p(max(count for _, count in calendar) or 1)
        buckets = [[] for _ in DOT_SIZES]
        last_label = None
        for index, (date, count) in enumerate(calendar):
            col, row = divmod(index + pad, 7)
            if date[8:10] == '01' or index == 0:
                label_x = x0 + col * cell
                if last_label is None or label_x - last_label >= (26 if c.mobile else 40):
                    c.mono(label_x, y, MONTHS[int(date[5:7]) - 1], MUTED, 10 if c.mobile else 11, tracking=.1)
                    last_label = label_x
            if count:
                level = to_level(math.log1p(count) / peak_value, col, row)
                if level:
                    buckets[level - 1].append((col, row))
        c.grid(x0, grid_top, weeks * cell, 7 * cell, cell)
        c.cells(x0, grid_top, cell, buckets)
        legend_y = grid_top + 7 * cell + (30 if c.mobile else 40)
        cursor = x0 + c.mono(x0, legend_y, 'Less', MUTED, 11) + 10
        for level in range(1, 6):
            size = max(2, round(12 * DOT_SIZES[level]))
            c.square(cursor + (12 - size) / 2, legend_y - 4 - size / 2, size, DOT_COLORS[level])
            cursor += 14
        c.mono(cursor + 8, legend_y, 'More', MUTED, 11)
        synced = f"Last 365 days · synced {source.get('as_of') or 'unknown'}"
        if source.get('status') == 'stale':
            synced = f"Cached · last sync {source.get('as_of') or 'unknown'}"
        if c.mobile:
            c.mono(x0, legend_y + 24, synced, MUTED, 11)
            y = legend_y + 24
        else:
            c.mono(width - c.m, legend_y, synced, MUTED, 11, 'end')
            y = legend_y
    height = math.ceil(y + (64 if c.mobile else 104))
    alt = 'Activity. ' + ' '.join(text for text, _ in runs)
    return c.render(height, 'Activity', alt), alt


def contact_head(content, width, number=6):
    c = Svg(width)
    bottom = section_head(c, number, 'Contact', content.get('contact_title') or ['Contact'], content.get('contact_intro'))
    height = math.ceil(bottom + (40 if c.mobile else 64))
    return c.render(height, 'Contact', 'Contact'), height


def contact_row(contact, last, width):
    c = Svg(width)
    live = bool(contact.get('url'))
    c.hline(c.m, width - c.m, 0)
    if c.mobile:
        height = 88
        c.mono(c.m, 32, contact.get('label') or '', MUTED, 11.5)
        c.text(c.m, 66, contact.get('detail') or contact.get('label') or '', 22, INK if live else MUTED, 'sans', 500, tracking=-.03)
        if live:
            c.arrow(width - c.m - 14, 42, 14, INK, 1.6)
    else:
        height = 104
        c.mono(c.m, height / 2 + 4.5, contact.get('label') or '')
        c.text(c.col(3), height / 2 + 12, contact.get('detail') or contact.get('label') or '', 34, INK if live else MUTED, 'sans', 500, tracking=-.035)
        if live:
            c.arrow(width - c.m - 18, height / 2 - 9, 18, INK, 1.7)
    if last:
        c.hline(c.m, width - c.m, height - 1)
    alt = '. '.join(str(part) for part in (contact.get('label'), contact.get('detail')) if part)
    return c.render(height, str(contact.get('label') or 'Contact'), alt), alt


def footer(content, as_of, width):
    c = Svg(width)
    top = 48 if c.mobile else 72
    area = 120 if c.mobile else 250
    c.dots(c.m, top, c.content, area, 4 if c.mobile else 8, wordmark_field(content.get('wordmark') or 'valdeir'), .5, .5, 1.0, 2.0, glint=True)
    rule = top + area + (20 if c.mobile else 28)
    c.hline(c.m, width - c.m, rule)
    owner = f"© {str(as_of)[:4]} {content.get('name') or ''}" if as_of else f"© {content.get('name') or ''}"
    items = [owner, 'Generated daily by GitHub Actions', f'Updated {as_of}' if as_of else 'Not synced yet']
    if c.mobile:
        for index, item in enumerate(items):
            c.mono(c.m, rule + 34 + index * 20, item, MUTED, 11)
        height = rule + 34 + 2 * 20 + 28
    else:
        c.mono(c.m, rule + 40, items[0], MUTED, 11.5)
        c.mono(width / 2, rule + 40, items[1], MUTED, 11.5, 'middle')
        c.mono(width - c.m, rule + 40, items[2], MUTED, 11.5, 'end')
        height = rule + 40 + 36
    return c.render(height, 'Footer', ' · '.join(items)), height


def picture(cell):
    filename, alt, url, share = cell
    tag = (f'<picture><source media="(max-width: 600px)" srcset="./assets/{filename}-mobile.svg">'
           f'<img src="./assets/{filename}.svg" width="{share or "100%"}" align="top" alt="{html.escape(alt, quote=True)}"></picture>')
    return '<a href="' + html.escape(url, quote=True) + '">' + tag + '</a>' if url else tag


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


def percent(span):
    return f'{math.floor(span / DESKTOP * 1e6) / 1e4:.4f}'.rstrip('0').rstrip('.') + '%'


def years_between(created_at, as_of):
    try:
        start, end = dt.date.fromisoformat(str(created_at)[:10]), dt.date.fromisoformat(str(as_of)[:10])
    except ValueError:
        return None
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def writing_head(number, width):
    c = Svg(width)
    bottom = section_head(c, number, 'Writing', ['Latest articles', 'on DEV.'], None)
    height = math.ceil(bottom + (40 if c.mobile else 64))
    return c.render(height, 'Writing', 'Latest articles on DEV'), height


def link_row(width, label, title, meta, live, last):
    c = Svg(width)
    c.hline(c.m, width - c.m, 0)
    if c.mobile:
        c.mono(c.m, 32, label, MUTED, 11.5)
        count = c.paragraph(c.m, 62, title, c.content - 40, 19, 24, INK if live else MUTED, 500, -.025)
        y = 62 + (count - 1) * 24
        for index, line in enumerate(wrap_runs([(str(meta).upper(), MUTED)], c.content - 40, 11, 'mono', 1.54) if meta else []):
            y += 17 if index else 26
            c.mono(c.m, y, ' '.join(word for word, _ in line), MUTED, 11)
        if live:
            c.arrow(width - c.m - 14, 42, 14, INK, 1.6)
        height = math.ceil(y + 28)
    else:
        count = c.paragraph(c.col(3), 52, title, c.span(8), 26, 31, INK if live else MUTED, 500, -.03)
        y = 52 + (count - 1) * 31
        for index, line in enumerate(wrap_runs([(str(meta).upper(), MUTED)], c.span(8), 11.5, 'mono', 1.61) if meta else []):
            y += 18 if index else 32
            c.mono(c.col(3), y, ' '.join(word for word, _ in line), MUTED, 11.5)
        c.mono(c.m, 50, label)
        if live:
            c.arrow(width - c.m - 18, 34, 18, INK, 1.7)
        height = math.ceil(y + 34)
    if last:
        c.hline(c.m, width - c.m, height - 1)
    return c.render(height, str(title), '. '.join(part for part in (label, str(title), meta) if part))


def article_row(article, last, width):
    meta = f"{article['reactions']:,} reactions · {article['comments']:,} comments"
    return link_row(width, article['published_at'][:10], article['title'], meta, True, last)


def dev_summary(dev_source):
    stats = (dev_source.get('data') or {}).get('stats', {})
    summary = ' · '.join(f'{stats[k]:,} {k}' for k in ['articles', 'reactions', 'comments', 'views', 'followers'] if stats.get(k) is not None)
    synced = 'Last successful sync ' + str(dev_source.get('as_of'))
    if dev_source.get('status') == 'stale' or stats.get('authenticated_status') == 'unavailable':
        synced = 'Some DEV metrics could not be refreshed · ' + synced
    return summary, synced


def render_profile(config, state, root):
    root = Path(root)
    assets = root / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    sources = matching_state(config, state)
    source = sources['github']
    github = source.get('data')
    dev_source = sources['dev']
    as_of = source.get('as_of') or dev_source.get('as_of')
    name = str(config.get('name') or '')
    rows = []

    def emit(filename, maker, alt, url=None, share=None):
        for width, suffix in [(DESKTOP, ''), (MOBILE, '-mobile')]:
            value = maker(width)
            (assets / (filename + suffix + '.svg')).write_text(value[0] if isinstance(value, tuple) else value)
        return filename, alt, valid_url(url), share

    contacts = config.get('contacts') or []
    rows.append([emit('hero', lambda w: hero(config, github, as_of, w), name + '. ' + str(config.get('headline') or ''))])
    if contacts:
        specs = hero_buttons(config)
        margin = 40
        rest = DESKTOP - margin - sum(spec[4] for spec in specs)
        cells = [emit('hero-start', lambda w: blank(w * margin / DESKTOP, 72 if w < 800 else 84), '', share=percent(margin))]
        for i, spec in enumerate(specs, 1):
            span = spec[4]
            cells.append(emit(f'hero-link-{i}', lambda w, spec=spec, span=span: hero_button(spec, w * span / DESKTOP, w < 800),
                              '. '.join(str(part) for part in (spec[0].get('label'), spec[0].get('detail')) if part),
                              spec[0].get('url'), percent(span)))
        cells.append(emit('hero-end', lambda w: blank(w * rest / DESKTOP, 72 if w < 800 else 84), '', share=percent(max(rest, 1))))
        rows.append(cells)
    numbers = iter(range(1, 20))
    index = next(numbers)
    rows.append([emit('about', lambda w, k=index: about(config, github, as_of, w, k), about(config, github, as_of, DESKTOP, index)[1])])
    if config.get('stack'):
        index = next(numbers)
        rows.append([emit('stack', lambda w, k=index: stack(config, w, k), stack(config, DESKTOP, index)[1])])
    if config.get('now_items'):
        index = next(numbers)
        rows.append([emit('now', lambda w, k=index: now(config, w, k), now(config, DESKTOP, index)[1])])
    dev = dev_source.get('data')
    if dev and config.get('dev', {}).get('show_writing', True):
        index = next(numbers)
        rows.append([emit('writing', lambda w, k=index: writing_head(k, w), 'Writing on DEV')])
        articles = dev.get('articles', [])
        summary, synced = dev_summary(dev_source)
        for i, article in enumerate(articles, 1):
            rows.append([emit(f'writing-{i}', lambda w, a=article: article_row(a, False, w),
                              f"{article['title']}. Published {article['published_at'][:10]}.", article['url'])])
        rows.append([emit('dev-stats', lambda w: link_row(w, 'DEV', 'All articles' if articles else 'No published articles.', summary + ' · ' + synced if summary else synced, True, True),
                          'DEV. ' + summary + '. ' + synced, 'https://dev.to/' + config['dev']['username'])])
    index = next(numbers)
    rows.append([emit('activity', lambda w, k=index: activity(config, source, w, k), activity(config, source, DESKTOP, index)[1])])
    if contacts:
        index = next(numbers)
        rows.append([emit('contact', lambda w, k=index: contact_head(config, w, k), 'Contact')])
        for i, contact in enumerate(contacts, 1):
            rows.append([emit(f'contact-{i}', lambda w, p=contact, last=i == len(contacts): contact_row(p, last, w),
                              contact_row(contact, i == len(contacts), DESKTOP)[1], contact.get('url'))])
    rows.append([emit('footer', lambda w: footer(config, as_of, w), name + (f'. Updated {as_of}.' if as_of else '.'))])
    lines = ['<!-- Generated by tools/profile/update.py. Edit profile.json, then regenerate. -->', '<p align="center">']
    lines.extend(''.join(picture(cell) for cell in row) for row in rows)
    lines.extend(['</p>', ''])
    readme = '\n'.join(lines)
    (root / 'README.md').write_text(readme)
    preview_style = ('*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#e6edf3;font-family:system-ui}'
                     'main{max-width:902px;margin:32px auto;padding:0 32px}p{margin:0;line-height:1.5}img{max-width:100%;vertical-align:top}'
                     'header{font:12px ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:#8b949e;margin:0 0 18px}'
                     '@media(max-width:600px){main{margin:16px auto;padding:0 12px}}')
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

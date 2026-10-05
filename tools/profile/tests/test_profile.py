import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1] / 'update.py'
spec = importlib.util.spec_from_file_location('profile_update', MODULE)
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def function(self, name):
        self.assertTrue(hasattr(profile, name), 'Missing behavior: ' + name)
        return getattr(profile, name)

    def test_calendar_is_exactly_365_days_even_midweek(self):
        days = {'2026-10-06': 8, '2025-10-06': 99, '2026-10-08': 99}
        result = self.function('calendar_window')(days, dt.date(2026, 10, 7))
        self.assertEqual(len(result), 365)
        self.assertEqual(result[0], ['2025-10-08', 0])
        self.assertEqual(result[-2:], [['2026-10-06', 8], ['2026-10-07', 0]])
        self.assertEqual(sum(n for _, n in result), 8)

    def test_streak_does_not_jump_across_missing_dates(self):
        result = self.function('streaks')({'2026-10-01': 3, '2026-10-03': 2, '2026-10-04': 1}, dt.date(2026, 10, 4))
        self.assertEqual(result, (2, 2))

    def test_failed_source_preserves_last_success_and_marks_stale(self):
        previous = {'username': 'owner', 'status': 'ok', 'as_of': '2026-10-01', 'data': {'stars': 7}}
        def fail():
            raise RuntimeError('API unavailable')
        result = self.function('refresh_source')(previous, 'owner', fail, '2026-10-04')
        self.assertEqual(result['data'], {'stars': 7})
        self.assertEqual(result['as_of'], '2026-10-01')
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['checked_at'], '2026-10-04')

    def test_changing_identity_cannot_display_previous_owners_metrics(self):
        previous = {'username': 'first', 'as_of': '2026-10-01', 'data': {'stars': 7}}
        def fail():
            raise RuntimeError('API unavailable')
        result = self.function('refresh_source')(previous, 'second', fail, '2026-10-04')
        self.assertIsNone(result['data'])
        self.assertEqual(result['status'], 'unavailable')

    def test_successful_empty_articles_clear_previous_posts(self):
        previous = {'username': 'owner', 'as_of': '2026-10-01', 'data': {'articles': [{'title': 'Old post'}]}}
        result = self.function('refresh_source')(previous, 'owner', lambda: {'articles': []}, '2026-10-04')
        self.assertEqual(result['data']['articles'], [])
        self.assertEqual(result['as_of'], '2026-10-04')
        self.assertEqual(result['status'], 'ok')

    def test_repository_pagination_includes_second_page_in_totals(self):
        def repo(name, stars):
            return {'nameWithOwner': 'owner/' + name, 'stargazerCount': stars, 'forkCount': 1,
                    'languages': {'edges': [{'size': 10, 'node': {'name': 'Python'}}],
                                  'pageInfo': {'hasNextPage': False, 'endCursor': None}}}
        def request(url, headers=None, body=None):
            query = body['query']; variables = body['variables']
            if 'ProfileRepositories' in query:
                if variables['after'] is None:
                    return {'data': {'user': {'repositories': {'nodes': [repo('one', 2)],
                                'pageInfo': {'hasNextPage': True, 'endCursor': 'NEXT'}}}}}
                self.assertEqual(variables['after'], 'NEXT')
                return {'data': {'user': {'repositories': {'nodes': [repo('two', 5)],
                            'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}
            if 'ProfileIdentity' in query:
                return {'data': {'user': {'login': 'owner', 'createdAt': '2026-01-01T00:00:00Z',
                    'followers': {'totalCount': 3}, 'pullRequests': {'totalCount': 4},
                    'merged': {'totalCount': 2}, 'contributionsCollection': {'contributionYears': [2026]}}}}
            if 'ProfileYear' in query:
                return {'data': {'user': {'contributionsCollection': {'totalCommitContributions': 2,
                    'contributionCalendar': {'totalContributions': 3, 'weeks': [{'contributionDays': [
                        {'date': '2026-10-03', 'contributionCount': 1}, {'date': '2026-10-04', 'contributionCount': 2}]}]}}}}}
            self.fail('Unexpected GraphQL query')
        data = self.function('fetch_github')('owner', 'TEST_TOKEN', dt.date(2026, 10, 4), request=request)
        self.assertEqual(data['stars'], 7)
        self.assertEqual(data['repo_count'], 2)
        self.assertEqual(data['languages'], {'Python': 20})
        self.assertEqual(data['contributions_year'], 3)
        self.assertEqual(data['calendar'][-1], ['2026-10-04', 2])

    def test_renderer_empty_state_has_no_fake_metrics(self):
        config = json.loads((MODULE.parents[2] / 'profile.json').read_text()) if (MODULE.parents[2] / 'profile.json').exists() else {'name': 'Valdeir Júnior'}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {'github': {'status': 'disabled', 'data': None}, 'dev': {'status': 'disabled', 'data': None}}, Path(tmp))
            assets = Path(tmp) / 'assets'
            self.assertTrue((assets / 'activity.svg').exists())
            svg = ET.parse(assets / 'activity.svg').getroot()
            text = ' '.join(svg.itertext())
            self.assertIn('GitHub account not configured', text)
            self.assertNotIn('0 contributions', text)
            self.assertNotIn('0 stars', text)

    def test_generated_links_and_alt_text_match_real_data_and_escape_content(self):
        config = {'name': 'Valdeir Júnior', 'github_username': 'owner', 'projects': [
            {'name': 'A & B', 'description': 'Useful <tool>', 'contribution': 'Parser',
             'repository': 'owner/tool', 'url': 'https://github.com/owner/tool', 'technologies': ['Python']}],
            'contacts': [{'label': 'Website', 'url': 'https://example.com/?a=1&b=2'}]}
        state = {'github': {'username': 'owner', 'status': 'ok', 'as_of': '2026-10-04', 'data': {
            'stars': 11, 'repo_stars': {'owner/tool': 11}, 'calendar': [], 'year': 2026}}, 'dev': {'status': 'disabled', 'data': None}}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, state, Path(tmp))
            readme = (Path(tmp) / 'README.md').read_text()
            self.assertIn('https://github.com/owner/tool', readme)
            self.assertIn('11 stars', readme)
            self.assertIn('A &amp; B', readme)
            self.assertIn('https://example.com/?a=1&amp;b=2', readme)
            for p in (Path(tmp) / 'assets').glob('*.svg'):
                ET.parse(p)

    def test_rendering_same_input_is_byte_identical(self):
        config = {'name': 'Valdeir Júnior'}
        state = {'github': {'status': 'disabled', 'data': None}, 'dev': {'status': 'disabled', 'data': None}}
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            render = self.function('render_profile')
            render(config, state, Path(a)); render(config, state, Path(b))
            left = {str(p.relative_to(a)): p.read_bytes() for p in Path(a).rglob('*') if p.is_file()}
            right = {str(p.relative_to(b)): p.read_bytes() for p in Path(b).rglob('*') if p.is_file()}
            self.assertEqual(left, right)

    def test_enabling_previously_disabled_source_does_not_crash(self):
        previous = {'username': None, 'status': 'disabled', 'data': None}
        result = self.function('refresh_source')(previous, 'owner', lambda: {'stars': 2}, '2026-10-05')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['stars'], 2)

    def test_activity_chart_draws_zero_activity_without_dividing_by_zero(self):
        calendar = [['2026-10-04', 0]]
        config = {'name': 'Test', 'github_username': 'owner'}
        state = {'github': {'username': 'owner', 'status': 'ok', 'as_of': '2026-10-04', 'data': {'calendar': calendar}}, 'dev': {}}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, state, Path(tmp))
            text = ' '.join(ET.parse(Path(tmp) / 'assets/activity.svg').getroot().itertext())
            self.assertIn('0 contributions', text)
            self.assertIn('0 active days', text)

    def test_disabled_dev_removes_old_generated_posts(self):
        config = {'name': 'Test', 'dev': {'enabled': True, 'username': 'writer'}}
        state = {'github': {}, 'dev': {'username': 'writer', 'status': 'ok', 'as_of': '2026-10-04', 'data': {
            'stats': {'articles': 1, 'reactions': 2, 'comments': 3}, 'articles': [{'title': 'Post', 'url': 'https://dev.to/writer/post',
            'published_at': '2026-10-01T00:00:00Z', 'reactions': 2, 'comments': 3}]}}}
        with tempfile.TemporaryDirectory() as tmp:
            render = self.function('render_profile')
            render(config, state, Path(tmp))
            self.assertTrue((Path(tmp) / 'assets/writing-1.svg').exists())
            config['dev']['enabled'] = False
            render(config, state, Path(tmp))
            self.assertFalse((Path(tmp) / 'assets/writing-1.svg').exists())
            self.assertNotIn('https://dev.to/writer/post', (Path(tmp) / 'README.md').read_text())

    def test_dev_key_cannot_mix_another_accounts_private_metrics(self):
        def request(url, headers=None, body=None):
            if '/users/me' in url:
                return {'username': 'another-account'}
            if '/articles?' in url:
                return [{'title': 'Owner post', 'url': 'https://dev.to/owner/post', 'published_at': '2026-10-01T00:00:00Z',
                         'public_reactions_count': 2, 'comments_count': 3}]
            self.fail('Another account must not be queried')
        result = self.function('fetch_dev')('owner', 'TEST_KEY', request=request)
        self.assertEqual(result['stats']['reactions'], 2)
        self.assertIsNone(result['stats']['views'])
        self.assertEqual(result['stats']['authenticated_status'], 'unavailable')

    def test_invalid_contact_url_is_rejected(self):
        with self.assertRaises(ValueError):
            self.function('valid_url')('javascript:alert(1)')

    def test_offline_cli_cannot_show_snapshot_for_different_identity(self):
        import os
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'profile.json').write_text(json.dumps({'name': 'Test', 'github_username': 'new-owner'}))
            data = root / 'tools/profile/data'; data.mkdir(parents=True)
            (data / 'sources.json').write_text(json.dumps({'github': {'username': 'old-owner', 'status': 'ok',
                'as_of': '2026-10-01', 'data': {'stars': 77}}}))
            env = {k: v for k, v in os.environ.items() if k not in ('GITHUB_OUTPUT', 'GITHUB_REPOSITORY_OWNER')}
            result = subprocess.run([__import__('sys').executable, str(MODULE), '--root', str(root), '--offline'],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ' '.join(''.join(n.itertext()) for n in ET.parse(root / 'assets/activity.svg').getroot().findall('.//{http://www.w3.org/2000/svg}text'))
            self.assertIn('GitHub data unavailable', svg)
            self.assertNotIn('77', svg)

    def test_readme_source_images_exist_after_adding_and_removing_projects(self):
        import re
        config = {'name': 'Test', 'projects': [{'name': 'One', 'description': 'Tool'}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); render = self.function('render_profile')
            render(config, {}, root)
            config['projects'] = []
            render(config, {}, root)
            readme = (root / 'README.md').read_text()
            for filename in re.findall(r'(?:src|srcset)="([^"]+)"', readme):
                self.assertTrue((root / filename).is_file(), filename)
            self.assertFalse((root / 'assets/work-1.svg').exists())

    def test_weekly_bars_keep_every_contribution(self):
        start = dt.date(2025, 10, 6)
        calendar = [[(start + dt.timedelta(days=i)).isoformat(), i % 4] for i in range(365)]
        bins, pad = self.function('weekly')(calendar)
        self.assertEqual(len(bins), 53)
        self.assertEqual(sum(bins), sum(n for _, n in calendar))
        self.assertEqual(bins[0], calendar[0][1])
        self.assertEqual(bins[-1], sum(n for _, n in calendar[-7:]))
        self.assertEqual(pad, 6)

    def test_hero_links_are_separate_clickable_slices_on_one_line(self):
        import re
        config = {'name': 'Valdeir Júnior', 'contacts': [
            {'label': 'GitHub', 'url': 'https://github.com/owner'},
            {'label': 'LinkedIn', 'detail': None, 'url': 'https://www.linkedin.com/in/owner/'},
            {'label': 'Email', 'detail': 'owner@example.com', 'url': 'mailto:owner@example.com'},
            {'label': 'Pending', 'url': None}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.function('render_profile')(config, {}, root)
            row = [line for line in (root / 'README.md').read_text().splitlines() if 'hero-gutter.svg' in line]
            self.assertEqual(len(row), 1)
            row = row[0]
            for name in ('hero-link-1.svg', 'hero-link-2.svg', 'hero-link-3.svg', 'hero-link-4.svg', 'hero-art.svg'):
                self.assertIn(name, row)
            self.assertNotRegex(row, r'>\s+<')
            self.assertEqual(re.findall(r'<a href="([^"]+)">', row),
                             ['https://github.com/owner', 'https://www.linkedin.com/in/owner/', 'mailto:owner@example.com'])
            shares = [float(value) for value in re.findall(r'width="([\d.]+)%"', row)]
            self.assertEqual(len(shares), 6)
            self.assertLessEqual(sum(shares), 100)
            self.assertGreater(sum(shares), 99.99)
            names = ['hero-gutter'] + ['hero-link-' + str(i) for i in range(1, 5)] + ['hero-art']
            for suffix, total in (('', 1024), ('-mobile', 480)):
                roots = [ET.parse(root / 'assets' / (name + suffix + '.svg')).getroot() for name in names]
                self.assertEqual(len({svg.get('height') for svg in roots}), 1)
                self.assertAlmostEqual(sum(float(svg.get('width')) for svg in roots), total, places=2)
                for svg, share in zip(roots, shares):
                    self.assertAlmostEqual(float(svg.get('width')) / total * 100, share, places=2)

    def test_each_svg_embeds_only_the_fonts_it_uses(self):
        config = {'name': 'Valdeir Júnior', 'contacts': [{'label': 'GitHub', 'url': 'https://github.com/owner'}],
                  'projects': [{'name': 'One', 'description': 'Tool'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {}, Path(tmp))
            assets = Path(tmp) / 'assets'
            self.assertNotIn('@font-face', (assets / 'hero-gutter.svg').read_text())
            self.assertNotIn('@font-face', (assets / 'hero-link-1-mobile.svg').read_text())
            self.assertIn('font-family:INT;font-weight:800', (assets / 'hero.svg').read_text())
            self.assertIn('font-family:INT;font-weight:800', (assets / 'work-1.svg').read_text())
            link = (assets / 'hero-link-1.svg').read_text()
            self.assertIn('font-family:JBM;font-weight:400', link)
            self.assertNotIn('font-family:INT;font-weight', link)

    def test_http_transport_encodes_graphql_json_and_decodes_response(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                response = json.dumps({'received': payload, 'content_type': self.headers['Content-Type']}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(response)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            result = self.function('http_json')('http://127.0.0.1:' + str(server.server_port), body={'query': 'query { viewer { login } }'})
            self.assertEqual(result, {'received': {'query': 'query { viewer { login } }'}, 'content_type': 'application/json'})
        finally:
            server.shutdown(); server.server_close(); worker.join()


if __name__ == '__main__':
    unittest.main()

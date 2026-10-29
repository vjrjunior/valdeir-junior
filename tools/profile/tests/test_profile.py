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
        config = json.loads((MODULE.parents[2] / 'profile.json').read_text())
        config['github_username'] = None
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {'github': {'status': 'disabled', 'data': None}, 'dev': {'status': 'disabled', 'data': None}}, Path(tmp))
            assets = Path(tmp) / 'assets'
            activity = ' '.join(ET.parse(assets / 'activity.svg').getroot().itertext())
            about = ' '.join(ET.parse(assets / 'about.svg').getroot().itertext())
            self.assertIn('GitHub activity is not connected yet.', activity)
            self.assertNotIn('0 contributions', activity)
            self.assertIn('N/A', about)
            self.assertNotIn('On GitHub since', about)

    def test_generated_links_and_alt_text_match_real_data_and_escape_content(self):
        config = {'name': 'Valdeir Júnior', 'github_username': 'owner', 'stats': ['contributions_all', 'streak_longest'],
                  'contacts': [{'label': 'Website', 'detail': 'A & B <tools>', 'url': 'https://example.com/?a=1&b=2'}]}
        state = {'github': {'username': 'owner', 'status': 'ok', 'as_of': '2026-10-04', 'data': {
            'contributions_all': 1234, 'streak_longest': 9, 'calendar': [['2026-10-03', 2], ['2026-10-04', 5]]}},
            'dev': {'status': 'disabled', 'data': None}}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, state, Path(tmp))
            readme = (Path(tmp) / 'README.md').read_text()
            self.assertIn('https://example.com/?a=1&amp;b=2', readme)
            self.assertIn('A &amp; B &lt;tools&gt;', readme)
            self.assertIn('Contributions: 1234', readme)
            self.assertIn('7 contributions in the last year. 2 active days, busiest on Oct 4 with 5.', readme)
            for p in (Path(tmp) / 'assets').glob('*.svg'):
                ET.parse(p)
            self.assertIn('A & B <tools>', ' '.join(ET.parse(Path(tmp) / 'assets/contact-1.svg').getroot().itertext()))

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
            self.assertIn('GitHub activity is unavailable right now.', svg)
            self.assertNotIn('77', svg)
            about = ET.parse(root / 'assets/about.svg').getroot().findall('.//{http://www.w3.org/2000/svg}text')
            self.assertNotIn('77', ' '.join(''.join(n.itertext()) for n in about))

    def test_readme_source_images_exist_after_adding_and_removing_contacts(self):
        import re
        config = {'name': 'Test', 'contacts': [{'label': 'GitHub', 'url': 'https://github.com/owner'}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); render = self.function('render_profile')
            render(config, {}, root)
            self.assertTrue((root / 'assets/contact-1.svg').exists())
            config['contacts'] = []
            render(config, {}, root)
            readme = (root / 'README.md').read_text()
            for filename in re.findall(r'(?:src|srcset)="([^"]+)"', readme):
                self.assertTrue((root / filename).is_file(), filename)
            self.assertFalse((root / 'assets/contact-1.svg').exists())
            self.assertFalse((root / 'assets/hero-link-1.svg').exists())

    def test_link_rows_are_separate_clickable_slices_on_one_line(self):
        import re
        config = {'name': 'Valdeir Júnior', 'contacts': [
            {'label': 'GitHub', 'url': 'https://github.com/owner'},
            {'label': 'LinkedIn', 'detail': None, 'url': 'https://www.linkedin.com/in/owner/'},
            {'label': 'Email', 'detail': 'owner@example.com', 'url': 'mailto:owner@example.com'},
            {'label': 'Pending', 'url': None}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.function('render_profile')(config, {}, root)
            lines = (root / 'README.md').read_text().splitlines()
            self.assertIn('assets/hero.svg', lines[2])
            names = ['hero-start'] + ['hero-link-' + str(i) for i in range(1, 5)] + ['hero-end']
            links = ['https://github.com/owner', 'https://www.linkedin.com/in/owner/', 'mailto:owner@example.com']
            row = [line for line in lines if 'hero-start.svg' in line]
            self.assertEqual(len(row), 1)
            row = row[0]
            self.assertNotRegex(row, r'>\s+<')
            self.assertEqual(re.findall(r'<a href="([^"]+)">', row), links)
            shares = [float(value) for value in re.findall(r'width="([\d.]+)%"', row)]
            self.assertEqual(len(shares), len(names))
            self.assertLessEqual(sum(shares), 100)
            self.assertGreater(sum(shares), 99.99)
            for suffix, total in (('', 1024), ('-mobile', 480)):
                roots = [ET.parse(root / 'assets' / (name + suffix + '.svg')).getroot() for name in names]
                self.assertEqual(len({svg.get('height') for svg in roots}), 1)
                self.assertAlmostEqual(sum(float(svg.get('width')) for svg in roots), total, delta=.05)
                for svg, share in zip(roots, shares):
                    self.assertAlmostEqual(float(svg.get('width')) / total * 100, share, places=2)

    def test_each_svg_embeds_only_the_fonts_it_uses(self):
        config = {'name': 'Valdeir Júnior', 'contacts': [{'label': 'GitHub', 'url': 'https://github.com/owner'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {}, Path(tmp))
            assets = Path(tmp) / 'assets'
            self.assertNotIn('@font-face', (assets / 'hero-start.svg').read_text())
            self.assertNotIn('@font-face', (assets / 'hero-link-1-mobile.svg').read_text())
            hero = (assets / 'hero.svg').read_text()
            self.assertIn('font-family:HG;font-weight:500', hero)
            self.assertIn('font-family:DM;font-weight:400', hero)
            link = (assets / 'hero-link-1.svg').read_text()
            self.assertIn('font-family:HG;font-weight:500', link)
            self.assertNotIn('font-family:DM;font-weight', link)

    def test_sections_are_numbered_in_order_when_optional_ones_are_missing(self):
        config = {'name': 'Test', 'contacts': [{'label': 'GitHub', 'url': 'https://github.com/owner'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {}, Path(tmp))
            text = lambda name: ' '.join(ET.parse(Path(tmp) / 'assets' / name).getroot().itertext())
            self.assertIn('(01)', text('about.svg'))
            self.assertIn('(02)', text('activity.svg'))
            self.assertIn('(03)', text('contact.svg'))
            self.assertFalse((Path(tmp) / 'assets/stack.svg').exists())

    def test_hero_code_animation_rests_on_its_first_frame_and_loops_back_to_it(self):
        import re
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')({'name': 'Test', 'contacts': []}, {}, Path(tmp))
            for name in ('hero.svg', 'hero-mobile.svg'):
                svg = (Path(tmp) / 'assets' / name).read_text()
                self.assertIn('@media(prefers-reduced-motion:reduce){*{animation:none!important}}', svg)
                frames = {key: re.findall(r'([\d.,%]+)\{([^{}]*)\}', body)
                          for key, body in re.findall(r'@keyframes (\w+)\{((?:[^{}]*\{[^{}]*\})*)\}', svg)}
                covers = re.findall(r'<g class="ty(\d+)"><rect x="[^"]+" y="([^"]+)" width="([^"]+)"', svg)
                self.assertGreater(len(covers), 2)
                (first, top, _), (last, bottom, _) = covers[0], covers[-1]
                pitch = (float(bottom) - float(top)) / (int(last) - int(first))
                scroll = frames['tys']
                self.assertEqual(scroll[0], ('0%', 'transform:translateY(0)'))
                self.assertEqual(scroll[-1][0], '100%')
                self.assertAlmostEqual(float(re.search(r'translateY\((-?[\d.]+)px\)', scroll[-1][1]).group(1)),
                                       -len(self.function('CODE').splitlines()) * pitch)
                for index, _, width in covers:
                    cover = frames['ty' + index]
                    self.assertTrue(cover[0][0].startswith('0%,'))
                    self.assertIn('translateX(0)', cover[0][1])
                    self.assertTrue(cover[-1][0].endswith(',100%'))
                    self.assertIn(f'translateX({width}px)', cover[-1][1])
                rest = re.search(r'\.tyc\{transform:(translateX\([^)]*\))', svg).group(1)
                cursor = frames['tyc']
                self.assertIn(rest, cursor[0][1])
                self.assertIn(rest, cursor[-1][1])

    def test_stack_icons_follow_their_motif_and_show_whole_without_motion(self):
        import re
        sprites, stack = self.function('SPRITES'), self.function('stack')
        for name, (rows, groups) in sprites.items():
            self.assertEqual(len({len(row) for row in rows}), 1, name)
            self.assertLessEqual(set(''.join(rows)) - set('.123456'), set(groups), name)
        card = lambda motif: stack({'stack': [{'area': 'Tools', 'motif': motif, 'tools': ['Git']}]}, 1024)[0]
        self.assertEqual(card('unknown'), card(next(iter(sprites))))
        self.assertNotEqual(card('branch'), card('code'))
        for width in (1024, 480):
            svg = stack({'stack': [{'area': name, 'motif': name, 'tools': []} for name in sprites]}, width)[0]
            self.assertIn('@media(prefers-reduced-motion:reduce){*{animation:none!important}}', svg)
            groups = re.findall(r'<g class="(s\d+)"([^>]*)>', svg)
            self.assertTrue(groups)
            for cls, extra in groups:
                self.assertEqual(extra, '')
                kind = re.search(r'\.' + cls + r'\{animation:(\w+) ', svg).group(1)
                self.assertIn('@keyframes ' + kind + '{', svg)

    def test_rules_stay_inside_the_margins_and_stat_dividers_meet_them_at_joints(self):
        import re
        n = self.function('n')
        config = {'name': 'Test', 'stats': ['years', 'contributions_all', 'streak_longest', 'followers'],
                  'stack': [{'area': 'Tools', 'tools': ['Git']}], 'contacts': [{'label': 'GitHub', 'url': 'https://github.com/owner'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.function('render_profile')(config, {}, Path(tmp))
            for path in (Path(tmp) / 'assets').glob('*.svg'):
                width = float(ET.parse(path).getroot().get('width'))
                margin = 20 if width == 480 else 40
                for x1, x2 in re.findall(r'<path d="M([\d.]+) [\d.]+H([\d.]+)" stroke', path.read_text()):
                    self.assertGreaterEqual(float(x1), margin, path.name)
                    self.assertLessEqual(float(x2), width - margin, path.name)
        for width in (1024, 480):
            svg = self.function('about')(config, {}, '2026-10-07', width)[0]
            rules = re.findall(r'<path d="M([\d.]+) ([\d.]+)H([\d.]+)"', svg)
            verticals = re.findall(r'<path d="M([\d.]+) ([\d.]+)V([\d.]+)"', svg)
            joints = set(re.findall(r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="5" height="5"', svg))
            self.assertEqual(len({(x1, x2) for x1, _, x2 in rules}), 1)
            heights = {float(y) - .5 for _, y, _ in rules}
            self.assertTrue(verticals)
            for x, y1, y2 in verticals:
                for y in (float(y1), float(y2)):
                    self.assertIn(y, heights)
                    self.assertIn((n(float(x) - 2.5), n(y - 2)), joints)

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

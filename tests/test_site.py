import importlib
import json
import os
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


TEST_DATABASE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DATABASE.close()
os.environ.setdefault('DATABASE_PATH', TEST_DATABASE.name)
app_module = importlib.import_module('app')


def setUpModule():
    # Other test modules may delete the database they created, so use a fresh one.
    app_module.DATABASE_PATH = TEST_DATABASE.name
    app_module.init_db()


def tearDownModule():
    os.unlink(TEST_DATABASE.name)

PUBLIC_PAGES = ['/', '/about', '/programs', '/admissions', '/courses', '/news', '/contact', '/register']


def valid_enquiry(**overrides):
    data = {
        'parent_name': 'Dilnoza Karimova',
        'parent_phone': '90 123 45 67',
        'child_name': 'Aziz',
        'child_birth_date': '2019-04-02',
        'grade': '1',
        'language': 'uz',
        'message': 'Salom',
        'consent': '1',
    }
    data.update(overrides)
    return data


class SitePageTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_public_pages_use_the_school_brand(self):
        for path in PUBLIC_PAGES:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('<html lang="uz" data-brand="school">', html)
                self.assertEqual(len(re.findall(r'<h1[\s>]', html)), 1)
                self.assertIn(f'<link rel="canonical" href="https://iceberglc.com{path}">', html)
                self.assertIn('/static/school/img/logo-h-maroon.png', html)
                self.assertNotIn('cdn.tailwindcss.com', html)

    def test_titles_are_unique(self):
        titles = []
        for path in PUBLIC_PAGES:
            html = self.client.get(path).get_data(as_text=True)
            titles.append(re.search(r'<title>(.*?)</title>', html).group(1))
        self.assertEqual(len(titles), len(set(titles)))

    def test_school_structured_data_has_no_placeholders(self):
        html = self.client.get('/').get_data(as_text=True)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data['@type'], 'School')
        self.assertEqual(data['subOrganization']['url'], 'https://iceberglc.com/courses')

        def strings(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
            elif isinstance(value, str):
                yield value
        self.assertFalse([text for text in strings(data) if '[' in text])

    def test_unconfirmed_facts_show_placeholders(self):
        html = self.client.get('/admissions').get_data(as_text=True)
        self.assertIn('<span class="ph">[NARX]</span>', html)
        self.assertNotIn('[TELEFON]', html)
        self.assertIn(f'href="tel:{app_module.SCHOOL_CONFIG["phone"]}"', html)

    def test_language_switcher_is_not_machine_translated(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('<label class="lang notranslate" translate="no">', html)
        self.assertIn('<select class="notranslate" translate="no" data-lang-select', html)

    def test_light_page_heroes_use_dark_buttons(self):
        # btn-light and btn-ghost are white; on the cream page hero they would be unreadable.
        for path in ('/about', '/programs', '/admissions', '/courses', '/news', '/contact', '/register'):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                hero = html.split('<section class="page-hero', 1)[1].split('</section>', 1)[0]
                self.assertNotIn('btn-light', hero)
                self.assertNotIn('btn-ghost', hero)

    def test_coming_soon_page_in_uzbek_and_english(self):
        response = self.client.get('/ilova')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Yangi imkoniyatlar ustida ishlayapmiz', html)
        self.assertIn("We're working on new features", html)
        self.assertIn('<meta name="robots" content="noindex">', html)

    def test_portal_and_app_links_follow_school_config(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn(f'href="{app_module.SCHOOL_CONFIG["portal_url"]}">Portal</a>', html)
        self.assertIn(f'href="{app_module.SCHOOL_CONFIG["app_url"]}"', html)

    def test_founding_year_and_campus_photos(self):
        year = app_module.SCHOOL_CONFIG['founded']
        home = self.client.get('/').get_data(as_text=True)
        about = self.client.get('/about').get_data(as_text=True)
        self.assertIn(f'Iceberg — {year}-yildan beri', home)
        self.assertIn(f'"foundingDate": "{year}"', home)
        self.assertIn(f'{year}-yildan beri', about)
        for name in ('playground', 'building', 'courtyard', 'football', 'rest-room', 'dining-hall', 'kitchen'):
            self.assertIn(f'/static/school/img/{name}.jpg', about)

    def test_search_results_use_the_school_crest_and_name(self):
        html = self.client.get('/').get_data(as_text=True)
        for href in ('/static/favicon-48x48.png', '/static/android-chrome-192x192.png'):
            self.assertIn(f'href="{href}"', html)
            self.assertEqual(self.client.get(href).status_code, 200)
        blocks = [json.loads(block) for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        website = [block for block in blocks if block['@type'] == 'WebSite']
        self.assertEqual(website[0]['name'], 'Iceberg School')
        self.assertEqual(website[0]['url'], 'https://iceberglc.com/')
        about = self.client.get('/about').get_data(as_text=True)
        self.assertNotIn('"WebSite"', about)

    def test_news_from_config_reaches_the_static_site(self):
        post = json.load(open('config/news.json', encoding='utf-8'))['posts'][0]
        news = self.client.get('/news').get_data(as_text=True)
        self.assertIn('news-card lift rv featured', news)
        self.assertIn(post['title'], news)
        self.assertIn(f'<a class="media poster" href="/static/{post["image"]}"', news)
        self.assertIn('Kattalashtirish', news)
        self.assertEqual(self.client.get(f'/static/{post["image"]}').status_code, 200)
        self.assertIn(post['excerpt'], self.client.get('/').get_data(as_text=True))
        with patch.object(app_module, 'STATIC_BUILD_MODE', True):
            self.assertIn(post['title'], self.client.get('/news').get_data(as_text=True))
        self.assertTrue(all(isinstance(item['id'], int) for item in app_module.fetch_news_posts(include_unpublished=True)))

    def test_school_location_from_the_owner_pin(self):
        school = app_module.SCHOOL_CONFIG
        contact = self.client.get('/contact').get_data(as_text=True)
        news = self.client.get('/news').get_data(as_text=True)
        for html in (contact, news):
            self.assertIn(f'href="{school["map_url"]}"', html.replace('&amp;', '&'))
            self.assertIn('Yandex Maps', html)
        self.assertNotIn('[MANZIL]', contact)
        self.assertNotIn('[ISH VAQTI]', contact)
        self.assertIn(school['hours'], contact)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', contact, re.S).group(1))
        self.assertEqual(data['geo']['latitude'], float(school['latitude']))
        self.assertEqual(data['address']['addressLocality'], 'Uychi')
        self.assertEqual(data['address']['streetAddress'], school['address'])
        self.assertEqual(data['telephone'], school['phone'])

    def test_partnership_pages_in_uzbek_and_english(self):
        for path, lang, heading in (('/hamkorlik', 'uz', 'Keling, birga quramiz'), ('/partners', 'en', 'build something together')):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}" data-brand="school">', html)
                self.assertEqual(len(re.findall(r'<h1[\s>]', html)), 1)
                self.assertIn(heading, html)
                self.assertIn(f'<link rel="canonical" href="https://iceberglc.com{path}">', html)
                self.assertIn('hreflang="uz" href="https://iceberglc.com/hamkorlik"', html)
                self.assertIn('hreflang="en" href="https://iceberglc.com/partners"', html)
                self.assertIn(f'href="tel:{app_module.SCHOOL_CONFIG["phone"]}"', html)
        self.assertIn('Korean, Chinese', self.client.get('/partners').get_data(as_text=True))
        sitemap = self.client.get('/sitemap.xml').get_data(as_text=True)
        self.assertIn('https://iceberglc.com/hamkorlik', sitemap)
        self.assertIn('https://iceberglc.com/partners', sitemap)
        self.assertIn('href="/partners"', self.client.get('/').get_data(as_text=True))

    def test_courses_page_lists_registration_programs(self):
        html = self.client.get('/courses').get_data(as_text=True)
        for program in app_module.REGISTRATION_CONFIG['programs']:
            self.assertIn(f'id="{program["id"]}"', html)
            self.assertIn(f'/register?program={program["id"]}', html)
        self.assertIn('id="savollar"', html)

    def test_every_legacy_url_redirects_to_a_live_page(self):
        for source, target, code in app_module.LEGACY_REDIRECTS:
            path = source.replace('/*', '/old-page/2024')
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, code)
                self.assertTrue(response.location.endswith(target))
                landing = self.client.get(target.split('#')[0])
                self.assertEqual(landing.status_code, 200)

    def test_legacy_redirects_never_cover_private_admin_paths(self):
        private = ('/admin', '/portal', '/students', '/contacts_list')
        for source, _target, _code in app_module.LEGACY_REDIRECTS:
            with self.subTest(source=source):
                self.assertFalse(source.startswith(private))

    def test_former_learning_center_urls_redirect_permanently(self):
        for old, new in (('/our_programs', '/courses'), ('/questions', '/courses#savollar')):
            with self.subTest(old=old):
                response = self.client.get(old)
                self.assertEqual(response.status_code, 301)
                self.assertTrue(response.location.endswith(new))

    def test_contact_page_has_no_hidden_admin_login(self):
        html = self.client.get('/contact').get_data(as_text=True)
        self.assertNotIn('admin_password', html)
        self.assertEqual(self.client.post('/contact').status_code, 405)


class AdmissionsFormTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    @patch.object(app_module, 'send_telegram_notification')
    @patch.object(app_module, 'send_registration_lead_to_management', return_value=True)
    def test_valid_enquiry_is_stored_and_forwarded_as_school_lead(self, forward, telegram):
        response = self.client.post('/admissions', data=valid_enquiry(grade='7'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/admissions/thanks'))
        payload = forward.call_args.args[0]
        self.assertEqual(payload['source'], 'school-website')
        self.assertEqual(payload['program'], 'Grade 7')
        self.assertEqual(payload['branch'], app_module.SCHOOL_BRANCH_NAME)
        self.assertEqual(payload['phone'], '+998901234567')
        self.assertIn('Farzand: Aziz', payload['message'])
        telegram.assert_called_once()
        with sqlite3.connect(TEST_DATABASE.name) as connection:
            row = connection.execute(
                'SELECT student_name, course, preferred_branch, forwarded_to_management FROM students ORDER BY id DESC LIMIT 1'
            ).fetchone()
        self.assertEqual(row, ('Dilnoza Karimova', 'school-grade-7', 'school', 1))

    @patch.object(app_module, 'send_telegram_notification')
    @patch.object(app_module, 'send_registration_lead_to_management', return_value=True)
    def test_invalid_enquiries_are_rejected(self, forward, _telegram):
        for field, override in (
            ('parent_name', {'parent_name': 'A'}),
            ('parent_phone', {'parent_phone': '123'}),
            ('grade', {'grade': '12'}),
            ('child_birth_date', {'child_birth_date': '2999-01-01'}),
            ('consent', {'consent': ''}),
        ):
            with self.subTest(field=field):
                response = self.client.post('/admissions', data=valid_enquiry(**override))
                self.assertEqual(response.status_code, 422)
                self.assertIn(f'id="{field}_error"', response.get_data(as_text=True))
        forward.assert_not_called()

    @patch.object(app_module, 'send_registration_lead_to_management')
    def test_honeypot_stores_nothing(self, forward):
        response = self.client.post('/admissions', data=valid_enquiry(website='spam'))
        self.assertEqual(response.status_code, 302)
        forward.assert_not_called()


if __name__ == '__main__':
    unittest.main()

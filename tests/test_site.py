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
        self.assertIn('<span class="ph">[TELEFON]</span>', html)

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

    def test_courses_page_lists_registration_programs(self):
        html = self.client.get('/courses').get_data(as_text=True)
        for program in app_module.REGISTRATION_CONFIG['programs']:
            self.assertIn(f'id="{program["id"]}"', html)
            self.assertIn(f'/register?program={program["id"]}', html)
        self.assertIn('id="savollar"', html)

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

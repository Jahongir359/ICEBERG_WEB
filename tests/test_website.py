import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from scripts.export_public_content import export


class WebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        database = str(Path(cls.directory.name) / 'website.db')
        os.environ['DATABASE_PATH'] = database
        cls.module = importlib.import_module('app')
        cls.original_database = cls.module.DATABASE_PATH
        cls.module.DATABASE_PATH = database
        cls.module.init_db()
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.module.DATABASE_PATH = cls.original_database
        cls.directory.cleanup()

    def test_all_public_pages_have_language_pairs(self):
        from scripts.build_firebase import PUBLIC_ROUTES
        for route in PUBLIC_ROUTES:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                english = route == '/en' or route.startswith('/en/')
                self.assertIn('<html lang="en">' if english else '<html lang="uz">', html)
                self.assertIn('hreflang="uz"', html)
                self.assertIn('hreflang="en"', html)
                self.assertNotIn('translate.google', html)
                self.assertNotIn('cdn.tailwindcss.com', html)
                self.assertIn('href="#main-content"', html)

    def test_no_unverified_homepage_outcomes(self):
        for route in ('/', '/en'):
            html = self.client.get(route).get_data(as_text=True)
            for claim in ('500+', '1,500', 'data-target=', 'IELTS 8 score holder'):
                self.assertNotIn(claim, html)
            self.assertIn('2027', html)

    def test_english_application_preserves_program_and_validation(self):
        html = self.client.get('/en/register?program=chemistry&branch=gayrat').get_data(as_text=True)
        self.assertIn('value="chemistry" selected', html)
        self.assertIn('value="gayrat" selected', html)
        self.assertIn('action="/en/register"', html)
        self.assertIn('Chemistry', html)
        response = self.client.post('/en/register', data={})
        self.assertEqual(response.status_code, 422)
        self.assertIn('Enter your full name.', response.get_data(as_text=True))

    @patch('app.send_telegram_notification')
    @patch('app.send_registration_lead_to_management', return_value=False)
    def test_english_application_is_saved_and_keeps_language(self, _forward, _notify):
        response = self.client.post('/en/register', data={
            'student_name': 'Test Student', 'student_phone': '901234567',
            'course': 'ielts', 'preferred_branch': 'main',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/en/register?success=1')
        with closing(sqlite3.connect(self.module.DATABASE_PATH)) as connection:
            self.assertEqual(connection.execute('SELECT course FROM students WHERE student_name = ?', ('Test Student',)).fetchone()[0], 'ielts')

    def test_contact_uses_admissions_telegram_in_both_languages(self):
        for route in ('/contact', '/en/contact'):
            html = self.client.get(route).get_data(as_text=True)
            self.assertIn('action="https://t.me/iceberg_qabulxona"', html)
            self.assertIn('data-static-lead-form="contact"', html)
            self.assertNotIn('wa.me', html)
        # Contact drafts no longer post personal details to the website.
        self.assertEqual(self.client.post('/contact', data={'name': 'Test'}).status_code, 405)

    def test_static_snapshot_displays_published_content(self):
        snapshot = {'news': [{'title': 'Verified event', 'excerpt': '', 'body': '<script>unsafe</script>',
                             'post_type': 'event', 'event_date': '2026-10-01',
                             'created_at': '2026-10-01', 'media_items': []}],
                    'content': {'hero_main_title': 'Approved headline'}, 'assets': {}, 'faqs': []}
        with patch.object(self.module, 'STATIC_BUILD_MODE', True), patch.object(self.module, 'PUBLIC_CONTENT', snapshot):
            home = self.client.get('/').get_data(as_text=True)
            news = self.client.get('/news').get_data(as_text=True)
            self.assertIn('Approved headline', home)
            self.assertIn('Verified event', news)
            self.assertIn('&lt;script&gt;', news)
            self.assertNotIn('<script>unsafe</script>', news)


class PublicExportTests(unittest.TestCase):
    def test_build_copies_only_approved_uploads(self):
        from scripts.build_firebase import copy_public_assets
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = root / 'static'
            (static / 'uploads').mkdir(parents=True)
            (static / 'published').mkdir()
            (static / 'uploads/private.png').write_bytes(b'private')
            (static / 'published/stale.png').write_bytes(b'stale')
            (static / 'published/approved.png').write_bytes(b'approved')
            (static / 'style.css').write_text('body {}')
            destination = root / 'public'
            copy_public_assets(static, destination, {'assets': {'site_logo': 'published/approved.png'}})
            self.assertTrue((destination / 'style.css').is_file())
            self.assertTrue((destination / 'published/approved.png').is_file())
            self.assertFalse((destination / 'uploads/private.png').exists())
            self.assertFalse((destination / 'published/stale.png').exists())

    def test_export_excludes_private_tables_drafts_and_unknown_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'cms.db'
            static_root = root / 'static'
            (static_root / 'uploads').mkdir(parents=True)
            (static_root / 'uploads/campus.png').write_bytes(b'public image fixture')
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript('''
                    CREATE TABLE site_content (content_key TEXT, content_value TEXT);
                    INSERT INTO site_content VALUES ('hero_main_title', 'Public title');
                    INSERT INTO site_content VALUES ('internal_secret', 'PRIVATE_SECRET');
                    CREATE TABLE site_assets (asset_key TEXT, file_path TEXT);
                    INSERT INTO site_assets VALUES ('site_logo', 'uploads/campus.png');
                    CREATE TABLE faq_items (id INTEGER, question TEXT, answer TEXT, sort_order INTEGER);
                    CREATE TABLE news_posts (id INTEGER, title TEXT, excerpt TEXT, body TEXT, post_type TEXT,
                                             event_date TEXT, created_at TEXT, is_published INTEGER);
                    INSERT INTO news_posts VALUES (1, 'Published', '', 'Event report', 'news', NULL, '2026-10-01', 1);
                    INSERT INTO news_posts VALUES (2, 'PRIVATE_DRAFT', '', '', 'news', NULL, '2026-10-01', 0);
                    CREATE TABLE news_media (id INTEGER, post_id INTEGER, file_path TEXT, media_type TEXT, caption TEXT, sort_order INTEGER);
                    INSERT INTO news_media VALUES (1, 1, 'uploads/campus.png', 'image', 'Campus', 1);
                    CREATE TABLE students (student_name TEXT, phone TEXT);
                    INSERT INTO students VALUES ('PRIVATE_STUDENT', 'PRIVATE_PHONE');
                    CREATE TABLE contacts (message TEXT);
                    INSERT INTO contacts VALUES ('PRIVATE_MESSAGE');
                ''')
            output = root / 'snapshot.json'
            snapshot = export(database, output, static_root)
            published = output.read_text()
            self.assertNotIn('PRIVATE_', published)
            self.assertEqual([post['title'] for post in snapshot['news']], ['Published'])
            self.assertTrue((static_root / snapshot['assets']['site_logo']).is_file())
            self.assertEqual(json.loads(published), snapshot)


if __name__ == '__main__':
    unittest.main()

import csv
import importlib
import io
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.module = importlib.import_module('app')
        cls.original_database = cls.module.DATABASE_PATH
        cls.module.DATABASE_PATH = str(Path(cls.directory.name) / 'security.db')
        cls.module.init_db()
        cls.auth_patch = patch.object(cls.module, 'ADMIN_ENABLED', True)
        cls.hash_patch = patch.object(cls.module, 'ADMIN_PASSWORD_HASH', generate_password_hash('test-only-password-9284'))
        cls.auth_patch.start()
        cls.hash_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.hash_patch.stop()
        cls.auth_patch.stop()
        cls.module.DATABASE_PATH = cls.original_database
        cls.directory.cleanup()

    def setUp(self):
        self.client = self.module.app.test_client()
        with self.module.get_db_connection() as conn:
            conn.execute('DELETE FROM students')
            conn.execute('DELETE FROM contacts')

    def token(self):
        with self.client.session_transaction() as session:
            return session['_csrf_token']

    def login(self):
        self.client.get('/portal/' + self.module.ADMIN_LOGIN_SLUG)
        result = self.client.post('/portal/' + self.module.ADMIN_LOGIN_SLUG,
                                  data={'password': 'test-only-password-9284', 'csrf_token': self.token()})
        self.assertEqual(result.status_code, 302)
        self.client.get('/admin/dashboard')
        return self.token()

    def test_admin_default_password_and_missing_configuration_are_rejected(self):
        with self.module.app.test_request_context():
            self.assertFalse(self.module.process_admin_login(''))
            self.assertFalse(self.module.process_admin_login('iceberg-admin'))
        with patch.object(self.module, 'ADMIN_ENABLED', False):
            self.assertEqual(self.client.get('/admin/dashboard').status_code, 503)
            self.assertEqual(self.client.get('/portal/' + self.module.ADMIN_LOGIN_SLUG).status_code, 503)

    def test_login_and_authenticated_mutations_require_csrf(self):
        login_url = '/portal/' + self.module.ADMIN_LOGIN_SLUG
        self.assertEqual(self.client.post(login_url, data={'password': 'test-only-password-9284'}).status_code, 400)
        token = self.login()
        self.assertEqual(self.client.post('/admin/faq', data={'action': 'create_faq', 'question': 'Valid question?', 'answer': 'A sufficiently long answer.'}).status_code, 400)
        result = self.client.post('/admin/faq', data={'action': 'create_faq', 'question': 'Valid question?', 'answer': 'A sufficiently long answer.', 'csrf_token': token})
        self.assertEqual(result.status_code, 302)

    def test_admin_read_and_downloads_are_not_publicly_cacheable(self):
        token = self.login()
        for path in ('/students', '/contacts_list', '/admin/dashboard', '/admin/tools'):
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertIn('no-store', result.headers['Cache-Control'])
        for path in ('/admin/students/export', '/admin/contacts/export', '/admin/tools/backup'):
            result = self.client.post(path, data={'csrf_token': token})
            self.assertEqual(result.status_code, 200)
            self.assertIn('no-store', result.headers['Cache-Control'])
            if path == '/admin/tools/backup':
                self.assertIn('faq_items', result.get_json())

    def test_admin_forms_and_json_clients_include_csrf(self):
        self.login()
        for path in ('/admin/dashboard', '/admin/assets', '/admin/content', '/admin/editor', '/admin/news', '/admin/faq', '/admin/tools', '/students', '/contacts_list'):
            html = self.client.get(path).get_data(as_text=True)
            for form in re.findall(r'<form\b[^>]*>.*?</form>', html, re.S):
                if re.search(r'method="post"', form, re.I):
                    self.assertIn('name="csrf_token"', form, path)
            if path in ('/students', '/contacts_list'):
                self.assertIn('X-CSRF-Token', html)

    def test_json_shapes_and_sql_column_injection_are_rejected(self):
        token = self.login()
        for payload in ([], 'text', {'field': 5, 'value': 'x'}, {'field': 'student_name', 'value': 5}, {'field': 'student_name = 1; DROP TABLE students', 'value': 'x'}):
            result = self.client.post('/admin/students/update/1', json=payload, headers={'X-CSRF-Token': token})
            self.assertEqual(result.status_code, 400)

    def test_csv_formula_injection_is_neutralized(self):
        with self.module.app.test_request_context():
            response = self.module.build_csv_response('test.csv', ['Name'], [['=HYPERLINK("bad")'], ['  +123'], ['@SUM(1)'], ['Normal name']])
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        self.assertTrue(all(row[0].startswith("'") for row in rows[1:4]))
        self.assertEqual(rows[4][0], 'Normal name')

    def test_confirmation_requires_a_saved_submission_and_retries_are_idempotent(self):
        html = self.client.get('/register?success=1').get_data(as_text=True)
        self.assertRegex(html, r'data-registration-success\s+hidden')
        payload = {'student_name': 'Repeat Test', 'student_phone': '901234567', 'course': 'ielts', 'preferred_branch': 'main', 'submission_id': '12345678-1234-4234-8234-123456789012'}
        with patch.object(self.module, 'send_registration_lead_to_management', return_value=False) as forward, patch.object(self.module, 'send_telegram_notification') as notify:
            for _ in range(2):
                result = self.client.post('/register', data=payload)
                self.assertEqual(result.status_code, 302)
                self.assertIn('no-store', result.headers['Cache-Control'])
            self.assertEqual(forward.call_count, 1)
            self.assertEqual(notify.call_count, 1)
        with self.module.get_db_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM students').fetchone()[0], 1)
        html = self.client.get('/register?success=1').get_data(as_text=True)
        self.assertRegex(html, r'data-registration-form[^>]+hidden')

    def test_oversized_registration_is_rejected(self):
        self.assertEqual(self.client.post('/register', data={'student_name': 'x' * 20000}).status_code, 413)

    def test_path_prefix_and_symlink_escape_cannot_delete_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'static/uploads').mkdir(parents=True)
            (root / 'static-private').mkdir()
            victim = root / 'static-private/secret.txt'
            victim.write_text('keep')
            (root / 'static/uploads/link.txt').symlink_to(victim)
            permitted = root / 'static/uploads/public.png'
            permitted.write_bytes(b'image')
            with patch.object(self.module.app, 'root_path', str(root)):
                self.module.remove_static_file('../static-private/secret.txt')
                self.module.remove_static_file('uploads/link.txt')
                self.module.remove_static_file('uploads/public.png')
            self.assertTrue(victim.exists())
            self.assertFalse(permitted.exists())

    def test_unpublished_news_media_requires_an_admin_session(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            (static / 'uploads/news').mkdir(parents=True)
            (static / 'uploads/news/draft.png').write_bytes(b'private draft')
            with self.module.get_db_connection() as conn:
                cursor = conn.execute("INSERT INTO news_posts (title, body, post_type, is_published, created_at, updated_at) VALUES ('Draft', 'Draft text', 'news', 0, '2026-10-13', '2026-10-13')")
                post_id = cursor.lastrowid
                conn.execute("INSERT INTO news_media (post_id, media_type, file_path, caption, sort_order, created_at) VALUES (?, 'image', 'uploads/news/draft.png', '', 1, '2026-10-13')", (post_id,))
            with patch.object(self.module.app, '_static_folder', str(static)):
                self.assertEqual(self.client.get('/static/uploads/news/draft.png').status_code, 404)
                with self.module.get_db_connection() as conn:
                    conn.execute('UPDATE news_posts SET is_published = 1 WHERE id = ?', (post_id,))
                result = self.client.get('/static/uploads/news/draft.png')
                self.assertEqual(result.status_code, 200)
                self.assertIn('no-store', result.headers['Cache-Control'])
                result.close()
            with self.module.get_db_connection() as conn:
                conn.execute('DELETE FROM news_media WHERE post_id = ?', (post_id,))
                conn.execute('DELETE FROM news_posts WHERE id = ?', (post_id,))


if __name__ == '__main__':
    unittest.main()

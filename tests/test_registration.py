import importlib
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


TEST_DATABASE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DATABASE.close()
os.environ['DATABASE_PATH'] = TEST_DATABASE.name
app_module = importlib.import_module('app')


class RegistrationRouteTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        os.unlink(TEST_DATABASE.name)

    def setUp(self):
        self.client = app_module.app.test_client()

    def test_form_has_only_four_visible_data_fields(self):
        html = self.client.get('/register').get_data(as_text=True)
        for name in ('student_name', 'student_phone', 'course', 'preferred_branch'):
            self.assertIn(f'name="{name}"', html)
        for forbidden in ('parent_phone', 'email', 'dob', 'preferred_schedule', 'message'):
            self.assertNotIn(f'name="{forbidden}"', html)
        self.assertIn('+998 70 106 04 04', html)
        self.assertIn('https://t.me/iceberg_qabulxona', html)

    def test_safe_query_preselection_and_unknown_fallback(self):
        selected = self.client.get('/register?program=ielts&branch=gayrat').get_data(as_text=True)
        self.assertIn('value="ielts" selected', selected)
        self.assertIn('value="gayrat" selected', selected)
        unknown = self.client.get('/register?program=bad&branch=bad').get_data(as_text=True)
        self.assertNotIn('value="bad"', unknown)

    def test_required_field_errors(self):
        cases = (
            ({'student_phone': '901234567', 'course': 'ielts', 'preferred_branch': 'main'}, 'student_name'),
            ({'student_name': 'Ali Valiyev', 'student_phone': '123', 'course': 'ielts', 'preferred_branch': 'main'}, 'student_phone'),
            ({'student_name': 'Ali Valiyev', 'student_phone': '901234567', 'preferred_branch': 'main'}, 'course'),
            ({'student_name': 'Ali Valiyev', 'student_phone': '901234567', 'course': 'ielts'}, 'preferred_branch'),
        )
        for data, field in cases:
            with self.subTest(field=field):
                response = self.client.post('/register', data=data)
                self.assertEqual(response.status_code, 422)
                self.assertIn(f'id="{field}"', response.get_data(as_text=True))

    @patch.object(app_module, 'send_telegram_notification')
    @patch.object(app_module, 'send_registration_lead_to_management', return_value=True)
    def test_valid_programs_and_branches_are_stored_as_ids(self, _forward, _telegram):
        for index, branch in enumerate(('main', 'gayrat', 'unknown')):
            response = self.client.post('/register', data={
                'student_name': f'Test Student {index}',
                'student_phone': '+998 90 123 45 67',
                'course': 'ielts',
                'preferred_branch': branch,
            })
            self.assertEqual(response.status_code, 302)
            self.assertIn('/register?success=1', response.location)
        with sqlite3.connect(TEST_DATABASE.name) as connection:
            rows = connection.execute(
                'SELECT student_phone, course, preferred_branch FROM students ORDER BY id DESC LIMIT 3'
            ).fetchall()
        self.assertEqual({row[2] for row in rows}, {'main', 'gayrat', 'unknown'})
        self.assertTrue(all(row[0] == '901234567' and row[1] == 'ielts' for row in rows))

    def test_unknown_ids_are_rejected(self):
        response = self.client.post('/register', data={
            'student_name': 'Ali Valiyev',
            'student_phone': '901234567',
            'course': 'invented',
            'preferred_branch': 'historical',
        })
        self.assertEqual(response.status_code, 422)

    def test_success_state(self):
        html = self.client.get('/register?success=1').get_data(as_text=True)
        self.assertIn('Arizangiz qabul qilindi!', html)
        self.assertIn('data-registration-success', html)

    def test_static_build_uses_same_origin_registration_endpoint(self):
        from scripts import build_firebase

        rendered = '<form action="/register" method="post"></form>'
        result = build_firebase.make_form_static(
            rendered,
            '/register',
            '998701060404',
            'https://preview.pages.dev',
            'public-site-key',
        )
        self.assertIn('action="/api/register"', result)
        self.assertNotIn('preview.pages.dev/api/register', result)


if __name__ == '__main__':
    unittest.main()

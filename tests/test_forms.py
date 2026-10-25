import re
import unittest

import app as app_module


FORMS = (('/register', 'register'), ('/admissions', 'school-enquiry'))


class LeadFormTests(unittest.TestCase):
    """Both forms post to the Cloudflare /api/register function; forms.js validates and sends them."""

    def setUp(self):
        self.client = app_module.app.test_client()

    def form(self, path):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'<form [^>]*>.*?</form>', html, re.S).group(0), html

    def test_forms_post_to_the_pages_function_in_every_language(self):
        for path, kind in FORMS:
            for prefix in ('', '/ru', '/en'):
                with self.subTest(path=prefix + path):
                    form, html = self.form(prefix + path)
                    self.assertIn('action="/api/register" method="post"', form)
                    self.assertIn(f'data-static-lead-form="{kind}"', form)
                    self.assertIn(f'data-turnstile-sitekey="{app_module.TURNSTILE_SITE_KEY}"', form)
                    self.assertTrue(app_module.TURNSTILE_SITE_KEY)
                    self.assertIn('novalidate', form)
                    self.assertIn('name="website"', form)  # honeypot
                    self.assertIn('/static/js/forms.js?v=', html)

    def test_course_form_has_only_four_visible_data_fields(self):
        form, html = self.form('/register')
        for name in ('student_name', 'student_phone', 'course', 'preferred_branch'):
            self.assertIn(f'name="{name}"', form)
        for forbidden in ('parent_phone', 'email', 'dob', 'preferred_schedule', 'message'):
            self.assertNotIn(f'name="{forbidden}"', form)
        for program in app_module.REGISTRATION_CONFIG['programs']:
            self.assertIn(f'<option value="{program["id"]}">', form)
        self.assertIn('data-registration-success hidden', html)
        self.assertIn('https://t.me/iceberg_qabulxona', html)

    def test_school_form_fields_and_thank_you_page(self):
        form, _html = self.form('/admissions')
        for name in ('parent_name', 'parent_phone', 'child_name', 'child_birth_date', 'grade', 'language', 'message', 'consent'):
            self.assertIn(f'name="{name}"', form)
        self.assertIn('data-thanks-url="/admissions/thanks"', form)
        self.assertIn('data-thanks-url="/ru/admissions/thanks"', self.form('/ru/admissions')[0])

    def test_forms_script_reads_campaign_and_course_from_the_address(self):
        with open('static/js/forms.js', encoding='utf-8') as file:
            script = file.read()
        self.assertEqual(script.count('utm("utm_source")'), 2)
        self.assertIn('params.get("program")', script)
        self.assertNotIn('reportValidity', script)


if __name__ == '__main__':
    unittest.main()

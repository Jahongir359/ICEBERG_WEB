import json
import re
import unittest

import app as app_module


def read(path):
    with open(path, encoding='utf-8') as file:
        return file.read()

PUBLIC_PAGES = ['/', '/about', '/programs', '/admissions', '/courses', '/news', '/contact', '/register']



class SitePageTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def static_status(self, path):
        response = self.client.get(path)
        response.close()
        return response.status_code

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

    def test_no_page_shows_placeholders(self):
        # Owner decision 2026-10-25: missing facts are hidden or reworded, never shown as [PLACEHOLDER].
        for path in PUBLIC_PAGES + ['/hamkorlik', '/en/partners', '/ru/partners']:
            with self.subTest(path=path):
                self.assertNotIn('class="ph"', self.client.get(path).get_data(as_text=True))
        admissions = self.client.get('/admissions').get_data(as_text=True)
        self.assertIn(f'href="tel:{app_module.SCHOOL_CONFIG["phone"]}"', admissions)

    def test_language_switcher_is_not_machine_translated(self):
        html = self.client.get('/').get_data(as_text=True)
        # Real translated pages replace the old Google Translate widget.
        self.assertIn('<option value="/ru/" lang="ru">RU</option>', html)
        self.assertIn('<option value="/en/" lang="en">EN</option>', html)
        self.assertNotIn('translate.google.com', html)
        self.assertNotIn('translate.google.com', read('static/js/site.js'))

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
            self.assertEqual(self.static_status(href), 200)
        blocks = [json.loads(block) for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        website = [block for block in blocks if block['@type'] == 'WebSite']
        self.assertEqual(website[0]['name'], 'Iceberg School')
        self.assertEqual(website[0]['url'], 'https://iceberglc.com/')
        about = self.client.get('/about').get_data(as_text=True)
        self.assertNotIn('"WebSite"', about)

    def test_news_from_config_reaches_the_static_site(self):
        post = json.loads(read('config/news.json'))['posts'][0]
        news = self.client.get('/news').get_data(as_text=True)
        self.assertIn('news-card lift rv featured', news)
        self.assertIn(post['title'], news)
        self.assertIn(f'<a class="media poster" href="/static/{post["image"]}"', news)
        self.assertIn('Kattalashtirish', news)
        self.assertEqual(self.static_status(f'/static/{post["image"]}'), 200)
        self.assertIn(post['excerpt'], self.client.get('/').get_data(as_text=True))

    def test_school_location_from_the_owner_pin(self):
        school = app_module.SCHOOL_CONFIG
        contact = self.client.get('/contact').get_data(as_text=True)
        news = self.client.get('/news').get_data(as_text=True)
        for html in (contact, news):
            self.assertIn(f'href="{school["map_url"]}"', html.replace('&amp;', '&'))
            self.assertIn('Yandex Maps', html)
        self.assertNotIn('[MANZIL]', contact)
        self.assertIn('href="mailto:support@iceberglc.com"', contact)
        self.assertNotIn('gmail.com', contact)
        self.assertNotIn('[ISH VAQTI]', contact)
        self.assertIn(school['hours'], contact)
        self.assertIn('@iceberg_school', contact)
        self.assertIn('@Iceberg_Study_Center', contact)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', contact, re.S).group(1))
        self.assertEqual(data['geo']['latitude'], float(school['latitude']))
        self.assertEqual(data['address']['addressLocality'], 'Uychi')
        self.assertEqual(data['address']['streetAddress'], school['address'])
        self.assertEqual(data['telephone'], school['phone'])
        self.assertEqual(data['email'], 'support@iceberglc.com')

    def test_partnership_pages_in_uzbek_and_english(self):
        for path, lang, heading in (('/hamkorlik', 'uz', 'Keling, birga quramiz'), ('/en/partners', 'en', 'build something together')):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}" data-brand="school">', html)
                self.assertEqual(len(re.findall(r'<h1[\s>]', html)), 1)
                self.assertIn(heading, html)
                self.assertIn(f'<link rel="canonical" href="https://iceberglc.com{path}">', html)
                self.assertIn('hreflang="uz" href="https://iceberglc.com/hamkorlik"', html)
                self.assertIn('hreflang="en" href="https://iceberglc.com/en/partners"', html)
                self.assertIn(f'href="tel:{app_module.SCHOOL_CONFIG["phone"]}"', html)
        partners = self.client.get('/en/partners').get_data(as_text=True)
        self.assertNotIn('class="ph"', partners)
        self.assertNotIn('class="ph"', self.client.get('/hamkorlik').get_data(as_text=True))
        self.assertIn('>1500+</strong>', partners)
        self.assertIn('>65+</strong>', partners)
        self.assertIn('href="mailto:international@iceberglc.com"', partners)
        for item in ('Korean', 'Chinese', 'Physics', 'Uzbek language and literature'):
            self.assertIn(f'<li>{item}</li>', partners)
        programs = self.client.get('/programs').get_data(as_text=True)
        for subject in app_module.SCHOOL_CONFIG['subjects']:
            self.assertIn(f'<li>{subject}</li>'.replace("'", '&#39;'), programs)
        sitemap = self.client.get('/sitemap.xml').get_data(as_text=True)
        self.assertIn('https://iceberglc.com/hamkorlik', sitemap)
        self.assertIn('https://iceberglc.com/en/partners', sitemap)
        self.assertIn('href="/hamkorlik"', self.client.get('/').get_data(as_text=True))

    def test_owner_facts_round_two(self):
        school = app_module.SCHOOL_CONFIG
        about = self.client.get('/about').get_data(as_text=True)
        self.assertIn('<blockquote>', about)
        self.assertIn('Maktabimizga xush kelibsiz', about)
        self.assertIn('Direktor · Iceberg School va Iceberg Courses', about)
        self.assertNotIn('Markaz direktori', about)
        for text in ('Azizbek Nasriddinov', 'Direktor', 'Jahongir Karimov', 'Islomjon Ergashboyev', 'Hammuassis'):
            self.assertIn(text, about)
        partners = self.client.get('/en/partners').get_data(as_text=True)
        for text in ('Azizbek Nasriddinov', 'Director · Iceberg School and Iceberg Courses', 'Jahongir Karimov', 'Islomjon Ergashboyev', 'Co-founder', 'Uzbek and Russian',
                     'href="https://t.me/iceberg_school"', 'href="https://www.instagram.com/iceberg_maktab"'):
            self.assertIn(text, partners)
        home = self.client.get('/').get_data(as_text=True)
        self.assertIn("2026–2027 va 2027–2028 o&#39;quv yillari uchun qabul ochiq", home)
        self.assertIn(f'<li><a href="tel:{school["phone"]}">{school["phone_display"]}</a></li>', home)
        self.assertIn('href="https://www.instagram.com/iceberg_maktab" aria-label="Instagram"', home)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', home, re.S).group(1))
        self.assertEqual(data['openingHours'], 'Mo-Sa 07:00-19:00')
        self.assertEqual([person['name'] for person in data['founder']], ['Jahongir Karimov', 'Islomjon Ergashboyev'])
        self.assertEqual(set(data['sameAs']), {school['instagram_url'], school['telegram_url']})
        admissions = self.client.get('/admissions').get_data(as_text=True)
        self.assertIn("o&#39;zbek va rus tillarida", admissions)
        self.assertIn('Maktab avtobusi bor', admissions)
        self.assertIn('Du–Sha, 7:00–19:00', admissions)
        courses = self.client.get('/courses').get_data(as_text=True)
        self.assertIn('href="https://www.instagram.com/Iceberg_Study_Center"', courses)
        self.assertIn('href="https://t.me/iceberg_qabulxona"', courses)

    def test_every_page_in_russian_and_english(self):
        app_module.MISSING_TRANSLATIONS.clear()
        for endpoint, (uz_path, other_path) in app_module.LOCALIZED_ROUTES.items():
            for lang in ('ru', 'en'):
                path = f'/{lang}{other_path}' if other_path != '/' else f'/{lang}/'
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertIn(f'<html lang="{lang}" data-brand="school">', html)
                    self.assertEqual(len(re.findall(r'<h1[\s>]', html)), 1)
                    self.assertIn(f'<link rel="canonical" href="https://iceberglc.com{path}">', html)
                    self.assertIn(f'hreflang="uz" href="https://iceberglc.com{uz_path}"', html)
                    # links stay in the page's language (the language switcher is the one exception)
                    self.assertIn(f'href="/{lang}/courses"', html)
                    links = re.sub(r'<a href="[^"]*" hreflang="\w+"|<option value="[^"]*"', '', html)
                    self.assertNotIn('href="/courses"', links)
        self.assertEqual(app_module.MISSING_TRANSLATIONS, set())

    def test_translations_keep_placeholders_and_markup(self):
        for lang, table in app_module.TRANSLATIONS.items():
            for source, text in table.items():
                with self.subTest(lang=lang, source=source):
                    self.assertTrue(text.strip())
                    self.assertEqual(set(re.findall(r'\{\w+\}', source)), set(re.findall(r'\{\w+\}', text)))
                    self.assertEqual(source.count('<span'), text.count('<span'))

    def test_translated_pages_read_in_their_language(self):
        ru = self.client.get('/ru/').get_data(as_text=True)
        en = self.client.get('/en/').get_data(as_text=True)
        self.assertIn('Прочный фундамент', ru)
        self.assertIn('strong foundation', en)
        for html in (ru, en):
            self.assertNotIn('Ariza topshirish', html)
            self.assertNotIn('Maktab haqida', html)
        self.assertIn('Ваша заявка принята', self.client.get('/ru/register').get_data(as_text=True))
        admissions = self.client.get('/en/admissions').get_data(as_text=True)
        self.assertIn('data-thanks-url="/en/admissions/thanks"', admissions)
        self.assertIn('<option value="en" selected>English</option>', admissions)

    def test_old_english_urls_reach_the_english_pages(self):
        for old, new in (('/partners', '/en/partners'), ('/en/our_programs', '/en/courses')):
            with self.subTest(old=old):
                response = self.client.get(old)
                self.assertEqual(response.status_code, 301)
                self.assertTrue(response.location.endswith(new))
        self.assertFalse([source for source, _t, _c in app_module.LEGACY_REDIRECTS if source in ('/en', '/en/*')])

    def test_korean_and_chinese_courses(self):
        courses = self.client.get('/courses').get_data(as_text=True)
        for program in ('korean', 'chinese'):
            self.assertIn(f'id="{program}"', courses)
            self.assertIn(f'value="{program}"', self.client.get('/register').get_data(as_text=True))
        self.assertIn('7 yoshdan boshlab', courses)
        self.assertIn('Korean', self.client.get('/en/courses').get_data(as_text=True))

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

    def test_old_admin_panel_is_gone(self):
        for path in ('/admin', '/admin/login', '/portal', '/students', '/contacts_list', '/admin/news'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.post('/register').status_code, 405)

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


if __name__ == '__main__':
    unittest.main()

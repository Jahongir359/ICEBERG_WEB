"""Reviewed public copy. Unknown institutional facts are deliberately omitted."""

NAVIGATION = [
    ('/', 'Bosh sahifa', 'Home'), ('/about', 'Iceberg haqida', 'About'),
    ('/our_programs', 'Dasturlar', 'Programs'), ('/results', 'Natijalar', 'Results'),
    ('/student-life', 'Markaz hayoti', 'Student life'),
    ('/international', 'Xalqaro hamkorlik', 'International'),
    ('/private-school', 'Xususiy maktab', 'Private school'),
    ('/news', 'Yangiliklar', 'News & events'),
    ('/admissions', 'Qabul va narxlar', 'Admissions & fees'),
    ('/contact', 'Aloqa', 'Contact'), ('/questions', 'Savollar', 'FAQ'),
    ('/privacy', 'Maxfiylik', 'Privacy'),
]

EXPORT_CONTENT_KEYS = {'hero_main_title', 'hero_main_subtitle', 'contact_email'}

# Each section is a title and paragraph. Both languages share the same facts.
PAGES = {
    'about': {
        'uz': ('Iceberg haqida', "Namangan viloyatidagi o'quv markazi: til, imtihon va akademik tayyorgarlik.", [
            ('Bizning faoliyatimiz', "ICEBERG ingliz tili, IELTS, SAT, matematika, kimyo va biologiya yo'nalishlarida ta'lim dasturlarini taklif qiladi. Maqsadimiz — mustahkam bilim, muntazam mashq va individual yordam orqali o'quvchini rivojlantirish."),
            ('Ta’limga yondashuv', "Nazariya va amaliyot, darajaga mos mashqlar, test tayyorgarligi va fikr-mulohaza. Kursni tanlashda maqsadingiz, mavjud darajangiz va qulay jadvalingizni qabul jamoasi bilan muhokama qiling."),
            ('Filiallar', "Qabul tizimida Asosiy va G'ayrat filiallari mavjud. G'ayrat filiali: oilaviy poliklinika yonidagi binoning 2-qavati. Tashrifdan oldin aniq manzil, dars mavjudligi va ish vaqtini tasdiqlang."),
            ('Kelajakdagi maktab', "ICEBERG xususiy maktabi — alohida loyiha. Ochilish 2027-yil sentabrga rejalashtirilgan; amaldagi o'quv markazi bilan bir xil faoliyat deb qaralmaydi."),
        ]),
        'en': ('About Iceberg', 'A learning center in Namangan region, Uzbekistan, focused on language, test preparation, and academic study.', [
            ('Educational activities', 'ICEBERG offers English, IELTS, SAT, mathematics, chemistry, and biology programs. Our aim is to help students build strong foundations through regular practice and individual support.'),
            ('Teaching approach', 'Theory and practice, level-appropriate exercises, test preparation, and feedback guide learning. Discuss your goals, current level, and preferred schedule with admissions before choosing a course.'),
            ('Campuses', 'Admissions currently lists the Main and G’ayrat branches. The G’ayrat branch is on the second floor of the building beside the family polyclinic. Confirm the precise location, available classes, and visiting hours before travel.'),
            ('Future school project', 'The ICEBERG private school is a separate project with an opening planned for September 2027. It is distinct from the operating learning center.'),
        ]),
    },
    'international': {
        'uz': ('Xalqaro hamkorlik', 'Ta’lim va madaniy muloqot bo‘yicha hamkorlik takliflari.', [
            ('Iceberg bilan tanishing', "ICEBERG — Namangan viloyati, O'zbekistondagi o'quv markazi. Ingliz tili, IELTS, SAT va akademik fanlar bo'yicha dasturlarimiz bor. Universitetlar uchun institutsional ma'lumot va hujjatlarni so'rov asosida taqdim etish imkoniyatini muhokama qilamiz."),
            ('Hamkorlik imkoniyatlari', "Mehmon ma'ruzalari, madaniy muloqot, o'qituvchilar malakasini oshirish va universitetlar haqida axborot uchrashuvlarini muhokama qilishga ochiqmiz. Yaponiya va boshqa mamlakatlardagi ta'lim tashkilotlari bilan suhbatni boshlashni istaymiz. Bular taklif etilayotgan yo'nalishlar, amaldagi kelishuvlar emas."),
            ('Xalqaro faoliyat', "Tasdiqlangan xalqaro tadbirlar haqida sana, mazmun va natijalar bilan ma'lumot shu yerda e'lon qilinadi. Hozircha bu sahifada bajarilgan xalqaro tadbir yoki imzolangan hamkorlik e'lon qilinmagan."),
            ('Hamkorlik uchun aloqa', "Hamkorlik taklifingizda tashkilotingiz, mamlakatingiz, maqsadingiz va taxminiy muddatni ko'rsating. Hozircha umumiy aloqa emailidan foydalaning va xat mavzusiga ‘International cooperation’ yozing."),
        ]),
        'en': ('International cooperation', 'An invitation to discuss educational and cultural cooperation.', [
            ('About Iceberg', 'ICEBERG is a learning center in Namangan region, Uzbekistan. Our programs cover English, IELTS, SAT, and academic subjects. Universities can contact us to discuss institutional information and supporting documentation.'),
            ('Partnership opportunities', 'We welcome discussions about guest lectures, cultural exchange, teacher development, and university information sessions, including with educational institutions in Japan. These are proposed areas of cooperation; they do not represent signed agreements or operational exchange programs.'),
            ('International activities', 'Verified activities will be reported here with dates, descriptions, and outcomes. No completed international activity or signed institutional partnership is currently published on this page.'),
            ('Contact for cooperation', 'Please include your institution, country, proposed activity, and preferred dates. Use our general contact email for now with “International cooperation” in the subject line.'),
        ]),
    },
    'private-school': {
        'uz': ('Iceberg xususiy maktabi', 'Ochilish 2027-yil sentabrga rejalashtirilgan.', [
            ('Loyiha holati', "Xususiy maktab — rejalashtirilayotgan loyiha, amaldagi o'quv markazidan alohida. Bu sahifa maktab ochilganini yoki maktabga qabul boshlanganini anglatmaydi."),
            ('Keyingi yangiliklar', "Sinf bosqichlari, o'quv dasturi, manzil, sharoitlar, to'lov va qabul muddatlari tasdiqlangach e'lon qilinadi. Rejalashtirilgan ochilish sanasi o'zgarishi mumkin."),
            ('Ma’lumot so‘rash', "Loyiha haqida savollaringizni qabul jamoasiga yuboring. O'quv markazi kurslariga yozilish maktabga ariza topshirish yoki joy band qilish hisoblanmaydi."),
        ]),
        'en': ('Iceberg Private School', 'Opening planned for September 2027.', [
            ('Project status', 'The private school is a planned project, separate from the operating learning center. This page does not indicate that the school is open or accepting enrollment.'),
            ('Future announcements', 'Grade levels, curriculum, location, facilities, fees, and admission dates will be published when confirmed. The planned opening date may change.'),
            ('Ask about the project', 'Contact admissions with questions about the project. Registering for a learning-center course does not constitute a school application or reserve a school place.'),
        ]),
    },
    'admissions': {
        'uz': ('Qabul va narxlar', 'Kursni tanlang, shartlarni aniqlang va ariza yuboring.', [
            ('1. Kurs va filialni tanlang', "IELTS, ingliz tili, SAT, matematika, kimyo yoki biologiya yo'nalishlarini ko'rib chiqing. Qaysi filial kerakligini bilmasangiz, arizada shu variantni tanlashingiz mumkin."),
            ('2. Tafsilot va to‘lovni so‘rang', "Yosh va daraja talabi, davomiylik, haftalik jadval, dars uzunligi, guruh hajmi, o'qituvchi, to'lov davri va jami narxni qabul jamoasidan aniqlang. Narxlar tasdiqlanmagani uchun saytda summa ko'rsatilmagan."),
            ('3. Bog‘lanish uchun ariza yuboring', "Arizada ism, telefon, dastur va filial so'raladi. Bu bog'lanish so'rovi; to'lov yoki o'qishga qabul kafolati emas. Jamoa bilan kelishgach kursni boshlash tartibini aniqlang."),
            ('Ota-onalar uchun', "Voyaga yetmagan o'quvchi uchun ota-ona yoki vasiy bilan maslahatlashib ariza yuboring. Sog'liq, pasport yoki boshqa maxfiy hujjatlarni oddiy xabar maydoniga yozmang."),
        ]),
        'en': ('Admissions & fees', 'Choose a course, confirm the details, and request a consultation.', [
            ('1. Choose your course and branch', 'Explore IELTS, English, SAT, mathematics, chemistry, or biology. If you are unsure which branch to choose, select “I do not know the branch” in the application.'),
            ('2. Request course details and fees', 'Ask admissions about age and entry-level requirements, duration, weekly timetable, lesson length, class size, teacher, payment period, and total fees. No amounts are published until confirmed.'),
            ('3. Send a contact request', 'The application asks for a name, phone number, program, and branch. It is a request to be contacted, not a payment or guarantee of admission. Agree the enrollment steps with our team before starting.'),
            ('For parents', 'For a child, discuss the application with a parent or guardian. Do not send health information, passport details, or other sensitive documents through a general message.'),
        ]),
    },
    'results': {
        'uz': ('O‘quvchi natijalari', 'Ishonchli natija — tekshiriladigan ma’lumot.', [
            ('Natijalarni baholash', "Imtihon ballari yoki universitetga qabul haqida maslahat olayotganda sana, tayyorgarlik davri va tasdiqlovchi ma'lumotni so'rang. Natija boshlang'ich daraja va muntazam mashqqa ham bog'liq."),
            ('Natijalar to‘plami', "Tekshirilgan va e'lon qilishga ruxsat berilgan o'quvchi hikoyalari shu sahifaga qo'shiladi. Hozircha tasdiqlanmagan raqam yoki anonim ball da'volari e'lon qilinmaydi."),
        ]),
        'en': ('Student results', 'Educational outcomes should be supported by evidence.', [
            ('Understanding outcomes', 'When discussing exam scores or university admission, ask about dates, the preparation period, and supporting evidence. Outcomes also depend on a student’s starting level and consistent practice.'),
            ('Student stories', 'Verified student stories with permission to publish will be added here. Unverified totals and anonymous score claims are not published.'),
        ]),
    },
    'student-life': {
        'uz': ('Markaz hayoti', 'Darslar, muhit va faoliyat haqida bilib oling.', [
            ('Markazga tashrif', "Dars muhiti va sharoitlarni o'zingiz ko'rish uchun qabul jamoasi bilan tashrifni kelishing. Filial manzili va ish vaqtini oldindan aniqlang."),
            ('Foto va tadbirlar', "Haqiqiy kampus suratlari va o'quvchi loyihalari ruxsat bilan e'lon qilinadi. Ta'lim tadbirlari uchun Yangiliklar sahifasini ko'ring."),
        ]),
        'en': ('Life at Iceberg', 'Learn about the teaching environment and activities.', [
            ('Arrange a visit', 'Contact admissions to arrange a visit and see the learning environment. Confirm the branch address and opening hours beforehand.'),
            ('Photos and activities', 'Original campus photographs and student projects will be published with permission. Visit News & events for educational updates.'),
        ]),
    },
    'privacy': {
        'uz': ('Maxfiylik haqida', 'Ariza va aloqa ma’lumotlari qanday ishlatiladi.', [
            ('Yig‘iladigan ma’lumot', "Kurs arizasi ism, telefon, tanlangan dastur va filialni oladi. Havoladagi kampaniya belgilari va sahifa manzili ariza manbasini aniqlash uchun yuborilishi mumkin. Aloqa formasida ism, telefon va xabar mazmunidan Telegram uchun xabar loyihasi tuziladi. Uni yuborish sizning Telegram ilovangizda davom etadi."),
            ('Maqsad va xizmatlar', "Ma'lumotlar so'rovga javob berish va arizani boshqarish uchun ishlatiladi. Saytning joylashtirilgan turiga qarab ariza markaz bazasida yoki Google Sheets orqali saqlanishi, sozlangan boshqaruv tizimiga va Telegram orqali mas'ul xodimlarga yuborilishi mumkin. Spamdan himoya uchun Cloudflare Turnstile so'rov ma'lumotlarini qayta ishlaydi."),
            ('Aloqa kanallari', "Telegram havolasini ochsangiz, xabarni yuborish o'sha xizmatda davom etadi va xizmatning maxfiylik shartlari qo'llanadi. Tashqi xarita va ijtimoiy tarmoq havolalari ham tegishli xizmatlarga olib boradi."),
            ('Bolalar ma’lumotlari', "Voyaga yetmaganlar uchun ota-ona yoki vasiy yordamida bog'laning. Arizaga pasport, sog'liq yoki boshqa ortiqcha maxfiy ma'lumotlarni kiritmang."),
            ('Saqlash va murojaat', "Ma'lumotlar saqlanish muddati haqida ma'lumot olish, tuzatish yoki o'chirishni so'rash uchun markaz emailiga murojaat qiling. So'rovni topish uchun yuborgan sana va aloqa raqamingizni ko'rsating; maxfiy hujjat yubormang."),
        ]),
        'en': ('Privacy notice', 'How course applications and inquiries are handled.', [
            ('Information collected', 'Course applications collect a name, phone number, selected program, and branch. Campaign tags from a link and the page URL may be submitted to identify the source of an application. The contact form prepares a Telegram draft from your name, phone number, and message. You choose whether to send it in Telegram.'),
            ('Purpose and services', 'Information is used to respond to inquiries and manage applications. Depending on the deployment, applications may be stored in the center’s database or through Google Sheets, forwarded to a configured management service, and sent to responsible staff through Telegram. Cloudflare Turnstile processes request information for spam protection.'),
            ('Contact channels', 'When you open a Telegram link, sending continues in that service and its privacy terms apply. External map and social links also lead to third-party services.'),
            ('Children’s information', 'A parent or guardian should help with inquiries for a child. Do not include passport details, health information, or unnecessary sensitive information.'),
            ('Retention and requests', 'Contact the center by email to ask about retention or request correction or deletion. Include the submission date and your contact number to help locate the request; do not send sensitive documents.'),
        ]),
    },
    'questions': {
        'uz': ('Savollar', 'Kursni tanlashdan oldin bilishingiz kerak bo‘lgan ma’lumotlar.', []),
        'en': ('Frequently asked questions', 'Practical answers before you apply.', [
            ('How do I find the right course?', 'Discuss your goal and starting level with admissions. Ask for the course requirements and a suitable timetable.'),
            ('How much does a course cost?', 'Request current tuition, payment frequency, and any additional charges from admissions before enrolling.'),
            ('Does an application reserve a place?', 'No. It requests contact from our team. Availability and enrollment terms must be confirmed.'),
            ('Is the private school open?', 'The private school is a separate project with an opening planned for September 2027. It is not currently presented as an operating school.'),
        ]),
    },
}

COURSE_COPY = {
    'ielts': ('IELTS', 'IELTS', "Reading, listening, writing va speaking bo'yicha imtihon tayyorgarligi, mock test va fikr-mulohaza.", 'Exam preparation across reading, listening, writing, and speaking, with mock tests and feedback.'),
    'english': ('CEFR / Ingliz tili', 'CEFR / English', "Grammatika, lug'at, talaffuz va kundalik muloqotni mustahkamlash.", 'Build grammar, vocabulary, pronunciation, and everyday communication.'),
    'sat': ('SAT', 'SAT', 'SAT imtihoniga tayyorgarlik, masala yechish va test strategiyalari.', 'Prepare for the SAT through problem solving and test strategies.'),
    'mathematics': ('Matematika', 'Mathematics', 'Matematik bilimlarni mustahkamlash va masalalar ustida ishlash.', 'Strengthen mathematical foundations through guided problem solving.'),
    'chemistry': ('Kimyo', 'Chemistry', 'Kimyo tushunchalari va o‘quv masalalarini tizimli o‘rganish.', 'Study chemistry concepts and work through academic exercises.'),
    'biology': ('Biologiya', 'Biology', 'Biologiya mavzularini o‘rganish va bilimlarni mashqlar bilan mustahkamlash.', 'Explore biology topics and reinforce understanding through exercises.'),
}

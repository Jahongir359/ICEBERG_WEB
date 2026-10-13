import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

test('Telegram draft goes to the admissions chat and preserves Unicode and punctuation', () => {
    let destination;
    let onSubmit;
    const values = { name: 'Ali & O‘g‘li', phone: '901234567', message: 'IELTS narxi? 日本語 #test' };
    const form = {
        action: 'https://t.me/iceberg_qabulxona',
        elements: { namedItem: name => ({ value: values[name] || '' }) },
        getAttribute: () => 'contact',
        reportValidity: () => true,
        addEventListener: (_event, callback) => { onSubmit = callback; },
    };
    const document = {
        documentElement: { lang: 'uz' },
        addEventListener: (_event, callback) => callback(),
        querySelectorAll: selector => selector.includes('data-static-lead-form') ? [form] : [],
    };
    vm.runInNewContext(readFileSync(new URL('../static/js/firebase-forms.js', import.meta.url), 'utf8'), {
        document, window: { location: { assign: value => { destination = value; } } }, URL,
    });
    onSubmit({ preventDefault() {} });
    const link = new URL(destination);
    assert.equal(link.hostname, 't.me');
    assert.equal(link.pathname, '/iceberg_qabulxona');
    assert.ok(link.searchParams.get('text').includes(values.name));
    assert.ok(link.searchParams.get('text').includes(values.message));
    assert.equal(link.hash, '');
});

test('Turnstile uses a supported language for Uzbek and English pages', () => {
    for (const language of ['uz', 'en']) {
        const children = [];
        const form = {
            getAttribute: name => name === 'data-turnstile-sitekey' ? 'test-key' : 'register',
            querySelector: () => null,
            appendChild: element => children.push(element),
            addEventListener() {},
        };
        const document = {
            documentElement: { lang: language },
            addEventListener: (_event, callback) => callback(),
            querySelectorAll: selector => selector.includes('data-static-lead-form') ? [form] : [],
            querySelector: () => ({}),
            createElement: () => ({ attributes: {}, style: {}, setAttribute(key, value) { this.attributes[key] = value; } }),
        };
        vm.runInNewContext(readFileSync(new URL('../static/js/firebase-forms.js', import.meta.url), 'utf8'), { document });
        assert.equal(children[0].attributes['data-language'], language === 'en' ? 'en' : 'auto');
    }
});

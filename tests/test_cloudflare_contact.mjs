import assert from 'node:assert/strict';
import test from 'node:test';
import { onRequest, onRequestPost } from '../functions/api/contact.js';


function environment(overrides = {}) {
    return {
        GOOGLE_SCRIPT_URL: 'https://script.google.com/macros/s/test-deployment/exec',
        GOOGLE_SCRIPT_SECRET: 'test-secret',
        TURNSTILE_SECRET_KEY: 'turnstile-secret',
        ...overrides
    };
}

function request(overrides = {}) {
    return new Request('https://iceberglc.com/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.10' },
        body: JSON.stringify({
            submission_id: 'abcdefab-1234-4234-8234-123456789012',
            name: 'Ali Valiyev',
            phone: '90 123 45 67',
            message: 'Salom,\nkurslar haqida savolim bor.',
            turnstile_token: 'valid-token',
            ...overrides
        })
    });
}

function mockNetwork({ turnstileSuccess = true, action = 'contact', backendSuccess = true } = {}) {
    const forwarded = [];
    globalThis.fetch = async (url, options) => {
        if (String(url).includes('turnstile')) {
            return new Response(JSON.stringify({ success: turnstileSuccess, action }));
        }
        forwarded.push(JSON.parse(options.body));
        return new Response(JSON.stringify({ ok: backendSuccess }), {
            status: backendSuccess ? 200 : 500
        });
    };
    return forwarded;
}

test('forwards a valid contact message to the receiver as type contact', async () => {
    const forwarded = mockNetwork();
    const response = await onRequestPost({ request: request(), env: environment() });
    assert.equal(response.status, 201);
    assert.equal(forwarded.length, 1);
    assert.equal(forwarded[0].type, 'contact');
    assert.equal(forwarded[0].secret, 'test-secret');
    assert.equal(forwarded[0].phone, '+998901234567');
    assert.equal(forwarded[0].message, 'Salom,\nkurslar haqida savolim bor.');
    assert.equal(forwarded[0].id, 'abcdefab-1234-4234-8234-123456789012');
});

test('rejects invalid name, phone, or empty message', async () => {
    const forwarded = mockNetwork();
    for (const override of [{ name: 'A' }, { phone: '123' }, { message: '' }]) {
        const response = await onRequestPost({ request: request(override), env: environment() });
        assert.equal(response.status, 422);
    }
    assert.equal(forwarded.length, 0);
});

test('rejects failed Turnstile and tokens issued for another form', async () => {
    mockNetwork({ turnstileSuccess: false });
    assert.equal((await onRequestPost({ request: request(), env: environment() })).status, 403);
    mockNetwork({ action: 'register' });
    assert.equal((await onRequestPost({ request: request(), env: environment() })).status, 403);
});

test('honeypot submissions are silently accepted and not forwarded', async () => {
    const forwarded = mockNetwork();
    const response = await onRequestPost({ request: request({ website: 'spam' }), env: environment() });
    assert.equal(response.status, 200);
    assert.equal(forwarded.length, 0);
});

test('reports missing configuration and receiver failures', async () => {
    mockNetwork();
    const missing = await onRequestPost({ request: request(), env: environment({ GOOGLE_SCRIPT_SECRET: '' }) });
    assert.equal(missing.status, 503);
    mockNetwork({ backendSuccess: false });
    const failed = await onRequestPost({ request: request(), env: environment() });
    assert.equal(failed.status, 502);
});

test('only POST is allowed', async () => {
    const response = await onRequest({ request: new Request('https://iceberglc.com/api/contact'), env: environment() });
    assert.equal(response.status, 405);
});

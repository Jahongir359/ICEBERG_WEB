import assert from 'node:assert/strict';
import test from 'node:test';
import { onRequestPost } from '../functions/api/register.js';
import registration from '../config/registration.json' with { type: 'json' };


function environment() {
    return {
        GOOGLE_SCRIPT_URL: 'https://script.example/exec',
        GOOGLE_SCRIPT_SECRET: 'test-secret',
        TURNSTILE_SECRET_KEY: 'turnstile-secret',
        ASSETS: {
            fetch: async () => new Response(JSON.stringify(registration), {
                headers: { 'Content-Type': 'application/json' }
            })
        }
    };
}

function request(overrides = {}) {
    return new Request('https://iceberglc.com/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.10' },
        body: JSON.stringify({
            submission_id: '12345678-1234-4234-8234-123456789012',
            student_name: 'Ali Valiyev',
            student_phone: '901234567',
            program: 'ielts',
            branch: 'main',
            turnstile_token: 'valid-token',
            ...overrides
        })
    });
}

function mockNetwork({ turnstileSuccess = true, backendSuccess = true } = {}) {
    const leads = [];
    globalThis.fetch = async (url, options) => {
        if (String(url).includes('turnstile')) {
            return new Response(JSON.stringify({ success: turnstileSuccess, action: 'register' }), {
                headers: { 'Content-Type': 'application/json' }
            });
        }
        leads.push(JSON.parse(options.body));
        return new Response(JSON.stringify({ ok: backendSuccess }), {
            status: backendSuccess ? 200 : 500,
            headers: { 'Content-Type': 'application/json' }
        });
    };
    return leads;
}

test('accepts every active branch and forwards stable IDs', async () => {
    const leads = mockNetwork();
    for (const branch of ['main', 'gayrat', 'unknown']) {
        const response = await onRequestPost({ request: request({ branch }), env: environment() });
        assert.equal(response.status, 201);
    }
    assert.deepEqual(leads.map(lead => lead.branch), ['main', 'gayrat', 'unknown']);
    assert.ok(leads.every(lead => lead.program === 'ielts'));
});

test('rejects invalid phone, missing selections, and unknown IDs', async () => {
    mockNetwork();
    for (const override of [
        { student_phone: '123' },
        { program: '' },
        { branch: '' },
        { program: 'invented' },
        { branch: 'fayziobod' }
    ]) {
        const response = await onRequestPost({ request: request(override), env: environment() });
        assert.equal(response.status, 422);
    }
});

test('normalizes a full Uzbekistan phone number', async () => {
    const leads = mockNetwork();
    const response = await onRequestPost({
        request: request({ student_phone: '+998 90 123 45 67' }),
        env: environment()
    });
    assert.equal(response.status, 201);
    assert.equal(leads[0].student_phone, '+998901234567');
});

test('rejects failed Turnstile verification', async () => {
    mockNetwork({ turnstileSuccess: false });
    const response = await onRequestPost({ request: request(), env: environment() });
    assert.equal(response.status, 403);
});

test('reports a downstream backend failure', async () => {
    mockNetwork({ backendSuccess: false });
    const response = await onRequestPost({ request: request(), env: environment() });
    assert.equal(response.status, 502);
});

test('repeated client submission ID remains idempotent downstream', async () => {
    const leads = mockNetwork();
    await onRequestPost({ request: request(), env: environment() });
    await onRequestPost({ request: request(), env: environment() });
    assert.equal(leads.length, 2);
    assert.equal(leads[0].id, leads[1].id);
});

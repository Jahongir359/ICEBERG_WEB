import assert from 'node:assert/strict';
import test from 'node:test';
import { onRequest, onRequestPost } from '../functions/api/register.js';
import registration from '../config/registration.json' with { type: 'json' };


function environment() {
    return {
        GOOGLE_SCRIPT_URL: 'https://script.google.com/macros/s/test-deployment/exec',
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
    const result = await response.json();
    assert.match(result.message, /Xato kodi/);
    assert.ok(result.reference);
});

test('rejects an invalid Apps Script deployment URL before processing', async () => {
    mockNetwork();
    const env = environment();
    env.GOOGLE_SCRIPT_URL = 'https://example.com/not-an-apps-script';
    const response = await onRequestPost({ request: request(), env });
    assert.equal(response.status, 503);
});

test('returns JSON for an unexpected handler failure', async () => {
    mockNetwork();
    const env = environment();
    Object.defineProperty(env, 'GOOGLE_SCRIPT_SECRET', {
        get() { throw new Error('unexpected test failure'); }
    });
    const response = await onRequest({ request: request(), env });
    assert.equal(response.status, 500);
    assert.match(response.headers.get('content-type'), /application\/json/);
    const result = await response.json();
    assert.ok(result.reference);
});

test('repeated client submission ID remains idempotent downstream', async () => {
    const leads = mockNetwork();
    await onRequestPost({ request: request(), env: environment() });
    await onRequestPost({ request: request(), env: environment() });
    assert.equal(leads.length, 2);
    assert.equal(leads[0].id, leads[1].id);
});

const ERP_URL = 'https://app.iceberglc.com/public/registration-leads/';

function erpEnvironment(branchNames = {}) {
    const env = environment();
    const config = structuredClone(registration);
    for (const branch of config.branches) {
        branch.erp_branch_name = branchNames[branch.id] || '';
    }
    env.ASSETS = {
        fetch: async () => new Response(JSON.stringify(config), {
            headers: { 'Content-Type': 'application/json' }
        })
    };
    env.REGISTRATION_LEADS_API_URL = ERP_URL;
    env.REGISTRATION_LEADS_API_TOKEN = 'erp-token';
    return env;
}

function mockNetworkWithErp({ duplicate = false, erpStatus = 201, erpThrows = false } = {}) {
    const calls = { sheets: [], erp: [] };
    globalThis.fetch = async (url, options) => {
        if (String(url).includes('turnstile')) {
            return new Response(JSON.stringify({ success: true, action: 'register' }));
        }
        if (String(url) === ERP_URL) {
            calls.erp.push({ headers: options.headers, body: JSON.parse(options.body) });
            if (erpThrows) {
                throw new TypeError('network down');
            }
            return new Response(JSON.stringify({ status: 'ok', lead_id: 1 }), { status: erpStatus });
        }
        calls.sheets.push(JSON.parse(options.body));
        return new Response(JSON.stringify({ ok: true, duplicate }));
    };
    return calls;
}

test('does not contact the ERP unless both ERP secrets are set', async () => {
    const calls = mockNetworkWithErp();
    const env = erpEnvironment();
    delete env.REGISTRATION_LEADS_API_TOKEN;
    const response = await onRequestPost({ request: request(), env });
    assert.equal(response.status, 201);
    assert.equal(calls.sheets.length, 1);
    assert.equal(calls.erp.length, 0);
});

test('forwards a stored lead to the ERP with the configured branch name', async () => {
    const calls = mockNetworkWithErp();
    const response = await onRequestPost({
        request: request({ branch: 'gayrat', utm_source: 'instagram' }),
        env: erpEnvironment({ gayrat: "G'ayrat" })
    });
    assert.equal(response.status, 201);
    assert.equal(calls.erp.length, 1);
    assert.equal(calls.erp[0].headers.Authorization, 'Bearer erp-token');
    assert.deepEqual(
        {
            full_name: calls.erp[0].body.full_name,
            phone: calls.erp[0].body.phone,
            program: calls.erp[0].body.program,
            branch: calls.erp[0].body.branch,
            source: calls.erp[0].body.source,
            utm_source: calls.erp[0].body.utm_source
        },
        {
            full_name: 'Ali Valiyev',
            phone: '+998901234567',
            program: 'IELTS',
            branch: "G'ayrat",
            source: 'website',
            utm_source: 'instagram'
        }
    );
    assert.equal(JSON.stringify(calls.sheets[0]).includes('erp-token'), false);
});

test('falls back to the branch ID without a mapping and sends unknown as empty', async () => {
    const calls = mockNetworkWithErp();
    for (const branch of ['main', 'unknown']) {
        await onRequestPost({ request: request({ branch }), env: erpEnvironment() });
    }
    assert.deepEqual(calls.erp.map(call => call.body.branch), ['main', '']);
});

test('skips the ERP for a submission Sheets already stored', async () => {
    const calls = mockNetworkWithErp({ duplicate: true });
    const response = await onRequestPost({ request: request(), env: erpEnvironment() });
    assert.equal(response.status, 201);
    assert.equal(calls.erp.length, 0);
});

test('an ERP failure never fails the stored application', async () => {
    for (const failure of [{ erpStatus: 401 }, { erpStatus: 503 }, { erpThrows: true }]) {
        mockNetworkWithErp(failure);
        const response = await onRequestPost({ request: request(), env: erpEnvironment() });
        assert.equal(response.status, 201);
    }
});

test('rejects a non-HTTPS ERP URL without sending the token', async () => {
    const calls = mockNetworkWithErp();
    const env = erpEnvironment();
    env.REGISTRATION_LEADS_API_URL = 'http://app.iceberglc.com/public/registration-leads/';
    const response = await onRequestPost({ request: request(), env });
    assert.equal(response.status, 201);
    assert.equal(calls.erp.length, 0);
});

test('uses waitUntil so the visitor does not wait for the ERP', async () => {
    mockNetworkWithErp();
    const pending = [];
    const response = await onRequestPost({
        request: request(),
        env: erpEnvironment(),
        waitUntil: promise => pending.push(promise)
    });
    assert.equal(response.status, 201);
    assert.equal(pending.length, 1);
    await Promise.all(pending);
});

function schoolRequest(overrides = {}) {
    return new Request('https://iceberglc.com/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.10' },
        body: JSON.stringify({
            form_type: 'school-enquiry',
            submission_id: '22345678-1234-4234-8234-123456789012',
            parent_name: 'Dilnoza Karimova',
            parent_phone: '90 123 45 67',
            child_name: 'Aziz',
            child_birth_date: '2019-04-02',
            grade: '1',
            language: 'uz',
            message: 'Sport bilan shug\'ullanadi',
            consent: true,
            turnstile_token: 'valid-token',
            ...overrides
        })
    });
}

test('stores a school enquiry in Sheets with its own fields', async () => {
    const calls = mockNetworkWithErp();
    const env = environment();
    const response = await onRequestPost({ request: schoolRequest(), env });
    assert.equal(response.status, 201);
    const stored = calls.sheets[0];
    assert.equal(stored.form_type, 'school-enquiry');
    assert.equal(stored.student_name, 'Dilnoza Karimova');
    assert.equal(stored.student_phone, '+998901234567');
    assert.equal(stored.program, 'grade-1');
    assert.equal(stored.branch, 'school');
    assert.equal(stored.child_name, 'Aziz');
    assert.equal(stored.language, 'uz');
    assert.equal(calls.erp.length, 0);
});

test('forwards a school enquiry to the ERP as a school-website lead', async () => {
    const calls = mockNetworkWithErp();
    const env = erpEnvironment();
    env.SCHOOL_BRANCH_NAME = 'Iceberg School Namangan';
    const response = await onRequestPost({ request: schoolRequest({ grade: '7' }), env });
    assert.equal(response.status, 201);
    assert.equal(calls.erp.length, 1);
    const body = calls.erp[0].body;
    assert.equal(body.source, 'school-website');
    assert.equal(body.program, 'Grade 7');
    assert.equal(body.branch, 'Iceberg School Namangan');
    assert.equal(body.full_name, 'Dilnoza Karimova');
    assert.match(body.message, /Farzand: Aziz · Tug'ilgan sana: 2019-04-02 · Til: O'zbek/);
});

test('uses Iceberg School as the default ERP branch for enquiries', async () => {
    const calls = mockNetworkWithErp();
    await onRequestPost({ request: schoolRequest(), env: erpEnvironment() });
    assert.equal(calls.erp[0].body.branch, 'Iceberg School');
});

test('rejects invalid school enquiries before Turnstile and storage', async () => {
    const calls = mockNetworkWithErp();
    for (const override of [
        { parent_name: 'A' },
        { parent_phone: '123' },
        { grade: '12' },
        { grade: '' },
        { language: 'fr' },
        { child_birth_date: '2019-02-30' },
        { child_birth_date: '2999-01-01' },
        { consent: false },
        { consent: 'yes' }
    ]) {
        const response = await onRequestPost({ request: schoolRequest(override), env: environment() });
        assert.equal(response.status, 422, JSON.stringify(override));
    }
    assert.equal(calls.sheets.length, 0);
});

test('a filled honeypot on the school form stores nothing', async () => {
    const calls = mockNetworkWithErp();
    const response = await onRequestPost({ request: schoolRequest({ website: 'spam' }), env: environment() });
    assert.equal(response.status, 200);
    assert.equal(calls.sheets.length, 0);
});

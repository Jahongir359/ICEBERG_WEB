import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';


class Range {
    constructor(sheet, row, column, rows = 1, columns = 1) {
        this.sheet = sheet;
        this.row = row;
        this.column = column;
        this.rows = rows;
        this.columns = columns;
    }

    getValues() {
        return Array.from({ length: this.rows }, (_, rowOffset) =>
            Array.from({ length: this.columns }, (_, columnOffset) =>
                this.sheet.valueAt(this.row + rowOffset, this.column + columnOffset)
            )
        );
    }

    setValues(values) {
        values.forEach((row, rowOffset) => row.forEach((value, columnOffset) => {
            this.sheet.setValue(this.row + rowOffset, this.column + columnOffset, value);
        }));
        return this;
    }

    setFontWeight() { return this; }
    setNumberFormat() { return this; }

    createTextFinder(expected) {
        const range = this;
        return {
            matchEntireCell() { return this; },
            findNext() {
                return range.getValues().flat().some(value => String(value) === expected)
                    ? {}
                    : null;
            }
        };
    }
}

class Sheet {
    constructor(name, rows = []) {
        this.name = name;
        this.rows = rows.map(row => [...row]);
        this.frozenRows = 0;
    }

    getName() { return this.name; }
    getLastRow() { return this.rows.length; }
    getLastColumn() { return Math.max(0, ...this.rows.map(row => row.length)); }
    getRange(row, column, rows, columns) { return new Range(this, row, column, rows, columns); }
    setFrozenRows(count) { this.frozenRows = count; }
    appendRow(row) { this.rows.push([...row]); }
    insertColumnsAfter(after, count) {
        this.rows.forEach(row => row.splice(after, 0, ...Array(count).fill('')));
    }
    valueAt(row, column) { return this.rows[row - 1]?.[column - 1] ?? ''; }
    setValue(row, column, value) {
        while (this.rows.length < row) this.rows.push([]);
        while (this.rows[row - 1].length < column) this.rows[row - 1].push('');
        this.rows[row - 1][column - 1] = value;
    }
}

class Spreadsheet {
    constructor(name = 'ICEBERG Website Registrations') {
        this.name = name;
        this.sheets = new Map();
    }

    getName() { return this.name; }
    getSheetByName(name) { return this.sheets.get(name) || null; }
    insertSheet(name) {
        const sheet = new Sheet(name);
        this.sheets.set(name, sheet);
        return sheet;
    }
}

function loadReceiver({ properties = {}, spreadsheet = new Spreadsheet() } = {}) {
    const output = content => ({
        content,
        setMimeType() { return this; }
    });
    const context = {
        console: { log() {}, error() {} },
        ContentService: {
            MimeType: { JSON: 'application/json' },
            createTextOutput: output
        },
        PropertiesService: {
            getScriptProperties: () => ({
                getProperty: name => properties[name] || null
            })
        },
        SpreadsheetApp: {
            openById(id) {
                if (id !== properties.SHEET_ID) throw new Error('Unknown spreadsheet');
                return spreadsheet;
            }
        },
        LockService: {
            getScriptLock: () => ({ waitLock() {}, releaseLock() {} })
        }
    };
    vm.createContext(context);
    vm.runInContext(readFileSync('google-apps-script/Code.gs', 'utf8'), context);
    return { context, spreadsheet };
}

function result(output) {
    return JSON.parse(output.content);
}

function validLead(overrides = {}) {
    return {
        postData: {
            contents: JSON.stringify({
                secret: 'shared-secret',
                id: '12345678-1234-4234-8234-123456789012',
                submitted_at: '2026-08-08T10:00:00.000Z',
                student_name: 'Ali Valiyev',
                student_phone: '+998901234567',
                program: 'ielts',
                branch: 'main',
                ...overrides
            })
        }
    };
}

test('setup creates the registrations sheet and complete header row', () => {
    const { context, spreadsheet } = loadReceiver({
        properties: { SHEET_ID: 'sheet-id', WEBHOOK_SECRET: 'shared-secret' }
    });
    const setup = context.setup();
    const sheet = spreadsheet.getSheetByName('Registrations');
    assert.equal(setup.ok, true);
    assert.equal(sheet.frozenRows, 1);
    assert.deepEqual(Array.from(sheet.rows[0]), [
        'ID', 'Submitted At', 'Student Name', 'Phone', 'Program ID', 'Branch ID',
        'UTM Source', 'UTM Medium', 'UTM Campaign', 'Page URL', 'Referrer',
        'Status', 'Staff Notes'
    ]);
    assert.equal(result(context.doGet()).sheet_ready, true);
});

test('doPost stores one idempotent row with stable program and branch IDs', () => {
    const { context, spreadsheet } = loadReceiver({
        properties: { SHEET_ID: 'sheet-id', WEBHOOK_SECRET: 'shared-secret' }
    });
    context.setup();
    const first = result(context.doPost(validLead()));
    const repeat = result(context.doPost(validLead()));
    assert.equal(first.ok, true);
    assert.equal(first.duplicate, false);
    assert.equal(repeat.ok, true);
    assert.equal(repeat.duplicate, true);
    const sheet = spreadsheet.getSheetByName('Registrations');
    assert.equal(sheet.rows.length, 2);
    const headers = sheet.rows[0];
    const stored = Object.fromEntries(headers.map((header, index) => [header, sheet.rows[1][index]]));
    assert.equal(stored['Student Name'], 'Ali Valiyev');
    assert.equal(stored['Phone'], "'+998901234567");
    assert.equal(stored['Program ID'], 'ielts');
    assert.equal(stored['Branch ID'], 'main');
    assert.equal(stored.Status, 'New');
});

test('setup preserves existing rows and adds missing columns safely', () => {
    const spreadsheet = new Spreadsheet();
    const sheet = spreadsheet.insertSheet('Registrations');
    sheet.rows = [
        ['ID', 'Submitted At', 'Student Name', 'Phone', 'Status'],
        ['old-id', new Date('2026-01-01T00:00:00Z'), 'Existing Student', '+998900000000', 'Called']
    ];
    const { context } = loadReceiver({
        properties: { SHEET_ID: 'sheet-id', WEBHOOK_SECRET: 'shared-secret' },
        spreadsheet
    });
    context.setup();
    assert.equal(sheet.rows[1][2], 'Existing Student');
    assert.ok(sheet.rows[0].includes('Program ID'));
    assert.ok(sheet.rows[0].includes('Branch ID'));
    assert.equal(result(context.doPost(validLead({ student_name: '=IMPORTXML("bad")' }))).ok, true);
    const nameColumn = sheet.rows[0].indexOf('Student Name');
    assert.match(sheet.rows[2][nameColumn], /^'/);
});

test('receiver reports configuration and authorization failures without writing', () => {
    const missing = loadReceiver();
    assert.equal(result(missing.context.doGet()).error, 'not_configured');

    const configured = loadReceiver({
        properties: { SHEET_ID: 'sheet-id', WEBHOOK_SECRET: 'shared-secret' }
    });
    const response = result(configured.context.doPost(validLead({ secret: 'wrong-secret' })));
    assert.equal(response.error, 'unauthorized');
    assert.equal(configured.spreadsheet.getSheetByName('Registrations'), null);
});

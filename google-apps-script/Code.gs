const REGISTRATIONS_SHEET = 'Registrations';
const HEADERS = [
  'ID',
  'Submitted At',
  'Student Name',
  'Phone',
  'Program ID',
  'Branch ID',
  'UTM Source',
  'UTM Medium',
  'UTM Campaign',
  'Page URL',
  'Referrer',
  'Status',
  'Staff Notes'
];
const CONTACTS_SHEET = 'Contacts';
const CONTACT_HEADERS = [
  'ID',
  'Submitted At',
  'Name',
  'Phone',
  'Message',
  'Page URL',
  'Referrer',
  'Status',
  'Staff Notes'
];
const DEFAULT_SUPPORT_EMAIL = 'support@iceberglc.com';
const RECEIVER_VERSION = '2026-11-18.2';

function jsonResult_(body) {
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

function safeCell_(value) {
  const text = String(value || '').replace(/[\u0000-\u001f\u007f]/g, '').trim();
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function receiverProperties_() {
  const properties = PropertiesService.getScriptProperties();
  return {
    spreadsheetId: properties.getProperty('SHEET_ID'),
    webhookSecret: properties.getProperty('WEBHOOK_SECRET'),
    supportEmail: (properties.getProperty('SUPPORT_EMAIL') || DEFAULT_SUPPORT_EMAIL).trim()
  };
}

function ensureSheet_(spreadsheet, name, expectedHeaders) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
  }

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, expectedHeaders.length).setValues([expectedHeaders]);
    sheet.setFrozenRows(1);
  } else {
    const existingHeaders = sheet
      .getRange(1, 1, 1, sheet.getLastColumn())
      .getValues()[0]
      .map(String);
    const missingHeaders = expectedHeaders.filter(header => !existingHeaders.includes(header));
    if (missingHeaders.length) {
      const firstNewColumn = sheet.getLastColumn() + 1;
      sheet.insertColumnsAfter(sheet.getLastColumn(), missingHeaders.length);
      sheet.getRange(1, firstNewColumn, 1, missingHeaders.length).setValues([missingHeaders]);
    }
  }

  sheet.getRange(1, 1, 1, sheet.getLastColumn()).setFontWeight('bold');
  return sheet;
}

function ensureRegistrationSheet_(spreadsheet) {
  return ensureSheet_(spreadsheet, REGISTRATIONS_SHEET, HEADERS);
}

function ensureContactSheet_(spreadsheet) {
  return ensureSheet_(spreadsheet, CONTACTS_SHEET, CONTACT_HEADERS);
}

function plainText_(value, maxLength) {
  return String(value || '').replace(/[\u0000-\u0009\u000b-\u001f\u007f]/g, '').trim().slice(0, maxLength);
}

// Email delivery must never cause a saved submission to be reported as failed:
// the row is already in the sheet, so a mail error is logged and ignored.
function notifySupport_(config, subject, lines) {
  if (!config.supportEmail) {
    return false;
  }
  try {
    MailApp.sendEmail({
      to: config.supportEmail,
      subject: plainText_(subject, 200).replace(/\n/g, ' '),
      body: lines.map(line => plainText_(line, 2500)).join('\n'),
      name: 'ICEBERG Website'
    });
    return true;
  } catch (error) {
    console.error('Support email failed', error);
    return false;
  }
}

function rowExists_(sheet, headers, id) {
  const idColumn = headers.indexOf('ID') + 1;
  if (!idColumn) {
    throw new Error('ID column is missing');
  }
  return Boolean(sheet
    .getRange(1, idColumn, sheet.getLastRow(), 1)
    .createTextFinder(String(id))
    .matchEntireCell(true)
    .findNext());
}

function submittedAt_(value) {
  const parsed = value ? new Date(String(value)) : new Date();
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function appendByHeader_(sheet, headers, valuesByHeader) {
  sheet.appendRow(headers.map(header => (
    Object.prototype.hasOwnProperty.call(valuesByHeader, header)
      ? valuesByHeader[header]
      : ''
  )));
  sheet
    .getRange(sheet.getLastRow(), headers.indexOf('Submitted At') + 1)
    .setNumberFormat('yyyy-mm-dd hh:mm:ss');
}

function headersOf_(sheet) {
  return sheet
    .getRange(1, 1, 1, sheet.getLastColumn())
    .getValues()[0]
    .map(String);
}

function storeContact_(config, data) {
  if (!data.id || !data.name || !data.phone || !data.message) {
    return { ok: false, error: 'missing_required_fields' };
  }

  let isNew = false;
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = ensureContactSheet_(SpreadsheetApp.openById(config.spreadsheetId));
    const headers = headersOf_(sheet);
    if (!rowExists_(sheet, headers, data.id)) {
      appendByHeader_(sheet, headers, {
        'ID': safeCell_(data.id),
        'Submitted At': submittedAt_(data.submitted_at),
        'Name': safeCell_(data.name),
        'Phone': safeCell_(data.phone),
        'Message': safeCell_(data.message),
        'Page URL': safeCell_(data.page_url),
        'Referrer': safeCell_(data.referrer),
        'Status': 'New',
        'Staff Notes': ''
      });
      isNew = true;
    }
  } finally {
    lock.releaseLock();
  }

  // email_sent: the website already emailed support directly (Resend).
  const emailed = isNew && data.email_sent !== true && notifySupport_(config, 'Saytdan yangi xabar: ' + data.name, [
    'ICEBERG saytidagi aloqa formasi orqali yangi xabar keldi.',
    '',
    'Ism: ' + data.name,
    'Telefon: ' + data.phone,
    '',
    'Xabar:',
    data.message,
    '',
    'Sahifa: ' + (data.page_url || '-'),
    'ID: ' + data.id
  ]);
  return { ok: true, id: String(data.id), emailed: emailed, version: RECEIVER_VERSION };
}

function setup() {
  const config = receiverProperties_();
  if (!config.spreadsheetId || !config.webhookSecret) {
    throw new Error('Add SHEET_ID and WEBHOOK_SECRET in Project Settings > Script properties first.');
  }
  const spreadsheet = SpreadsheetApp.openById(config.spreadsheetId);
  const sheet = ensureRegistrationSheet_(spreadsheet);
  const contactSheet = ensureContactSheet_(spreadsheet);
  // Referencing MailApp here makes Apps Script request the email permission
  // when setup is run, before the first real submission needs it.
  const remainingEmailQuota = MailApp.getRemainingDailyQuota();
  const result = {
    ok: true,
    version: RECEIVER_VERSION,
    spreadsheet: spreadsheet.getName(),
    sheet: sheet.getName(),
    contact_sheet: contactSheet.getName(),
    support_email: config.supportEmail,
    remaining_email_quota: remainingEmailQuota
  };
  console.log(JSON.stringify(result));
  return result;
}

function doGet() {
  try {
    const config = receiverProperties_();
    if (!config.spreadsheetId || !config.webhookSecret) {
      return jsonResult_({
        ok: false,
        service: 'ICEBERG registration receiver',
        version: RECEIVER_VERSION,
        error: 'not_configured'
      });
    }
    const spreadsheet = SpreadsheetApp.openById(config.spreadsheetId);
    const sheet = spreadsheet.getSheetByName(REGISTRATIONS_SHEET);
    const contactSheet = spreadsheet.getSheetByName(CONTACTS_SHEET);
    return jsonResult_({
      ok: Boolean(sheet) && Boolean(contactSheet),
      service: 'ICEBERG registration receiver',
      version: RECEIVER_VERSION,
      sheet_ready: Boolean(sheet),
      contact_sheet_ready: Boolean(contactSheet)
    });
  } catch (error) {
    console.error(error);
    return jsonResult_({
      ok: false,
      service: 'ICEBERG registration receiver',
      version: RECEIVER_VERSION,
      error: 'sheet_unavailable'
    });
  }
}

function doPost(e) {
  try {
    const config = receiverProperties_();
    if (!config.spreadsheetId || !config.webhookSecret) {
      return jsonResult_({ ok: false, error: 'not_configured' });
    }

    const data = JSON.parse((e.postData && e.postData.contents) || '{}');
    if (!data.secret || data.secret !== config.webhookSecret) {
      return jsonResult_({ ok: false, error: 'unauthorized' });
    }
    if (data.type === 'contact') {
      return jsonResult_(storeContact_(config, data));
    }
    if (!data.id || !data.student_name || !data.student_phone || !data.program || !data.branch) {
      return jsonResult_({ ok: false, error: 'missing_required_fields' });
    }

    let isNew = false;
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const sheet = ensureRegistrationSheet_(SpreadsheetApp.openById(config.spreadsheetId));
      const headers = headersOf_(sheet);
      if (!rowExists_(sheet, headers, data.id)) {
        appendByHeader_(sheet, headers, {
          'ID': safeCell_(data.id),
          'Submitted At': submittedAt_(data.submitted_at),
          'Student Name': safeCell_(data.student_name),
          'Phone': safeCell_(data.student_phone),
          'Program ID': safeCell_(data.program),
          'Branch ID': safeCell_(data.branch),
          'UTM Source': safeCell_(data.utm_source),
          'UTM Medium': safeCell_(data.utm_medium),
          'UTM Campaign': safeCell_(data.utm_campaign),
          'Page URL': safeCell_(data.page_url),
          'Referrer': safeCell_(data.referrer),
          'Status': 'New',
          'Staff Notes': ''
        });
        isNew = true;
      }
    } finally {
      lock.releaseLock();
    }

    const emailed = isNew && data.email_sent !== true && notifySupport_(config, 'Yangi ariza: ' + data.student_name, [
      'ICEBERG saytida yangi ro\'yxatdan o\'tish arizasi.',
      '',
      'Ism: ' + data.student_name,
      'Telefon: ' + data.student_phone,
      'Dastur: ' + data.program,
      'Filial: ' + data.branch,
      '',
      'Sahifa: ' + (data.page_url || '-'),
      'ID: ' + data.id
    ]);

    return jsonResult_({ ok: true, id: String(data.id), emailed: emailed, version: RECEIVER_VERSION });
  } catch (error) {
    console.error(error);
    return jsonResult_({ ok: false, error: 'internal_error' });
  }
}

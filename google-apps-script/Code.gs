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
const RECEIVER_VERSION = '2026-08-08.1';

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
    webhookSecret: properties.getProperty('WEBHOOK_SECRET')
  };
}

function ensureRegistrationSheet_(spreadsheet) {
  let sheet = spreadsheet.getSheetByName(REGISTRATIONS_SHEET);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(REGISTRATIONS_SHEET);
  }

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sheet.setFrozenRows(1);
  } else {
    const existingHeaders = sheet
      .getRange(1, 1, 1, sheet.getLastColumn())
      .getValues()[0]
      .map(String);
    const missingHeaders = HEADERS.filter(header => !existingHeaders.includes(header));
    if (missingHeaders.length) {
      const firstNewColumn = sheet.getLastColumn() + 1;
      sheet.insertColumnsAfter(sheet.getLastColumn(), missingHeaders.length);
      sheet.getRange(1, firstNewColumn, 1, missingHeaders.length).setValues([missingHeaders]);
    }
  }

  sheet.getRange(1, 1, 1, sheet.getLastColumn()).setFontWeight('bold');
  return sheet;
}

function setup() {
  const config = receiverProperties_();
  if (!config.spreadsheetId || !config.webhookSecret) {
    throw new Error('Add SHEET_ID and WEBHOOK_SECRET in Project Settings > Script properties first.');
  }
  const spreadsheet = SpreadsheetApp.openById(config.spreadsheetId);
  const sheet = ensureRegistrationSheet_(spreadsheet);
  const result = {
    ok: true,
    version: RECEIVER_VERSION,
    spreadsheet: spreadsheet.getName(),
    sheet: sheet.getName()
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
    return jsonResult_({
      ok: Boolean(sheet),
      service: 'ICEBERG registration receiver',
      version: RECEIVER_VERSION,
      sheet_ready: Boolean(sheet)
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
    if (!data.id || !data.student_name || !data.student_phone || !data.program || !data.branch) {
      return jsonResult_({ ok: false, error: 'missing_required_fields' });
    }

    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const spreadsheet = SpreadsheetApp.openById(config.spreadsheetId);
      const sheet = ensureRegistrationSheet_(spreadsheet);
      const headers = sheet
        .getRange(1, 1, 1, sheet.getLastColumn())
        .getValues()[0]
        .map(String);
      const idColumn = headers.indexOf('ID') + 1;
      if (!idColumn) {
        throw new Error('ID column is missing');
      }

      const existing = sheet
        .getRange(1, idColumn, sheet.getLastRow(), 1)
        .createTextFinder(String(data.id))
        .matchEntireCell(true)
        .findNext();
      if (!existing) {
        const parsedSubmittedAt = data.submitted_at
          ? new Date(String(data.submitted_at))
          : new Date();
        const submittedAt = Number.isNaN(parsedSubmittedAt.getTime())
          ? new Date()
          : parsedSubmittedAt;
        const valuesByHeader = {
          'ID': safeCell_(data.id),
          'Submitted At': submittedAt,
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
        };
        sheet.appendRow(headers.map(header => (
          Object.prototype.hasOwnProperty.call(valuesByHeader, header)
            ? valuesByHeader[header]
            : ''
        )));
        sheet
          .getRange(sheet.getLastRow(), headers.indexOf('Submitted At') + 1)
          .setNumberFormat('yyyy-mm-dd hh:mm:ss');
      }
    } finally {
      lock.releaseLock();
    }

    return jsonResult_({ ok: true, id: String(data.id), version: RECEIVER_VERSION });
  } catch (error) {
    console.error(error);
    return jsonResult_({ ok: false, error: 'internal_error' });
  }
}

const REGISTRATIONS_SHEET = 'Registrations';
const HEADERS = [
  'ID',
  'Submitted At',
  'Student Name',
  'Phone',
  'UTM Source',
  'UTM Medium',
  'UTM Campaign',
  'Page URL',
  'Referrer',
  'Status',
  'Staff Notes'
];

function jsonResult_(body) {
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

function safeCell_(value) {
  const text = String(value || '').replace(/[\u0000-\u001f\u007f]/g, '').trim();
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function doPost(e) {
  try {
    const properties = PropertiesService.getScriptProperties();
    const spreadsheetId = properties.getProperty('SHEET_ID');
    const expectedSecret = properties.getProperty('WEBHOOK_SECRET');
    if (!spreadsheetId || !expectedSecret) {
      throw new Error('SHEET_ID or WEBHOOK_SECRET is not configured');
    }

    const data = JSON.parse((e.postData && e.postData.contents) || '{}');
    if (!data.secret || data.secret !== expectedSecret) {
      return jsonResult_({ ok: false, error: 'Unauthorized' });
    }
    if (!data.id || !data.student_name || !data.student_phone) {
      return jsonResult_({ ok: false, error: 'Missing required fields' });
    }

    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
      let sheet = spreadsheet.getSheetByName(REGISTRATIONS_SHEET);
      if (!sheet) {
        sheet = spreadsheet.insertSheet(REGISTRATIONS_SHEET);
      }
      if (sheet.getLastRow() === 0) {
        sheet.appendRow(HEADERS);
        sheet.setFrozenRows(1);
        sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
      }

      const existing = sheet
        .getRange(1, 1, sheet.getLastRow(), 1)
        .createTextFinder(String(data.id))
        .matchEntireCell(true)
        .findNext();
      if (!existing) {
        sheet.appendRow([
          safeCell_(data.id),
          safeCell_(data.submitted_at),
          safeCell_(data.student_name),
          safeCell_(data.student_phone),
          safeCell_(data.utm_source),
          safeCell_(data.utm_medium),
          safeCell_(data.utm_campaign),
          safeCell_(data.page_url),
          safeCell_(data.referrer),
          'New',
          ''
        ]);
      }
    } finally {
      lock.releaseLock();
    }

    return jsonResult_({ ok: true, id: String(data.id) });
  } catch (error) {
    console.error(error);
    return jsonResult_({ ok: false, error: 'Internal error' });
  }
}

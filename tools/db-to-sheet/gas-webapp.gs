/**
 * db-to-sheet 受け口（Google Apps Script Web アプリ）
 *
 * 設置手順:
 *   1. 転記先スプレッドシートを開く → 拡張機能 → Apps Script
 *   2. このファイルの中身を貼り付けて保存
 *   3. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *        次のユーザーとして実行: 自分
 *        アクセスできるユーザー: 全員        ← ブラウザから直接POSTするために必要
 *   4. 発行された /exec のURLを scraper.js の postUrl に設定
 *
 * 注意: 「全員」公開のURLを知っている人は誰でも書き込めます。URLは他人に共有しないこと。
 *       心配なら下の SHARED_SECRET を設定し、scraper.js 側の body に secret を足してください。
 */

const SHEET_NAME    = 'シート1';
const KEY_COLUMN    = 'リンク';  // 重複排除に使う列名。'' にすると重複排除しない
const SHARED_SECRET = '';        // 例: 'my-secret-123'。'' なら認証なし

function doGet() {
  return ContentService.createTextOutput('db-to-sheet: OK');
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const payload = JSON.parse(e.postData.contents);

    if (SHARED_SECRET && payload.secret !== SHARED_SECRET) {
      return ContentService.createTextOutput('NG: secret mismatch');
    }

    const records = payload.records || [];
    if (!records.length) return ContentService.createTextOutput('OK: 0件');

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);

    // --- ヘッダー行を取得（無ければ作る／新しい列は右に足す） ---
    let headers = sh.getLastRow() > 0
      ? sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0].filter(String)
      : [];

    const incoming = payload.headers || Object.keys(records[0]);
    const added = incoming.filter(function (h) { return headers.indexOf(h) === -1; });
    if (added.length) {
      headers = headers.concat(added);
      sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
      sh.setFrozenRows(1);
    }

    // --- 既存データのキーを集めて重複を弾く ---
    const keyIdx = KEY_COLUMN ? headers.indexOf(KEY_COLUMN) : -1;
    const seen = {};
    if (keyIdx >= 0 && sh.getLastRow() > 1) {
      sh.getRange(2, keyIdx + 1, sh.getLastRow() - 1, 1).getValues()
        .forEach(function (r) { if (r[0]) seen[String(r[0])] = true; });
    }

    const rows = [];
    records.forEach(function (rec) {
      const key = keyIdx >= 0 ? String(rec[KEY_COLUMN] || '') : '';
      if (key && seen[key]) return;
      if (key) seen[key] = true;
      rows.push(headers.map(function (h) { return rec[h] != null ? rec[h] : ''; }));
    });

    if (rows.length) {
      sh.getRange(sh.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
    }
    return ContentService.createTextOutput(
      'OK: 受信' + records.length + '件 / 追記' + rows.length + '件 / スキップ' + (records.length - rows.length) + '件');
  } catch (err) {
    return ContentService.createTextOutput('ERROR: ' + err);
  } finally {
    lock.releaseLock();
  }
}

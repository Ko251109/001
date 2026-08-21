/* =============================================================
 * db-to-sheet scraper
 * 規則性のあるデータベースサイトのページから「1件＝1行」を抽出する。
 *
 * 使い方（手動モード）:
 *   1. 対象ページをChromeで開く（ログイン済みのタブでOK）
 *   2. F12 → Console タブ
 *   3. このファイルの中身を全部貼り付けて Enter
 *   4. TSVがクリップボードにコピーされるので、スプレッドシートのA1に貼り付け
 *
 * 使い方（自動送信モード）:
 *   貼り付ける前に、Consoleで先に設定を入れる:
 *     window.DBX_CONFIG = { postUrl: 'https://script.google.com/macros/s/xxxx/exec' };
 *   その後このファイルを貼り付けると、GASのWebアプリ経由でシートに直接追記される。
 *
 * 複数ページをまとめて取る:
 *     window.DBX_CONFIG = { maxPages: 20 };            // 次ページを自動追尾
 *     window.DBX_CONFIG = { maxPages: 20, nextSelector: 'a.next' };  // 明示指定
 * ============================================================= */
(async () => {
  'use strict';

  const CFG = Object.assign({
    postUrl: '',          // 空ならクリップボードへTSVコピー
    maxPages: 1,          // 次ページ追尾の上限
    nextSelector: '',     // 次ページリンクのCSSセレクタ（空なら自動推測）
    recordSelector: '',   // 1件分ブロックのCSSセレクタ（空なら自動検出）
    fieldMap: null,       // { '列名': 'CSSセレクタ' } 明示指定したい場合
    pageDelayMs: 400,     // ページ取得の間隔（サーバ負荷への配慮）
  }, window.DBX_CONFIG || {});

  const txt = (el) => (el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '');

  /* ---------- 1件分のブロックを見つける ---------- */

  function detectRecords(doc) {
    if (CFG.recordSelector) {
      const list = [...doc.querySelectorAll(CFG.recordSelector)];
      if (list.length) return { kind: 'block', nodes: list };
    }

    // (a) データテーブルがあればそれを最優先
    let bestTable = null, bestScore = 0;
    for (const t of doc.querySelectorAll('table')) {
      const rows = [...t.rows].filter((r) => r.cells.length >= 2);
      const score = rows.length * (rows[0] ? rows[0].cells.length : 0);
      if (rows.length >= 3 && score > bestScore) { bestScore = score; bestTable = t; }
    }
    if (bestTable) return { kind: 'table', table: bestTable };

    // (b) 同じ親の下に並ぶ「同じ見た目の兄弟要素」＝レコードの繰り返し、とみなす
    let best = null;
    for (const parent of doc.querySelectorAll('body *')) {
      const groups = new Map();
      for (const child of parent.children) {
        const sig = child.tagName + '.' + [...child.classList].sort().join('.');
        (groups.get(sig) || groups.set(sig, []).get(sig)).push(child);
      }
      for (const nodes of groups.values()) {
        if (nodes.length < 3) continue;
        const total = nodes.reduce((s, n) => s + txt(n).length, 0);
        const avg = total / nodes.length;
        if (avg < 15) continue;                       // ナビゲーション等の短いリストを除外
        if (!best || total > best.total) best = { total, nodes };
      }
    }
    return best ? { kind: 'block', nodes: best.nodes } : null;
  }

  /* ---------- 1件分から項目を取り出す ---------- */

  function extractFields(rec, baseUrl) {
    const out = {};
    const put = (k, v) => { k = k.replace(/[:：]\s*$/, '').trim(); if (k && v && !out[k]) out[k] = v; };

    if (CFG.fieldMap) {
      for (const [name, sel] of Object.entries(CFG.fieldMap)) put(name, txt(rec.querySelector(sel)));
    }

    // dl > dt/dd 形式
    rec.querySelectorAll('dl').forEach((dl) => {
      const kids = [...dl.children];
      for (let i = 0; i < kids.length; i++) {
        if (kids[i].tagName !== 'DT') continue;
        const dds = [];
        for (let j = i + 1; j < kids.length && kids[j].tagName === 'DD'; j++) dds.push(txt(kids[j]));
        put(txt(kids[i]), dds.join(' / '));
      }
    });

    // tr > th/td 形式（レコード内の小さな表）
    rec.querySelectorAll('tr').forEach((tr) => {
      const th = tr.querySelector('th'), td = tr.querySelector('td');
      if (th && td) put(txt(th), txt(td));
    });

    // class名に label/key/name と value/data が対で入っている形式
    rec.querySelectorAll('[class*="label"],[class*="ttl"],[class*="head"]').forEach((lab) => {
      const val = lab.nextElementSibling;
      if (val && !val.querySelector('[class*="label"]')) put(txt(lab), txt(val));
    });

    // 見出し・リンク
    const h = rec.querySelector('h1,h2,h3,h4,[class*="title"],[class*="name"]');
    if (h) put('タイトル', txt(h));
    const a = rec.querySelector('a[href]');
    if (a) { put('リンク', new URL(a.getAttribute('href'), baseUrl).href); put('タイトル', txt(a)); }

    // 何も取れなければ直下の子要素をそのまま列にする
    if (Object.keys(out).length <= 2) {
      [...rec.children].forEach((c, i) => put('列' + (i + 1), txt(c)));
    }
    if (!Object.keys(out).length) put('本文', txt(rec));
    return out;
  }

  function parseDoc(doc, baseUrl) {
    const det = detectRecords(doc);
    if (!det) return [];

    if (det.kind === 'table') {
      const rows = [...det.table.rows];
      const head = [...rows[0].cells].map((c, i) => txt(c) || '列' + (i + 1));
      return rows.slice(1)
        .filter((r) => r.cells.length >= 2)
        .map((r) => Object.fromEntries([...r.cells].map((c, i) => [head[i] || '列' + (i + 1), txt(c)])));
    }
    return det.nodes.map((n) => extractFields(n, baseUrl)).filter((o) => Object.keys(o).length);
  }

  /* ---------- 次ページ ---------- */

  function findNext(doc) {
    if (CFG.nextSelector) return doc.querySelector(CFG.nextSelector);
    return doc.querySelector('a[rel="next"]')
      || [...doc.querySelectorAll('a[href]')].find((a) => /^(次|次へ|次のページ|next|›|»|>)\s*$/i.test(txt(a)));
  }

  /* ---------- 収集 ---------- */

  const records = [];
  let doc = document, baseUrl = location.href, pages = 0;

  while (true) {
    const got = parseDoc(doc, baseUrl);
    records.push(...got);
    pages++;
    console.log(`[db-to-sheet] page ${pages}: ${got.length}件 (${baseUrl})`);
    if (pages >= CFG.maxPages) break;

    const next = findNext(doc);
    const href = next && next.getAttribute('href');
    if (!href) break;
    const nextUrl = new URL(href, baseUrl).href;
    if (nextUrl === baseUrl) break;

    await new Promise((r) => setTimeout(r, CFG.pageDelayMs));
    const res = await fetch(nextUrl, { credentials: 'include' });
    if (!res.ok) { console.warn('[db-to-sheet] 取得失敗:', res.status, nextUrl); break; }
    doc = new DOMParser().parseFromString(await res.text(), 'text/html');
    baseUrl = nextUrl;
  }

  if (!records.length) {
    console.error('[db-to-sheet] レコードを検出できませんでした。'
      + '\n1件分のブロックを右クリック→「検証」でCSSセレクタを調べ、'
      + '\nwindow.DBX_CONFIG = { recordSelector: ".あなたのクラス名" } を設定してから再実行してください。');
    return;
  }

  // 列は「最初に出てきた順」で揃える
  const headers = [];
  records.forEach((r) => Object.keys(r).forEach((k) => { if (!headers.includes(k)) headers.push(k); }));

  console.log(`[db-to-sheet] 合計 ${records.length}件 / ${headers.length}列`, headers);
  console.table(records.slice(0, 5));

  /* ---------- 出力 ---------- */

  if (CFG.postUrl) {
    const res = await fetch(CFG.postUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' }, // GAS向け: プリフライトを避ける
      body: JSON.stringify({ headers, records, sourceUrl: location.href }),
    });
    console.log('[db-to-sheet] シート送信結果:', await res.text());
    return;
  }

  const esc = (v) => String(v == null ? '' : v).replace(/[\t\r\n]+/g, ' ');
  const tsv = [headers.join('\t'), ...records.map((r) => headers.map((h) => esc(r[h])).join('\t'))].join('\n');

  try {
    await navigator.clipboard.writeText(tsv);
    console.log('[db-to-sheet] ✅ クリップボードにコピーしました。スプレッドシートのA1に貼り付けてください。');
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = tsv;
    Object.assign(ta.style, { position: 'fixed', top: '10px', left: '10px', width: '90vw', height: '70vh', zIndex: 99999 });
    document.body.appendChild(ta);
    ta.select();
    console.warn('[db-to-sheet] 自動コピー不可。画面上のテキストエリアを Ctrl+A → Ctrl+C してください。');
  }
  window.__DBX_RESULT = { headers, records };
})();

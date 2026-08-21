# db-to-sheet — データベースサイト → スプレッドシート転記

規則性のあるWebサイトの一覧ページから「1件＝1行」を抽出し、Googleスプレッドシートへ転記するための道具立て。

転記先: `https://docs.google.com/spreadsheets/d/1Q-XyDFD5SHrx_vzjLOAAoAFprkJcKJ78bgPNeQuwf5M/` の「シート1」

---

## どの方法を選ぶか

| | 方法 | 手間 | 使える条件 |
|---|---|---|---|
| **A** | **Chromeのコンソールで `scraper.js` を実行 → TSVをコピー → シートに貼り付け** | ★最小（初回3分） | ほぼ常に使える。ログイン必須ページ・JS描画ページでもOK |
| B | A + `gas-webapp.gs`（貼り付け不要、シートへ直接送信） | 初回15分 | 何度も繰り返すなら |
| C | スプレッドシートの `IMPORTHTML` / `IMPORTXML` 関数 | ★最小 | ページが**ログイン不要 かつ 素のHTML**のときだけ |
| D | Apps Script の `UrlFetchApp` で定期実行 | 30分〜 | 同上＋自動更新したいとき |

**まずAを試す。** 対象URLが `/r_confidential/` 配下でブラウザのセッションに依存する可能性があるため、
C・Dは「シートやGASのサーバから見ると中身が見えない（ログイン画面が返る）」で失敗しやすい。
Aはあなたが見ている画面そのものを読むので、その問題が原理的に起きない。

---

## A. コンソール実行（推奨）

1. 対象ページをChromeで開く
2. `F12` → **Console** タブ
3. `scraper.js` の中身を全部コピーして貼り付け、Enter
4. `✅ クリップボードにコピーしました` と出たら、シート1のA1を選んで `Ctrl+V`

初回は「貼り付けを許可しますか」と聞かれるので、コンソールに `allow pasting` と打ってEnter。

### 自動検出がうまくいかないとき

`レコードを検出できませんでした` と出た／列がずれる場合は、1件分のブロックを右クリック →「検証」で
クラス名を確認し、**貼り付ける前に**次を実行する。

```js
window.DBX_CONFIG = { recordSelector: '.result-item' };   // 1件分のブロック
```

列名を自分で決めたい場合:

```js
window.DBX_CONFIG = {
  recordSelector: '.result-item',
  fieldMap: {
    '名称':   '.name',
    '住所':   '.address',
    '電話':   '.tel',
  },
};
```

### 複数ページをまとめて取る

```js
window.DBX_CONFIG = { maxPages: 20 };                        // 次ページを自動追尾
window.DBX_CONFIG = { maxPages: 20, nextSelector: 'a.next' }; // 次ページリンクを明示
```

`credentials: 'include'` でログイン状態のまま取得し、`pageDelayMs`（既定400ms）の間隔を空ける。

### 検索語を変えて何度も回す

URLの `?search_term=` を変えるだけなので、検索語ごとにタブを開いてAを繰り返すのが一番速い。
シートに検索語リストを作って回したくなったらB以降を検討する。

---

## B. シートへ直接送信

1. `gas-webapp.gs` の手順どおりWebアプリをデプロイし、`/exec` のURLを取得
2. コンソールで、`scraper.js` を貼る**前に**:

```js
window.DBX_CONFIG = { postUrl: 'https://script.google.com/macros/s/XXXX/exec', maxPages: 20 };
```

3. `scraper.js` を貼り付け → シート1に直接追記される

`KEY_COLUMN`（既定は `リンク`）で重複を弾くので、同じページを何度流し込んでも二重にならない。

---

## C. IMPORTHTML / IMPORTXML（ログイン不要なら最短）

シート1のA1に入れて試す:

```
=IMPORTHTML("https://www.tsunenaruhikaritotomoni.net/r_confidential/p10tfE3hotsh/?search_term=照光堂","table",1)
```

表でなくリスト構造なら `"list"` に変える。`#N/A` や `#REF!` が返る、あるいはログイン画面の文言が入る場合は
このルートは使えないのでAへ戻る。XPathで細かく取るなら:

```
=IMPORTXML(A1,"//div[@class='result-item']//span[@class='name']")
```

---

## 注意

- 転記先スプレッドシートの共有範囲を確認すること。`/r_confidential/` 配下のデータを扱う場合、
  シートを「リンクを知っている全員」にしていると意図せず公開される。
- Bの Web アプリを「全員」でデプロイする場合、`/exec` のURLは書き込み口そのもの。共有しない。
  気になる場合は `SHARED_SECRET` を設定する。
- 取得間隔を詰めすぎない（`pageDelayMs`）。サイトの利用規約も確認しておくこと。

# Paper Management

[English](README.en.md) | [简体中文](README.zh-CN.md)

ローカル完結型の論文管理・執筆支援ツール。
EndNote / Mendeley / Paperpile に相当する機能を、データベースを持たない
**ファイルベース構成（PDF + Markdown ペア）** で実現します。
<img width="1672" height="941" alt="論文管理アプリ" src="https://github.com/user-attachments/assets/e040cbef-3409-4823-ac07-4cc401f32559" />

## 主な機能

### アプリ本体（Web UI）
- **自動取り込み** — 監視フォルダにPDFを置くと、Paperpile形式（`著者 et al. 年 - タイトル.pdf`）にリネームし、第一著者の頭文字フォルダへ自動振り分け
- **PDF + Markdown 並列保存** — 各論文をPDFと、YAMLフロントマター付きMDのペアで保存。MDにはPDF本文・図も埋め込まれ、Obsidianの全文検索が論文内容にヒットします
- **メタデータ取得** — CrossRef API（DOI→書誌情報）・PDF内DOI自動抽出・Chrome拡張からのメタデータ送信
- **多フィールド検索** — 著者・タイトル・abstract・メモ・年・タグを横断し、スペース区切りでAND検索
- **コレクション** — 執筆プロジェクト別に論文を参照でまとめる（実体は移動しない）
- **論文の削除・再スキャン** — UIからの完全削除、アプリ外ファイル変更のライブラリ再スキャン
- **Obsidian連携** — `obsidian://` URI でノート閲覧・全文検索をObsidianに委譲
- **PDFなし論文の登録** — DOI付きメタデータのみで論文を登録し、後からPDFを添付可能

### AIエージェント連携（アプリ外・AI指示MD方式）
- **wikiリンク生成** — AI指示MDを使い、Claude Code / Codex / Gemini いずれかのCLIで論文間の関連wikiリンク・概念ページ・目次を生成
- **引用整形** — 原稿中の `[[論文リンク]]` を投稿規定に沿って番号付け・文献リスト生成
- **スタイル生成** — Author GuidelinesからAIが投稿スタイル定義を生成
- **関連論文探索** — AIがライブラリから関連論文を探し、原稿に引用リンクを挿入

> アプリ自体はAI機能・APIキーを持ちません。`vault_template` に同梱されたAI指示MDを、利用者が各AI CLIで直接実行します。

## 動作環境

- Windows（主対象）
- Obsidian（論文MDの閲覧・検索に使用）
- Google Chrome（論文リネーマー拡張を使う場合、任意）

> **配布版を使う場合、Python や uv のインストールは不要です。** 配布フォルダに同梱された `uv.exe` が、必要な Python と依存パッケージを自動で用意します。
> ソースコードから開発する場合のみ、Python 3.11 以上と [uv](https://docs.astral.sh/uv/) が別途必要です。

## セットアップ

### 1. セットアップスクリプトを実行

`セットアップ.bat` をダブルクリックします。以下が自動で行われます:

- （初回のみ）同梱の `uv.exe` による Python の自動取得
- 依存パッケージの同期（`uv sync`）
- `config.yaml.example` から `config.yaml` を作成

> 初回は依存パッケージ（PDF解析ライブラリ等、数百MB〜）のダウンロードに数分かかります。2回目以降はキャッシュにより高速になります。
>
> ⚠️ **このフォルダを `C:\Program Files\` 配下に置かないでください。** 書き込み権限がなくインストールに失敗します。「ドキュメント」フォルダや D ドライブ直下など、書き込み可能な場所に展開してください。

### 2. Vault フォルダを配置

`vault_template/paper_management/` フォルダごと、お使いの **Obsidian Vault のルート直下**にコピーします。

```
<あなたのVault>/
└── paper_management/
    ├── library/    ← 論文の保存先
    ├── styles/     ← 投稿スタイル定義
    ├── inbox/      ← 監視フォルダ（PDFをここに置く）
    ├── wiki/       ← 知識ベース（AIが構築）
    ├── workspace/  ← 論文執筆用（原稿テンプレート・執筆ガイド）
    └── AI_AGENT_GUIDE.md etc.
```

### 3. アプリを起動してパスを設定

`起動.bat` をダブルクリックすると、サーバが起動しブラウザが自動で開きます。

「設定」画面の「参照」ボタンから以下のフォルダを設定してください:

| 設定項目 | 選択するフォルダ |
|---------|--------------|
| 論文保存ルート | `<Vault>/paper_management/library` |
| Vaultパス | `<Vault>` のルート |
| スタイル定義フォルダ | `<Vault>/paper_management/styles` |
| 監視フォルダ | `<Vault>/paper_management/inbox` |

### 4.（任意）Chrome拡張のインストール

`chrome://extensions` でデベロッパーモードを有効にし、`paper rename/` フォルダを「パッケージ化されていない拡張機能を読み込む」で追加します。

## 使い方

### 起動

`起動.bat` をダブルクリック → ブラウザで `http://127.0.0.1:12000` が開きます。
終了するには Ctrl+C を押すか、ウィンドウを閉じてください。

### 論文の取り込み

PDFを取り込むと、書誌情報を解決し、Paperpile形式へのリネーム・頭文字フォルダ振り分け・MD生成を行います。

#### 方法1: 監視フォルダに置く（最も簡単）

PDF を `inbox`（監視フォルダ）に置くだけです。PDF内にDOIが記載されていれば、CrossRefから書誌情報を自動取得して取り込まれます。

#### 方法2: Chrome拡張からメタデータを送信（DOIのないPDFにも対応）

1. Chrome で論文のWebページを開く
2. 拡張機能「論文リネーマー」のポップアップで「**送信**」ボタンを押す → メタデータがバックエンドに一時保存（10分で失効）
3. **10分以内**にPDFを `inbox` に置く、または「PDFを取り込む」ボタンで取り込む

#### 方法3: 手動取り込み

「取り込み状況」画面の「PDFを取り込む」ボタンでファイル選択ダイアログから選んで取り込めます。

#### メタデータが取得できない場合

PDFにDOIがなく、Chrome拡張からも未送信の場合、PDFは `library` の**「未整理」フォルダ**へ退避され、「取り込み状況」画面に通知されます。

#### 方法4: AIエージェントのdeep research結果から登録（DOI一括登録API）

Claude Code などのAIエージェントに「○○について論文を探して登録して」と依頼すると、
AIがdeep researchで関連論文を探し、見つけた論文のDOIをアプリのAPIに渡して
**メタデータのみのエントリ（PDFなし）として一括登録**できます。

1. アプリを起動しておく（`http://127.0.0.1:12000`）
2. `paper_management` フォルダでAI CLIを起動し、テーマを指定して登録を依頼する
3. AIがDOIを特定し、登録APIへ送信する

APIを直接利用する場合:

- エンドポイント: `POST http://127.0.0.1:12000/api/import/doi`
- リクエストボディ（JSON）: `{"dois": ["10.xxxx/aaaa", "10.yyyy/bbbb"]}`
- 呼び出し例:

  ```bash
  curl -X POST http://127.0.0.1:12000/api/import/doi \
    -H "Content-Type: application/json" \
    -d '{"dois":["10.xxxx/example-doi-1","10.xxxx/example-doi-2"]}'
  ```

レスポンスはDOIごとに `registered`（新規）/ `duplicate`（既存）/
`failed`（不正DOI・CrossRef未ヒット）を返します。書誌情報はCrossRef APIから取得します。
PDF本文は登録されないため、必要に応じてインスペクタ画面から後で添付してください。

> AIエージェント向けの詳しい手順は `vault_template/paper_management/AI_AGENT_GUIDE.md` の
> 「論文の探索と自動登録（deep research）」を参照してください。

### 論文の管理

- **論文一覧** — 頭文字レール（A-Z, #）でフィルタ、多フィールド検索で絞り込み
- **インスペクタ** — 論文をクリックして書誌情報・abstract・memoを確認
- **Obsidianで開く** — ボタンクリックでObsidianのノートを直接開く
- **コレクション** — 「コレクション」画面でプロジェクト別に論文をまとめる
- **削除** — インスペクタの「削除」でPDF・MD・アセットフォルダ・コレクション参照を一括削除
- **再スキャン** — アプリ外でファイルを変更した場合、ツールバーの再スキャンボタンで反映

### AIエージェントによる知識ベース化・執筆支援

`paper_management` フォルダで AI CLI（Claude Code / Codex / Gemini）を起動し、タスクを指示します。

- **wikiリンク生成**: 「全論文を読んで関連リンクと概念ページを生成して」
- **スタイル生成**: Author Guidelinesを渡して「スタイル定義を作って」
- **引用整形**: 原稿を指定して「投稿用に仕上げて」
- **関連論文探索**: 原稿を指定して「関連論文を探してリンクを張って」

詳細は `vault_template/paper_management/AI_AGENT_GUIDE.md` および `workspace/論文執筆ガイド.md` を参照してください。

## 既知の制限・注意事項

- **Obsidian Web Viewer 内では「Obsidianで開く」が動作しません。** `obsidian://` URI がWeb Viewer側で処理されないため、通常のWebブラウザでこのアプリを使用してください。
- **Docling の初回利用時**、PDF本文・図の抽出に使う機械学習モデル（約1.3GB）が自動ダウンロードされます。`config.yaml` の `import_settings.extract_full_text: false` で本文抽出を無効化できます。
- **監視フォルダの自動検知**は、Windows + Google Drive同期環境では稀に不安定になることがあります。その場合は「PDFを取り込む」ボタンでの手動取り込みをご利用ください。

## よくある質問（FAQ）

### 監視フォルダに複数のPDFを入れたらどうなりますか？

**1件ずつ順番に処理されます**（同時並行ではありません）。内部で直列化されているため、
大量に入れてもCPUが逼迫することはありませんが、件数分の処理時間がかかります
（本文・図の抽出は1論文あたり10〜60秒程度）。大量取り込み時に急ぐ場合は、
`config.yaml` の `import_settings.extract_full_text: false` で本文抽出を省略すると高速になります。

### 複数のPCで使えますか？

**使えます。** アプリ本体はコードのみで、論文データ（PDF・MD・コレクション・wiki 等）は
すべて Obsidian Vault 内のファイルです。Vault を Google Drive 等のクラウドに置けば各PCに同期されます。

他のPCでは「アプリをクローン／展開 → `セットアップ.bat` 実行 → `config.yaml` の各パスを
そのPCでのVaultの場所に合わせる」だけで、同じ環境で作業できます
（クラウドのマウント先はPCごとに異なるため、`config.yaml` は各PCで設定します）。

⚠️ 同期の競合・破損を避けるため、**複数PCで同時に同じVaultを編集しないでください**。1台ずつ利用します。

### CrossRef設定の「連絡先メール」は入れるべき？

**入れることを推奨します**（必須ではありません）。

このアプリはDOIから書誌情報を取得する際にCrossRef APIを使います。設定画面の
「連絡先メール」にメールアドレスを入れると、APIリクエストに `mailto:` 情報が付き、
CrossRefの **polite pool（優遇プール）** に振り分けられます。これにより、混雑時でも
応答が安定・高速になります。

- メールはCrossRefへの**アカウント登録ではありません**。欄に書いて保存するだけです。
- 認証用ではなく、CrossRefが大量アクセス時に連絡するための窓口です。
- 空欄でもCrossRefは利用できます（public pool）が、polite poolの優遇は受けられません。

## アンインストール

このアプリは**フォルダ単位**で動作し、レジストリやスタートメニューへの登録は行いません。アンインストールはフォルダの削除だけです。

### 手順

1. アプリが起動中なら、`起動.bat` のウィンドウを閉じる
2. （Vault データを残したい場合のみ）Obsidian Vault 内の `paper_management/` フォルダを別の場所にバックアップ
3. **配布フォルダ全体をエクスプローラーで削除**（`.venv` ・`config.yaml` も中に入っているため一緒に消えます）
4. （任意）Chrome 拡張を導入していた場合は `chrome://extensions` から「論文リネーマー」を削除

### 注意

- Obsidian Vault 内の `paper_management/` には**あなたの論文データ（PDF・MD・コレクション）**が入っています。アプリと一緒に削除したい場合のみ手動で消してください。
- `config.yaml`（設定）は配布フォルダ内にあるため、フォルダ削除で同時に消えます。再セットアップ時は `セットアップ.bat` で自動再生成されます。

### 完全クリーンアップ（任意・上級者向け）

同梱の `uv.exe` が自動取得した Python と依存パッケージのキャッシュも消したい場合は、PowerShell で次を実行します。

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\uv"
```

⚠️ **他のアプリで uv を使っている場合は実行しないでください**（共有資産です）。

## 技術構成

- **バックエンド**: Python 3.11+ / FastAPI / Jinja2 + htmx（SPA不要のパーシャル更新）
- **アーキテクチャ**: ヘキサゴナル（ポート＆アダプタ）
  - `src/domain/` — ドメインモデル（外部依存なしの純Python）
  - `src/adapters/` — ファイルシステム・CrossRef・フォルダ監視
  - `src/application/` — 取り込み・ライブラリ・コレクションの各サービス
  - `src/web/` — FastAPIアプリ・ルート・テンプレート
- **PDF処理**: pypdf（DOI抽出）、Docling（本文・図のMarkdown化）— ともにMITライセンス
- **データ**: DBなし。論文は `PDF + MD` ペア、コレクションはYAMLファイルで保存
- **テスト**: 515件（pytest）、全パス、ruffクリーン

## 開発

```
uv run pytest          # テスト実行（515件）
uv run ruff check .    # 静的解析
uv run ruff format .   # フォーマット
```

## ライセンス

Apache License 2.0 — `LICENSE` ファイルを参照してください。

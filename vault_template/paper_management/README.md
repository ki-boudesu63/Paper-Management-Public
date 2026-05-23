
# paper_management — 論文管理アプリ用フォルダ

このフォルダは、論文管理アプリ「Paper Management」が使う保存先をまとめた**標準フォルダ配置の雛形**です。

## 使い方（セットアップ手順）

### 1. このフォルダをVaultに貼り付ける

`paper_management` フォルダごと、お使いの **Obsidian Vault のルート直下** にコピーしてください。

```
<あなたのVault>/
└── paper_management/      ← これを貼り付ける
    ├── library/
    ├── styles/
    └── inbox/
```

### 2. アプリにパスを登録する

登録方法は2通りあります。**「参照」ボタンを使う方法が簡単でおすすめです。**

#### 方法A：設定画面の「参照」ボタン（推奨）

1. `起動.py` をダブルクリックしてアプリを起動（ブラウザが `http://127.0.0.1:12000` で開く）
2. 「設定」画面を開く
3. 各パス入力欄の「参照」ボタンを押し、下表のフォルダを選択
4. 「保存」を押す（`config.yaml` に自動で書き込まれます）

#### 方法B：`config.yaml` を直接編集

ワークスペース直下の `config.yaml` を、下記の記入例にならって編集します。

## 各フォルダと設定キーの対応

| フォルダ | `config.yaml` のキー | 役割 |
|---------|---------------------|------|
| `paper_management/library/` | `paths.library_root` | 論文（PDF + MD）の保存先 |
| `paper_management/styles/`  | `paths.style_folder` | 投稿スタイル定義の置き場 |
| `paper_management/inbox/`   | `paths.watch_folder` | 新規PDFを置く監視フォルダ |
| Vault ルート自体            | `paths.vault_path`   | Obsidian Vault のルート |

## `config.yaml` 記入例

Vault が `G:\マイドライブ\Obsidian Vault` の場合の例です。
**パスの区切りは `/`（スラッシュ）で書く**とYAMLのエスケープ事故を防げます。

```yaml
paths:
  library_root: "G:/マイドライブ/Obsidian Vault/paper_management/library"
  vault_path:   "G:/マイドライブ/Obsidian Vault"
  style_folder: "G:/マイドライブ/Obsidian Vault/paper_management/styles"
  watch_folder: "G:/マイドライブ/Obsidian Vault/paper_management/inbox"
vault_name: "Obsidian Vault"       # 空欄なら vault_path のフォルダ名末尾を使用
server:
  host: "127.0.0.1"
  port: 12000
import_settings:
  unsorted_folder_name: "未整理"
  watch_interval_sec: 2
  contact_email: ""                # CrossRef polite pool 用の連絡先メール
```

## 補足

- `library/` 配下の頭文字フォルダ（A〜Z, #）・`未整理/`・`.collections/` は**アプリが自動で作成**します。手動で作る必要はありません。
- 各サブフォルダの詳しい説明は、それぞれの `README.md` を参照してください。

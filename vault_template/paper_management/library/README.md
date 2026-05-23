# library — 論文ライブラリ（保存先）

`config.yaml` の **`paths.library_root`** に指定するフォルダです。

## 役割

取り込まれた論文の **PDF と MD（YAMLフロントマター付き）のペア**が、ここに保存されます。

## 自動で作られるもの（手動で作らないでください）

アプリが必要に応じて以下を自動生成します：

| 自動生成 | 内容 |
|---------|------|
| `A/` 〜 `Z/`, `#/` | 第一著者の姓の頭文字フォルダ。論文はここに振り分けられる（`#` は非英字） |
| `未整理/` | メタデータ取得に失敗した論文の退避先 |
| `.collections/` | コレクション（執筆プロジェクト別の論文束）の定義YAML |

## 注意

- このフォルダ内のファイルは**アプリが管理**します。手動でのリネーム・移動は避けてください。
- 1論文 = PDF + 同名 MD のペアです。MD には書誌情報（著者・年・DOI 等）が記録されます。

---

## English

### library — Paper Library (Storage)

This is the folder specified by **`paths.library_root`** in `config.yaml`.

### Purpose

Imported papers are stored here as **pairs of PDF and MD files (with YAML front matter)**.

### Auto-Generated Contents (Do Not Create Manually)

The app automatically generates the following as needed:

| Auto-Generated | Description |
|----------------|-------------|
| `A/` to `Z/`, `#/` | Subfolders based on the first letter of the first author's surname. Papers are sorted into these folders (`#` is for non-alphabetic characters) |
| `未整理/` | Destination for papers whose metadata retrieval failed |
| `.collections/` | YAML definitions for collections (groups of papers organized by writing project) |

### Notes

- Files in this folder are **managed by the app**. Avoid manually renaming or moving them.
- Each paper consists of a PDF + MD pair with the same name. The MD file contains bibliographic information (authors, year, DOI, etc.).

---

## 简体中文

### library — 论文库（存储目录）

此文件夹对应 `config.yaml` 中 **`paths.library_root`** 的设定路径。

### 用途

导入的论文以 **PDF 和 MD（含 YAML front matter）配对**的形式保存在此处。

### 自动生成的内容（请勿手动创建）

应用会根据需要自动生成以下内容：

| 自动生成项 | 说明 |
|-----------|------|
| `A/` 至 `Z/`、`#/` | 按第一作者姓氏首字母分类的子文件夹，论文会被自动分配到对应文件夹（`#` 用于非英文字母） |
| `未整理/` | 元数据获取失败的论文的暂存位置 |
| `.collections/` | 集合（按写作项目分组的论文集）的 YAML 定义文件 |

### 注意事项

- 此文件夹中的文件由**应用统一管理**，请勿手动重命名或移动。
- 每篇论文由同名的 PDF + MD 文件组成。MD 文件中记录了文献信息（作者、年份、DOI 等）。

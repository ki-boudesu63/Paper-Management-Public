# inbox — 取り込み待ちフォルダ（監視フォルダ）

`config.yaml` の **`paths.watch_folder`** に指定するフォルダです。

## 役割

新しく入手した論文PDFを**ここに置く（またはダウンロード先に指定する）**と、アプリが自動で取り込みます。

## 取り込みの流れ

1. PDF をこの `inbox/` に置く
2. アプリ（監視機能）が新規PDFを検知する
3. メタデータを取得（Chrome拡張から送信された情報、またはPDF内のDOIから CrossRef 照会）
4. Paperpile形式（`Author et al. YYYY - Title.pdf`）にリネーム
5. `library/` の頭文字フォルダへ振り分け、MD を同時生成
6. 取得失敗時は `library/未整理/` へ退避

## 注意

- 取り込みが完了すると PDF は `library/` へ移動します。**`inbox/` が空になるのが正常な状態**です。
- ダウンロード中の一時ファイル（`.crdownload` / `.part` / `.tmp`）はアプリが無視します。完全にダウンロードされてから取り込まれます。

---

## English

### inbox — Incoming Papers Folder (Watch Folder)

This is the folder specified by **`paths.watch_folder`** in `config.yaml`.

### Purpose

Place newly acquired paper PDFs **here (or set it as your download destination)**, and the app will automatically import them.

### Import Workflow

1. Place a PDF in this `inbox/` folder
2. The app (file watcher) detects the new PDF
3. Metadata is retrieved (from information sent by the Chrome extension, or by querying CrossRef using the DOI found in the PDF)
4. The file is renamed to Paperpile format (`Author et al. YYYY - Title.pdf`)
5. The file is sorted into the appropriate initial-letter subfolder under `library/`, and a corresponding MD file is generated
6. If metadata retrieval fails, the file is moved to `library/未整理/` (unsorted)

### Notes

- Once import is complete, the PDF is moved to `library/`. **An empty `inbox/` is the normal state.**
- Temporary download files (`.crdownload` / `.part` / `.tmp`) are ignored by the app. Files are only imported after the download is fully complete.

---

## 简体中文

### inbox — 待导入文件夹（监视文件夹）

此文件夹对应 `config.yaml` 中 **`paths.watch_folder`** 的设定路径。

### 用途

将新获取的论文 PDF **放入此处（或将其设为下载目标文件夹）**，应用会自动完成导入。

### 导入流程

1. 将 PDF 放入 `inbox/` 文件夹
2. 应用（文件监视功能）检测到新 PDF
3. 获取元数据（通过 Chrome 扩展发送的信息，或根据 PDF 中的 DOI 查询 CrossRef）
4. 按照 Paperpile 格式重命名文件（`Author et al. YYYY - Title.pdf`）
5. 将文件分类到 `library/` 下对应首字母的子文件夹中，并同时生成 MD 文件
6. 如果元数据获取失败，文件将被移至 `library/未整理/`（未分类）

### 注意事项

- 导入完成后，PDF 会被移至 `library/`。**`inbox/` 为空是正常状态。**
- 下载过程中的临时文件（`.crdownload` / `.part` / `.tmp`）会被应用忽略，只有在下载完全完成后才会进行导入。

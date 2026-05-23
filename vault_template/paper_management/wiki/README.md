# wiki — 論文知識ベース（概念層）

このフォルダは、論文ライブラリ（`library/`）を素材として AIエージェントが構築する
**知識ベースの上位層**です。

## 構成

- `concepts/` — 概念ページ。複数の論文に横断するトピック（手法・研究テーマ等）ごとに1ファイル。
  各ページは概念の説明＋関連論文への `[[リンク]]` を持つ。
- `index.md` — 概念ページの目次。

## 生成のしかた

このフォルダの中身は **AIエージェントが生成・更新**します。手動で書く必要はありません。

`paper_management` フォルダで Claude Code / Codex / Gemini いずれかのCLIを起動し、
「全論文を読んで関連リンクと概念ページを生成して」と指示してください。
See `paper_management/AI_AGENT_GUIDE.md` for details.

## 注意

- `concepts/` 配下のページと `index.md` はAIが管理します。
- 論文（`library/` のMD）には、AIが「## 関連論文」「## 関連概念」セクションを追記します。
- 論文の事実情報・PDFはAIによって改変されません。

---

## English

### wiki — Paper Knowledge Base (Concept Layer)

This folder is the **upper layer of the knowledge base** that AI agents build using the paper library (`library/`) as source material.

### Structure

- `concepts/` — Concept pages. One file per topic (methodology, research theme, etc.) that spans multiple papers. Each page contains a description of the concept and `[[links]]` to related papers.
- `index.md` — Table of contents for concept pages.

### How to Generate

The contents of this folder are **generated and updated by AI agents**. There is no need to write them manually.

Launch Claude Code / Codex / Gemini CLI in the `paper_management` folder and instruct it to "read all papers and generate related links and concept pages."
See `paper_management/AI_AGENT_GUIDE.md` for details.

### Notes

- Pages under `concepts/` and `index.md` are managed by AI.
- AI will append "## Related Papers" and "## Related Concepts" sections to paper MDs in `library/`.
- Factual information in papers and PDFs are never modified by AI.

---

## 简体中文

### wiki — 论文知识库（概念层）

此文件夹是 AI 代理以论文库（`library/`）为素材构建的**知识库上层结构**。

### 结构

- `concepts/` — 概念页面。每个跨多篇论文的主题（方法论、研究方向等）对应一个文件。每个页面包含概念说明及指向相关论文的 `[[链接]]`。
- `index.md` — 概念页面的目录。

### 生成方式

此文件夹的内容由 **AI 代理自动生成和更新**，无需手动编写。

在 `paper_management` 文件夹中启动 Claude Code / Codex / Gemini CLI，并指示其"阅读所有论文并生成关联链接和概念页面"。
详细说明请参阅 `paper_management/AI_AGENT_GUIDE.md`。

### 注意事项

- `concepts/` 下的页面和 `index.md` 由 AI 管理。
- AI 会在 `library/` 的论文 MD 中追加"## 相关论文"和"## 相关概念"章节。
- 论文的事实信息和 PDF 不会被 AI 修改。

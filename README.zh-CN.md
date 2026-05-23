# Paper Management

[日本語](README.md) | [English](README.en.md)

完全本地化的论文管理与写作辅助工具。
提供与 EndNote / Mendeley / Paperpile 相当的功能，采用无数据库的
**基于文件的架构（PDF + Markdown 配对）** 实现。

## 主要功能

### 应用主体（Web UI）
- **自动导入** — 将 PDF 放入监视文件夹，自动重命名为 Paperpile 格式（`作者 et al. 年份 - 标题.pdf`），并按第一作者姓氏首字母分类到对应文件夹
- **PDF + Markdown 并行存储** — 每篇论文以 PDF 和带 YAML 前置元数据的 MD 文件配对保存。MD 中嵌入 PDF 正文和图表，使 Obsidian 全文搜索可以匹配论文内容
- **元数据获取** — CrossRef API（DOI→文献信息）、PDF 内 DOI 自动提取、Chrome 扩展发送元数据
- **多字段搜索** — 跨作者、标题、摘要、笔记、年份、标签进行空格分隔 AND 搜索
- **合集** — 按写作项目将论文以引用方式分组（文件不会移动）
- **删除与重新扫描** — 从 UI 完全删除，以及对应用外文件更改进行库重新扫描
- **Obsidian 集成** — 通过 `obsidian://` URI 将笔记查看和全文搜索委托给 Obsidian
- **无 PDF 论文注册** — 仅通过 DOI 元数据注册论文，之后可附加 PDF

### AI 代理集成（应用外部，通过 AI 指示 MD 方式）
- **Wiki 链接生成** — 使用 AI 指示 MD，通过 Claude Code / Codex / Gemini CLI 生成论文间关联 wiki 链接、概念页面和目录
- **引用格式化** — 按照投稿规范为原稿中的 `[[论文链接]]` 编号并生成参考文献列表
- **样式生成** — AI 从 Author Guidelines 生成投稿样式定义
- **相关论文探索** — AI 从库中搜索相关论文并在原稿中插入引用链接

> 应用本身不包含 AI 功能或 API 密钥。用户直接使用各 AI CLI 执行 `vault_template` 中附带的 AI 指示 MD 文件。

## 运行环境

- Windows（主要目标）
- Obsidian（用于查看和搜索论文 MD）
- Google Chrome（使用论文重命名扩展时需要，可选）

> **使用发布版时无需安装 Python 或 uv。** 发布文件夹中附带的 `uv.exe` 会自动准备所需的 Python 和依赖包。
> 仅当从源代码进行开发时，才需要另行安装 Python 3.11 以上和 [uv](https://docs.astral.sh/uv/)。

## 设置

### 1. 运行设置脚本

双击 `セットアップ.bat`。以下步骤将自动执行：

- （仅首次）附带的 `uv.exe` 自动下载 Python
- 同步依赖包（`uv sync`）
- 从 `config.yaml.example` 创建 `config.yaml`

> 首次运行需要几分钟下载依赖包（PDF 解析库等，数百 MB 起）。第二次以后由于缓存会很快。
>
> ⚠️ **请勿将此文件夹放在 `C:\Program Files\` 目录下。** 由于缺少写入权限，安装会失败。请解压到可写入的位置，例如「文档」文件夹或 D 盘根目录。

### 2. 放置 Vault 文件夹

将 `vault_template/paper_management/` 整个文件夹复制到您的 **Obsidian Vault 根目录**。

```
<您的Vault>/
└── paper_management/
    ├── library/    ← 论文存储位置
    ├── styles/     ← 投稿样式定义
    ├── inbox/      ← 监视文件夹（将 PDF 放在此处）
    ├── wiki/       ← 知识库（由 AI 构建）
    ├── workspace/  ← 写作工作区（原稿模板与写作指南）
    └── AI_AGENT_GUIDE.md 等
```

### 3. 启动应用并配置路径

双击 `起動.bat` 启动服务器，浏览器将自动打开。

在"设置"界面中，使用"浏览"按钮配置以下文件夹：

| 设置项 | 选择的文件夹 |
|--------|-------------|
| 论文存储根目录 | `<Vault>/paper_management/library` |
| Vault 路径 | `<Vault>` 根目录 |
| 样式定义文件夹 | `<Vault>/paper_management/styles` |
| 监视文件夹 | `<Vault>/paper_management/inbox` |

### 4.（可选）安装 Chrome 扩展

在 `chrome://extensions` 启用开发者模式，然后点击"加载已解压的扩展程序"并选择 `paper rename/` 文件夹。

## 使用方法

### 启动

双击 `起動.bat` → 浏览器中打开 `http://127.0.0.1:12000`。
按 Ctrl+C 或关闭窗口即可停止。

### 导入论文

导入 PDF 时，系统会解析文献信息，重命名为 Paperpile 格式、按首字母分类到文件夹、并生成 MD 文件。

#### 方法 1：放入监视文件夹（最简单）

只需将 PDF 放入 `inbox`（监视文件夹）。如果 PDF 中包含 DOI，将自动从 CrossRef 获取文献信息。

#### 方法 2：从 Chrome 扩展发送元数据（适用于无 DOI 的 PDF）

1. 在 Chrome 中打开论文的网页
2. 在"论文重命名"扩展弹窗中点击"**发送**"按钮 → 元数据被临时存储在后端（10 分钟后过期）
3. **10 分钟内**将 PDF 放入 `inbox`，或使用"导入 PDF"按钮导入

#### 方法 3：手动导入

在"导入状态"界面中使用"导入 PDF"按钮，通过文件选择对话框选择并导入。

#### 无法获取元数据时

如果 PDF 没有 DOI 且未从 Chrome 扩展发送元数据，PDF 将被移至 `library` 的**"未整理"文件夹**，并在"导入状态"界面显示通知。

#### 方法 4：从 AI 代理 Deep Research 结果注册（批量 DOI 注册 API）

向 Claude Code 等 AI 代理发出"搜索关于○○的论文并注册"的指令，AI 通过 deep research 搜索相关论文，将找到的论文 DOI 发送到应用的 API，**以纯元数据条目（无 PDF）的形式批量注册**。

1. 保持应用运行（`http://127.0.0.1:12000`）
2. 在 `paper_management` 文件夹中启动 AI CLI，指定主题并请求注册
3. AI 识别 DOI 并发送到注册 API

直接使用 API：

- 端点：`POST http://127.0.0.1:12000/api/import/doi`
- 请求体（JSON）：`{"dois": ["10.xxxx/aaaa", "10.yyyy/bbbb"]}`
- 调用示例：

  ```bash
  curl -X POST http://127.0.0.1:12000/api/import/doi \
    -H "Content-Type: application/json" \
    -d '{"dois":["10.xxxx/example-doi-1","10.xxxx/example-doi-2"]}'
  ```

响应为每个 DOI 返回 `registered`（新注册）/ `duplicate`（已存在）/ `failed`（无效 DOI 或 CrossRef 未匹配）。文献信息通过 CrossRef API 获取。由于不注册 PDF 正文，如需要请稍后在检查器界面附加。

> AI 代理的详细步骤请参阅 `vault_template/paper_management/AI_AGENT_GUIDE.md` 中的"Paper Discovery and Automatic Registration (Deep Research)"章节。

### 管理论文

- **论文列表** — 通过字母导航栏（A-Z, #）筛选，多字段搜索缩小范围
- **检查器** — 点击论文查看文献信息、摘要和备注
- **在 Obsidian 中打开** — 点击按钮直接在 Obsidian 中打开笔记
- **合集** — 在"合集"界面按项目分组论文
- **删除** — 检查器中的"删除"可一次性删除 PDF、MD、资源文件夹和合集引用
- **重新扫描** — 使用工具栏的重新扫描按钮反映应用外的文件更改

### AI 代理知识库化与写作支持

在 `paper_management` 文件夹中启动 AI CLI（Claude Code / Codex / Gemini），下达任务指令。

- **Wiki 链接生成**："阅读所有论文，生成关联链接和概念页面"
- **样式生成**：提供 Author Guidelines 并说"创建样式定义"
- **引用格式化**：指定原稿并说"按投稿要求完成定稿"
- **相关论文探索**：指定原稿并说"搜索相关论文并添加引用链接"

详情请参阅 `vault_template/paper_management/AI_AGENT_GUIDE.md` 和 `workspace/論文執筆ガイド.md`。

## 已知限制与注意事项

- **在 Obsidian Web Viewer 中"在 Obsidian 中打开"无法使用。** `obsidian://` URI 不被 Web Viewer 处理，请使用普通 Web 浏览器访问本应用。
- **首次使用 Docling 时**，用于 PDF 正文和图表提取的机器学习模型（约 1.3GB）会自动下载。可通过 `config.yaml` 中的 `import_settings.extract_full_text: false` 禁用正文提取。
- **监视文件夹的自动检测**在 Windows + Google Drive 同步环境下偶尔可能不稳定。此时请使用"导入 PDF"按钮进行手动导入。

## 常见问题（FAQ）

### 将多个 PDF 放入监视文件夹会怎样？

**将按顺序逐一处理**（非并行）。内部进行了串行化处理，因此即使大量放入也不会使 CPU 过载，但处理时间与文件数量成正比（正文和图表提取每篇论文约需 10-60 秒）。批量导入时如需加速，可在 `config.yaml` 中设置 `import_settings.extract_full_text: false` 跳过正文提取。

### 可以在多台电脑上使用吗？

**可以。** 应用本身只是代码，所有论文数据（PDF、MD、合集、wiki 等）都是 Obsidian Vault 内的文件。将 Vault 放在 Google Drive 等云端即可在各 PC 间同步。

在其他电脑上，只需"克隆/解压应用 → 运行 `セットアップ.bat` → 将 `config.yaml` 中的各路径调整为该电脑上 Vault 的位置"即可在相同环境中工作（由于云端挂载路径因电脑而异，`config.yaml` 需在每台电脑上单独配置）。

Warning: 为避免同步冲突和数据损坏，**请勿在多台电脑上同时编辑同一个 Vault**。请逐台使用。

### CrossRef 设置中的"联系邮箱"应该填写吗？

**建议填写**（非必填）。

本应用在通过 DOI 获取文献信息时会使用 CrossRef API。在设置界面的"联系邮箱"
字段中填入邮箱地址后，API 请求会附带 `mailto:` 信息，并被分配到 CrossRef 的
**polite pool（优待池）**。这样即使在繁忙时段，响应也会更稳定、更快速。

- 该邮箱**不是 CrossRef 的账号注册**。只需在字段中填写并保存即可。
- 它并非用于身份验证，而是 CrossRef 在出现大量访问时联系您的渠道。
- 即使留空 CrossRef 也可使用（public pool），但无法享受 polite pool 的优待。

## 卸载

本应用以**单一文件夹**形式运行，不会写入注册表或开始菜单。卸载只需删除该文件夹即可。

### 步骤

1. 如果应用正在运行，请关闭 `起動.bat` 窗口
2. （仅当希望保留数据时）将 Obsidian Vault 中的 `paper_management/` 文件夹备份到其他位置
3. **在资源管理器中删除整个发布文件夹**（`.venv` 和 `config.yaml` 都在其中，将一同被删除）
4. （可选）如果安装了 Chrome 扩展，请在 `chrome://extensions` 中删除「论文重命名」

### 注意

- Obsidian Vault 中的 `paper_management/` 文件夹存放着**您的论文数据（PDF、MD、集合）**。仅当希望连同应用一起丢弃这些数据时，才手动删除该文件夹。
- `config.yaml`（您的设置）位于发布文件夹内，会随文件夹一起被删除。下次设置时，`セットアップ.bat` 会自动重新生成。

### 完全清理（可选、面向高级用户）

如果您还想删除附带的 `uv.exe` 自动下载的 Python 及依赖包缓存，请在 PowerShell 中运行:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\uv"
```

⚠️ **如果您还在其他应用中使用 `uv`，请不要执行此命令**——该目录是共享的。

## 技术架构

- **后端**：Python 3.11+ / FastAPI / Jinja2 + htmx（无需 SPA 的局部更新）
- **架构**：六边形架构（端口与适配器）
  - `src/domain/` — 领域模型（无外部依赖的纯 Python）
  - `src/adapters/` — 文件系统、CrossRef、文件夹监视
  - `src/application/` — 导入、库管理、合集服务
  - `src/web/` — FastAPI 应用、路由、模板
- **PDF 处理**：pypdf（DOI 提取）、Docling（正文与图表 Markdown 化）— 均为 MIT 许可证
- **数据**：无数据库。论文以 `PDF + MD` 配对存储，合集以 YAML 文件保存
- **测试**：515 项（pytest），全部通过，ruff 无警告

## 开发

```
uv run pytest          # 运行测试（515 项）
uv run ruff check .    # 静态分析
uv run ruff format .   # 格式化
```

## 许可证

Apache License 2.0 — 请参阅 `LICENSE` 文件。

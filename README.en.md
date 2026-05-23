# Paper Management

[日本語](README.md) | [简体中文](README.zh-CN.md)

A fully local paper management and writing support tool.
It provides functionality equivalent to EndNote / Mendeley / Paperpile using a
**file-based architecture (PDF + Markdown pairs)** with no database.

## Key Features

### Main Application (Web UI)
- **Auto-import** — Drop a PDF into the watch folder and it will be renamed to Paperpile format (`Author et al. Year - Title.pdf`) and sorted into an alphabetical folder by the first author's initial
- **PDF + Markdown parallel storage** — Each paper is stored as a PDF paired with a YAML front-matter Markdown file. The MD includes the full text and figures from the PDF, enabling Obsidian full-text search to match paper contents
- **Metadata retrieval** — CrossRef API (DOI to bibliographic info), automatic DOI extraction from PDFs, and metadata submission from the Chrome extension
- **Multi-field search** — Cross-searches author, title, abstract, notes, year, and tags with space-separated AND queries
- **Collections** — Group papers by writing project as references (files are not moved)
- **Delete & rescan** — Full deletion from the UI, and library rescan for file changes made outside the app
- **Obsidian integration** — Delegates note viewing and full-text search to Obsidian via `obsidian://` URIs
- **Register papers without PDF** — Register papers with DOI metadata only, and attach PDFs later

### AI Agent Integration (External to app, via AI instruction MD)
- **Wiki-link generation** — Use AI instruction MD to generate inter-paper wiki-links, concept pages, and tables of contents with Claude Code / Codex / Gemini CLI
- **Citation formatting** — Number `[[paper links]]` in a manuscript according to submission guidelines and generate a reference list
- **Style generation** — AI generates submission style definitions from Author Guidelines
- **Related paper discovery** — AI searches the library for related papers and inserts citation links into manuscripts

> The app itself has no AI functionality or API keys. Users execute the AI instruction MD files bundled in `vault_template` directly with their AI CLI of choice.

## System Requirements

- Windows (primary target)
- Obsidian (for viewing and searching paper MDs)
- Google Chrome (optional, for the paper renamer extension)

> **You do not need to install Python or uv to use the distributed package.** The bundled `uv.exe` inside the distribution folder automatically provides the required Python and dependencies.
> Python 3.11+ and [uv](https://docs.astral.sh/uv/) are only needed if you develop from the source code.

## Setup

### 1. Run the Setup Script

Double-click `セットアップ.bat`. The following steps are performed automatically:

- (First run only) The bundled `uv.exe` downloads Python automatically
- Sync dependencies (`uv sync`)
- Create `config.yaml` from `config.yaml.example`

> The first run takes a few minutes to download dependencies (PDF parsing libraries, etc., several hundred MB and up). Later runs are fast thanks to the cache.
>
> ⚠️ **Do not place this folder under `C:\Program Files\`.** Installation will fail there due to missing write permissions. Extract it to a writable location such as your Documents folder or the root of the D: drive.

### 2. Place the Vault Folder

Copy the entire `vault_template/paper_management/` folder to the **root of your Obsidian Vault**.

```
<your-vault>/
└── paper_management/
    ├── library/    ← Paper storage
    ├── styles/     ← Submission style definitions
    ├── inbox/      ← Watch folder (drop PDFs here)
    ├── wiki/       ← Knowledge base (built by AI)
    ├── workspace/  ← Writing workspace (manuscript templates & writing guide)
    └── AI_AGENT_GUIDE.md etc.
```

### 3. Launch the App and Configure Paths

Double-click `起動.bat` to start the server and automatically open the browser.

In the "Settings" screen, use the "Browse" buttons to configure the following folders:

| Setting | Folder to Select |
|---------|-----------------|
| Paper storage root | `<Vault>/paper_management/library` |
| Vault path | `<Vault>` root |
| Style definitions folder | `<Vault>/paper_management/styles` |
| Watch folder | `<Vault>/paper_management/inbox` |

### 4. (Optional) Install the Chrome Extension

Enable Developer Mode at `chrome://extensions`, then click "Load unpacked" and select the `paper rename/` folder.

## Usage

### Launch

Double-click `起動.bat` → `http://127.0.0.1:12000` opens in your browser.
Press Ctrl+C or close the window to shut down.

### Importing Papers

When a PDF is imported, bibliographic information is resolved and the file is renamed to Paperpile format, sorted into an alphabetical folder, and an MD file is generated.

#### Method 1: Drop into the Watch Folder (Easiest)

Simply place a PDF in `inbox` (the watch folder). If the PDF contains a DOI, bibliographic information is automatically retrieved from CrossRef.

#### Method 2: Send Metadata from the Chrome Extension (Works for PDFs without DOI)

1. Open the paper's webpage in Chrome
2. Click "**Send**" in the "Paper Renamer" extension popup → metadata is temporarily stored in the backend (expires in 10 minutes)
3. **Within 10 minutes**, place the PDF in `inbox` or use the "Import PDF" button

#### Method 3: Manual Import

Use the "Import PDF" button on the "Import Status" screen to select and import files via a file dialog.

#### When Metadata Cannot Be Retrieved

If the PDF has no DOI and no metadata was sent from the Chrome extension, the PDF is moved to the **"Unsorted" folder** in `library` and a notification appears on the "Import Status" screen.

#### Method 4: Register from AI Agent Deep Research Results (Batch DOI Registration API)

Ask an AI agent like Claude Code to "search for papers about X and register them." The AI performs deep research to find related papers and sends their DOIs to the app's API to **batch-register them as metadata-only entries (without PDF)**.

1. Keep the app running (`http://127.0.0.1:12000`)
2. Launch an AI CLI in the `paper_management` folder and request registration with a topic
3. The AI identifies DOIs and sends them to the registration API

To use the API directly:

- Endpoint: `POST http://127.0.0.1:12000/api/import/doi`
- Request body (JSON): `{"dois": ["10.xxxx/aaaa", "10.yyyy/bbbb"]}`
- Example call:

  ```bash
  curl -X POST http://127.0.0.1:12000/api/import/doi \
    -H "Content-Type: application/json" \
    -d '{"dois":["10.xxxx/example-doi-1","10.xxxx/example-doi-2"]}'
  ```

The response returns `registered` (new) / `duplicate` (existing) / `failed` (invalid DOI or no CrossRef match) for each DOI. Bibliographic information is retrieved from the CrossRef API. Since PDF content is not registered, attach it later from the inspector screen as needed.

> For detailed AI agent instructions, see the "Paper Discovery and Automatic Registration (Deep Research)" section in `vault_template/paper_management/AI_AGENT_GUIDE.md`.

### Managing Papers

- **Paper list** — Filter by alphabetical rail (A-Z, #), narrow down with multi-field search
- **Inspector** — Click a paper to view bibliographic info, abstract, and memo
- **Open in Obsidian** — Button click opens the note directly in Obsidian
- **Collections** — Group papers by project on the "Collections" screen
- **Delete** — "Delete" in the inspector removes the PDF, MD, asset folder, and collection references at once
- **Rescan** — Use the rescan button in the toolbar to reflect file changes made outside the app

### AI Agent Knowledge Base & Writing Support

Launch an AI CLI (Claude Code / Codex / Gemini) in the `paper_management` folder and give instructions.

- **Wiki-link generation**: "Read all papers and generate related links and concept pages"
- **Style generation**: Provide Author Guidelines and say "Create a style definition"
- **Citation formatting**: Specify a manuscript and say "Finalize for submission"
- **Related paper discovery**: Specify a manuscript and say "Find related papers and add citation links"

For details, see `vault_template/paper_management/AI_AGENT_GUIDE.md` and `workspace/論文執筆ガイド.md`.

## Known Limitations & Notes

- **"Open in Obsidian" does not work inside Obsidian Web Viewer.** The `obsidian://` URI is not processed by the Web Viewer; use a regular web browser for this app.
- **On first use of Docling**, the machine learning models (~1.3 GB) used for full-text and figure extraction from PDFs are automatically downloaded. You can disable full-text extraction with `import_settings.extract_full_text: false` in `config.yaml`.
- **Watch folder auto-detection** may occasionally be unstable on Windows with Google Drive sync. In that case, use the "Import PDF" button for manual import.

## FAQ

### What happens if I put multiple PDFs in the watch folder?

**They are processed one at a time sequentially** (not in parallel). Processing is serialized internally, so even large batches won't overwhelm the CPU, but processing time scales with the number of files (full-text and figure extraction takes approximately 10-60 seconds per paper). To speed up bulk imports, set `import_settings.extract_full_text: false` in `config.yaml` to skip full-text extraction.

### Can I use this on multiple PCs?

**Yes.** The app itself is code only, and all paper data (PDF, MD, collections, wiki, etc.) are files within the Obsidian Vault. If you place the Vault in a cloud service like Google Drive, it will sync across PCs.

On other PCs, simply "clone/extract the app → run `セットアップ.bat` → adjust the paths in `config.yaml` to match the Vault location on that PC" to work in the same environment (since cloud mount points differ between PCs, `config.yaml` is configured per PC).

Warning: To avoid sync conflicts and corruption, **do not edit the same Vault simultaneously on multiple PCs**. Use one PC at a time.

### Should I set the "Contact Email" in CrossRef settings?

**It is recommended** (but not required).

This app uses the CrossRef API to retrieve bibliographic information from DOIs.
When you enter an email address in the "Contact Email" field on the settings screen,
a `mailto:` value is attached to API requests, and they are routed to CrossRef's
**polite pool**. This keeps responses stable and fast even when CrossRef is busy.

- The email is **not an account registration** with CrossRef. You just type it into the field and save.
- It is not for authentication; it is a contact point so CrossRef can reach you in case of heavy access.
- CrossRef still works with the field empty (public pool), but you won't get the polite pool benefits.

## Uninstall

This app runs as a **single folder** with no registry or Start Menu entries. Uninstalling is just deleting the folder.

### Steps

1. If the app is running, close the `起動.bat` window
2. (Optional, only if you want to keep your data) Back up the `paper_management/` folder inside your Obsidian Vault
3. **Delete the entire distribution folder from Explorer** (`.venv` and `config.yaml` are inside, so they go with it)
4. (Optional) If you installed the Chrome extension, remove "Paper Renamer" from `chrome://extensions`

### Notes

- The `paper_management/` folder inside your Obsidian Vault holds **your paper data (PDFs, MDs, collections)**. Delete it manually only if you want to discard that data along with the app.
- `config.yaml` (your settings) lives inside the distribution folder and is removed together with it. The next time you set up, `セットアップ.bat` will regenerate it.

### Full Cleanup (Optional, Advanced)

To also remove the Python interpreter and dependency cache that the bundled `uv.exe` downloaded, run in PowerShell:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\uv"
```

⚠️ **Do not run this if you use `uv` for any other application** — that directory is shared.

## Technical Architecture

- **Backend**: Python 3.11+ / FastAPI / Jinja2 + htmx (partial updates without SPA)
- **Architecture**: Hexagonal (Ports & Adapters)
  - `src/domain/` — Domain models (pure Python with no external dependencies)
  - `src/adapters/` — File system, CrossRef, folder watching
  - `src/application/` — Import, library, and collection services
  - `src/web/` — FastAPI app, routes, templates
- **PDF processing**: pypdf (DOI extraction), Docling (full-text & figure Markdown conversion) — both MIT licensed
- **Data**: No database. Papers are stored as `PDF + MD` pairs; collections are saved as YAML files
- **Tests**: 515 tests (pytest), all passing, ruff clean

## Development

```
uv run pytest          # Run tests (515 tests)
uv run ruff check .    # Lint
uv run ruff format .   # Format
```

## License

Apache License 2.0 — See the `LICENSE` file.

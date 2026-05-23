# AI Agent Guide — Building a Knowledge Base from the Paper Vault

This file provides shared instructions for AI agents (Claude Code / Codex / Gemini CLI, etc.)
to organize the Paper Management app's Vault (`paper_management` folder)
into a **concept-layered knowledge base**.

When an AI CLI opens the `paper_management` folder, the agent references this file
through its own instruction file (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`).

---

## Your Role

You are an agent that organizes and nurtures the paper library into a
**progressive knowledge base** connected by inter-paper links and "concept pages."

## Vault Structure

- `library/` — Paper storage. Papers are organized under initial-letter folders (A–Z, `#`), each containing a PDF + MD pair.
  Each MD has a YAML frontmatter (`paper_id` / `title` / `authors` / `year` / `doi` /
  `tags` / `abstract` / `memo`, etc.) plus body text.
  **These paper MDs serve as the "source (primary information)" of the knowledge base.**
- `wiki/` — The upper layer of the knowledge base (you build and maintain this).
  - `wiki/concepts/` — Concept pages. One file per cross-paper topic.
  - `wiki/index.md` — Table of contents for concept pages.
- `styles/` `inbox/` — Out of scope for organization.

## Paper Discovery and Automatic Registration (Deep Research)

Procedure when asked to "find and register related papers" for a specific theme or research area.
(This is the paper-addition phase. The "Tasks" section below covers organizing already-registered papers.)

1. Use WebSearch or Deep Research capabilities to discover papers related to the theme.
2. Identify the **DOI** of each paper
   (A DOI starts with `10.` — obtain it from the paper's page, PubMed, publisher site, etc.).
3. Pass the identified DOIs to the Paper Management app's API in bulk.
   The app (local server) must be running.

   - Endpoint: `POST http://127.0.0.1:12000/api/import/doi`
   - Request body (JSON): `{"dois": ["10.xxxx/aaaa", "10.yyyy/bbbb"]}`
   - Example call:

     ```bash
     curl -X POST http://127.0.0.1:12000/api/import/doi \
       -H "Content-Type: application/json" \
       -d '{"dois":["10.xxxx/example-doi-1","10.xxxx/example-doi-2"]}'
     ```

4. The API fetches metadata (title, authors, year, journal, abstract, etc.) from CrossRef for each DOI
   and automatically registers it in `library/` as a metadata-only entry (no PDF).
5. Check the response for per-DOI results:

   - `registered` — Newly registered
   - `duplicate` — Already exists in the library (no duplicate registration)
   - `failed` — Invalid DOI format, or not found on CrossRef (`error` contains the reason)

### Strict Rules for Discovery and Registration

- PDF full text is not registered. If needed, attach it manually via the app interface after registration.
- Papers without a DOI cannot be registered. Always identify the DOI before submitting.
- Never submit guessed or fabricated DOIs. Only submit DOIs confirmed to exist.

---

## Tasks

### Task 1: Inter-Paper Related Links

Add a "## Related Papers" section at the end of each paper MD in `library/`,
listing strongly related papers as wikilinks in `[[paper-MD-filename]]` format.

### Task 2: Concept Page Generation (Concepts Layer)

1. Read all paper MDs under `library/`.
2. Extract **concepts, topics, methods, and research themes** that appear across multiple papers
   (e.g., "iPSC," "dental pulp regeneration," "mechanical stress").
3. Create/update `wiki/concepts/<lowercase-slug>.md` for each concept. Format:

   ```
   ---
   name: Concept name
   description: One-sentence summary
   type: concept
   status: full | stub
   ---

   # Concept Name

   (Description of the concept. Synthesize findings from multiple papers.)

   ## Related Papers
   - [[paper-MD-filename]] — Brief note on how this paper addresses the concept

   ## Related Concepts
   - [[concept-slug]]
   ```

   - `status`: Use `full` if two or more papers reference it and the content is substantial; use `stub` if only one paper mentions it or coverage is thin.
4. Add a "## Related Concepts" section at the end of each paper MD, linking to the concept pages
   the paper addresses via `[[concept-slug]]` (bidirectional links between papers and concepts).

### Task 3: Table of Contents (Index)

Create/update `wiki/index.md`, listing all concept pages in `wiki/concepts/`
organized by field, using `[[concepts/concept-slug]]` links.

## Strict Rules

- Do not alter factual information of papers (title, authors, year, DOI, body text).
- Additions to paper MDs are limited to "## Related Papers" and "## Related Concepts" sections.
  Do not break existing frontmatter values.
- Never touch PDF files. `inbox/` and `styles/` are out of scope.
- Write concept pages based on paper content. Do not fabricate information not found in the papers.
- If `wiki/` pages already exist, do not delete them entirely — supplement and update while avoiding duplication.
- Do not create uncertain relations or concepts (prioritize precision over noise).

## For Users: How to Run

Open an AI CLI in the `paper_management` folder and instruct it to
"read all papers and generate related links and concept pages."
This guide ensures consistent behavior across Claude Code / Codex / Gemini CLI.
Triggering from the app itself is not required — run directly from each CLI.

## Paper Writing Support

When asked for paper writing support (generating submission style definitions or
finalizing manuscripts for submission), read `workspace/論文執筆ガイド.md` and follow its instructions.

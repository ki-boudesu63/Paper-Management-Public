// content.js — Extract metadata from academic paper pages and send to background.js
// Supports citation_* meta tags (Google Scholar / Highwire Press standard)
// with fallback to DOI regex scanning for unsupported sites.

(function () {
  'use strict';

  try {
    // ================================================================
    // Helper: query meta tags (case-insensitive name match)
    // ================================================================

    const allMetas = [...document.querySelectorAll('meta[name]')];

    /**
     * Get the content of the first meta tag matching the given name.
     * @param {string} name - Meta tag name (case-insensitive)
     * @returns {string|null}
     */
    function getMeta(name) {
      const lower = name.toLowerCase();
      return allMetas.find(m => m.getAttribute('name')?.toLowerCase() === lower)
        ?.content?.trim() || null;
    }

    /**
     * Get all meta tag contents matching the given name.
     * @param {string} name - Meta tag name (case-insensitive)
     * @returns {string[]}
     */
    function getAllMeta(name) {
      const lower = name.toLowerCase();
      return allMetas
        .filter(m => m.getAttribute('name')?.toLowerCase() === lower)
        .map(m => m.content?.trim())
        .filter(Boolean);
    }

    // ================================================================
    // Helper: extract surname from author string
    // ================================================================

    /**
     * Parse an author string into {family, given}.
     * Handles three common citation_author formats:
     *   "Mizuno, Takahiro"  (Lastname, Firstname)    -> family="Mizuno"
     *   "Takahiro Mizuno"   (Firstname Lastname)     -> family="Mizuno"
     *   "Hamano S" / "Hamano SA"  (Lastname Initials) -> family="Hamano"
     * The "Lastname Initials" case is detected when the last token is a
     * short all-uppercase initials block; otherwise the last token is
     * treated as the surname.
     * @param {string} raw
     * @returns {{family: string, given: string}}
     */
    function parseAuthorName(raw) {
      raw = (raw || '').trim();
      if (!raw) return { family: '', given: '' };
      // "Lastname, Firstname"
      if (raw.includes(',')) {
        const parts = raw.split(',');
        return { family: parts[0].trim(), given: (parts[1] || '').trim() };
      }
      const parts = raw.split(/\s+/);
      if (parts.length === 1) return { family: parts[0], given: '' };
      const last = parts[parts.length - 1];
      // "Lastname Initials": last token is a short all-uppercase block
      // such as "S", "S.", "SA", "S.A." -> surname is everything before it.
      if (/^[A-Z]\.?([A-Z]\.?){0,3}$/.test(last)) {
        return { family: parts.slice(0, -1).join(' '), given: last };
      }
      // "Firstname ... Lastname"
      return { family: last, given: parts.slice(0, -1).join(' ') };
    }

    /**
     * Extract just the family name from an author string.
     * @param {string} name
     * @returns {string|null}
     */
    function extractSurname(name) {
      if (!name) return null;
      return parseAuthorName(name).family || null;
    }

    /**
     * Extract a 4-digit year (1900-2099) from a string.
     * @param {string} str
     * @returns {string|null}
     */
    function extractYear(str) {
      if (!str) return null;
      const m = str.match(/(19|20)\d{2}/);
      return m ? m[0] : null;
    }

    // ================================================================
    // Strategy 1: citation_* meta tags (primary)
    // ================================================================

    /**
     * Try to extract metadata from citation_* meta tags.
     * @returns {object|null} Metadata object or null if title not found
     */
    function extractFromCitationMeta() {
      const title = getMeta('citation_title');
      if (!title) return null;

      // Authors: citation_author (multiple tags) or citation_authors (single, semicolon-separated)
      let authorMetas = getAllMeta('citation_author');
      if (authorMetas.length === 0) {
        const combined = getMeta('citation_authors');
        if (combined) {
          authorMetas = combined.split(';').map(a => a.trim()).filter(Boolean);
        }
      }

      // Parse all authors into {family, given} pairs for backend
      const authors = authorMetas.map(parseAuthorName);

      const authorCount = authors.length;
      const firstAuthor = authorCount > 0 ? authors[0].family : null;

      const year =
        extractYear(getMeta('citation_date')) ||
        extractYear(getMeta('citation_publication_date')) ||
        extractYear(getMeta('citation_online_date'));

      const doi = getMeta('citation_doi');

      return { title, year, firstAuthor, authorCount, doi, authors, source: 'citation_meta' };
    }

    // ================================================================
    // Strategy 2: DOM-based extraction (PubMed-specific fallback)
    // ================================================================

    /**
     * Try PubMed-specific DOM selectors as fallback.
     * @returns {object|null}
     */
    function extractFromPubMedDOM() {
      // Only on PubMed
      if (!location.hostname.includes('pubmed.ncbi.nlm.nih.gov')) return null;

      const titleEl = document.querySelector('.heading-title');
      const title = titleEl?.textContent?.trim();
      if (!title) return null;

      const domAuthors = [...document.querySelectorAll('.authors-list .full-name, .inline-authors a')]
        .map(el => el.textContent.trim())
        .filter(Boolean);

      const authorCount = domAuthors.length;
      const firstAuthor = extractSurname(domAuthors[0] || null);

      // Try to find year from the page
      const dateEl = document.querySelector('.cit');
      const year = dateEl ? extractYear(dateEl.textContent) : null;

      // Try DOI from the page
      const doiEl = document.querySelector('.id-link[data-ga-action="DOI"]');
      const doi = doiEl?.textContent?.trim() || null;

      return { title, year, firstAuthor, authorCount, doi, authors: [], source: 'pubmed_dom' };
    }

    // ================================================================
    // Strategy 3: DOI regex scan (last resort fallback)
    // ================================================================

    /**
     * Scan the page for a DOI pattern when no structured metadata found.
     * @returns {object|null}
     */
    function extractFromDOIScan() {
      // Check meta tags first (dc.identifier, DC.identifier, etc.)
      const dcIdentifier = getMeta('dc.identifier') || getMeta('DC.identifier');
      if (dcIdentifier) {
        const doiMatch = dcIdentifier.match(/10\.\d{4,9}\/[^\s]+/);
        if (doiMatch) {
          return {
            title: getMeta('dc.title') || getMeta('DC.title') || document.title || '',
            year: extractYear(getMeta('dc.date') || getMeta('DC.date') || ''),
            firstAuthor: extractSurname(getMeta('dc.creator') || getMeta('DC.creator') || ''),
            authorCount: 0,
            doi: doiMatch[0],
            authors: [],
            source: 'doi_scan',
          };
        }
      }

      // Scan visible text for DOI pattern (limit to reduce noise)
      const bodyText = (document.body?.innerText || '').substring(0, 50000);
      const doiRegex = /\b(10\.\d{4,9}\/[^\s<>"{}|\\^`[\]]+)\b/;
      const match = bodyText.match(doiRegex);
      if (match) {
        return {
          title: document.title || '',
          year: null,
          firstAuthor: null,
          authorCount: 0,
          doi: match[1],
          authors: [],
          source: 'doi_scan',
        };
      }

      return null;
    }

    // ================================================================
    // Main: try strategies in order
    // ================================================================

    const metadata =
      extractFromCitationMeta() ||
      extractFromPubMedDOM() ||
      extractFromDOIScan();

    if (!metadata) return; // No metadata found, skip this page

    // Ensure title exists
    if (!metadata.title) return;

    chrome.runtime.sendMessage({
      type: 'PAPER_METADATA',
      metadata: metadata,
    });

  } catch (err) {
    console.error('[Paper Management] Metadata extraction error:', err);
  }
})();

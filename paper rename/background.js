'use strict';

// ================================================================
// Constants
// ================================================================

const MAX_CANDIDATES = 10;
const BACKEND_URL = 'http://127.0.0.1:12000/api/import/metadata';
const POST_TIMEOUT_MS = 5000;

// ================================================================
// State
// ================================================================

// Recent candidate list (max 10 entries)
let candidates = [];
// Selected index (candidates[selectedIndex] is used for download rename)
let selectedIndex = 0;

// ================================================================
// Message handler
// ================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  if (message.type === 'PAPER_METADATA') {
    addCandidate(message.metadata);
    // No longer auto-sends; user must click "送信" in the popup
    return false;
  }

  if (message.type === 'GET_CANDIDATES') {
    sendResponse({ candidates: candidates.slice(0, MAX_CANDIDATES), selectedIndex });
    return true;
  }

  if (message.type === 'SELECT_CANDIDATE') {
    if (message.index >= 0 && message.index < candidates.length) {
      selectedIndex = message.index;
    }
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'SEND_METADATA') {
    const idx = message.index;
    if (idx >= 0 && idx < candidates.length) {
      const entry = candidates[idx];
      if (entry.sendStatus === 'sending' || entry.sendStatus === 'sent') {
        // Already sending or sent — return current status without re-sending
        sendResponse({ ok: true, sendStatus: entry.sendStatus });
        return true;
      }
      entry.sendStatus = 'sending';
      entry.sendError = null;
      postMetadataToBackend(entry).then(() => {
        sendResponse({ ok: true, sendStatus: entry.sendStatus, sendError: entry.sendError });
      });
    } else {
      sendResponse({ ok: false, sendStatus: 'error', sendError: 'Invalid index' });
    }
    return true; // Keep sendResponse channel open for async
  }

  if (message.type === 'GET_SEND_STATUS') {
    sendResponse({ statuses: candidates.slice(0, MAX_CANDIDATES).map(c => ({
      title: c.title,
      sendStatus: c.sendStatus || 'unsent',
      sendError: c.sendError || null,
    }))});
    return true;
  }

  return false;
});

// ================================================================
// Candidate management (dedup, newest first)
// ================================================================

function addCandidate(metadata) {
  // Remove existing entries with the same DOI or title
  candidates = candidates.filter(c => {
    if (metadata.doi && c.doi === metadata.doi) return false;
    if (metadata.title && c.title === metadata.title) return false;
    return true;
  });

  candidates.unshift({
    ...metadata,
    addedAt: Date.now(),
    sendStatus: 'unsent',
    sendError: null,
  });
  if (candidates.length > MAX_CANDIDATES) candidates = candidates.slice(0, MAX_CANDIDATES);
  selectedIndex = 0; // Auto-select newest
  console.log('[Paper Management] Candidate added:', candidates[0]);
}

// ================================================================
// POST metadata to backend
// ================================================================

/**
 * Send metadata to the backend via HTTP POST.
 * Called only when the user clicks "送信" in the popup.
 * @param {object} entry - Candidate entry from the candidates array
 */
async function postMetadataToBackend(entry) {
  const payload = {
    title: entry.title || '',
    doi: entry.doi || null,
    year: entry.year ? parseInt(entry.year, 10) : null,
    first_author: entry.firstAuthor || null,
    author_count: entry.authorCount || 0,
    authors: entry.authors || [],
    source: entry.source || 'unknown',
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), POST_TIMEOUT_MS);

    const response = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      entry.sendStatus = 'sent';
      entry.sendError = null;
      console.log('[Paper Management] Metadata sent to backend:', payload.title);
    } else {
      const errorText = await response.text().catch(() => 'Unknown error');
      entry.sendStatus = 'error';
      entry.sendError = `HTTP ${response.status}: ${errorText}`;
      console.warn('[Paper Management] Backend returned error:', response.status, errorText);
    }
  } catch (err) {
    entry.sendStatus = 'error';
    entry.sendError = err.message || 'Network error';
    console.warn('[Paper Management] Failed to send metadata to backend:', err.message);
  }
}

// ================================================================
// Download rename (Paperpile format)
// ================================================================

chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
  const isPdf =
    (downloadItem.filename && downloadItem.filename.toLowerCase().endsWith('.pdf')) ||
    (downloadItem.mime && downloadItem.mime.toLowerCase().includes('pdf'));

  if (!isPdf) {
    suggest();
    return true;
  }

  const metadata = candidates[selectedIndex] || null;
  if (!metadata) {
    console.log('[Paper Management] No candidate, using original filename');
    suggest();
    return true;
  }

  const filename = buildFilename(metadata);
  console.log('[Paper Management] Rename:', filename);
  suggest({ filename, conflictAction: 'uniquify' });
  return true;
});

// ================================================================
// Filename generation (Paperpile format)
// ================================================================

function sanitize(str, maxLen = 200) {
  if (!str) return 'Unknown';
  return str
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
    .replace(/_{2,}/g, '_')
    .replace(/^_+|_+$/g, '')
    .substring(0, maxLen) || 'Unknown';
}

function buildFilename(metadata) {
  const surname = sanitize(metadata.firstAuthor || 'Unknown', 50);
  const authorPart = (metadata.authorCount > 1)
    ? `${surname} et al.`
    : surname;
  const year = metadata.year || 'Unknown';
  const title = sanitize(metadata.title || 'Unknown', 200);
  return `${authorPart} ${year} - ${title}.pdf`;
}

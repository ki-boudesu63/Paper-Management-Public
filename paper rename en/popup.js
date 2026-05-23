// popup.js — Display candidate list with selection and send status

'use strict';

document.addEventListener('DOMContentLoaded', () => {
  // Fetch candidate list and send statuses from background.js
  chrome.runtime.sendMessage({ type: 'GET_CANDIDATES' }, (candidateResp) => {
    if (chrome.runtime.lastError) {
      renderEmpty();
      return;
    }

    chrome.runtime.sendMessage({ type: 'GET_SEND_STATUS' }, (statusResp) => {
      if (chrome.runtime.lastError) {
        // Render without status info
        render(candidateResp.candidates || [], candidateResp.selectedIndex || 0, []);
        return;
      }
      render(
        candidateResp.candidates || [],
        candidateResp.selectedIndex || 0,
        statusResp.statuses || []
      );
    });
  });
});

/**
 * Render candidate cards (max 3 visible).
 * @param {Array} candidates - Candidate list
 * @param {number} selectedIdx - Currently selected index
 * @param {Array} statuses - Send status list from background
 */
function render(candidates, selectedIdx, statuses) {
  const container = document.getElementById('container');
  container.innerHTML = '';

  if (candidates.length === 0) {
    renderEmpty();
    return;
  }

  // Show up to 3 most recent candidates
  const items = candidates.slice(0, 3);
  items.forEach((meta, i) => {
    const card = document.createElement('div');
    card.className = 'card' + (i === selectedIdx ? ' selected' : '');

    // Author / year line
    const authorDiv = document.createElement('div');
    authorDiv.className = 'card-author';
    const authorText = meta.authorCount > 1
      ? `${meta.firstAuthor || 'Unknown'} et al.`
      : (meta.firstAuthor || 'Unknown');
    authorDiv.textContent = `${authorText} (${meta.year || 'Unknown'})`;
    card.appendChild(authorDiv);

    // Title (2-line clamp)
    const titleDiv = document.createElement('div');
    titleDiv.className = 'card-title';
    titleDiv.textContent = meta.title || '(No title)';
    card.appendChild(titleDiv);

    // Footer: button + send status badge
    const footer = document.createElement('div');
    footer.className = 'card-footer';

    // "Use" button
    const btn = document.createElement('button');
    btn.className = 'card-btn';
    btn.textContent = i === selectedIdx ? 'Selected' : 'Use';
    if (i !== selectedIdx) {
      btn.addEventListener('click', () => selectCandidate(i));
    }
    footer.appendChild(btn);

    // Send button
    const statusInfo = statuses[i] || { sendStatus: 'unsent' };
    const sendBtn = document.createElement('button');
    sendBtn.className = 'send-btn';
    const isSendable = statusInfo.sendStatus === 'unsent' || statusInfo.sendStatus === 'error';
    sendBtn.disabled = !isSendable;
    sendBtn.textContent = isSendable ? 'Send' : (statusInfo.sendStatus === 'sending' ? 'Sending...' : 'Sent');
    if (isSendable) {
      sendBtn.addEventListener('click', () => sendMetadata(i));
    }
    footer.appendChild(sendBtn);

    // Send status badge
    const badge = document.createElement('span');
    badge.className = 'send-badge ' + statusInfo.sendStatus;
    const statusLabels = {
      unsent: 'Not sent',
      sending: 'Sending',
      sent: 'Sent',
      error: 'Send failed',
    };
    badge.textContent = statusLabels[statusInfo.sendStatus] || 'Unknown';
    if (statusInfo.sendStatus === 'error' && statusInfo.sendError) {
      badge.title = statusInfo.sendError;
    }
    footer.appendChild(badge);

    card.appendChild(footer);
    container.appendChild(card);
  });
}

/**
 * Show empty state message.
 */
function renderEmpty() {
  const container = document.getElementById('container');
  container.innerHTML = '<div class="empty-msg">Open an academic paper page<br>to display candidates</div>';
}

/**
 * Select a candidate and refresh the view.
 * @param {number} index - Index to select
 */
function selectCandidate(index) {
  chrome.runtime.sendMessage({ type: 'SELECT_CANDIDATE', index }, () => {
    refreshView();
  });
}

/**
 * Send metadata for a specific candidate to the backend.
 * @param {number} index - Candidate index to send
 */
function sendMetadata(index) {
  chrome.runtime.sendMessage({ type: 'SEND_METADATA', index }, () => {
    refreshView();
  });
}

/**
 * Re-fetch candidates and statuses, then re-render.
 */
function refreshView() {
  chrome.runtime.sendMessage({ type: 'GET_CANDIDATES' }, (candidateResp) => {
    if (!candidateResp) return;
    chrome.runtime.sendMessage({ type: 'GET_SEND_STATUS' }, (statusResp) => {
      render(
        candidateResp.candidates || [],
        candidateResp.selectedIndex || 0,
        (statusResp && statusResp.statuses) || []
      );
    });
  });
}

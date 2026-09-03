const API = '';

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function fetchDocs() {
  try {
    const data = await fetchJson(`${API}/api/documents`);
    return data.documents || [];
  } catch {
    return [];
  }
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function copyToClipboard(text, successMsg = 'Copied to clipboard!') {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMsg, 'success');
    }).catch(() => fallbackCopy(text, successMsg));
  } else {
    fallbackCopy(text, successMsg);
  }
}

function fallbackCopy(text, successMsg) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand('copy');
    showToast(successMsg, 'success');
  } catch {
    showToast('Failed to copy', 'error');
  }
  document.body.removeChild(ta);
}

function copyCode(btn) {
  const pre = btn.closest('.code-block-wrapper')?.querySelector('pre code');
  if (!pre) return;
  const text = pre.innerText;
  copyToClipboard(text, 'Code copied!');
  const originalText = btn.textContent;
  btn.textContent = 'Copied!';
  btn.classList.add('copied');
  setTimeout(() => {
    btn.textContent = originalText;
    btn.classList.remove('copied');
  }, 2000);
}

function formatMarkdown(text) {
  if (!text) return '';

  // Extract and preserve code blocks first
  const codeBlocks = [];
  let formatted = text.replace(/```([a-zA-Z0-9_\-]+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    const language = lang ? escHtml(lang) : 'code';
    codeBlocks.push(
      `<div class="code-block-wrapper">` +
        `<div class="code-header">` +
          `<span class="code-lang">${language}</span>` +
          `<button class="copy-code-btn" onclick="copyCode(this)" title="Copy snippet">Copy</button>` +
        `</div>` +
        `<pre><code class="language-${language}">${escHtml(code.trim())}</code></pre>` +
      `</div>`
    );
    return placeholder;
  });

  // Escape HTML in the rest of the text
  formatted = escHtml(formatted);

  // Restore placeholders from escaping
  formatted = formatted.replace(/__CODE_BLOCK_(\d+)__/g, (match, id) => codeBlocks[Number(id)]);

  // Format headers
  formatted = formatted
    .replace(/^### (.*$)/gim, '<h4 class="md-h4">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 class="md-h3">$1</h3>')
    .replace(/^# (.*$)/gim, '<h2 class="md-h2">$1</h2>');

  // Format bold & italic
  formatted = formatted
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Format inline code
  formatted = formatted.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');

  // Format blockquotes
  formatted = formatted.replace(/^\> (.*$)/gim, '<blockquote class="md-quote">$1</blockquote>');

  // Format source citations inline: [Source N] or [Source N: Doc, Page P]
  formatted = formatted.replace(/\[Source (\d+)(?::\s*([^,\]]+)(?:,\s*(?:Page|p\.)\s*(\d+))?)?\]/gi, (m, idx, doc, page) => {
    const pageText = page ? ` p.${page}` : '';
    const label = doc ? `${doc}${pageText}` : `Source ${idx}`;
    return `<span class="source-inline" title="Document Reference">[src.${idx}: ${escHtml(label)}]</span>`;
  });

  // Format bullet lists
  formatted = formatted.replace(/^[\*\-] (.*$)/gim, '<li class="md-li">$1</li>');
  formatted = formatted.replace(/(<li class="md-li">.*<\/li>)/gms, '<ul class="md-ul">$1</ul>');
  // Clean duplicate nested <ul> wrappers
  formatted = formatted.replace(/<\/ul>\s*<ul class="md-ul">/g, '');

  // Format numbered lists
  formatted = formatted.replace(/^(\d+)\.\s+(.*$)/gim, '<li class="md-ol-li"><span class="ol-num">$1.</span> $2</li>');
  formatted = formatted.replace(/(<li class="md-ol-li">.*<\/li>)/gms, '<ol class="md-ol">$1</ol>');
  formatted = formatted.replace(/<\/ol>\s*<ol class="md-ol">/g, '');

  // Format paragraphs
  const paragraphs = formatted.split(/\n\s*\n/);
  formatted = paragraphs.map(p => {
    p = p.trim();
    if (!p) return '';
    if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') || p.startsWith('<div') || p.startsWith('<blockquote')) {
      return p;
    }
    return `<p class="md-p">${p.replace(/\n/g, '<br/>')}</p>`;
  }).join('');

  return formatted;
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${escHtml(message)}</span>`;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

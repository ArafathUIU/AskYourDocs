// ── Shared utilities across all pages ──────────────────────────────────────

const API = '';  // Same origin

async function fetchDocs() {
  try {
    const res = await fetch(`${API}/api/documents`);
    const data = await res.json();
    return data.documents || [];
  } catch {
    return [];
  }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[Source (\d+)\]/g, '<span style="color:var(--accent);font-weight:600;font-family:var(--font-mono);font-size:0.8em;">[src.$1]</span>')
    .replace(/^(\d+\.) /gm, '<br/><strong>$1</strong> ')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = escHtml(message);
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
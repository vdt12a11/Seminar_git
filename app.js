const $ = (s) => document.querySelector(s);
const dbId = localStorage.getItem('query-room-db') || crypto.randomUUID();
localStorage.setItem('query-room-db', dbId);
$('#session-id').textContent = dbId.slice(0, 8).toUpperCase();
const sqlEditor = $('#sql-editor');
const bugs = [
  ['empty_name', 'Tên rỗng được chấp nhận'],
  ['null_email', 'Email NULL được chấp nhận'],
  ['long_name', 'Tên vượt quá 30 ký tự'],
  ['orphan_enrollment', 'Khoá ngoại không được bảo vệ'],
  ['duplicate_enrollment', 'Đăng ký bị trùng'],
  ['trigger_drift', 'Trigger làm lệch số đếm'],
  ['over_capacity', 'Vượt quá sức chứa'],
];
sqlEditor.value = 'SELECT * FROM members;';
function updateLines() { $('#line-numbers').textContent = Array.from({ length: sqlEditor.value.split('\n').length }, (_, i) => i + 1).join('\n'); }
sqlEditor.addEventListener('input', updateLines); updateLines();
function headers() { return { 'Content-Type': 'application/json', 'X-Database-Id': dbId }; }
function renderBugs(status = {}) {
  const found = bugs.filter(([key]) => status[key]).length;
  $('#bug-count').textContent = `${found} / ${bugs.length}`;
  $('#bug-list').innerHTML = bugs.map(([key, label]) => `<div class="bug-item ${status[key] ? 'found' : ''}"><span class="bug-icon">${status[key] ? '✓' : '·'}</span><span>${label}</span></div>`).join('');
}
async function refreshSchema() {
  const response = await fetch('/api/state', { headers: headers() });
  const data = await response.json();
  $('#schema-list').innerHTML = data.schema.map(table => `<div class="schema-item"><div class="schema-name">${table.name}</div><div class="schema-cols">${table.columns.map(c => `<div><b class="${c.pk ? 'pk' : ''}">${c.name}</b> ${c.type || '—'}${c.pk ? ' · PK' : ''}</div>`).join('')}</div></div>`).join('');
  renderBugs(data.flaws);
}
function showResult(data) {
  const body = $('#result-body');
  if (data.error) {
    body.innerHTML = `<div class="result-error">SQLITE ERROR\n${escapeHtml(data.error)}</div>`;
    $('#result-caption').textContent = 'Truy vấn thất bại'; $('#result-meta').textContent = 'ERROR'; return;
  }
  if (data.columns.length) {
    body.innerHTML = data.rows.length ? `<table class="data-table"><thead><tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>${data.rows.map(row => `<tr>${data.columns.map(c => `<td class="${row[c] === null ? 'null-value' : ''}">${row[c] === null ? 'NULL' : escapeHtml(String(row[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<div class="result-message">Truy vấn thành công · 0 dòng</div>';
    $('#result-caption').textContent = `${data.rows.length} dòng`; $('#result-meta').textContent = `OK · ${data.rows.length} ROW${data.rows.length === 1 ? '' : 'S'}`;
  } else {
    body.innerHTML = `<div class="result-message">✓&nbsp; Thực thi thành công · ${data.changes} thay đổi trong phiên</div>`;
    $('#result-caption').textContent = 'Thực thi thành công'; $('#result-meta').textContent = 'OK · WRITE';
  }
  renderBugs(data.flaws);
}
function escapeHtml(value) { return value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
function formatQuery(sql) {
  let formatted = sql.trim().replace(/\s+/g, ' ');
  if (/^SELECT\b/i.test(formatted)) formatted = formatted.replace(/\s+FROM\s+/i, '\nFROM ');
  formatted = formatted
    .replace(/\s+(LEFT(?: OUTER)? JOIN|RIGHT(?: OUTER)? JOIN|INNER JOIN|FULL(?: OUTER)? JOIN|CROSS JOIN|JOIN)\s+/gi, '\n$1 ')
    .replace(/\s+ON\s+/gi, '\n  ON ')
    .replace(/\s+WHERE\s+/gi, '\nWHERE ')
    .replace(/\s+GROUP BY\s+/gi, '\nGROUP BY ')
    .replace(/\s+HAVING\s+/gi, '\nHAVING ')
    .replace(/\s+ORDER BY\s+/gi, '\nORDER BY ')
    .replace(/\s+LIMIT\s+/gi, '\nLIMIT ');
  if (/^INSERT\b/i.test(formatted)) formatted = formatted.replace(/\s+VALUES\s+/i, '\nVALUES ');
  if (/^UPDATE\b/i.test(formatted)) formatted = formatted.replace(/\s+SET\s+/i, '\nSET ');
  return formatted;
}
async function runQuery() {
  const button = $('#run-btn'); button.disabled = true; button.querySelector('span').textContent = 'Đang chạy…';
  try {
    const response = await fetch('/api/query', { method: 'POST', headers: headers(), body: JSON.stringify({ sql: sqlEditor.value }) });
    showResult(await response.json()); await refreshSchema();
  } catch { showResult({ error: 'Không kết nối được server. Hãy chạy python server.py trong thư mục project.' }); }
  finally { button.disabled = false; button.querySelector('span').textContent = 'Chạy truy vấn'; }
}
$('#run-btn').addEventListener('click', runQuery);
$('#reset-btn').addEventListener('click', () => { sqlEditor.value = ''; sqlEditor.focus(); updateLines(); });
document.querySelectorAll('[data-query]').forEach(btn => btn.addEventListener('click', () => { sqlEditor.value = formatQuery(btn.dataset.query); updateLines(); sqlEditor.focus(); }));
document.querySelectorAll('[data-library-tab]').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('[data-library-tab]').forEach(item => {
    const active = item === tab;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('[data-library-panel]').forEach(panel => {
    panel.hidden = panel.dataset.libraryPanel !== tab.dataset.libraryTab;
  });
}));
sqlEditor.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); runQuery(); } if (e.key === 'Tab') { e.preventDefault(); const start = sqlEditor.selectionStart; sqlEditor.setRangeText('  ', start, sqlEditor.selectionEnd, 'end'); updateLines(); } });
refreshSchema().catch(() => { $('#schema-list').innerHTML = '<div class="loading-line">Không kết nối được server. Chạy <code>python server.py</code> để bắt đầu.</div>'; });

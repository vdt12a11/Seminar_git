const $ = s => document.querySelector(s);
const editor = $('#sql-editor');
let state;
let busy = false;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localTime = value => new Date(value.replace(' ', 'T') + 'Z').toLocaleString('vi-VN');
const verdicts = {confirmed:'Đã xác nhận', needs_evidence:'Cần thêm bằng chứng', duplicate:'Đã ghi nhận trước đó'};
const hints = {
  'REQ-01': ['ID thành viên', 'Độ dài tên thực tế', 'Kết quả đọc cần có id, name; có thể thêm length(name). Nhập số ký tự thực tế vào giá trị quan sát. SQL cần khớp nguyên văn lệnh bạn đã chạy.'],
  'REQ-02': ['ID thành viên', 'Giá trị email quan sát', 'Kết quả đọc cần có id, email. Nếu quan sát thấy SQL NULL, nhập NULL (khác chuỗi ký tự có nội dung NULL). SQL cần khớp nguyên văn lệnh bạn đã chạy.'],
  'REQ-03': ['ID đăng ký', 'Bản ghi cha không tồn tại', 'Dùng LEFT JOIN tới cả members và workshops. Kết quả phải có id, member_id, workshop_id, m.id AS member_exists, w.id AS workshop_exists. Cột parent tương ứng phải là NULL để chứng minh thiếu bản ghi.'],
  'REQ-04': ['ID một đăng ký liên quan', 'Số đăng ký cùng cặp', 'Kết quả đọc cần liệt kê id, member_id, workshop_id của các đăng ký liên quan; hoặc nhóm theo member_id, workshop_id và đặt tên số đếm là copies. SQL cần khớp nguyên văn lệnh bạn đã chạy.'],
  'REQ-05': ['ID workshop', 'Số đăng ký thực tế', 'Đối chiếu cả workshops và enrollments. Kết quả cần có id (workshop), registered_count, actual_count (số đăng ký bạn tính được). Dùng đúng tên cột/alias này. SQL cần khớp nguyên văn lệnh bạn đã chạy.'],
  'REQ-06': ['ID workshop', 'Số đăng ký thực tế', 'Đối chiếu cả workshops và enrollments. Kết quả cần có id (workshop), capacity, actual_count (số đăng ký bạn tính được). Dùng đúng tên cột/alias này. SQL cần khớp nguyên văn lệnh bạn đã chạy.']
};
const evidencePrompts = {
  'REQ-01': 'Lọc riêng thành viên vi phạm bằng WHERE; trả về id, name và độ dài tên để chứng minh dòng cụ thể. Không SELECT toàn bảng.',
  'REQ-02': 'Dùng WHERE email IS NULL để lọc thành viên vi phạm; trả về id, name, email của dòng đó.',
  'REQ-03': 'LEFT JOIN enrollments với members và workshops, lọc dòng thiếu bản ghi cha bằng WHERE parent.id IS NULL; trả về id đăng ký, member_id, workshop_id và ID cha tìm được.',
  'REQ-04': 'Lọc cặp member_id + workshop_id bị trùng; trả về ID của các dòng enrollment liên quan và cả hai ID trong cặp.',
  'REQ-05': 'Đối chiếu mỗi workshop với enrollment bằng LEFT JOIN và GROUP BY; lọc số đếm lưu khác số dòng thực tế. Trả về id workshop, registered_count, actual_count.',
  'REQ-06': 'Đối chiếu mỗi workshop với enrollment bằng LEFT JOIN và GROUP BY; lọc số dòng thực tế lớn hơn capacity. Trả về id workshop, capacity, actual_count.'
};
const defaultEvidencePlaceholder = 'Viết SELECT có WHERE để lọc đúng dòng vi phạm và trả về ID cùng giá trị cần đối chiếu; không chỉ SELECT * cả bảng.';
$('#evidence-sql').placeholder = defaultEvidencePlaceholder;
editor.value = 'SELECT * FROM members;';
function updateLines() { $('#line-numbers').textContent = editor.value.split('\n').map((_, i) => i + 1).join('\n'); }
editor.addEventListener('input', updateLines); updateLines();
function setBusy(value) {
  busy = value;
  ['#run-btn', '#submit-report', '#reset-data'].forEach(s => $(s).disabled = value || !state);
}
async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Yêu cầu thất bại.');
  return result;
}
function showResult(data, id) {
  const body = $('#result-body');
  $('#result-caption').textContent = id ? `Nhật ký #${id}` : '';
  if (data.error) {
    body.innerHTML = `<div class="result-error">${escapeHtml(data.error)}</div>`;
    $('#result-meta').textContent = 'ERROR · ĐÃ LƯU NHẬT KÝ'; return;
  }
  if (data.columns.length) {
    body.innerHTML = data.rows.length ? `<table class="data-table"><thead><tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>${data.rows.map(r => `<tr>${data.columns.map(c => `<td class="${r[c] === null ? 'null-value' : ''}">${r[c] === null ? 'NULL' : escapeHtml(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<div class="result-message">Truy vấn thành công · 0 dòng</div>';
    $('#result-meta').textContent = `OK · ${data.rows.length} DÒNG${data.truncated ? ' · ĐÃ GIỚI HẠN HIỂN THỊ' : ''}`;
  } else {
    body.innerHTML = `<div class="result-message">Thực thi thành công · ${data.changes} thay đổi (bao gồm trigger).<br><br>Hãy kiểm chứng kết quả và nộp báo cáo nếu tìm thấy vi phạm.</div>`;
    $('#result-meta').textContent = 'OK · WRITE';
  }
}
function render() {
  $('#group-label').textContent = `NHÓM ${state.group}`;
  $('#session-id').textContent = state.session;
  $('#round-label').textContent = String(state.round).padStart(2, '0');
  $('#score').textContent = state.score;
  $('#schema-list').innerHTML = state.schema.map(t => `<div class="schema-item"><div class="schema-name">${escapeHtml(t.name)}</div><div class="schema-cols">${t.columns.map(c => `<div><b class="${c.pk ? 'pk' : ''}">${escapeHtml(c.name)}</b> ${escapeHtml(c.type)}${c.pk ? ' · PK' : ''}</div>`).join('')}</div></div>`).join('');
  $('#bug-count').textContent = `${state.discoveries.length} ĐÃ XÁC NHẬN`;
  $('#bug-list').innerHTML = state.discoveries.length ? state.discoveries.map(r => `<div class="discovery"><span>✓</span><div><b>${escapeHtml(r.title)}</b><small>${escapeHtml(r.report.requirement)} · Báo cáo #${r.id} · +100 điểm</small></div></div>`).join('') : '<p class="empty-copy">Chưa có phát hiện được xác nhận.<br>Đọc đặc tả và bắt đầu điều tra.</p>';
  $('#history-count').textContent = `${state.history.length} LẦN CHẠY`;
  $('#history-list').innerHTML = state.history.length ? [...state.history].reverse().map(h => `<details class="history-item"><summary><span>#${h.id} · ${h.result.error ? 'LỖI SQL' : h.is_write ? 'GHI DỮ LIỆU' : 'ĐỌC DỮ LIỆU'}</span><code>${escapeHtml(h.sql.slice(0, 70))}</code></summary><div class="history-content"><small>${escapeHtml(localTime(h.created))}</small><pre>${escapeHtml(h.sql)}</pre><p>${h.result.error ? escapeHtml(h.result.error) : `${h.result.rows.length} dòng trả về · ${h.result.changes} thay đổi`}</p><button type="button" class="secondary" data-view="${h.id}">Xem lại kết quả</button></div></details>`).join('') : '<p class="empty-copy">Lịch sử SQL sẽ xuất hiện tại đây.</p>';
  $('#reports-list').innerHTML = state.reports.length ? state.reports.map(r => {
    const writeSql = r.report.mutation_sql || state.history.find(h => h.id === Number(r.report.mutation_id))?.sql || 'Chưa lưu câu lệnh.';
    const readSql = r.report.evidence_sql || state.history.find(h => h.id === Number(r.report.evidence_id))?.sql || 'Chưa lưu câu lệnh.';
    return `<details class="submitted-report"><summary><span class="verdict ${r.verdict}">${verdicts[r.verdict]}</span><b>#${r.id} · ${escapeHtml(r.report.requirement)}</b><span>${escapeHtml(r.title || 'Báo cáo điều tra')}</span></summary><div class="history-content"><p>${escapeHtml(r.message)}</p><p><b>Bằng chứng:</b> câu thao tác #${escapeHtml(r.report.mutation_id)} → câu kiểm chứng #${escapeHtml(r.report.evidence_id)} · ID ${escapeHtml(r.report.target_id)} · Quan sát: ${escapeHtml(r.report.observed)}</p><p><b>SQL thao tác:</b></p><pre>${escapeHtml(writeSql)}</pre><p><b>SQL kiểm chứng:</b></p><pre>${escapeHtml(readSql)}</pre><p><b>Thực tế:</b> ${escapeHtml(r.report.actual)}</p><p><b>Kết luận:</b> ${escapeHtml(r.report.conclusion)}</p></div></details>`;
  }).join('') : '<p class="empty-copy">Báo cáo và phản hồi xác minh sẽ được lưu tại đây.</p>';
}
try { localStorage.removeItem('query_room_group'); localStorage.removeItem('query_room_recovery'); } catch (_) {}
function enterGame(data) {
  state = data;
  $('#group-gate').hidden = true;
  render();
  setBusy(false);
  $('#connection-status').textContent = '';
}
function showGate(data) {
  state = null;
  setBusy(false);
  $('#group-gate').hidden = false;
  $('#group-form').hidden = !!data.kicked;
  $('#back-to-groups').hidden = !data.kicked;
  $('#gate-foot').hidden = !!data.kicked;
  $('#gate-title').textContent = data.kicked ? 'Phiên đã bị loại' : 'Chọn nhóm của bạn';
  $('#gate-description').textContent = data.kicked
    ? 'Quản trị viên đã loại phiên này khỏi phòng chơi. Liên hệ giáo viên nếu cần hỗ trợ.'
    : 'Mỗi nhóm từ 1 đến 11 có một phiên điều tra riêng. Nhóm đã có người chơi không thể được chọn lại.';
  $('#gate-status').textContent = '';
  if (data.kicked) return;
  const selected = $('#group-select').value;
  $('#group-select').innerHTML = '<option value="">Chọn nhóm…</option>' + data.groups.map(g =>
    `<option value="${g.number}" ${g.active ? 'disabled' : ''}>Nhóm ${g.number}${g.active ? ' · đã có người chơi' : ' · còn trống'}</option>`).join('');
  if (data.groups.some(g => String(g.number) === selected && !g.active)) $('#group-select').value = selected;
}
async function refresh() {
  const data = await api('/api/state');
  if (!data.needs_group && !data.kicked) { enterGame(data); return; }
  showGate(data);
}
$('#group-form').addEventListener('submit', async event => {
  event.preventDefault();
  const group = Number($('#group-select').value);
  if (!group) return;
  $('#join-button').disabled = true;
  $('#gate-status').textContent = '';
  try {
    enterGame(await api('/api/join', {group}));
  } catch (error) { $('#gate-status').textContent = error.message; }
  finally { $('#join-button').disabled = false; }
});
$('#back-to-groups').addEventListener('click', async () => {
  const button = $('#back-to-groups');
  button.disabled = true;
  $('#gate-status').textContent = '';
  try {
    await api('/api/new-session', {});
    await refresh();
  } catch (error) { $('#gate-status').textContent = error.message; }
  finally { button.disabled = false; }
});
setInterval(async () => {
  if (!state) return;
  try {
    const heartbeat = await api('/api/heartbeat', {bug_count:state.discoveries.length});
    if (heartbeat.score !== state.score) await refresh();
  } catch (_) { try { await refresh(); } catch (_) {} }
}, 10000);
async function runQuery() {
  if (busy || !state) return;
  setBusy(true);
  try { const result = await api('/api/query', {sql:editor.value}); showResult(result, result.history_id); await refresh(); }
  catch (error) { showResult({error:error.message}); }
  finally { setBusy(false); }
}
$('#run-btn').addEventListener('click', runQuery);
$('#reset-btn').addEventListener('click', () => { editor.value = ''; updateLines(); editor.focus(); });
editor.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runQuery(); } });
document.querySelectorAll('[data-query]').forEach(b => b.addEventListener('click', () => { editor.value = b.dataset.query; updateLines(); editor.focus(); }));
$('#history-list').addEventListener('click', e => {
  const view = e.target.closest('[data-view]');
  if (view) { const h = state.history.find(h => h.id === Number(view.dataset.view)); showResult(h.result, h.id); $('#result-body').scrollIntoView({behavior:'smooth', block:'center'}); }
});
$('#requirement').addEventListener('change', () => {
  const hint = hints[$('#requirement').value];
  $('#target-label').textContent = hint?.[0] || 'ID bản ghi';
  $('#observed-label').textContent = hint?.[1] || 'Giá trị quan sát';
  $('#evidence-help').textContent = hint?.[2] || 'Dán nguyên văn hai câu SQL bạn đã chạy. Server đối chiếu chúng với nhật ký của phiên này.';
  $('#evidence-sql').placeholder = evidencePrompts[$('#requirement').value] || defaultEvidencePlaceholder;
  $('#observed').value = ''; $('#expected').value = ''; $('#report-feedback').textContent = '';
});
$('#report-form').addEventListener('submit', async e => {
  e.preventDefault(); if (busy || !state) return; setBusy(true);
  const payload = Object.fromEntries(['requirement','mutation-sql','evidence-sql','target-id','observed','expected'].map(id => [id.replaceAll('-', '_'), $('#' + id).value]));
  try {
    const result = await api('/api/reports', payload);
    $('#report-feedback').className = `feedback ${result.verdict}`;
    $('#report-feedback').textContent = `${verdicts[result.verdict]} — ${result.message}`;
    await refresh();
  } catch (error) { $('#report-feedback').className = 'feedback needs_evidence'; $('#report-feedback').textContent = error.message; }
  finally { setBusy(false); }
});
$('#reset-data').addEventListener('click', async () => {
  if (busy || !state || !window.confirm('Nạp lại dữ liệu mẫu và mở lượt điều tra mới? Dữ liệu SQL hiện tại sẽ được thay thế; báo cáo và điểm đã ghi nhận được giữ lại.')) return;
  setBusy(true);
  try {
    await api('/api/reset', {confirm:'reset'}); await refresh();
    $('#report-form').reset(); $('#requirement').dispatchEvent(new Event('change'));
    $('#result-body').innerHTML = '<div class="result-message">Đã nạp dữ liệu mẫu sạch. Bắt đầu lượt điều tra mới.</div>';
    $('#result-caption').textContent = ''; $('#result-meta').textContent = 'LƯỢT MỚI';
  } catch (error) { $('#connection-status').textContent = error.message; }
  finally { setBusy(false); }
});
refresh().then(() => setBusy(false)).catch(error => { $('#connection-status').textContent = `Không kết nối được: ${error.message}. Tải lại trang để thử lại.`; });

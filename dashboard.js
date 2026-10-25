const $ = selector => document.querySelector(selector);
let loading = false;
let wasLoggedIn = false;

async function request(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || 'Yêu cầu thất bại.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function showLogin(message = '') {
  $('#login-view').hidden = false;
  $('#dashboard-view').hidden = true;
  $('#logout').hidden = true;
  $('#login-error').textContent = message;
}

function render(data) {
  wasLoggedIn = true;
  $('#login-view').hidden = true;
  $('#dashboard-view').hidden = false;
  $('#logout').hidden = false;
  $('#updated-at').textContent = 'Cập nhật: ' + new Date(data.updated_at * 1000).toLocaleTimeString('vi-VN');
  $('#active-count').textContent = data.groups.filter(group => group.active).length;
  $('#online-count').textContent = data.groups.filter(group => group.online).length;
  $('#total-bugs').textContent = data.groups.reduce((sum, group) => sum + group.bug_count, 0);
  $('#leaderboard-body').innerHTML = data.groups.map(group => `<tr class="${group.active ? '' : 'empty-group'}">
    <td><span class="rank">${group.active ? String(group.rank).padStart(2, '0') : '—'}</span></td>
    <td><strong>Nhóm ${group.number}</strong></td>
    <td><span class="presence ${group.online ? 'online' : group.active ? 'away' : 'vacant'}">${group.online ? 'Đang làm' : group.active ? 'Mất kết nối · giữ chỗ' : 'Chưa chọn'}</span></td>
    <td><strong>${group.bug_count}</strong></td>
    <td>${group.active ? `<button type="button" class="kick-button" data-kick="${group.number}">Kick</button>` : '—'}</td>
  </tr>`).join('');
}

async function refresh() {
  if (loading) return;
  loading = true;
  try { render(await request('/api/dashboard')); $('#dashboard-status').textContent = ''; }
  catch (error) {
    if (error.status === 401) showLogin(wasLoggedIn ? 'Phiên quản trị đã hết hạn. Đăng nhập lại.' : '');
    else $('#dashboard-status').textContent = error.message;
  }
  finally { loading = false; }
}

$('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('#login-form button');
  button.disabled = true;
  $('#login-error').textContent = '';
  try {
    render(await request('/api/admin/login', {
      username: $('#admin-username').value, password: $('#admin-password').value
    }));
    $('#admin-password').value = '';
  } catch (error) { $('#login-error').textContent = error.message; }
  finally { button.disabled = false; }
});

$('#leaderboard-body').addEventListener('click', async event => {
  const button = event.target.closest('[data-kick]');
  if (!button) return;
  const group = Number(button.dataset.kick);
  if (!window.confirm(`Kick Nhóm ${group}? Nhóm sẽ được giải phóng và phiên hiện tại mất quyền truy cập.`)) return;
  button.disabled = true;
  try { render(await request('/api/admin/kick', {group})); $('#dashboard-status').textContent = `Đã kick Nhóm ${group}.`; }
  catch (error) { $('#dashboard-status').textContent = error.message; button.disabled = false; }
});

$('#logout').addEventListener('click', async () => {
  try { await request('/api/admin/logout', {}); } catch (_) {}
  showLogin();
});

refresh();
setInterval(refresh, 10000);

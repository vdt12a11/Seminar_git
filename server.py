"""Query Room: local investigation game. Python standard library only."""
from contextlib import closing
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import secrets
import sqlite3
import threading
import time

from game import TABLES, initialize, snapshot, execute_query, verify_report, public_history

ROOT = Path(__file__).parent
DATA = ROOT / 'data' / 'hotel-game-v1'
DATA.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
ADMIN_PASSWORD_FILE = ROOT / 'data' / 'admin-password.txt'
if os.environ.get('QUERY_ROOM_ADMIN_PASSWORD'):
    ADMIN_PASSWORD = os.environ['QUERY_ROOM_ADMIN_PASSWORD']
elif ADMIN_PASSWORD_FILE.exists():
    ADMIN_PASSWORD = ADMIN_PASSWORD_FILE.read_text(encoding='utf-8').strip()
else:
    ADMIN_PASSWORD = secrets.token_urlsafe(18)
    ADMIN_PASSWORD_FILE.write_text(ADMIN_PASSWORD, encoding='utf-8')
    print(f'Admin password generated in {ADMIN_PASSWORD_FILE}', flush=True)
ADMIN_SESSION_SECONDS = 8 * 60 * 60
ONLINE_SECONDS = 30


def journal():
    conn = sqlite3.connect(DATA / 'journal.sqlite3')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, round INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY, player TEXT, round INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP,
            sql TEXT, result TEXT, before_state TEXT, after_state TEXT, reads TEXT, writes TEXT);
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY, player TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP,
            payload TEXT, verdict TEXT, message TEXT, bug_key TEXT, title TEXT);
        CREATE TABLE IF NOT EXISTS groups (
            number INTEGER PRIMARY KEY CHECK(number BETWEEN 1 AND 11),
            player TEXT UNIQUE, active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1)),
            last_seen INTEGER);
        CREATE TABLE IF NOT EXISTS admin_sessions (token TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
    ''')
    if 'kicked' not in {r['name'] for r in conn.execute('PRAGMA table_info(players)')}:
        conn.execute('ALTER TABLE players ADD COLUMN kicked INTEGER NOT NULL DEFAULT 0')
    if 'recovery_code' in {r['name'] for r in conn.execute('PRAGMA table_info(groups)')}:
        conn.execute('UPDATE groups SET recovery_code=NULL WHERE recovery_code IS NOT NULL')
    conn.executemany('INSERT OR IGNORE INTO groups(number) VALUES (?)', [(n,) for n in range(1, 12)])
    conn.commit()
    return conn


def group_for(store, player_id):
    return store.execute('SELECT * FROM groups WHERE player=? AND active=1', (player_id,)).fetchone()


def bug_count(store, player_id):
    return store.execute("SELECT COUNT(DISTINCT bug_key) FROM reports WHERE player=? AND verdict='confirmed'", (player_id,)).fetchone()[0]


def group_list(store):
    return [{'number': row['number'], 'active': bool(row['active'])} for row in store.execute('SELECT number,active FROM groups ORDER BY number')]


class Handler(BaseHTTPRequestHandler):
    def cookie_value(self, name):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            return cookie[name].value if name in cookie else ''
        except Exception:
            return ''

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if getattr(self, 'new_cookie', False):
            self.send_header('Set-Cookie', f'query_room_game={self.player}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000')
        if getattr(self, 'clear_player_cookie', False):
            self.send_header('Set-Cookie', 'query_room_game=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
        if getattr(self, 'admin_cookie', None):
            self.send_header('Set-Cookie', self.admin_cookie)
        self.end_headers()
        self.wfile.write(body)

    def session(self, store):
        value = self.cookie_value('query_room_game')
        player = store.execute('SELECT * FROM players WHERE id=?', (value,)).fetchone()
        self.new_cookie = not bool(player)
        if not player:
            value = secrets.token_hex(24)
            store.execute('INSERT INTO players(id) VALUES (?)', (value,))
            store.commit()
            with closing(sqlite3.connect(DATA / f'{value}.sqlite3')) as conn:
                initialize(conn)
            player = store.execute('SELECT * FROM players WHERE id=?', (value,)).fetchone()
        self.player = value
        return player

    def admin_authorized(self, store):
        token = self.cookie_value('query_room_admin')
        if not token:
            return False
        row = store.execute('SELECT expires_at FROM admin_sessions WHERE token=?', (token,)).fetchone()
        return bool(row and row['expires_at'] > int(time.time()))

    def dashboard_state(self, store):
        now = int(time.time())
        rows = []
        for group in store.execute('SELECT * FROM groups ORDER BY number'):
            count = bug_count(store, group['player']) if group['active'] and group['player'] else 0
            rows.append({'number': group['number'], 'active': bool(group['active']),
                         'online': bool(group['active'] and group['last_seen'] and now - group['last_seen'] <= ONLINE_SECONDS),
                         'last_seen': group['last_seen'], 'bug_count': count, 'score': count * 100})
        rows.sort(key=lambda r: (-r['bug_count'], not r['active'], r['number']))
        for index, row in enumerate(rows, 1):
            row['rank'] = index
        return {'groups': rows, 'updated_at': now, 'online_seconds': ONLINE_SECONDS}

    def state(self, store, player, group):
        with closing(sqlite3.connect(DATA / f'{self.player}.sqlite3')) as conn:
            schema = [{'name': t, 'columns': [dict(zip(('cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'), c))
                       for c in conn.execute(f'PRAGMA table_info({t})')]} for t in TABLES]
        history = store.execute('SELECT * FROM history WHERE player=? AND round=? ORDER BY id',
                                (self.player, player['round'])).fetchall()
        reports = []
        for r in store.execute('SELECT * FROM reports WHERE player=? ORDER BY id DESC', (self.player,)):
            reports.append({'id': r['id'], 'created': r['created'], 'report': json.loads(r['payload']),
                            'verdict': r['verdict'], 'message': r['message'], 'title': r['title']})
        confirmed = [r for r in reports if r['verdict'] == 'confirmed']
        return {'session': self.player[:8].upper(), 'group': group['number'],
                'round': player['round'], 'schema': schema,
                'history': [public_history(r) for r in history], 'reports': reports,
                'discoveries': confirmed, 'score': bug_count(store, self.player) * 100}

    def do_GET(self):
        if self.path == '/api/state':
            with LOCK, closing(journal()) as store:
                player = self.session(store)
                if player['kicked']:
                    self.send_json(200, {'kicked': True})
                else:
                    group = group_for(store, self.player)
                    self.send_json(200, self.state(store, player, group) if group else
                                   {'needs_group': True, 'groups': group_list(store)})
            return
        if self.path == '/api/dashboard':
            with LOCK, closing(journal()) as store:
                if not self.admin_authorized(store):
                    self.send_json(401, {'error': 'Đăng nhập admin để xem dashboard.'})
                else:
                    self.send_json(200, self.dashboard_state(store))
            return
        path = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/app.css': 'app.css',
                '/dashboard': 'dashboard.html', '/dashboard.js': 'dashboard.js', '/dashboard.css': 'dashboard.css'}.get(self.path)
        if not path:
            self.send_error(404)
            return
        body = (ROOT / path).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[path.split('.')[-1]] + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in ('/api/query', '/api/reports', '/api/reset', '/api/join', '/api/heartbeat', '/api/new-session',
                             '/api/admin/login', '/api/admin/logout', '/api/admin/kick'):
            self.send_error(404)
            return
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.send_json(403, {'error': 'Yêu cầu phải đến từ trang minigame.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 40000:
                raise ValueError('Nội dung yêu cầu không hợp lệ hoặc quá dài.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Yêu cầu phải dùng JSON.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Nội dung yêu cầu phải là một đối tượng JSON.')
            with LOCK, closing(journal()) as store:
                if self.path == '/api/admin/login':
                    username, password = payload.get('username'), payload.get('password')
                    if not isinstance(username, str) or not isinstance(password, str) or not (
                        secrets.compare_digest(username, 'admin') and secrets.compare_digest(password, ADMIN_PASSWORD)
                    ):
                        self.send_json(401, {'error': 'Tên đăng nhập hoặc mật khẩu không đúng.'})
                        return
                    token = secrets.token_hex(32)
                    store.execute('DELETE FROM admin_sessions WHERE expires_at<=?', (int(time.time()),))
                    store.execute('INSERT INTO admin_sessions(token,expires_at) VALUES (?,?)',
                                  (token, int(time.time()) + ADMIN_SESSION_SECONDS))
                    store.commit()
                    self.admin_cookie = f'query_room_admin={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={ADMIN_SESSION_SECONDS}'
                    self.send_json(200, self.dashboard_state(store))
                    return
                if self.path.startswith('/api/admin/'):
                    if not self.admin_authorized(store):
                        self.send_json(401, {'error': 'Phiên admin đã hết hạn. Hãy đăng nhập lại.'})
                        return
                    if self.path == '/api/admin/logout':
                        store.execute('DELETE FROM admin_sessions WHERE token=?', (self.cookie_value('query_room_admin'),))
                        store.commit()
                        self.admin_cookie = 'query_room_admin=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
                        self.send_json(200, {'message': 'Đã đăng xuất.'})
                        return
                    number = payload.get('group')
                    if type(number) is not int or not 1 <= number <= 11:
                        raise ValueError('Chọn nhóm từ 1 đến 11.')
                    slot = store.execute('SELECT * FROM groups WHERE number=?', (number,)).fetchone()
                    if slot['active'] and slot['player']:
                        store.execute('UPDATE players SET kicked=1 WHERE id=?', (slot['player'],))
                    store.execute('UPDATE groups SET active=0, player=NULL, last_seen=NULL WHERE number=?', (number,))
                    store.commit()
                    self.send_json(200, self.dashboard_state(store))
                    return
                player = self.session(store)
                if self.path == '/api/new-session':
                    if not player['kicked']:
                        self.send_json(403, {'error': 'Chỉ phiên đã bị kick mới có thể quay lại chọn nhóm.'})
                        return
                    self.clear_player_cookie = True
                    self.send_json(200, {'message': 'Đã mở trang chọn nhóm. Phiên mới bắt đầu với dữ liệu mẫu.'})
                    return
                if player['kicked']:
                    self.send_json(403, {'error': 'Phiên này đã bị quản trị viên loại khỏi phòng chơi.'})
                    return
                group = group_for(store, self.player)
                if self.path == '/api/join':
                    number = payload.get('group')
                    if type(number) is not int or not 1 <= number <= 11:
                        raise ValueError('Chọn nhóm từ 1 đến 11.')
                    if group and group['number'] != number:
                        self.send_json(409, {'error': 'Phiên này đã thuộc một nhóm. Tải lại trang để tiếp tục.'})
                        return
                    slot = store.execute('SELECT * FROM groups WHERE number=?', (number,)).fetchone()
                    if slot['active'] and slot['player'] != self.player:
                        self.send_json(409, {'error': 'Nhóm này đã có người chơi. Nếu mất cookie, nhờ admin kick phiên cũ để giải phóng nhóm.'})
                        return
                    elif slot['active'] and slot['player'] == self.player:
                        store.execute('UPDATE groups SET last_seen=? WHERE number=?', (int(time.time()), number))
                        store.commit()
                        self.send_json(200, self.state(store, player, group_for(store, self.player)))
                        return
                    store.execute('UPDATE groups SET active=1, player=?, last_seen=? WHERE number=?',
                                  (self.player, int(time.time()), number))
                    store.commit()
                    player = store.execute('SELECT * FROM players WHERE id=?', (self.player,)).fetchone()
                    self.send_json(200, self.state(store, player, group_for(store, self.player)))
                    return
                if not group:
                    self.send_json(403, {'error': 'Hãy chọn nhóm trước khi chơi.'})
                    return
                if self.path == '/api/heartbeat':
                    store.execute('UPDATE groups SET last_seen=? WHERE number=? AND player=?',
                                  (int(time.time()), group['number'], self.player))
                    store.commit()
                    count = bug_count(store, self.player)
                    self.send_json(200, {'group': group['number'], 'bug_count': count, 'score': count * 100})
                    return
                if self.path == '/api/query':
                    sql = payload.get('sql', '')
                    if not isinstance(sql, str) or not sql.strip() or len(sql) > 6000:
                        raise ValueError('Nhập một câu SQL, tối đa 6000 ký tự.')
                    with closing(sqlite3.connect(DATA / f'{self.player}.sqlite3')) as conn:
                        before = snapshot(conn)
                        result, reads, writes = execute_query(conn, sql)
                        after = snapshot(conn)
                    cursor = store.execute('''INSERT INTO history
                        (player, round, sql, result, before_state, after_state, reads, writes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (self.player, player['round'], sql, json.dumps(result), json.dumps(before),
                         json.dumps(after), json.dumps(reads), json.dumps(writes)))
                    store.commit()
                    self.send_json(200, {**result, 'history_id': cursor.lastrowid})
                elif self.path == '/api/reports':
                    outcome = verify_report(store, self.player, player['round'], payload)
                    saved_payload = {key: payload.get(key) for key in
                                     ('requirement', 'mutation_sql', 'evidence_sql', 'target_id',
                                      'observed', 'expected')}
                    if outcome.get('mutation_ids'):
                        saved_payload['mutation_ids'] = outcome['mutation_ids']
                        saved_payload['evidence_id'] = outcome['evidence_id']
                    store.execute('''INSERT INTO reports (player,payload,verdict,message,bug_key,title)
                        VALUES (?,?,?,?,?,?)''', (self.player, json.dumps(saved_payload, ensure_ascii=False),
                        outcome['verdict'], outcome['message'], outcome.get('bug_key'), outcome.get('title', '')))
                    store.commit()
                    self.send_json(200, outcome)
                else:
                    if payload.get('confirm') != 'reset':
                        raise ValueError('Chưa xác nhận đặt lại dữ liệu.')
                    with closing(sqlite3.connect(DATA / f'{self.player}.sqlite3')) as conn:
                        initialize(conn, reset=True)
                    store.execute('UPDATE players SET round=round+1 WHERE id=?', (self.player,))
                    store.commit()
                    self.send_json(200, {'message': 'Đã nạp dữ liệu mẫu sạch. Báo cáo và điểm được giữ lại.'})
        except (ValueError, TypeError, sqlite3.Error, OSError) as exc:
            self.send_json(400, {'error': str(exc)})

    def log_message(self, *_args):
        pass


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Query Room investigation game: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

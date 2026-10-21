"""Server-owned evidence and deterministic validators; not browser assets."""
import json
import sqlite3

TABLES = ('members', 'workshops', 'enrollments')
RULES = {
    'empty_name': ('REQ-01', 'Tên rỗng được chấp nhận'),
    'long_name': ('REQ-01', 'Tên vượt quá 30 ký tự được lưu'),
    'null_email': ('REQ-02', 'Email NULL được chấp nhận'),
    'orphan_enrollment': ('REQ-03', 'Đăng ký không có bản ghi cha hợp lệ'),
    'duplicate_enrollment': ('REQ-04', 'Một thành viên đăng ký trùng workshop'),
    'trigger_drift': ('REQ-05', 'Số đếm không cập nhật theo đăng ký'),
    'over_capacity': ('REQ-06', 'Đăng ký vượt sức chứa'),
}


def initialize(conn, reset=False):
    if reset:
        conn.executescript('DROP TABLE IF EXISTS enrollments; DROP TABLE IF EXISTS members; DROP TABLE IF EXISTS workshops;')
    conn.executescript('''
        CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT,
                              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE workshops (id INTEGER PRIMARY KEY, title TEXT NOT NULL, capacity INTEGER NOT NULL,
                                registered_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE enrollments (id INTEGER PRIMARY KEY, member_id INTEGER, workshop_id INTEGER,
                                  enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TRIGGER enrollment_added AFTER INSERT ON enrollments BEGIN
            UPDATE workshops SET registered_count=registered_count+1 WHERE id=NEW.workshop_id;
        END;
        INSERT INTO members(name,email) VALUES ('An Nguyen','an@example.test'),
            ('Minh Tran','minh@example.test'), ('Linh Pham','linh@example.test');
        INSERT INTO workshops(title,capacity) VALUES ('Database Testing 101',2), ('SQL Clinic',12), ('Bug Hunt Lab',8);
    ''')
    conn.commit()


def snapshot(conn):
    conn.row_factory = sqlite3.Row
    return {t: [dict(r) for r in conn.execute(f'SELECT * FROM {t} ORDER BY id')] for t in TABLES}


def execute_query(conn, sql):
    reads, writes = set(), set()
    def authorize(action, table, column, db, source):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and table in TABLES and (db == 'main' or (db is None and column == '')):
            reads.add((table, column))
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_DENY if column.lower() in ('load_extension', 'writefile', 'readfile') else sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and table in TABLES and db == 'main':
            allowed = table in ('members', 'enrollments')
            if action == sqlite3.SQLITE_UPDATE and column == 'id':
                allowed = False
            if table == 'workshops':
                allowed = action == sqlite3.SQLITE_UPDATE and column in ('title', 'capacity')
                allowed |= action == sqlite3.SQLITE_UPDATE and column == 'registered_count' and source == 'enrollment_added'
            if allowed:
                writes.add(table)
                return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    conn.execute('BEGIN')
    conn.set_authorizer(authorize)
    budget = [0]
    def progress():
        budget[0] += 1
        return budget[0] > 3000
    conn.set_progress_handler(progress, 1000)
    if hasattr(conn, 'setlimit'):  # Python 3.11+; the classroom machine also has 3.10.
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100000)
    try:
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchmany(501)] if cur.description else []
        result = {'columns': [d[0] for d in cur.description] if cur.description else [],
                  'rows': rows[:500], 'truncated': len(rows) > 500, 'changes': conn.total_changes}
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        conn.set_progress_handler(None, 0)
        if any(conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] > 1000 for t in TABLES):
            raise ValueError('Mỗi bảng giới hạn 1000 bản ghi trong một lượt điều tra.')
        if any(isinstance(value, bytes) for table in [*snapshot(conn).values(), result['rows']] for row in table for value in row.values()):
            raise ValueError('Bản này chỉ hỗ trợ dữ liệu văn bản và số; không dùng BLOB.')
        if conn.execute("SELECT 1 FROM workshops WHERE typeof(capacity) != 'integer' OR capacity < 1 OR capacity > 1000").fetchone():
            raise ValueError('Sức chứa workshop phải là số nguyên từ 1 đến 1000.')
        conn.commit()
    except (sqlite3.Error, ValueError) as exc:
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        conn.set_progress_handler(None, 0)
        conn.rollback()
        message = str(exc)
        if 'authorized' in message or 'prohibited' in message:
            message = 'Chế độ chơi chỉ cho đọc và sửa dữ liệu nghiệp vụ. Cấu trúc, ID hiện có và số đếm hệ thống được bảo vệ.'
        result = {'error': message}
        writes.clear()
    return result, sorted(reads), sorted(writes)


def witnesses(state):
    """Canonical counterexamples from trusted snapshots, not player projections."""
    out = {k: {} for k in RULES}
    members = {r['id']: r for r in state['members']}
    workshops = {r['id']: r for r in state['workshops']}
    enrollments = state['enrollments']
    for r in members.values():
        if not r['name'].strip():
            out['empty_name'][r['id']] = r
        if len(r['name']) > 30:
            out['long_name'][r['id']] = r
        if r['email'] is None:
            out['null_email'][r['id']] = r
    for r in enrollments:
        if r['member_id'] not in members or r['workshop_id'] not in workshops:
            out['orphan_enrollment'][r['id']] = r
        copies = sum(e['member_id'] == r['member_id'] and e['workshop_id'] == r['workshop_id'] for e in enrollments)
        if copies > 1:
            out['duplicate_enrollment'][r['id']] = {**r, 'copies': copies}
    for r in workshops.values():
        actual = sum(e['workshop_id'] == r['id'] for e in enrollments)
        if r['registered_count'] != actual:
            out['trigger_drift'][r['id']] = {**r, 'actual_count': actual}
        if actual > r['capacity']:
            out['over_capacity'][r['id']] = {**r, 'actual_count': actual}
    return out


def public_history(row):
    return {'id': row['id'], 'sql': row['sql'], 'created': row['created'],
            'result': json.loads(row['result']), 'is_write': bool(json.loads(row['writes']))}


def verify_report(store, player, round_no, payload):
    def fail(message):
        return {'verdict': 'needs_evidence', 'message': message}
    rule = payload.get('requirement')
    if rule not in {v[0] for v in RULES.values()}:
        return fail('Chọn yêu cầu nghiệp vụ cần chứng minh.')
    for field in ('conclusion', 'actual'):
        if not isinstance(payload.get(field), str) or not 20 <= len(payload[field].strip()) <= 2000:
            return fail('Mô tả thực tế và kết luận cần từ 20 đến 2000 ký tự mỗi phần.')
    expected = 'synchronize' if rule == 'REQ-05' else 'reject'
    if payload.get('expected') != expected:
        return fail('Kết quả mong đợi chưa phù hợp với yêu cầu nghiệp vụ đã chọn.')
    def canonical_sql(value):
        if not isinstance(value, str):
            return ''
        value = value.strip()
        return value[:-1].strip() if value.endswith(';') else value
    mutation_sql = canonical_sql(payload.get('mutation_sql'))
    evidence_sql = canonical_sql(payload.get('evidence_sql'))
    if not mutation_sql or not evidence_sql or len(mutation_sql) > 6000 or len(evidence_sql) > 6000:
        return fail('Nhập hai câu SQL đã chạy trong phiên này: câu gây vi phạm và câu truy vấn kiểm chứng.')
    try:
        target = int(payload['target_id'])
    except (ValueError, TypeError, KeyError):
        return fail('Nhập ID bản ghi được trả về trong kết quả SQL.')
    mutations = store.execute('SELECT * FROM history WHERE player=? AND round=? ORDER BY id DESC',
                              (player, round_no)).fetchall()
    evidence_queries = mutations
    matched_any = False
    for mutation in mutations:
        mutation_id = mutation['id']
        if canonical_sql(mutation['sql']) != mutation_sql:
            continue
        mr = json.loads(mutation['result'])
        if 'error' in mr or not json.loads(mutation['writes']) or mr['changes'] == 0:
            continue
        for evidence in evidence_queries:
            evidence_id = evidence['id']
            if evidence_id <= mutation_id or canonical_sql(evidence['sql']) != evidence_sql:
                continue
            er = json.loads(evidence['result'])
            if 'error' in er or json.loads(evidence['writes']) or not er.get('rows'):
                continue
            between = store.execute('SELECT writes FROM history WHERE player=? AND round=? AND id>? AND id<?',
                                    (player, round_no, mutation_id, evidence_id)).fetchall()
            if any(json.loads(r['writes']) for r in between):
                continue
            matched_any = True
            before = witnesses(json.loads(mutation['before_state']))
            after = witnesses(json.loads(mutation['after_state']))
            state = json.loads(evidence['after_state'])
            current = witnesses(state)
            read_tables = {t for t, c in json.loads(evidence['reads'])}
            for key, (req, title) in RULES.items():
                if req != rule or target not in after[key] or target in before[key] or target not in current[key]:
                    continue
                record = current[key][target]
                rows = er['rows']
                observed = str(payload.get('observed', '')).strip()
                matches = False
                if key in ('empty_name', 'long_name'):
                    matches = 'members' in read_tables and observed == str(len(record['name'])) and any(
                        r.get('id') == target and r.get('name') == record['name'] for r in rows)
                elif key == 'null_email':
                    matches = 'members' in read_tables and observed.upper() == 'NULL' and any(
                        r.get('id') == target and 'email' in r and r['email'] is None for r in rows)
                elif key == 'orphan_enrollment':
                    missing = {'member': record['member_id'] not in {r['id'] for r in state['members']},
                               'workshop': record['workshop_id'] not in {r['id'] for r in state['workshops']}}
                    joined_rows = [r for r in rows if all(r.get(c) == record[c] for c in ('id', 'member_id', 'workshop_id'))]
                    parent_column = {'member': 'member_exists', 'workshop': 'workshop_exists'}.get(observed)
                    matches = {'enrollments', 'members', 'workshops'} <= read_tables and missing.get(observed, False) and any(
                        parent_column in r and r[parent_column] is None for r in joined_rows)
                elif key == 'duplicate_enrollment':
                    matching = [r for r in rows if all(r.get(c) == record[c] for c in ('member_id', 'workshop_id')) and 'id' in r]
                    matches = 'enrollments' in read_tables and observed == str(record['copies']) and (
                        len({r['id'] for r in matching}) == record['copies'] or
                        any(all(r.get(c) == record[c] for c in ('member_id', 'workshop_id', 'copies')) for r in rows))
                elif key in ('trigger_drift', 'over_capacity'):
                    field = 'registered_count' if key == 'trigger_drift' else 'capacity'
                    matches = {'workshops', 'enrollments'} <= read_tables and observed == str(record['actual_count']) and any(
                        all(r.get(c) == record[c] for c in ('id', field, 'actual_count')) for r in rows)
                if not matches:
                    continue
                if store.execute("SELECT 1 FROM reports WHERE player=? AND verdict='confirmed' AND bug_key=?", (player, key)).fetchone():
                    return {'verdict': 'duplicate', 'message': 'Bạn đã được ghi nhận lỗi này. Không cộng điểm lần nữa.', 'title': title}
                return {'verdict': 'confirmed', 'bug_key': key, 'title': title,
                        'mutation_id': mutation_id, 'evidence_id': evidence_id,
                        'message': 'Bằng chứng và đối chiếu nghiệp vụ hợp lệ. +100 điểm. Phần diễn giải được lưu để giáo viên xem.'}
    if matched_any:
        return fail('Hai câu SQL đã chạy nhưng dữ liệu trả về chưa chứng minh đúng yêu cầu, bản ghi hoặc giá trị bạn báo cáo.')
    return fail('Không tìm thấy hai câu SQL khớp với nhật ký phiên này. Dán đúng câu lệnh thao tác và truy vấn kiểm chứng bạn đã chạy.')

"""Hotel booking sandbox and server-side evidence checks.

The Drive SQL Server script is preserved in source/. This is an intentional
SQLite port for the dependency-free classroom game, not an execution of T-SQL.
"""
import json
import re
import sqlite3
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TABLES = ('Guest', 'RoomType', 'Room', 'Booking', 'Payment')
RULES = {
    'invalid_email': ('BR-01', 'Email sai định dạng', 'Guest'),
    'duplicate_email': ('BR-02', 'Email trùng khác chữ hoa/thường', 'Guest'),
    'blank_name': ('BR-03', 'Tên khách chỉ có khoảng trắng', 'Guest'),
    'invalid_room_type': ('BR-04', 'Loại phòng không thuộc danh mục', 'Room'),
    'inactive_room': ('BR-05', 'Đặt phòng không hoạt động', 'Booking'),
    'overlap': ('BR-08', 'Hai đặt phòng chồng lấn', 'Booking'),
    'wrong_nights': ('BR-07', 'Số đêm không khớp ngày', 'Booking'),
    'wrong_discount': ('BR-10', 'Giảm giá sai chính sách', 'Booking'),
    'wrong_total': ('BR-11', 'Tổng tiền đặt phòng sai', 'Booking'),
    'overpayment': ('BR-12', 'Thanh toán vượt tổng tiền', 'Payment'),
    'wrong_status': ('BR-13', 'Trạng thái không khớp thanh toán', 'Booking'),
    'cancelled_payment': ('BR-14', 'Đặt phòng đã huỷ vẫn nhận thanh toán', 'Payment'),
}


def initialize(conn, reset=False):
    conn.execute('PRAGMA foreign_keys=ON')
    if reset:
        conn.executescript('DROP TABLE IF EXISTS Payment; DROP TABLE IF EXISTS Booking; '
                           'DROP TABLE IF EXISTS Room; DROP TABLE IF EXISTS RoomType; DROP TABLE IF EXISTS Guest;')
    conn.executescript('''
        CREATE TABLE Guest (guest_id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL CHECK(length(trim(full_name)) > 0), phone TEXT);
        CREATE TABLE RoomType (room_type_id INTEGER PRIMARY KEY, type_name TEXT NOT NULL UNIQUE);
        CREATE TABLE Room (room_id INTEGER PRIMARY KEY, room_number TEXT NOT NULL UNIQUE,
            room_type TEXT NOT NULL, price_per_night NUMERIC NOT NULL CHECK(price_per_night > 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
        CREATE TABLE Booking (booking_id INTEGER PRIMARY KEY, booking_code TEXT NOT NULL UNIQUE,
            guest_id INTEGER NOT NULL REFERENCES Guest(guest_id),
            room_id INTEGER NOT NULL REFERENCES Room(room_id),
            check_in TEXT NOT NULL, check_out TEXT NOT NULL, nights INTEGER NOT NULL CHECK(nights > 0),
            discount_rate NUMERIC NOT NULL DEFAULT 0 CHECK(discount_rate BETWEEN 0 AND 1),
            total_amount NUMERIC NOT NULL CHECK(total_amount >= 0),
            status TEXT NOT NULL DEFAULT 'BOOKED' CHECK(status IN ('BOOKED','PAID','CANCELLED')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(date(check_out) > date(check_in)));
        CREATE TABLE Payment (payment_id INTEGER PRIMARY KEY,
            booking_id INTEGER NOT NULL REFERENCES Booking(booking_id) ON DELETE CASCADE,
            amount NUMERIC NOT NULL CHECK(amount > 0), paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX booking_room_dates ON Booking(room_id,check_in,check_out);
        CREATE INDEX payment_booking ON Payment(booking_id);
        CREATE TRIGGER payment_insert AFTER INSERT ON Payment BEGIN
            UPDATE Booking SET status=CASE WHEN
                (SELECT coalesce(sum(amount),0) FROM Payment WHERE booking_id=NEW.booking_id)>=total_amount
                THEN 'PAID' ELSE 'BOOKED' END
            WHERE booking_id=NEW.booking_id AND status<>'CANCELLED';
        END;
        CREATE TRIGGER payment_update AFTER UPDATE ON Payment BEGIN
            UPDATE Booking SET status=CASE WHEN
                (SELECT coalesce(sum(amount),0) FROM Payment WHERE booking_id=NEW.booking_id)>=total_amount
                THEN 'PAID' ELSE 'BOOKED' END
            WHERE booking_id=NEW.booking_id AND status<>'CANCELLED';
            UPDATE Booking SET status=CASE WHEN
                (SELECT coalesce(sum(amount),0) FROM Payment WHERE booking_id=OLD.booking_id)>=total_amount
                THEN 'PAID' ELSE 'BOOKED' END
            WHERE booking_id=OLD.booking_id AND status<>'CANCELLED';
        END;
        CREATE TRIGGER payment_delete AFTER DELETE ON Payment BEGIN
            UPDATE Booking SET status=CASE WHEN
                (SELECT coalesce(sum(amount),0) FROM Payment WHERE booking_id=OLD.booking_id)>=total_amount
                THEN 'PAID' ELSE 'BOOKED' END
            WHERE booking_id=OLD.booking_id AND status<>'CANCELLED';
        END;
        INSERT INTO RoomType(type_name) VALUES ('Standard'),('Deluxe'),('Family');
        INSERT INTO Guest(email,full_name,phone) VALUES
            ('anna@example.test','Anna Nguyen','0900000101'),
            ('minh@example.test','Minh Tran','0900000102'),
            ('linh@example.test','Linh Pham','0900000103');
        INSERT INTO Room(room_number,room_type,price_per_night,active) VALUES
            ('101','Standard',1000000,1),('102','Deluxe',1600000,1),('201','Family',2200000,0);
        INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount)
            VALUES ('HTL-1001',1,1,'2026-11-02','2026-11-05',3,0.1,2700000),
                   ('HTL-1002',2,2,'2026-11-07','2026-11-09',2,0,3200000);
        INSERT INTO Payment(booking_id,amount) VALUES (1,500000),(2,3200000);
    ''')
    conn.commit()


def snapshot(conn):
    conn.row_factory = sqlite3.Row
    return {table: [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]
            for table in TABLES}


def execute_query(conn, sql):
    conn.execute('PRAGMA foreign_keys=ON')
    reads, writes = set(), set()
    allowed = {t.lower(): t for t in TABLES}
    def authorize(action, table, column, db, source):
        name = allowed.get((table or '').lower())
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and name and db == 'main':
            reads.add((name, column))
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_DENY if (column or '').lower() in ('load_extension','writefile','readfile') else sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and name and db == 'main':
            if name == 'RoomType' or (action == sqlite3.SQLITE_UPDATE and column in
                ('guest_id','room_id','booking_id','payment_id','room_type_id')):
                return sqlite3.SQLITE_DENY
            if source and source not in ('payment_insert','payment_update','payment_delete'):
                return sqlite3.SQLITE_DENY
            writes.add(name)
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    conn.execute('BEGIN')
    conn.set_authorizer(authorize)
    budget = [0]
    def progress():
        budget[0] += 1
        return budget[0] > 3000
    conn.set_progress_handler(progress, 1000)
    if hasattr(conn, 'setlimit'):
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100000)
    before_changes = conn.total_changes
    try:
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchmany(501)] if cur.description else []
        result = {'columns': [d[0] for d in cur.description] if cur.description else [],
                  'rows': rows[:500], 'truncated': len(rows) > 500,
                  'changes': conn.total_changes - before_changes}
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        conn.set_progress_handler(None, 0)
        if any(conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] > 1000 for t in TABLES):
            raise ValueError('Mỗi bảng giới hạn 1000 bản ghi trong một lượt điều tra.')
        conn.commit()
    except (sqlite3.Error, ValueError) as exc:
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        conn.set_progress_handler(None, 0)
        conn.rollback()
        message = str(exc)
        if 'authorized' in message or 'prohibited' in message:
            message = 'Chỉ được truy vấn và sửa dữ liệu nghiệp vụ; cấu trúc, ID và danh mục loại phòng được bảo vệ.'
        result = {'error': message}
        writes.clear()
    return result, sorted(reads), sorted(writes)


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def email_valid(value):
    if not isinstance(value, str) or value.count('@') != 1 or re.search(r'\s', value):
        return False
    local, domain = value.split('@')
    parts = domain.split('.')
    return bool(local and len(parts) >= 2 and all(parts))


def witnesses(state):
    """Independent oracle; never derives a verdict from a player's SELECT alone."""
    out = {key: {} for key in RULES}
    guests = {r['guest_id']: r for r in state['Guest']}
    rooms = {r['room_id']: r for r in state['Room']}
    room_types = {r['type_name'] for r in state['RoomType']}
    bookings = {r['booking_id']: r for r in state['Booking']}
    payments = state['Payment']
    for g in guests.values():
        if not email_valid(g['email']):
            out['invalid_email'][g['guest_id']] = g
        if not g['full_name'].strip() or len(g['full_name'].strip()) > 100:
            out['blank_name'][g['guest_id']] = g
        other = next((x for x in guests.values() if x['guest_id'] != g['guest_id'] and
                      x['email'].lower() == g['email'].lower()), None)
        if other:
            out['duplicate_email'][g['guest_id']] = {**g, 'other_id': other['guest_id'],
                                                      'other_email': other['email']}
    for room in rooms.values():
        if room['room_type'] not in room_types:
            out['invalid_room_type'][room['room_id']] = room
    for b in bookings.values():
        bid = b['booking_id']
        room = rooms.get(b['room_id'])
        paid = sum(money(p['amount']) for p in payments if p['booking_id'] == bid)
        if room and not room['active']:
            out['inactive_room'][bid] = {**b, 'active': room['active']}
        other = next((x for x in bookings.values() if x['booking_id'] != bid and
                      x['room_id'] == b['room_id'] and x['status'] != 'CANCELLED' and
                      b['status'] != 'CANCELLED' and
                      b['check_in'] < x['check_out'] and x['check_in'] < b['check_out']), None)
        if other:
            out['overlap'][bid] = {**b, 'other_id': other['booking_id'],
                                   'other_check_in': other['check_in'], 'other_check_out': other['check_out']}
        try:
            actual_nights = (date.fromisoformat(b['check_out']) - date.fromisoformat(b['check_in'])).days
        except (ValueError, TypeError):
            actual_nights = None
        if actual_nights is not None and b['nights'] != actual_nights:
            out['wrong_nights'][bid] = {**b, 'actual_nights': actual_nights}
        correct_rate = Decimal('0.1') if b['nights'] >= 3 else Decimal('0')
        if money(b['discount_rate']) != correct_rate:
            out['wrong_discount'][bid] = b
        if room:
            total = money(Decimal(str(b['nights'])) * Decimal(str(room['price_per_night'])) *
                          (1 - Decimal(str(b['discount_rate']))))
            if money(b['total_amount']) != total:
                out['wrong_total'][bid] = {**b, 'price_per_night': room['price_per_night'],
                                           'expected_total': float(total)}
        if paid > money(b['total_amount']):
            out['overpayment'][bid] = {**b, 'paid_total': float(paid)}
        if b['status'] != 'CANCELLED':
            correct_status = 'PAID' if paid >= money(b['total_amount']) else 'BOOKED'
            if b['status'] != correct_status:
                out['wrong_status'][bid] = {**b, 'paid_total': float(paid)}
        else:
            for p in payments:
                if p['booking_id'] == bid:
                    out['cancelled_payment'][p['payment_id']] = {**p, 'status': b['status']}
    return out


def public_history(row):
    result = json.loads(row['result'])
    return {'id': row['id'], 'sql': row['sql'], 'created': row['created'],
            'result': result, 'is_write': bool(json.loads(row['writes']))}


def canonical_sql(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    return value[:-1].strip() if value.endswith(';') else value


def split_statements(value):
    """One statement per game execution; semicolons inside string literals are allowed."""
    if not isinstance(value, str) or len(value) > 30000:
        return []
    statements, chunk = [], ''
    for character in value:
        chunk += character
        if character == ';' and sqlite3.complete_statement(chunk):
            statements.append(canonical_sql(chunk))
            chunk = ''
    if chunk.strip():
        statements.append(canonical_sql(chunk))
    return [s for s in statements if s]


def proof_matches(key, record, rows, reads, target):
    """Require concrete row values and underlying columns, not just a table read."""
    fields = {
        'invalid_email': ('guest_id', 'email'),
        'duplicate_email': ('guest_id', 'email', 'other_id'),
        'blank_name': ('guest_id', 'full_name'),
        'invalid_room_type': ('room_id', 'room_type'),
        'inactive_room': ('booking_id', 'room_id', 'active'),
        'overlap': ('booking_id', 'room_id', 'check_in', 'check_out', 'other_id', 'other_check_in', 'other_check_out'),
        'wrong_nights': ('booking_id', 'nights', 'actual_nights'),
        'wrong_discount': ('booking_id', 'nights', 'discount_rate'),
        'wrong_total': ('booking_id', 'nights', 'discount_rate', 'total_amount', 'price_per_night'),
        'overpayment': ('booking_id', 'total_amount', 'paid_total'),
        'wrong_status': ('booking_id', 'total_amount', 'paid_total', 'status'),
        'cancelled_payment': ('payment_id', 'booking_id', 'amount', 'status'),
    }[key]
    needed_reads = {
        'invalid_email': {('Guest','guest_id'),('Guest','email')},
        'duplicate_email': {('Guest','guest_id'),('Guest','email')},
        'blank_name': {('Guest','guest_id'),('Guest','full_name')},
        'invalid_room_type': {('Room','room_id'),('Room','room_type'),('RoomType','type_name')},
        'inactive_room': {('Booking','booking_id'),('Booking','room_id'),('Room','active')},
        'overlap': {('Booking','booking_id'),('Booking','room_id'),('Booking','check_in'),('Booking','check_out')},
        'wrong_nights': {('Booking','booking_id'),('Booking','nights'),('Booking','check_in'),('Booking','check_out')},
        'wrong_discount': {('Booking','booking_id'),('Booking','nights'),('Booking','discount_rate')},
        'wrong_total': {('Booking','booking_id'),('Booking','nights'),('Booking','discount_rate'),
                        ('Booking','total_amount'),('Room','price_per_night')},
        'overpayment': {('Booking','booking_id'),('Booking','total_amount'),('Payment','amount')},
        'wrong_status': {('Booking','booking_id'),('Booking','total_amount'),('Booking','status'),('Payment','amount')},
        'cancelled_payment': {('Booking','booking_id'),('Booking','status'),
                              ('Payment','payment_id'),('Payment','amount')},
    }[key]
    if not needed_reads <= set(map(tuple, reads)):
        return False
    if key == 'duplicate_email':
        # Accept either a single joined row with other_id, or two rows that
        # explicitly identify the reported guest and its matching counterpart.
        for row in rows:
            if ('guest_id' in row and 'email' in row and 'other_id' in row and
                    row['guest_id'] == target and row['guest_id'] == record['guest_id'] and
                    row['email'] == record['email'] and row['other_id'] == record['other_id']):
                return True
        if len(rows) != 2 or any(not {'guest_id', 'email'} <= set(row) for row in rows):
            return False
        by_id = {row['guest_id']: row for row in rows}
        if len(by_id) != 2 or set(by_id) != {target, record['other_id']}:
            return False
        return (by_id[target]['email'] == record['email'] and
                by_id[record['other_id']]['email'] == record['other_email'])
    if key == 'overlap':
        # As with duplicate values, overlapping rows may be shown as one joined
        # proof row or as the exact pair of booking rows with their IDs.
        for row in rows:
            if (all(field in row for field in fields) and
                    all(row[field] == record[field] for field in fields) and
                    row['booking_id'] == target):
                return True
        pair_fields = {'booking_id', 'room_id', 'check_in', 'check_out'}
        if len(rows) != 2 or any(not pair_fields <= set(row) for row in rows):
            return False
        by_id = {row['booking_id']: row for row in rows}
        if len(by_id) != 2 or set(by_id) != {target, record['other_id']}:
            return False
        target_row, other_row = by_id[target], by_id[record['other_id']]
        return (target_row['room_id'] == record['room_id'] and
                target_row['check_in'] == record['check_in'] and
                target_row['check_out'] == record['check_out'] and
                other_row['room_id'] == record['room_id'] and
                other_row['check_in'] == record['other_check_in'] and
                other_row['check_out'] == record['other_check_out'])
    for row in rows:
        if not all(field in row for field in fields):
            continue
        if not all(row[field] == record[field] for field in fields):
            continue
        if row[fields[0]] == target:
            return True
    return False


def causal_step_valid(key, selected, target):
    """Check the timing of rules that apply only when a row is newly created."""
    if key not in ('inactive_room','cancelled_payment'):
        return True
    for step in selected:
        before = json.loads(step['before_state'])
        after = json.loads(step['after_state'])
        if key == 'inactive_room':
            old_ids = {r['booking_id'] for r in before['Booking']}
            booking = next((r for r in after['Booking'] if r['booking_id'] == target), None)
            if booking and target not in old_ids and 'Booking' in json.loads(step['writes']):
                room = next((r for r in before['Room'] if r['room_id'] == booking['room_id']), None)
                if room and room['active'] == 0:
                    return True
        else:
            old_ids = {r['payment_id'] for r in before['Payment']}
            payment = next((r for r in after['Payment'] if r['payment_id'] == target), None)
            if payment and target not in old_ids and 'Payment' in json.loads(step['writes']):
                booking = next((r for r in before['Booking'] if r['booking_id'] == payment['booking_id']), None)
                if booking and booking['status'] == 'CANCELLED':
                    return True
    return False


def _row_map(state, table):
    return {row[next(iter(row))]: row for row in state[table]}


def _changed_ids(before, after, table):
    old, new = _row_map(before, table), _row_map(after, table)
    return {row_id for row_id in old.keys() | new.keys() if old.get(row_id) != new.get(row_id)}


def relevant_write_ids(key, target, record, writes_after_boundary):
    """Return writes touching the reported violation or its aggregate evidence.

    Unrelated experiments are intentionally ignored. Rows needed only as existing
    foreign-key parents are context, not part of the bug-producing action.
    """
    if key in ('invalid_email', 'blank_name'):
        dependencies = {'Guest': {target}}
    elif key == 'duplicate_email':
        dependencies = {'Guest': {target, record['other_id']}}
    elif key == 'invalid_room_type':
        dependencies = {'Room': {target}}
    elif key == 'inactive_room':
        dependencies = {'Booking': {target}}
    elif key == 'overlap':
        dependencies = {'Booking': {target, record['other_id']}}
    elif key in ('wrong_nights', 'wrong_discount'):
        dependencies = {'Booking': {target}}
    elif key == 'wrong_total':
        dependencies = {'Booking': {target}, 'Room': {record['room_id']}}
    elif key == 'overpayment':
        dependencies = {'Payment': None}
    elif key == 'wrong_status':
        dependencies = {'Booking': {target}, 'Payment': None}
    else:  # cancelled_payment
        dependencies = {'Booking': {record['booking_id']}, 'Payment': {target}}

    relevant = []
    for step in writes_after_boundary:
        tables = set(json.loads(step['writes']))
        before, after = json.loads(step['before_state']), json.loads(step['after_state'])
        for table, ids in dependencies.items():
            if table not in tables:
                continue
            changed = _changed_ids(before, after, table)
            if ids is None:
                if table == 'Payment':
                    changed = {row_id for row_id in changed if
                               any(r['payment_id'] == row_id and r['booking_id'] == record.get('booking_id', target)
                                   for r in after['Payment'] + before['Payment'])}
                else:
                    changed = set()
            if changed & ids if ids is not None else changed:
                relevant.append(step)
                break
    # If the player created the reported booking and had to create its valid guest
    # first, retain that prerequisite in the submitted chain. Existing parent rows
    # remain context and unrelated guest inserts are still excluded.
    booking_id = target if key in ('inactive_room', 'overlap', 'wrong_nights', 'wrong_discount',
                                   'wrong_total', 'wrong_status') else None
    if booking_id is not None:
        booking = next((r for r in json.loads(writes_after_boundary[-1]['after_state'])['Booking']
                        if r['booking_id'] == booking_id), None)
        if booking:
            for step in writes_after_boundary:
                if 'Guest' in json.loads(step['writes']) and booking['guest_id'] in _changed_ids(
                        json.loads(step['before_state']), json.loads(step['after_state']), 'Guest'):
                    if step not in relevant:
                        relevant.append(step)
    return relevant


def verify_report(store, player, round_no, payload, group_number):
    def fail(message):
        return {'verdict': 'needs_evidence', 'message': message}
    rule = payload.get('requirement')
    if rule not in {entry[0] for entry in RULES.values()}:
        return fail('Chọn quy tắc nghiệp vụ có lỗi tự động chấm.')
    target_keys = [key for key,(req,_,_) in RULES.items() if req == rule]
    already = store.execute('SELECT title FROM group_discoveries WHERE group_number=? AND bug_key IN ('+
        ','.join('?' for _ in target_keys)+') LIMIT 1', (group_number,*target_keys)).fetchone()
    if already:
        return {'verdict':'duplicate','title':already['title'],
                'message':'Nhóm đã được ghi nhận lỗi này; không cộng điểm lần nữa.'}
    expected_by_rule = {'BR-13':'synchronize','BR-07':'derive','BR-10':'derive','BR-11':'derive'}
    if payload.get('expected') != expected_by_rule.get(rule, 'reject'):
        return fail('Chọn kết quả mong đợi theo đặc tả.')
    statements = split_statements(payload.get('mutation_sql'))
    evidence_sql = canonical_sql(payload.get('evidence_sql'))
    if not statements or not evidence_sql or len(evidence_sql) > 6000:
        return fail('Nhập toàn bộ câu thao tác đã chạy, ngăn cách bằng dấu ; và một câu SELECT kiểm chứng.')
    try:
        target = int(payload['target_id'])
    except (ValueError, TypeError, KeyError):
        return fail('Nhập ID của bản ghi hoặc booking vi phạm.')
    history = store.execute('SELECT * FROM history WHERE player=? AND round=? ORDER BY id',
                            (player, round_no)).fetchall()
    history_ids = {h['id'] for h in history}
    boundary = 0
    for previous_report in store.execute("SELECT payload FROM reports WHERE player=? AND verdict='confirmed' ORDER BY id",(player,)):
        try:
            previous_evidence = int(json.loads(previous_report['payload']).get('evidence_id',0))
        except (ValueError, TypeError):
            continue
        if previous_evidence in history_ids:
            boundary = max(boundary, previous_evidence)
    candidates = [h for h in history if canonical_sql(h['sql']) == evidence_sql and
                  h['id'] > boundary and not json.loads(h['writes']) and
                  'error' not in json.loads(h['result']) and json.loads(h['result']).get('rows')]
    # Submitted statements must contain every causally relevant write. Extra
    # statements are accepted only when they are successful writes in this proof
    # interval; unrelated experiments do not affect the independent verdict.
    for evidence in reversed(candidates):
        interval = [h for h in history if boundary < h['id'] < evidence['id'] and
                    'error' not in json.loads(h['result'])]
        writes = [h for h in interval if json.loads(h['writes']) and
                  json.loads(h['result']).get('changes', 0) > 0]
        if not writes:
            continue
        at_evidence = witnesses(json.loads(evidence['after_state']))
        rows = json.loads(evidence['result'])['rows']
        reads = json.loads(evidence['reads'])
        baseline_state = json.loads(interval[0]['before_state']) if interval else json.loads(evidence['before_state'])
        for key, (requirement, title, _) in RULES.items():
            if requirement != rule or target not in at_evidence[key]:
                continue
            record = at_evidence[key][target]
            selected = relevant_write_ids(key, target, record, writes)
            submitted_counts = Counter(statements)
            required_counts = Counter(canonical_sql(h['sql']) for h in selected)
            logged_counts = Counter(canonical_sql(h['sql']) for h in interval
                                    if json.loads(h['writes']) and 'error' not in json.loads(h['result']))
            if (not selected or any(submitted_counts[sql] < count for sql, count in required_counts.items()) or
                    any(count > logged_counts[sql] for sql, count in submitted_counts.items())):
                continue
            before = witnesses(baseline_state)
            if target in before[key]:
                continue
            # Confirm the violation first appears during this run, then stays visible
            # in the frozen state captured by the player's SELECT.
            appeared = False
            previous_state = baseline_state
            for step in interval:
                current_state = json.loads(step['after_state'])
                if target not in witnesses(previous_state)[key] and target in witnesses(current_state)[key]:
                    appeared = True
                    break
                previous_state = current_state
            if not appeared or not causal_step_valid(key, interval, target):
                continue
            if not proof_matches(key, record, rows, reads, target):
                continue
            observed_field = {
                'invalid_email':'email','duplicate_email':'email','blank_name':'full_name',
                'invalid_room_type':'room_type','inactive_room':'active','overlap':'other_id',
                'wrong_nights':'actual_nights','wrong_discount':'discount_rate',
                'wrong_total':'total_amount','overpayment':'paid_total',
                'wrong_status':'status','cancelled_payment':'amount',
            }[key]
            observed = str(payload.get('observed','')).strip()
            actual_value = len(record['full_name'].strip()) if key == 'blank_name' else record[observed_field]
            try:
                numeric_match = money(observed) == money(actual_value)
            except (ValueError, TypeError, ArithmeticError):
                numeric_match = False
            if not (observed == str(actual_value).strip() or numeric_match):
                continue
            if store.execute('SELECT 1 FROM group_discoveries WHERE group_number=? AND bug_key=?',
                             (group_number,key)).fetchone():
                return {'verdict':'duplicate','title':title,
                        'message':'Lỗi này đã được ghi nhận cho nhóm; không cộng điểm lần nữa.'}
            return {'verdict':'confirmed','bug_key':key,'title':title,
                    'mutation_ids':[h['id'] for h in selected], 'evidence_id':evidence['id'],
                    'message':'Bằng chứng khớp các thao tác liên quan và trạng thái tại thời điểm SELECT. +100 điểm.'}
    return fail('Không khớp đầy đủ các thao tác liên quan đến lỗi, hoặc SELECT chưa chỉ ra đúng dòng và giá trị vi phạm.')

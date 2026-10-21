"""End-to-end HTTP checks using isolated, temporary databases."""
import http.cookiejar
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class Player:
    def __init__(self, base):
        self.base = base
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        lobby = self.state()
        if lobby.get('needs_group'):
            available = next(group['number'] for group in lobby['groups'] if not group['active'])
            self.call('/api/join', {'group': available})

    def call(self, path, payload=None):
        request = urllib.request.Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(),
                                         headers={} if payload is None else {'Content-Type': 'application/json'})
        try:
            with self.http.open(request) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise AssertionError((path, error.code, error.read().decode())) from error

    def state(self):
        return self.call('/api/state')

    def sql(self, sql):
        result = self.call('/api/query', {'sql': sql})
        if 'error' in result:
            raise AssertionError((sql, result))
        if 'flaws' in result:
            raise AssertionError('Hidden answers leaked')
        result['sql'] = sql
        return result

    def report(self, req, mutation, evidence, target, observed, **extra):
        payload = dict(requirement=req, mutation_sql=mutation['sql'], evidence_sql=evidence['sql'],
                       target_id=target, observed=observed, expected='synchronize' if req == 'REQ-05' else 'reject',
                       actual='The saved query returned the invalid data described in this report.',
                       conclusion='The observed record violates the selected business requirement.')
        payload.update(extra)
        return self.call('/api/reports', payload)


class InvestigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_data = server.DATA
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    def setUp(self):
        # Each case gets a fresh eleven-group classroom.
        server.DATA = Path(self.temp.name) / self._testMethodName
        server.DATA.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        server.DATA = cls.original_data
        cls.temp.cleanup()

    def player(self):
        return Player(self.base)

    def test_reading_and_writing_alone_do_not_score(self):
        p = self.player()
        healthy = p.sql('SELECT * FROM members;')
        self.assertEqual(len(healthy['rows']), 3)
        self.assertNotIn('flaws', p.state())
        self.assertEqual(p.report('REQ-01', healthy, healthy, 1, '9')['verdict'], 'needs_evidence')
        p.sql("INSERT INTO members(name,email) VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345','long@example.test');")
        self.assertEqual(p.state()['score'], 0)

    def test_long_name_evidence_dedup_and_reset(self):
        p = self.player()
        m = p.sql("INSERT INTO members(name,email) VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345','long@example.test');")
        e = p.sql('SELECT id,name,length(name) AS name_length FROM members WHERE id=4;')
        self.assertEqual(p.report('REQ-01', m, e, 4, '30')['verdict'], 'needs_evidence')
        self.assertEqual(p.report('REQ-01', m, e, 4, '31', expected='allow')['verdict'], 'needs_evidence')
        self.assertEqual(p.report('REQ-01', m, e, 4, '31')['verdict'], 'confirmed')
        self.assertEqual(p.report('REQ-01', m, e, 4, '31')['verdict'], 'duplicate')
        p.sql('DELETE FROM members WHERE id=4;')
        self.assertEqual(p.state()['score'], 100)
        p.call('/api/reset', {'confirm': 'reset'})
        self.assertEqual(p.state()['score'], 100)
        self.assertEqual(p.state()['history'], [])
        self.assertEqual(p.report('REQ-01', m, e, 4, '31')['verdict'], 'needs_evidence')

    def test_all_remaining_findings(self):
        cases = [
            ('REQ-01', "INSERT INTO members(name,email) VALUES ('','a@test');", 'SELECT * FROM members WHERE id=4;', 4, '0'),
            ('REQ-02', "INSERT INTO members(name,email) VALUES ('Valid name',NULL);", 'SELECT id,email FROM members WHERE id=4;', 4, 'NULL'),
            ('REQ-03', 'INSERT INTO enrollments(member_id,workshop_id) VALUES (9999,1);',
             'SELECT e.id,e.member_id,e.workshop_id,m.id AS member_exists,w.id AS workshop_exists FROM enrollments e LEFT JOIN members m ON m.id=e.member_id LEFT JOIN workshops w ON w.id=e.workshop_id WHERE m.id IS NULL OR w.id IS NULL;', 1, 'member'),
            ('REQ-04', 'INSERT INTO enrollments(member_id,workshop_id) VALUES (1,1),(1,1);', 'SELECT * FROM enrollments;', 1, '2'),
            ('REQ-05', 'DELETE FROM enrollments WHERE id=1;', 'SELECT w.id,w.registered_count,count(e.id) AS actual_count FROM workshops w LEFT JOIN enrollments e ON e.workshop_id=w.id GROUP BY w.id;', 1, '0'),
            ('REQ-06', 'INSERT INTO enrollments(member_id,workshop_id) VALUES (1,1),(2,1),(3,1);', 'SELECT w.id,w.capacity,count(e.id) AS actual_count FROM workshops w LEFT JOIN enrollments e ON e.workshop_id=w.id GROUP BY w.id;', 1, '3'),
        ]
        for req, write, read, target, observed in cases:
            with self.subTest(requirement=req):
                p = self.player()
                if req == 'REQ-05':
                    p.sql('INSERT INTO enrollments(member_id,workshop_id) VALUES (1,1);')
                m, e = p.sql(write), p.sql(read)
                outcome = p.report(req, m, e, target, observed)
                self.assertEqual(outcome['verdict'], 'confirmed', outcome)

    def test_foreign_or_constant_evidence_is_rejected(self):
        p, other = self.player(), self.player()
        m = p.sql("INSERT INTO members(name,email) VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345','long@example.test');")
        fake = p.sql("SELECT 4 AS id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ12345' AS name;")
        self.assertEqual(p.report('REQ-01', m, fake, 4, '31')['verdict'], 'needs_evidence')
        e = p.sql('SELECT * FROM members WHERE id=4;')
        self.assertEqual(other.report('REQ-01', m, e, 4, '31')['verdict'], 'needs_evidence')
        self.assertEqual(other.state()['score'], 0)

    def test_reporter_must_supply_matching_sql(self):
        p = self.player()
        m = p.sql("INSERT INTO members(name,email) VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345','long@example.test');")
        e = p.sql('SELECT id,name,length(name) AS name_length FROM members WHERE id=4;')
        outcome = p.report('REQ-01', m, e, 4, '31', mutation_sql="INSERT INTO members(name,email) VALUES ('guessed','guessed@test');")
        self.assertEqual(outcome['verdict'], 'needs_evidence')
        outcome = p.report('REQ-01', m, e, 4, '31', evidence_sql='SELECT * FROM members;')
        self.assertEqual(outcome['verdict'], 'needs_evidence')
        spaced = p.report('REQ-01', m, e, 4, '31', mutation_sql='  ' + m['sql'] + '  ', evidence_sql=' ' + e['sql'] + ' ')
        self.assertEqual(spaced['verdict'], 'confirmed')
        self.assertEqual(p.state()['score'], 100)
        saved = p.state()['reports'][0]['report']
        self.assertEqual(saved['mutation_id'], m['history_id'])
        self.assertEqual(saved['evidence_id'], e['history_id'])

    def test_permissions_and_failed_query_rollback(self):
        p = self.player()
        forbidden = [
            'UPDATE workshops SET registered_count=999 WHERE id=1;',
            'DROP TABLE members;', "ATTACH DATABASE 'other.sqlite3' AS x;", 'PRAGMA writable_schema=ON;',
            'UPDATE members SET id=999 WHERE id=1;', 'SELECT * FROM sqlite_master;', 'BEGIN;',
            "UPDATE members SET name=x'6162' WHERE id=1;", 'UPDATE workshops SET capacity=0 WHERE id=1;',
        ]
        for sql in forbidden:
            with self.subTest(sql=sql):
                self.assertIn('error', p.call('/api/query', {'sql': sql}))
        self.assertEqual(p.sql('SELECT name FROM members WHERE id=1;')['rows'][0]['name'], 'An Nguyen')
        self.assertEqual(p.sql('SELECT registered_count FROM workshops WHERE id=1;')['rows'][0]['registered_count'], 0)

    def test_intervening_writes_do_not_create_a_causal_report(self):
        p = self.player()
        m = p.sql("INSERT INTO members(name,email) VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345','long@example.test');")
        p.sql("UPDATE members SET email='changed@example.test' WHERE id=4;")
        e = p.sql('SELECT * FROM members WHERE id=4;')
        self.assertEqual(p.report('REQ-01', m, e, 4, '31')['verdict'], 'needs_evidence')


if __name__ == '__main__':
    unittest.main(verbosity=2)

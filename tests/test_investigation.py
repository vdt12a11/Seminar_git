"""HTTP scoring checks with isolated classroom databases."""
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
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.base = base
        lobby = self.call('/api/state')
        self.call('/api/join', {'group': next(x['number'] for x in lobby['groups'] if not x['active'])})

    def call(self, path, payload=None):
        req = urllib.request.Request(self.base + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={} if payload is None else {'Content-Type':'application/json'})
        try:
            with self.http.open(req) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise AssertionError((path,error.code,error.read().decode())) from error

    def sql(self, sql):
        result = self.call('/api/query', {'sql':sql})
        if 'error' in result:
            raise AssertionError((sql,result))
        return result

    def report(self, rule, mutations, evidence, target, observed, **overrides):
        expected = 'synchronize' if rule == 'BR-13' else 'derive' if rule in ('BR-07','BR-10','BR-11') else 'reject'
        payload = dict(requirement=rule,mutation_sql='\n'.join(mutations),evidence_sql=evidence,
            target_id=str(target),observed=str(observed),expected=expected)
        payload.update(overrides)
        return self.call('/api/reports',payload)


class HotelScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_data = server.DATA
        cls.http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    def setUp(self):
        server.DATA = Path(self.temp.name) / self._testMethodName
        server.DATA.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        server.DATA = cls.original_data
        cls.temp.cleanup()

    def test_all_automatic_rules_require_specific_rows(self):
        p = Player(self.base)
        cases = [
            ('BR-01', ["INSERT INTO Guest(email,full_name) VALUES ('not-email','Test Guest');"],
             'SELECT guest_id,email FROM Guest WHERE guest_id=4;',4,'not-email'),
            ('BR-02', ["INSERT INTO Guest(email,full_name) VALUES ('ANNA@example.test','Other Anna');"],
             'SELECT g.guest_id,g.email,g2.guest_id AS other_id FROM Guest g JOIN Guest g2 ON lower(g.email)=lower(g2.email) AND g.guest_id<>g2.guest_id WHERE g.guest_id=4;',4,'ANNA@example.test'),
            ('BR-03', ["INSERT INTO Guest(email,full_name) VALUES ('tab@example.test',char(9));"],
             'SELECT guest_id,full_name FROM Guest WHERE guest_id=4;',4,'0'),
            ('BR-04', ["INSERT INTO Room(room_number,room_type,price_per_night,active) VALUES ('301','Mystery',1000000,1);"],
             'SELECT r.room_id,r.room_type FROM Room r LEFT JOIN RoomType t ON r.room_type=t.type_name WHERE r.room_id=4 AND t.type_name IS NULL;',4,'Mystery'),
            ('BR-05', ["INSERT INTO Guest(email,full_name) VALUES ('four@example.test','Four Guest');",
                        "INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-INACTIVE',4,3,'2026-11-10','2026-11-11',1,0,2200000);"],
             'SELECT b.booking_id,b.room_id,r.active FROM Booking b JOIN Room r ON r.room_id=b.room_id WHERE b.booking_id=3;',3,'0'),
            ('BR-07', ["INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-NIGHTS',1,2,'2026-11-15','2026-11-17',3,0.1,4320000);"],
             'SELECT booking_id,nights,CAST(julianday(check_out)-julianday(check_in) AS INTEGER) AS actual_nights FROM Booking WHERE booking_id=3;',3,'2'),
            ('BR-08', ["INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-OVERLAP',1,1,'2026-11-04','2026-11-06',2,0,2000000);"],
             'SELECT b.booking_id,b.room_id,b.check_in,b.check_out,o.booking_id AS other_id,o.check_in AS other_check_in,o.check_out AS other_check_out FROM Booking b JOIN Booking o ON b.room_id=o.room_id AND b.booking_id<>o.booking_id AND b.check_in<o.check_out AND o.check_in<b.check_out WHERE b.booking_id=3;',3,'1'),
            ('BR-10', ["INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-DISCOUNT',1,2,'2026-11-15','2026-11-18',3,0,4800000);"],
             'SELECT booking_id,nights,discount_rate FROM Booking WHERE booking_id=3;',3,'0'),
            ('BR-11', ["INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-TOTAL',1,2,'2026-11-15','2026-11-16',1,0,100);"],
             'SELECT b.booking_id,b.nights,b.discount_rate,b.total_amount,r.price_per_night FROM Booking b JOIN Room r ON r.room_id=b.room_id WHERE b.booking_id=3;',3,'100'),
            ('BR-12', ['INSERT INTO Payment(booking_id,amount) VALUES (1,2300000);'],
             'SELECT b.booking_id,b.total_amount,sum(p.amount) AS paid_total FROM Booking b JOIN Payment p ON p.booking_id=b.booking_id WHERE b.booking_id=1 GROUP BY b.booking_id;',1,'2800000'),
            ('BR-13', ['UPDATE Booking SET total_amount=4000000 WHERE booking_id=2;'],
             'SELECT b.booking_id,b.total_amount,sum(p.amount) AS paid_total,b.status FROM Booking b LEFT JOIN Payment p ON p.booking_id=b.booking_id WHERE b.booking_id=2 GROUP BY b.booking_id;',2,'PAID'),
            ('BR-14', ["UPDATE Booking SET status='CANCELLED' WHERE booking_id=1;",
                        'INSERT INTO Payment(booking_id,amount) VALUES (1,100);'],
             'SELECT p.payment_id,p.booking_id,p.amount,b.status FROM Payment p JOIN Booking b ON b.booking_id=p.booking_id WHERE p.payment_id=3;',3,'100'),
        ]
        for index,(rule,writes,read,target,observed) in enumerate(cases):
            with self.subTest(rule=rule):
                if index:
                    p.call('/api/reset',{'confirm':'reset'})
                for sql in writes:
                    p.sql(sql)
                self.assertEqual(p.call('/api/state')['score'],index*100)
                p.sql(read)
                outcome = p.report(rule,writes,read,target,observed)
                self.assertEqual(outcome['verdict'],'confirmed',outcome)
                self.assertEqual(len(outcome['mutation_ids']),len(writes))
        self.assertEqual(p.call('/api/state')['score'],len(cases)*100)

    def test_missing_step_wrong_value_and_generic_select_rejected(self):
        p = Player(self.base)
        setup = "INSERT INTO Guest(email,full_name) VALUES ('four@example.test','Four Guest');"
        mutation = "INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES ('B-INACTIVE',4,3,'2026-11-10','2026-11-11',1,0,2200000);"
        proof = 'SELECT b.booking_id,b.room_id,r.active FROM Booking b JOIN Room r ON r.room_id=b.room_id WHERE b.booking_id=3;'
        p.sql(setup); p.sql(mutation); p.sql(proof)
        self.assertEqual(p.report('BR-05',[mutation],proof,3,0)['verdict'],'needs_evidence')
        self.assertEqual(p.report('BR-05',[setup,mutation],proof,3,1)['verdict'],'needs_evidence')
        self.assertEqual(p.report('BR-05',[setup,mutation],proof,3,0,expected='derive')['verdict'],'needs_evidence')
        generic = 'SELECT * FROM Booking;'
        p.sql(generic)
        self.assertEqual(p.report('BR-05',[setup,mutation],generic,3,0)['verdict'],'needs_evidence')
        self.assertEqual(p.report('BR-05',[setup,mutation],proof,3,0,
                                  actual='nonsense',conclusion='nonsense')['verdict'],'confirmed')
        saved = p.call('/api/state')['reports'][0]['report']
        self.assertNotIn('actual',saved)
        self.assertNotIn('conclusion',saved)
        self.assertEqual(p.report('BR-05',[setup,mutation],proof,3,0)['verdict'],'duplicate')

    def test_protected_rules_and_round_isolation(self):
        p = Player(self.base)
        self.assertIn('error',p.call('/api/query',{'sql':'INSERT INTO Booking(booking_code,guest_id,room_id,check_in,check_out,nights,discount_rate,total_amount) VALUES (\'BAD\',999,1,\'2026-11-10\',\'2026-11-11\',1,0,1000000);'}))
        self.assertIn('error',p.call('/api/query',{'sql':'DROP TABLE Booking;'}))
        mutation = "INSERT INTO Guest(email,full_name) VALUES ('bad','Test Guest');"
        proof = 'SELECT guest_id,email FROM Guest WHERE guest_id=4;'
        p.sql(mutation); p.sql(proof)
        p.call('/api/reset',{'confirm':'reset'})
        self.assertEqual(p.report('BR-01',[mutation],proof,4,'bad')['verdict'],'needs_evidence')

    def test_timing_matters_for_booking_and_cancelled_payment(self):
        p = Player(self.base)
        deactivate = 'UPDATE Room SET active=0 WHERE room_id=1;'
        inactive_proof = 'SELECT b.booking_id,b.room_id,r.active FROM Booking b JOIN Room r ON r.room_id=b.room_id WHERE b.booking_id=1;'
        p.sql(deactivate); p.sql(inactive_proof)
        self.assertEqual(p.report('BR-05',[deactivate],inactive_proof,1,0)['verdict'],'needs_evidence')
        p.call('/api/reset',{'confirm':'reset'})
        cancel = "UPDATE Booking SET status='CANCELLED' WHERE booking_id=1;"
        existing_proof = 'SELECT p.payment_id,p.booking_id,p.amount,b.status FROM Payment p JOIN Booking b ON b.booking_id=p.booking_id WHERE p.payment_id=1;'
        p.sql(cancel); p.sql(existing_proof)
        self.assertEqual(p.report('BR-14',[cancel],existing_proof,1,500000)['verdict'],'needs_evidence')

    def test_leave_releases_group_and_switch_starts_fresh_session(self):
        p = Player(self.base)
        old = p.call('/api/state')
        mutation = "INSERT INTO Guest(email,full_name) VALUES ('bad','Test Guest');"
        proof = 'SELECT guest_id,email FROM Guest WHERE guest_id=4;'
        p.sql(mutation); p.sql(proof)
        self.assertEqual(p.report('BR-01',[mutation],proof,4,'bad')['verdict'],'confirmed')
        self.assertEqual(p.call('/api/state')['score'],100)
        p.call('/api/leave',{})
        lobby = p.call('/api/state')
        self.assertTrue(lobby['needs_group'])
        self.assertFalse(next(g for g in lobby['groups'] if g['number'] == old['group'])['active'])
        p.call('/api/join',{'group':2})
        fresh = p.call('/api/state')
        self.assertEqual(fresh['group'],2)
        self.assertNotEqual(fresh['session'],old['session'])
        self.assertEqual(fresh['score'],0)
        self.assertEqual(fresh['reports'],[])
        self.assertEqual(fresh['history'],[])
        self.assertEqual(Player(self.base).call('/api/state')['group'],old['group'])


if __name__ == '__main__':
    unittest.main()

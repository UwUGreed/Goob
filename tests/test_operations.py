import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from operations.db import connect, seed
from operations.modules import agreements, inventory, workflow
from operations.modules.registry import configure

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'test.sqlite3')
        self.db = connect(self.path)
        seed(self.db)
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def proposal(self):
        return workflow.propose(self.db,'demo','owner')['id']
    def test_approval_and_retry(self):
        p=self.proposal()
        workflow.approve(self.db,'demo','owner',p)
        self.assertTrue(workflow.approve(self.db,'demo','owner',p)['replayed'])
        self.assertEqual(agreements.balance(self.db,'demo','care-v1'),0)
        self.assertEqual(inventory.read(self.db,'demo')[0]['available'],7)
        invoice=json.loads(self.db.execute('SELECT snapshot FROM invoices').fetchone()[0])
        self.assertEqual(invoice['approved_cents'],18000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],1)
    def test_wrong_equipment_property_trade(self):
        for field,value in [('equipment','hvac-2'),('property','46 Willow Way'),('trade','Electrical')]:
            job=workflow.job(self.db,'demo')|{field:value}
            with self.assertRaises(ValueError): agreements.eligibility(self.db,'demo',job,'2026-10-10')
    def test_expired_and_overlapping(self):
        with self.assertRaises(ValueError): agreements.eligibility(self.db,'demo',workflow.job(self.db,'demo'),'2030-01-01')
        self.db.execute("INSERT INTO agreements SELECT tenant,'overlap',equipment,property,trade,start,\"end\",discount,terms FROM agreements")
        with self.assertRaises(ValueError): self.proposal()
    def test_permissions_and_tenant_isolation(self):
        p=self.proposal()
        with self.assertRaises(ValueError): workflow.approve(self.db,'demo','technician',p)
        with self.assertRaises(ValueError): workflow.approve(self.db,'other','owner',p)
        self.assertEqual(inventory.read(self.db,'other'),[])
    def test_stale_proposal(self):
        p=self.proposal()
        self.db.execute('UPDATE jobs SET revision=revision+1')
        with self.assertRaises(ValueError): workflow.approve(self.db,'demo','owner',p)
        self.assertEqual(agreements.balance(self.db,'demo','care-v1'),1)
    def test_changed_terms(self):
        p=self.proposal()
        self.db.execute('UPDATE agreements SET discount=20')
        with self.assertRaises(ValueError): workflow.approve(self.db,'demo','owner',p)
    def test_atomic_rollback(self):
        p=self.proposal()
        self.db.execute("CREATE TRIGGER fail_invoice BEFORE INSERT ON invoices BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(Exception): workflow.approve(self.db,'demo','owner',p)
        self.assertEqual(agreements.balance(self.db,'demo','care-v1'),1)
        self.assertEqual(inventory.read(self.db,'demo')[0]['available'],6)
        self.assertEqual(workflow.job(self.db,'demo')['status'],'Awaiting confirmation')
    def test_concurrent_approvals(self):
        ids=[self.proposal(),self.proposal()]
        def run(p):
            db=connect(self.path)
            try:
                workflow.approve(db,'demo','owner',p)
                return True
            except ValueError:return False
            finally:db.close()
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(run,ids))
        self.assertEqual(sum(results),1)
        self.assertEqual(agreements.balance(self.db,'demo','care-v1'),0)
    def test_module_dependencies_and_disabled_command(self):
        with self.assertRaises(ValueError):configure(self.db,'demo','owner',['workflow'])
        configure(self.db,'demo','owner',['crm'])
        with self.assertRaises(ValueError):self.proposal()
        self.assertEqual(agreements.balance(self.db,'demo','care-v1'),1)

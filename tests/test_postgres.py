"""Run the same behavior suite in disposable PostgreSQL schemas when opted in."""
import os
import unittest
import uuid
from unittest.mock import patch
from operations.db import PostgresConnection, SCHEMA
from test_operations import OperationsTests as BaseOperationsTests


@unittest.skipUnless(os.environ.get('GOOB_TEST_POSTGRES_URL'), 'PostgreSQL integration URL not configured')
class PostgresTests(BaseOperationsTests):
    def setUp(self):
        self.schema = 'goob_test_' + uuid.uuid4().hex
        self.path = os.environ['GOOB_TEST_POSTGRES_URL']
        self.db = PostgresConnection(self.path)
        self.db.execute(f'CREATE SCHEMA {self.schema}')
        self.db.execute(f'SET search_path TO {self.schema}')
        self.db.execute(SCHEMA)
        from operations.db import seed
        seed(self.db)
        def connect_test(path):
            db = PostgresConnection(path)
            db.execute(f'SET search_path TO {self.schema}')
            return db
        self.patcher = patch('test_operations.connect', connect_test)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.db.rollback()
        self.db.execute(f'DROP SCHEMA {self.schema} CASCADE')
        self.db.close()

    def test_atomic_rollback(self):
        from operations.modules import workflow, agreements, inventory
        proposal = self.proposal()
        self.db.execute("""CREATE FUNCTION fail_invoice() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'test failure'; END $$;
            CREATE TRIGGER fail_invoice BEFORE INSERT ON invoices
            FOR EACH ROW EXECUTE FUNCTION fail_invoice()""")
        with self.assertRaises(Exception):
            workflow.approve(self.db, 'demo', 'owner', proposal)
        self.assertEqual(agreements.balance(self.db, 'demo', 'care-v1'), 1)
        self.assertEqual(inventory.read(self.db, 'demo')[0]['available'], 6)
        self.assertEqual(workflow.job(self.db, 'demo')['status'], 'Awaiting confirmation')

# Avoid collecting the imported base class a second time.
del BaseOperationsTests

"""Offline guards: application configuration must never select a local database."""
import unittest
from unittest.mock import patch

from operations.config import database_target
from operations.db import connect, PostgresConnection


class CloudConfigurationTests(unittest.TestCase):
    def test_missing_cloud_url_fails_without_fallback(self):
        with patch.dict('os.environ', {}, clear=True), patch('dotenv.load_dotenv'):
            with self.assertRaises(RuntimeError):
                database_target()

    def test_old_local_override_is_rejected(self):
        with patch.dict('os.environ', {'GOOB_DEMO_DB': '/tmp/old.sqlite3'}, clear=True):
            with self.assertRaises(RuntimeError):
                database_target()

    def test_native_cloud_url_is_preserved(self):
        url = 'postgresql://test@example.invalid/test?sslmode=verify-full'
        with patch.dict('os.environ', {'DATABASE_URL': url}, clear=True), patch('dotenv.load_dotenv'):
            self.assertEqual(database_target(), url)

    def test_file_path_is_not_opened_as_a_database(self):
        with self.assertRaises(ValueError):
            connect('/tmp/old.sqlite3')

    def test_plaintext_cloud_connection_is_rejected_before_connect(self):
        with patch('psycopg2.connect') as connection:
            with self.assertRaises(ValueError):
                PostgresConnection('postgresql://test@example.invalid/test?sslmode=disable')
            connection.assert_not_called()

    def test_cloud_certificate_verification_is_not_downgraded(self):
        with patch('psycopg2.connect') as connection:
            PostgresConnection('postgresql://test@example.invalid/test?sslmode=verify-full')
            self.assertEqual(connection.call_args.kwargs['sslmode'], 'verify-full')

    def test_normal_connection_never_initializes_schema(self):
        with patch('operations.db.PostgresConnection') as adapter:
            connect('postgresql://test@example.invalid/test?sslmode=require')
            adapter.return_value.initialize.assert_not_called()

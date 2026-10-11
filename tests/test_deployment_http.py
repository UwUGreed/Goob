"""Offline tests for deployment health and the HTTPS proxy origin boundary."""
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch

with patch('operations.config.database_target', return_value='postgresql://unused/test'):
    server = importlib.import_module('operations.server')


class DeploymentHTTPTests(unittest.TestCase):
    def handler(self, path):
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.reply = MagicMock()
        handler.headers = {}
        return handler

    def test_health_checks_database_and_closes_connection(self):
        handler = self.handler('/api/health')
        with patch.object(server, 'connect') as connect:
            handler.do_GET()
            connect.return_value.execute.assert_called_once_with('SELECT 1 FROM tenants LIMIT 1')
            connect.return_value.close.assert_called_once()
        handler.reply.assert_called_once_with(200, {'status': 'ok'})

    def test_health_failure_does_not_disclose_exception(self):
        handler = self.handler('/api/health')
        with patch.object(server, 'connect', side_effect=RuntimeError('SECRET')):
            handler.do_GET()
        handler.reply.assert_called_once_with(503, {'status': 'unavailable'})

    def test_https_origin_reaches_command_validation(self):
        handler = self.handler('/api/unknown')
        handler.headers = {'Origin': 'https://demo.example', 'Host': 'demo.example'}
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = b'{}'
        with patch.dict(os.environ, {'GOOB_PUBLIC_ORIGIN': 'https://demo.example'}), patch.object(server, 'connect'):
            handler.do_POST()
        self.assertEqual(handler.reply.call_args.args[0], 400)

    def test_other_origin_rejected_before_database_access(self):
        handler = self.handler('/api/propose')
        handler.headers = {'Origin': 'https://attacker.example', 'Host': 'demo.example'}
        with patch.dict(os.environ, {'GOOB_PUBLIC_ORIGIN': 'https://demo.example'}), patch.object(server, 'connect') as connect:
            handler.do_POST()
            connect.assert_not_called()
        self.assertEqual(handler.reply.call_args.args[0], 403)

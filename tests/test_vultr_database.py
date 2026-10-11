"""Cloud deployment target guards; no network or database mutations."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'vultr_database', Path(__file__).resolve().parents[1] / 'scripts/vultr-database.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CloudDeploymentTargetTests(unittest.TestCase):
    def config(self):
        url = 'postgresql://user:password@cloud.example:12345/tsdb?sslmode=verify-full&sslrootcert=/etc/tiger/ca.pem'
        return dict(DATABASE_URL=url, GOOB_DATABASE_URL=url,
                    TIGER_DB_HOST='cloud.example', TIGER_DB_PORT='12345', TIGER_DB_NAME='tsdb')

    def test_matching_cloud_target(self):
        self.assertEqual(module.validate_target(self.config()), ('cloud.example', '12345', 'tsdb'))

    def test_host_port_database_mismatch(self):
        for key in ('TIGER_DB_HOST', 'TIGER_DB_PORT', 'TIGER_DB_NAME'):
            config = self.config()
            config[key] = '99999' if key == 'TIGER_DB_PORT' else 'wrong'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                module.validate_target(config)

    def test_insecure_or_untrusted_tls(self):
        for replacement in ('sslmode=require', 'sslmode=disable', 'sslmode=verify-full'):
            config = self.config()
            config['DATABASE_URL'] = config['DATABASE_URL'].split('?')[0] + '?' + replacement
            with self.subTest(tls=replacement), self.assertRaises(RuntimeError):
                module.validate_target(config)

    def test_local_target_and_override_rejected(self):
        config = self.config()
        config['TIGER_DB_HOST'] = '127.0.0.1'
        with self.assertRaises(RuntimeError):
            module.validate_target(config)
        config = self.config()
        config['GOOB_API_DATABASE_URL'] = 'postgresql://other/db'
        with self.assertRaises(RuntimeError):
            module.validate_target(config)

    def test_hackathon_requires_explicit_opt_in_and_encryption(self):
        config = self.config()
        for key in ('DATABASE_URL', 'GOOB_DATABASE_URL'):
            config[key] = config[key].split('?')[0] + '?sslmode=require'
        config.update(GOOB_ENV='hackathon', GOOB_HACKATHON_UNVERIFIED_TLS='1')
        self.assertEqual(module.validate_target(config), ('cloud.example', '12345', 'tsdb'))
        for changes in ({'GOOB_ENV': 'production'}, {'GOOB_HACKATHON_UNVERIFIED_TLS': '0'},
                        {'DATABASE_URL': config['DATABASE_URL'].replace('require', 'disable')}):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                module.validate_target(dict(config, **changes))

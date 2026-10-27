import tempfile
import unittest
from pathlib import Path

from tools.planner_dev_server import PersonalStore


class PersonalConfigTest(unittest.TestCase):
    def test_persist_backup_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'personal_config.json'
            store = PersonalStore(path)
            payload = {'format': 'matrix-planner-v2', 'characters': [], 'teams': []}
            first = store.save(None, payload)
            self.assertEqual(PersonalStore(path).read(), first)
            with self.assertRaises(FileExistsError):
                store.save(None, payload)
            store.save(first['revision'], payload)
            self.assertTrue(path.with_suffix('.previous.json').exists())

    def test_invalid_configuration_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'personal_config.json'
            with self.assertRaises(ValueError):
                PersonalStore(path).save(None, {'format': 'unknown'})
            self.assertFalse(path.exists())

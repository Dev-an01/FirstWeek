"""Regression coverage for explicit profile selection after persona retirement."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "profile_id_mapper", Path(__file__).parents[1] / "profile_management" / "profile_id_mapper.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfileSelectionTest(unittest.TestCase):
    def test_missing_selection_fails_and_unknown_ids_never_redirect(self):
        for value in (None, ""):
            with self.assertRaises(ValueError):
                module.normalize_profile_id(value)
        for value in ("workspace_profile", "exec_001_test", "unknown-profile"):
            self.assertEqual(module.ProfileIDMapper.to_database_id(value), value)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app.utils.path_utils import resolve_path


class PathTests(unittest.TestCase):
    def test_session_file_paths_cannot_escape_work_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = (Path(folder)/'session_test').resolve()
            root.mkdir()
            self.assertEqual(Path(resolve_path('report.md',str(root))),root/'report.md')
            for value in ['../secret.key',str(Path(folder)/'secret.key'),'updated/../../secret.key']:
                with self.subTest(path=value), self.assertRaises(ValueError):
                    resolve_path(value,str(root))

    def test_virtual_workspace_and_repeated_session_prefixes_are_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = (Path(folder)/'session_test').resolve(); root.mkdir()
            self.assertEqual(Path(resolve_path('/workspace/report.md',str(root))),root/'report.md')
            self.assertEqual(Path(resolve_path('output/session_test/report.md',str(root))),root/'report.md')


if __name__ == '__main__':
    unittest.main()

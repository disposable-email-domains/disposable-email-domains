import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VERIFY = Path(__file__).resolve().parents[1] / "verify.py"


class VerifyCLITests(unittest.TestCase):
    def run_verify(self, blocklist, suffix_list="com\n"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "disposable_email_blocklist.conf").write_text(blocklist, encoding="utf-8")
            (root / "publicsuffixlist.local").write_text("", encoding="utf-8")
            # Keep the normal CLI entry point and PSL parser; only the HTTP
            # response is replaced with a tiny UTF-8 public suffix list.
            script = (
                "import runpy, sys\n"
                "from unittest.mock import patch\n"
                f"sys.argv = [{str(VERIFY)!r}]\n"
                "with patch('requests.get') as get:\n"
                f"    get.return_value.content = {suffix_list.encode('utf-8')!r}\n"
                f"    runpy.run_path({str(VERIFY)!r}, run_name='__main__')\n"
            )
            return subprocess.run(
                [sys.executable, "-X", "utf8=0", "-c", script],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=30,
            )

    def test_utf8_suffix_list(self):
        result = self.run_verify("example.com\n", "// UTF-8 comment: \u4e8f\ncom\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("All domain entries seem valid.", result.stdout)

if __name__ == "__main__":
    unittest.main()

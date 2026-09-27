#!/usr/bin/env python3
"""Exercise the real launcher: adjacent payloads need a scoped, consensual grant."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerFolder(unittest.TestCase):
    def launch(self, consent):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            tools = work / "bin"
            tools.mkdir()
            folder = work / "Game files (1)"
            folder.mkdir()
            target = folder / "setup.exe"
            target.write_bytes(b"MZ")
            (folder / "data1.bin").write_bytes(b"payload")
            output = work / "args.json"
            scripts = {
                "engine": '#!/bin/sh\necho \'{"name":{"en":"Windows programs"},"ready":true,"chosen":{"id":"com.usebottles.bottles","sandboxed":true}}\'\n',
                "kdialog": f"#!/bin/sh\nexit {consent}\n",
                "notify-send": "#!/bin/sh\nexit 0\n",
                # Synchronous in the fixture, never detach a real desktop process.
                "setsid": '#!/bin/sh\nexec "$@"\n',
                "flatpak": '#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["TEST_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n',
            }
            for name, text in scripts.items():
                path = tools / name
                path.write_text(text)
                path.chmod(0o755)
            env = {"PATH": f"{tools}:/usr/bin:/bin", "HOME": raw,
                   "MOOS_APP_ENGINE": str(tools / "engine"), "TEST_ARGS": str(output)}
            result = subprocess.run(["bash", str(ROOT / "system_files/usr/bin/moos-run-foreign"),
                                     str(target)], env=env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            if consent == 1:
                deadline = time.monotonic() + 2
                while not output.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
            return json.loads(output.read_text()) if output.exists() else None, str(folder), str(target)

    def test_accepted_folder_is_read_only_and_per_launch(self):
        args, folder, target = self.launch(1)
        self.assertEqual(args, ["run", f"--filesystem={folder}:ro", "--command=bottles",
                                "--file-forwarding", "com.usebottles.bottles", "@@u", target, "@@"])

    def test_cancel_and_escape_launch_nothing(self):
        for response in (0, 2):
            self.assertIsNone(self.launch(response)[0])


if __name__ == "__main__":
    unittest.main()

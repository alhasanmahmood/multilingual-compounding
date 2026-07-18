import os
import pathlib
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.env import load_env_file  # noqa: E402


class EnvLoaderTests(unittest.TestCase):
    def test_native_openai_key_does_not_inherit_openrouter_base_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = pathlib.Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        'OPENAI_API_KEY="native-key"',
                        'OPENROUTER_API_KEY="router-key"',
                        'OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"',
                    ]
                ),
                encoding="utf-8",
            )

            original = {
                key: os.environ.get(key)
                for key in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"]
            }
            try:
                for key in original:
                    os.environ.pop(key, None)
                load_env_file(env_path)
                self.assertEqual(os.environ.get("OPENAI_API_KEY"), "native-key")
                self.assertIsNone(os.environ.get("OPENAI_BASE_URL"))
            finally:
                for key in original:
                    os.environ.pop(key, None)
                    if original[key] is not None:
                        os.environ[key] = original[key]


if __name__ == "__main__":
    unittest.main()

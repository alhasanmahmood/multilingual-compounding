import pathlib
import sys
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.settings import (  # noqa: E402
    env_backbone_pool_model_keys,
    language_pairs,
    resolve_language_codes,
    resolve_model_keys,
)


class SettingsTests(unittest.TestCase):
    def test_resolve_model_keys_accepts_openrouter_pool_entries(self):
        resolved = resolve_model_keys(
            [
                "openrouter/openai/gpt-5.4",
                "openrouter/google/gemini-3-flash-preview",
                "anthropic/claude-sonnet-4.6",
                "openai/gpt-4.1",
                "anthropic/claude-opus-4.1",
                "google/gemini-2.5-pro-preview",
            ]
        )
        self.assertEqual(
            resolved,
            [
                "gpt54",
                "gemini",
                "claude_sonnet46",
                "gpt41",
                "claude_opus41",
                "gemini25_pro_preview",
            ],
        )

    def test_env_backbone_pool_model_keys_deduplicates_aliases(self):
        resolved = env_backbone_pool_model_keys(
            "openrouter/openai/gpt-4o-2024-08-06,gpt4o,openrouter/google/gemini-3-flash-preview"
        )
        self.assertEqual(resolved, ["gpt4o", "gemini"])

    def test_resolve_language_codes_preserves_requested_order(self):
        resolved = resolve_language_codes(["tr", "en", "tr"])
        self.assertEqual(resolved, ["TR", "EN"])

    def test_language_pairs_filters_to_requested_subset(self):
        pairs = language_pairs(["EN", "TR"])
        self.assertEqual(pairs, [("EN", "English"), ("TR", "Turkish")])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_expansion_manuscript as updater


class PrimaryDisplayRegenerationTests(unittest.TestCase):
    def test_regeneration_preserves_reviewed_manuscript(self):
        """Regenerating evidence displays must not replace an author's prose."""
        with tempfile.TemporaryDirectory() as temporary:
            target = pathlib.Path(temporary)
            analysis = target / "analysis/bfcl"
            analysis.mkdir(parents=True)
            paper = target / "paper"
            paper.mkdir()
            prose = b"Reviewed manuscript with edits that must survive regeneration.\n"
            (paper / "main.tex").write_bytes(prose)
            for name in ("newstudy20261010_expansion_collection_audit.json", "newstudy20261010_expansion_cf_summary.json"):
                (analysis / name).write_bytes((ROOT / "analysis/bfcl" / name).read_bytes())
            audit = json.loads((analysis / "newstudy20261010_expansion_collection_audit.json").read_text())
            with patch.object(updater, "ROOT", target), patch.object(updater, "validate_completed_collection", return_value=audit):
                updater.main()
            self.assertEqual((paper / "main.tex").read_bytes(), prose)
            self.assertIn("Model & Lang.", (paper / "generated/newstudy20261010_main_table.tex").read_text())
            self.assertIn(r"\label{fig:results}", (paper / "generated/newstudy20261010_delta_figure.tex").read_text())


if __name__ == "__main__":
    unittest.main()

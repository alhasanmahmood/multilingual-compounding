"""Apply indexed AI review proposals and refresh corrected backtranslations.

Only public benchmark text is sent to the configured translation provider.
The original cache and every before/after edit are retained as audit artifacts.
Human approval remains pending. No benchmark model collection occurs here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from multilingual_compounding.bfcl_vendor import load_bfcl_multiturn_tasks
from multilingual_compounding.env import load_env_file
from multilingual_compounding.evaluation import (
    _provider_credentials, _validate_localization_record, get_original_turn_texts,
    read_jsonl, task_content_sha256, write_jsonl_atomic, write_localization_review_report,
)
from multilingual_compounding.localization import OpenAICompatibleTranslator, build_localization_artifact
from multilingual_compounding.paths import ROOT_ENV_FILE
from multilingual_compounding.settings import PILOT_TEST_CATEGORIES

PREFIX = "newstudy20261010"
QUOTED = re.compile(r"(?<!\w)'([^'\n]+)'(?!\w)|\"([^\"\n]+)\"")


def turns_hash(turns):
    return hashlib.sha256(json.dumps(turns, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply proposals and refresh backtranslations through live API calls")
    args = parser.parse_args()
    analysis = ROOT / "analysis/bfcl"
    cache = ROOT / f"data/bfcl/localized_queries/{PREFIX}_bfcl_multiturn_localizations.jsonl"
    backup = analysis / f"{PREFIX}_localizations_before_review.jsonl"
    rows = read_jsonl(cache)
    if len(rows) != 160 or len({(r['task_id'], r['language_code']) for r in rows}) != 160:
        raise ValueError("Expected exactly 160 unique localization rows")
    tasks = {t.prompt_entry['id']: t for t in load_bfcl_multiturn_tasks(list(PILOT_TEST_CATEGORIES))}
    reviews = {}
    for suffix in ("AR_HI_SW", "TR_ZH", "JA_ES"):
        path = analysis / f"{PREFIX}_translation_review_{suffix}.json"
        for record in json.loads(path.read_text(encoding="utf8"))["records"]:
            key = (record['task_id'], record['language_code'])
            if key in reviews:
                raise ValueError(f"Duplicate review {key}")
            reviews[key] = (record, path)
    proposals = []
    for row in rows:
        task = tasks[row['task_id']]
        source = get_original_turn_texts(task)
        if row['language_code'] == 'EN':
            _validate_localization_record(row, task, 'EN')
            continue
        review, path = reviews[(row['task_id'], row['language_code'])]
        review_hash = hashlib.sha256(json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        existing = row.get('ai_review', {})
        if (existing.get('status') in {'reviewed', 'corrected'}
                and existing.get('localized_turns_sha256') == turns_hash(row['localized_turns'])
                and existing.get('audit_record_sha256') == review_hash):
            if review['status'] not in {'reviewed', 'correction_proposed'} or review.get('original_source_task_sha256') != task_content_sha256(task):
                raise ValueError('Previously applied review is no longer approved or source-aligned')
            for original, target in zip(source, row['localized_turns']):
                if any((left or right) not in target for left, right in QUOTED.findall(original)):
                    raise ValueError('Previously reviewed target has missing exact quoted literals')
            _validate_localization_record(row, task, row['language_code'])
            continue
        if review['localized_turns_sha256'] != turns_hash(row['localized_turns']):
            raise ValueError(f"Review hash mismatch: {row['task_id']}/{row['language_code']}")
        if review.get('original_source_task_sha256') != task_content_sha256(task):
            raise ValueError("Review source hash mismatch")
        if review['status'] not in {'reviewed', 'correction_proposed'}:
            raise ValueError(f"Unresolved review {row['task_id']}/{row['language_code']}: {review['status']}")
        proposed = list(row['localized_turns'])
        proposed.extend([''] * max(0, len(source) - len(proposed)))
        if len(proposed) != len(source):
            raise ValueError("Review must repair turn alignment")
        for correction in review.get('corrections', []):
            index = correction['turn_index']
            if not 0 <= index < len(source):
                raise ValueError("Correction turn index out of range")
            proposed[index] = correction['replacement']
        for original, target in zip(source, proposed):
            if bool(original.strip()) != bool(target.strip()):
                raise ValueError(f"Unrepaired empty-turn alignment: {row['task_id']}/{row['language_code']}")
            literals = [left or right for left, right in QUOTED.findall(original)]
            missing = [literal for literal in literals if literal not in target]
            if missing:
                raise ValueError(f"Exact quoted literals missing: {row['task_id']}/{row['language_code']}: {missing}")
        proposals.append((row, task, proposed, review, path))
    print(f"Validated {len(reviews)} non-English reviews; {sum(p[0]['localized_turns'] != p[2] for p in proposals)} rows require correction.", flush=True)
    if not args.apply:
        return
    load_env_file(ROOT_ENV_FILE)
    key, url = _provider_credentials('openrouter')
    translator = OpenAICompatibleTranslator(model='openai/gpt-4o-2024-08-06', api_key=key, base_url=url)
    if not backup.exists():
        write_jsonl_atomic(backup, copy.deepcopy(rows))
    for row, task, proposed, review, path in proposals:
        review_hash = hashlib.sha256(json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        before = copy.deepcopy(row)
        changed = proposed != row['localized_turns']
        if changed:
            print(f"Refreshing corrected backtranslation: {row['task_id']}/{row['language_code']}", flush=True)
            translator.provider_reported_model_ids.clear()
            backtranslated = translator.backtranslate_turns(proposed, row['language_name'])
            row.update(asdict(build_localization_artifact(
                task.prompt_entry['id'], row['language_code'], row['language_name'],
                get_original_turn_texts(task), proposed, backtranslated, task.ground_truth,
            )))
        row['ai_review'] = {
            'status': 'corrected' if changed else 'reviewed',
            'reviewer': 'Codex AI direct-text review with independent language-group review',
            'reviewed_at': datetime.now(timezone.utc).isoformat(),
            'audit_path': str(path.relative_to(ROOT)),
            'audit_record_sha256': review_hash,
            'source_task_sha256': task_content_sha256(task),
            'localized_turns_sha256': turns_hash(proposed),
            'unresolved_issues': [],
            'corrections': review.get('corrections', []),
            'backtranslation_refresh_model': translator.model if changed else None,
            'backtranslation_refresh_provider_reported_model_ids': list(dict.fromkeys(translator.provider_reported_model_ids)) if changed else [],
            'before_localized_turns_sha256': turns_hash(before['localized_turns']),
        }
        _validate_localization_record(row, task, row['language_code'])
        write_jsonl_atomic(cache, rows)
    write_localization_review_report(list({r['task_id']: tasks[r['task_id']] for r in rows}.values()), rows,
                                     analysis / f"{PREFIX}_localization_review.md", cache)
    print('All translations reviewed; human approval remains pending.', flush=True)


if __name__ == '__main__':
    main()

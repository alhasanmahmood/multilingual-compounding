"""Create an offline, filterable view of the expansion translation audit."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'newstudy20261010'


def main():
    cache = ROOT / f'data/bfcl/localized_queries/{PREFIX}_bfcl_multiturn_localizations.jsonl'
    rows = [json.loads(line) for line in cache.read_text(encoding='utf8').splitlines() if line.strip()]
    attestation_path = ROOT / f'analysis/bfcl/{PREFIX}_author_translation_review.json'
    attestation = None
    if attestation_path.exists():
        attestation = json.loads(attestation_path.read_text(encoding='utf8'))
        if attestation['cache_sha256'] != hashlib.sha256(cache.read_bytes()).hexdigest():
            raise ValueError('Author review attestation belongs to a different cache')
    source = {r['task_id']: r['localized_turns'] for r in rows if r['language_code'] == 'EN'}
    for row in rows:
        row['source_turns'] = source[row['task_id']]
    data = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>BFCL translation review</title><style>
body{font:16px/1.5 system-ui,sans-serif;margin:24px;color:#172d3b;background:#f7fafb}main{max-width:1500px;margin:auto}
h1{font-size:26px}select{font:inherit;margin:0 24px 12px 8px;padding:7px}table{width:100%;border-collapse:collapse;background:white}
th,td{padding:14px;border:1px solid #d2dce0;vertical-align:top;text-align:start;width:33%}th{background:#e5eff2}
.turn{margin:28px 0}p{max-width:1050px}.status{padding:12px;background:#e5eff2;border-radius:6px}
details{background:white;padding:12px;margin-top:12px}code{font-size:13px}a{color:#176788}
</style><main><h1>20-scenario BFCL translation review</h1>
<p>Compare each translation with the English source. The backtranslation is a secondary check.
AI review and corrections are recorded separately from human review. Exact quoted action text,
file names and lookup names retain their source spelling. Empty source turns remain empty.</p>
<p id="author-review"></p>
<label>Language<select id="language"></select></label><label>Scenario<select id="task"></select></label>
<div class="status" id="status"></div><details><summary>Recorded corrections</summary><div id="edits"></div></details>
<div id="turns"></div></main><script>
const rows=DATA;const authorReview=AUTHOR_REVIEW;
if(authorReview){document.querySelector('#author-review').textContent='Subsequent author review reported '+authorReview.reported_date+': '+authorReview.reported_method+'. Judgment: '+authorReview.reported_judgment+' This is author attestation, not independent bilingual expert validation. Individual cache statuses retain their collection-time values.';}
const language=document.querySelector('#language'),task=document.querySelector('#task');
const codes=[...new Set(rows.map(r=>r.language_code))].filter(c=>c!=='EN');
for(const c of codes){const o=document.createElement('option');o.value=c;o.textContent=rows.find(r=>r.language_code===c).language_name+' ('+c+')';language.append(o)}
for(const id of [...new Set(rows.map(r=>r.task_id))]){const o=document.createElement('option');o.value=id;o.textContent=id;task.append(o)}
function show(){const r=rows.find(r=>r.language_code===language.value&&r.task_id===task.value);const ai=r.ai_review||{};
document.querySelector('#status').textContent='AI review before collection: '+(ai.status||'pending')+' | Human row approval at collection: '+(r.human_review?.status||'pending');
const edits=document.querySelector('#edits');edits.replaceChildren();for(const c of ai.corrections||[]){const p=document.createElement('p');p.textContent='Turn '+(c.turn_index+1)+': '+c.reason;edits.append(p)}if(!edits.childNodes.length)edits.textContent='No correction recorded.';
const turns=document.querySelector('#turns');turns.replaceChildren();r.source_turns.forEach((s,i)=>{const d=document.createElement('div');d.className='turn';const h=document.createElement('h2');h.textContent='Turn '+(i+1);h.style.fontSize='18px';d.append(h);const table=document.createElement('table');const header=document.createElement('tr');for(const title of ['English source',r.language_name,'Backtranslation']){const th=document.createElement('th');th.textContent=title;header.append(th)}table.append(header);const tr=document.createElement('tr');for(const value of [s,r.localized_turns[i],r.backtranslated_turns[i]]){const td=document.createElement('td');td.dir='auto';td.textContent=value===undefined?'[MISSING TURN]':value||'[Empty source-aligned turn]';tr.append(td)}table.append(tr);d.append(table);turns.append(d)})}
language.addEventListener('change',show);task.addEventListener('change',show);show();
</script></html>'''.replace('DATA', data).replace('AUTHOR_REVIEW', json.dumps(attestation, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))
    output = ROOT / f'analysis/bfcl/{PREFIX}_translation_review.html'
    output.write_text(html, encoding='utf8')
    print(output)


if __name__ == '__main__':
    main()

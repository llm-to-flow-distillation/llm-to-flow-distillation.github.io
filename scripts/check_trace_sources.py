#!/usr/bin/env python3
"""Check every exported representation and explicit judgment against the archive."""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive-root', type=Path, required=True)
args = parser.parse_args()
receipts = json.loads((ROOT / 'data/trace-sources.json').read_text())['sources']
for item in receipts:
    assert hashlib.sha256((args.archive_root / item['file']).read_bytes()).hexdigest() == item['sha256'], item['file']

@lru_cache(None)
def read(file):
    return json.loads((args.archive_root / file).read_text())

@lru_cache(None)
def pool(file):
    rows = [json.loads(line) for line in (args.archive_root / file).read_text().splitlines() if line.strip()]
    return {row.get('item_id', row.get('candidate_id')): row for row in rows}

counts = {'recorded_candidates': 0, 'verbatim_judge_outputs': 0, 'goal_rationales': 0, 'original_goals': 0, 'placeholder_slots': 0}
for task in json.loads((ROOT / 'data/tasks.json').read_text())['tasks']:
    for stage in task['stages']:
        selection = stage['selection']
        if selection['status'] == 'recorded':
            source = read(selection['source']['file'])
            if task['id'] == 'gsk3b':
                assert selection['rationale'] == source['proposal']['rationale']
                assert selection['bridge'] == source['proposal']['bridge_to_final_goal']
                assert selection['deferredRequirements'] == source['proposal']['deferred_final_requirements']
            else:
                assert selection['rationale'] == source['goal']['bridge_to_final']
                assert selection['uncertainty'] == source['goal']['limitations']
            counts['goal_rationales'] += 1
        elif selection['status'] == 'original-goal':
            counts['original_goals'] += 1
        for pair in stage['tracePairs']:
            for index, key in enumerate(['positiveId', 'negativeId']):
                trace = next(t for t in stage['traces'] if t['sampleId'] == pair[key])
                if trace['status'] == 'recorded':
                    rep = trace['representation']
                    original = pool(rep['source']['file'])[trace['sampleId']]
                    size = original['length'] if rep['kind'] == 'peptide' else original['card']['descriptors']['molecular_weight_da']
                    assert size == pair['sizes'][index]
        for trace in stage['traces']:
            if trace['status'] == 'placeholder':
                assert task['id'] in {'d2','ood'}
                assert trace['representation'] is None and trace['rationale'] is None and trace['uncertainty'] is None
                counts['placeholder_slots'] += 1
                continue
            rep = trace['representation']
            row = pool(rep['source']['file'])[trace['sampleId']]
            if rep['kind'] == 'peptide':
                assert rep['value'] == row['sequence']
            else:
                assert rep['value'] == row['card']['identity']['isomeric_smiles']
            for output in trace['passes']:
                source = read(output['source']['file'])
                rows = source['result']['judgments'] if rep['kind'] == 'peptide' else source['results']
                saved = next(row for row in rows if row.get('item_id',row.get('candidate_id')) == trace['sampleId'])
                assert output['rationale'] == saved['rationale']
                assert output['uncertainty'] == saved['critical_unknowns']
                assert output['label'].lower() == saved.get('final_label',saved.get('label'))
                assert not saved.get('override_reason')
                counts['verbatim_judge_outputs'] += 1
            counts['recorded_candidates'] += 1
assert counts == {'recorded_candidates':64,'verbatim_judge_outputs':128,'goal_rationales':13,'original_goals':3,'placeholder_slots':28}, counts
print(json.dumps({'status':'passed','source_receipts':len(receipts),**counts},indent=2))

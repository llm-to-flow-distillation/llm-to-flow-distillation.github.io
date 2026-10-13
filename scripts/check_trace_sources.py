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
    indexed = {}
    for row in rows:
        for key in ['item_id', 'candidate_id', 'generation_id']:
            if row.get(key):
                assert row[key] not in indexed or indexed[row[key]] == row
                indexed[row[key]] = row
    return indexed


def candidate(trace):
    rows = pool(trace['representation']['source']['file'])
    # New molecular traces also retain the generation identifier, which can
    # differ from the judge item number after failed/unjudgeable attempts.
    for key in [trace.get('generationId'), trace['sampleId']]:
        if key in rows:
            return rows[key]
    raise AssertionError(f"Candidate not found: {trace['sampleId']}")


def field(source, path):
    for key in path.split('.'):
        source = source[key]
    return source

counts = {'recorded_candidates': 0, 'verbatim_judge_outputs': 0, 'goal_rationales': 0, 'original_goals': 0, 'placeholder_slots': 0}
for task in json.loads((ROOT / 'data/tasks.json').read_text())['tasks']:
    for stage in task['stages']:
        selection = stage['selection']
        assert selection['status'] in {'recorded', 'original-goal'}
        if selection['status'] == 'recorded':
            source = read(selection['source']['file'])
            assert selection['rationale'] == field(source, selection['rationaleField'])
            if selection['rationaleField'] == 'proposal.rationale':
                assert selection['bridge'] == source['proposal']['bridge_to_final_goal']
                assert selection['deferredRequirements'] == source['proposal']['deferred_final_requirements']
            if selection.get('uncertaintyField'):
                assert selection['uncertainty'] == field(source, selection['uncertaintyField'])
            counts['goal_rationales'] += 1
        elif selection['status'] == 'original-goal':
            source = read(selection['source']['file'])
            original_goal = source['final_goal'] if 'final_goal' in source else source['goal']['frontier_criterion']
            assert original_goal.strip() == stage['exactGoal'].strip()
            counts['original_goals'] += 1
        if stage.get('traceProvenance'):
            stable = read(stage['traceProvenance']['stableSummary']['file'])
            assert stable['goal'].strip() == stage['exactGoal'].strip()
        for pair in stage['tracePairs']:
            for index, key in enumerate(['positiveId', 'negativeId']):
                trace = next(t for t in stage['traces'] if t['sampleId'] == pair[key])
                assert trace['status'] == 'recorded'
                rep = trace['representation']
                original = candidate(trace)
                size = original['length'] if rep['kind'] == 'peptide' else original['card']['descriptors']['molecular_weight_da']
                assert size == pair['sizes'][index]
        for trace in stage['traces']:
            assert trace['status'] == 'recorded'
            rep = trace['representation']
            row = candidate(trace)
            if rep['kind'] == 'peptide':
                assert rep['value'] == row['sequence']
            else:
                assert rep['value'] == row['card']['identity']['isomeric_smiles']
                descriptors = row['card']['descriptors']
                assert trace['observables'] == [
                    {'label': label, 'value': str(descriptors[key])}
                    for key, label in [('molecular_weight_da', 'MW (Da)'), ('hydrogen_bond_donor_count', 'H-bond donors'), ('hydrogen_bond_acceptor_count', 'H-bond acceptors')]
                ]
            assert [output['pass'] for output in trace['passes']] == [1, 2]
            for output in trace['passes']:
                source = read(output['source']['file'])
                rows = source['result']['judgments'] if rep['kind'] == 'peptide' else source['results']
                saved = next(row for row in rows if row.get('item_id',row.get('candidate_id')) == trace['sampleId'])
                assert output['rationale'] == saved['rationale']
                assert output['uncertainty'] == saved['critical_unknowns']
                assert output['label'] == trace['label']
                assert output['label'].lower() == saved.get('final_label',saved.get('label')).lower()
                assert not saved.get('override_reason')
                counts['verbatim_judge_outputs'] += 1
            counts['recorded_candidates'] += 1
assert counts == {'recorded_candidates':90,'verbatim_judge_outputs':180,'goal_rationales':18,'original_goals':5,'placeholder_slots':0}, counts
print(json.dumps({'status':'passed','source_receipts':len(receipts),**counts},indent=2))

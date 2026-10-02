#!/usr/bin/env python3
"""Import allowlisted final-output evidence from a local archive; no model calls.

Usage: python3.11 scripts/import_traces.py --archive-root /path/to/archive
Only portable source paths and content hashes enter the public data.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', required=True, type=Path)
    args = parser.parse_args()
    archive = args.archive_root.resolve()
    data_path = ROOT / 'data/tasks.json'
    data = json.loads(data_path.read_text())
    receipts = {}

    def receipt(path):
        path = Path(path)
        relative = str(path.relative_to(archive))
        entry = {'file': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        receipts[relative] = entry
        return entry

    def read(path):
        receipt(path)
        return json.loads(Path(path).read_text())

    def pool(path):
        receipt(path)
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    molecular = {
        'g0': ('EXP-0131/campaign/rounds/round-01', 'EXP-0131/campaign/rounds/round-01/goal_selection/proposal-1.json'),
        'g1': ('EXP-0131/campaign/rounds/round-02', 'EXP-0131/campaign/rounds/round-02/goal_selection/proposal-1.json'),
        'g2': ('EXP-0131/campaign/rounds/round-05', 'EXP-0131/campaign/rounds/round-03/goal_selection/proposal-1.json'),
        'g3': ('EXP-0155/campaign/bound_goal/round-03', 'EXP-0131/campaign/rounds/round-06/goal_selection/proposal-1.json'),
        'g': ('EXP-0165/campaign/final_f/round-02', None),
    }
    previous = ROOT / 'data/trace-summary-archive.json'
    if not previous.exists():
        previous.write_text(json.dumps({'description': 'Previous illustrative paraphrases, superseded by verbatim archived judgments or explicitly marked placeholders.', 'tasks': {t['id']: {s['id']: s['traces'] for s in t['stages']} for t in data['tasks']}}, ensure_ascii=False, indent=2) + '\n')

    prior_examples = json.loads(previous.read_text())['tasks']
    for task in data['tasks']:
        for stage in task['stages']:
            if task['id'] in {'d2', 'ood'}:
                stage['selection'] = {'status': 'placeholder', 'rationale': None, 'uncertainty': None}
                stage['traces'] = [{'status': 'placeholder', 'label': label, 'sampleId': f'placeholder-{label.lower()}-{i}', 'representation': None, 'rationale': None, 'uncertainty': None} for label in ('POSITIVE', 'NEGATIVE') for i in (1, 2)]
                continue
            first_path = archive / stage['traces'][0]['source']
            first = read(first_path)
            peptide = task['id'] in {'anticancer', 'cpp'}
            second_path = first_path.with_name('pass-1.json' if peptide else 'repeat-2.json')
            second = read(second_path)
            if peptide:
                campaign = first_path.parents[3]
                manifest = read(campaign / 'distributions' / first['distribution_id'] / 'distribution_split_manifest.json')
                pool_path = Path(manifest['source_artifact']['path'])
                assert receipt(pool_path)['sha256'] == manifest['source_artifact']['sha256']
                candidates = {row['candidate_id']: row for row in pool(pool_path)}
                goal_path = campaign / 'goals' / (first['goal_id'] + '.json')
                goal_doc = read(goal_path)
                goal = goal_doc['goal']
                assert goal['frontier_criterion'].strip() == stage['exactGoal'].strip()
                stage['selection'] = {'status': 'original-goal' if goal['is_final'] else 'recorded', 'rationale': goal['bridge_to_final'], 'uncertainty': goal['limitations'], 'rationaleField': 'goal.bridge_to_final', 'uncertaintyField': 'goal.limitations', 'source': receipt(goal_path)}
                rows1, rows2 = first['result']['judgments'], second['result']['judgments']
                id_key, label_key = 'candidate_id', 'label'
            else:
                round_dir, proposal = molecular[stage['id']]
                round_record = read(archive / round_dir / 'round_result.json')
                judgment_key = 'target_child_judgment' if stage['id'] == 'g3' else 'child_final_goal_judgment' if stage['id'] == 'g' else 'child_development_judgment'
                assert round_record[judgment_key] == first_path.parent.name
                cohort_path = archive / round_dir / 'development/child/cohort_receipt.json'
                cohort = read(cohort_path)
                pool_path = Path(cohort['pool']) / 'candidate_pool.jsonl'
                candidates = {row['item_id']: row for row in pool(pool_path)}
                stable = read(first_path.with_name('stable_summary.json'))
                assert stable['goal'].strip() == stage['exactGoal'].strip()
                if proposal:
                    proposal_path = archive / proposal
                    doc = read(proposal_path)
                    p = doc['proposal']
                    assert doc['accepted'] is True and p['proposed_goal'].strip() == stage['exactGoal'].strip()
                    stage['selection'] = {'status': 'recorded', 'rationale': p['rationale'], 'bridge': p['bridge_to_final_goal'], 'deferredRequirements': p['deferred_final_requirements'], 'rationaleField': 'proposal.rationale', 'source': receipt(proposal_path)}
                else:
                    config_path = archive / 'EXP-0165/campaign/frozen_config.json'
                    assert read(config_path)['final_goal'].strip() == stage['exactGoal'].strip()
                    stage['selection'] = {'status': 'original-goal', 'rationale': None, 'uncertainty': None, 'source': receipt(config_path)}
                rows1, rows2 = first['results'], second['results']
                id_key, label_key = 'item_id', 'final_label'
            map2 = {row[id_key]: row for row in rows2}
            picked = []
            # Keep previously shown examples, then use archive order. Never rank by activity.
            old_ids = [t['sampleId'] for t in prior_examples[task['id']][stage['id']]]
            ordered = sorted(enumerate(rows1), key=lambda pair: (0 if pair[1][id_key] in old_ids else 1, pair[0]))
            for label in ('positive', 'negative'):
                eligible = [row for _, row in ordered if row[label_key] == label and row[id_key] in map2 and map2[row[id_key]][label_key] == label and not row.get('override_reason') and not map2[row[id_key]].get('override_reason')]
                assert len(eligible) >= 2, (task['id'], stage['id'], label)
                selected_representations = set()
                for row in eligible:
                    candidate = candidates[row[id_key]]
                    value = candidate['sequence'] if peptide else candidate['card']['identity']['isomeric_smiles']
                    if value in selected_representations:
                        continue
                    selected_representations.add(value)
                    if peptide:
                        observables = [{'label': 'Length', 'value': str(candidate['length']) + ' aa'}]
                        for k, v in candidate.get('developability_evidence', {}).items():
                            if k in {'non_hemolysis', 'solubility'}:
                                observables.append({'label': k.replace('_', '-').capitalize(), 'value': v.replace('_', ' ') + ' band'})
                    else:
                        desc = candidate['card']['descriptors']
                        observables = [{'label': label_, 'value': str(desc[key])} for key, label_ in [('molecular_weight_da', 'MW (Da)'), ('hydrogen_bond_donor_count', 'H-bond donors'), ('hydrogen_bond_acceptor_count', 'H-bond acceptors')]]
                    passes = []
                    for pass_index, (judgment, path) in enumerate([(row, first_path), (map2[row[id_key]], second_path)], 1):
                        passes.append({'pass': pass_index, 'label': judgment[label_key].upper(), 'rationale': judgment['rationale'], 'uncertainty': judgment['critical_unknowns'], 'source': receipt(path)})
                    picked.append({'status': 'recorded', 'label': label.upper(), 'sampleId': row[id_key], 'representation': {'kind': 'peptide' if peptide else 'smiles', 'value': value, 'source': receipt(pool_path)}, 'observables': observables, 'rationale': row['rationale'], 'uncertainty': row['critical_unknowns'], 'passes': passes, 'source': str(first_path.relative_to(archive)), 'sourceSha256': receipt(first_path)['sha256'], 'paraphrased': False, 'agreement': 'Same label in both recorded judge passes.'})
                    if len(selected_representations) == 2:
                        break
                assert len(selected_representations) == 2
            stage['traces'] = picked
            print(task['id'], stage['id'], '4 recorded candidates')
    data['schemaVersion'] = 2
    data['selectionNote'] = 'Two distinct stable-positive and two distinct stable-negative candidates per available stage. Previously illustrated candidates are retained when eligible, then archive order is used. Both explicit judge-output rationales and critical_unknowns fields are reproduced verbatim. D2 and constrained-design slots are placeholders and are not recorded judgments. Provider reasoning metadata is excluded.'
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'data/trace-sources.json').write_text(json.dumps({'selection': data['selectionNote'], 'sources': sorted(receipts.values(), key=lambda r: r['file'])}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()

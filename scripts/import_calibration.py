#!/usr/bin/env python3
"""Import Figure 3's frozen results and prompt components, without model calls."""
import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]


def extract(archive):
    receipts = {}

    def read(path):
        raw = (archive / path).read_bytes()
        receipts[path] = hashlib.sha256(raw).hexdigest()
        return raw.decode('utf-8')

    meta = json.loads(read('figures/all_models_boxed.json'))
    bars = list(csv.DictReader(read('figures/all_models_boxed.csv').splitlines()))
    models = []
    domains = []
    prompts = {'common': read('prompts/common.txt'), 'methods': {}}
    methods = [
        ('individual_score', 'Score', 'Score each candidate independently on a 1–100 scale; compare the scores.'),
        ('ranking', 'Ranking', 'Rank the candidates together from best to worst; compare their ranks.'),
        ('positive_negative', 'Pos × Neg', 'Label candidates positive, negative, or abstain; prefer every positive to every negative.'),
        ('duel', 'Duels', 'Ask which of two candidates better satisfies the task.')]
    for key, label, description in [('joint_score', 'Joint scoring', 'Score the candidates together on a 1–100 scale; compare differences between scores.')] + methods:
        paths = {'default': 'prompts/methods/{}.txt'.format(key)}
        if key == 'positive_negative':
            paths = {'default': 'prompts/variants/positive_negative_informative_v1.txt',
                     'opus': 'prompts/methods/positive_negative_opus_v3.txt'}
        prompts['methods'][key] = {'label': label, 'description': description,
                                  'variants': {name: read(path) for name, path in paths.items()}}
    all_points = {}
    for model in meta['models']:
        models.append({'id': model['key'], 'label': model['label'], 'color': model['color'],
                       'symbol': {'o': 'circle', 's': 'square', '^': 'triangle-up'}[model['marker']],
                       'logo': 'assets/model-logos/{}.svg'.format(model['logo'])})
        base = '{}/{}/analysis/'.format(model['key'], model['full'])
        all_points[model['key']] = list(csv.DictReader(read(base + 'cardinal_pairs.csv').splitlines()))
    descriptions = {
        'peptide': ('PepDFM', 'Helical hydrophobic moment', 'Greater whole-sequence α-helical hydrophobic moment.'),
        'mattergen': ('MatterGen', 'Thermodynamic stability', 'Lower energy above the convex hull after structural relaxation.'),
        'qm9': ('QM9', 'Molecular lipophilicity', 'Larger RDKit Wildman–Crippen MolLogP.')}
    for key, label in meta['domains'].items():
        generator, metric, task = descriptions[key]
        domain = {'id': key, 'label': label, 'generator': generator, 'metric': metric, 'task': task,
                  'prompt': read('prompts/domains/{}.txt'.format(key)), 'series': []}
        reference = None
        for model in meta['models']:
            points = [row for row in all_points[model['key']] if row['domain'] == key]
            truth = {(r['seed'], r['a'], r['b']): float(r['true_difference']) for r in points}
            assert len(points) == len(truth) == 288
            assert reference is None or reference == truth
            reference = truth
            mae = fmean(abs(float(r['true_difference']) - float(r['estimated_difference'])) for r in points)
            assert math.isclose(mae, meta['cardinal'][model['label']][key]['mae_points'], abs_tol=1e-9)
            values = []
            for method, _, _ in methods:
                method_label = meta['methods'][method]
                matches = [row for row in bars if row['domain'] == key and row['model'] == model['label'] and row['method'] == method_label]
                assert len(matches) == 1
                row = matches[0]
                original = json.loads(read(row['source']))['pairwise'][key][method]
                mean, sd = float(row['accuracy_percent']), float(row['sample_sd_percent'])
                assert math.isclose(mean, 100 * original['accuracy_mean'], abs_tol=1e-9)
                assert math.isclose(sd, 100 * original['accuracy_sample_sd'], abs_tol=1e-9)
                assert int(row['emitted_pairs']) == original['emitted_pairs_total']
                assert int(row['selected_pairs']) == original['selected_pairs_total'] == 288
                assert original['nonempty_seeds'] == 3
                values.append({'method': method, 'mean': mean, 'sd': sd,
                               'emitted': int(row['emitted_pairs']), 'selected': int(row['selected_pairs'])})
            domain['series'].append({'model': model['key'], 'mae': mae,
                'points': [[float(r['true_difference']), float(r['estimated_difference']), int(r['seed'])] for r in points], 'bars': values})
        domains.append(domain)
    return {'models': models, 'methods': [m[0] for m in methods], 'domains': domains, 'prompts': prompts,
            'provenance': {'archive': archive.name, 'figure': 3, 'layout': 'all_models_boxed',
                'scatter': 'Original joint-score differences; no fitted calibration applied.',
                'uncertainty': 'Sample standard deviation across three seeds, not a confidence interval.',
                'coverage': 'Accuracy is conditional on emitted preferences; coverage totals span all three seeds.',
                'promptVariants': {'terra': 'revised_pn', 'gemini37': 'revised_pn', 'opus': 'pn_v3'},
                'selection': 'Revised positive/negative prompts are exploratory on previously inspected seeds.',
                'sources': [{'file': path, 'sha256': digest} for path, digest in sorted(receipts.items())]}}


def validate(data):
    assert [d['id'] for d in data['domains']] == ['peptide', 'mattergen', 'qm9']
    assert [m['id'] for m in data['models']] == ['terra', 'opus', 'gemini37']
    for domain in data['domains']:
        assert domain['prompt'] and len(domain['series']) == 3
        for series in domain['series']:
            assert len(series['points']) == 288
            assert set(p[2] for p in series['points']) == {10101, 10102, 10103}
            assert all(math.isfinite(n) for p in series['points'] for n in p)
            assert math.isclose(fmean(abs(p[0] - p[1]) for p in series['points']), series['mae'], abs_tol=1e-9)
            assert [b['method'] for b in series['bars']] == data['methods']
            for bar in series['bars']:
                assert 0 <= bar['mean'] <= 100 and math.isfinite(bar['sd']) and bar['sd'] >= 0
                assert 0 < bar['emitted'] <= bar['selected'] == 288
    assert data['provenance']['layout'] == 'all_models_boxed'
    assert data['prompts']['methods']['positive_negative']['variants'].keys() == {'default', 'opus'}
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = validate(extract(args.archive))
    target = ROOT / 'data/calibration.json'
    if args.check:
        assert json.loads(target.read_text()) == data
    else:
        target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
        logos = ROOT / 'assets/model-logos'
        logos.mkdir(exist_ok=True)
        for name in ['openai.svg', 'claude.svg', 'gemini.svg', 'README.md', 'LICENSE']:
            shutil.copy2(args.archive / 'code/assets/logos' / name, logos / name)
    print('Verified 2,592 score-difference points, 9 MAEs, 36 means/SDs/coverage counts and exact prompt components.')

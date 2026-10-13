#!/usr/bin/env python3
"""Validate evidence and assemble a dependency-free GitHub Pages artifact."""
import argparse
import hashlib
import json
import math
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from import_calibration import validate as validate_calibration

ROOT = Path(__file__).resolve().parents[1]


def validate():
    task_data = json.loads((ROOT / 'data/tasks.json').read_text())
    tasks = task_data['tasks']
    results = json.loads((ROOT / 'data/results.json').read_text())
    assert {t['id'] for t in tasks} == {'anticancer', 'cpp', 'd2', 'gsk3b', 'ood'}
    assert len(tasks) == 5
    expected_rounds = {'anticancer': 13, 'cpp': 7, 'd2': 9, 'gsk3b': 10, 'ood': 6}
    expected_stages = {'anticancer': 8, 'cpp': 3, 'd2': 3, 'gsk3b': 5, 'ood': 4}
    expected_lineage = {
        ('d2', 'g0'): ('drugs-ltfd-c3h3g2-08', 2, 5, 'G02-child-development'),
        ('d2', 'g1'): ('drugs-ltfd-c3h3g2s-07', 1, 6, 'G01-child-development'),
        ('d2', 'g'): ('drugs-ltfd-c3h3g2s-07g-03', 3, 9, 'G03-child-development'),
        ('ood', 'g0'): ('kinase-ltfd-linkrelaxed-p020-x20-05', 1, 1, 'G01-child-development'),
        ('ood', 'g1'): ('kinase-ltfd-linkrelaxed-p020-x20-05', 2, 2, 'G02-child-development'),
        ('ood', 'g2'): ('kinase-ltfd-linkrelaxed-p020-x20-05', 6, 6, 'G06-child-development'),
        ('ood', 'g'): ('kinase-ltfd-linkrelaxed-p020-x20-05', 6, 6, 'F06-child-development'),
    }
    receipts = json.loads((ROOT / 'data/trace-sources.json').read_text())['sources']
    receipt_hashes = {item['file']: item['sha256'] for item in receipts}
    assert len(receipt_hashes) == len(receipts)

    def validate_receipt(receipt):
        assert receipt['file'] and not Path(receipt['file']).is_absolute()
        assert '..' not in Path(receipt['file']).parts
        assert re.fullmatch(r'[a-f0-9]{64}', receipt['sha256'])
        assert receipt_hashes.get(receipt['file']) == receipt['sha256'], receipt['file']

    curation = json.loads((ROOT / 'data/trace-pairs.json').read_text())['tasks']
    trace_count = 0
    pass_count = 0
    selection_counts = {'recorded': 0, 'original-goal': 0}
    for task in tasks:
        assert sum(s['rounds'] for s in task['stages']) == expected_rounds[task['id']]
        assert len({s['id'] for s in task['stages']}) == len(task['stages']) == expected_stages[task['id']]
        if task['id'] in {'d2', 'ood'}:
            assert [s['id'] for s in task['stages']] == (['g0', 'g1', 'g'] if task['id'] == 'd2' else ['g0', 'g1', 'g2', 'g'])
            assert [s['rounds'] for s in task['stages']] == ([5, 1, 3] if task['id'] == 'd2' else [1, 1, 4, 0])
            assert sum(len(s['traces']) for s in task['stages']) == (12 if task['id'] == 'd2' else 14)
        for stage in task['stages']:
            assert stage['summary'] and stage['title'] and stage['paperPages']
            assert stage['exactGoal'] and stage['goalTextSource']['verbatim'] is True
            assert stage['goalTextSource']['file'] == 'assets/paper.pdf'
            assert stage['goalTextSource']['page'] in stage['paperPages']
            assert stage['goalTextSource']['kind'] == ('original-goal' if stage['id'] == 'g' else 'llm-subgoal')
            assert all(1 <= page <= 43 for page in stage['paperPages'])
            selection = stage['selection']
            assert selection['status'] == ('original-goal' if stage['id'] == 'g' else 'recorded')
            selection_counts[selection['status']] += 1
            validate_receipt(selection['source'])
            if selection['status'] == 'recorded':
                assert selection['rationale'] and selection['source']
            assessment = task['id'] == 'ood' and stage['id'] == 'g'
            pair_count = 1 if assessment else 2
            candidate_count = 2 * pair_count
            assert len(stage['traces']) == candidate_count
            assert len(stage['tracePairs']) == pair_count
            assert stage['tracePairs'] == curation[task['id']][stage['id']]
            if task['id'] in {'d2', 'ood'}:
                lineage = stage['traceProvenance']
                assert tuple(lineage[key] for key in ['run', 'round', 'cumulativeUpdates', 'judgment']) == expected_lineage[(task['id'], stage['id'])]
                validate_receipt(lineage['stableSummary'])
                judgment_dir = f"{lineage['run']}/campaign/judgments/{lineage['judgment']}"
                assert lineage['stableSummary']['file'] == f'{judgment_dir}/stable_summary.json'
            if assessment:
                assert stage['assessment'] == {
                    'generationAttempts': 512, 'judgeableCandidates': 506,
                    'stablePositive': 1, 'stableNegative': 505,
                    'unjudgeableAttempts': 6, 'unstableJudgments': 0,
                    'positiveItemId': 'item-151', 'positiveGenerationSampleIndex': 154,
                }
                assert 'The saturated amine-containing ring need not be carbon-linked to the aza-aromatic ring.' in stage['exactGoal']
            by_id = {trace['sampleId']: trace for trace in stage['traces']}
            paired_ids = []
            for pair in stage['tracePairs']:
                positive, negative = by_id[pair['positiveId']], by_id[pair['negativeId']]
                assert positive['label'] == 'POSITIVE' and negative['label'] == 'NEGATIVE'
                assert positive['pairId'] == negative['pairId'] == pair['id']
                paired_ids.extend([pair['positiveId'], pair['negativeId']])
                assert pair['selectionReason'] and len(pair['sizes']) == 2
                if pair['sizeUnit'] == 'aa':
                    assert pair['sizes'][0] == pair['sizes'][1]
                    assert pair['sizes'] == [len(positive['representation']['value']), len(negative['representation']['value'])]
                else:
                    assert pair['sizeUnit'] == 'Da' and abs(pair['sizes'][0] - pair['sizes'][1]) < 20
                    assert pair['sizes'] == [float(next(o['value'] for o in trace['observables'] if o['label'] == 'MW (Da)')) for trace in [positive, negative]]
            assert len(set(paired_ids)) == candidate_count
            if pair_count == 2:
                assert max(stage['tracePairs'][0]['sizes']) < min(stage['tracePairs'][1]['sizes'])
            assert [t['label'] for t in stage['traces']].count('POSITIVE') == pair_count
            assert [t['label'] for t in stage['traces']].count('NEGATIVE') == pair_count
            if task['id'] == 'd2' and stage['id'] == 'g':
                assert by_id['item-004']['label'] == 'POSITIVE' and by_id['item-005']['label'] == 'NEGATIVE'
            if assessment:
                assert by_id['item-151']['label'] == 'POSITIVE'
                assert by_id['item-151']['generationId'] == 'development-attempt-0154'
            for trace in stage['traces']:
                assert trace['label'] in {'POSITIVE', 'NEGATIVE'}
                assert trace['status'] == 'recorded'
                assert trace['source'] and trace['rationale'] and trace['uncertainty']
                assert trace['paraphrased'] is False
                assert re.fullmatch(r'[a-f0-9]{64}', trace['sourceSha256'])
                assert trace['representation']['kind'] in {'peptide', 'smiles'}
                assert trace['representation']['value']
                validate_receipt(trace['representation']['source'])
                assert [p['pass'] for p in trace['passes']] == [1, 2]
                assert all(p['label'] == trace['label'] for p in trace['passes'])
                assert all(p['rationale'] and p['uncertainty'] and re.fullmatch(r'[a-f0-9]{64}', p['source']['sha256']) for p in trace['passes'])
                assert trace['rationale'] == trace['passes'][0]['rationale']
                assert trace['uncertainty'] == trace['passes'][0]['uncertainty']
                assert trace['source'] == trace['passes'][0]['source']['file']
                assert trace['sourceSha256'] == trace['passes'][0]['source']['sha256']
                for output in trace['passes']:
                    validate_receipt(output['source'])
                if task['id'] in {'d2', 'ood'}:
                    assert trace['representation']['kind'] == 'smiles'
                    assert re.fullmatch(r'development-attempt-\d{4}', trace['generationId'])
                    assert [o['label'] for o in trace['observables']] == ['MW (Da)', 'H-bond donors', 'H-bond acceptors']
                    assert all(isinstance(o['value'], str) and o['value'] for o in trace['observables'])
                    assert trace['representation']['source']['file'] == f"{lineage['run']}/campaign/rounds/round-{lineage['round']:02d}/development/child/pool/candidate_pool.jsonl"
                    assert [p['source']['file'] for p in trace['passes']] == [f'{judgment_dir}/repeat-{i}.json' for i in [1, 2]]
                pass_count += len(trace['passes'])
                trace_count += 1
            assert len({t['sampleId'] for t in stage['traces']}) == candidate_count
            assert len({t['representation']['value'] for t in stage['traces']}) == candidate_count
    assert trace_count == 90 and pass_count == 180
    assert selection_counts == {'recorded': 18, 'original-goal': 5}
    assert not any(key in json.dumps(task_data) for key in ['thought_summary', 'thought_summaries', 'request_hash', 'model_versions'])
    provenance = json.loads((ROOT / 'data/provenance.json').read_text())
    assert hashlib.sha256((ROOT / provenance['paper']['file']).read_bytes()).hexdigest() == provenance['paper']['sha256']
    assert len(results) == 4
    for result in results:
        assert len(result['metrics']) == 3
        assert sum(row['method'] == 'LFD' for row in result['rows']) == 1
        assert all(len(row['values']) == 3 for row in result['rows'])
    serialized = json.dumps(task_data)
    assert 'sourceFiles' not in serialized
    assert not re.search(r'/iopsstor/|/capstor/|/users/|(?:github_pat_|ghp_)[A-Za-z0-9_]{10,}', serialized)
    for file in (ROOT / 'data').glob('*.json'):
        assert not re.search(r'/iopsstor/|/capstor/|/users/|/cluster/', file.read_text()), file
    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name in {'src', 'href'} and value:
                    url = urlparse(value)
                    if not url.scheme and not url.netloc and url.path:
                        if url.path != 'data/site-data.js':
                            assert (ROOT / unquote(url.path)).is_file(), value
    # site-data.js is generated next; validate the other static assets now.
    Links().feed((ROOT / 'index.html').read_text())
    return task_data, results, trace_count


def validate_charts():
    data = json.loads((ROOT / 'data/charts.json').read_text())
    assert data['target'] == 'GSK3β' and data['paperFigure'] == 7
    assert [r['round'] for r in data['trajectory']] == list(range(8))
    for index, row in enumerate(data['trajectory']):
        assert row['bestRound'] <= row['round']
        assert row['bestMean'] == max(r['checkpointMean'] for r in data['trajectory'][:index+1])
        assert row['ciLow'] <= row['bestMean'] <= row['ciHigh']
        assert all(math.isfinite(row[k]) for k in ['checkpointMean', 'bestMean', 'ciLow', 'ciHigh'])
    assert len(data['novelty']) == 6
    for row in data['novelty']:
        assert row['samplingSeeds'] == 5 and row['proposalsPerSeed'] == 256
        assert row['noveltyCI95'] >= 0 and row['negativeRDockCI95'] >= 0
    for receipt in data['sources']:
        assert re.fullmatch(r'[a-f0-9]{64}', receipt['sha256'])
        assert receipt['retrieved'] == '2026-10-01'
    d2 = data['d2']
    assert d2['target'] == 'D2' and d2['paperFigure'] == 7 and d2['paperPanel'] == 'b'
    assert d2['samplingSeedIds'] == [34601, 35601, 36601, 37601, 38601]
    assert d2['samplingSeeds'] == 5 and d2['proposalsPerSeed'] == 256
    assert d2['referencePolicy'] == 'geom_training_smiles'
    assert d2['referenceEntries'] == 243480 and d2['referenceDistinctScaffolds'] == 79679
    expected_d2 = {
        'Pre-trained': (39.0, 2.483327996407533, 14.221039999999999, 0.1703927109006674),
        'LFD': (63.4, 4.856795354126119, 16.1832, 0.5776547233218813),
        'DPO': (28.2, 6.108179231435157, 13.98672, 0.38373378099425304),
        'Flow-GRPO': (40.8, 4.919873261135413, 14.345098461538461, 0.7583819051203323),
        'DiffusionNFT': (48.6, 6.605372389920251, 15.13471846153846, 0.8112282016587546),
        'Guidance': (43.0, 6.3312689561666415, 13.995944615384616, 0.3301832199537165),
    }
    assert len(d2['novelty']) == 6 and {row['method'] for row in d2['novelty']} == set(expected_d2)
    for row in d2['novelty']:
        coordinates = tuple(row[key] for key in ['noveltyMean', 'noveltyCI95', 'negativeRDockMean', 'negativeRDockCI95'])
        assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in coordinates)
        assert coordinates == expected_d2[row['method']]
        assert row['samplingSeeds'] == 5 and row['proposalsPerSeed'] == 256
        assert row['referencePolicy'] == 'geom_training_smiles' and row['referenceEntries'] == 243480
    assert len(d2['sources']) == 5
    for receipt in d2['sources']:
        assert re.fullmatch(r'[a-f0-9]{64}', receipt['sha256'])
        assert not Path(receipt['file']).is_absolute()
    return data


def version_static_assets():
    """Change local CSS/JS URLs whenever their contents change."""
    index = ROOT / 'index.html'
    html = index.read_text()
    def version(match):
        url = urlparse(match.group('url'))
        if url.scheme or url.netloc:
            return match.group(0)
        digest = hashlib.sha256((ROOT / unquote(url.path)).read_bytes()).hexdigest()[:12]
        return '{}="{}?v={}"'.format(match.group('attribute'), url.path, digest)
    pattern = r'\b(?P<attribute>src|href)="(?P<url>[^"\n]+\.(?:css|js)(?:\?[^"\n]*)?)"'
    updated = re.sub(pattern, version, html)
    if updated != html:
        index.write_text(updated)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    task_data, results, count = validate()
    charts = validate_charts()
    panels = json.loads((ROOT / 'data/result-panels.json').read_text())
    assert [t['id'] for t in panels['tasks']] == [t['id'] for t in task_data['tasks']]
    assert [t['number'] for t in panels['tasks']] == list(range(1, 6))
    assert all(t['goal'] and 1 <= t['paperPage'] <= 43 for t in panels['tasks'])
    for panel, task in zip(panels['tasks'], task_data['tasks']):
        assert panel['generator'] == task['generator']
        assert panel['description'] and panel['proxy'] and panel['observableSummary']
        assert panel['observables'] and len(panel['observables']) == len(set(panel['observables']))
        assert all(1 <= page <= 43 for page in panel['appendixPages'])
    docking = panels['dockingDisplay']
    assert docking['metrics'] == ['GNINA', 'Vina', 'rDock']
    assert docking['source'] == 'assets/paper.pdf' and docking['sourcePage'] == 8
    assert docking['caption'] and docking['label']
    assert docking['confidenceLevel'] in (None, 95)
    assert docking['baseline'] == 'Pre-trained' and docking['baselineReference'] == 'fixed_mean'
    assert all(sum(row['method'] == docking['baseline'] for row in result['rows']) == 1 for result in results if result['table'] == 2)
    assert all(row['values'][index][0] < 0 for result in results if result['table'] == 2 for row in result['rows'] for index in (1, 2))
    hit_figure = panels['oodEvidence']['figure']
    assert hashlib.sha256((ROOT / hit_figure['file']).read_bytes()).hexdigest() == hit_figure['sha256']
    assert panels['oodEvidence']['pretrained'] == {'attempts': 38500, 'fullGoalHits': 0}
    assert panels['oodEvidence']['lfd']['batchSize'] == 512 and panels['oodEvidence']['lfd']['round'] == 6
    metric_help = json.loads((ROOT / 'data/metric-definitions.json').read_text())
    for metric in metric_help['metrics'].values():
        assert metric['title'] and metric['text'] and metric['references']
        assert all(key in metric_help['references'] for key in metric['references'])
    for reference in metric_help['references'].values():
        assert reference['label'] and reference['title'] and reference['url'].startswith('https://doi.org/')
    calibration = validate_calibration(json.loads((ROOT / 'data/calibration.json').read_text()))
    payload = {'tasks': task_data['tasks'], 'results': results, 'charts': charts, 'resultPanels': panels, 'metricHelp': metric_help, 'calibration': calibration}
    script = '// Generated by scripts/build.py from the public JSON sources.\nwindow.LFD_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';\n'
    (ROOT / 'data/site-data.js').write_text(script)
    version_static_assets()
    dist = args.output_dir.resolve()
    dist.mkdir(exist_ok=True)
    for name in ['index.html', 'site.css', 'site.js', 'results.js', 'calibration.js', '.nojekyll']:
        shutil.copy2(ROOT / name, dist / name)
    for name in ['assets', 'data']:
        shutil.copytree(ROOT / name, dist / name, dirs_exist_ok=True)
    print(f'Validated 5 tasks, 23 stages, {count} recorded candidates, 180 judge passes, no placeholder slots, 4 result tables and the paper hash.')
    print(f'Site artifact: {dist}')


if __name__ == '__main__':
    main()

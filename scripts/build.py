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

ROOT = Path(__file__).resolve().parents[1]


def validate():
    task_data = json.loads((ROOT / 'data/tasks.json').read_text())
    tasks = task_data['tasks']
    results = json.loads((ROOT / 'data/results.json').read_text())
    assert {t['id'] for t in tasks} == {'anticancer', 'cpp', 'd2', 'gsk3b', 'ood'}
    assert len(tasks) == 5
    expected_rounds = {'anticancer': 13, 'cpp': 7, 'd2': 9, 'gsk3b': 10, 'ood': 6}
    trace_count = 0
    for task in tasks:
        assert sum(s['rounds'] for s in task['stages']) == expected_rounds[task['id']]
        assert len({s['id'] for s in task['stages']}) == len(task['stages'])
        for stage in task['stages']:
            assert stage['summary'] and stage['title'] and stage['paperPages']
            assert stage['exactGoal'] and stage['goalTextSource']['verbatim'] is True
            assert stage['goalTextSource']['file'] == 'assets/paper.pdf'
            assert stage['goalTextSource']['page'] in stage['paperPages']
            assert stage['goalTextSource']['kind'] == ('original-goal' if stage['id'] == 'g' else 'llm-subgoal')
            assert all(1 <= page <= 43 for page in stage['paperPages'])
            selection = stage['selection']
            assert selection['status'] in {'recorded', 'original-goal', 'placeholder'}
            if selection['status'] == 'recorded':
                assert selection['rationale'] and selection['source']
            assert len(stage['traces']) == 4
            assert len(stage['tracePairs']) == 2
            by_id = {trace['sampleId']: trace for trace in stage['traces']}
            paired_ids = []
            for pair in stage['tracePairs']:
                positive, negative = by_id[pair['positiveId']], by_id[pair['negativeId']]
                assert positive['label'] == 'POSITIVE' and negative['label'] == 'NEGATIVE'
                assert positive['pairId'] == negative['pairId'] == pair['id']
                paired_ids.extend([pair['positiveId'], pair['negativeId']])
                if selection['status'] != 'placeholder':
                    assert pair['selectionReason'] and len(pair['sizes']) == 2
                    if pair['sizeUnit'] == 'aa':
                        assert pair['sizes'][0] == pair['sizes'][1]
                        assert pair['sizes'] == [len(positive['representation']['value']), len(negative['representation']['value'])]
                    else:
                        assert pair['sizeUnit'] == 'Da' and abs(pair['sizes'][0] - pair['sizes'][1]) < 20
            assert len(set(paired_ids)) == 4
            if selection['status'] != 'placeholder':
                assert max(stage['tracePairs'][0]['sizes']) < min(stage['tracePairs'][1]['sizes'])
            assert [t['label'] for t in stage['traces']].count('POSITIVE') == 2
            assert [t['label'] for t in stage['traces']].count('NEGATIVE') == 2
            for trace in stage['traces']:
                assert trace['label'] in {'POSITIVE', 'NEGATIVE'}
                if trace['status'] == 'placeholder':
                    assert task['id'] in {'d2', 'ood'}
                    assert all(trace[key] is None for key in ['representation', 'rationale', 'uncertainty'])
                    assert 'source' not in trace and 'passes' not in trace
                    continue
                assert trace['status'] == 'recorded' and task['id'] not in {'d2', 'ood'}
                assert trace['source'] and trace['rationale'] and trace['uncertainty']
                assert trace['paraphrased'] is False
                assert re.fullmatch(r'[a-f0-9]{64}', trace['sourceSha256'])
                assert trace['representation']['kind'] in {'peptide', 'smiles'}
                assert trace['representation']['value']
                assert [p['pass'] for p in trace['passes']] == [1, 2]
                assert all(p['label'] == trace['label'] for p in trace['passes'])
                assert all(p['rationale'] and p['uncertainty'] and re.fullmatch(r'[a-f0-9]{64}', p['source']['sha256']) for p in trace['passes'])
                assert trace['rationale'] == trace['passes'][0]['rationale']
                assert trace['uncertainty'] == trace['passes'][0]['uncertainty']
                trace_count += 1
            if selection['status'] != 'placeholder':
                assert len({t['sampleId'] for t in stage['traces']}) == 4
                assert len({t['representation']['value'] for t in stage['traces']}) == 4
    assert trace_count == 64
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
        assert not re.search(r'/iopsstor/|/capstor/|/users/', file.read_text()), file
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
    payload = {'tasks': task_data['tasks'], 'results': results, 'charts': charts, 'resultPanels': panels, 'metricHelp': metric_help}
    script = '// Generated by scripts/build.py from the public JSON sources.\nwindow.LFD_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';\n'
    (ROOT / 'data/site-data.js').write_text(script)
    version_static_assets()
    dist = args.output_dir.resolve()
    dist.mkdir(exist_ok=True)
    for name in ['index.html', 'site.css', 'site.js', 'results.js', '.nojekyll']:
        shutil.copy2(ROOT / name, dist / name)
    for name in ['assets', 'data']:
        shutil.copytree(ROOT / name, dist / name, dirs_exist_ok=True)
    print(f'Validated 5 tasks, 23 stages, {count} recorded candidates + 28 placeholder slots, 4 result tables and the paper hash.')
    print(f'Site artifact: {dist}')


if __name__ == '__main__':
    main()

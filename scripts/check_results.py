#!/usr/bin/env python3
"""Verify five task panels, paired metrics, exact source values, and interaction."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', default='test-results/charts')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = json.loads((root / 'data/results.json').read_text())
    charts = json.loads((root / 'data/charts.json').read_text())
    panel_data = json.loads((root / 'data/result-panels.json').read_text())
    goals = panel_data['tasks']
    tasks = json.loads((root / 'data/tasks.json').read_text())['tasks']
    widths = [360, 390, 768, 901, 1024, 1280, 1440, 1920, 2227, 2560]
    errors, failures = [], []
    expected_symbols={'LFD':'square','Pre-trained':'x','DPO':'circle','DiffusionNFT':'diamond','Flow-GRPO':'triangle-up','Guidance':'triangle-down'}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':2227,'height':1165}, reduced_motion='reduce')
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        page.goto(args.url + '/#results', wait_until='networkidle')
        expect(page.locator('#result-cards [role="tab"]')).to_have_count(5)
        assert 'Compare methods' not in page.locator('body').inner_text()
        for task in goals:
            assert page.locator(f'#result-goal-{task["id"]}').inner_text() == task['goal']
        def select(task):
            page.locator(f'[data-result-task="{task}"]').click()
            page.wait_for_function('(id)=>document.querySelector("#task-results-panel").dataset.plotReadyTask===id',arg=task)
            expect(page.locator('#result-cards [aria-selected="true"]')).to_have_count(1)
            expect(page.locator(f'[data-result-task="{task}"]')).to_have_attribute('aria-selected','true')
            expect(page.locator('#task-results-panel')).to_have_attribute('aria-labelledby','result-card-'+task)
        # Each colored goal owns its appendix context and all recorded curriculum stages.
        inspected_stages = 0
        for goal in goals:
            task = next(t for t in tasks if t['id'] == goal['id'])
            select(goal['id'])
            card = page.locator(f'[data-result-task="{goal["id"]}"]')
            expect(card).to_have_attribute('data-generator', task['generator'])
            assert card.locator('.goal-number').evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)') >= 22
            expect(page.locator('#result-generator')).to_contain_text(task['generator'])
            expect(page.locator('#task-results-panel')).to_have_attribute('data-generator', task['generator'])
            assert page.locator('.proxy-context p').inner_text() == goal['proxy']
            page.locator('.observable-details summary').click()
            assert page.locator('.observable-details li').all_text_contents() == goal['observables']
            page.locator('.observable-details summary').click()
            assert page.locator('[data-curriculum-stage]').count() == len(task['stages'])
            for stage in task['stages']:
                page.locator(f'[data-curriculum-stage="{stage["id"]}"]').click()
                expect(page.locator('#task-result-curriculum')).to_have_attribute('data-selected-stage', stage['id'])
                assert page.locator('#result-curriculum-preview p').inner_text() == stage.get('exactGoal', stage['summary'])
                link = page.locator('.curriculum-preview-links a')
                assert link.get_attribute('href') == f'#explorer?task={task["id"]}&stage={stage["id"]}&tab=traces'
                inspected_stages += 1
            # The final-stage link opens the matching trace view, not merely an anchor.
            page.locator('.curriculum-preview-links a').click()
            expect(page.locator(f'[data-task="{task["id"]}"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('[data-stage="g"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('#tab-traces')).to_have_attribute('aria-selected','true')
            assert page.locator('.trace-card').count() == len(task['stages'][-1]['traces'])
        assert inspected_stages == 23
        select('anticancer')
        page.locator('[data-curriculum-stage="g0"]').focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('[data-curriculum-stage="g1"]')).to_be_focused()
        expect(page.locator('[data-curriculum-stage="g1"]')).to_have_attribute('aria-selected','true')
        page.keyboard.press('End')
        expect(page.locator('[data-curriculum-stage="g"]')).to_be_focused()
        page.keyboard.press('Home')
        expect(page.locator('[data-curriculum-stage="g0"]')).to_be_focused()
        for result in results:
            select(result['id'])
            expected_values=[f'{mean:.2f}' for mean,error in next(row for row in result['rows'] if row['method']=='LFD')['values']]
            assert page.locator('.metric-value strong').all_text_contents() == expected_values
            for index,row in enumerate(result['rows']):
                values=page.locator('#results-table tbody tr').nth(index).locator('td').all_text_contents()
                assert values == [f'{mean:.2f} ± {error:.2f}' for mean,error in row['values']], (result['id'],index,values)
            if result['id']=='gsk3b':
                assert page.locator('#task-results-plots .js-plotly-plot').count()==2
                expect(page.locator('#trajectory-chart')).to_be_visible()
                expect(page.locator('#novelty-chart')).to_be_visible()
                assert page.locator('#comparison-chart').count()==0
                continue
            assert page.locator('#task-results-plots .js-plotly-plot').count()==1
            assert page.locator('#trajectory-chart,#novelty-chart,#curriculum-chart').count()==0
            yindex=1 if result['table']==1 else 2
            points=page.locator('#comparison-chart').evaluate('(plot)=>plot.data.map(trace=>({method:trace.name,x:trace.x[0],y:trace.y[0],dx:trace.error_x.array[0],dy:trace.error_y.array[0],symbol:trace.marker.symbol}))')
            assert points == [{'method':r['method'],'x':r['values'][0][0],'y':r['values'][yindex][0],'dx':r['values'][0][1],'dy':r['values'][yindex][1],'symbol':expected_symbols[r['method']]} for r in result['rows']]
            legend=page.locator('#task-results-plots [data-legend-method]').evaluate_all('(els)=>els.map(el=>({method:el.dataset.legendMethod,symbol:el.querySelector("svg").dataset.markerSymbol}))')
            assert {r['method']:r['symbol'] for r in legend} == {r['method']:expected_symbols[r['method']] for r in result['rows']}
            page.mouse.move(5,5)
            page.locator('#comparison-chart .scatterlayer .trace').last.locator('.point').hover(force=True)
            expect(page.locator('#comparison-readout')).to_contain_text('LFD')
            for metric_index,metric in enumerate(result['metrics']):
                expect(page.locator('#comparison-chart .hoverlayer')).to_contain_text(f'{result["rows"][-1]["values"][metric_index][0]:.2f}')
        select('gsk3b')
        trajectory=page.locator('#trajectory-chart').evaluate('(plot)=>plot.data.find(trace=>trace.name==="LFD best so far").y')
        assert trajectory == [r['bestMean'] for r in charts['trajectory']]
        page.locator('#trajectory-chart .scatterlayer .trace').last.locator('.point').nth(6).hover(force=True)
        expect(page.locator('#trajectory-chart .hoverlayer')).to_contain_text('6.726')
        expect(page.locator('#trajectory-chart .hoverlayer')).to_contain_text('6.839')
        novelty=page.locator('#novelty-chart').evaluate('(plot)=>plot.data.map(trace=>({method:trace.name,x:trace.x[0],y:trace.y[0],dx:trace.error_x.array[0],dy:trace.error_y.array[0]}))')
        assert novelty == [{'method':r['method'],'x':r['noveltyMean'],'y':r['negativeRDockMean'],'dx':r['noveltyCI95'],'dy':r['negativeRDockCI95']} for r in charts['novelty']]
        page.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').hover(force=True)
        expect(page.locator('#novelty-readout')).to_contain_text('89.00')
        select('ood')
        assert page.locator('#task-results-plots .js-plotly-plot').count()==1
        assert page.locator('#comparison-chart,#trajectory-chart,#novelty-chart').count()==0
        expect(page.locator('.discovery-zero')).to_have_text('0 / 38,500')
        expect(page.locator('.discovery-hit')).to_contain_text('Round 6')
        expect(page.locator('.discovery-hit')).to_contain_text('512-sample batch')
        hit=page.locator('.goal5-hit img')
        expect(hit).to_have_attribute('src','assets/hitGoal5.png')
        hit.scroll_into_view_if_needed()
        page.wait_for_function('document.querySelector(".goal5-hit img").naturalWidth===7212')
        assert '38,500' in page.locator('#results-table').inner_text()
        assert '512-sample batch' in page.locator('#results-table').inner_text()
        assert 'Reported full-goal hit' in page.locator('#results-table').inner_text()
        curriculum=page.locator('#curriculum-chart').evaluate('(plot)=>plot.data.map(trace=>({x:trace.x,y:trace.y}))')
        assert curriculum == [{'x':[1,2,3,4,5,6],'y':[0,1,2,2,2,2]},{'x':[6],'y':[3]}]
        page.locator('#curriculum-chart .scatterlayer .trace').last.locator('.point').hover(force=True)
        expect(page.locator('#curriculum-readout')).to_contain_text('no additional training update')
        # Tab semantics and standard arrow/Home/End navigation retain focus on the card.
        select('anticancer')
        page.locator('[data-result-task="anticancer"]').focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('[data-result-task="cpp"]')).to_be_focused()
        expect(page.locator('[data-result-task="cpp"]')).to_have_attribute('aria-selected','true')
        page.keyboard.press('End')
        expect(page.locator('[data-result-task="ood"]')).to_be_focused()
        page.keyboard.press('Home')
        expect(page.locator('[data-result-task="anticancer"]')).to_be_focused()
        # Rapid selections must not leave plots from a previous task in the panel.
        page.evaluate('''()=>['gsk3b','ood','cpp','gsk3b','anticancer'].forEach(id=>document.querySelector('[data-result-task="'+id+'"]').click())''')
        page.wait_for_function('document.querySelector("#task-results-panel").dataset.plotReadyTask === "anticancer"')
        assert page.locator('.js-plotly-plot').count()==1
        assert page.locator('#trajectory-chart,#novelty-chart,#curriculum-chart').count()==0
        for width in widths:
            page.set_viewport_size({'width':width,'height':1165})
            for task in ['anticancer','gsk3b','ood']:
                select(task)
                page.wait_for_timeout(250)
                assert page.evaluate('document.documentElement.scrollWidth')<=width,(width,task)
                assert page.locator('.js-plotly-plot').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'),(width,task)
                if width in [390,2227]:
                    page.locator('#task-results-panel').screenshot(path=str(out/f'{task}-{width}.png'))
            if width>=1280:
                page.locator('#method').evaluate('(el)=>el.scrollIntoView({behavior:"instant"})')
                boxes=page.locator('#contents,#method').evaluate_all('(els)=>els.map(el=>el.getBoundingClientRect().toJSON())')
                assert boxes[0]['right']<=boxes[1]['left']-10
        mobile=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
        touch=mobile.new_page()
        touch.on('pageerror',lambda error:errors.append(str(error)))
        touch.goto(args.url+'/#results',wait_until='networkidle')
        for task in ['cpp','gsk3b','ood']:
            touch.locator(f'[data-result-task="{task}"]').tap()
            touch.wait_for_function('(id)=>document.querySelector("#task-results-panel").dataset.plotReadyTask===id',arg=task)
            touch.locator('[data-curriculum-stage="g1"]').tap()
            expect(touch.locator('[data-curriculum-stage="g1"]')).to_have_attribute('aria-selected','true')
            if task=='cpp':
                touch.locator('#comparison-chart .scatterlayer .trace').last.locator('.point').tap(force=True)
                expect(touch.locator('#comparison-readout')).to_contain_text('69.06')
                expect(touch.locator('#comparison-readout')).to_contain_text('37.02')
            elif task=='gsk3b':
                touch.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').tap(force=True)
                expect(touch.locator('#novelty-readout')).to_contain_text('89.00')
            else:
                touch.locator('#curriculum-chart .scatterlayer .trace').last.locator('.point').tap(force=True)
                expect(touch.locator('#curriculum-readout')).to_contain_text('512')
        page.goto((root/'index.html').as_uri(),wait_until='load')
        page.wait_for_function('document.querySelector("#task-results-panel").dataset.plotReadyTask === "anticancer"')
        expect(page.locator('#result-cards [role="tab"]')).to_have_count(5)
        assert not errors,errors
        assert not failures,failures
        browser.close()
    report={'status':'passed','viewports':widths,'goals':5,'table_metric_pairs':66,'paired_activity_toxicity':'passed','task_plot_isolation':'passed','marker_legends':'passed','paper_goals':'passed','fifth_task_evidence':'passed','goal5_figure':'passed','generator_colors':'passed','observable_lists':'passed','curriculum_stages':23,'curriculum_keyboard_touch':'passed','curriculum_trace_links':'passed','numerical_summaries':'passed','rapid_switching':'passed','keyboard':'passed','hover_touch':'passed','local_file':'passed','browser_errors':errors,'failed_requests':failures}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

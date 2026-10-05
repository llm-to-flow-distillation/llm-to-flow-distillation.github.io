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
    expected_colors={'LFD':'#8732ad','Pre-trained':'#33373f','DPO':'#d77b00','DiffusionNFT':'#286565','Flow-GRPO':'#719adc','Guidance':'#c54b59'}
    def rgb(hex_color):
        return 'rgb('+', '.join(str(int(hex_color[i:i+2],16)) for i in (1,3,5))+')'
    expected_symbols={'LFD':'square','Pre-trained':'x','DPO':'circle','DiffusionNFT':'diamond','Flow-GRPO':'triangle-up','Guidance':'triangle-down'}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':2227,'height':1165}, reduced_motion='reduce')
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        page.goto(args.url + '/#results', wait_until='networkidle')
        expect(page.locator('#result-cards [role="tab"]')).to_have_count(5)
        assert 'Compare methods' not in page.locator('body').inner_text()
        assert 'Plot data and uncertainty' not in page.locator('body').inner_text()
        assert page.locator('.goal-preview').count() == 0
        assert page.locator('#task-results-panel').evaluate('(el)=>["borderLeftWidth","borderRightWidth","borderBottomWidth","borderRadius"].every(key=>parseFloat(getComputedStyle(el)[key])>0)')
        assert page.locator('a').evaluate_all('(els)=>els.every(el=>!el.textContent.toLowerCase().includes("in the paper"))')
        for task in goals:
            assert page.locator(f'#result-name-{task["id"]}').inner_text() == task['name']
        assert page.locator('.result-goal, .card-generator, .proxy-context, #result-generator').count() == 0
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
            assert card.locator('.result-task-name').evaluate('(el)=>getComputedStyle(el).fontWeight') == '700'
            expect(card.locator('.goal-card-state')).to_have_text('✓')
            expect(card.locator('.goal-number')).to_have_text(f'Goal {goal["number"]}')
            assert card.evaluate('(el)=>parseFloat(getComputedStyle(el.querySelector(".goal-number")).fontSize)>parseFloat(getComputedStyle(el.querySelector(".result-task-name")).fontSize)')
            original_goal=next(stage['exactGoal'] for stage in task['stages'] if stage['id']=='g')
            expect(page.locator('#task-result-description q')).to_have_text(original_goal)
            assert page.locator('#task-result-description q').evaluate('(el)=>getComputedStyle(el).fontStyle')=='italic'
            assert page.locator('#task-result-curriculum').evaluate('(el)=>{const s=getComputedStyle(el);return parseFloat(s.borderWidth)>0 && parseFloat(s.borderRadius)>0 && s.backgroundColor!=="rgba(0, 0, 0, 0)"}')
            assert page.locator('a').evaluate_all('(els)=>els.every(el=>!el.textContent.toLowerCase().includes("in the paper"))')
            expect(page.locator(f'.generator-legend [data-generator="{task["generator"]}"]')).to_contain_text(task['generator'])
            expect(page.locator('#task-results-panel')).to_have_attribute('data-generator', task['generator'])
            assert page.locator('.proxy-context,.chart-readout,#results-table-note,.task-scatter figcaption,.task-docking figcaption,.scaffold-novelty figcaption').count() == 0
            assert page.locator('.observable-context p').inner_text() == goal['observableSummary']
            obs=page.locator('.observable-context').bounding_box()
            if goal['id'] in ('d2','gsk3b'):
                figure=page.locator('.task-molecule');expect(figure).to_be_visible()
                assert figure.bounding_box()['x']>obs['x']+obs['width']
                img=figure.locator('img');img.scroll_into_view_if_needed()
                page.wait_for_function('document.querySelector(".task-molecule img").complete && document.querySelector(".task-molecule img").naturalWidth>0')
            page.locator('.observable-details summary').click()
            assert page.locator('.observable-details li').all_text_contents() == goal['observables']
            page.locator('.observable-details summary').click()
            assert page.locator('[data-curriculum-stage]').count() == len(task['stages'])
            for stage in task['stages']:
                page.locator(f'[data-curriculum-stage="{stage["id"]}"]').click()
                expect(page.locator('#task-result-curriculum')).to_have_attribute('data-selected-stage', stage['id'])
                assert page.locator('#result-curriculum-preview > p q').inner_text() == stage['exactGoal']
                assert page.locator('#result-curriculum-preview > h5').count()==0
                assert page.locator('#result-curriculum-preview > p q').evaluate('(el)=>getComputedStyle(el).fontStyle')=='italic'
                expect(page.locator('.curriculum-traces > summary')).to_contain_text('Explore LLM traces')
                inspected_stages += 1
            # The selected subgoal expands its own traces inside the same goal panel.
            page.locator('.curriculum-traces > summary').click()
            expect(page.locator('#tab-overview')).to_be_visible()
            page.locator('#tab-traces').click()
            expect(page.locator(f'[data-result-task="{task["id"]}"]')).to_have_attribute('aria-selected','true')
            expect(page.locator('[data-curriculum-stage="g"]')).to_have_attribute('aria-selected','true')
            expect(page.locator('#tab-traces')).to_have_attribute('aria-selected','true')
            assert page.locator('#task-results-panel .trace-card').count() == len(task['stages'][-1]['traces'])
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
            assert page.locator('.metric-summary,.metric-tile,.goal-preview').count() == 0
            assert page.locator('#result-discovery').inner_html() == ''
            for index,row in enumerate(result['rows']):
                name=page.locator('#results-table tbody tr').nth(index).locator('.table-method')
                assert name.evaluate('(el)=>getComputedStyle(el).color')==rgb(expected_colors[row['method']])
                assert name.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
                values=page.locator('#results-table tbody tr').nth(index).locator('td').all_text_contents()
                assert values == [f'{mean:.2f} ± {error:.2f}' for mean,error in row['values']], (result['id'],index,values)
            assert page.locator('#results-table thead th').first.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=13
            assert page.locator('#results-table-title,.task-scatter h4,.task-docking h4,.scaffold-novelty h4').count()==0
            if result['table']==2:
                baseline=next(row for row in result['rows'] if row['method']=='Pre-trained')
                methods=[row for row in result['rows'] if row is not baseline]
                assert page.locator('#task-results-plots .js-plotly-plot').count()==1
                expect(page.locator('#docking-chart')).to_be_visible()
                assert page.locator('#comparison-chart,#trajectory-chart').count()==0
                if result['id']=='gsk3b':
                    expect(page.locator('#novelty-chart')).to_be_visible()
                    assert page.locator('#task-results-panel .js-plotly-plot').count()==2
                    novelty=page.locator('#novelty-chart').evaluate('(plot)=>plot.data.map(t=>({method:t.name,x:t.x[0],y:t.y[0],dx:t.error_x.array[0],dy:t.error_y.array[0],symbol:t.marker.symbol,color:t.marker.color,xColor:t.error_x.color,yColor:t.error_y.color}))')
                    assert novelty==[{'method':r['method'],'x':r['noveltyMean'],'y':r['negativeRDockMean'],'dx':r['noveltyCI95'],'dy':r['negativeRDockCI95'],'symbol':expected_symbols[r['method']],'color':expected_colors[r['method']],'xColor':expected_colors[r['method']],'yColor':expected_colors[r['method']]} for r in charts['novelty']]
                    strokes=page.locator('#novelty-chart .scatterlayer .trace').evaluate_all('(els)=>els.map(el=>[...el.querySelectorAll(".errorbar path")].map(path=>getComputedStyle(path).stroke))')
                    assert strokes==[[rgb(expected_colors[r['method']])]*2 for r in charts['novelty']]
                    page.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').hover(force=True)
                    expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('LFD')
                    expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('89.00')
                    expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('17.373')
                    expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('95% CIs')
                    label=page.locator('#novelty-axis-label');tip=page.locator('#metric-help-popover')
                    label.hover();expect(tip).to_be_visible()
                    expect(tip).to_contain_text('Bemis–Murcko')
                    expect(tip).to_contain_text('consistency-filtered training reference')
                    expect(tip).to_contain_text('count only once')
                    tip.hover();expect(tip).to_be_visible()
                    page.mouse.move(1,1);expect(tip).to_be_hidden()
                    label.focus();expect(tip).to_be_visible()
                    page.keyboard.press('Escape');expect(tip).to_be_hidden()
                    page.keyboard.press('Enter');expect(tip).to_be_visible()
                    page.locator('#results-table tbody th').first.click();expect(tip).to_be_hidden()
                else:
                    assert page.locator('#novelty-chart').count()==0
                bars=page.locator('#docking-chart').evaluate('(plot)=>plot.data.map(t=>({type:t.type,method:t.name,x:t.x,y:t.y,error:t.error_y.array,color:t.marker.color,errorColor:t.error_y.color,original:t.customdata.map(v=>v[0]),baseline:t.customdata.map(v=>v[4])}))')
                assert bars == [{'type':'bar','method':r['method'],'x':['GNINA<br>(pK)','|Vina|<br>(kcal/mol)','|rDock|'],'y':[abs(v[0])-abs(baseline['values'][i][0]) for i,v in enumerate(r['values'])],'error':[v[1] for v in r['values']],'color':expected_colors[r['method']],'errorColor':'#000000','original':[v[0] for v in r['values']],'baseline':[v[0] for v in baseline['values']]} for r in methods]
                reference_deltas={'d2':{'DPO':[-.51,-.71,.47],'LFD':[.43,.96,2.25]},'gsk3b':{'Guidance':[-.04,-.20,-.48],'LFD':[.97,1.52,4.36]}}
                for method,expected in reference_deltas[result['id']].items():
                    assert [round(value,2) for value in next(bar for bar in bars if bar['method']==method)['y']]==expected
                axis=page.locator('#docking-chart').evaluate('(plot)=>plot.layout.yaxis')
                assert axis['zeroline'] and axis['range'][0]<0
                assert all(axis['range'][0]<value-spread and axis['range'][1]>value+spread for bar in bars for value,spread in zip(bar['y'],bar['error']))
                legend=page.locator('#task-results-plots [data-legend-method]').evaluate_all('(els)=>els.map(el=>({method:el.dataset.legendMethod,symbol:el.querySelector("svg").dataset.markerSymbol,color:el.querySelector("svg").style.color}))')
                assert all(row['symbol']=='bar' for row in legend)
                assert [row['method'] for row in legend]==[r['method'] for r in methods]
                expect(page.locator('#docking-chart')).to_have_attribute('aria-label',f"Interactive {result['name']} docking improvements: absolute method score minus absolute pretrained score")
                for index,metric in enumerate(result['metrics']):
                    bar=page.locator('#docking-chart .barlayer .trace').last.locator('.point path').nth(index)
                    bar.hover(force=True)
                    expect(page.locator('#docking-chart .hoverlayer')).to_contain_text('LFD')
                    expect(page.locator('#docking-chart .hoverlayer')).to_contain_text(f'{result["rows"][-1]["values"][index][0]:.2f}')
                    expect(page.locator('#docking-chart .hoverlayer')).to_contain_text(f'{bars[-1]["y"][index]:+.2f}')
                    expect(page.locator('#docking-chart .hoverlayer')).to_contain_text(f'{baseline["values"][index][0]:.2f}')
                # A worse score must remain below zero rather than becoming an absolute delta.
                method,index=('DPO',0) if result['id']=='d2' else ('Guidance',2)
                curve=next(i for i,row in enumerate(methods) if row['method']==method)
                page.locator('#docking-chart .barlayer .trace').nth(curve).locator('.point path').nth(index).hover(force=True)
                expect(page.locator('#docking-chart .hoverlayer')).to_contain_text(f'{bars[curve]["y"][index]:.2f}')
                assert bars[curve]['y'][index]<0
                continue
            assert page.locator('#task-results-plots .js-plotly-plot').count()==1
            assert page.locator('#trajectory-chart,#novelty-chart,#curriculum-chart,#docking-chart').count()==0
            yindex=1 if result['table']==1 else 2
            points=page.locator('#comparison-chart').evaluate('(plot)=>plot.data.map(trace=>({method:trace.name,x:trace.x[0],y:trace.y[0],dx:trace.error_x.array[0],dy:trace.error_y.array[0],symbol:trace.marker.symbol}))')
            assert points == [{'method':r['method'],'x':r['values'][0][0],'y':r['values'][yindex][0],'dx':r['values'][0][1],'dy':r['values'][yindex][1],'symbol':expected_symbols[r['method']]} for r in result['rows']]
            legend=page.locator('#task-results-plots [data-legend-method]').evaluate_all('(els)=>els.map(el=>({method:el.dataset.legendMethod,symbol:el.querySelector("svg").dataset.markerSymbol}))')
            assert {r['method']:r['symbol'] for r in legend} == {r['method']:expected_symbols[r['method']] for r in result['rows']}
            page.mouse.move(5,5)
            page.locator('#comparison-chart .scatterlayer .trace').last.locator('.point').hover(force=True)
            expect(page.locator('#comparison-chart .hoverlayer')).to_contain_text('LFD')
            for metric_index,metric in enumerate(result['metrics']):
                expect(page.locator('#comparison-chart .hoverlayer')).to_contain_text(f'{result["rows"][-1]["values"][metric_index][0]:.2f}')
        select('ood')
        assert page.locator('#task-results-plots .js-plotly-plot').count()==0
        assert page.locator('#comparison-chart,#trajectory-chart,#novelty-chart,#docking-chart,#curriculum-chart,#curriculum-readout').count()==0
        assert page.locator('#task-results-plots').inner_html()==''
        expect(page.locator('#task-results-plots')).to_be_hidden()
        assert 'From intermediate subgoals to the full goal' not in page.locator('#task-results-panel').inner_text()
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
        assert page.locator('#trajectory-chart,#novelty-chart,#curriculum-chart,#docking-chart').count()==0
        for width in widths:
            page.set_viewport_size({'width':width,'height':1165})
            cards=page.locator('.result-card').evaluate_all('(els)=>els.map(el=>el.getBoundingClientRect().toJSON())')
            if width>600:
                assert cards[0]['y']==cards[1]['y']
                assert cards[2]['y']==cards[3]['y']==cards[4]['y']
                assert cards[2]['y']>cards[0]['bottom']
                assert max(card['height'] for card in cards)<=116,(width,cards)
            for task in ['anticancer','cpp','d2','gsk3b','ood']:
                select(task)
                page.wait_for_timeout(250)
                assert page.evaluate('document.documentElement.scrollWidth')<=width,(width,task)
                assert page.locator('.js-plotly-plot').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'),(width,task)
                for figure in page.locator('.task-scatter,.task-docking,.scaffold-novelty').all():
                    chart=figure.locator('.interactive-chart').bounding_box()
                    legend=figure.locator('.plot-key').bounding_box()
                    assert legend['y']>=chart['y']+chart['height'],(width,task,chart,legend)
                if task in ('d2','gsk3b'):
                    figure=page.locator('.task-molecule');expect(figure).to_be_visible()
                    obs=page.locator('.observable-context').bounding_box()
                    if width>900:assert figure.bounding_box()['x']>obs['x']+obs['width']
                    else:assert figure.bounding_box()['y']>obs['y']+obs['height']
                if task in ('anticancer','cpp'):
                    table=page.locator('#results-values').bounding_box();plot=page.locator('#task-results-plots').bounding_box()
                    if width>=1200:
                        assert plot['x']>=table['x']+table['width']+20,(width,table,plot)
                        assert abs(plot['y']-table['y'])<1
                        assert abs(plot['height']-table['height'])<2,(width,table,plot)
                        content=page.locator('#results-table').bounding_box();legend=page.locator('.task-scatter .plot-key').bounding_box()
                        assert abs(content['y']+content['height']-legend['y']-legend['height'])<2,(width,content,legend)
                        assert page.locator('#results-values .table-scroll').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1'),width
                    else:
                        assert plot['y']>=table['y']+table['height']+19,(width,table,plot)
                if task=='gsk3b':
                    table=page.locator('#results-values').bounding_box();novelty=page.locator('#task-scaffold-novelty').bounding_box()
                    if width>=1200:
                        assert novelty['x']>=table['x']+table['width']+20,(width,table,novelty)
                        assert abs(novelty['y']-table['y'])<1
                        assert abs(novelty['height']-table['height'])<2,(width,table,novelty)
                        content=page.locator('#results-table').bounding_box();legend=page.locator('.scaffold-novelty .plot-key').bounding_box()
                        assert abs(content['y']+content['height']-legend['y']-legend['height'])<2,(width,content,legend)
                        assert page.locator('#results-values .table-scroll').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1'),width
                    else:
                        assert novelty['y']>=table['y']+table['height']+19,(width,table,novelty)
                else:
                    assert page.locator('#novelty-chart').count()==0
                if width>=1440:
                    for legend in page.locator('.plot-key').all():
                        tops=legend.locator('[data-legend-method]').evaluate_all('(els)=>els.map(el=>el.getBoundingClientRect().top)')
                        assert max(tops)-min(tops)<1,(width,task,tops)
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
        for task in ['anticancer','cpp','d2','gsk3b','ood']:
            touch.locator(f'[data-result-task="{task}"]').tap()
            touch.wait_for_function('(id)=>document.querySelector("#task-results-panel").dataset.plotReadyTask===id',arg=task)
            touch.locator('[data-curriculum-stage="g1"]').tap()
            expect(touch.locator('[data-curriculum-stage="g1"]')).to_have_attribute('aria-selected','true')
            if task in ('anticancer','cpp'):
                touch.locator('#comparison-chart .scatterlayer .trace').last.locator('.point').tap(force=True)
                expect(touch.locator('#comparison-chart .hoverlayer')).to_contain_text('53.54' if task=='anticancer' else '69.06')
                expect(touch.locator('#comparison-chart .hoverlayer')).to_contain_text('42.48' if task=='anticancer' else '37.02')
                touch.locator('.task-scatter .plot-key').tap()
                expect(touch.locator('#comparison-chart .hoverlayer')).to_have_text('')
            elif task in ('d2','gsk3b'):
                result=next(r for r in results if r['id']==task)
                for index in range(3):
                    bar=touch.locator('#docking-chart .barlayer .trace').last.locator('.point path').nth(index)
                    bar.scroll_into_view_if_needed();bar.tap(force=True)
                    expect(touch.locator('#docking-chart .hoverlayer')).to_contain_text(f'{result["rows"][-1]["values"][index][0]:.2f}')
                    baseline=next(row for row in result['rows'] if row['method']=='Pre-trained')
                    delta=abs(result['rows'][-1]['values'][index][0])-abs(baseline['values'][index][0])
                    expect(touch.locator('#docking-chart .hoverlayer')).to_contain_text(f'{delta:+.2f}')
                if task=='gsk3b':
                    touch.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').tap(force=True)
                    expect(touch.locator('#novelty-chart .hoverlayer')).to_contain_text('89.00')
                    expect(touch.locator('#novelty-chart .hoverlayer')).to_contain_text('17.373')
                    label=touch.locator('#novelty-axis-label');tip=touch.locator('#metric-help-popover')
                    label.tap();expect(tip).to_be_visible()
                    bounds=tip.bounding_box()
                    assert bounds['x']>=0 and bounds['x']+bounds['width']<=390
                    label.tap();expect(tip).to_be_hidden()
            else:
                assert touch.locator('#task-results-plots .js-plotly-plot').count()==0
                expect(touch.locator('#task-results-plots')).to_be_hidden()
                touch.locator('[data-curriculum-stage="g"]').tap()
                expect(touch.locator('[data-curriculum-stage="g"]')).to_have_attribute('aria-selected','true')
                expect(touch.locator('#result-curriculum-preview .curriculum-preview-links > span')).to_contain_text('Assessment only')
        page.goto((root/'index.html').as_uri(),wait_until='load')
        page.wait_for_function('document.querySelector("#task-results-panel").dataset.plotReadyTask === "anticancer"')
        expect(page.locator('#result-cards [role="tab"]')).to_have_count(5)
        assert not errors,errors
        assert not failures,failures
        browser.close()
    report={'status':'passed','viewports':widths,'goals':5,'table_metric_pairs':66,'paired_activity_toxicity':'passed','docking_grouped_bars':'passed','docking_absolute_values':'passed','docking_baseline_deltas':'passed','docking_negative_improvements':'passed','docking_zero_reference':'passed','docking_black_error_bars':'passed','docking_signed_hover':'passed','molecule_context_layout':'passed','scaffold_novelty_values':'passed','scaffold_novelty_marker_colored_cis':'passed','table_method_colors':'passed','scaffold_axis_definition_hover_focus_touch':'passed','scaffold_novelty_hover_touch':'passed','scaffold_novelty_table_layout':'passed','plot_data_disclosure':'removed','task_plot_isolation':'passed','marker_legends':'passed','lower_plot_legends':'passed','desktop_single_line_legends':'passed','table_plot_equal_height':'passed','plot_and_table_footers':'removed','hover_tooltips':'passed','redundant_table_plot_headings':'removed','compact_numbered_two_row_cards':'passed','verbatim_goal_headers':'passed','curriculum_subbox':'passed','anticancer_table_plot_layout':'passed','cpp_table_plot_layout':'passed','proxy_paragraphs':'removed','shared_generator_legend':'passed','fifth_task_evidence':'passed','goal5_curriculum_plot':'removed','goal5_figure':'passed','generator_colors':'passed','observable_lists':'passed','curriculum_stages':23,'curriculum_keyboard_touch':'passed','curriculum_trace_links':'passed','score_footers_and_metric_tiles':'removed','single_results_panel':'passed','selected_task_highlight':'passed','inline_paper_links':'removed','verbatim_curriculum_goals':23,'rapid_switching':'passed','keyboard':'passed','hover_touch':'passed','local_file':'passed','browser_errors':errors,'failed_requests':failures}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

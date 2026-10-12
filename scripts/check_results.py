#!/usr/bin/env python3
"""Verify persistent case-study plots, source values, and independent trace views."""
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
    novelty = json.loads((root / 'data/charts.json').read_text())['novelty']
    panel_data = json.loads((root / 'data/result-panels.json').read_text())
    colors = {'LFD':'#8732ad','Pre-trained':'#33373f','DPO':'#d77b00',
              'DiffusionNFT':'#286565','Flow-GRPO':'#719adc','Guidance':'#c54b59'}
    symbols = {'LFD':'square','Pre-trained':'x','DPO':'circle',
               'DiffusionNFT':'diamond','Flow-GRPO':'triangle-up','Guidance':'triangle-down'}
    errors, failures = [], []
    widths = [360,390,600,768,1024,1440,1920]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('response', lambda r: failures.append(r.url) if r.status >= 400 else None)
        page.goto(args.url+'/#peptides', wait_until='networkidle')
        page.wait_for_function('document.querySelector("#result-cards").dataset.plotsReady === "true"')
        expect(page.locator('#task-results-panel')).to_be_hidden()
        assert page.locator('.result-overview').count() == 5
        assert page.locator('.snapshot-value,#goal-results-toggle,#goal-results-content').count() == 0
        assert page.locator('.result-overview .js-plotly-plot').count() == 4
        for result in results:
            task = result['id']
            overview = page.locator(f'[data-result-overview="{task}"]')
            assert f'Goal {next(g["number"] for g in panel_data["tasks"] if g["id"]==task)}' in overview.locator('h4').inner_text().replace('\xa0',' ')
            table = overview.locator('.results-table')
            for index,row in enumerate(result['rows']):
                tr=table.locator('tbody tr').nth(index)
                assert tr.locator('td').all_text_contents() == [f'{mean:.2f} ± {error:.2f}' for mean,error in row['values']]
                assert tr.locator('.table-method').evaluate('(el)=>el.style.color') == 'rgb('+', '.join(str(int(colors[row['method']][i:i+2],16)) for i in (1,3,5))+')'
            if result['table']==1:
                chart=overview.locator('.js-plotly-plot')
                actual=chart.evaluate('(el)=>el.data.map(t=>({method:t.name,x:t.x[0],y:t.y[0],dx:t.error_x.array[0],dy:t.error_y.array[0],color:t.marker.color,symbol:t.marker.symbol,xc:t.error_x.color,yc:t.error_y.color}))')
                expected=[dict(method=r['method'],x=r['values'][0][0],y=r['values'][1][0],dx=r['values'][0][1],dy=r['values'][1][1],color=colors[r['method']],symbol=symbols[r['method']],xc=colors[r['method']],yc=colors[r['method']]) for r in result['rows']]
                assert actual==expected,(task,actual)
                chart.locator('.scatterlayer .trace').last.locator('.point').hover(force=True)
                expect(chart.locator('.hoverlayer')).to_contain_text('LFD')
                for mean,error in result['rows'][-1]['values']:
                    expect(chart.locator('.hoverlayer')).to_contain_text(f'{mean:.2f} ± {error:.2f}')
            details=overview.locator('.result-metrics')
            expect(details).not_to_have_attribute('open','')
            details.locator('summary').focus();page.keyboard.press('Enter')
            expect(table).to_be_visible()
            if result['table']==2:
                chart=overview.locator(f'#docking-{task}')
                page.wait_for_function('(id)=>document.querySelector(id).data !== undefined',arg=f'#docking-{task}')
                actual=chart.evaluate('(el)=>el.data.map(t=>({method:t.name,y:t.y,error:t.error_y.array,ci:t.error_y.color,color:t.marker.color,original:t.customdata.map(d=>d[0])}))')
                base=result['rows'][0]['values']
                for trace,row in zip(actual,result['rows'][1:]):
                    assert trace['method']==row['method']
                    assert trace['y']==[abs(mean)-abs(base[i][0]) for i,(mean,spread) in enumerate(row['values'])]
                    assert trace['error']==[spread for mean,spread in row['values']]
                    assert trace['original']==[mean for mean,spread in row['values']]
                    assert trace['ci']=='#000000' and trace['color']==colors[row['method']]
                assert any(value<0 for trace in actual for value in trace['y'])
                chart.locator('.barlayer .trace').last.locator('.point path').nth(0).hover(force=True)
                expect(chart.locator('.hoverlayer')).to_contain_text('LFD')
                expect(chart.locator('.hoverlayer')).to_contain_text('Original score:')
                assert chart.locator('.errorbar path').evaluate_all('(els)=>els.length>0 && els.every(el=>getComputedStyle(el).stroke==="rgb(0, 0, 0)")')
            details.locator('summary').click()
            expect(table).not_to_be_visible()
        chart=page.locator('#novelty-chart')
        actual=chart.evaluate('(el)=>el.data.map(t=>({method:t.name,x:t.x[0],y:t.y[0],dx:t.error_x.array[0],dy:t.error_y.array[0],color:t.marker.color,xc:t.error_x.color,yc:t.error_y.color}))')
        assert actual==[dict(method=r['method'],x=r['noveltyMean'],y=r['negativeRDockMean'],dx=r['noveltyCI95'],dy=r['negativeRDockCI95'],color=colors[r['method']],xc=colors[r['method']],yc=colors[r['method']]) for r in novelty]
        hit=page.locator('.discovery-overview')
        expect(hit).to_contain_text('0 / 38,500')
        expect(hit).to_contain_text('A full-goal hit')
        expect(hit.locator('img')).to_have_attribute('src',panel_data['oodEvidence']['figure']['file'])
        assert hit.locator('table').count()==0
        # Opening and switching traces must leave the same live plot nodes/data intact.
        page.evaluate('window.primaryPlot=document.querySelector("#comparison-anticancer");window.primaryData=window.primaryPlot.data')
        for goal in panel_data['tasks']:
            page.locator(f'[data-result-task="{goal["id"]}"]').click()
            expect(page.locator('#panel-overview')).to_be_visible()
            assert page.locator('#task-results-panel > .goal-section').count()==2
            assert page.locator('#task-results-panel .js-plotly-plot,#task-results-panel table').count()==0
            page.locator('#tab-traces').click()
            assert page.locator('.trace-card').count()==4
            assert page.evaluate('window.primaryPlot===document.querySelector("#comparison-anticancer") && window.primaryPlot.data===window.primaryData')
        for width in widths:
            page.set_viewport_size({'width':width,'height':1000})
            page.wait_for_timeout(350)  # Plotly responds to window resize asynchronously.
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
            assert page.locator('.result-overview .js-plotly-plot:visible').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'),width
            ids=page.locator('[id]').evaluate_all('(els)=>els.map(el=>el.id)')
            assert len(ids)==len(set(ids)),width
            for details in page.locator('.result-metrics').all():
                details.locator('summary').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
                details.locator('summary').click()
            if width in [390,1440]:
                page.locator('#peptides .case-results-summary').screenshot(path=str(out/f'peptides-{width}.png'))
                page.locator('#molecules .case-results-summary').screenshot(path=str(out/f'molecules-{width}.png'))
        # Real touch still exposes values on the now persistent charts.
        mobile=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
        touch=mobile.new_page();touch.on('pageerror',lambda e:errors.append(str(e)))
        touch.goto(args.url,wait_until='networkidle')
        touch.wait_for_function('document.querySelector("#result-cards").dataset.plotsReady === "true"')
        for task,kind in [('anticancer','scatter'),('cpp','scatter'),('d2','bar'),('gsk3b','novelty')]:
            selector='#novelty-chart' if kind=='novelty' else f'#docking-{task}' if kind=='bar' else f'#comparison-{task}'
            chart=touch.locator(selector)
            point=chart.locator('.barlayer .trace').last.locator('.point path').first if kind=='bar' else chart.locator('.scatterlayer .trace').last.locator('.point')
            point.tap(force=True)
            expect(chart.locator('.hoverlayer')).not_to_have_text('')
            touch.locator('[data-result-task="ood"]').tap()
            expect(chart.locator('.hoverlayer')).to_have_text('')
        mobile.close();browser.close()
    assert not errors,errors
    assert not failures,failures
    report={'status':'passed','primary_plots':4,'supplementary_docking_plot':1,'source_tables':4,
            'goal5_hit':'preserved','results_outside_traces':'passed','persistent_plot_nodes':'passed',
            'hover_touch':'passed','black_docking_intervals':'passed','colored_scaffold_intervals':'passed',
            'viewports':widths,'browser_errors':errors,'failed_http_requests':failures}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':
    main()

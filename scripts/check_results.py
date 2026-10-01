#!/usr/bin/env python3
"""Verify chart values, mouse/touch inspection, and large-screen geometry."""
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
    widths = [360, 390, 768, 901, 1024, 1280, 1440, 1920, 2227, 2560]
    errors, failures, geometry = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 2227, 'height': 1165}, reduced_motion='reduce')
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        page.goto(args.url + '/#results', wait_until='networkidle')
        page.wait_for_function('document.querySelectorAll(".js-plotly-plot").length === 3')
        for result in results:
            page.locator('#result-task').select_option(result['id'])
            for index, metric in enumerate(result['metrics']):
                page.locator('#result-metric').select_option(str(index))
                page.wait_for_function('''({id,index,count}) => {
                    const plot=document.querySelector('#comparison-chart');
                    return plot.data && plot.data.length===count && plot.dataset.chartTask===id &&
                        plot.dataset.chartMetric===String(index) && plot.layout.xaxis.title.text===window.LFD_DATA.results.find(r=>r.id===id).metrics[index].label;
                }''', arg={'id':result['id'],'index':index,'count':len(result['rows'])})
                points = page.locator('#comparison-chart').evaluate('(plot)=>plot.data.map(trace=>({method:trace.name,mean:trace.x[0],error:trace.error_x.array[0]}))')
                assert points == [{'method':row['method'],'mean':row['values'][index][0],'error':row['values'][index][1]} for row in result['rows']], (result['id'],index,points)
            page.mouse.move(5, 5)  # mirror leaving the dropdown before inspecting a marker
            point = page.locator('#comparison-chart .scatterlayer .trace').last.locator('.point')
            point.hover(force=True)
            expect(page.locator('#comparison-chart .hoverlayer')).to_contain_text('LFD')
            expect(page.locator('#comparison-readout')).to_contain_text('LFD')
            for metric_index, metric in enumerate(result['metrics']):
                assert f'{result["rows"][-1]["values"][metric_index][0]:.2f}' in page.locator('#comparison-chart .hoverlayer').text_content()
        page.locator('[data-result-task="cpp"]').click()
        expect(page.locator('#result-task')).to_have_value('cpp')
        expect(page.locator('#result-task')).to_be_focused()
        # Plotly handles pointer input on its transparent event layer above markers.
        point=page.locator('#trajectory-chart .scatterlayer .trace').last.locator('.point').nth(6)
        point.hover(force=True)
        expect(page.locator('#trajectory-chart .hoverlayer')).to_contain_text('round 6')
        expect(page.locator('#trajectory-chart .hoverlayer')).to_contain_text('6.726')
        expect(page.locator('#trajectory-chart .hoverlayer')).to_contain_text('6.839')
        trajectory = page.locator('#trajectory-chart').evaluate('(plot)=>plot.data.find(trace=>trace.name==="LFD best so far").y')
        assert trajectory == [row['bestMean'] for row in charts['trajectory']]
        novelty=page.locator('#novelty-chart').evaluate('(plot)=>plot.data.map(trace=>({method:trace.name,x:trace.x[0],y:trace.y[0],dx:trace.error_x.array[0],dy:trace.error_y.array[0]}))')
        assert novelty == [{'method':r['method'],'x':r['noveltyMean'],'y':r['negativeRDockMean'],'dx':r['noveltyCI95'],'dy':r['negativeRDockCI95']} for r in charts['novelty']]
        page.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').hover(force=True)
        expect(page.locator('#novelty-readout')).to_contain_text('LFD')
        expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('89.00')
        expect(page.locator('#novelty-chart .hoverlayer')).to_contain_text('17.373')
        for width in widths:
            page.set_viewport_size({'width':width,'height':1165})
            page.locator('#method').evaluate('(el)=>el.scrollIntoView({behavior:"instant"})')
            page.wait_for_timeout(250)  # allow Plotly's debounced responsive resize
            assert page.evaluate('document.documentElement.scrollWidth') <= width, width
            assert page.locator('.algorithm-row').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'), width
            boxes=page.locator('#contents,#method,.algorithm-box').evaluate_all('(els)=>els.map(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width};})')
            if width >= 1280:
                assert boxes[0]['right'] <= boxes[1]['left'] - 10, (width,boxes)
                assert page.locator('.contents-list a').first.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)') == 16
            if width >= 1920:
                assert 425 <= boxes[2]['width'] <= 430
                assert boxes[0]['left'] > 150
            assert page.locator('.js-plotly-plot').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'), width
            geometry.append({'width':width,'menu':boxes[0],'method':boxes[1],'algorithm':boxes[2]})
            if width in [390,2227]:
                page.screenshot(path=str(out/f'method-{width}.png'))
                page.locator('#results').evaluate('(el)=>el.scrollIntoView({behavior:"instant"})')
                page.screenshot(path=str(out/f'results-{width}.png'))
                page.locator('.figure-section').evaluate('(el)=>el.scrollIntoView({behavior:"instant"})')
                page.screenshot(path=str(out/f'figures-{width}.png'))
        mobile=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
        touch=mobile.new_page()
        touch.goto(args.url+'/#results',wait_until='networkidle')
        touch.locator('#result-task').select_option('d2')
        touch.locator('#comparison-chart .scatterlayer .trace').last.locator('.point').tap(force=True)
        expect(touch.locator('#comparison-readout')).to_contain_text('LFD')
        expect(touch.locator('#comparison-readout')).to_contain_text('6.54')
        touch.locator('#novelty-chart .scatterlayer .trace').nth(1).locator('.point').tap(force=True)
        expect(touch.locator('#novelty-readout')).to_contain_text('LFD')
        expect(touch.locator('#novelty-readout')).to_contain_text('89.00')
        assert touch.evaluate('document.documentElement.scrollWidth') <= 390
        page.goto((root/'index.html').as_uri(),wait_until='load')
        page.wait_for_function('document.querySelectorAll(".js-plotly-plot").length === 3')
        assert not errors, errors
        assert not failures, failures
        browser.close()
    (out/'report.json').write_text(json.dumps({'status':'passed','viewports':widths,'geometry':geometry,'table_metric_pairs':66,'plot_panels':3,'mouse_hover':'passed','touch_inspection':'passed','local_file':'passed','browser_errors':errors,'failed_requests':failures},indent=2)+'\n')
    print('All table/chart values, saved plot coordinates, hover, touch, local files, and ten viewport widths passed.')


if __name__ == '__main__':
    main()

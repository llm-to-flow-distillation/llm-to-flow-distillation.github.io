#!/usr/bin/env python3
"""Check metric definitions, citations, and pointer/keyboard/touch access."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8876')
    parser.add_argument('--output-dir',default='test-results/metric-help')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    definitions=json.loads((root/'data/metric-definitions.json').read_text())
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    errors=[];seen=set();inspected=0
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--no-sandbox'])
        for width in [1440,390]:
            page=browser.new_page(viewport={'width':width,'height':1000},has_touch=width==390,is_mobile=width==390,reduced_motion='reduce')
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(args.url+'/#results',wait_until='networkidle')
            tip=page.locator('#metric-help-popover')
            for task in ['anticancer','cpp','d2','gsk3b']:
                page.locator(f'[data-result-task="{task}"]').click()
                page.wait_for_function('(id)=>document.querySelector("#task-results-panel").dataset.plotReadyTask===id',arg=task)
                assert page.locator('#results-table-title,.task-scatter h4,.scaffold-novelty h4,.task-docking h4').count()==0
                labels=page.locator('#task-results-panel [data-metric]')
                for label in labels.all():
                    key=label.get_attribute('data-metric');seen.add(key)
                    label.scroll_into_view_if_needed()
                    # Reset pointer/focus before exercising each independent control.
                    page.keyboard.press('Escape')
                    page.locator('#task-results-panel').evaluate('(el)=>el.focus({preventScroll:true})')
                    if width==1440:label.hover()
                    else:label.tap()
                    expect(tip).to_be_visible()
                    expect(label).to_have_attribute('aria-expanded','true')
                    expect(tip.locator('p')).to_have_text(definitions['metrics'][key]['text'])
                    refs=[definitions['references'][r] for r in definitions['metrics'][key]['references']]
                    assert tip.locator('a').evaluate_all('(els)=>els.map(el=>el.href)')==[r['url'] for r in refs]
                    assert tip.locator('a').evaluate_all('(els)=>els.every(el=>el.target==="_blank" && el.rel.includes("noopener"))')
                    box=tip.bounding_box()
                    assert box['x']>=0 and box['x']+box['width']<=width+1,(key,width,box)
                    assert box['y']>=0 and box['y']+box['height']<=1001,(key,width,box)
                    if width==1440:
                        tip.hover();expect(tip).to_be_visible()
                        page.mouse.move(1,1);expect(tip).to_be_hidden()
                        label.focus();expect(tip).to_be_visible()
                        page.keyboard.press('Tab');expect(tip.locator('a').first).to_be_focused()
                        page.keyboard.press('Escape');expect(tip).to_be_hidden();expect(label).to_be_focused()
                        page.keyboard.press('Enter');expect(tip).to_be_visible()
                        page.keyboard.press('Escape');expect(tip).to_be_hidden()
                    else:
                        label.tap();expect(tip).to_be_hidden()
                    inspected+=1
                # Changing tasks closes any open definition instead of retaining stale text.
                labels.first.click();expect(tip).to_be_visible()
                page.locator('[data-result-task="ood"]').click();expect(tip).to_be_hidden()
            page.locator('[data-result-task="anticancer"]').click()
            page.wait_for_function('document.querySelector("#task-results-panel").dataset.plotReadyTask==="anticancer"')
            axis=page.locator('#comparison-chart .xtitle')
            axis.scroll_into_view_if_needed();axis.click();expect(tip).to_be_visible()
            page.screenshot(path=str(out/f'axis-help-{width}.png'))
            # Definitions remain attached to plot labels after Plotly handles a resize.
            page.set_viewport_size({'width':width+40,'height':1000})
            expect(tip).to_be_hidden();page.wait_for_timeout(300)
            expect(page.locator('#comparison-chart .xtitle')).to_have_attribute('data-metric','anticp')
            page.locator('#comparison-chart .xtitle').click();expect(tip).to_be_visible()
            page.evaluate('window.scrollTo(0,0)');expect(tip).to_be_hidden()
            page.close()
        browser.close()
    assert seen==set(definitions['metrics']),seen
    assert not errors,errors
    report={'status':'passed','metric_definitions':len(seen),'controls_inspected':inspected,'viewports':[1440,390],'headings':'removed','citations':'verified DOI links','hover_focus_touch':'passed','citation_keyboard_access':'passed','viewport_containment':'passed','resize_and_task_switching':'passed','browser_errors':errors}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':
    main()

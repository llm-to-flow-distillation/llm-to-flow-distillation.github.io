#!/usr/bin/env python3
"""Check algorithm explanations with pointer, keyboard, and touch input."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', default='test-results/method')
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    errors, failures, views = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        popup = page.locator('#algorithm-details')
        trigger = lambda name: page.locator(f'[data-function="{name}"]')
        page.goto(args.url + '/#method', wait_until='networkidle')
        expect(popup).not_to_be_visible()
        disclosure = page.locator('#method-algorithm')
        summary = disclosure.locator('summary')
        expect(disclosure).not_to_have_attribute('open', '')
        expect(page.locator('.algorithm-box')).not_to_be_visible()
        expect(page.locator('.method-steps')).to_be_visible()
        assert page.locator('.algorithm-function').count() == 5
        page.screenshot(path=str(out/'desktop-overview.png'))
        summary.focus()
        page.keyboard.press('Enter')
        expect(page.locator('.algorithm-box')).to_be_visible()
        assert summary.locator('span').evaluate('(el)=>getComputedStyle(el).transform') == 'none'
        for name in ['sample','observe','setgoal','judge','minimize','learnable']:
            trigger(name).hover()
            expect(popup).to_be_visible()
            expect(trigger(name)).to_have_attribute('aria-expanded','true')
            expect(popup.locator(f'[data-function-panel="{name}"]')).to_be_visible()
            # The reader can move onto the explanation without it disappearing.
            popup.hover(position={'x':20,'y':20})
            expect(popup).to_be_visible()
            page.keyboard.press('Escape')
            expect(popup).not_to_be_visible()
        trigger('setgoal').hover()
        page.mouse.move(1400,40)
        expect(popup).not_to_be_visible()
        trigger('learnable').focus()
        expect(popup).to_be_visible()
        expect(popup.locator('[data-function-panel="learnable"]')).to_have_text(
            'i.e., such that the LLM judgement yields enough positive and negative examples for DPO.')
        page.keyboard.press('Enter')
        expect(popup).to_be_focused()
        page.keyboard.press('Escape')
        expect(trigger('learnable')).to_be_focused()
        expect(popup).not_to_be_visible()
        # Click pins; hovering another operation does not replace pinned content.
        trigger('minimize').click()
        page.mouse.move(1400,40)
        expect(popup).to_be_visible()
        expect(popup).to_have_attribute('data-pinned','true')
        trigger('judge').hover()
        expect(popup.locator('[data-function-panel="minimize"]')).to_be_visible()
        page.screenshot(path=str(out/'desktop-minimize.png'))
        page.locator('#close-function-details').click()
        expect(popup).not_to_be_visible()
        expect(trigger('minimize')).to_be_focused()
        # A focused function previews details; Enter pins and lets readers enter it.
        trigger('judge').focus()
        expect(popup.locator('[data-function-panel="judge"]')).to_be_visible()
        page.keyboard.press('Enter')
        expect(popup).to_be_focused()
        page.keyboard.press('Escape')
        expect(popup).not_to_be_visible()
        expect(trigger('judge')).to_be_focused()
        page.keyboard.press('Tab')
        expect(trigger('minimize')).to_be_focused()
        expect(popup.locator('[data-function-panel="minimize"]')).to_be_visible()
        page.keyboard.press('Escape')
        expect(popup).not_to_be_visible()
        # Collapsing the pseudocode dismisses any pinned function explanation.
        trigger('judge').click()
        expect(popup).to_be_visible()
        disclosure.evaluate('(el)=>el.open=false')
        expect(popup).not_to_be_visible()
        expect(page.locator('.algorithm-box')).not_to_be_visible()
        for width in [360,390,768,1024,1280,1440]:
            page.set_viewport_size({'width':width,'height':1000})
            page.goto(args.url + '/#method',wait_until='networkidle')
            page.reload(wait_until='networkidle')
            page.wait_for_function('document.fonts.status === "loaded"')
            expect(page.locator('.algorithm-box')).not_to_be_visible()
            summary.click()
            expect(page.locator('.algorithm-box')).to_be_visible()
            layout = page.evaluate("""() => {
                const box = element => { const r = element.getBoundingClientRect();
                    return {x:r.x, y:r.y, right:r.right, bottom:r.bottom, width:r.width}; };
                const get = selector => box(document.querySelector(selector));
                return {content:get('.method-content'), algorithm:get('.algorithm-box'),
                    intro:get('.method-introduction'), steps:[...document.querySelectorAll('.method-step')].map(box),
                    curriculum:get('.method-curriculum'), disclosure:get('#method-algorithm')};
            }""")
            content, algorithm = layout['content'], layout['algorithm']
            reading_order = [layout['intro'], *layout['steps'], layout['curriculum'], layout['disclosure']]
            assert all(before['bottom'] <= after['y'] for before,after in zip(reading_order,reading_order[1:])), (width,layout)
            assert abs((algorithm['x']+algorithm['right'])-(content['x']+content['right'])) < 2, (width,layout)
            assert page.locator('.method-content .math-display, .method-curriculum .math-display').evaluate_all(
                '(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'), width
            assert page.locator('.method-content h3').count() == 3
            expect(page.locator('.method-curriculum p > #curriculum-title')).to_have_text('A design-space view.')
            assert r'\mathcal D_t' not in page.locator('.method-preference-equation').get_attribute('data-tex')
            expect(page.locator('.method-update [data-tex]').first).to_have_attribute(
                'data-tex', r'\mathcal D_t=\mathcal P_t\times\mathcal N_t')
            assert page.evaluate('document.documentElement.scrollWidth') <= width
            assert page.locator('.algorithm-row').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'), width
            for name in ['sample','observe','setgoal','judge','minimize','learnable']:
                trigger(name).click()
                expect(popup).to_be_visible()
                page.wait_for_function('document.fonts.status === "loaded"')
                bounds = popup.bounding_box()
                assert bounds['x'] >= 0 and bounds['x']+bounds['width'] <= width+1, (width,bounds)
                assert bounds['y'] >= 0 and bounds['y']+bounds['height'] <= 1001, (width,bounds)
                assert popup.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1'), (width,name)
                assert popup.locator('.math-display:visible').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)'), (width,name)
                assert page.locator('.katex-error').count() == 0
                page.keyboard.press('Escape')
                expect(popup).not_to_be_visible()
            views.append(width)
        # Actual touch input opens and dismisses the mobile panel.
        mobile = browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
        touch = mobile.new_page()
        touch.on('pageerror',lambda error:errors.append(str(error)))
        touch.goto(args.url + '/#method',wait_until='networkidle')
        touch.locator('#method-algorithm > summary').tap()
        touch.locator('[data-function="minimize"]').tap()
        expect(touch.locator('#algorithm-details')).to_be_visible()
        expect(touch.locator('#algorithm-details')).to_have_attribute('data-pinned','true')
        touch.screenshot(path=str(out/'mobile-minimize.png'))
        touch.locator('#close-function-details').tap()
        expect(touch.locator('#algorithm-details')).not_to_be_visible()
        touch.locator('[data-function="judge"]').tap()
        touch.locator('#method-title').tap()
        expect(touch.locator('#algorithm-details')).not_to_be_visible()
        touch.locator('[data-function="learnable"]').tap()
        expect(touch.locator('#algorithm-details')).to_be_visible()
        expect(touch.locator('[data-function-panel="learnable"]')).to_be_visible()
        touch.locator('#close-function-details').tap()
        expect(touch.locator('#algorithm-details')).not_to_be_visible()
        # Resizing an open panel repositions it inside the viewport.
        page.set_viewport_size({'width':1440,'height':1000})
        page.goto(args.url + '/#method',wait_until='networkidle')
        page.reload(wait_until='networkidle')
        summary.click()
        trigger('minimize').click()
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_function('''() => {const r=document.querySelector('#algorithm-details').getBoundingClientRect();return r.x>=0 && r.right<=innerWidth && r.y>=0 && r.bottom<=innerHeight;}''')
        page.keyboard.press('Escape')
        page.locator('[data-result-task="anticancer"]').click()
        page.locator('#tab-traces').click()
        assert page.locator('.trace-card').count() == 4
        assert not errors, errors
        assert not failures, failures
        browser.close()
    report={'status':'passed','viewports':views,'pointer_hover':'passed','pinning':'passed','keyboard':'passed','touch':'passed','responsive_positioning':'passed','trace_smoke':'passed','ordered_method_steps':'passed','algorithm_disclosure':'passed','learnable_definition':'passed','browser_errors':errors,'failed_requests':failures}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

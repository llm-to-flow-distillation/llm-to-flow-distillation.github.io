#!/usr/bin/env python3
"""Check all Figure 3 data, linked controls, prompt variants and responsive layout."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8876')
    parser.add_argument('--output-dir', type=Path, default=Path('/tmp/lfd-calibration-check'))
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=True)
    data = json.loads((Path(__file__).resolve().parents[1] / 'data/calibration.json').read_text())
    errors, bad_requests = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('response', lambda r: bad_requests.append(r.url) if r.status >= 400 else None)
        page.goto(args.url + '/#why-preferences', wait_until='networkidle')
        expect(page.locator('#calibration-grid')).to_have_attribute('data-ready', 'true')
        assert page.locator('.project-contents a').evaluate_all('(els)=>els.map(el=>el.hash)') == ['#method', '#why-preferences', '#peptides', '#molecules']
        assert page.locator('#method').bounding_box()['y'] < page.locator('#why-preferences').bounding_box()['y'] < page.locator('#peptides').bounding_box()['y']
        assert page.locator('#calibration-grid .js-plotly-plot').count() == 6
        for domain in data['domains']:
            for kind in ['scatter', 'bars']:
                chart = page.locator(f'#calibration-{kind}-{domain["id"]}')
                actual = chart.evaluate('(el) => el.data.map(t=>({x:t.x,y:t.y,customdata:t.customdata,error:t.error_y,marker:t.marker}))')
                for model, expected, trace in zip(data['models'], domain['series'], actual):
                    assert trace['marker']['color'] == model['color']
                    if kind == 'scatter':
                        assert trace['x'] == [p[0] for p in expected['points']]
                        assert trace['y'] == [p[1] for p in expected['points']]
                        assert trace['marker']['symbol'] == model['symbol']
                    else:
                        assert trace['y'] == [b['mean'] for b in expected['bars']]
                        assert trace['error']['array'] == [b['sd'] for b in expected['bars']]
                        assert trace['error']['color'] == '#252d28'
                        assert [r[2:] for r in trace['customdata']] == [[b['emitted'], b['selected']] for b in expected['bars']]
            # Every domain and method exposes the correct task and exact instruction text.
            for method in ['joint_score'] + data['methods']:
                trigger = page.locator(f'.calibration-prompt[data-domain="{domain["id"]}"][data-method="{method}"]')
                trigger.focus()
                popup = page.locator('#calibration-prompt-dialog')
                expect(popup).to_be_visible()
                assert popup.locator('blockquote').nth(0).inner_text() == domain['prompt'].strip()
                assert popup.locator('.calibration-instructions').inner_text().strip() == data['prompts']['methods'][method]['variants']['default'].strip()
                if method == 'positive_negative':
                    trigger.click()
                    popup.locator('[data-variant="opus"]').click()
                    assert popup.locator('.calibration-instructions').inner_text().strip() == data['prompts']['methods'][method]['variants']['opus'].strip()
                    popup.locator('summary').click()
                    assert popup.locator('details blockquote').inner_text().strip() == data['prompts']['common'].strip()
                page.keyboard.press('Escape')
                expect(popup).not_to_be_visible()
        # Native bar hover and keyboard point inspection both work.
        bar = page.locator('#calibration-bars-peptide .barlayer .trace').first.locator('.point path').first
        # Plotly's transparent event layer intentionally sits above the SVG bar.
        bar.hover(force=True)
        expect(page.locator('#calibration-bars-peptide .hovertext')).to_contain_text('Accuracy: 79.89% ± 5.61 SD')
        expect(page.locator('#calibration-bars-peptide .hovertext')).not_to_contain_text('Emitted pairs')
        expect(page.locator('#calibration-bars-peptide .hovertext')).not_to_contain_text('Mean across')
        assert page.locator('#calibration-caption').count() == 0
        assert 'Preferences · higher is better' not in page.locator('#calibration-grid').inner_text()
        page.locator('#calibration-scatter-peptide').focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('#calibration-scatter-peptide .hovertext')).to_contain_text('Absolute error')
        page.keyboard.press('Escape')
        # One shared model legend controls all six panels, including uncertainty bars.
        for index, model in enumerate(data['models']):
            button = page.locator(f'[data-calibration-model="{model["id"]}"]')
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'false')
            page.wait_for_function('(index) => [...document.querySelectorAll(".calibration-plot")].every(el=>el.data[index].visible===false)', arg=index)
            button.click()
            page.wait_for_function('(index) => [...document.querySelectorAll(".calibration-plot")].every(el=>el.data[index].visible===true)', arg=index)
        widths = [360, 390, 700, 768, 1024, 1280, 1440, 1920]
        for width in widths:
            page.set_viewport_size({'width': width, 'height': 1100})
            page.wait_for_timeout(200)
            page.locator('#why-preferences').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            for selector in ['.calibration-scatter', '.calibration-bars']:
                boxes = page.locator(selector).evaluate_all('(els)=>els.map(el=>({y:el.getBoundingClientRect().y,x:el.getBoundingClientRect().x,width:el.getBoundingClientRect().width}))')
                if width > 700:
                    assert max(b['y'] for b in boxes) - min(b['y'] for b in boxes) < 2, (width, boxes)
                else:
                    assert len(set(round(b['x']) for b in boxes)) == 1
            if width in [390, 1440]:
                page.locator('#why-preferences').screenshot(path=str(args.output_dir / f'preferences-{width}.png'))
        # Touch pins the prompt, variants remain usable, and the dialog stays on screen.
        mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, reduced_motion='reduce')
        phone = mobile.new_page()
        phone.goto(args.url + '/#why-preferences', wait_until='networkidle')
        phone.locator('.calibration-prompt[data-domain="peptide"][data-method="positive_negative"]').tap()
        popup = phone.locator('#calibration-prompt-dialog')
        expect(popup).to_be_visible()
        popup.locator('[data-variant="opus"]').tap()
        expect(popup.locator('[data-variant="opus"]')).to_have_attribute('aria-pressed', 'true')
        rect = popup.bounding_box()
        assert 0 <= rect['x'] and rect['x'] + rect['width'] <= 390
        assert 0 <= rect['y'] and rect['y'] + rect['height'] <= 844
        popup.screenshot(path=str(args.output_dir / 'prompt-mobile.png'))
        popup.locator('.calibration-close').tap()
        expect(popup).not_to_be_visible()
        mobile.close()
        browser.close()
    assert not errors, errors
    assert not bad_requests, bad_requests
    print('Passed: all 2,592 points and 36 bars, exact prompts/variants, hover, keyboard, touch, linked legend and eight responsive widths.')


if __name__ == '__main__':
    main()

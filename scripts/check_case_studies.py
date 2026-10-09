#!/usr/bin/env python3
"""Check case-study navigation, source-derived summaries, and figure access."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8876')
    parser.add_argument('--output-dir', default='test-results/case-studies')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = json.loads((root / 'data/results.json').read_text())
    evidence = json.loads((root / 'data/result-panels.json').read_text())['oodEvidence']
    author_urls = [
        'https://www.riccardodesanti.com/', 'https://federicodigennaro.github.io/',
        'https://angelognazzo.github.io/', 'https://sophtang.github.io/',
        'https://www.chatterjeelab.com/', 'https://sml.inf.ethz.ch/group/fannyy/',
        'https://www.cs.ox.ac.uk/people/ismaililkan.ceylan/',
        'https://www.cs.ox.ac.uk/people/michael.bronstein/', 'https://las.inf.ethz.ch/krausea',
    ]
    errors, failures = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        for width in [390, 768, 1440]:
            page = browser.new_page(viewport={'width': width, 'height': 1000},
                                    has_touch=width == 390, reduced_motion='reduce')
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
            page.goto(args.url, wait_until='networkidle')
            page.evaluate('document.fonts.ready')
            assert page.locator('.author-row a').evaluate_all('(els)=>els.map(el=>el.href)') == author_urls
            assert page.locator('.author-row a,.institution').evaluate_all('(els)=>els.every(el=>el.target==="_blank" && el.rel.includes("noopener"))')
            logos = page.locator('.institution img')
            assert logos.count() == 6
            assert logos.evaluate_all('(els)=>els.every(el=>el.complete && el.naturalWidth>0 && el.alt.length>0)')
            for group, ids in [('peptides', ['anticancer', 'cpp']), ('molecules', ['d2', 'gsk3b', 'ood'])]:
                section = page.locator('#' + group)
                assert section.locator('[data-result-task]').evaluate_all('(els)=>els.map(el=>el.dataset.resultTask)') == ids
                assert section.locator('[data-open-result]').evaluate_all('(els)=>els.map(el=>el.dataset.openResult)') == ids
            # Summary values come from the same exact means and uncertainty terms as the full tables.
            for result in results:
                card = page.locator(f'[data-snapshot="{result["id"]}"]')
                for index, method in enumerate(['Pre-trained', 'LFD']):
                    mean, error = next(row for row in result['rows'] if row['method'] == method)['values'][0]
                    value = card.locator('.snapshot-value').nth(index)
                    unit = '%' if result['unit'] == '%' else ''
                    expect(value.locator('strong')).to_have_text(f'{mean:.2f}{unit}')
                    expect(value.locator('.snapshot-uncertainty')).to_have_text(f'± {error:.2f}')
            hit = page.locator('.discovery-snapshot')
            expect(hit).to_contain_text(f'0 / {evidence["pretrained"]["attempts"]:,}')
            expect(hit).to_contain_text(f'round {evidence["lfd"]["round"]}, {evidence["lfd"]["batchSize"]} samples')
            # Reduced motion pauses the overview; user playback remains available.
            video = page.locator('.hero-figure video')
            expect(video).to_have_js_property('paused', True)
            control = page.locator('#animation-toggle')
            expect(control).to_have_text('Play animation')
            control.click()
            expect(video).to_have_js_property('paused', False)
            expect(control).to_have_text('Pause animation')
            control.click()
            expect(video).to_have_js_property('paused', True)
            # Direct result links open the correct goal and skip no data in the comparison.
            for task in ['anticancer', 'cpp', 'd2', 'gsk3b', 'ood']:
                button = page.locator(f'[data-open-result="{task}"]')
                if width == 390:
                    button.tap()
                else:
                    button.focus()
                    page.keyboard.press('Enter')
                expect(page.locator(f'[data-result-task="{task}"]')).to_have_attribute('aria-expanded', 'true')
                expect(page.locator('#goal-results-content')).to_be_visible()
                expect(page.locator('#goal-results-toggle')).to_be_focused()
                page.wait_for_function('(task)=>document.querySelector("#task-results-panel").dataset.plotReadyTask===task', arg=task)
                assert page.locator('[data-result-task][aria-expanded="true"]').count() == 1
                if task != 'ood':
                    source = next(item for item in results if item['id'] == task)
                    assert page.locator('#results-table tbody tr').count() == len(source['rows'])
                else:
                    expect(page.locator('#result-discovery')).to_be_visible()
                if task in ['d2', 'gsk3b', 'ood']:
                    figure = page.locator('[data-zoom-figure]')
                    assert figure.count() == 1
                    figure.focus()
                    if width == 390:
                        figure.tap()
                    else:
                        page.keyboard.press('Enter')
                    viewer = page.locator('#figure-viewer')
                    expect(viewer).to_be_visible()
                    image = viewer.locator('img')
                    assert image.get_attribute('src').endswith(figure.get_attribute('href'))
                    assert image.get_attribute('alt') == figure.locator('img').get_attribute('alt')
                    page.wait_for_function('document.querySelector("#figure-viewer-image").naturalWidth > 0')
                    expect(page.locator('#close-figure-viewer')).to_be_focused()
                    bounds = viewer.bounding_box()
                    assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1
                    if task == 'gsk3b':
                        page.screenshot(path=str(out / f'figure-viewer-{width}.png'))
                    if width == 390:
                        page.locator('#close-figure-viewer').tap()
                    else:
                        page.keyboard.press('Escape')
                    expect(viewer).to_be_hidden()
                    expect(figure).to_be_focused()
                    assert not page.locator('body').evaluate('(el)=>el.classList.contains("figure-viewer-open")')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, task)
            # Summary metric help is usable before opening any goal.
            page.goto(args.url, wait_until='networkidle')
            label = page.locator('[data-snapshot="anticancer"] [data-metric]')
            label.scroll_into_view_if_needed()
            page.wait_for_timeout(100)
            label.click()
            expect(page.locator('#metric-help-popover')).to_be_visible()
            page.keyboard.press('Escape')
            page.evaluate('window.scrollTo(0, 0)')
            page.screenshot(path=str(out / f'overview-{width}.png'))
            page.locator('#peptides').evaluate('(el)=>el.scrollIntoView({block:"start"})')
            page.screenshot(path=str(out / f'peptides-{width}.png'))
            assert page.locator('.result-snapshot').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth+1)')
            page.close()
        browser.close()
    assert not errors, errors
    assert not failures, failures
    report = {'status': 'passed', 'author_links': 9, 'institution_logos': 6,
              'case_studies': 2, 'source_derived_summaries': 5, 'direct_results': 'keyboard and touch',
              'figure_viewer': '3 figures, keyboard and touch, focus restoration',
              'reduced_motion_and_playback': 'passed', 'viewports': [390, 768, 1440],
              'browser_errors': errors, 'failed_requests': failures}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

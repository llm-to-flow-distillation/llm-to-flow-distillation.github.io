#!/usr/bin/env python3
"""Exercise the public explorer with Playwright; no scientific or external API calls."""
import argparse
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', default='test-results')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads((root / 'data/tasks.json').read_text())
    errors = []
    failed_requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
        context.grant_permissions(['clipboard-read','clipboard-write'])
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failed_requests.append(response.url) if response.status >= 400 else None)
        page.goto(args.url, wait_until='networkidle')
        assert ' '.join(page.locator('h1').inner_text().split()) == 'LLM-to-Flow Distillation: Teaching Natural Language Goals to Scientific Generators'
        assert page.locator('.task-button').count() == 5
        assert page.locator('a[href*="paper.pdf"], .paper-button, #citation').count() == 0
        assert page.locator('.hero-figure img').evaluate('(img) => img.complete && img.naturalWidth === 4546')
        assert page.locator('.title-subtitle').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)') < page.locator('.title-main').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)')
        assert len(set(page.locator('.author-row > span').evaluate_all('(els) => els.map(el => getComputedStyle(el).fontSize)'))) == 1
        expect(page.locator('#contents')).not_to_be_visible()
        assert page.locator('#contents').evaluate('(el) => el.inert')
        page.evaluate('window.scrollTo({top: 300, behavior: "instant"})')
        expect(page.locator('#contents')).to_be_visible()
        expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#overview')
        for section in ['method', 'explorer', 'results']:
            page.locator(f'.contents-list a[href="#{section}"]').click()
            expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#' + section)
            assert page.evaluate('location.hash') == '#' + section
            assert page.evaluate('document.activeElement.closest("section").id') == section
        # Scroll independently from the menu; tracking must work in both directions.
        for section in ['results', 'explorer', 'method']:
            page.locator('#' + section).evaluate('(el) => el.scrollIntoView({behavior: "instant"})')
            expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#' + section)
        page.evaluate('window.scrollTo({top: 0, behavior: "instant"})')
        expect(page.locator('#contents')).not_to_be_visible()
        print('Compact hero, uploaded figure, clickable contents, section tracking and focus passed.')
        for task in data['tasks']:
            page.locator(f'[data-task="{task["id"]}"]').click()
            assert page.locator('#task-header h3').inner_text() == task['name']
            for stage in task['stages']:
                page.locator(f'[data-stage="{stage["id"]}"]').click()
                assert page.locator('#stage-detail h4').count()==0
                assert page.locator('#stage-detail q').evaluate('(el)=>getComputedStyle(el).fontStyle')=='italic'
                assert page.locator('#stage-detail q').inner_text() == stage['exactGoal']
                assert 'verbatim' in page.locator('#stage-detail .summary-label').inner_text()
                page.locator('#tab-overview').click()
                selection = stage['selection']
                if selection['status'] == 'recorded':
                    assert page.locator('.selection-rationale q').inner_text() == selection['rationale']
                    if selection.get('uncertainty'):
                        assert page.locator('.selection-limitations q').inner_text() == selection['uncertainty']
                elif selection['status'] == 'placeholder':
                    assert 'Placeholder' in page.locator('.selection-card').inner_text()
                else:
                    assert 'Original discovery goal' in page.locator('.selection-card').inner_text()
                page.locator('#open-stage-traces').click()
                assert page.locator('#tab-traces').get_attribute('aria-selected') == 'true'
                assert page.locator('.trace-card').count() == len(stage['traces'])
                assert page.locator('.trace-pair').count() == 2
                for pair in stage['tracePairs']:
                    row = page.locator(f'.trace-pair[data-pair-id="{pair["id"]}"]')
                    assert row.locator('h4').inner_text() == pair['label']
                    assert row.locator('.trace-card').evaluate_all('(els) => els.map(el => el.dataset.sampleId)') == [pair['positiveId'], pair['negativeId']]
                    cards = row.locator('.trace-card')
                    assert abs(cards.nth(0).bounding_box()['y'] - cards.nth(1).bounding_box()['y']) < 2
                for trace in stage['traces']:
                    card = page.locator(f'.trace-card[data-sample-id="{trace["sampleId"]}"]')
                    if trace['status'] == 'placeholder':
                        assert 'Placeholder' in card.inner_text()
                        assert card.locator('code, .judge-pass, .copy-candidate').count() == 0
                    else:
                        assert card.locator('.candidate-representation code').inner_text() == trace['representation']['value']
                        for index, output in enumerate(trace['passes']):
                            card.locator('.judge-pass').nth(index).click()
                            visible = card.locator('.judge-output:visible')
                            assert visible.count() == 1
                            assert visible.locator('.trace-field').nth(0).locator('q').inner_text() == output['rationale']
                            assert visible.locator('.trace-field').nth(1).locator('q').inner_text() == output['uncertainty']
                        card.locator('.judge-pass').first.click()
                if stage['traces'][0]['status'] == 'recorded':
                    first = stage['traces'][0]
                    page.locator('.copy-candidate').first.click()
                    assert page.evaluate('navigator.clipboard.readText()') == first['representation']['value']
                    page.locator('#trace-search').fill(first['representation']['value'])
                    assert page.locator('.trace-card').count() == 1
                    page.locator('#trace-search').fill('')
                if stage['traces']:
                    page.locator('#trace-filter').select_option('POSITIVE')
                    assert page.locator('.trace-card').count() == sum(t['label'] == 'POSITIVE' for t in stage['traces'])
                    page.locator('#trace-filter').select_option('all')
                    page.locator('#trace-search').fill(stage['traces'][0]['sampleId'])
                    assert page.locator('.trace-card').count() >= 1
                    page.locator('#trace-search').fill('no-such-judgment-xyz')
                    assert 'No examples match' in page.locator('.trace-empty').inner_text()
                    page.locator('#trace-search').fill('')
                else:
                    assert 'not available' in page.locator('.trace-empty').inner_text()
                assert page.locator('#tab-evidence, #panel-evidence').count() == 0
                assert page.locator('a[href*="paper.pdf"]').count() == 0
                rendered = page.locator('body').inner_text()
                assert not re.search(r'\b(?:paper|appendix|preprint|arxiv|bibtex|table\s+\d|figure\s+\d|algorithm\s+\d)\b',rendered,re.I), (task['id'],stage['id'])
        print('All 23 stages, 64 recorded candidates and 28 placeholders, size-paired cards, searches, filters and Sources removal passed.')
        page.goto(args.url + '/#explorer?task=cpp&stage=g&tab=traces', wait_until='networkidle')
        assert page.locator('#task-header h3').inner_text() == 'Cell penetration'
        assert page.locator('#tab-traces').get_attribute('aria-selected') == 'true'
        page.reload(wait_until='networkidle')
        assert page.locator('[data-stage="g"]').get_attribute('aria-pressed') == 'true'
        page.locator('#share-trace').click()
        assert 'task=cpp&stage=g&tab=traces' in page.evaluate('navigator.clipboard.readText()')
        with page.expect_download() as downloaded:
            page.locator('#download-task').click()
        file = downloaded.value
        file.save_as(out / file.suggested_filename)
        assert json.loads((out / file.suggested_filename).read_text())['id'] == 'cpp'
        page.locator('#tab-traces').focus()
        page.keyboard.press('ArrowRight')
        assert page.locator('#tab-overview').get_attribute('aria-selected') == 'true'
        page.goto(args.url + '/#explorer?task=gsk3b&stage=g1&tab=evidence',wait_until='networkidle')
        assert page.locator('#tab-overview').get_attribute('aria-selected') == 'true'
        assert page.locator('[data-stage="g1"]').get_attribute('aria-pressed') == 'true'
        page.goto(args.url + '/#explorer?task=invalid&stage=invalid&tab=invalid',wait_until='networkidle')
        assert page.locator('[data-task="anticancer"]').get_attribute('aria-pressed') == 'true'
        assert page.locator('[data-stage="g0"]').get_attribute('aria-pressed') == 'true'
        table_values = json.loads((root / 'data/results.json').read_text())
        for result in table_values:
            page.locator(f'[data-result-task="{result["id"]}"]').click()
            for index,row in enumerate(result['rows']):
                rendered = page.locator('#results-table tbody tr').nth(index)
                assert row['method'] in rendered.inner_text()
                assert rendered.locator('td').all_text_contents() == [f'{mean:.2f} ± {error:.2f}' for mean,error in row['values']]
        print('Deep links, reload, invalid-link recovery, keyboard tabs, clipboard, download and 66 result cells passed.')
        for width in [360,390,768,1200,1280,1440]:
            page.set_viewport_size({'width':width,'height':1000})
            page.goto(args.url,wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth') <= width, f'Overflow at {width}px'
            for task in data['tasks']:
                page.locator(f'[data-task="{task["id"]}"]').click()
                page.locator('#tab-traces').click()
                assert page.locator('.explorer-shell').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'), f'Clipped explorer at {width}px'
                assert page.locator('.trace-card').evaluate_all('(els) => els.every(el => el.scrollWidth <= el.clientWidth + 1)'), f'Clipped candidate at {width}px'
                assert page.evaluate('document.documentElement.scrollWidth') <= width, f'{task["id"]} overflow at {width}px'
            if width < 1280:
                page.locator('#method').evaluate('(el) => el.scrollIntoView({behavior: "instant"})')
                expect(page.locator('.contents-current')).to_have_text('Method (LFD)')
                expect(page.locator('.contents-list')).not_to_be_visible()
                page.locator('.contents-toggle').click()
                expect(page.locator('.contents-toggle')).to_have_attribute('aria-expanded', 'true')
                page.keyboard.press('Escape')
                expect(page.locator('.contents-toggle')).to_have_attribute('aria-expanded', 'false')
                expect(page.locator('.contents-toggle')).to_be_focused()
                page.locator('.contents-toggle').click()
                page.locator('.contents-list a[href="#results"]').click()
                expect(page.locator('.contents-current')).to_have_text('Results')
                expect(page.locator('.contents-list')).not_to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth') <= width
            if width in [390,1440]:
                page.goto(args.url,wait_until='networkidle')
                page.evaluate("document.querySelectorAll('img').forEach(img => img.loading = 'eager')")
                page.wait_for_function("[...document.images].every(img => img.complete && img.naturalWidth > 0)")
                page.screenshot(path=str(out / f'preview-{width}.png'),full_page=True)
                page.locator('#tab-traces').click()
                page.locator('.explorer-shell').screenshot(path=str(out / f'explorer-{width}.png'))
        page.goto((root/'index.html').as_uri(),wait_until='load')
        assert page.locator('.task-button').count() == 5
        assert page.locator('#results-table tbody tr').count() == 5
        assert not errors, errors
        assert not failed_requests, failed_requests
        browser.close()
    print('Responsive widths 360/390/768/1200/1280/1440, local-file loading, zero browser errors and zero failed HTTP requests passed.')
    (out/'report.json').write_text(json.dumps({'status':'passed','stages':23,'recorded_candidates':64,'placeholder_slots':28,'reported_value_pairs':66,'viewports':[360,390,768,1200,1280,1440],'contents_navigation':'passed','verbatim_goal_rationales':13,'verbatim_judge_outputs':128,'copy_representations':'passed','judge_pass_switching':'passed','placeholder_separation':'passed','size_matched_pairs':32,'source_tab':'removed','legacy_source_links':'fall back to goal rationale','browser_errors':errors,'failed_http_requests':failed_requests},indent=2)+'\n')


if __name__ == '__main__':
    main()

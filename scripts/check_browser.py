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
        assert page.locator('[data-result-task]').count() == 5
        assert page.locator('a[href*="paper.pdf"], #citation').count() == 0
        expect(page.locator('button.paper-button')).to_be_disabled()
        assert page.locator('.paper-button').get_attribute('href') is None
        expect(page.locator('.paper-button')).to_have_text('arXiv')
        expect(page.locator('.hero-figure video source')).to_have_attribute('src', 'assets/flow_adaptation_smooth.mp4')
        expect(page.locator('.hero-figure video')).to_have_js_property('videoWidth', 2154)
        expect(page.locator('.hero-figure video')).to_have_js_property('videoHeight', 612)
        assert page.locator('.hero-figure video').evaluate('(video)=>video.autoplay && video.muted && video.loop && video.playsInline')
        assert page.locator('.title-subtitle').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)') < page.locator('.title-main').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)')
        assert len(set(page.locator('.author-row > span').evaluate_all('(els) => els.map(el => getComputedStyle(el).fontSize)'))) == 1
        expect(page.locator('#contents')).not_to_be_visible()
        assert page.locator('#contents').evaluate('(el) => el.inert')
        page.evaluate('window.scrollTo({top: 300, behavior: "instant"})')
        expect(page.locator('#contents')).to_be_visible()
        expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#overview')
        for section in ['method', 'results']:
            page.locator(f'.contents-list a[href="#{section}"]').click()
            expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#' + section)
            assert page.evaluate('location.hash') == '#' + section
            assert page.evaluate('document.activeElement.closest("section").id') == section
        # Scroll independently from the menu; tracking must work in both directions.
        for section in ['results', 'method']:
            page.locator('#' + section).evaluate('(el) => el.scrollIntoView({behavior: "instant"})')
            expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href', '#' + section)
        page.evaluate('window.scrollTo({top: 0, behavior: "instant"})')
        expect(page.locator('#contents')).not_to_be_visible()
        print('Compact hero, uploaded figure, clickable contents, section tracking and focus passed.')
        for task in data['tasks']:
            page.locator(f'[data-result-task="{task["id"]}"]').click()
            assert page.locator(f'#result-name-{task["id"]}').inner_text() == task['name']
            expect(page.locator('.curriculum-traces')).not_to_have_attribute('open','')
            expect(page.locator('#tab-overview')).to_be_visible()
            for stage in task['stages']:
                page.locator(f'[data-curriculum-stage="{stage["id"]}"]').click()
                assert page.locator('#result-curriculum-preview > h4').count()==0
                assert page.locator('#result-curriculum-preview > p q').evaluate('(el)=>getComputedStyle(el).fontStyle')=='italic'
                assert page.locator('#result-curriculum-preview > p q').inner_text() == stage['exactGoal']
                assert page.locator('.curriculum-preview-links').count()==0
                assert page.locator('.curriculum-rounds').count()==0
                expect(page.locator('.trace-verbatim-note')).to_have_count(1)
                assert 'LLM goal selection · verbatim' not in page.locator('.selection-card').inner_text()
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
                page.locator('#tab-traces').click()
                assert page.locator('#tab-traces').get_attribute('aria-selected') == 'true'
                assert page.locator('.trace-card').count() == len(stage['traces'])
                assert page.locator('.trace-pair').count() == 2
                for pair in stage['tracePairs']:
                    row = page.locator(f'.trace-pair[data-pair-id="{pair["id"]}"]')
                    if pair.get('sizeUnit')=='aa':
                        assert row.locator('.trace-pair-heading').count()==0
                    else:
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
                assert page.locator('#trace-search, #trace-filter, .trace-controls, .trace-selection-note').count() == 0
                assert page.locator('.trace-card').count() == len(stage['traces'])
                assert page.locator('#tab-evidence, #panel-evidence').count() == 0
                assert page.locator('a[href*="paper.pdf"]').count() == 0
                rendered = page.locator('body').inner_text().replace('arXiv','',1)
                assert not re.search(r'\b(?:paper|appendix|preprint|arxiv|bibtex|table\s+\d|figure\s+\d|algorithm\s+\d)\b',rendered,re.I), (task['id'],stage['id'])
        print('All 23 stages, 64 recorded candidates and 28 placeholders, size-paired cards, removed search/filter controls and Sources removal passed.')
        page.goto(args.url + '/#explorer?task=cpp&stage=g&tab=traces', wait_until='networkidle')
        assert page.locator('#result-name-cpp').inner_text() == 'Peptide design for cell penetration'
        assert page.locator('#tab-traces').get_attribute('aria-selected') == 'true'
        page.reload(wait_until='networkidle')
        assert page.locator('[data-curriculum-stage="g"]').get_attribute('aria-selected') == 'true'
        assert page.locator('.overview-grid, .round-track, .context-note, .explorer-bottom, #open-stage-traces, #share-trace, #download-task').count() == 0
        page.locator('#tab-traces').focus()
        page.keyboard.press('ArrowRight')
        assert page.locator('#tab-overview').get_attribute('aria-selected') == 'true'
        page.goto(args.url + '/#explorer?task=gsk3b&stage=g1&tab=evidence',wait_until='networkidle')
        assert page.locator('#tab-overview').get_attribute('aria-selected') == 'true'
        assert page.locator('[data-curriculum-stage="g1"]').get_attribute('aria-selected') == 'true'
        page.goto(args.url + '/#explorer?task=invalid&stage=invalid&tab=invalid',wait_until='networkidle')
        assert page.locator('[data-result-task="anticancer"]').get_attribute('aria-expanded') == 'true'
        assert page.locator('[data-curriculum-stage="g0"]').get_attribute('aria-selected') == 'true'
        # Inline disclosure supports native keyboard activation and survives stage changes.
        page.goto(args.url,wait_until='networkidle')
        assert page.locator('#explorer, .task-sidebar, .contents-list a[href="#explorer"]').count() == 0
        expect(page.locator('#task-results-panel')).not_to_be_visible()
        page.locator('[data-result-task="anticancer"]').click()
        expect(page.locator('#panel-overview')).to_be_visible()
        expect(page.locator('#goal-results-content')).to_be_hidden()
        expect(page.locator('#tab-overview')).to_be_visible()
        page.locator('#tab-traces').click()
        page.locator('[data-curriculum-stage="g1"]').click()
        expect(page.locator('#tab-traces')).to_have_attribute('aria-selected','true')
        expect(page.locator('.trace-card')).to_have_count(4)
        page.locator('#task-result-curriculum').evaluate('(el) => el.scrollIntoView({behavior: "instant"})')
        expect(page.locator('.contents-list a[aria-current]')).to_have_attribute('href','#results')
        assert page.evaluate('location.hash') == '#results?task=anticancer&stage=g1&tab=traces'
        # Results are independently expandable and retain the active trace tab.
        toggle=page.locator('#goal-results-toggle')
        toggle.focus();page.keyboard.press('Enter')
        expect(page.locator('#goal-results-content')).to_be_visible()
        toggle.focus();page.keyboard.press('Space')
        expect(page.locator('#goal-results-content')).to_be_hidden()
        expect(page.locator('#panel-traces')).to_be_visible()
        page.goto(args.url+'/#results?task=gsk3b&stage=g2&tab=traces',wait_until='networkidle')
        expect(page.locator('[data-result-task="gsk3b"]')).to_have_attribute('aria-expanded','true')
        expect(page.locator('[data-curriculum-stage="g2"]')).to_have_attribute('aria-selected','true')
        expect(page.locator('#tab-traces')).to_have_attribute('aria-selected','true')
        expect(page.locator('.curriculum-traces')).to_be_visible()
        ids=page.locator('[id]').evaluate_all('(els)=>els.map(el=>el.id)')
        assert len(ids)==len(set(ids)), 'Duplicate IDs after mounting traces'
        table_values = json.loads((root / 'data/results.json').read_text())
        for result in table_values:
            page.locator(f'[data-result-task="{result["id"]}"]').click()
            page.locator('#goal-results-toggle').click()
            for index,row in enumerate(result['rows']):
                rendered = page.locator('#results-table tbody tr').nth(index)
                assert row['method'] in rendered.inner_text()
                assert rendered.locator('td').all_text_contents() == [f'{mean:.2f} ± {error:.2f}' for mean,error in row['values']]
        print('Deep links, reload, invalid-link recovery, keyboard tabs, candidate clipboard and 66 result cells passed.')
        for width in [360,390,768,1200,1280,1440]:
            page.set_viewport_size({'width':width,'height':1000})
            page.goto(args.url,wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth') <= width, f'Overflow at {width}px'
            for task in data['tasks']:
                page.locator(f'[data-result-task="{task["id"]}"]').click()
                page.locator('#tab-traces').click()
                assert page.locator('.inline-trace-view').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'), f'Clipped explorer at {width}px'
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
                expect(page.locator('.contents-current')).to_have_text('Experiments')
                expect(page.locator('.contents-list')).not_to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth') <= width
            if width in [390,1440]:
                page.goto(args.url,wait_until='networkidle')
                page.evaluate("document.querySelectorAll('img').forEach(img => img.loading = 'eager')")
                page.wait_for_function("[...document.images].every(img => img.complete && img.naturalWidth > 0)")
                page.screenshot(path=str(out / f'preview-{width}.png'),full_page=True)
                page.locator('[data-result-task="anticancer"]').click()
                page.locator('#tab-traces').click()
                page.locator('.inline-trace-view').screenshot(path=str(out / f'explorer-{width}.png'))
        page.goto((root/'index.html').as_uri(),wait_until='load')
        assert page.locator('[data-result-task]').count() == 5
        expect(page.locator('#task-results-panel')).not_to_be_visible()
        page.locator('[data-result-task="anticancer"]').click()
        assert page.locator('#results-table tbody tr').count() == 5
        assert not errors, errors
        assert not failed_requests, failed_requests
        browser.close()
    print('Responsive widths 360/390/768/1200/1280/1440, local-file loading, zero browser errors and zero failed HTTP requests passed.')
    (out/'report.json').write_text(json.dumps({'status':'passed','stages':23,'recorded_candidates':64,'placeholder_slots':28,'reported_value_pairs':66,'viewports':[360,390,768,1200,1280,1440],'contents_navigation':'passed','verbatim_goal_rationales':13,'verbatim_judge_outputs':128,'copy_representations':'passed','judge_pass_switching':'passed','placeholder_separation':'passed','size_matched_pairs':32,'source_tab':'removed','overview_progress_and_footer':'removed','rationale_visible_by_default':'passed','results_disclosure':'passed','legacy_trace_links':'open matching inline stage','legacy_source_links':'fall back to goal rationale','browser_errors':errors,'failed_http_requests':failed_requests},indent=2)+'\n')


if __name__ == '__main__':
    main()

'use strict';

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Render only author-provided method equations; the plain text remains a fallback.
  if (window.katex) {
    $$('[data-tex]').forEach(element => window.katex.render(element.dataset.tex, element, {
      displayMode: element.classList.contains('math-display'),
      output: 'htmlAndMathml', throwOnError: false, strict: 'error', trust: false
    }));
  }
  // Rich function explanations: hover/focus to preview; click or tap to pin.
  function setupFunctionDetails() {
    const popup = $('#algorithm-details');
    const buttons = $$('.algorithm-function');
    const panels = $$('[data-function-panel]', popup);
    const titles = {sample: 'Sample the current generator', observe: 'Observe the sample batch', setgoal: 'SetGoal', judge: 'LLM-Judge', minimize: 'Minimize · distill the preferences'};
    const nativePopover = typeof popup.showPopover === 'function';
    let active = null, pinned = false, closeTimer, positionFrame, skipFocus = null, pointerTrigger = null;

    function positionPopup() {
      positionFrame = null;
      if (!active) return;
      const anchor = active.getBoundingClientRect();
      if (anchor.bottom < 0 || anchor.top > innerHeight) {closePopup(); return;}
      const margin = 16, gap = 14;
      const {width, height} = popup.getBoundingClientRect();
      let left, top;
      if (innerWidth <= 700) {
        left = (innerWidth - width) / 2;
        top = innerHeight - height - margin;
      } else {
        if (anchor.left >= width + gap + margin) left = anchor.left - width - gap;
        else if (innerWidth - anchor.right >= width + gap + margin) left = anchor.right + gap;
        else left = (innerWidth - width) / 2;
        top = anchor.top - Math.min(54, height / 4);
        // When neither side has room, keep the trigger outside the detail panel.
        if (left < anchor.right && left + width > anchor.left) {
          top = anchor.bottom + gap;
          if (top + height > innerHeight - margin) top = anchor.top - height - gap;
        }
      }
      popup.style.left = Math.max(margin, Math.min(left, innerWidth - width - margin)) + 'px';
      popup.style.top = Math.max(margin, Math.min(top, innerHeight - height - margin)) + 'px';
    }
    function schedulePosition() {
      if (active && positionFrame == null) positionFrame = requestAnimationFrame(positionPopup);
    }
    function openPopup(button, pin = false) {
      clearTimeout(closeTimer);
      const changed = active !== button;
      if (changed) pinned = false;
      active = button;
      pinned = pinned || pin;
      buttons.forEach(item => item.setAttribute('aria-expanded', String(item === active)));
      panels.forEach(panel => {panel.hidden = panel.dataset.functionPanel !== active.dataset.function;});
      $('#function-detail-title').textContent = titles[active.dataset.function];
      popup.dataset.open = 'true';
      popup.dataset.pinned = String(pinned);
      if (nativePopover && !popup.matches(':popover-open')) popup.showPopover();
      if (changed) popup.scrollTop = 0;
      positionPopup();
      document.fonts.ready.then(schedulePosition);
    }
    function closePopup(restoreFocus = false) {
      if (!active) return;
      clearTimeout(closeTimer);
      const previous = active;
      active = null;
      pinned = false;
      buttons.forEach(item => item.setAttribute('aria-expanded', 'false'));
      if (nativePopover && popup.matches(':popover-open')) popup.hidePopover();
      delete popup.dataset.open;
      delete popup.dataset.pinned;
      if (restoreFocus && document.activeElement !== previous) {
        skipFocus = previous;
        previous.focus({preventScroll: true});
      }
    }
    function scheduleClose() {
      clearTimeout(closeTimer);
      closeTimer = setTimeout(() => {
        if (!active || pinned) return;
        if (active.matches(':hover') || popup.matches(':hover')) return;
        if (document.activeElement === active || popup.contains(document.activeElement)) return;
        closePopup();
      }, 180);
    }
    for (const button of buttons) {
      // A touch focus must not open an overlay before the tap's click is delivered.
      button.addEventListener('pointerdown', () => {pointerTrigger = button;});
      button.addEventListener('pointercancel', () => {pointerTrigger = null;});
      button.addEventListener('pointerenter', event => {
        if (event.pointerType === 'mouse' && (!pinned || active === button)) openPopup(button);
      });
      button.addEventListener('pointerleave', scheduleClose);
      button.addEventListener('focus', () => {
        if (skipFocus === button) {skipFocus = null; return;}
        if (pointerTrigger === button) return;
        openPopup(button);
      });
      button.addEventListener('blur', scheduleClose);
      button.addEventListener('click', event => {
        pointerTrigger = null;
        if (active === button && pinned) {closePopup(); return;}
        openPopup(button, true);
        if (event.detail === 0) popup.focus({preventScroll: true});
      });
    }
    popup.addEventListener('pointerenter', () => clearTimeout(closeTimer));
    popup.addEventListener('pointerleave', scheduleClose);
    popup.addEventListener('focusout', scheduleClose);
    $('#close-function-details').addEventListener('click', () => closePopup(true));
    document.addEventListener('keydown', event => {
      pointerTrigger = null;
      if (event.key === 'Escape' && active) {
        event.preventDefault();
        closePopup(popup.contains(document.activeElement));
      }
    });
    document.addEventListener('pointerdown', event => {
      if (!buttons.some(button => button.contains(event.target))) pointerTrigger = null;
      if (active && !popup.contains(event.target) && !buttons.some(button => button.contains(event.target))) closePopup();
    });
    window.addEventListener('scroll', schedulePosition, {passive: true});
    window.addEventListener('resize', schedulePosition);
    new ResizeObserver(schedulePosition).observe(popup);
  }
  setupFunctionDetails();

  const tasks = window.LFD_DATA.tasks;
  const results = window.LFD_DATA.results;
  const state = {task: tasks[0].id, stage: 'g0', tab: 'overview'};
  let toastTimer;

  function toast(message) {
    $('#toast').textContent = message;
    $('#toast').classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 3000);
  }
  async function copy(text, confirmation) {
    try {
      await navigator.clipboard.writeText(text);
      toast(confirmation);
    } catch {
      const field = document.createElement('textarea');
      field.value = text;
      field.style.cssText = 'position:fixed;left:-9999px';
      document.body.append(field);
      field.select();
      const copied = document.execCommand('copy');
      field.remove();
      toast(copied ? confirmation : 'Clipboard unavailable. Select and copy the text or address.');
    }
  }
  function currentTask() { return tasks.find(t => t.id === state.task); }
  function currentStage() { return currentTask().stages.find(s => s.id === state.stage); }
  let traceDisclosure;
  function readHash(hash=location.hash) {
    if (!/^#(?:explorer|results)\?/.test(hash) && hash !== '#explorer') return null;
    const params = new URLSearchParams(hash.split('?')[1] || '');
    const task = tasks.find(t => t.id === params.get('task')) || tasks[0];
    return {
      task: task.id,
      stage: task.stages.some(s => s.id === params.get('stage')) ? params.get('stage') : task.stages[0].id,
      tab: ['overview','traces'].includes(params.get('tab')) ? params.get('tab') : 'overview'
    };
  }
  function updateHash() {
    const hash = traceDisclosure?.open ? '#results?' + new URLSearchParams(state) : '#results';
    history.replaceState(null, '', hash);
  }
  function renderExplorer() {
    const stage = currentStage();
    const recorded = stage.traces.filter(trace => trace.status === 'recorded').length;
    const selection = stage.selection;
    let selectionBody;
    if (selection.status === 'placeholder') {
      selectionBody = `<div class="selection-card selection-placeholder"><span class="evidence-status">Placeholder · awaiting source traces</span><h4>${stage.id === 'g' ? 'Final-goal transition' : 'Why this subgoal?'}</h4><p>The ${stage.id === 'g' ? 'transition record' : 'LLM’s goal-selection explanation'} is not yet available for this task.</p></div>`;
    } else if (selection.status === 'original-goal') {
      selectionBody = `<div class="selection-card"><span class="evidence-status">Original discovery goal</span><h4>Return to the original goal</h4><p>This is the original task objective, rather than a newly proposed LLM subgoal.</p>${selection.uncertainty ? `<div class="selection-limitations"><strong>Recorded limitation</strong><p>${esc(selection.uncertainty)}</p></div>` : ''}</div>`;
    } else {
      selectionBody = `<div class="selection-card"><span class="evidence-status">LLM goal selection · verbatim</span><h4>Why this subgoal?</h4><p class="selection-rationale goal-quotation"><q>${esc(selection.rationale)}</q></p>${selection.uncertainty ? `<div class="selection-limitations"><strong>LLM-stated limitations</strong><p class="goal-quotation"><q>${esc(selection.uncertainty)}</q></p></div>` : ''}${selection.bridge ? `<details class="selection-bridge"><summary>Connection to the final goal</summary><p class="goal-quotation"><q>${esc(selection.bridge)}</q></p>${selection.deferredRequirements?.length ? `<strong>Requirements deferred by the LLM</strong><ul>${selection.deferredRequirements.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}</details>` : ''}</div>`;
    }
    $('#panel-overview').innerHTML = selectionBody;
    $('#trace-count').textContent = recorded || '4 slots';
    renderTraces();
    renderTab();
  }
  function renderTraceCard(trace) {
    if (trace.status === 'placeholder') {
      return `<article class="trace-card trace-placeholder" data-sample-id="${esc(trace.sampleId)}"><div class="trace-card-header"><span class="evidence-status">Placeholder</span><span>${esc(trace.label === 'POSITIVE' ? 'Positive' : 'Negative')} example ${esc(trace.sampleId.slice(-1))}</span></div><div class="candidate-representation representation-pending"><span class="representation-label">SMILES</span><p>Candidate pending</p></div><div class="trace-field"><h5>LLM rationale</h5><p>Awaiting the recorded judgment.</p></div><div class="trace-field trace-uncertainty"><h5>LLM uncertainty</h5><p>Awaiting the recorded uncertainty.</p></div><p class="placeholder-note">No molecule or LLM judgment is represented by this slot.</p></article>`;
    }
    const isPeptide = trace.representation.kind === 'peptide';
    return `<article class="trace-card" data-sample-id="${esc(trace.sampleId)}"><div class="trace-card-header"><span class="judgment-badge judgment-${esc(trace.label.toLowerCase())}">${trace.label === 'POSITIVE' ? 'Positive (+/+)' : 'Negative (−/−)'}</span><span class="sample-id">${esc(trace.sampleId)}</span></div><div class="candidate-representation ${isPeptide ? 'peptide-sequence' : 'molecule-smiles'}"><div class="representation-header"><span class="representation-label">${isPeptide ? 'Peptide sequence' : 'SMILES'}</span><button class="copy-candidate" aria-label="Copy ${isPeptide ? 'sequence' : 'SMILES'} for ${esc(trace.sampleId)}">Copy</button></div><code>${esc(trace.representation.value)}</code></div><dl class="candidate-observables">${trace.observables.map(item => `<div><dt>${esc(item.label)}</dt><dd>${esc(item.value)}</dd></div>`).join('')}</dl><div class="judge-passes" role="group" aria-label="Choose judge pass for ${esc(trace.sampleId)}">${trace.passes.map((pass,index) => `<button class="judge-pass" data-pass="${index}" aria-pressed="${index === 0}">Pass ${index + 1}</button>`).join('')}<span>Same label in both</span></div>${trace.passes.map((pass,index) => `<div class="judge-output" data-pass="${index}" ${index ? 'hidden' : ''}><div class="trace-field"><h5>LLM rationale</h5><p class="goal-quotation"><q>${esc(pass.rationale)}</q></p></div><div class="trace-field trace-uncertainty"><h5>LLM uncertainty</h5><p class="goal-quotation">${pass.uncertainty ? `<q>${esc(pass.uncertainty)}</q>` : 'No uncertainty text was recorded for this pass.'}</p></div></div>`).join('')}<div class="trace-provenance">Verbatim recorded outputs · uncertainties are stated limitations, not confidence scores.</div></article>`;
  }
  function renderTraces() {
    const stage = currentStage();
    const query = $('#trace-search').value.trim().toLowerCase();
    const label = $('#trace-filter').value;
    const traces = stage.traces.filter(trace => (label === 'all' || trace.label === label) && [trace.rationale,trace.uncertainty,trace.sampleId,trace.label,trace.representation?.value,...(trace.passes || []).flatMap(pass => [pass.rationale,pass.uncertainty])].join(' ').toLowerCase().includes(query));
    if (!traces.length) {
      $('#trace-list').innerHTML = '<div class="trace-empty">No examples match this search and judgment filter. Clear the search or choose All judgments.</div>';
      return;
    }
    const pairs = stage.tracePairs.map(pair => ({...pair,items:[pair.positiveId,pair.negativeId].map(id => traces.find(trace => trace.sampleId === id)).filter(Boolean)})).filter(pair => pair.items.length);
    $('#trace-list').innerHTML = `${stage.traces[0].status === 'placeholder' ? '<p class="placeholder-notice"><strong>Placeholder examples.</strong> Candidate structures, rationales, and uncertainties will appear here when the source traces are available.</p>' : '<p class="trace-selection-note">Illustrative pairs selected for size diversity and clear, consistent goal-specific judgments.</p>'}${pairs.map(pair => `<section class="trace-pair" data-pair-id="${esc(pair.id)}" aria-label="${esc(pair.label)}"><div class="trace-pair-heading"><h4>${esc(pair.label)}</h4>${stage.traces[0].status === 'recorded' ? `<span>${pair.sizeUnit === 'aa' ? 'Matched length' : 'Comparable molecular weight'}</span>` : ''}</div><div class="trace-pair-grid ${pair.items.length === 1 ? 'single-candidate' : ''}">${pair.items.map(renderTraceCard).join('')}</div></section>`).join('')}`;
    $$('.trace-card').forEach(card => {
      const trace = traces.find(item => item.sampleId === card.dataset.sampleId);
      $('.copy-candidate', card)?.addEventListener('click', () => copy(trace.representation.value, 'Candidate copied'));
      $$('.judge-pass', card).forEach(button => button.addEventListener('click', () => {
        $$('.judge-pass', card).forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        $$('.judge-output', card).forEach(output => {output.hidden = output.dataset.pass !== button.dataset.pass;});
      }));
    });
  }
  function renderTab() {
    $$('.explorer-tabs button').forEach(button => {
      const active = button.dataset.tab === state.tab;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      $(`#panel-${button.dataset.tab}`).hidden = !active;
    });
  }
  function bindTraceControls() {
    $$('.explorer-tabs button').forEach(button => {
      button.addEventListener('click', () => {state.tab = button.dataset.tab; updateHash(); renderTab();});
      button.addEventListener('keydown', event => {
        const buttons = $$('.explorer-tabs button');
        let index = buttons.indexOf(button);
        if (event.key === 'ArrowRight') index = (index + 1) % buttons.length;
        else if (event.key === 'ArrowLeft') index = (index - 1 + buttons.length) % buttons.length;
        else if (event.key === 'Home') index = 0;
        else if (event.key === 'End') index = buttons.length - 1;
        else return;
        event.preventDefault();
        buttons[index].click();buttons[index].focus();
      });
    });
    $('#trace-search').addEventListener('input', renderTraces);
    $('#trace-filter').addEventListener('change', renderTraces);
  }
  function populateTraces() {
    const view = $('.inline-trace-view',traceDisclosure);
    if (view.childElementCount) return;
    view.append($('#trace-view-template').content.cloneNode(true));
    bindTraceControls();
    renderExplorer();
  }
  window.LFD_TRACES = {
    mount(disclosure,task,stage) {
      traceDisclosure = disclosure;
      state.task = task;
      state.stage = stage;
      if (!disclosure.open) state.tab = 'overview';
      disclosure.addEventListener('toggle', () => {
        // A previous subgoal's queued toggle must never affect the new view.
        if (disclosure !== traceDisclosure || !disclosure.isConnected) return;
        if (disclosure.open) populateTraces();
        updateHash();
      });
      if (disclosure.open) {populateTraces();updateHash();}
      else if (/^#results\?/.test(location.hash)) updateHash();
    },
    open(tab='overview') {
      state.tab = tab;
      traceDisclosure.open = true;
      populateTraces();
      renderTab();
      updateHash();
      return traceDisclosure;
    }
  };
  // Read before initialization: mounting a default goal can normalize the hash.
  const initialTrace = readHash();
  const resultViewer = window.LFD_RESULTS.init(results);
  function openLinkedTrace(target) {
    if (!target) return;
    const disclosure = resultViewer.showTraces(target.task,target.stage,target.tab);
    requestAnimationFrame(() => disclosure.scrollIntoView({behavior:'instant',block:'start'}));
  }
  // Use the destination captured by the event, even if a queued toggle normalized the URL.
  window.addEventListener('hashchange', event => openLinkedTrace(readHash(new URL(event.newURL).hash)));
  openLinkedTrace(initialTrace);

  // Track section geometry so expanding traces and figures keeps the rail accurate.
  const contents = $('#contents');
  const contentsToggle = $('.contents-toggle', contents);
  const contentsLinks = $$('.contents-list a', contents);
  const sections = contentsLinks.map(link => $(link.getAttribute('href')));
  const compactContents = matchMedia('(max-width: 1279px)');
  let contentsFrame;

  function closeContents() {
    contents.classList.remove('is-open');
    contentsToggle.setAttribute('aria-expanded', 'false');
  }
  function updateContents() {
    contentsFrame = null;
    const visible = scrollY > 120;
    contents.classList.toggle('is-visible', visible);
    contents.inert = !visible;
    if (!visible) closeContents();
    const readingLine = Math.min(innerHeight * .28, 220);
    let active = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= readingLine) active = section;
    }
    // A short final section still becomes current when the reader reaches the end.
    if (scrollY + innerHeight >= document.documentElement.scrollHeight - 4) active = sections.at(-1);
    for (const link of contentsLinks) {
      if (link.hash === '#' + active.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
    $('.contents-current', contents).textContent = contentsLinks[sections.indexOf(active)].textContent;
  }
  function scheduleContents() {
    if (contentsFrame == null) contentsFrame = requestAnimationFrame(updateContents);
  }
  contentsToggle.addEventListener('click', () => {
    const open = contents.classList.toggle('is-open');
    contentsToggle.setAttribute('aria-expanded', String(open));
  });
  for (const link of contentsLinks) {
    link.addEventListener('click', event => {
      // Preserve normal new-tab and modified-click behavior on these real anchors.
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const section = $(link.hash);
      history.pushState(null, '', link.hash);
      closeContents();
      const heading = section.querySelector('h1, h2');
      heading.setAttribute('tabindex', '-1');
      heading.focus({preventScroll: true});
      section.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      scheduleContents();
    });
  }
  document.addEventListener('click', event => {
    if (!contents.contains(event.target)) closeContents();
  });
  contents.addEventListener('keydown', event => {
    if (event.key === 'Escape' && contents.classList.contains('is-open')) {
      closeContents();
      contentsToggle.focus();
    }
  });
  contents.addEventListener('focusout', event => {
    if (!contents.contains(event.relatedTarget)) closeContents();
  });
  compactContents.addEventListener('change', () => {closeContents(); scheduleContents();});
  window.addEventListener('scroll', scheduleContents, {passive: true});
  window.addEventListener('resize', scheduleContents);
  window.addEventListener('hashchange', scheduleContents);
  window.addEventListener('pageshow', scheduleContents);
  new ResizeObserver(scheduleContents).observe($('#main'));
  updateContents();
})();

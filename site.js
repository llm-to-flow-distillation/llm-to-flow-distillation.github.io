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
  function stageLabel(stage) { return stage.id === 'g' ? (stage.rounds === 0 ? 'g · assess' : 'g · final') : 'g' + [...stage.id.slice(1)].map(n => '₀₁₂₃₄₅₆₇₈₉'[Number(n)]).join(''); }
  function readHash() {
    if (!location.hash.startsWith('#explorer?')) return false;
    const params = new URLSearchParams(location.hash.split('?')[1]);
    const task = tasks.find(t => t.id === params.get('task')) || tasks[0];
    state.task = task.id;
    state.stage = task.stages.some(s => s.id === params.get('stage')) ? params.get('stage') : task.stages[0].id;
    state.tab = ['overview','traces','evidence'].includes(params.get('tab')) ? params.get('tab') : 'overview';
    return true;
  }
  function updateHash() {
    const hash = '#explorer?' + new URLSearchParams({task:state.task,stage:state.stage,tab:state.tab});
    history.replaceState(null, '', hash);
  }
  function renderTasks() {
    let category = '';
    $('#task-list').innerHTML = tasks.map(task => {
      const label = category !== task.category ? `<div class="task-category">${esc(task.category.toUpperCase())}</div>` : '';
      category = task.category;
      return `${label}<button class="task-button" data-task="${esc(task.id)}" aria-pressed="${task.id === state.task}">${esc(task.name)}<small>${esc(task.generator)} · ${task.stages.length} stages</small></button>`;
    }).join('');
    $$('.task-button').forEach(button => button.addEventListener('click', () => {
      state.task = button.dataset.task;
      state.stage = currentTask().stages[0].id;
      $('#trace-search').value = '';
      $('#trace-filter').value = 'all';
      updateHash();
      renderExplorer();
      $(`.task-button[data-task="${state.task}"]`).focus({preventScroll:true});
    }));
  }
  function renderExplorer() {
    const task = currentTask();
    const stage = currentStage();
    renderTasks();
    $('#task-header').innerHTML = `<div class="task-header-line"><h3>${esc(task.name)}</h3><span class="generator-badge">${esc(task.generator)}</span></div><p class="task-goal">${esc(task.goal)}</p>`;
    $('#stage-count').textContent = `${task.stages.filter(s => s.rounds > 0).length} training stages · ${task.stages.reduce((sum,s) => sum + s.rounds,0)} updates`;
    $('#stage-list').innerHTML = task.stages.map(s => `<button class="stage-button" data-stage="${esc(s.id)}" aria-label="${esc(s.id === 'g' ? 'Final goal' : `Subgoal ${s.id.slice(1)}`)}: ${esc(s.title)}" aria-pressed="${s.id === stage.id}">${esc(stageLabel(s))}</button>`).join('');
    $$('.stage-button').forEach(button => button.addEventListener('click', () => {
      state.stage = button.dataset.stage;
      $('#trace-search').value = '';
      $('#trace-filter').value = 'all';
      updateHash();
      renderExplorer();
      $(`.stage-button[data-stage="${state.stage}"]`).focus({preventScroll:true});
    }));
    $('#stage-detail').innerHTML = `<div class="stage-title-line"><h4>${esc(stage.title)}</h4><span class="stage-rounds">${stage.rounds ? `${stage.rounds} update${stage.rounds === 1 ? '' : 's'}` : 'Assessment only'}</span></div><p class="stage-summary">${esc(stage.summary)}</p><span class="summary-label">${stage.exactGoal ? 'Subgoal summary · operative goal available below' : 'High-level summary of the reported goal'}</span>`;
    const total = task.stages.reduce((sum,s) => sum + s.rounds, 0);
    const index = task.stages.indexOf(stage);
    const start = task.stages.slice(0,index).reduce((sum,s) => sum + s.rounds,0);
    const bars = Array.from({length:total},(_,i) => `<span class="round-block ${i >= start && i < start + stage.rounds ? 'active' : ''}"></span>`).join('');
    $('#panel-overview').innerHTML = `<div class="overview-grid"><div><div class="panel-label">Place in the curriculum</div><div class="panel-description">${stage.rounds ? `Updates ${start + 1}${stage.rounds > 1 ? `–${start + stage.rounds}` : ''} of ${total} in the reported trajectory.` : 'Final-goal evaluation of samples from the third intermediate stage. No extra training update.'}</div><div class="round-track" role="img" aria-label="${stage.rounds} of ${total} training updates in this stage">${bars}</div><div class="round-track-label">Pretrained generator → reported checkpoint</div></div><div><div class="panel-label">Available judgments</div><div class="panel-description">${stage.traces.length ? `${stage.traces.length} illustrative recorded examples. Open Judge traces to inspect assessments and stated uncertainties.` : 'The curriculum is documented in the paper. Candidate-level judgments for this stage are not included in the available evidence.'}</div></div></div>${stage.exactGoal ? `<details><summary>Read the operative goal <span aria-hidden="true">+</span></summary><p class="panel-description">${esc(stage.exactGoal)}</p></details>` : ''}<p class="context-note">${esc(stage.context || task.shortCaveat)} These examples are selected illustrations, not an exhaustive trace archive.</p>`;
    $('#trace-count').textContent = stage.traces.length;
    $('#panel-evidence').innerHTML = `<div class="panel-label">Source lineage</div><p class="panel-description">${esc(task.lineage)}</p><div class="source-links">${stage.paperPages.map(page => `<a href="assets/paper.pdf#page=${page}" target="_blank" rel="noopener">Paper · page ${page} ↗</a>`).join('')}<a href="data/tasks.json" target="_blank" rel="noopener">Public evidence JSON ↗</a></div><div class="panel-label">Interpretation & selection context</div><ul class="caveat-list">${task.caveats.map(c => `<li>${esc(c)}</li>`).join('')}</ul><details><summary>Inspect this stage’s structured record <span aria-hidden="true">+</span></summary><pre class="evidence-json">${esc(JSON.stringify(stage,null,2))}</pre></details>`;
    renderTraces();
    renderTab();
  }
  function renderTraces() {
    const stage = currentStage();
    const query = $('#trace-search').value.trim().toLowerCase();
    const label = $('#trace-filter').value;
    const traces = stage.traces.filter(trace => (label === 'all' || trace.label === label) && [trace.rationale,trace.uncertainty,trace.sampleId,trace.label].join(' ').toLowerCase().includes(query));
    if (!stage.traces.length) {
      $('#trace-list').innerHTML = `<div class="trace-empty">This subgoal is documented in the paper, but its raw candidate judgments were not available in the local evidence archive. The explorer preserves that gap.<div class="source-links"><a href="assets/paper.pdf#page=${stage.paperPages[0]}" target="_blank" rel="noopener">Read the documented curriculum ↗</a></div></div>`;
    } else if (!traces.length) {
      $('#trace-list').innerHTML = '<div class="trace-empty">No examples match this search and judgment filter. Clear the search or choose All judgments.</div>';
    } else {
      $('#trace-list').innerHTML = traces.map(trace => `<article class="trace-card"><div class="trace-card-header"><span class="judgment-badge judgment-${esc(trace.label.toLowerCase())}">${esc(trace.label)}</span><span>${esc(trace.sampleId)}</span></div><p>${esc(trace.rationale)}</p><div class="trace-uncertainty"><strong>Still unknown</strong> · ${esc(trace.uncertainty)}</div><div class="trace-provenance">${trace.paraphrased ? 'Faithful high-level paraphrase' : 'Recorded excerpt'}${trace.agreement ? ' · ' + esc(trace.agreement) : ''}<br>Source: ${esc(trace.source)}${trace.sourceSha256 ? `<br>SHA-256: ${esc(trace.sourceSha256)}` : ''}</div></article>`).join('');
    }
  }
  function renderTab() {
    $$('.explorer-tabs button').forEach(button => {
      const active = button.dataset.tab === state.tab;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      $(`#panel-${button.dataset.tab}`).hidden = !active;
    });
  }
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
  $('#share-trace').addEventListener('click', () => {updateHash();copy(location.href,'Link to this view copied');});
  $('#download-task').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(currentTask(),null,2) + '\n'],{type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;link.download = `lfd-${state.task}-evidence.json`;
    document.body.append(link);link.click();link.remove();
    setTimeout(() => URL.revokeObjectURL(url),1000);
    toast('Task evidence downloaded');
  });
  $('#copy-citation').addEventListener('click', () => copy($('#citation-text').textContent,'BibTeX copied'));
  window.addEventListener('hashchange', () => {
    if (readHash()) {renderExplorer();$('#explorer').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});}
  });
  readHash();
  renderExplorer();
  if (location.hash.startsWith('#explorer?')) requestAnimationFrame(() => $('#explorer').scrollIntoView({behavior:'instant'}));

  // Reported table values; no computed scientific results are introduced here.
  $('#result-task').innerHTML = results.map(result => `<option value="${esc(result.id)}">${esc(result.name)}</option>`).join('');
  $('#result-cards').innerHTML = results.map(result => {
    const ours = result.rows.find(row => row.method === 'LFD').values[0][0];
    const base = result.rows[0].values[0][0];
    return `<article class="result-card"><span class="tiny-label">${esc(result.metricShort)}</span><h3>${esc(result.name)}</h3><div class="result-number">${ours.toFixed(2)}<small>${esc(result.unit)}</small></div><div class="result-baseline">${base.toFixed(2)} pretrained → ${ours.toFixed(2)} LFD</div><div class="result-bar" aria-hidden="true"><span style="width:${result.unit === '%' ? ours : ours / 8 * 100}%"></span></div></article>`;
  }).join('');
  function renderResults() {
    const result = results.find(r => r.id === $('#result-task').value);
    const best = result.metrics.map((metric,i) => (metric.direction === 'up' ? Math.max : Math.min)(...result.rows.map(row => row.values[i][0])));
    $('#results-table').innerHTML = `<caption class="sr-only">${esc(result.name)}, paper Table ${result.table}. Higher is better for up arrows, lower for down arrows.</caption><thead><tr><th scope="col">Method</th>${result.metrics.map(m => `<th scope="col">${esc(m.label)} ${m.direction === 'up' ? '↑' : '↓'}</th>`).join('')}</tr></thead><tbody>${result.rows.map(row => `<tr class="${row.method === 'LFD' ? 'ours' : ''}"><th scope="row">${esc(row.method === 'LFD' ? 'LFD · ours' : row.method)}</th>${row.values.map(([mean,error],i) => `<td class="${mean === best[i] ? 'best' : ''}">${mean.toFixed(2)} ± ${error.toFixed(2)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  }
  $('#result-task').addEventListener('change', renderResults);
  renderResults();

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

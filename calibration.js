'use strict';

// Figure 3: original joint-score differences and emitted-preference accuracy.
(() => {
  const data = window.LFD_DATA.calibration;
  const grid = document.querySelector('#calibration-grid');
  const legend = document.querySelector('#calibration-legend');
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const activeModels = new Set(data.models.map(m => m.id));
  const charts = [];
  const marker = model => `<span class="calibration-symbol ${model.symbol}" style="--model-color:${model.color}" aria-hidden="true"></span>`;
  const promptButton = (domain, method, text, extra = '') => `<button type="button" class="calibration-prompt ${extra}" data-domain="${domain.id}" ${method ? `data-method="${method}"` : ''} aria-haspopup="dialog" aria-controls="calibration-prompt-dialog" aria-expanded="false">${text}</button>`;

  grid.innerHTML = data.domains.map(domain => `<div class="calibration-domain" data-calibration-domain="${domain.id}">
    <div class="calibration-domain-heading">${promptButton(domain, null, esc(domain.label), 'calibration-task')}<span>${esc(domain.metric)}</span></div>
    <div class="calibration-score-panel">
      <div id="calibration-scatter-${domain.id}" class="calibration-plot calibration-scatter" tabindex="0" role="group" aria-label="${esc(domain.label)}: LLM-estimated versus true score differences. Arrow keys inspect points; Escape dismisses the value."></div>
      <div class="calibration-mae" aria-label="Mean absolute error"><span>MAE</span>${domain.series.map(series => {const model = data.models.find(m => m.id === series.model); return `<span data-mae-model="${model.id}" title="${esc(model.label)}: mean absolute error ${series.mae.toFixed(2)}">${marker(model)}${series.mae.toFixed(1)}</span>`;}).join('')}</div>
    </div>
    <div class="calibration-accuracy-panel">
      <div id="calibration-bars-${domain.id}" class="calibration-plot calibration-bars" tabindex="0" role="group" aria-label="${esc(domain.label)}: pairwise accuracy by elicitation method. Arrow keys inspect bars; Escape dismisses the value."></div>
      <div class="calibration-methods">${data.methods.map(method => promptButton(domain, method, esc(data.prompts.methods[method].label))).join('')}</div>
    </div>
  </div>`).join('');
  legend.innerHTML = data.models.map(model => `<button type="button" data-calibration-model="${model.id}" aria-pressed="true" aria-label="Show ${esc(model.label)}" style="--model-color:${model.color}"><span class="calibration-logo" style="--logo:url('${model.logo}')" aria-hidden="true"></span><span>${esc(model.label)}</span>${marker(model)}</button>`).join('');

  const live = document.createElement('div');
  live.className = 'sr-only';
  live.setAttribute('aria-live', 'polite');
  grid.after(live);
  const axis = {gridcolor: '#e5ebe8', zerolinecolor: '#ccd5d0', tickfont: {size: 10, color: '#68736d'}, fixedrange: true, ticks: '', automargin: false};
  function layout(kind) {
    const scatter = kind === 'scatter';
    return {
      autosize: true, height: scatter ? 244 : 216,
      margin: {l: 46, r: 12, t: 10, b: scatter ? 40 : 7},
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      font: {family: 'Inter, sans-serif', size: 11, color: '#35423b'},
      showlegend: false, hovermode: 'closest', dragmode: false,
      hoverlabel: {bgcolor: '#fff', bordercolor: '#a7b6ac', font: {family: 'Inter, sans-serif', size: 11}},
      xaxis: scatter ? {...axis, range: [-104, 104], tickvals: [-100, 0, 100], title: {text: 'True difference', font: {size: 11}, standoff: 8}} : {...axis, range: [-.5, 3.5], showticklabels: false, showgrid: false, zeroline: false},
      yaxis: {...axis, range: scatter ? [-104, 104] : [0, 109], tickvals: scatter ? [-100, 0, 100] : [0, 25, 50, 75, 100], title: {text: scatter ? 'LLM-estimated difference' : 'Pairwise accuracy (%)', font: {size: 11}, standoff: 5}},
      shapes: scatter ? [{type: 'line', x0: -100, x1: 100, y0: -100, y1: 100, line: {color: '#344a3e', width: 1.3, dash: 'dash'}}] : [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 50, y1: 50, line: {color: '#344a3e', width: 1.3, dash: 'dash'}}],
      annotations: scatter ? [{x: -78, y: -89, text: 'y = x', showarrow: false, font: {size: 10, color: '#344a3e'}, bgcolor: 'rgba(255,255,255,.85)'}] : [],
      barmode: 'group', bargap: .24, bargroupgap: .05
    };
  }
  async function render() {
    for (const domain of data.domains) {
      for (const kind of ['scatter', 'bars']) {
        const element = document.getElementById(`calibration-${kind}-${domain.id}`);
        const traces = domain.series.map(series => {
          const model = data.models.find(m => m.id === series.model);
          const common = {name: model.label, legendgroup: model.id, uid: `${domain.id}-${kind}-${model.id}`};
          if (kind === 'scatter') return {...common, type: 'scatter', mode: 'markers',
            x: series.points.map(p => p[0]), y: series.points.map(p => p[1]),
            customdata: series.points.map(p => [Math.abs(p[1] - p[0]), p[2]]),
            marker: {color: model.color, symbol: model.symbol, size: model.id === 'gemini37' ? 5.5 : 5, opacity: .58},
            hovertemplate: `<b>${esc(model.label)}</b> · ${esc(domain.label)}<br>True difference: %{x:.2f}<br>LLM difference: %{y:.2f}<br>Absolute error: %{customdata[0]:.2f}<br>Seed: %{customdata[1]}<extra></extra>`};
          return {...common, type: 'bar', x: [0, 1, 2, 3], y: series.bars.map(b => b.mean),
            customdata: series.bars.map(b => [data.prompts.methods[b.method].label, b.sd, b.emitted, b.selected]),
            marker: {color: model.color},
            error_y: {type: 'data', array: series.bars.map(b => b.sd), visible: true, color: '#252d28', thickness: 1, width: 2},
            hovertemplate: `<b>${esc(model.label)}</b><br>%{customdata[0]} · ${esc(domain.label)}<br>Accuracy: %{y:.2f}% ± %{customdata[1]:.2f} SD<extra></extra>`};
        });
        await Plotly.newPlot(element, traces, layout(kind), {responsive: true, displayModeBar: false, scrollZoom: false});
        charts.push(element);
        let selected = -1;
        element.addEventListener('keydown', event => {
          if (event.key === 'Escape') {Plotly.Fx.unhover(element); return;}
          if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
          event.preventDefault();
          const points = traces.flatMap((trace, curveNumber) => activeModels.has(trace.legendgroup) ? trace.x.map((_, pointNumber) => ({curveNumber, pointNumber})) : []);
          if (!points.length) return;
          selected = (selected + (['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1) + points.length) % points.length;
          const point = points[selected], trace = traces[point.curveNumber], i = point.pointNumber;
          Plotly.Fx.hover(element, [point]);
          live.textContent = kind === 'scatter' ? `${trace.name}. True difference ${trace.x[i].toFixed(2)}; LLM difference ${trace.y[i].toFixed(2)}.` : `${trace.name}, ${trace.customdata[i][0]}. Accuracy ${trace.y[i].toFixed(2)} percent, SD ${trace.customdata[i][1].toFixed(2)}.`;
        });
        element.addEventListener('blur', () => Plotly.Fx.unhover(element));
      }
    }
    grid.dataset.ready = 'true';
  }
  const ready = render();
  legend.addEventListener('click', async event => {
    const button = event.target.closest('[data-calibration-model]');
    if (!button) return;
    const key = button.dataset.calibrationModel;
    activeModels.has(key) ? activeModels.delete(key) : activeModels.add(key);
    button.setAttribute('aria-pressed', String(activeModels.has(key)));
    document.querySelectorAll(`[data-mae-model="${key}"]`).forEach(el => el.classList.toggle('muted', !activeModels.has(key)));
    await ready;
    await Promise.all(charts.map(chart => Plotly.restyle(chart, {visible: data.models.map(m => activeModels.has(m.id))})));
  });

  // Prompt components are copied verbatim; candidate data varies per request.
  const popup = document.createElement('div');
  popup.id = 'calibration-prompt-dialog';
  popup.className = 'calibration-prompt-dialog';
  popup.setAttribute('role', 'dialog');
  popup.setAttribute('aria-labelledby', 'calibration-prompt-title');
  popup.hidden = true;
  document.body.append(popup);
  let trigger = null, pinned = false, timer, ignoreFocus = null, variant = 'default';
  function position() {
    if (!trigger || popup.hidden) return;
    const rect = trigger.getBoundingClientRect();
    const bounds = popup.getBoundingClientRect();
    const left = Math.min(Math.max(12, rect.left), innerWidth - bounds.width - 12);
    const below = rect.bottom + 10;
    const top = below + bounds.height <= innerHeight - 12 ? below : Math.max(12, rect.top - bounds.height - 10);
    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;
  }
  function content() {
    const domain = data.domains.find(d => d.id === trigger.dataset.domain);
    const method = data.prompts.methods[trigger.dataset.method];
    popup.innerHTML = `<div class="calibration-prompt-header"><h3 id="calibration-prompt-title">${esc(domain.label)}${method ? ` · ${esc(method.label)}` : ' · task'}</h3><button type="button" class="calibration-close" aria-label="Close prompt">×</button></div>
      ${method ? `<p class="calibration-prompt-description">${esc(method.description)}</p>` : ''}
      <p class="calibration-prompt-kicker">Task · verbatim</p><blockquote>${esc(domain.prompt.trim())}</blockquote>
      ${method ? `<p class="calibration-prompt-kicker">Elicitation instructions · verbatim</p>
        ${method.variants.opus ? `<div class="calibration-variants" role="group" aria-label="Prompt variant"><button type="button" data-variant="default" aria-pressed="${variant === 'default'}">GPT / Gemini</button><button type="button" data-variant="opus" aria-pressed="${variant === 'opus'}">Claude</button></div>` : ''}
        <blockquote class="calibration-instructions">${esc(method.variants[variant] || method.variants.default)}</blockquote>` : ''}
      <details><summary>Shared instructions · verbatim</summary><blockquote>${esc(data.prompts.common.trim())}</blockquote></details>
      <p class="calibration-prompt-footnote">Each request combines these instructions with the candidate representations. True property values are hidden from the LLM.${trigger.dataset.method === 'joint_score' ? ' For evaluation, true properties are direction-corrected and min–max scaled to 1–100; the LLM outputs are not recalibrated.' : ''}</p>`;
    position();
  }
  function close(restore = false) {
    clearTimeout(timer);
    const old = trigger;
    if (old) old.setAttribute('aria-expanded', 'false');
    trigger = null; pinned = false; popup.hidden = true;
    if (restore && old) {ignoreFocus = old; old.focus(); ignoreFocus = null;}
  }
  function open(button, pin = false) {
    clearTimeout(timer);
    if (pinned && trigger !== button && !pin) return;
    const changed = trigger !== button;
    if (changed) {if (trigger) trigger.setAttribute('aria-expanded', 'false'); variant = 'default';}
    trigger = button;
    pinned = pin || (!changed && pinned);
    popup.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    if (changed || !popup.innerHTML) content();
    position();
  }
  function delayedClose() {clearTimeout(timer); if (!pinned) timer = setTimeout(() => close(), 220);}
  grid.querySelectorAll('.calibration-prompt').forEach(button => {
    button.addEventListener('pointerenter', event => {if (event.pointerType !== 'touch') open(button);});
    button.addEventListener('pointerleave', delayedClose);
    button.addEventListener('focus', () => {if (ignoreFocus !== button) open(button);});
    button.addEventListener('blur', event => {if (!popup.contains(event.relatedTarget)) delayedClose();});
    button.addEventListener('click', () => {if (trigger === button && pinned) close(); else open(button, true);});
    button.addEventListener('keydown', event => {if (event.key === 'ArrowDown') {event.preventDefault(); open(button, true); popup.querySelector('.calibration-close').focus();}});
  });
  popup.addEventListener('pointerenter', () => clearTimeout(timer));
  popup.addEventListener('pointerleave', delayedClose);
  popup.addEventListener('focusin', () => {clearTimeout(timer); pinned = true;});
  popup.addEventListener('focusout', event => {if (!popup.contains(event.relatedTarget) && event.relatedTarget !== trigger) close();});
  popup.addEventListener('click', event => {
    if (event.target.closest('.calibration-close')) close(true);
    const choice = event.target.closest('[data-variant]');
    if (choice) {
      variant = choice.dataset.variant;
      const method = data.prompts.methods[trigger.dataset.method];
      popup.querySelector('.calibration-instructions').textContent = method.variants[variant];
      popup.querySelectorAll('[data-variant]').forEach(button => button.setAttribute('aria-pressed', String(button === choice)));
      position();
    }
  });
  popup.addEventListener('toggle', position, true);
  document.addEventListener('pointerdown', event => {if (trigger && !popup.contains(event.target) && !trigger.contains(event.target)) close();});
  document.addEventListener('keydown', event => {if (event.key === 'Escape' && trigger) {event.preventDefault(); close(popup.contains(document.activeElement));}});
  window.addEventListener('resize', position);
  window.addEventListener('scroll', () => {if (!pinned) close(); else position();}, {passive: true});
})();

/* Interactive views of preserved table and plot values; no new evaluations. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const palette = {
    'LFD': {color:'#8732ad', symbol:'square'},
    'Pre-trained': {color:'#33373f', symbol:'x'},
    'DPO': {color:'#d77b00', symbol:'circle'},
    'DiffusionNFT': {color:'#286565', symbol:'diamond'},
    'Flow-GRPO': {color:'#719adc', symbol:'triangle-up'},
    'Guidance': {color:'#c54b59', symbol:'triangle-down'}
  };
  const style = method => palette[method] || palette['Pre-trained'];
  const config = {responsive:true, displayModeBar:false, scrollZoom:false, showTips:false};
  const fonts = document.fonts ? document.fonts.ready : Promise.resolve();
  function layout(overrides = {}) {
    return {
      autosize:true, margin:{l:65,r:24,t:24,b:65}, paper_bgcolor:'#fff', plot_bgcolor:'#fff',
      font:{family:'Inter, sans-serif',size:12,color:'#4b515c'}, showlegend:false,
      hovermode:'closest', hoverdistance:24, dragmode:false,
      hoverlabel:{bgcolor:'#fff',bordercolor:'#d8dce3',font:{family:'Inter, sans-serif',size:12,color:'#202124'},align:'left'},
      xaxis:{fixedrange:true,gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,gridcolor:'#eceef2',zeroline:false,automargin:true},
      ...overrides
    };
  }
  function draw(selector, traces, options, onInspect) {
    const element = $(selector);
    return Plotly.react(element,traces,options,config).then(() => {
      if (element.removeAllListeners) {
        element.removeAllListeners('plotly_hover');
        element.removeAllListeners('plotly_click');
      }
      if (onInspect) {
        const inspect = event => onInspect(event.points[0]);
        element.on('plotly_hover',inspect);
        element.on('plotly_click',inspect);
      }
    });
  }
  function interval(mean, spread, digits = 2) { return `${mean.toFixed(digits)} ± ${spread.toFixed(digits)}`; }
  function table(title, headings, rows) {
    return `<div class="table-scroll" tabindex="0" role="region" aria-label="${esc(title)}"><table><caption>${esc(title)}</caption><thead><tr>${headings.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${esc(row[0])}</th>${row.slice(1).map(value=>`<td>${esc(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function init(results) {
    const taskSelect = $('#result-task');
    const metricSelect = $('#result-metric');
    taskSelect.innerHTML = results.map(result=>`<option value="${esc(result.id)}">${esc(result.name)}</option>`).join('');
    $('#result-cards').innerHTML = results.map(result => {
      const [mean,spread] = result.rows.find(row=>row.method === 'LFD').values[0];
      const base = result.rows.find(row=>row.method === 'Pre-trained').values[0][0];
      return `<article class="result-card" data-result-card="${esc(result.id)}"><h3>${esc(result.name)}</h3><span class="tiny-label">${esc(result.metricShort)}</span><div class="result-number">${mean.toFixed(2)}<small>${esc(result.unit)}</small></div><div class="result-uncertainty">± ${spread.toFixed(2)} · LFD</div><div class="result-baseline">Pre-trained: ${base.toFixed(2)} ${esc(result.unit)}</div><button class="result-jump" data-result-task="${esc(result.id)}">Compare methods <span class="sr-only">for ${esc(result.name)}</span><span aria-hidden="true"> ↗</span></button></article>`;
    }).join('');
    function renderComparison() {
      const result = results.find(item=>item.id === taskSelect.value);
      const index = Number(metricSelect.value);
      const metric = result.metrics[index];
      const direction = index === 2 && result.table === 1 ? 'Distance from the prior · a descriptive measure of distribution shift' : `${metric.direction === 'up' ? 'Higher' : 'Lower'} is better`;
      $('#comparison-context').textContent = `${result.name} · ${metric.label} · ${direction}`;
      $('#comparison-readout').textContent = 'Hover or tap a marker to see all metric values.';
      $('#comparison-chart').dataset.chartTask = result.id;
      $('#comparison-chart').dataset.chartMetric = String(index);
      const traces = result.rows.map(row=>({
        type:'scatter',mode:'markers',name:row.method,x:[row.values[index][0]],y:[row.method],
        marker:{color:style(row.method).color,symbol:style(row.method).symbol,size:row.method === 'LFD' ? 13 : 11},
        error_x:{type:'data',array:[row.values[index][1]],visible:true,color:style(row.method).color,thickness:1.5,width:5},
        hovertemplate:`<b>${esc(row.method)}</b><br>${result.metrics.map((m,i)=>`${esc(m.label)}: ${interval(...row.values[i])}`).join('<br>')}<extra></extra>`
      }));
      const options = layout({
        margin:{l:112,r:40,t:25,b:65},
        xaxis:{fixedrange:true,title:{text:metric.label,standoff:18},gridcolor:'#eceef2',zeroline:false,automargin:true},
        yaxis:{fixedrange:true,categoryorder:'array',categoryarray:result.rows.map(row=>row.method).reverse(),showgrid:false,automargin:true}
      });
      fonts.then(()=>draw('#comparison-chart',traces,options,point=>{
        const row = result.rows[point.curveNumber];
        $('#comparison-readout').innerHTML = `<strong>${esc(row.method)}</strong> · ${result.metrics.map((m,i)=>`${esc(m.label)}: ${interval(...row.values[i])}`).join(' · ')}`;
      }));
    }
    function renderTask() {
      const result = results.find(item=>item.id === taskSelect.value);
      metricSelect.innerHTML = result.metrics.map((metric,index)=>`<option value="${index}">${esc(metric.label)}${index === 2 && result.table === 1 ? '' : metric.direction === 'up' ? ' ↑' : ' ↓'}</option>`).join('');
      const best = result.metrics.map((metric,i)=>(metric.direction === 'up' ? Math.max : Math.min)(...result.rows.map(row=>row.values[i][0])));
      $('#results-table').innerHTML = `<caption class="sr-only">${esc(result.name)}, paper Table ${result.table}. Higher is better for up arrows, lower for down arrows. Distance from prior is descriptive.</caption><thead><tr><th scope="col">Method</th>${result.metrics.map((m,i)=>`<th scope="col">${esc(m.label)} ${i === 2 && result.table === 1 ? '' : m.direction === 'up' ? '↑' : '↓'}</th>`).join('')}</tr></thead><tbody>${result.rows.map(row=>`<tr class="${row.method === 'LFD' ? 'ours' : ''}"><th scope="row">${esc(row.method === 'LFD' ? 'LFD · ours' : row.method)}</th>${row.values.map(([mean,error],i)=>`<td class="${!(i === 2 && result.table === 1) && mean === best[i] ? 'best' : ''}">${interval(mean,error)}</td>`).join('')}</tr>`).join('')}</tbody>`;
      document.querySelectorAll('[data-result-card]').forEach(card=>card.classList.toggle('is-selected',card.dataset.resultCard === result.id));
      renderComparison();
    }
    taskSelect.addEventListener('change',renderTask);
    metricSelect.addEventListener('change',renderComparison);
    document.querySelectorAll('[data-result-task]').forEach(button=>button.addEventListener('click',()=>{
      taskSelect.value = button.dataset.resultTask;
      renderTask();
      $('#results-comparison').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',block:'start'});
      taskSelect.focus({preventScroll:true});
    }));
    renderTask();
    fonts.then(renderDocking);
  }
  function renderDocking() {
    const data = window.LFD_DATA.charts;
    $('#docking-legend').innerHTML = ['LFD','DPO','DiffusionNFT','Flow-GRPO','Guidance','Pre-trained'].map(method=>`<span><i style="--plot-color:${style(method).color}" aria-hidden="true"></i>${esc(method)}</span>`).join('');
    const rounds = data.trajectory.map(row=>row.round);
    const trajectory = data.trajectory;
    const traces = [
      {type:'scatter',x:rounds,y:trajectory.map(row=>row.ciLow),mode:'lines',line:{width:0},hoverinfo:'skip'},
      {type:'scatter',x:rounds,y:trajectory.map(row=>row.ciHigh),mode:'lines',line:{width:0},fill:'tonexty',fillcolor:'rgba(135,50,173,.14)',hoverinfo:'skip'}
    ];
    data.baselines.forEach(row=>{
      const color = style(row.method).color;
      const half = Math.max(row.mean-row.ciLow,row.ciHigh-row.mean);
      traces.push({type:'scatter',x:[0,7],y:[row.mean-half,row.mean-half],mode:'lines',line:{width:0},hoverinfo:'skip'});
      traces.push({type:'scatter',x:[0,7],y:[row.mean+half,row.mean+half],mode:'lines',line:{width:0},fill:'tonexty',fillcolor:color+'13',hoverinfo:'skip'});
      traces.push({type:'scatter',name:row.method,x:[0,7],y:[row.mean,row.mean],mode:'lines',line:{color,width:1.8,dash:'dash'},hovertemplate:`<b>${esc(row.method)}</b><br>GNINA: ${row.mean.toFixed(3)} pK<br>95% interval: ${row.ciLow.toFixed(3)}–${row.ciHigh.toFixed(3)}<br>Docked molecules: ${row.dockedMolecules}<extra></extra>`});
    });
    traces.push({
      type:'scatter',name:'LFD best so far',x:rounds,y:trajectory.map(row=>row.bestMean),mode:'lines+markers',
      line:{color:style('LFD').color,width:3},marker:{color:style('LFD').color,symbol:'square',size:8},
      customdata:trajectory.map(row=>[row.checkpointMean,row.bestRound,row.ciLow,row.ciHigh,row.dockedMolecules,row.goal]),
      hovertemplate:'<b>LFD · round %{x}</b><br>Best so far: %{y:.3f} pK (round %{customdata[1]})<br>This checkpoint: %{customdata[0]:.3f} pK<br>Best checkpoint 95% interval: %{customdata[2]:.3f}–%{customdata[3]:.3f}<br>Docked at this round: %{customdata[4]}<extra></extra>'
    });
    draw('#trajectory-chart',traces,layout({
      xaxis:{fixedrange:true,title:{text:'Curriculum round',standoff:14},dtick:1,range:[-.15,7.15],gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,title:{text:'GNINA CNNaffinity (pK)',standoff:10},gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      const row = trajectory[point.pointIndex];
      if (point.data.name === 'LFD best so far') $('#trajectory-readout').innerHTML = `<strong>Round ${row.round}</strong> · This checkpoint: ${row.checkpointMean.toFixed(3)} pK · Best so far: ${row.bestMean.toFixed(3)} pK, from round ${row.bestRound}`;
      else {
        const base = data.baselines.find(row=>row.method === point.data.name);
        if (base) $('#trajectory-readout').innerHTML = `<strong>${esc(base.method)}</strong> · ${base.mean.toFixed(3)} pK · 95% interval: ${base.ciLow.toFixed(3)}–${base.ciHigh.toFixed(3)}`;
      }
    });
    const novelty = data.novelty.map(row=>({
      type:'scatter',mode:'markers',name:row.method,x:[row.noveltyMean],y:[row.negativeRDockMean],
      marker:{color:style(row.method).color,symbol:style(row.method).symbol,size:row.method === 'LFD' ? 13 : 11},
      error_x:{type:'data',array:[row.noveltyCI95],color:style(row.method).color,thickness:1.4,width:4,visible:true},
      error_y:{type:'data',array:[row.negativeRDockCI95],color:style(row.method).color,thickness:1.4,width:4,visible:true},
      hovertemplate:`<b>${esc(row.method)}</b><br>Novel scaffolds: ${interval(row.noveltyMean,row.noveltyCI95,2)}<br>Negative rDock (top 5%): ${interval(row.negativeRDockMean,row.negativeRDockCI95,3)}<br>95% intervals · ${row.samplingSeeds} sampling seeds<extra></extra>`
    }));
    draw('#novelty-chart',novelty,layout({
      xaxis:{fixedrange:true,title:{text:'Novel scaffolds in top 100',standoff:14},gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,title:{text:'Negative rDock (top 5%)',standoff:10},gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      const row = data.novelty[point.curveNumber];
      $('#novelty-readout').innerHTML = `<strong>${esc(row.method)}</strong> · Novel scaffolds: ${interval(row.noveltyMean,row.noveltyCI95)} · Negative rDock: ${interval(row.negativeRDockMean,row.negativeRDockCI95,3)} · 95% intervals`;
    });
    $('#figure-data-tables').innerHTML = table('GSK3β trajectory', ['Round','Checkpoint mean (pK)','Best so far (pK)','Best round','Best checkpoint 95% interval'], trajectory.map(row=>[row.round,row.checkpointMean.toFixed(3),row.bestMean.toFixed(3),row.bestRound,`${row.ciLow.toFixed(3)}–${row.ciHigh.toFixed(3)}`])) + table('GSK3β baseline evaluations',['Method','GNINA (pK)','95% interval','Docked molecules'],data.baselines.map(row=>[row.method,row.mean.toFixed(3),`${row.ciLow.toFixed(3)}–${row.ciHigh.toFixed(3)}`,row.dockedMolecules])) + table('GSK3β scaffold novelty',['Method','Novel scaffolds ± 95% CI','Negative rDock ± 95% CI','Sampling seeds'], data.novelty.map(row=>[row.method,interval(row.noveltyMean,row.noveltyCI95),interval(row.negativeRDockMean,row.negativeRDockCI95,3),row.samplingSeeds]));
  }
  window.LFD_RESULTS = {init};
})();

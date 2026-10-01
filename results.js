/* Task-specific views of the preserved paper tables and aggregate plot data. */
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
  function markerKey(method) {
    const {color,symbol} = style(method);
    const shapes = {
      square:'<rect x="3" y="3" width="10" height="10"/>',
      x:'<path d="M4 4L12 12M4 12L12 4" fill="none" stroke="currentColor" stroke-width="3.5"/>',
      circle:'<circle cx="8" cy="8" r="5"/>',
      diamond:'<path d="M8 1L15 8L8 15L1 8Z"/>',
      'triangle-up':'<path d="M8 2L15 14H1Z"/>',
      'triangle-down':'<path d="M1 2H15L8 14Z"/>'
    };
    return `<svg viewBox="0 0 16 16" width="15" height="15" data-marker-symbol="${symbol}" style="color:${color};fill:currentColor" aria-hidden="true">${shapes[symbol]}</svg>`;
  }
  function legend(methods) {
    return `<div class="plot-key" aria-label="Methods and plot markers">${['LFD','DPO','DiffusionNFT','Flow-GRPO','Guidance','Pre-trained'].filter(method=>methods.includes(method)).map(method=>`<span data-legend-method="${esc(method)}">${markerKey(method)}${esc(method)}</span>`).join('')}</div>`;
  }
  function scatterMarkup(result) {
    const peptide = result.table === 1;
    return `${legend(result.rows.map(row=>row.method))}<figure class="task-scatter"><h4>${peptide ? 'Activity and predicted toxicity' : 'Docking scores'}</h4><div id="comparison-chart" class="interactive-chart" role="region" aria-label="${peptide ? 'Interactive activity and toxicity scatterplot' : 'Interactive docking score scatterplot'}"></div><p id="comparison-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a marker to inspect its metric values.</p><figcaption>${peptide ? 'Activity increases to the right; predicted hemolysis decreases downward. Error bars show the ± terms printed in Table 1.' : 'GNINA affinity increases to the right; rDock decreases downward. Error bars show the ± terms printed in Table 2.'}</figcaption></figure>`;
  }
  function renderScatter(result) {
    const yIndex = result.table === 1 ? 1 : 2;
    const traces = result.rows.map(row=>({
      type:'scatter',mode:'markers',name:row.method,x:[row.values[0][0]],y:[row.values[yIndex][0]],
      marker:{color:style(row.method).color,symbol:style(row.method).symbol,size:row.method === 'LFD' ? 13 : 11},
      error_x:{type:'data',array:[row.values[0][1]],visible:true,color:style(row.method).color,thickness:1.5,width:5},
      error_y:{type:'data',array:[row.values[yIndex][1]],visible:true,color:style(row.method).color,thickness:1.5,width:5},
      hovertemplate:`<b>${esc(row.method)}</b><br>${result.metrics.map((m,i)=>`${esc(m.label)}: ${interval(...row.values[i])}`).join('<br>')}<extra></extra>`
    }));
    return draw('#comparison-chart',traces,layout({
      xaxis:{fixedrange:true,title:{text:result.metrics[0].label+' ↑',standoff:18},gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,title:{text:result.metrics[yIndex].label+' ↓',standoff:16},gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      const row = result.rows[point.curveNumber];
      $('#comparison-readout').innerHTML = `<strong>${esc(row.method)}</strong> · ${result.metrics.map((m,i)=>`${esc(m.label)}: ${interval(...row.values[i])}`).join(' · ')}`;
    });
  }
  function renderTable(result) {
    const best = result.metrics.map((metric,i)=>(metric.direction === 'up' ? Math.max : Math.min)(...result.rows.map(row=>row.values[i][0])));
    $('#results-table-title').textContent = 'Numerical results';
    $('#results-table').innerHTML = `<caption class="sr-only">${esc(result.name)}, paper Table ${result.table}. Higher is better for up arrows, lower for down arrows. Distance from prior is descriptive.</caption><thead><tr><th scope="col">Method</th>${result.metrics.map((m,i)=>`<th scope="col">${esc(m.label)} ${i === 2 && result.table === 1 ? '' : m.direction === 'up' ? '↑' : '↓'}</th>`).join('')}</tr></thead><tbody>${result.rows.map(row=>`<tr class="${row.method === 'LFD' ? 'ours' : ''}"><th scope="row">${esc(row.method === 'LFD' ? 'LFD · ours' : row.method)}</th>${row.values.map(([mean,error],i)=>`<td class="${!(i === 2 && result.table === 1) && mean === best[i] ? 'best' : ''}">${interval(mean,error)}</td>`).join('')}</tr>`).join('')}</tbody>`;
    $('#results-table-note').textContent = 'Means and ± terms are preserved from the paper. These are computational evaluations; see the paper for evaluation and checkpoint-selection details.';
  }
  function dockingMarkup() {
    return `${legend(Object.keys(palette))}<div class="docking-chart-grid">
      <figure class="chart-card"><h4>Docking across curriculum rounds</h4><p>GNINA CNNaffinity · higher is better</p><div id="trajectory-chart" class="interactive-chart" role="region" aria-label="GSK3 beta interactive docking trajectory"></div><p id="trajectory-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a round to inspect its checkpoint and best-so-far score.</p><figcaption>The purple line carries forward the best checkpoint mean seen so far. Dashed lines show the baseline evaluations.</figcaption></figure>
      <figure class="chart-card"><h4>Docking quality and scaffold novelty</h4><p>Moving up and right improves both metrics</p><div id="novelty-chart" class="interactive-chart" role="region" aria-label="GSK3 beta interactive scaffold novelty comparison"></div><p id="novelty-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a method to inspect both metrics and their intervals.</p><figcaption>Novelty counts distinct novel scaffolds among the top 100. The vertical axis shows negative rDock for the top 5%.</figcaption></figure>
    </div>`;
  }
  function molecularExample(task) {
    if (task.id !== 'd2' && task.id !== 'gsk3b') return '';
    const d2=task.id === 'd2';
    return `<details class="task-example"><summary>Illustrative docking pose · Figure ${d2 ? '6' : '8'}</summary><figure><img src="assets/${d2 ? 'd2' : 'gsk3b'}-docking.png" alt="${esc(task.name)}: LFD-generated molecular structure and computational docking pose" loading="lazy"><figcaption>Computational docking example from the supplied preprint.</figcaption></figure></details>`;
  }
  function renderOODTable() {
    const evidence = window.LFD_DATA.resultPanels.oodEvidence;
    $('#results-table-title').textContent = 'Reported discovery evidence';
    $('#results-table').innerHTML = `<caption class="sr-only">Constrained molecular design, paper Figure 9. Sampling budgets differ.</caption><thead><tr><th scope="col">Generator</th><th scope="col">Full-goal outcome</th><th scope="col">Samples</th><th scope="col">Round</th></tr></thead><tbody><tr><th scope="row">Pre-trained</th><td>No hits</td><td>${evidence.pretrained.attempts.toLocaleString('en-US')}</td><td>—</td></tr><tr class="ours"><th scope="row">LFD · ours</th><td>${esc(evidence.lfd.outcome)}</td><td>${evidence.lfd.batchSize}-sample batch</td><td>${evidence.lfd.round}</td></tr></tbody>`;
    $('#results-table-note').textContent = evidence.caveat;
  }
  function renderOOD(task) {
    const points=[];
    let round=0;
    task.stages.filter(stage=>stage.rounds>0).forEach((stage,index)=>{
      for (let i=0;i<stage.rounds;i++) points.push({round:++round,index,title:stage.title,summary:stage.summary});
    });
    const traces=[{
      type:'scatter',name:'Curriculum subgoal',x:points.map(point=>point.round),y:points.map(point=>point.index),mode:'lines+markers',
      marker:{color:style('LFD').color,symbol:'circle',size:10},line:{color:style('LFD').color,width:2.5,shape:'hv'},
      customdata:points.map(point=>[point.title]),hovertemplate:'<b>Round %{x}</b><br>%{customdata[0]}<extra></extra>'
    },{
      type:'scatter',name:'Final-goal assessment',x:[6],y:[3],mode:'markers',marker:{color:'#c54b59',symbol:'square',size:13},
      hovertemplate:'<b>Full-goal assessment · round 6</b><br>Reported hit in a 512-sample batch<br>No additional training update<extra></extra>'
    }];
    return draw('#curriculum-chart',traces,layout({
      xaxis:{fixedrange:true,title:{text:'Curriculum round',standoff:18},dtick:1,range:[.5,6.5],gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,tickvals:[0,1,2,3],ticktext:['g<sub>0</sub>','g<sub>1</sub>','g<sub>2</sub>','Final goal'],range:[-.4,3.4],gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      if (point.curveNumber===1) $('#curriculum-readout').innerHTML='<strong>Round 6 · final goal</strong> · Reported full-goal hit in a 512-sample batch. This is an assessment, with no additional training update.';
      else {
        const row=points[point.pointIndex];
        $('#curriculum-readout').innerHTML=`<strong>Round ${row.round} · ${esc(row.title)}</strong> · ${esc(row.summary)}`;
      }
    });
  }
  function init(results) {
    const data=window.LFD_DATA;
    const goals=data.resultPanels.tasks;
    const cards=$('#result-cards');
    const panel=$('#task-results-panel');
    let active=goals[0].id;
    let generation=0;
    cards.innerHTML=goals.map((task,index)=>`<button id="result-card-${esc(task.id)}" class="result-card" role="tab" aria-selected="${index===0}" aria-controls="task-results-panel" aria-labelledby="result-name-${esc(task.id)}" aria-describedby="result-goal-${esc(task.id)}" tabindex="${index===0 ? 0 : -1}" data-result-task="${esc(task.id)}"><span class="goal-card-heading"><span class="tiny-label">GOAL ${task.number}</span><span class="goal-card-state" aria-hidden="true">${index===0 ? 'Selected' : '↗'}</span></span><strong id="result-name-${esc(task.id)}" class="result-task-name">${esc(task.name)}</strong><span id="result-goal-${esc(task.id)}" class="result-goal">${esc(task.goal)}</span></button>`).join('');
    function render(id) {
      active=id;
      const current=++generation;
      const goal=goals.find(task=>task.id===id);
      const task=data.tasks.find(task=>task.id===id);
      const result=results.find(result=>result.id===id);
      panel.dataset.selectedTask=id;
      delete panel.dataset.plotReadyTask;
      panel.setAttribute('aria-labelledby','result-card-'+id);
      cards.querySelectorAll('[data-result-task]').forEach(card=>{
        const selected=card.dataset.resultTask===id;
        card.setAttribute('aria-selected',String(selected));
        card.tabIndex=selected ? 0 : -1;
        card.classList.toggle('is-selected',selected);
        card.querySelector('.goal-card-state').textContent=selected ? 'Selected' : '↗';
      });
      // Dispose of inactive plots so resize listeners and tooltips cannot leak across tasks.
      panel.querySelectorAll('.js-plotly-plot').forEach(plot=>Plotly.purge(plot));
      $('#task-results-title').textContent=goal.name;
      $('#result-source').textContent=`GOAL ${goal.number} · ${result ? 'TABLE '+result.table : 'FIGURE 9'}${id==='gsk3b' ? ' · FIGURE 7' : ''}`;
      $('#result-paper-link').href=`assets/paper.pdf#page=${goal.paperPage}`;
      $('#task-result-example').innerHTML=molecularExample(task);
      if (id==='gsk3b') {
        $('#task-result-description').textContent='Follow docking performance across curriculum rounds, then explore the relation between docking quality and scaffold novelty.';
        $('#task-results-plots').innerHTML=dockingMarkup();
        $('#task-results-evidence').innerHTML='<details class="figure-evidence"><summary>Plot data and uncertainty</summary><p>The trajectory is a descriptive post-hoc comparison of independently sampled checkpoint cohorts. Shaded 95% intervals belong to the selected checkpoint and are not adjusted for best-so-far selection. Novelty error bars are Student-t 95% intervals across five sampling seeds, conditional on one frozen checkpoint per method and using the filtered scaffold reference.</p><div id="figure-data-tables"></div><div class="chart-data-links"><a href="data/charts.json" download>Download chart data (JSON)</a><a href="assets/paper.pdf#page=9" target="_blank" rel="noopener">Figure 7 in the paper ↗</a></div></details>';
        renderTable(result);
      } else if (id==='ood') {
        $('#task-result-description').textContent='The curriculum reaches a reported design satisfying the full structural goal. The final-goal assessment is separate from the intermediate training subgoal.';
        $('#task-results-plots').innerHTML='<figure class="task-scatter"><h4>From intermediate subgoals to the full goal</h4><div class="plot-key" aria-label="Curriculum markers"><span><svg viewBox="0 0 16 16" width="15" height="15" fill="#8732ad" aria-hidden="true"><circle cx="8" cy="8" r="5"/></svg>Curriculum subgoal</span><span><svg viewBox="0 0 16 16" width="15" height="15" fill="#c54b59" aria-hidden="true"><rect x="3" y="3" width="10" height="10"/></svg>Final-goal assessment</span></div><div id="curriculum-chart" class="interactive-chart" role="region" aria-label="Interactive constrained-design curriculum"></div><p id="curriculum-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a round to inspect the active subgoal.</p><figcaption>Six recorded training rounds; the full-goal assessment at round 6 uses no additional training update.</figcaption></figure>';
        $('#task-results-evidence').innerHTML='<div class="chart-data-links"><a href="#explorer?task=ood&stage=g&tab=traces">Inspect the recorded discovery example ↗</a><a href="assets/paper.pdf#page=9" target="_blank" rel="noopener">Figure 9 in the paper ↗</a></div>';
        renderOODTable();
      } else {
        $('#task-result-description').textContent=result.table===1 ? 'Activity and predicted toxicity are shown together. Moving right and down increases the activity score and reduces predicted hemolysis.' : 'Explore the joint docking scores, with all three evaluators reported in the table and marker details.';
        $('#task-results-plots').innerHTML=scatterMarkup(result);
        $('#task-results-evidence').innerHTML=id==='d2' ? '<div class="chart-data-links"><a href="assets/paper.pdf#page=9" target="_blank" rel="noopener">D2 trajectory and novelty panels in Figure 7 ↗</a></div>' : '';
        renderTable(result);
      }
      fonts.then(()=>{
        if (current!==generation) return;
        const work=id==='gsk3b' ? renderDocking() : id==='ood' ? renderOOD(task) : renderScatter(result);
        return Promise.resolve(work).then(()=>{if (current===generation) panel.dataset.plotReadyTask=id;});
      });
    }
    cards.addEventListener('click',event=>{
      const card=event.target.closest('[data-result-task]');
      if (card) render(card.dataset.resultTask);
    });
    cards.addEventListener('keydown',event=>{
      const index=goals.findIndex(task=>task.id===active);
      let next;
      if (event.key==='ArrowRight' || event.key==='ArrowDown') next=(index+1)%goals.length;
      if (event.key==='ArrowLeft' || event.key==='ArrowUp') next=(index+goals.length-1)%goals.length;
      if (event.key==='Home') next=0;
      if (event.key==='End') next=goals.length-1;
      if (next==null) return;
      event.preventDefault();
      render(goals[next].id);
      const nextCard=$('#result-card-'+goals[next].id);
      nextCard.focus({preventScroll:true});
      nextCard.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});
    });
    render(active);
  }
  function renderDocking() {
    const data = window.LFD_DATA.charts;
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
    const trajectoryPlot = draw('#trajectory-chart',traces,layout({
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
    const noveltyPlot = draw('#novelty-chart',novelty,layout({
      xaxis:{fixedrange:true,title:{text:'Novel scaffolds in top 100',standoff:14},gridcolor:'#eceef2',zeroline:false,automargin:true},
      yaxis:{fixedrange:true,title:{text:'Negative rDock (top 5%)',standoff:10},gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      const row = data.novelty[point.curveNumber];
      $('#novelty-readout').innerHTML = `<strong>${esc(row.method)}</strong> · Novel scaffolds: ${interval(row.noveltyMean,row.noveltyCI95)} · Negative rDock: ${interval(row.negativeRDockMean,row.negativeRDockCI95,3)} · 95% intervals`;
    });
    $('#figure-data-tables').innerHTML = table('GSK3β trajectory', ['Round','Checkpoint mean (pK)','Best so far (pK)','Best round','Best checkpoint 95% interval'], trajectory.map(row=>[row.round,row.checkpointMean.toFixed(3),row.bestMean.toFixed(3),row.bestRound,`${row.ciLow.toFixed(3)}–${row.ciHigh.toFixed(3)}`])) + table('GSK3β baseline evaluations',['Method','GNINA (pK)','95% interval','Docked molecules'],data.baselines.map(row=>[row.method,row.mean.toFixed(3),`${row.ciLow.toFixed(3)}–${row.ciHigh.toFixed(3)}`,row.dockedMolecules])) + table('GSK3β scaffold novelty',['Method','Novel scaffolds ± 95% CI','Negative rDock ± 95% CI','Sampling seeds'], data.novelty.map(row=>[row.method,interval(row.noveltyMean,row.noveltyCI95),interval(row.negativeRDockMean,row.negativeRDockCI95,3),row.samplingSeeds]));
    return Promise.all([trajectoryPlot, noveltyPlot]);
  }
  window.LFD_RESULTS = {init};
})();

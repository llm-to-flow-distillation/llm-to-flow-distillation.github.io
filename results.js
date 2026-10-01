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
  function legend(methods, bars = false) {
    const ordered = bars ? methods : ['LFD','DPO','DiffusionNFT','Flow-GRPO','Guidance','Pre-trained'].filter(method=>methods.includes(method));
    return `<div class="plot-key" aria-label="Methods and plot markers">${ordered.map(method=>`<span data-legend-method="${esc(method)}">${bars ? `<svg viewBox="0 0 16 16" width="15" height="15" data-marker-symbol="bar" style="color:${style(method).color};fill:currentColor" aria-hidden="true"><rect x="2" y="2" width="12" height="12" rx="1"/></svg>` : markerKey(method)}${esc(method)}</span>`).join('')}</div>`;
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
    $('#results-table').innerHTML = `<caption class="sr-only">${esc(result.name)}, paper Table ${result.table}. Higher is better for up arrows, lower for down arrows. Distance from prior is descriptive.</caption><thead><tr><th scope="col">Method</th>${result.metrics.map((m,i)=>`<th scope="col">${esc(m.label)} ${i === 2 && result.table === 1 ? '' : m.direction === 'up' ? '↑' : '↓'}</th>`).join('')}</tr></thead><tbody>${result.rows.map(row=>`<tr class="${row.method === 'LFD' ? 'ours' : ''}"><th scope="row">${esc(row.method === 'LFD' ? 'LFD · ours' : row.method)}</th>${row.values.map(([mean,error],i)=>`<td class="${!(i === 2 && result.table === 1) && mean === best[i] ? 'best' : ''}"><span class="table-mean">${mean.toFixed(2)}</span> <span class="table-uncertainty">± ${error.toFixed(2)}</span></td>`).join('')}</tr>`).join('')}</tbody>`;
    $('#results-table-note').textContent = 'Means and ± terms are preserved from the paper. These are computational evaluations; see the paper for evaluation and checkpoint-selection details.';
  }
  const dockingMetrics = [
    {label:'GNINA', tick:'GNINA<br>(pK)', unit:' pK'},
    {label:'Vina', tick:'|Vina|<br>(kcal/mol)', unit:' kcal/mol'},
    {label:'rDock', tick:'|rDock|', unit:''}
  ];
  function dockingMarkup(result) {
    const uncertainty=window.LFD_DATA.resultPanels.dockingDisplay;
    return `${legend(result.rows.map(row=>row.method),true)}<figure class="task-docking"><h4>Docking score comparison</h4><div class="docking-chart-scroll" tabindex="0" role="region" aria-label="Docking scores; scroll horizontally on small screens"><div id="docking-chart" class="interactive-chart docking-bar-chart" role="region" aria-label="Interactive ${esc(result.name)} docking score bars"></div></div><p class="chart-scroll-hint">Scroll horizontally for all three scores.</p><p id="docking-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a bar to inspect its score and uncertainty.</p><figcaption>Vina and rDock are shown as absolute values of their negative scores. Higher bars are better within each score; units differ between scores. ${esc(uncertainty.caption)}</figcaption></figure>`;
  }
  function molecularExample(task) {
    if (task.id !== 'd2' && task.id !== 'gsk3b') return '';
    const d2=task.id === 'd2';
    const file=`assets/${d2 ? 'd2' : 'gsk3b'}-docking.png`;
    return `<figure class="task-molecule"><a href="${file}" target="_blank" rel="noopener" aria-label="Open the ${esc(task.name)} docking figure at full resolution"><img src="${file}" width="${d2 ? 772 : 776}" height="${d2 ? 424 : 396}" alt="${esc(task.name)}: LFD-generated molecular structure and computational docking pose" loading="lazy"></a><figcaption>Illustrative LFD molecule and computational docking pose.</figcaption></figure>`;
  }
  function renderDiscoverySummary() {
    const evidence=window.LFD_DATA.resultPanels.oodEvidence;
    const figure=evidence.figure;
    $('#result-discovery').innerHTML=`<div class="discovery-summary"><div class="discovery-comparison"><div class="discovery-prior"><span class="metric-policy">Pretrained FlowMol3</span><div class="discovery-zero">0 <span>/ ${evidence.pretrained.attempts.toLocaleString('en-US')}</span></div><p>samples satisfy the full goal</p></div><div class="discovery-hit"><span class="metric-policy">LFD-adapted FlowMol3</span><strong>A full-goal hit</strong><p>Round ${evidence.lfd.round} · a ${evidence.lfd.batchSize}-sample batch</p></div></div><figure class="goal5-hit"><a href="${esc(figure.file)}" target="_blank" rel="noopener" aria-label="Open the Goal 5 hit figure at full resolution"><img src="${esc(figure.file)}" width="${figure.width}" height="${figure.height}" alt="LFD-generated Goal 5 hit, with the required structural features annotated" loading="lazy"></a><figcaption>The reported structure satisfying Goal 5.</figcaption></figure></div>`;
  }
  function renderTaskContext(goal) {
    const example=molecularExample(goal);
    $('#task-result-context').innerHTML=`<div class="task-context-grid ${example ? 'context-with-molecule' : ''}"><div class="task-context-copy"><div class="proxy-context"><h4>Direct proxy baselines</h4><p>${esc(goal.proxy)}</p></div><div class="observable-context"><h4>What the LLM sees</h4><p>${esc(goal.observableSummary)}</p><details class="observable-details"><summary>Observable list <span>${goal.observables.length} inputs <span aria-hidden="true">+</span></span></summary><ul>${goal.observables.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></details></div></div>${example}</div><div class="context-source"><a href="assets/paper.pdf#page=${goal.appendixPages[0]}" target="_blank" rel="noopener">Task details · Appendix D <span aria-hidden="true">↗</span></a></div>`;
  }
  function curriculumLabel(stage) {
    return stage.id==='g' ? stage.rounds===0 ? 'Final assessment' : 'Final goal' : 'g'+stage.id.slice(1);
  }
  function showCurriculumStage(task, id) {
    const stage=task.stages.find(item=>item.id===id);
    const controls=$('#task-result-curriculum');
    controls.dataset.selectedStage=id;
    controls.querySelectorAll('[data-curriculum-stage]').forEach(button=>{
      const selected=button.dataset.curriculumStage===id;
      button.setAttribute('aria-selected',String(selected));
      button.tabIndex=selected ? 0 : -1;
    });
    const preview=$('#result-curriculum-preview');
    preview.setAttribute('aria-labelledby',`curriculum-${task.id}-${id}`);
    const rounds=stage.rounds===0 ? 'Assessment only' : `${stage.rounds} training ${stage.rounds===1 ? 'round' : 'rounds'}`;
    preview.innerHTML=`<div class="curriculum-preview-heading"><h5>${esc(stage.title)}</h5><span>${esc(rounds)}</span></div><p>${esc(stage.exactGoal)}</p><div class="curriculum-preview-links"><span>${stage.id==='g' ? 'Original goal · verbatim' : 'LLM subgoal · verbatim'}</span><a href="#explorer?task=${encodeURIComponent(task.id)}&stage=${encodeURIComponent(id)}&tab=traces">Inspect judge traces <span aria-hidden="true">↗</span></a></div>`;
  }
  function renderCurriculum(task) {
    const target=$('#task-result-curriculum');
    target.dataset.curriculumTask=task.id;
    target.innerHTML=`<div class="curriculum-heading"><h4>Explore the subgoals</h4><span>${task.stages.filter(stage=>stage.id!=='g').length} intermediate subgoals</span></div><div class="curriculum-tabs" role="tablist" aria-label="${esc(task.name)} curriculum">${task.stages.map((stage,index)=>`<button id="curriculum-${task.id}-${stage.id}" type="button" role="tab" data-curriculum-stage="${stage.id}" aria-selected="${index===0}" aria-controls="result-curriculum-preview" aria-label="${esc(curriculumLabel(stage)+': '+stage.title)}" tabindex="${index===0 ? 0 : -1}">${stage.id==='g' ? esc(curriculumLabel(stage)) : 'g<sub>'+esc(stage.id.slice(1))+'</sub>'}</button>`).join('')}</div><div id="result-curriculum-preview" class="curriculum-preview" role="tabpanel" aria-labelledby="curriculum-${task.id}-${task.stages[0].id}"></div>`;
    showCurriculumStage(task,task.stages[0].id);
  }
  function renderOODTable() {
    const evidence = window.LFD_DATA.resultPanels.oodEvidence;
    $('#results-table-title').textContent = 'Reported discovery evidence';
    $('#results-table').innerHTML = `<caption class="sr-only">Constrained molecular design, paper Figure 9. Sampling budgets differ.</caption><thead><tr><th scope="col">Generator</th><th scope="col">Full-goal outcome</th><th scope="col">Samples</th><th scope="col">Round</th></tr></thead><tbody><tr><th scope="row">Pre-trained</th><td>0 full-goal hits</td><td>${evidence.pretrained.attempts.toLocaleString('en-US')}</td><td>—</td></tr><tr class="ours"><th scope="row">LFD · ours</th><td>${esc(evidence.lfd.outcome)}</td><td>${evidence.lfd.batchSize}-sample batch</td><td>${evidence.lfd.round}</td></tr></tbody>`;
    $('#results-table-note').textContent = evidence.caveat;
  }
  function renderOOD(task) {
    const points=[];
    let round=0;
    task.stages.filter(stage=>stage.rounds>0).forEach((stage,index)=>{
      for (let i=0;i<stage.rounds;i++) points.push({round:++round,index,title:stage.title,summary:stage.exactGoal});
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
    cards.innerHTML=goals.map((goal,index)=>`<button id="result-card-${esc(goal.id)}" class="result-card" role="tab" aria-selected="${index===0}" aria-controls="task-results-panel" aria-labelledby="result-number-${esc(goal.id)} result-name-${esc(goal.id)}" aria-describedby="result-goal-${esc(goal.id)}" tabindex="${index===0 ? 0 : -1}" data-result-task="${esc(goal.id)}" data-generator="${esc(goal.generator)}"><span class="goal-card-heading"><span id="result-number-${esc(goal.id)}" class="goal-number">Goal ${goal.number}</span><span class="goal-card-state" aria-hidden="true">${index===0 ? 'Selected' : '↗'}</span></span><span class="card-generator">${esc(goal.generator)} · ${esc(goal.domain.toLowerCase())}</span><strong id="result-name-${esc(goal.id)}" class="result-task-name">${esc(goal.name)}</strong><span id="result-goal-${esc(goal.id)}" class="result-goal">${esc(goal.goal)}</span></button>`).join('');
    function render(id) {
      active=id;
      const current=++generation;
      const goal=goals.find(task=>task.id===id);
      const task=data.tasks.find(task=>task.id===id);
      const result=results.find(result=>result.id===id);
      panel.dataset.selectedTask=id;
      panel.dataset.generator=goal.generator;
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
      $('#result-generator').dataset.generator=goal.generator;
      $('#result-generator').textContent=goal.generator+' · '+goal.domain.toLowerCase();
      $('#task-result-description').textContent=goal.description;
      $('#result-discovery').innerHTML='';
      if (!result) renderDiscoverySummary();
      renderTaskContext(goal);
      renderCurriculum(task);
      $('#result-source').textContent=`GOAL ${goal.number} · ${result ? 'TABLE '+result.table : 'FIGURE 9'}`;
      if (result && result.table===2) {
        $('#task-results-plots').innerHTML=dockingMarkup(result);
        $('#task-results-evidence').innerHTML='';
        renderTable(result);
      } else if (id==='ood') {
        $('#task-results-plots').innerHTML='<figure class="task-scatter"><h4>From intermediate subgoals to the full goal</h4><div class="plot-key" aria-label="Curriculum markers"><span><svg viewBox="0 0 16 16" width="15" height="15" fill="#8732ad" aria-hidden="true"><circle cx="8" cy="8" r="5"/></svg>Curriculum subgoal</span><span><svg viewBox="0 0 16 16" width="15" height="15" fill="#c54b59" aria-hidden="true"><rect x="3" y="3" width="10" height="10"/></svg>Final-goal assessment</span></div><div id="curriculum-chart" class="interactive-chart" role="region" aria-label="Interactive constrained-design curriculum"></div><p id="curriculum-readout" class="chart-readout" role="status" aria-live="polite">Hover or tap a round to inspect the active subgoal.</p><figcaption>Six recorded training rounds; the full-goal assessment at round 6 uses no additional training update.</figcaption></figure>';
        $('#task-results-evidence').innerHTML='<div class="chart-data-links"><a href="#explorer?task=ood&stage=g&tab=traces">Inspect the recorded discovery example ↗</a></div>';
        renderOODTable();
      } else {
        $('#task-results-plots').innerHTML=scatterMarkup(result);
        $('#task-results-evidence').innerHTML='';
        renderTable(result);
      }
      fonts.then(()=>{
        if (current!==generation) return;
        const work=result && result.table===2 ? renderDockingBars(result) : id==='ood' ? renderOOD(task) : renderScatter(result);
        return Promise.resolve(work).then(()=>{if (current===generation) panel.dataset.plotReadyTask=id;});
      });
    }
    $('#task-result-curriculum').addEventListener('click',event=>{
      const button=event.target.closest('[data-curriculum-stage]');
      if (!button) return;
      const task=data.tasks.find(task=>task.id===active);
      showCurriculumStage(task,button.dataset.curriculumStage);
    });
    $('#task-result-curriculum').addEventListener('keydown',event=>{
      if (!event.target.matches('[data-curriculum-stage]')) return;
      const task=data.tasks.find(task=>task.id===active);
      const index=task.stages.findIndex(stage=>stage.id===$('#task-result-curriculum').dataset.selectedStage);
      let next;
      if (event.key==='ArrowRight' || event.key==='ArrowDown') next=(index+1)%task.stages.length;
      if (event.key==='ArrowLeft' || event.key==='ArrowUp') next=(index+task.stages.length-1)%task.stages.length;
      if (event.key==='Home') next=0;
      if (event.key==='End') next=task.stages.length-1;
      if (next==null) return;
      event.preventDefault();
      showCurriculumStage(task,task.stages[next].id);
      $('#curriculum-'+task.id+'-'+task.stages[next].id).focus({preventScroll:true});
    });
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
  function renderDockingBars(result) {
    const uncertainty=window.LFD_DATA.resultPanels.dockingDisplay;
    const traces=result.rows.map(row=>({
      type:'bar',name:row.method,x:dockingMetrics.map(metric=>metric.tick),y:row.values.map(([mean])=>Math.abs(mean)),
      marker:{color:style(row.method).color},
      error_y:{type:'data',array:row.values.map(([,spread])=>spread),visible:true,color:style(row.method).color,thickness:1.6,width:4},
      customdata:row.values.map(([mean,spread],index)=>[mean,spread,dockingMetrics[index].label,dockingMetrics[index].unit]),
      hovertemplate:`<b>${esc(row.method)}</b><br>%{customdata[2]}: %{customdata[0]:.2f}%{customdata[3]}<br>Displayed magnitude: %{y:.2f}<br>${esc(uncertainty.label)}: ± %{customdata[1]:.2f}<extra></extra>`
    }));
    const max=Math.max(...result.rows.flatMap(row=>row.values.map(([mean,spread])=>Math.abs(mean)+spread)));
    return draw('#docking-chart',traces,layout({
      barmode:'group',bargap:.26,bargroupgap:.12,margin:{l:54,r:18,t:25,b:75},
      xaxis:{fixedrange:true,type:'category',categoryorder:'array',categoryarray:dockingMetrics.map(metric=>metric.tick),tickfont:{size:12},automargin:true},
      yaxis:{fixedrange:true,title:{text:'Score (metric-specific units)',standoff:12},range:[0,max*1.1],gridcolor:'#eceef2',zeroline:false,automargin:true}
    }),point=>{
      const row=result.rows[point.curveNumber],index=point.pointIndex;
      const [mean,spread]=row.values[index],metric=dockingMetrics[index];
      $('#docking-readout').innerHTML=`<strong>${esc(row.method)} · ${metric.label}</strong> · Original score: ${interval(mean,spread)}${metric.unit} · Plotted magnitude: ${Math.abs(mean).toFixed(2)} · ${esc(uncertainty.label)}`;
    });
  }
  window.LFD_RESULTS = {init};
})();

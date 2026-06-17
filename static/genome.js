let simulation, svg, g;

async function loadTree(filter) {
  const url = filter
    ? `/api/genome/tree?model=${encodeURIComponent(filter)}`
    : '/api/genome/tree';
  const data = await fetch(url).then(r => r.json());
  renderGraph(data);
}

function renderGraph(data) {
  const el = document.getElementById('graph');
  el.innerHTML = '';
  const W = el.clientWidth || window.innerWidth;
  const H = el.clientHeight || window.innerHeight - 140;

  svg = d3.select('#graph').append('svg')
    .attr('width', W).attr('height', H);

  // Arrow markers
  svg.append('defs').selectAll('marker')
    .data(['fine_tuned_from', 'distilled_from', 'merged_from', 'trained_from'])
    .join('marker')
      .attr('id', d => `arrow-${d}`)
      .attr('viewBox', '0 -5 10 10').attr('refX', 22).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
    .append('path').attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', d => ({
        fine_tuned_from: '#58a6ff', distilled_from: '#3fb950',
        merged_from: '#f85149', trained_from: '#e3b341'
      })[d] || '#888');

  g = svg.append('g');

  // Zoom
  svg.call(d3.zoom().scaleExtent([0.1, 4])
    .on('zoom', e => g.attr('transform', e.transform)));

  const link = g.append('g').selectAll('line')
    .data(data.links).join('line')
      .attr('stroke', d => d.color || '#888')
      .attr('stroke-width', 1.5).attr('stroke-opacity', 0.7)
      .attr('marker-end', d => `url(#arrow-${d.relation})`);

  const nodeGroup = g.append('g').selectAll('g')
    .data(data.nodes).join('g').attr('class', 'node')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  const familyColors = {
    'Llama 3': '#58a6ff', 'Llama 3.2': '#79c0ff',
    'Qwen 2.5': '#3fb950', 'Qwen 3': '#56d364',
    'Mistral': '#e3b341', 'Mixtral': '#d29922',
    'Gemma 2': '#bc8cff', 'Gemma 3': '#a371f7',
    'Phi': '#ff7b72', 'DeepSeek R1': '#ffa657',
    'Code Llama': '#79c0ff', 'Hermes': '#58a6ff',
  };

  nodeGroup.append('circle')
    .attr('r', d => Math.max(8, Math.min(24, ((d.params_b || 1) * 0.8))))
    .attr('fill', d => d.type === 'local' ? '#f85149' : '#21262d')
    .attr('stroke', d => familyColors[d.family] || '#888')
    .attr('stroke-width', 2);

  nodeGroup.append('text')
    .attr('dy', d => -Math.max(8, Math.min(24, ((d.params_b || 1) * 0.8))) - 4)
    .attr('text-anchor', 'middle')
    .attr('font-size', '11px').attr('fill', '#e6edf3')
    .text(d => d.name.length > 22 ? d.name.slice(0, 20) + '…' : d.name);

  // Tooltip
  const tooltip = document.getElementById('tooltip');
  nodeGroup.on('mouseover', (e, d) => {
    const pb = d.params_b || 0;
    tooltip.innerHTML = `
      <strong>${d.name}</strong><br>
      Family: ${d.family || '?'} | Org: ${d.org || '?'}<br>
      ${pb ? `Params: ${pb}B<br>` : ''}
      ${d.type === 'local' ? `<span style="color:#f85149">📦 Local | ${d.confidence || '?'}</span>` : ''}
    `;
    tooltip.style.opacity = '1';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  }).on('mousemove', e => {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  }).on('mouseout', () => { tooltip.style.opacity = '0'; });

  if (simulation) simulation.stop();
  simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).id(d => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(30))
    .on('tick', () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

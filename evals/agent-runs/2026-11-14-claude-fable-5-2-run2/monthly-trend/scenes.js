// 折线图：12 个月的走势。画面只由 t 决定。
export default {
  line(scene, root, kit) {
    const { svg, ease, clamp, chartHead } = kit;
    chartHead(scene, root);

    const W = 1640;
    const H = 600;
    const L = 90;
    const R = 1600;
    const T = 70;
    const B = 520;
    const items = scene.series || [];
    const n = items.length;
    const ticks = scene.ticks || [];
    const top = Math.max(...ticks, ...items.map((it) => it.value));
    const px = (i) => L + ((R - L) * i) / Math.max(1, n - 1);
    const py = (v) => B - ((B - T) * v) / top;

    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'margin-top:14px;flex:none' }, root);

    // 坐标轴：刻度不是事实数字，整组标成 tick
    const axis = svg('g', { 'data-df-role': 'tick' }, chart);
    for (const v of ticks) {
      svg('line', { x1: L, x2: R, y1: py(v), y2: py(v), style: 'stroke:var(--track);stroke-width:2' }, axis);
      const tx = svg('text', { x: L - 22, y: py(v) + 8, 'text-anchor': 'end', style: 'fill:var(--muted);font-size:24px' }, axis);
      tx.textContent = String(v);
    }
    items.forEach((it, i) => {
      const tx = svg('text', { x: px(i), y: B + 46, 'text-anchor': 'middle', style: 'fill:var(--muted);font-size:24px' }, axis);
      tx.textContent = it.label;
    });

    // 折线，用裁剪矩形从左到右揭开
    const clipId = `clip-${scene.id}`;
    const defs = svg('defs', {}, chart);
    const clip = svg('clipPath', { id: clipId }, defs);
    const clipRect = svg('rect', { x: 0, y: 0, width: 0, height: H }, clip);
    svg(
      'polyline',
      {
        points: items.map((it, i) => `${px(i)},${py(it.value)}`).join(' '),
        'clip-path': `url(#${clipId})`,
        style: 'fill:none;stroke:var(--accent);stroke-width:6;stroke-linejoin:round;stroke-linecap:round',
      },
      chart,
    );

    // 每个月一个点，标上数值
    const dots = items.map((it, i) =>
      svg(
        'circle',
        { cx: px(i), cy: py(it.value), r: 9, 'data-df-value': it.value, style: 'fill:var(--accent);stroke:var(--bg);stroke-width:3' },
        chart,
      ),
    );

    // 需要标在图上的数量；place 决定标签相对于点的位置
    const place = scene.place || {};
    const labels = (scene.callouts || []).map((c) => {
      const i = items.findIndex((it) => it.label === c.label);
      const pos = place[c.label] || 'above';
      const x = px(i);
      const y = py(c.value);
      const at =
        pos === 'below' ? { x, y: y + 48, anchor: 'middle' }
        : pos === 'left' ? { x: x - 22, y: y - 6, anchor: 'end' }
        : pos === 'above-right' ? { x: x - 4, y: y - 24, anchor: 'start' }
        : { x, y: y - 24, anchor: 'middle' };
      const hl = c.label === scene.highlight;
      const el = svg(
        'text',
        { x: at.x, y: at.y, 'text-anchor': at.anchor, style: `fill:var(${hl ? '--accent' : '--text'});font-size:${hl ? 40 : 32}px;font-weight:700` },
        chart,
      );
      el.textContent = `${c.label} ${c.value}`;
      return { el, i };
    });

    // reveal[k] = 第 k 句旁白结束时折线画到第几个月（从 0 数）
    const reveal = scene.reveal || [];

    return (t, lines) => {
      let rev = n - 1;
      if (lines.length && reveal.length === lines.length) {
        rev = 0;
        let from = 0;
        for (let k = 0; k < lines.length; k++) {
          const span = Math.max(0.4, Math.min(lines[k].end - lines[k].start - 0.3, 3.2));
          const p = ease((t - lines[k].start) / span);
          rev = from + (reveal[k] - from) * p;
          if (p < 1) break;
          from = reveal[k];
        }
      } else {
        rev = (n - 1) * ease((t - 0.4) / 4);
      }
      const intro = ease((t - 0.1) / 0.5);
      axis.style.opacity = String(intro);
      clipRect.setAttribute('width', String(px(rev) + 4));
      dots.forEach((d, i) => {
        d.style.opacity = String(intro * clamp((rev - i) * 4 + 1));
      });
      labels.forEach(({ el, i }) => {
        el.style.opacity = String(intro * ease((rev - i) * 3 + 1));
      });
    };
  },
};

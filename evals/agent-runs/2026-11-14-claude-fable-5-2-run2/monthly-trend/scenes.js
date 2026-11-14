// 折线图：12 个月的走势。画面只由 t 决定。
export default {
  line(scene, root, kit) {
    const { svg, clamp, chartHead } = kit;
    chartHead(scene, root);
    const W = 1640;
    const H = 560;
    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'margin-top:24px;overflow:visible' }, root);

    const items = scene.series || [];
    const n = items.length;
    const max = Math.max(1, ...items.map((it) => it.value));
    const peak = items.findIndex((it) => it.value === max);
    const X0 = 70;
    const X1 = W - 70;
    const BASE = 470;
    const TOP = 96;
    const x = (i) => X0 + ((X1 - X0) * i) / Math.max(1, n - 1);
    const y = (v) => BASE - ((BASE - TOP) * v) / max;

    // 哪些月份标数值：film.json 里点名的月份，加上全年最高的月份
    const marked = new Set(scene.mark || []);
    if (peak >= 0) marked.add(items[peak].label);

    // 零基线
    svg('line', { x1: X0 - 30, x2: X1 + 30, y1: BASE, y2: BASE, style: 'stroke:var(--bar);stroke-width:2' }, chart);

    // 月份标签是坐标轴刻度
    const ticks = svg('g', { 'data-df-role': 'tick' }, chart);
    items.forEach((it, i) => {
      const hot = marked.has(it.label);
      const t = svg('text', {
        x: x(i), y: BASE + 46, 'text-anchor': 'middle',
        style: `font-size:26px;fill:var(${hot ? '--text' : '--muted'})`,
      }, ticks);
      t.textContent = it.label;
    });

    // 折线，用裁剪矩形从左到右揭开
    const clipId = `df-line-clip-${scene.id}`;
    const defs = svg('defs', {}, chart);
    const clipRect = svg('rect', { x: 0, y: 0, width: 0, height: H }, svg('clipPath', { id: clipId }, defs));
    const d = items.map((it, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(it.value).toFixed(1)}`).join(' ');
    svg('path', {
      d, 'clip-path': `url(#${clipId})`,
      style: 'fill:none;stroke:var(--accent);stroke-width:5;stroke-linejoin:round;stroke-linecap:round',
    }, chart);

    // 数据点与数值标签
    const points = items.map((it, i) => {
      const hot = marked.has(it.label);
      const cx = x(i);
      const cy = y(it.value);
      const dot = svg('circle', {
        cx, cy, r: hot ? 11 : 7, 'data-df-value': it.value,
        style: `fill:var(${hot ? '--accent' : '--bg'});stroke:var(--accent);stroke-width:4`,
      }, chart);
      const texts = [];
      if (hot) {
        // 标签放在折线不经过的一侧
        const prev = items[i - 1]?.value ?? it.value;
        const next = items[i + 1]?.value ?? it.value;
        let lx = cx;
        let ly = cy - 26;
        let anchor = 'middle';
        if (i === peak) {
          const cap = svg('text', { x: cx, y: cy - 72, 'text-anchor': 'middle', style: 'font-size:28px;fill:var(--muted)' }, chart);
          cap.textContent = '全年最高';
          texts.push(cap);
        } else if (next > it.value * 1.5) {
          ly = cy + 52; // 右侧陡升：放到点的下方
        } else if (it.value > prev * 1.5) {
          lx = cx - 24; // 左侧陡升：放到点的左上方
          ly = cy - 4;
          anchor = 'end';
        }
        const label = svg('text', {
          x: lx, y: ly, 'text-anchor': anchor,
          style: 'font-size:38px;font-weight:700;fill:var(--text)',
        }, chart);
        label.textContent = kit.fmt(it.value);
        texts.push(label);
      }
      return { dot, texts };
    });

    // 每句旁白把折线推进到一个月份
    const targets = (scene.reveal || []).map((label) => items.findIndex((it) => it.label === label)).filter((i) => i >= 0);

    return (t, lines) => {
      let p = 0; // 折线已经画到第几个点（可以是小数）
      if (lines.length && targets.length === lines.length) {
        let from = 0;
        for (let k = 0; k < lines.length; k++) {
          const line = lines[k];
          const span = Math.min(2.4, Math.max(0.6, (line.end - line.start) * 0.75));
          p = from + (targets[k] - from) * clamp((t - line.start) / span);
          if (t < line.start + span) break;
          from = targets[k];
        }
      } else {
        p = (n - 1) * clamp((t - 0.5) / 4);
      }
      clipRect.setAttribute('width', (x(p) + 3).toFixed(1));
      points.forEach((pt, i) => {
        const o = i === 0 ? 1 : clamp((p - (i - 0.3)) / 0.3);
        pt.dot.style.opacity = String(o);
        pt.texts.forEach((el) => {
          el.style.opacity = String(o);
        });
      });
    };
  },
};

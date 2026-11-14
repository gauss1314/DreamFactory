// 折线图场景：12 个月的每月新增作品数（内置场景没有折线图）
export default {
  line(scene, root, kit) {
    const { svg, clamp, fmt, chartHead } = kit;
    chartHead(scene, root); // 标题和副标题

    const data = scene.series; // 已填好的 [{label, value}]，共 12 行
    const n = data.length;
    const W = 1640;
    const H = 560;
    const padL = 130;
    const padR = 60;
    const padT = 60;
    const padB = 70;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const maxV = 600;
    const xOf = (i) => padL + (plotW * i) / (n - 1);
    const yOf = (v) => padT + plotH * (1 - v / maxV);

    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, root);

    // 刻度和网格：不是事实，标 tick
    for (let v = 0; v <= maxV; v += 100) {
      svg('line', {
        x1: padL, x2: W - padR, y1: yOf(v), y2: yOf(v),
        style: 'stroke: var(--track); stroke-width: 2',
      }, chart);
      const tk = svg('text', {
        x: padL - 16, y: yOf(v) + 8, 'text-anchor': 'end', 'data-df-role': 'tick',
        style: 'fill: var(--muted); font-size: 22px',
      }, chart);
      tk.textContent = fmt(v);
    }

    // 月份标签
    data.forEach((d, i) => {
      const m = svg('text', {
        x: xOf(i), y: H - 24, 'text-anchor': 'middle', 'data-df-role': 'tick',
        style: 'fill: var(--muted); font-size: 22px',
      }, chart);
      m.textContent = d.label;
    });

    // 折线：用 pathLength 归一化，靠 stroke-dashoffset 逐步画出来
    const dPath = data
      .map((d, i) => `${i ? 'L' : 'M'}${xOf(i).toFixed(1)} ${yOf(d.value).toFixed(1)}`)
      .join(' ');
    const line = svg('path', {
      d: dPath, pathLength: 1, fill: 'none',
      style: 'stroke: var(--accent); stroke-width: 6; stroke-linejoin: round; '
        + 'stroke-linecap: round; stroke-dasharray: 1 1; stroke-dashoffset: 1',
    }, chart);

    // 数据点：每个点标 data-df-value，按组区分
    const KEY = new Set([0, 8, 9, 10]); // 1月、9月、10月、11月
    const dots = data.map((d, i) => svg('circle', {
      cx: xOf(i), cy: yOf(d.value), r: KEY.has(i) ? 12 : 8,
      'data-df-value': d.value, 'data-df-group': 'monthly',
      style: `fill: ${KEY.has(i) ? 'var(--accent)' : 'var(--text)'}; opacity: 0`,
    }, chart));

    // 四个关键数值的标注：数据下标、对应旁白句序号、位置
    const callouts = [
      { i: 0, k: 0, anchor: 'start', dx: 16, dy: -40 },
      { i: 8, k: 1, anchor: 'end', dx: -16, dy: -14 },
      { i: 9, k: 2, anchor: 'end', dx: -16, dy: -14 },
      { i: 10, k: 3, anchor: 'end', dx: -16, dy: -14 },
    ].map((c) => {
      const el = svg('text', {
        x: xOf(c.i) + c.dx, y: yOf(data[c.i].value) + c.dy, 'text-anchor': c.anchor,
        style: 'fill: var(--text); font-size: 30px; font-weight: 600; opacity: 0',
      }, chart);
      const extra = c.i === 10 ? '（全年最高）' : '';
      el.textContent = `${data[c.i].label} ${fmt(data[c.i].value)} 件${extra}`;
      return { ...c, el };
    });

    // 每一帧只由 t 和旁白时间决定
    return (t, lines) => {
      const L = lines && lines.length ? lines : [{ start: 0, end: 1 }];
      const T = L[L.length - 1].end;
      const p = clamp(t / Math.max(T * 0.9, 0.001)); // 画线进度 0–1
      line.style.strokeDashoffset = String(1 - p);
      dots.forEach((c, i) => {
        c.style.opacity = p >= i / (n - 1) - 1e-9 ? '1' : '0';
      });
      callouts.forEach((c) => {
        const on = t >= L[c.k].start && p >= c.i / (n - 1) - 1e-9;
        c.el.style.opacity = on ? '1' : '0';
      });
    };
  },
};

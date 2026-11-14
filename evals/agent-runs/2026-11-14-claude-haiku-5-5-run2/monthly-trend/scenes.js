// 折线图场景：每月数量的走势。画面只由 t 决定。
export default {
  line(scene, root, kit) {
    const { svg, clamp, fmt, chartHead } = kit;
    chartHead(scene, root);

    const W = 1640;
    const H = 560;
    const pad = { l: 130, r: 70, t: 60, b: 70 };
    const pw = W - pad.l - pad.r;
    const ph = H - pad.t - pad.b;
    const pts = scene.series;
    const n = pts.length;
    const step = 100;
    const axisMax = Math.ceil(Math.max(...pts.map((p) => p.value)) / step) * step;
    const X = (i) => pad.l + (pw * i) / (n - 1);
    const Y = (v) => pad.t + ph - (ph * v) / axisMax;

    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, root);

    // 刻度线和纵轴刻度
    for (let v = 0; v <= axisMax; v += step) {
      svg('line', {
        x1: pad.l, x2: W - pad.r, y1: Y(v), y2: Y(v),
        'data-df-role': 'tick',
        style: 'stroke: var(--track); stroke-width: 2',
      }, chart);
      const tk = svg('text', {
        x: pad.l - 18, y: Y(v) + 8, 'text-anchor': 'end',
        'data-df-role': 'tick',
        style: 'fill: var(--muted); font-size: 22px',
      }, chart);
      tk.textContent = fmt(v);
    }

    // 横轴月份
    pts.forEach((p, i) => {
      const tk = svg('text', {
        x: X(i), y: H - 22, 'text-anchor': 'middle',
        'data-df-role': 'tick',
        style: 'fill: var(--muted); font-size: 22px',
      }, chart);
      tk.textContent = p.label;
    });

    // 折线
    const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.value).toFixed(1)}`).join(' ');
    const line = svg('path', {
      d, fill: 'none',
      style: 'stroke: var(--accent); stroke-width: 6; stroke-linejoin: round; stroke-linecap: round',
    }, chart);
    const len = line.getTotalLength();
    line.style.strokeDasharray = String(len);

    // 数据点
    const dots = pts.map((p, i) => svg('circle', {
      cx: X(i), cy: Y(p.value), r: 8,
      'data-df-group': 'monthly',
      'data-df-value': p.value,
      style: 'fill: var(--accent); opacity: 0',
    }, chart));

    // 四个要标出的数量：1月、9月、10月、11月（全年最高）
    const keys = ['1月', '9月', '10月', '11月'];
    const labels = keys.map((name) => {
      const i = pts.findIndex((p) => p.label === name);
      const p = pts[i];
      const dx = name === '10月' ? -18 : name === '1月' ? 14 : 0;
      const dy = name === '10月' ? 8 : name === '9月' ? 54 : -26;
      const anchor = name === '10月' ? 'end' : name === '1月' ? 'start' : 'middle';
      const el = svg('text', {
        x: X(i) + dx, y: Y(p.value) + dy, 'text-anchor': anchor,
        style: 'fill: var(--text); font-size: 30px; font-weight: 600; opacity: 0',
      }, chart);
      el.textContent = `${p.label} ${fmt(p.value)}件`;
      return { name, i, el };
    });

    return (t, lines) => {
      // 第一句旁白期间把折线画完
      const drawEnd = lines[0] ? lines[0].end : 4;
      const q = clamp(t / drawEnd);
      line.style.strokeDashoffset = String(len * (1 - q));
      dots.forEach((dot, i) => {
        dot.style.opacity = q * (n - 1) >= i ? '1' : '0';
      });
      // 每个数量在它所在的那句旁白开始前 0.3 秒出现
      labels.forEach(({ name, el }) => {
        const s = lines[keys.indexOf(name) + 1];
        const start = s ? s.start - 0.3 : 0;
        el.style.opacity = String(clamp((t - start) / 0.3));
      });
    };
  },
};

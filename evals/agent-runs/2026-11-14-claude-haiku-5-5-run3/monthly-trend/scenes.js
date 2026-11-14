// 折线场景：12 个月的走势。1 月、9 月、10 月、11 月的数量标在图上；画面只由 t 决定。
export default {
  line(scene, root, kit) {
    const { svg, ease, clamp, chartHead } = kit;
    chartHead(scene, root);

    const data = scene.series;
    const n = data.length;
    const W = 1640;
    const H = 560;
    const X0 = 150; // 第一个月的横坐标
    const X1 = 1580; // 最后一个月的横坐标
    const BASE = 480; // 零值所在的纵坐标
    const TOP = 40;
    const MAX = 600; // 纵轴上限，刻度每 100 一格
    const xOf = (i) => X0 + ((X1 - X0) * i) / (n - 1);
    const yOf = (v) => BASE - ((BASE - TOP) * v) / MAX;

    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, root);

    // 刻度和月份是坐标轴，不是事实，标 tick。
    for (let v = 0; v <= MAX; v += 100) {
      svg('line', { x1: X0, x2: X1, y1: yOf(v), y2: yOf(v), style: 'stroke: var(--track); stroke-width: 2' }, chart);
      const tick = svg(
        'text',
        { x: X0 - 26, y: yOf(v) + 8, 'text-anchor': 'end', 'data-df-role': 'tick', style: 'fill: var(--muted); font-size: 22px' },
        chart,
      );
      tick.textContent = String(v);
    }
    data.forEach((d, i) => {
      const lab = svg(
        'text',
        { x: xOf(i), y: BASE + 46, 'text-anchor': 'middle', 'data-df-role': 'tick', style: 'fill: var(--muted); font-size: 22px' },
        chart,
      );
      lab.textContent = d.label;
    });

    // 折线：pathLength 归一化为 1，靠虚线偏移逐步画出。
    const d = data.map((p, i) => `${i ? 'L' : 'M'}${xOf(i)} ${yOf(p.value)}`).join(' ');
    const path = svg(
      'path',
      {
        d,
        pathLength: 1,
        fill: 'none',
        style: 'stroke: var(--accent); stroke-width: 6; stroke-linejoin: round; stroke-linecap: round; stroke-dasharray: 1 2',
      },
      chart,
    );

    // 每个月一个点，标上数值，供检查核对高低。
    const dots = data.map((p, i) =>
      svg(
        'circle',
        { cx: xOf(i), cy: yOf(p.value), r: 7, 'data-df-value': p.value, 'data-df-group': 'monthly', style: 'fill: var(--accent)' },
        chart,
      ),
    );

    const at = (label) => data.findIndex((p) => p.label === label);
    const text = (str, x, y, anchor, color) => {
      const el = svg('text', { x, y, 'text-anchor': anchor, style: `fill: ${color}; font-size: 30px; font-weight: 700` }, chart);
      el.textContent = str;
      return el;
    };
    // 每个标注跟着它所在那句旁白出现（line 是旁白的序号，从 0 开始）。
    const note = (label, str, dy, anchor, color, line) => {
      const i = at(label);
      return { el: text(str, xOf(i), yOf(data[i].value) + dy, anchor, color), line };
    };
    const notes = [
      note('1月', String(data[at('1月')].value), -22, 'middle', 'var(--text)', 0),
      note('9月', String(data[at('9月')].value), 48, 'middle', 'var(--text)', 2),
      note('10月', String(data[at('10月')].value), -22, 'middle', 'var(--text)', 3),
      note('11月', String(data[at('11月')].value), -22, 'middle', 'var(--accent)', 4),
    ];
    const peak = at('11月');
    notes.push({
      el: text(`${data[peak].label} · 全年最高`, xOf(peak) - 30, yOf(data[peak].value) + 8, 'end', 'var(--accent)'),
      line: 4,
    });

    return (tl, lines) => {
      const start = (k) => (lines[k] ? lines[k].start : 0);
      const end = lines.length ? lines[lines.length - 1].end : 1;
      // 折线从开头画到最后一句讲完之前。
      const p = clamp((tl - 0.4) / Math.max(1, end - 1.2));
      path.style.strokeDashoffset = String(1 - p);
      const f = p * (n - 1); // 已经画到第几个月
      dots.forEach((c, i) => {
        c.style.opacity = String(clamp((f - i + 0.3) / 0.3));
      });
      for (const { el, line } of notes) el.style.opacity = String(ease((tl - start(line)) / 0.35));
    };
  },
};

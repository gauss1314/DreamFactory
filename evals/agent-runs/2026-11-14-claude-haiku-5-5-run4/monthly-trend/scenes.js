// 折线图场景：12 个月的新增作品数逐月画出；1月、9月、10月、11月、12月标数值。
// 画面只由 t 决定：线的走向由旁白每句的开始时刻（lines[k].start）逐段插值得到。
export default {
  line(scene, root, kit) {
    const { svg, clamp, chartHead } = kit;
    chartHead(scene, root);

    const W = 1640;
    const H = 560;
    const X0 = 150; // 第 1 个月的横坐标
    const X1 = 1560; // 第 12 个月的横坐标
    const YT = 40; // 数值 600 所在的纵坐标
    const YB = 470; // 数值 0 所在的纵坐标
    const VMAX = 600;

    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, root);
    const xOf = (i) => X0 + (i * (X1 - X0)) / 11;
    const yOf = (v) => YB - (v / VMAX) * (YB - YT);

    const rows = scene.series;
    const pts = rows.map((r, i) => ({ x: xOf(i), y: yOf(r.value), v: r.value, label: r.label }));

    // 刻度线和刻度数字（标为 tick，不当作事实核对）
    for (const v of [0, 200, 400, 600]) {
      const y = yOf(v);
      svg('line', { x1: X0, x2: X1, y1: y, y2: y, style: 'stroke:var(--track);stroke-width:2' }, chart);
      const tk = svg('text', { x: X0 - 24, y: y + 8, 'text-anchor': 'end', 'data-df-role': 'tick', style: 'fill:var(--muted);font-size:22px' }, chart);
      tk.textContent = String(v);
    }

    // 月份标签
    pts.forEach((p) => {
      const m = svg('text', { x: p.x, y: YB + 46, 'text-anchor': 'middle', 'data-df-role': 'tick', style: 'fill:var(--muted);font-size:24px' }, chart);
      m.textContent = p.label;
    });

    const line = svg('path', { fill: 'none', style: 'stroke:var(--accent);stroke-width:6;stroke-linejoin:round;stroke-linecap:round' }, chart);

    const dots = pts.map((p) =>
      svg('circle', { cx: p.x, cy: p.y, r: 9, 'data-df-group': 'monthly', 'data-df-value': p.v, style: 'fill:var(--accent)' }, chart),
    );

    // 关键月份的下标：1月、9月、10月、11月、12月
    const KEY = [0, 8, 9, 10, 11];
    // 标签位置：避开线段走向；9月、10月、11月的标签放在点的左上方，免得压在线上或与相邻标签重叠
    const place = {
      0: { dx: 0, dy: -26, anchor: 'middle' },
      8: { dx: -18, dy: -24, anchor: 'end' },
      9: { dx: -18, dy: -14, anchor: 'end' },
      10: { dx: -18, dy: -16, anchor: 'end' },
      11: { dx: 0, dy: -26, anchor: 'middle' },
    };
    const tags = KEY.map((i) => {
      const p = pts[i];
      const at = place[i];
      const el = svg('text', { x: p.x + at.dx, y: p.y + at.dy, 'text-anchor': at.anchor, style: 'fill:var(--text);font-size:30px;font-weight:600' }, chart);
      el.textContent = i === 10 ? `全年最高 ${p.v}件` : `${p.v}件`;
      return { i, el };
    });

    // 画线进行到的位置（以月份下标计），在旁白每句开始时到达对应月份
    const headAt = (t, lines) => {
      const times = KEY.map((_, k) => (lines && lines[k] ? lines[k].start : k * 3));
      if (t <= times[0]) return KEY[0];
      for (let k = 0; k < KEY.length - 1; k++) {
        if (t < times[k + 1]) {
          const f = clamp((t - times[k]) / Math.max(times[k + 1] - times[k], 0.001));
          return KEY[k] + (KEY[k + 1] - KEY[k]) * f;
        }
      }
      return KEY[KEY.length - 1];
    };

    return (t, lines) => {
      const h = headAt(t, lines);
      const n = Math.min(Math.floor(h), pts.length - 1);
      const f = h - n;
      let d = '';
      for (let i = 0; i <= n; i++) d += `${i === 0 ? 'M' : 'L'}${pts[i].x.toFixed(1)} ${pts[i].y.toFixed(1)} `;
      if (n < pts.length - 1 && f > 0) {
        const a = pts[n];
        const b = pts[n + 1];
        d += `L${(a.x + (b.x - a.x) * f).toFixed(1)} ${(a.y + (b.y - a.y) * f).toFixed(1)}`;
      }
      line.setAttribute('d', d.trim());
      dots.forEach((c, i) => c.setAttribute('opacity', clamp((h - i) * 10 + 1).toFixed(3)));
      tags.forEach(({ i, el }) => el.setAttribute('opacity', clamp((h - i) * 4 + 1).toFixed(3)));
    };
  },
};

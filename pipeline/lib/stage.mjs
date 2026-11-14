// The stage: a film's page open in headless Chromium. The page contract is small:
//   window.DF = { duration, seek(t) }   and   <html data-ready="1"> once fonts and DOM are in place.
// Text is read back from the live DOM, so checks see exactly what a viewer would.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { startServer } from './server.mjs';

const require = createRequire(import.meta.url);

export async function openStage({ outDir, vertical, draft = false }) {
  const { chromium } = require('playwright');
  const server = await startServer({ '/runtime/': vertical.runtimeDir, '/film/': path.join(outDir, 'build') });
  const browser = await chromium.launch();
  const scale = draft ? 0.5 : 1;
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: scale });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message || e)));
  await page.goto(`${server.origin}/runtime/index.html`);
  try {
    await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 15000 });
  } catch {
    await browser.close();
    await server.close();
    throw new Error(`the film page did not become ready${errors.length ? `: ${errors.join('; ')}` : ''}`);
  }
  return {
    page,
    scale,
    errors,
    seek: (t) => page.evaluate((x) => window.DF.seek(x), t),
    close: async () => {
      await browser.close();
      await server.close();
    },
  };
}

/** Runs in the page: every visible piece of text with its box, opacity, colour and role. */
function readTexts() {
  const root = document.getElementById('stage') || document.body;
  const ids = (window.__dfIds ||= new WeakMap());
  window.__dfSeq ||= 0;
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n.nodeValue.replace(/\s+/g, ' ').trim();
    const el = n.parentElement;
    if (!text || !el || el.getClientRects().length === 0) continue;
    let opacity = 1;
    let visible = true;
    let role = '';
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.display === 'none' || cs.visibility === 'hidden') {
        visible = false;
        break;
      }
      opacity *= parseFloat(cs.opacity);
      if (!role && a.dataset.dfRole) role = a.dataset.dfRole;
    }
    if (!visible || opacity < 0.02) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (!ids.has(el)) ids.set(el, ++window.__dfSeq);
    const cs = getComputedStyle(el);
    // A text box is as tall as the font's ascent plus descent, well over the glyphs themselves.
    // Trim it to the em square so neighbours are judged by where the ink is.
    const fontSize = parseFloat(cs.fontSize);
    const lineBox = range.getClientRects()[0];
    const inset = lineBox ? Math.max(0, (lineBox.height - fontSize) / 2) : 0;
    const boxEl = el.closest('[data-df-box]');
    const b = boxEl ? boxEl.getBoundingClientRect() : null;
    const sceneEl = el.closest('[data-scene]');
    out.push({
      id: ids.get(el),
      text,
      role,
      opacity: Math.round(opacity * 1000) / 1000,
      x: r.left,
      y: r.top + inset,
      w: r.width,
      h: r.height - 2 * inset,
      color: cs.color,
      fontSize,
      box: b ? { x: b.left, y: b.top, w: b.width, h: b.height } : null,
      scene: sceneEl ? sceneEl.dataset.scene : '',
    });
  }
  return out;
}

/** Runs in the page: contrast of each text against the pixels just outside its box, from a screenshot. */
async function measureContrast({ png, items, scale }) {
  const blob = await (await fetch(`data:image/png;base64,${png}`)).blob();
  const bmp = await createImageBitmap(blob);
  const canvas = new OffscreenCanvas(bmp.width, bmp.height);
  const g = canvas.getContext('2d', { willReadFrequently: true });
  g.drawImage(bmp, 0, 0);
  const W = bmp.width;
  const H = bmp.height;
  const px = g.getImageData(0, 0, W, H).data;
  const lin = (v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const median = (a) => a.sort((p, q) => p - q)[a.length >> 1];
  return items.map((it) => {
    const x0 = Math.round(it.x * scale) - 2;
    const y0 = Math.round(it.y * scale) - 2;
    const x1 = Math.round((it.x + it.w) * scale) + 2;
    const y1 = Math.round((it.y + it.h) * scale) + 2;
    const ch = [[], [], []];
    const take = (x, y) => {
      if (x < 0 || y < 0 || x >= W || y >= H) return;
      const i = (y * W + x) * 4;
      ch[0].push(px[i]);
      ch[1].push(px[i + 1]);
      ch[2].push(px[i + 2]);
    };
    for (let x = x0; x <= x1; x++) {
      take(x, y0);
      take(x, y1);
    }
    for (let y = y0; y <= y1; y++) {
      take(x0, y);
      take(x1, y);
    }
    if (!ch[0].length) return { id: it.id, ratio: null };
    const bg = ch.map(median);
    const [r, gg, b, a = 1] = (it.color.match(/[\d.]+/g) || []).map(Number);
    const fg = [r, gg, b].map((v, i) => v * a + bg[i] * (1 - a));
    const l1 = lum(fg);
    const l2 = lum(bg);
    return { id: it.id, ratio: Math.round(((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)) * 100) / 100 };
  });
}

/** Runs in the page: are CJK glyphs really drawn, or is the font falling back to empty boxes? */
function cjkGlyphsDraw() {
  const family = getComputedStyle(document.getElementById('stage') || document.body).fontFamily;
  const draw = (ch) => {
    const c = new OffscreenCanvas(64, 64);
    const g = c.getContext('2d');
    g.font = `48px ${family}`;
    g.textBaseline = 'top';
    g.fillText(ch, 4, 4);
    return g.getImageData(0, 0, 64, 64).data;
  };
  const glyph = draw('永');
  const missing = draw('￿');
  let ink = 0;
  let same = true;
  for (let i = 3; i < glyph.length; i += 4) {
    if (glyph[i]) ink++;
    if (glyph[i] !== missing[i]) same = false;
  }
  return ink > 0 && !same;
}

export const SAMPLE_STEP = 0.25;

/**
 * Walk the film once: read text on a fixed grid (plus the midpoint of every narration line and
 * scene), measure contrast once a second, and tile a contact sheet for the agent to look at.
 */
export async function sampleFilm(stage, timeline, { contactFile } = {}) {
  const times = new Map();
  const gridCount = Math.floor(timeline.duration / SAMPLE_STEP + 1e-6);
  for (let i = 0; i <= gridCount; i++) times.set(Math.min(i * SAMPLE_STEP, timeline.duration - 0.001).toFixed(3), { grid: true });
  for (const scene of timeline.scenes) {
    const mid = ((scene.start + scene.end) / 2).toFixed(3);
    if (!times.has(mid)) times.set(mid, { grid: false });
    for (const line of scene.lines) {
      const m = ((line.start + line.end) / 2).toFixed(3);
      if (!times.has(m)) times.set(m, { grid: false });
    }
  }
  const order = [...times.keys()].map(Number).sort((a, b) => a - b);

  const sheetEvery = Math.max(2, Math.ceil(timeline.duration / 24));
  let sheet = null;
  let sheetFrames = 0;
  if (contactFile) {
    const cols = 4;
    const rows = Math.ceil((Math.floor(timeline.duration / sheetEvery) + 1) / cols);
    sheet = spawn(
      'ffmpeg',
      ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '1', '-c:v', 'mjpeg', '-i', '-',
        '-vf', `scale=480:-2,tile=${cols}x${rows}:padding=6:margin=6:color=0x202020`, '-frames:v', '1', '-q:v', '3', contactFile],
      { stdio: ['pipe', 'ignore', 'pipe'] },
    );
    sheet.stdin.on('error', () => {});
  }

  const samples = [];
  for (const t of order) {
    await stage.seek(t);
    const texts = await stage.page.evaluate(readTexts);
    const meta = times.get(t.toFixed(3));
    const onSecond = meta.grid && Math.abs(t - Math.round(t)) < 1e-6;
    if (onSecond) {
      const settled = texts.filter((x) => x.opacity >= 0.95 && x.role !== 'animating');
      if (settled.length) {
        const png = (await stage.page.screenshot({ type: 'png' })).toString('base64');
        const ratios = await stage.page.evaluate(measureContrast, { png, items: settled, scale: stage.scale });
        const byId = new Map(ratios.map((r) => [r.id, r.ratio]));
        for (const x of settled) x.contrast = byId.get(x.id) ?? null;
      }
      if (sheet && Math.round(t) % sheetEvery === 0) {
        sheet.stdin.write(await stage.page.screenshot({ type: 'jpeg', quality: 85 }));
        sheetFrames++;
      }
    }
    samples.push({ t, grid: meta.grid, texts });
  }
  if (sheet) {
    await new Promise((resolve) => {
      sheet.on('close', resolve);
      sheet.stdin.end();
    });
  }
  const cjkOk = await stage.page.evaluate(cjkGlyphsDraw);
  return { samples, cjkOk, sheetFrames, pageErrors: stage.errors };
}

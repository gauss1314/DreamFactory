import * as dom from './dom.mjs';
import * as media from './media.mjs';

export const CHECKS = [
  dom.spec,
  dom.dataAccuracy,
  dom.citation,
  dom.readability,
  dom.layout,
  dom.contrast,
  dom.subtitles,
  dom.sync,
  dom.typography,
  dom.emptyFrames,
  dom.marks,
  dom.determinism,
  dom.heading,
  dom.contact,
  dom.landing,
  dom.edges,
  dom.fonts,
  media.videoStillness,
  media.audioLevels,
  media.audioGaps,
  media.asr,
  media.pops,
  media.palette,
  media.cueSync,
  media.voiceOverMusic,
];

/** Run the checks that apply. Media checks need a rendered film; `only` narrows to given ids. */
export async function runChecks(ctx, { only, timing } = {}) {
  const results = [];
  for (const check of CHECKS) {
    if (only && !only.includes(check.id)) continue;
    if (check.tier === 'media' && !ctx.video) continue;
    let r;
    try {
      r = await check.run(ctx);
    } catch (e) {
      r = { status: 'fail', summary: `检查本身出错：${String(e.message || e).split('\n')[0]}`, details: [] };
    }
    results.push({ id: check.id, title: check.title, tier: check.tier, ...r });
    timing?.(`check ${check.id}`);
  }
  return results;
}

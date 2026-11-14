#!/usr/bin/env node
// Agent-facing entry point. Exit code: 0 all checks pass, 1 some check failed, 2 the run itself broke.
import fs from 'node:fs';
import path from 'node:path';
import { runFilm } from './film.mjs';

const USAGE = `用法：node pipeline/cli.mjs run <影片目录> [选项]

  影片目录里要有 film.json 和 data.json，可选 expect.json。产物写到 <影片目录>/out/。

选项：
  --draft               草稿画质（半分辨率、15 帧），返工阶段用，快
  --no-video            不渲染视频，只做文字层检查，最快
  --tts <后端>          auto（默认）| espeak | edge | silent
  --only <a,b>          只跑指定的检查
  --cost-usd <数字>     记录这一轮花掉的模型费用
  --intervention <说明> 记录一次人工介入
`;

const args = process.argv.slice(2);
if (args[0] !== 'run' || !args[1] || args.includes('--help')) {
  console.log(USAGE);
  process.exit(args.includes('--help') ? 0 : 2);
}
const value = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
};

const filmDir = path.resolve(args[1]);
try {
  const report = await runFilm(filmDir, {
    draft: args.includes('--draft'),
    video: !args.includes('--no-video'),
    tts: value('--tts'),
    only: value('--only')?.split(','),
    costUsd: value('--cost-usd') != null ? Number(value('--cost-usd')) : undefined,
    intervention: value('--intervention'),
  });
  process.stdout.write(fs.readFileSync(path.join(filmDir, 'out', 'report.md'), 'utf8'));
  process.exit(report.passed ? 0 : 1);
} catch (e) {
  console.error(`运行失败：${e.message}`);
  process.exit(2);
}

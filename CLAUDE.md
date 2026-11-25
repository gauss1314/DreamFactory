# DreamFactory

用代码做视频的管线。第一条垂直管线是数据故事短片：一份简报加一份数据，产出一支带旁白的数据讲解视频，并用自检把关。背景和判断见 `docs/llm-video-game-research.md`。

## 常用命令

```bash
node pipeline/cli.mjs run <影片目录> --no-video   # 只做文字层检查，十几秒
node pipeline/cli.mjs run <影片目录> --draft      # 草稿画质，带视频和声音检查
node pipeline/cli.mjs run <影片目录>              # 成片
node evals/run.mjs                                # 跑评测集：画面没改约四分钟，改了运行时约十五分钟
node evals/run.mjs --only <id,id>                 # 只跑指定的用例或缺陷
node evals/agent-run.mjs                          # 让模型无人值守做完每个用例，要花模型费用
node evals/review.mjs <影片目录>                   # 让另一个模型只看画面审片，列出要退回的地方
```

做数据短片之前先读 `DIRECTOR.md`，做叙事短片之前先读 `verticals/narrative/DIRECTOR.md`。

## 结构

- `pipeline/`：管线本体。`film.mjs` 是一次运行的全流程，`lib/` 是各个环节，`checks/` 是自检，`tools/asr.py` 是语音识别的 Python 小工具。
- `.cache/tts/`：合成过的语音和听写结果的缓存，不入库，删掉只会让下次运行慢一些。
- `verticals/narrative/`：叙事短片的画面引擎（`runtime/engine.js`）和美术规范 `ART.md`。一支叙事片的角色和镜头写在它自己的 `scenes.js`，配乐和音效写在 `sound.js`，画面事件的时刻只在 `film.json` 里写一次。
- `pipeline/lib/synth.mjs`：合成乐器、音效和混响，两条管线共用。
- `verticals/data-story/`：数据短片的画面。`ART.md` 是视觉规范，`runtime/` 按它实现，`runtime/df.js` 里每种场景是一个函数。影片目录里的 `scenes.js` 可以为那一支片子增加场景。
- `evals/cases/`：评测用例，每个目录有简报、数据、要求和一支参考影片，个别带参考的 `scenes.js`。
- `evals/defects.json`：缺陷注入集，每条在参考影片上改一处，并写明哪项检查必须失败。
- `evals/BASELINE.md`：上一次评测的结果。
- `evals/agent-run.mjs`：无人值守评测。模型只拿到简报、数据、要求和 `DIRECTOR.md`，看不到参考影片。
- `evals/agent-runs/`：每次无人值守运行交付的分镜、运行记录和汇总。

## 约定

- 改画面之前先改 `ART.md`，再改运行时。改完按 `ART.md` 第六节看抽帧图，并跑评测。
- 画面必须只由时间决定。`seek(t)` 里不能用时钟、随机数、CSS 动画，也不能依赖上一帧。
- 新增或修改一项检查，必须同时在 `evals/defects.json` 里加一条它应该抓到的缺陷，然后跑评测。没有缺陷样例的检查等于没有验证过。
- 改了管线或画面之后跑 `node evals/run.mjs`。干净用例出现失败是误报，要修检查或修参考影片，不能放宽到看不见为止。
- 页面上的文字靠 `data-df-role` 标注角色：`subtitle`、`source`、`tick`（刻度）、`animating`（跳动中的数字）。新场景里的刻度和跳动数字必须标注，否则会被当成事实去核对。
- 文字必须留在最近的 `data-df-box` 容器内，新场景要给会溢出的文字加上这个标记。
- 代表数据的图形要带 `data-df-value`，`marks` 检查靠它核对图形与数值是否一致。
- 缺陷可以改场景代码：`{"file": "scenes", "replace": "原文", "with": "改成"}`。改参考的 `scenes.js` 时要确认缺陷里引用的原文还在。
- 不引入 npm 依赖，除了 Playwright。在已经预装 Playwright 的云端环境里不要运行 `npm install`。
- 语音供应商都在 `pipeline/lib/tts.mjs`，一个后端一个函数。新增后端后跑一遍评测，参考影片的片长会随语速变化，贴着时长上下限的要调整参考影片，不要放宽要求。
- 评测默认用 `auto` 选中的语音。没有网络时加 `--tts espeak`，这时听写核对会跳过，对应的缺陷记为“未判定”。
- 每条垂直管线在 `vertical.mjs` 里列出自己要跑的检查。新增检查时要决定它属于哪条管线。
- 代码注释用英文，文档和报告用中文。
- `.cache/render/` 按画面的全部来源（分镜、场景代码、运行时、渲染和抽样代码）缓存渲染和抽样结果。只改声音或检查时，评测会复用画面，只重新混音。缓存不入库，删掉只会变慢；怀疑缓存有问题时设 `DF_RENDER_CACHE=off`。`DF_TIMING=1` 会打印每一步的用时。
- 叙事片的画面里不要在设了 `filter` 的画布上画很多笔，每一笔都会单独模糊一次，一帧能慢到几秒。先画进底版再整体模糊。
- 同一时间只跑一个 `node evals/run.mjs`：它启动时会清空共用的 `evals/.tmp/`，两个同时跑会互相删掉对方的文件。

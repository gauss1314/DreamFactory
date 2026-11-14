# DreamFactory

用代码做视频的管线。第一条垂直管线是数据故事短片：一份简报加一份数据，产出一支带旁白的数据讲解视频，并用自检把关。背景和判断见 `docs/llm-video-game-research.md`。

## 常用命令

```bash
node pipeline/cli.mjs run <影片目录> --no-video   # 只做文字层检查，十几秒
node pipeline/cli.mjs run <影片目录> --draft      # 草稿画质，带视频和声音检查
node pipeline/cli.mjs run <影片目录>              # 成片
node evals/run.mjs                                # 跑评测集，约两分钟
node evals/run.mjs --only <用例或缺陷的 id>
```

做片子之前先读 `DIRECTOR.md`。

## 结构

- `pipeline/`：管线本体。`film.mjs` 是一次运行的全流程，`lib/` 是各个环节，`checks/` 是自检。
- `verticals/data-story/`：数据短片的画面。`runtime/df.js` 里每种场景是一个函数。
- `evals/cases/`：评测用例，每个目录有简报、数据、要求和一支参考影片。
- `evals/defects.json`：缺陷注入集，每条在参考影片上改一处，并写明哪项检查必须失败。
- `evals/BASELINE.md`：上一次评测的结果。

## 约定

- 画面必须只由时间决定。`seek(t)` 里不能用时钟、随机数、CSS 动画，也不能依赖上一帧。
- 新增或修改一项检查，必须同时在 `evals/defects.json` 里加一条它应该抓到的缺陷，然后跑评测。没有缺陷样例的检查等于没有验证过。
- 改了管线或画面之后跑 `node evals/run.mjs`。干净用例出现失败是误报，要修检查或修参考影片，不能放宽到看不见为止。
- 页面上的文字靠 `data-df-role` 标注角色：`subtitle`、`source`、`tick`（刻度）、`animating`（跳动中的数字）。新场景里的刻度和跳动数字必须标注，否则会被当成事实去核对。
- 文字必须留在最近的 `data-df-box` 容器内，新场景要给会溢出的文字加上这个标记。
- 不引入 npm 依赖，除了 Playwright。在已经预装 Playwright 的云端环境里不要运行 `npm install`。
- 代码注释用英文，文档和报告用中文。

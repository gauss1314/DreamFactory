# 导演规范：数据故事短片

这份规范写给做片子的智能体。任务是把一份简报和一份数据，做成一支带旁白的数据短片，并让它通过自检。

## 流程

1. 读影片目录里的 `brief.md`、`data.json`、`expect.json`。
2. 写 `film.json`（字段见下文）。
3. 跑文字层检查，十几秒出结果：

   ```bash
   node pipeline/cli.mjs run <影片目录> --no-video
   ```

4. 读终端里的报告，再看 `out/contact.jpg` 抽帧图。报告只查得出能量化的问题，构图和节奏要靠看图。
5. 修 `film.json`，重跑。检查都通过后，渲染草稿并查画面和声音：

   ```bash
   node pipeline/cli.mjs run <影片目录> --draft
   ```

6. 草稿通过后，去掉 `--draft` 出成片，成片在 `out/film.mp4`。

最多返工 3 轮。3 轮后仍不通过，停下来把报告交给人，不要继续试。

## 硬性规则

- **数字只引用，不手写。** 来自数据的数字一律写成 `{{facts.total}}` 或 `{"$": "series.categories"}`。手写的数字只要不在 `data.json` 里，检查就会失败。
- **不要为了通过检查去改 `data.json` 或 `expect.json`。** 它们是任务给的事实和要求。确实需要一个数据里没有的数字（比如年份），停下来问人。
- **数字写阿拉伯数字。** 检查不认识“两千七百”这样的写法。
- **每句旁白不超过 30 个汉字**（英文 84 个字符），一句只讲一件事。长句拆开。
- **数字和拉丁字母单位之间留空格**，写 `220 KB`，不写 `220KB`。紧贴字母的数字会被当成名字的一部分，比如 `3D`。
- **有数据的片子必须写 `source`**，并包含 `data.json` 里的 `source.name`。
- **不要削弱检查。** 检查报错时改片子，不改 `pipeline/checks/`。认为检查本身错了，停下来说明理由。

## 记录

每跑一次，`out/runs.jsonl` 会记一轮。下面两项需要自己补：

```bash
# 人改了东西，或者人给了修改意见
node pipeline/cli.mjs run <影片目录> --no-video --intervention "把标题改短"

# 这一轮花掉的模型费用
node pipeline/cli.mjs run <影片目录> --draft --cost-usd 1.25
```

管线靠这三个数衡量：每分钟成片成本、返工轮数、人工介入次数。

## film.json

```json
{
  "vertical": "data-story",
  "lang": "zh",
  "title": "片名，只用于报告",
  "source": "数据来源：{{source.name}}（截至 {{source.asOf}}）",
  "theme": { "accent": "#62c6ff" },
  "voice": { "backend": "auto" },
  "scenes": []
}
```

- `lang`：`zh` 或 `en`，决定语音和字幕长度上限。
- `theme`：可选，可改 `bg`、`text`、`muted`、`accent`、`bar`、`track` 六个颜色。
- `voice.backend`：`auto`、`espeak`、`edge`、`silent`。

每个场景都可以带这些字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 场景名，出现在报告里 |
| `type` | 场景类型，见下表 |
| `narration` | 旁白，一句一个字符串；字幕与它逐句对应 |
| `minDuration` | 这个场景至少停留多少秒 |
| `duration` | 把场景固定为多少秒；短于旁白会报错 |

场景时长默认由旁白决定：旁白念多久，场景就停多久。

## 场景类型

| 类型 | 用途 | 专有字段 |
| --- | --- | --- |
| `title` | 开场 | `kicker`、`headline`、`sub` |
| `bignumber` | 强调一个数字 | `label`、`value`、`unit`、`note` |
| `bars` | 比较一组数量 | `title`、`sub`、`series`、`highlight`、`unit`、`showShare` |
| `ranges` | 比较一组区间，对数刻度 | `title`、`sub`、`series`、`highlight`、`unit`、`scale` |
| `bullets` | 几条结论 | `title`、`items` |
| `outro` | 收尾 | `headline`、`sub` |

- `bars` 的 `series` 是 `[{label, value}]`，`ranges` 的是 `[{label, low, high}]`，都应该引用数据。
- `highlight` 填一个 `label`，那一行用强调色。
- `showShare` 为真时，每行多显示占比。
- `bullets` 的条数和旁白句数相同时，每条会在对应那句旁白开始时出现。

## 数据引用

| 写法 | 得到 |
| --- | --- |
| `{"$": "series.categories"}` | 整个数组或对象 |
| `{{facts.total}}` | 一个数字；画面上带千分位，旁白里不带 |
| `{{series.categories[游戏]}}` | 按 `label` 取一行的 `value` |
| `{{series.cost[工作室].high}}` | 按 `label` 取一行里的某个字段 |
| `{{share series.categories[游戏]}}` | 这一行占整组的百分比，取整 |

可以出现的数字有三类：`data.json` 里的任何数字、每组数据的合计、每一行的占比。

## 检查失败时怎么改

| 检查 | 常见原因 | 改法 |
| --- | --- | --- |
| `data-accuracy` | 手写了数字，或漏了必须出现的数据 | 改成引用；对照 `expect.json` 的 `mustShow` 和 `mustSay` |
| `citation` | 没写 `source` | 补上，并包含 `source.name` |
| `readability` | 场景太短 | 加旁白，或设 `minDuration` |
| `layout` | 文字太长 | 缩短文字 |
| `contrast` | 改了主题色 | 换一个与背景差得更开的颜色 |
| `subtitles` | 旁白太长 | 拆成两句 |
| `empty-frames` | 场景没有内容 | 补内容，或删掉这个场景 |
| `video-stillness` | 一句旁白太长，画面一直不动 | 拆句，或把内容分到两个场景 |
| `audio-gaps` | 场景没有旁白，或 `minDuration` 远大于旁白 | 补旁白，或缩短 |
| `spec` | 片长超出要求 | 增删场景或旁白 |

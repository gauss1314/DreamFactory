# 导演规范：叙事短片

这份规范写给做叙事短片的智能体。任务是把一份简报做成一支手绘风的动画短片：画面、配乐和音效全部用代码生成，不用图片、字体和采样素材，并让它通过自检。

先读美术规范 `verticals/narrative/ART.md`：它规定片子长什么样、怎么动、声音怎么配。这份文件讲怎么做。

## 流程

1. 读任务目录里的 `brief.md` 和 `expect.json`，再读 `ART.md`。
2. 定镜头表和色彩脚本，写 `film.json`。
3. 写 `scenes.js`：角色和每个镜头的画法。能用引擎里现成的画法就用，不要自己重写天空、云、水、房子。
4. 写 `sound.js`：配乐和音效。
5. 跑一遍，十几秒出结果，并生成抽帧图：

   ```bash
   node pipeline/cli.mjs run task --no-video
   ```

6. 用读取工具看 `task/out/contact.jpg`（见下文“看图”）。按 `ART.md` 第六节写下最弱的三处，改掉。也要问：这个动作在现实里可能吗？
7. 渲染草稿，查画面和声音：

   ```bash
   node pipeline/cli.mjs run task --draft
   ```

最多返工 4 轮。仍不通过就停下，说明卡在哪里。终端输出的开头就是结论。运行本身出错时只有一行“运行失败”和原因，多半是代码写错了。

## film.json

```json
{
  "vertical": "narrative",
  "lang": "zh",
  "title": "片名",
  "tempo": 96,
  "finish": { "vignette": 0.34, "halation": 0.16, "grain": 0.06, "warm": "#ffd9a0" },
  "look": { "sky": [[0, "#3d4f8a"], [0.5, "#8a86b8"], [1, "#ffd99a"]] },
  "scenes": [
    { "id": "s1-wide", "type": "wide", "duration": 4.0, "fadeIn": 0.6 },
    { "id": "s2-close", "type": "close", "duration": 4.0, "events": { "knock": 2.5 } },
    { "id": "s3-end", "type": "end", "duration": 4.0, "fadeOut": 1.0, "events": { "bell": [1.0, 1.3] } }
  ]
}
```

- `type` 是 `scenes.js` 里一个镜头函数的名字。
- `duration` 是镜头的秒数。换镜头最好落在配乐的拍点或小节线上：`tempo` 是每分钟拍数。
- `events` 是这个镜头里要配声音的画面事件，单位是从镜头开始算起的秒数；一个名字可以对应几个时刻。同一个时刻，`scenes.js` 和 `sound.js` 都从这里读，不要在两边各写一遍。
- `look` 是这支片子的配色，没写的部分用引擎的默认值（晴朗的傍晚）。可设的键见 `runtime/painters.js` 开头的 `DEFAULT_LOOK`：`sky`、`cloud`、`water`、`grass`、`road`、`reeds`、`houseWalls`、`stone`、`cobble`、`lamp` 等。
- `finish` 是全片统一的成片质感：暗角、高光晕染、颗粒、暖色调。
- `contacts` 声明这个镜头里必须碰在一起的两点，写成 `["角色.点", "道具.点"]`；只在一段时间内成立的写成 `{ "a": "鹈鹕.hand", "b": "鹈鹕.bell", "from": 1.2, "to": 1.85 }`（镜头内秒数），默认相距不超过 12 像素，可以用 `max` 改。不该碰到的写 `{ "a": "刺猬.nose", "b": "推车.back", "min": 10 }`。**角色抓着、推着、骑着、叼着东西时必须声明。**
- `horizon` 是这个镜头的地平线在画面上的高度（像素）。只有当抛出去的东西要往镜头这边或远处飞时才需要写。

## scenes.js

```js
import { paintSky, paintClouds, path, cel, line, groundShadow } from '/runtime/painters.js';

export default {
  // 名字就是 film.json 里的 type
  wide(kit, scene) {
    // 这里只运行一次：把不动的背景画进一张底版
    const plate = kit.layer(1920, 1080);
    paintSky(kit, plate.g, 1920, 600, [1500, 520], 1);
    // 画面事件：scene.events.knock 是从镜头开始算的秒数
    // 密集的小动作（脚步）用 kit.cue 报告时刻，声音会照着放
    kit.cue('step1', 0.5, 'step', { minor: true });
    // 返回的函数每一帧调用一次，t 是镜头内的秒数
    return (g, t, dur) => {
      g.drawImage(plate.canvas, 0, 0);
      const x = 300 + t * 120;
      // 每一帧报告角色在地面上的位置、大小和朝向（朝向检查靠它），以及接触点（接触检查靠它）
      const points = character(kit, g, x, 900, 0.5, { phase: kit.twos(t) * 6 }); // 角色函数里用 kit.at 取点并返回
      kit.actor('角色', { x, y: 900, s: 0.5, facing: 'right', points });
    };
  },
};
```

规则，每条都有检查或会让运行失败：

- **画面只由 `t` 决定。** 不用 `Math.random()`、`Date`、定时器，不在两帧之间保留状态。随机要用 `kit.rng(种子)`。
- **角色一拍二。** 角色的动作用 `kit.twos(t)` 取时间，镜头运动用 `t`。
- **往哪儿走就朝哪儿。** 正侧面画的角色只能横着走，不能往纵深里走，也不能斜着走。每一帧都要用 `kit.actor()` 报告；坐标是角色在地面上的位置，跟拍镜头里要加上镜头移动的距离。
- **画面不能突然跳。** 剪辑点、淡入淡出和 `events` 里声明的时刻以外，相邻两帧不能有大的变化。
- **碰着的地方真的碰着。** 角色抓着、推着、骑着、叼着东西时，在报告里给出这几处的点，并在 `film.json` 的 `contacts` 里声明。点用 `kit.at(g, x, y)` 取：它把当前变换下的 (x, y) 换算成画面像素，所以在角色函数里、在 `g.translate`/`g.scale` 之后取都可以。两端各自取，不要把一端的坐标抄给另一端，否则检查就失去意义。
- **抛出去的东西走抛物线。** 被颠出、扔出、弹起的东西，每帧用 `kit.prop('面包', { x, y, s, air, ballistic: true, from: '推车' })` 报告：`y` 是它正下方的地面高度，`air` 是离地多高（像素），`from` 是它从谁身上飞出去。高度要随时间按抛物线变化。侧面镜头里 `y` 不变；要往镜头这边飞，就在 `film.json` 里写 `horizon`，并让 `s` 按 `s ∝ (y − horizon)` 变大。
- **只用 `/runtime/painters.js` 和 `kit`**，不要引入别的模块，也不要用图片。

### 引擎提供的工具

`kit` 上的工具（来自 `runtime/engine.js`）：

| 工具 | 作用 |
| --- | --- |
| `kit.layer(w, h)` | 新建一张画布，返回 `{ canvas, g }` |
| `kit.rng(seed)` | 固定种子的随机数，返回一个函数 |
| `kit.twos(t)` | 把时间取整到一秒 12 张画 |
| `kit.clamp`、`kit.lerp`、`kit.smooth` | 常用数学；`smooth` 是平滑的 0–1 过渡 |
| `kit.hex`、`kit.mix`、`kit.css`、`kit.jit`、`kit.ramp` | 颜色：混合、转 CSS、加一点抖动、按色标取色 |
| `kit.spline(点)` | 过这些点的平滑曲线 |
| `kit.stroke(g, 点, 选项)` | 一笔水粉笔触，有几根鬃毛，两头收尖 |
| `kit.dab`、`kit.mottle` | 短笔触，以及用许多短笔触铺一块颜色 |
| `kit.cloud(g, cx, cy, w, h, 选项)` | 一团有受光面的积云 |
| `kit.grass(g, [x0, x1], 底线, 选项)` | 一片草，每根都不一样 |
| `kit.ink(g, [[x, y, 粗细], ...], 颜色)` | 有粗细变化的描线 |
| `kit.tooth(g, w, h)` | 纸张纹理 |
| `kit.actor(名字, { x, y, s, facing, points })` | 报告角色位置和接触点，见上文 |
| `kit.prop(名字, { x, y, s, points, air, ballistic, from })` | 报告道具：车、邮筒、抛出去的面包 |
| `kit.at(g, x, y)` | 当前变换下的一点换算成画面像素，用来报告接触点 |
| `kit.cue(名字, 时刻, 种类, 选项)` | 报告一个要配声音的小动作 |
| `kit.look` | 这支片子的配色 |

`/runtime/painters.js` 里的通用画法：

| 画法 | 作用 |
| --- | --- |
| `path(kit, 点, closed)` | 把点连成平滑的形状，返回 `{ P, q }`：`P` 用来填色，`q` 用来描线 |
| `cel(g, P, { base, shade, rim, light, sd, rw })` | 赛璐珞上色：底色、一块硬边阴影、一条受光边 |
| `line(kit, g, q, 粗细, 种子)` | 沿形状描一圈墨线 |
| `groundShadow(g, x, y, s, 长度, 颜色)` | 角色脚下的地面阴影 |
| `paintSky(kit, g, w, 地平线, 太阳, 种子)` | 天空和太阳 |
| `paintClouds(kit, g, [[cx, cy, w, h], ...], 太阳)` | 一组积云，朝太阳的一面受光 |
| `paintFarBank`、`paintBridge` | 远处的山和城，桁架桥 |
| `paintRiver(kit, g, w, y0, y1, 太阳x, 种子)` | 映着天空的河面 |
| `glitter(kit, g, t, 太阳x, y0, y1, 宽度, 种子)` | 太阳下面闪烁的碎金 |
| `paintSlope`、`paintRoad`、`reeds` | 草坡、碎石路、芦苇 |
| `paintHouses(kit, g, x0, x1, 底线, 种子, { reflect, haze })` | 一排各不相同的房子，可带倒影 |
| `paintWall`、`paintArchBridge`、`paintCobbles`、`paintPuddle` | 石墙、石拱桥、石板路、水洼 |
| `ripples`、`rain` | 水洼里的涟漪、斜着落的雨（都按一拍二动） |
| `lampPost(kit, g, x, 地面, 顶部, 亮度)` | 路灯杆，返回灯的位置 |

角色要自己画：用 `path` 和 `cel` 画形状，用 `line` 描线。两支参考片的角色在评测用例里，可以先看看它们的写法：`evals/cases/pelican-embankment/scenes.js` 和 `evals/cases/postman-tortoise/scenes.js`。这次任务里这两个目录不在工作区，规范里的接口就是全部。

## sound.js

```js
export default function score({ synth: S, film, timeline, events, eventList }) {
  const dur = timeline.duration;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];
  // 配乐：在 music 上放音符
  S.place(music, S.piano(S.hz('A4'), 0.6, 0.6), 1.0, 0.4);
  // 音效：events 是 { '镜头id.事件名': 全片秒数 }，eventList 还包括 kit.cue 报告的小动作
  for (const ev of eventList) {
    if (ev.name.endsWith('.knock')) {
      S.place(sfx, S.softKick(0.8), ev.t, 0.8);
      // 每个 film.json 里声明的事件都要登记：声画同步检查会在这个频带里找声音的起点
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [60, 400] });
    }
  }
  return { music: S.room(music, 0.3).subarray(0, S.n(dur)), sfx: sfx.subarray(0, S.n(dur)), cues };
}
```

`synth` 里的工具（来自 `pipeline/lib/synth.mjs`）：

| 工具 | 作用 |
| --- | --- |
| `S.buffer(秒)`、`S.n(秒)`、`S.SR` | 新建一段音频；秒数换算成采样数；采样率 48000 |
| `S.place(目标, 声音, 时刻, 音量)` | 把一段声音放到某个时刻 |
| `S.hz('A4')` | 音名换成频率 |
| `S.piano`、`S.pluck`、`S.strings`、`S.glock`、`S.bell` | 毡面钢琴、拨弦、弦乐、钢片琴、铃 |
| `S.softKick`、`S.brush` | 轻鼓、刷子 |
| `S.noise(秒, 种子)` | 固定种子的噪声，做风、雨、水、脚步、翅膀的原料 |
| `S.lowpass`、`S.highpass`、`S.bandpass` | 滤波；截止频率可以是随时间变化的函数 |
| `S.shape(声音, 包络函数)` | 按时间改变音量 |
| `S.room(声音, 湿度)` | 加一点混响 |
| `S.rng(种子)`、`S.db(分贝)` | 随机数，分贝换成倍数 |

- `film.json` 里声明的每个事件都要有声音，并且登记进 `cues`；`band` 填这个声音最突出的频率范围。
- 两个事件离得很近时（比如连按两下铃），前一个声音要在后一个之前收住，否则后一个的起点被盖住，检查会判没有声音。
- 两段声音的总响度管线会自动调整，不用自己凑。

## 看图

抽帧图每两秒一张，常会错过关键时刻。截任意时刻的画面：

```bash
node pipeline/cli.mjs run task --no-video
```

之后 `task/out/contact.jpg` 是抽帧图。需要更细时，在 `scenes.js` 里临时把某个镜头的 `duration` 拉长、或把事件提前，再看抽帧图，看完改回来。

## 检查失败时怎么改

| 检查 | 常见原因 | 改法 |
| --- | --- | --- |
| `heading` | 侧面画的角色斜着走或往纵深走；跟拍镜头没把镜头移动算进位置 | 让角色横着走；`kit.actor` 报告地面坐标 |
| `contact` | 声明碰着的两点离得太远：手没握住、东西对不上口；或者不该碰的碰上了；或者某一帧没报告这个点 | 改画法让它们真的碰着，不要只改报告的坐标 |
| `landing` | 抛出去的东西匀速飘、往上加速；飞行中地面高度变了却没写 `horizon`；往镜头飞却没有按透视变大 | 高度用 `h0 + v·t − ½·g·t²`；侧面镜头里保持 `y` 不变，或写 `horizon` 并按透视缩放 |
| `pops` | 背景、角色在某一帧跳了位置 | 找出不连续的公式；故意的突变要在 `events` 里声明 |
| `palette` | 某个镜头的整体颜色偏离了 `expect.json` 的色彩脚本 | 调整 `look` 或镜头里的颜色 |
| `cue-sync` | 事件没登记声音；声音晚了；被前一个声音盖住 | 登记 `cues`；把声音放在 `ev.t`；收住前一个声音 |
| `determinism` | 用了 `Math.random()` 或时钟，或在两帧之间留了状态 | 改用 `kit.rng` 和传入的 `t` |
| `video-stillness` | 画面静止太久 | 加一点动：草、水、雨、镜头慢移 |
| `audio-levels` | 峰值超过 -1 dBFS：管线会把整体响度调到 -14 LUFS，但不压峰值，一个比别的都响得多的瞬间声音（撞击、落地）会被一起抬上去 | 把那个声音调轻，让它和其他声音差不多响；不要去调整体音量 |
| `spec` | 片长不在 `expect.json` 的范围内 | 改镜头时长 |

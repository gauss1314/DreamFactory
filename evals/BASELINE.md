# 评测基线

干净用例误报 0/10，缺陷检出 42/42。

运行环境：Node v22.23.4 · 语音后端 edge · 草稿画质 · 2026-11-25

## 干净用例

参考影片不应触发任何检查。这里的失败就是误报。

| 用例 | 结果 | 片长（秒） | 误报的检查 |
| --- | --- | --- | --- |
| asks-for-derived-number | 通过 | 26.6 |  |
| baker-hedgehog | 通过 | 13.0 |  |
| cost-per-minute | 通过 | 43.5 |  |
| monthly-trend | 通过 | 27.4 |  |
| pelican-embankment | 通过 | 15.0 |  |
| postman-tortoise | 通过 | 12.0 |  |
| top-of-long-list | 通过 | 22.0 |  |
| twenty-seconds | 通过 | 14.1 |  |
| works-by-category | 通过 | 52.6 |  |
| works-by-category-en | 通过 | 48.6 |  |

## 缺陷注入

每条缺陷只在参考影片上改一处。指定的检查必须失败，否则算漏检。

| 缺陷 | 改了什么 | 应失败的检查 | 结果 | 连带失败的检查 |
| --- | --- | --- | --- | --- |
| number-typo-on-screen | 画面上的数字打错：5,000 写成 5,500 | data-accuracy | 抓到 |  |
| number-wrong-in-narration | 旁白念错数字：483 念成 438 | data-accuracy | 抓到 |  |
| inline-series-wrong-value | 图表不引用数据，手抄时把 483 抄成 583 | data-accuracy | 抓到 | marks |
| required-fact-missing | 任务要求展示的总数没有出现在画面上 | data-accuracy | 抓到 |  |
| range-typo | 区间图手抄数据，把 15,000 抄成 150,000 | data-accuracy | 抓到 |  |
| number-typo-english | 英文版画面上的数字打错：5,000 写成 50,000 | data-accuracy | 抓到 |  |
| double-percent | 占比引用后面又手写了一个百分号，显示成 17%% | typography | 抓到 |  |
| leftover-template | 数据引用少写一个括号，模板符号原样出现在画面上 | typography | 抓到 |  |
| no-source | 数据画面没有标注来源 | citation | 抓到 |  |
| flash-text | 结尾画面一闪而过，来不及读 | readability | 抓到 |  |
| headline-overflow | 标题太长，撑出画面 | layout | 抓到 | readability |
| low-contrast | 次要文字颜色太接近背景 | contrast | 抓到 |  |
| long-subtitle | 一句旁白太长，字幕挤成两行 | subtitles | 抓到 |  |
| empty-scene | 一个场景里什么内容都没有 | empty-frames | 抓到 |  |
| duration-out-of-range | 片长不符合任务要求 | spec | 抓到 |  |
| dead-air | 结尾画面静止且无声地停了十秒 | video-stillness、audio-gaps | 抓到 |  |
| year-with-separator | 年份当成普通数字，显示成 2,026 年 | typography | 抓到 |  |
| share-of-subset | 只展示前 6 名却显示占比，占比是按这 6 个算的 | data-accuracy | 抓到 |  |
| long-list-overflow | 把 24 个品类全部塞进一张图 | layout | 抓到 | contrast |
| over-the-time-limit | 20 秒的片子讲了太多，超出时长上限 | spec | 抓到 |  |
| built-in-instead-of-line-chart | 任务要求折线图，却用内置柱状图交差 | spec | 抓到 | layout |
| chart-points-misplaced | 折线图上的点画在了别的月份的高度上 | marks | 抓到 |  |
| chart-axis-inverted | 折线图的纵轴画反了，数值越大位置越低 | marks | 抓到 | layout |
| chart-without-values | 自定义图表没有标出每个点代表的数值 | marks | 抓到 |  |
| chart-uses-random | 自定义场景里用了随机数，每次重画都不一样 | determinism | 抓到 |  |
| chart-points-invisible | 折线图上的点半径写成零，画不出来 | marks | 抓到 |  |
| ranges-scale-not-a-range | 区间图的 scale 写成了 "log"，四根条形画不出来 | 拒绝运行并报错 | 抓到 |  |
| chart-lags-narration | 折线图画得太晚，旁白念完数字画面才出现 | sync | 抓到 |  |
| voice-says-something-else | 字幕是一句话，语音念的是另一句话 | asr | 抓到 |  |
| voice-says-wrong-number | 字幕写 483，语音念成 438 | data-accuracy、asr | 抓到 |  |
| background-jump | 跟拍镜头的远景在半途跳了一截 | pops | 抓到 |  |
| wrong-time-of-day | 天空画成了正午的蓝，偏离傍晚的色彩脚本 | palette | 抓到 |  |
| bell-late | 车铃声比画面晚了四分之一秒 | cue-sync | 抓到 |  |
| event-without-sound | 分镜里声明了一个画面事件，却没有配声音 | cue-sync | 抓到 |  |
| riding-sideways | 侧面画的鹈鹕沿着通向纵深的路斜着往远处滑（这支片子第一版的真实错误） | heading | 抓到 |  |
| music-too-loud | 配乐开得太响，盖住了旁白 | voice-over-music | 抓到 |  |
| chime-late | 主角亮起时的钢片琴晚了 0.3 秒 | cue-sync | 抓到 |  |
| hand-off-bar | 鹈鹕的手悬在车把上方，没有握住 | contact | 抓到 |  |
| letter-misses-slot | 邮筒立得太高，乌龟投信时信封对不上投信口 | contact | 抓到 |  |
| nose-in-cart | 刺猬的鼻子顶在车厢上，像是用脸推车（无人值守交付版的真实问题） | contact | 抓到 |  |
| bun-wrong-perspective | 面包往镜头这边飞，大小却不变 | landing | 抓到 |  |
| bun-floats | 面包匀速飘下来，没有受重力加速 | landing | 抓到 |  |

## 各项检查的覆盖

| 检查 | 缺陷样例 | 抓到 | 备注 |
| --- | --- | --- | --- |
| spec | 3 | 3 |  |
| data-accuracy | 8 | 8 |  |
| citation | 1 | 1 |  |
| readability | 1 | 1 |  |
| layout | 2 | 2 |  |
| contrast | 1 | 1 |  |
| subtitles | 1 | 1 |  |
| sync | 1 | 1 |  |
| typography | 3 | 3 |  |
| empty-frames | 1 | 1 |  |
| marks | 4 | 4 |  |
| determinism | 1 | 1 |  |
| heading | 1 | 1 | 本次运行跳过 |
| contact | 3 | 3 | 本次运行跳过 |
| landing | 2 | 2 | 本次运行跳过 |
| fonts | 0 | 0 | 没有缺陷样例，效果未经验证 |
| video-stillness | 1 | 1 |  |
| audio-levels | 0 | 0 | 没有缺陷样例，效果未经验证 |
| audio-gaps | 1 | 1 |  |
| asr | 2 | 2 | 本次运行跳过 |
| pops | 1 | 1 |  |
| palette | 1 | 1 | 本次运行跳过 |
| cue-sync | 3 | 3 |  |
| voice-over-music | 1 | 1 |  |

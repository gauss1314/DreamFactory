# 评测基线

干净用例误报 0/3，缺陷检出 16/16。

运行环境：Node v22.23.4 · 语音后端 espeak · 草稿画质 · 2026-11-14

## 干净用例

参考影片不应触发任何检查。这里的失败就是误报。

| 用例 | 结果 | 片长（秒） | 误报的检查 |
| --- | --- | --- | --- |
| cost-per-minute | 通过 | 45.7 |  |
| works-by-category | 通过 | 54.1 |  |
| works-by-category-en | 通过 | 52.3 |  |

## 缺陷注入

每条缺陷只在参考影片上改一处。指定的检查必须失败，否则算漏检。

| 缺陷 | 改了什么 | 应失败的检查 | 结果 | 连带失败的检查 |
| --- | --- | --- | --- | --- |
| number-typo-on-screen | 画面上的数字打错：5,000 写成 5,500 | data-accuracy | 抓到 |  |
| number-wrong-in-narration | 旁白念错数字：483 念成 438 | data-accuracy | 抓到 |  |
| inline-series-wrong-value | 图表不引用数据，手抄时把 483 抄成 583 | data-accuracy | 抓到 |  |
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

## 各项检查的覆盖

| 检查 | 缺陷样例 | 抓到 | 备注 |
| --- | --- | --- | --- |
| spec | 1 | 1 |  |
| data-accuracy | 6 | 6 |  |
| citation | 1 | 1 |  |
| readability | 1 | 1 |  |
| layout | 1 | 1 |  |
| contrast | 1 | 1 |  |
| subtitles | 1 | 1 |  |
| typography | 2 | 2 |  |
| empty-frames | 1 | 1 |  |
| fonts | 0 | 0 | 没有缺陷样例，效果未经验证 |
| video-stillness | 1 | 1 |  |
| audio-levels | 0 | 0 | 没有缺陷样例，效果未经验证 |
| audio-gaps | 1 | 1 |  |
| asr | 0 | 0 | 本次运行跳过 |

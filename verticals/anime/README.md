# 动画垂直管线

手绘风的剧场动画短片：水粉背景、赛璐珞角色、35 毫米胶片质感，配乐和音效全部合成。画面和声音由 Python 生成（numpy、OpenCV、pycairo、numba、scipy），时间轴、事件、混音和自检仍走 DreamFactory 的管线。

## 来源

`lp/`（画法引擎）和 `audio/`（合成乐器、音效、房间混响）来自 [The Last Page](https://github.com/ChetasLua/the-last-page)，个人探索用途，原样借用，只改了两处：`lp/__init__.py` 加了缓存目录，`audio/core.py` 的片长改由驱动设定。

| 模块 | 作用 |
| --- | --- |
| `lp/paint.py` | 水粉：鬃毛笔触、按形体重画、分形斑驳、纸纹 |
| `lp/ink.py` | 两倍超采样的赛璐珞和压力描线 |
| `lp/cam.py` | 以米为单位的透视相机、平面单应、Voronoi 砌缝 |
| `lp/comp.py` | 合成、光束、焦外光斑、35 毫米成片质感 |
| `lp/clouds.py` `plants.py` `brush.py` `props.py` `ink_letters.py` | 云、植物、毛笔笔画、灯笼、题字 |
| `audio/` | 毡面钢琴、弦乐、铜管、合唱、打击、风、火、爪子等的合成，混响房间，响度和限幅 |
| `tools/film.py` | 驱动：画面、声音、静帧质检、单镜头预览 |

## 一支片子

片子目录里有 `film.json`（镜头表和事件，和其他垂直管线一样）、`shots/<type>.py`（每种镜头一个模块，接口见 `tools/film.py` 开头）、片子自己的角色和道具模块，以及 `sound.py`。例子：`films/lighthouse-keeper/`，它的 `CONTRACT.md` 是制作约定。

```bash
node pipeline/cli.mjs run films/lighthouse-keeper --no-video   # 画面报告、抽帧图、声音和检查，不渲染视频
node pipeline/cli.mjs run films/lighthouse-keeper --draft      # 半分辨率、每秒 12 张的草稿
node pipeline/cli.mjs run films/lighthouse-keeper              # 2048×1152、24 帧的成片
.venv/bin/python verticals/anime/tools/film.py still films/lighthouse-keeper s1 0 60 --crop 900,400
```

## 环境

```bash
python3 -m venv .venv
.venv/bin/pip install numpy opencv-python-headless pycairo scipy pillow numba soundfile
```

`.venv/` 不入库。管线默认用 `.venv/bin/python`，可以用 `DF_PYTHON` 改。渲染结果和画面报告按画面的全部来源（`film.json`、片子的 Python 文件、引擎）缓存在 `.cache/render/`，画好的底版缓存在 `.cache/anime/`。

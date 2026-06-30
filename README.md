# MyTerraria

基于 [Fegaria-Remastered](https://github.com/FergusGriggs/Fegaria-Remastered) 的简化版泰拉瑞亚克隆——从一个纯矩形 demo 起步，逐步扩展到带生物群系、昼夜、史莱姆王 Boss、物品掉落、完整物品栏的 2D 玩法闭环，并在击败 Boss 后切入一个 **3D 体素胜利场景**（pygame + PyOpenGL），可在方块世界里行走、挖掘、放置、开箱子、与跳跃的方块史莱姆战斗。

当前版本：**ver5.0**（详见 `CLAUDE.md` 末尾的版本日志，报告见 `REPORT.md`）

## 功能

### 2D 模式（主玩法）

- **Perlin 噪声地形**：草地 / 泥土 / 石头 / 铜矿 / 银矿 / 铁矿 / 树木，3 个生物群系（森林 / 雪地 / 沙漠）
- **昼夜系统**：现实 ~30 秒白天 + ~15 秒夜晚循环，天空颜色随阶段渐变（黎明 / 白天 / 黄昏 / 黑夜）
- **背景墙**：地下挖空后露出对应群系的背景墙（连成片，不留缝）
- **方块破坏与放置**：铜镐挖掘，6 种可放置方块
- **战斗**：铜剑挥砍 + 史莱姆敌人 AI（跳跃追击、受击闪红、死亡爆炸粒子）
- **King Slime Boss**：HP 8000，HP 跌过 66% / 33% 时分裂；击败后进入 3D 胜利场景
- **物品掉落系统**：方块和怪物死亡都会掉落实体，靠近自动吸附 + 顶部浮动文字
- **完整物品栏**：8 格快捷栏 + ESC 打开整包 + 拖拽（单击进入拖拽态，再次点击放下）
- **主菜单 + BGM**：标题画面播放 the Journey Begins，游戏内播放 Overworld Day
- **音效**：挖掘 / 挥剑 / 受击 / 死亡 / 拾取

### 3D 模式（胜利场景，pygame + PyOpenGL）

- **体素世界**：120×120×18 的方块网格（25 万体素），3 群系色带，简单光照 shading，**numpy 向量化面提取 + VBO**（放置/挖掘后重建只要 ~23ms，60 FPS 稳定）
- **第一人称控制**：WASD + 鼠标视角，行走 + 跳跃 + 疾跑（Shift / 双击 W）
- **挖掘 / 放置方块**：准星射线命中 + 线框高亮 + 8 种方块选择（土/石/木/沙/雪/草/铜/银）+ 按方块硬度分级的挖掘耗时 + 按住 LMB 连续挖掘
- **方块放置约束**：必须贴着已有方块的某个面（不能悬空）
- **E 键背包**：8×4 = 32 格独立背包，热栏 ↔ 背包 ↔ 箱子之间支持单击粘滞拖拽（合并 / 交换 / 放空槽 / 拖空白退回原位）
- **箱子右键交互**：程序化木屋内嵌箱子方块，右键瞄准开箱；每个箱子按坐标 seed 生成固定 loot（铜矿 / 银矿 / 木头 + 随机额外方块）
- **物品图标 + 悬停 tooltip**：所有方块槽位画 `res/images/items/*.png` 真实图标（不是涂色块）；鼠标悬停在非空槽位时在光标附近显示物品名
- **MC 风方块史莱姆**：5 面身体贴图 + 1 面带眼睛的 `slime_face.png`；群落式生成（5 只，大小 0.6 / 0.8 / 1.0 / 1.5，HP 随大小缩放）；指数平滑滞后转向（追玩家但有"反应时间"）；血条 + 受击闪红 + 死亡 5 秒后原地复活
- **程序化木屋**：地图上随机散布 5×5 木屋（带门洞、屋顶），内嵌箱子
- **BGM 延续**：3D 场景继续播放 2D 的 Overworld Day（mixer 全局，与显示模式无关）
- **暂停菜单**：ESC 暂停 + 释放鼠标（解决 3D 模式鼠标锁定时无法切输入法的问题）+ QUIT 按钮

## 快速开始

**进入游戏后请将输入法调整至英文！** 否则 2D 模式按键可能被吞。

```bash
conda create -n terraria python=3.13
conda activate terraria
pip install -r requirements.txt
python run.py
```

**调试入口**：跳过菜单和 Boss 战，直接进 3D 场景测试：

```bash
python run.py --3d
```

## 操作

### 2D 模式

| 按键 | 功能 |
|------|------|
| A / D | 左右移动 |
| Space | 跳跃 |
| 鼠标左键 | 使用物品（挖掘 / 放置 / 挥剑） |
| 滚轮 / 1-8 | 切换快捷栏 |
| ESC | 暂停 / 打开整包 + QUIT |

### 3D 模式

| 按键 | 功能 |
|------|------|
| W A S D | 前后左右移动 |
| Space | 跳跃（行走模式） |
| Shift / 双击 W | 疾跑 |
| 鼠标移动 | 视角 |
| 鼠标左键 | 挖方块（按住连续挖）/ 拿剑砍史莱姆 |
| 鼠标右键 | 放方块 / 右键瞄准箱子开箱 |
| 1-2 | 切工具（镐 / 剑） |
| 3-8 | 切方块 |
| E | 打开背包 |
| ESC | 暂停 + 释放鼠标（可切输入法）+ QUIT |

## 项目结构

```
MyTerraria/
  run.py                  入口（含 --3d 调试参数）
  requirements.txt        依赖
  README.md               本文件
  REPORT.md               大作业报告（开发流程 / 架构 / 核心代码）
  CLAUDE.md               版本日志 + 实现规划
  King_Slime.gif          Boss 动画源（assets.py 抽帧）
  preview_zombie.py       离线 OBJ 模型预览工具（调试用）
  src/
    constants.py          常量 + 方块 / 物品 / 群系数据
    perlin.py             Simplex 噪声
    world.py              世界 + 地形生成 + 渲染
    player.py             玩家物理 + 物品栏 + 方块交互
    slime.py              2D 史莱姆敌人
    boss.py               King Slime Boss
    drop.py               掉落物实体（吸附 + 浮动文字）
    assets.py             资源加载（精灵图、音效、音乐）
    game.py               主菜单 + 2D 游戏循环 + 摄像机 + UI
    scene3d.py            3D 胜利场景（PyOpenGL + 体素世界 + 方块史莱姆）
  res/                    2D 资源（来自原项目）
    images/  sounds/  music/  fonts/  players/  worlds/  game_data/
  3dres/                  3D 模式资源
    slime.png             MC 史莱姆展开图（裁取身体面）
    slime_face.png        预制作的正面贴图（带眼睛）
```

## 关键参数调优

所有参数都在 `src/scene3d.py` 顶部，可直接改。

### 3D 史莱姆跳跃（`src/scene3d.py` ~415 行）

```python
SLIME_GRAVITY_3D = 18.0      # 下落加速度（越小越漂浮）
SLIME_JUMP_VY = 7.5          # 起跳向上速度（越大跳越高）
SLIME_HSPEED = 4.0           # 跳跃水平速度（块/秒）
SLIME_JUMP_INTERVAL = 1.0    # 落地到下次起跳的最小间隔（秒）
SLIME_JUMP_JITTER = 0.5      # 间隔随机抖动
```

### 3D 史莱姆转向滞后（~423 行）

```python
SLIME_LAG_TIME = 0.5         # 滞后时间常数（秒）——越大反应越慢
SLIME_TURN_SPEED = 8.0       # 朝向插值速度（弧度/秒）
```

机制：玩家位置经指数平滑得到 `player_pos_lagged`（τ = `SLIME_LAG_TIME`），史莱姆读滞后位置算朝向 → "玩家移动后过一会儿史莱姆才转过来"的效果。

### 3D 史莱姆群落（`run_epilogue` 内，~1328 行）

```python
SLIME_SPAWNS = [
    (0.50, 0.50, 1.5, 150),    # 中央大史莱姆（Boss 风）
    (0.32, 0.40, 0.8, 80),
    (0.68, 0.42, 0.8, 80),
    (0.42, 0.68, 1.0, 100),
    (0.62, 0.66, 0.6, 60),     # 小但快
]
```

每条 = (相对坐标 rx, rz, size, hp)；rx/rz 是 0..1 比例（相对 WORLD_SIZE），size 是方块边长。删 / 加 / 改条目即可调整数量、大小、HP。

### 3D 挖掘耗时（~50 行 `TILE_MINE_TIME`）

```python
TILE_MINE_TIME = {
    SLOT_GRASS: 0.30, SLOT_DIRT: 0.30, SLOT_SAND: 0.30, SLOT_SNOW: 0.30,
    SLOT_WOOD: 0.50, SLOT_LEAVES: 0.20,
    SLOT_STONE: 0.80,
    SLOT_COPPER: 1.10, SLOT_SILVER: 1.30,
    SLOT_CHEST: 0.80,
}
```

### 体素世界规模（~12 行）

```python
WORLD_SIZE = 120         # 地面边长（立方体数）
MAX_H = 18               # 最大高度（地下厚度 ~10+，地表 ~5-7）
```

## 致谢

- 原项目：[Fegaria-Remastered by FergusGriggs](https://github.com/FergusGriggs/Fegaria-Remastered)
- 2D 模式的音乐、音效、精灵图来自 Terraria，版权归原作者所有
- 3D 模式的 MC 风方块史莱姆基于 Minecraft 的 slime.png（裁取身体面板）+ 自制 `slime_face.png`（正面带眼睛）

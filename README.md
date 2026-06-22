# MyTerraria

基于 [Fegaria-Remastered](https://github.com/FergusGriggs/Fegaria-Remastered) 的简化版泰拉瑞亚克隆——从一个纯矩形 demo 起步，逐步扩展到带生物群系、昼夜、史莱姆王 Boss、物品掉落、完整物品栏的 2D 玩法闭环，并在击败 Boss 后切入一个 **3D 体素胜利场景**（pygame + PyOpenGL），可在方块世界里行走、飞行、挖掘、放置、与跳跃的方块史莱姆战斗。

当前版本：**ver4.7**（详见 `CLAUDE.md` 末尾的版本日志）

## 功能

### 2D 模式（主玩法）

- **Perlin 噪声地形**：草地 / 泥土 / 石头 / 铜矿 / 银矿 / 铁矿 / 树木，3 个生物群系（森林 / 雪地 / 沙漠）
- **昼夜系统**：现实 ~30 秒白天 + ~15 秒夜晚循环
- **背景墙**：地下挖空后露出对应群系的背景墙
- **方块破坏与放置**：铜镐挖掘，6 种可放置方块
- **战斗**：铜剑挥砍 + 史莱姆敌人 AI（跳跃追击、受击闪红、死亡爆炸粒子）
- **King Slime Boss**：击败后进入 3D 胜利场景
- **物品掉落系统**：方块和怪物死亡都会掉落实体，靠近自动吸附 + 顶部浮动文字
- **完整物品栏**：8 格快捷栏 + ESC 打开整包 + 拖拽（单击进入拖拽态，再次点击放下）
- **主菜单 + BGM**：标题画面播放 the journey begins，游戏内播放 overworldday
- **音效**：挖掘 / 挥剑 / 受击 / 死亡 / 拾取

### 3D 模式（胜利场景，pygame + PyOpenGL）

- **体素世界**：40×40×MAX_H 的方块网格，3 群系色带，简单光照 shading
- **第一人称控制**：WASD + 鼠标视角，飞行 + 行走 + 跳跃 + 疾跑（Shift / 双击 W）
- **挖掘 / 放置方块**：准星射线命中 + 线框高亮 + 6 种方块选择 + 数量管理
- **方块放置约束**：必须贴着已有方块的某个面（不能悬空）
- **MC 风方块史莱姆**：5 面身体贴图 + 1 面带眼睛的 `slime_face.png`，会朝玩家跳跃（速度比 2D 慢得多），血条 + 受击 + 5 秒复活
- **暂停菜单**：ESC 暂停 + QUIT 按钮（解决 3D 模式鼠标锁定时无法切输入法的问题）

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
| 鼠标左键 | 挖方块 / 拿剑砍史莱姆 |
| 鼠标右键 | 放方块 |
| 1-2 | 切工具（镐 / 剑） |
| 3-8 | 切方块 |
| ESC | 暂停 + 释放鼠标（可切输入法）+ QUIT |

## 项目结构

```
MyTerraria/
  run.py                  入口（含 --3d 调试参数）
  requirements.txt        依赖
  CLAUDE.md               版本日志 + 实现规划
  preview_zombie.py       离线 OBJ 模型预览工具（调试用）
  src/
    constants.py          常量 + 方块 / 物品数据
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

### 3D 史莱姆跳跃（`src/scene3d.py` 顶部）

```python
SLIME_GRAVITY_3D = 18.0      # 下落加速度（越小越漂浮）
SLIME_JUMP_VY = 7.5          # 起跳向上速度（越大跳越高）
SLIME_HSPEED = 4.0           # 跳跃水平速度（块/秒）
SLIME_JUMP_INTERVAL = 1.0    # 落地到下次起跳的最小间隔（秒）
SLIME_JUMP_JITTER = 0.5      # 间隔随机抖动
```

### 3D 史莱姆大小

`src/scene3d.py` 中 `run_epilogue()` 内的 `SLIME_SIZE = 2.0`（搜索定位即可）。

### 3D 史莱姆脸朝向

固定在 south 面不跟踪玩家。如要换面或加跟踪，看 `_draw_textured_cube()` 的 `side_tex` 和 `face_yaw` 参数。

## 致谢

- 原项目：[Fegaria-Remastered by FergusGriggs](https://github.com/FergusGriggs/Fegaria-Remastered)
- 2D 模式的音乐、音效、精灵图来自 Terraria，版权归原作者所有
- 3D 模式的 MC 风方块史莱姆基于 Minecraft 的 slime.png（裁取身体面板）+ 自制 `slime_face.png`（正面带眼睛）

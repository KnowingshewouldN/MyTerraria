# MyTerraria - 简化版泰拉瑞亚克隆计划

## 项目背景
Fegaria-Remastered 项目（~4500行代码，15+文件）是一个功能完备的泰拉瑞亚克隆，拥有复杂系统（XML数据驱动、精灵图、敌人AI、菜单系统、存档/读档、粒子特效、光照系统等）。我们的目标是基于其核心框架，在 `D:\Python Gaming\Terraria\MyTerraria\` 创建一个**大幅简化版本**，只实现基本玩法：移动跳跃、挥剑攻击、破坏方块、放置方块。

**核心策略：** 保留框架模式（游戏循环、delta time 物理、Tile 世界、摄像机），用硬编码数据替代 XML，剥离所有非必要系统。

**渲染策略（便于后续升级精灵图）：**
- 第一版使用纯色矩形渲染，但通过抽象函数隔离图像获取逻辑
- 后续可直接复制原项目 `res/` 文件夹，只修改以下函数即可切换到精灵图渲染：
  - `get_tile_surface(tile_id)` → 返回方块图像（当前返回纯色矩形，后续改为加载 `res/images/tiles/` 精灵）
  - `get_item_icon(item_id)` → 返回物品图标（当前返回纯色矩形，后续改为加载 `res/images/items/` 精灵）
  - `Player.draw()` → 玩家渲染（当前画矩形，后续改为加载 `res/images/` 身体/手臂精灵）
- 游戏逻辑代码无需修改，渲染和逻辑完全解耦

---

## 目标文件结构（约 980 行代码）

```
MyTerraria/
  run.py              (~30 行)    入口文件
  src/
    __init__.py       (0 行)
    constants.py      (~70 行)    常量 + 硬编码方块/物品数据
    perlin.py         (~200 行)   从原项目复制，只保留 2D 噪声
    world.py          (~200 行)   世界数据 + 地形生成 + 渲染
    player.py         (~200 行)   玩家物理 + 背包 + 方块交互
    game.py           (~300 行)   主游戏循环 + 摄像机 + 输入 + UI
```

---

## 实现步骤

### 阶段一：基础框架

**步骤 1：创建 `constants.py`** — 替代原项目的 `commons.py` + `game_data.py` + `item.py`
- 核心常量：`BLOCKSIZE=16`、`GRAVITY`、`PLAYER_SPEED=12`、`JUMP_VELOCITY=-50`、`PLAYER_REACH=8`、`FPS=60`、窗口大小 1280x720
- 世界大小：`WORLD_WIDTH=400`、`WORLD_HEIGHT=200`
- 方块字典：AIR(0)、GRASS(1)、DIRT(2)、STONE(3)、WOOD(4)、COPPER_ORE(5) — 每个含 `{name, color, solid, drop_item}`
- 物品字典：铜镐、铜剑、泥土/石头/木头/草方块 — 每个含 `{name, color, is_block, place_tile, is_pickaxe, is_sword, damage}`
- 默认快捷栏：`[铜镐, 铜剑, 泥土x99, 石头x99, 木头x99, None, None, None]`

**步骤 2：复制 `perlin.py`** — 只保留 2D 噪声函数
- 从 `Fegaria-Remastered/src/perlin.py` 复制，只保留 `noise2` 方法

### 阶段二：世界系统

**步骤 3：创建 `world.py`** — 从原项目 ~1200 行简化到 ~200 行
- `World` 类：`tile_data[x][y]` = 单个整数（去掉原项目的墙壁层）
- `tile_in_map(x, y)`：边界检查
- `get_neighbor_count(x, y)`：计算相邻实心方块数（用于放置验证）
- `generate_terrain(world)`：柏林噪声地表 + 泥土层 + 石头层 + 洞穴 + 铜矿 + 简单树木 + 出生点
- `create_terrain_surface(world)`：用纯色矩形绘制所有方块到大型 pygame.Surface
- `update_tile(surface, world, x, y)`：方块改变时重绘单个格子

与原项目的关键简化：
- 无生物群系、无墙壁、无多方块、无箱子、无建筑结构
- 纯色矩形替代精灵遮罩

### 阶段三：玩家系统

**步骤 4：创建 `player.py`** — 从原项目 ~1390 行简化到 ~200 行
- `Player` 类：position、velocity、rect、hotbar、hp、direction、swing 状态
- `update(world, dt)`：重力 + 移动 + 碰撞检测（原项目 5x5 格子检测，305-366行） + 世界边界限制
- `jump()`：如果着地则设置 velocity.y = JUMP_VELOCITY
- `use_item(world, mouse_tile)`：根据手持物品分派到挖掘/放置/挥剑
  - 镐：将方块设为 AIR，掉落物直接加入快捷栏
  - 方块物品：检查距离 + 不与玩家重叠 + 有相邻方块，放置方块，减少数量
  - 剑：触发挥剑动画
- `draw(screen, cam_x, cam_y)`：纯色矩形（身体 + 头部），挥剑时画一条线

与原项目的关键简化：
- 无精灵动画、无手臂/身体分离、无复杂旋转
- 挖掘直接加入快捷栏（无需掉落物实体）
- 无伤害数字、无粒子、无击退

### 阶段四：游戏循环 + 整合

**步骤 5：创建 `game.py`** — 从原项目 ~1463 行简化到 ~300 行
- `run(screen)`：主游戏函数
  - 初始化：创建 World、生成地形、创建地形 Surface、在出生点创建 Player
  - 循环：delta time、事件处理、鼠标持续按下、更新玩家、更新摄像机、渲染
- 输入处理：
  - A/D：移动，Space：跳跃，1-8：快捷栏，ESC：退出
  - 鼠标左键（持续按住）：使用物品，滚轮：切换快捷栏
- 摄像机：跟随玩家，限制在世界边界内
- 渲染管线：天空填充 -> 地形 Surface -> 玩家绘制 -> 方块高亮 -> 快捷栏 UI -> 血条 -> 翻转
- `draw_hotbar()`：8 个槽位矩形，显示物品颜色和数量
- `draw_health_bar()`：右上角血条

**步骤 6：创建 `run.py`** — 入口文件
- Pygame 初始化，创建 1280x720 窗口，调用 game.run(screen)

### 阶段五：完善
- 方块高亮光标（鼠标悬停方块的白色边框）
- 方块交互距离检查
- 挥剑视觉效果（约 0.2 秒的线条）
- 物品数量管理（放置减少，挖掘增加）
- 挖掘冷却（不能瞬间挖，添加小延迟）

---

## 原项目关键参考

| 用途 | 原文件 | 关键行号 |
|------|--------|----------|
| 物理/碰撞 | `src/player.py` | 221-366（移动、重力、碰撞） |
| 方块交互 | `src/player.py` | 593-790（use_item、place_block、use_tool） |
| 地形生成 | `src/world.py` | 432-636（generate_terrain） |
| 地形渲染 | `src/world.py` | 644-866（surface 创建/更新） |
| 游戏循环 | `src/fegaria_remastered.py` | 812-1462（完整循环） |
| 摄像机 | `src/fegaria_remastered.py` | 865-907 |
| 常量 | `src/commons.py` | 1-93 |
| 柏林噪声 | `src/perlin.py` | 整个文件 |

## 测试验证
1. 运行 `python run.py` — 游戏窗口以 1280x720 打开
2. 玩家出现在地形表面，正确下落并着陆
3. A/D 左右移动，Space 跳跃
4. 鼠标悬停显示方块高亮边框
5. 持有镐左键点击破坏方块，物品出现在快捷栏
6. 持有方块物品左键点击放置方块，数量减少
7. 持有剑左键点击显示挥剑动画
8. 数字键 1-8 和滚轮切换快捷栏
9. ESC 退出游戏


# ver1问题
完全的各种矩形，没有泰拉瑞亚的感觉
得先把各种工具，方块以及人物的资源弄上去

# ver1.1问题
1.人物目前就是一个紫色矩形加一个头发和脚，显然不够，我要人的全身。
2.草方块和石头方块之间总是有很多空白，不知道是不是噪声地形生成导致的。这个噪声只需要确保地面是崎岖不平的即可，先别想着生成洞穴了，地下全部填满（但不仅要有石头，还要添加一定量的铜矿和铁矿（前提是原项目也做了且res里有对应资源））
3.虽然物品栏有物品图标，但是人物拿在手上的还是没有模型，需要加上。
4.泰拉瑞亚里的树是可以穿过的，现在的版本不能
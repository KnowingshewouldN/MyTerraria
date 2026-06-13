# MyTerraria

基于 [Fegaria-Remastered](https://github.com/FergusGriggs/Fegaria-Remastered) 的简化版泰拉瑞亚克隆。保留核心玩法——移动跳跃、挖掘方块、放置方块、挥剑战斗、史莱姆敌人，去除了原项目的复杂系统（生物群系、存档、粒子、光照等）。

## 功能

- Perlin 噪声生成的随机地形（草地、泥土、石头、铜矿、银矿、树木）
- 方块破坏与放置（镐、泥土、石头、木头、草）
- 玩家物理（重力、碰撞、跳跃）
- 铜剑挥砍攻击 + 史莱姆敌人 AI
- 主菜单 + 背景音乐
- 快捷栏 UI

## 快速开始

进入游戏后请将输入法调整至英文！否则将无法移动！

推荐使用 Conda 创建环境：

```bash
conda create -n Terraria python=3.13
conda activate Terraria
pip install -r requirements.txt
python run.py
```

## 操作

| 按键 | 功能 |
|------|------|
| A / D | 左右移动 |
| Space | 跳跃 |
| S | 下落（穿过平台） |
| 鼠标左键 | 使用物品（挖掘/放置/挥剑） |
| 滚轮 / 1-8 | 切换快捷栏 |
| ESC | 退出 |

## 项目结构

```
MyTerraria/
  run.py              入口
  requirements.txt    依赖
  src/
    constants.py      常量 + 方块/物品数据
    perlin.py         Simplex 噪声
    world.py          世界 + 地形生成 + 渲染
    player.py         玩家物理 + 快捷栏 + 方块交互
    slime.py          史莱姆敌人
    assets.py         资源加载（精灵图、音效、音乐）
    game.py           主菜单 + 游戏循环 + 摄像机 + UI
  res/                资源文件（来自原项目）
    images/           精灵图
    sounds/           音效
    music/            背景音乐
    fonts/            字体
```

## 致谢

- 原项目：[Fegaria-Remastered by FergusGriggs](https://github.com/FergusGriggs/Fegaria-Remastered)
- 音乐与音效来自 Terraria，版权归原作者所有

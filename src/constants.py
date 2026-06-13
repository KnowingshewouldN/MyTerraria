# constants.py - 所有游戏常量和硬编码数据
import pygame

# 窗口
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

# 方块
BLOCKSIZE = 16

# 物理
GRAVITY = 9.8 * BLOCKSIZE * 0.666
PLAYER_SPEED = 12
JUMP_VELOCITY = -50

# 玩家
PLAYER_WIDTH = 26
PLAYER_HEIGHT = 48
PLAYER_REACH = 8

# 世界
WORLD_WIDTH = 400
WORLD_HEIGHT = 200

# 方块定义: id -> {name, color, solid, drop_item}
TILES = {
    0:  {"name": "Air",        "color": None,             "solid": False, "drop_item": None},
    1:  {"name": "Grass",      "color": (76, 153, 0),     "solid": True,  "drop_item": 5},
    2:  {"name": "Dirt",       "color": (139, 90, 43),    "solid": True,  "drop_item": 2},
    3:  {"name": "Stone",      "color": (128, 128, 128),  "solid": True,  "drop_item": 3},
    4:  {"name": "Wood",       "color": (181, 137, 72),   "solid": True,  "drop_item": 4},
    5:  {"name": "CopperOre",  "color": (184, 115, 51),   "solid": True,  "drop_item": 6},
    6:  {"name": "Leaves",     "color": (34, 120, 15),    "solid": False, "drop_item": None},
    7:  {"name": "Platform",   "color": (160, 130, 80),   "solid": False, "drop_item": None},
    8:  {"name": "Trunk",      "color": (120, 80, 40),    "solid": False, "drop_item": 4},
    9:  {"name": "SilverOre",  "color": (192, 192, 192),  "solid": True,  "drop_item": 7},
    10: {"name": "Snow",       "color": (240, 240, 255),  "solid": True,  "drop_item": 9},
    11: {"name": "Ice",        "color": (150, 200, 255),  "solid": True,  "drop_item": None},
    12: {"name": "Sand",       "color": (220, 200, 150),  "solid": True,  "drop_item": 8},
    13: {"name": "Sandstone",  "color": (200, 180, 130),  "solid": True,  "drop_item": None},
    14: {"name": "SnowLeaves", "color": (200, 230, 220),  "solid": False, "drop_item": None},
    15: {"name": "Lamp",       "color": (255, 255, 200),  "solid": False, "drop_item": 12},}

AIR = 0

# 背景墙定义: id -> {name, sprite_file}
WALLS = {
    0: {"name": "None"},
    1: {"name": "DirtWall",      "sprite": "wall_dirt.png"},
    2: {"name": "StoneWall",     "sprite": "wall_stone.png"},
    3: {"name": "SnowWall",      "sprite": "wall_snow.png"},
    4: {"name": "IceWall",       "sprite": "wall_ice.png"},
    5: {"name": "SandWall",      "sprite": "wall_sand.png"},
    6: {"name": "SandstoneWall", "sprite": "wall_sandstone.png"},
}

# 群系定义: id -> {name, surface_tile, underground_tile, deep_tile, underground_wall, deep_wall, tree_leaves}
BIOMES = {
    0: {"name": "Forest",  "surface": 1,  "underground": 2,  "deep": 3,  "ug_wall": 1, "deep_wall": 2, "leaves": 6},
    1: {"name": "Snow",    "surface": 10, "underground": 10, "deep": 11, "ug_wall": 3, "deep_wall": 4, "leaves": 14},
    2: {"name": "Desert",  "surface": 12, "underground": 12, "deep": 13, "ug_wall": 5, "deep_wall": 6, "leaves": None},
}

# 物品定义
ITEMS = {
    0: {"name": "Copper Pickaxe", "color": (184, 115, 51), "is_block": False, "place_tile": None, "is_pickaxe": True,  "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 1},
    1: {"name": "Copper Sword",   "color": (200, 80, 80),  "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": True,  "is_gun": False, "damage": 15, "max_stack": 1},
    2: {"name": "Dirt",           "color": (139, 90, 43),  "is_block": True,  "place_tile": 2,    "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    3: {"name": "Stone",          "color": (128, 128, 128),"is_block": True,  "place_tile": 3,    "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    4: {"name": "Wood",           "color": (181, 137, 72), "is_block": True,  "place_tile": 4,    "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    5: {"name": "Grass",          "color": (76, 153, 0),   "is_block": True,  "place_tile": 1,    "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    6: {"name": "Copper Ore",     "color": (184, 115, 51), "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    7: {"name": "Silver Ore",     "color": (192, 192, 192),"is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    8:  {"name": "Sand",           "color": (220, 200, 150),"is_block": True,  "place_tile": 12,   "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    9:  {"name": "Snow",           "color": (240, 240, 255),"is_block": True,  "place_tile": 10,   "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    10: {"name": "Musket",         "color": (100, 80, 60),  "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": True,  "damage": 12, "max_stack": 1},
    11: {"name": "Musket Ball",    "color": (180, 180, 180),"is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 7,  "max_stack": 99},
    12: {"name": "Lamp",           "color": (255, 255, 200),"is_block": True,  "place_tile": 15,   "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    13: {"name": "Gel",            "color": (30, 180, 255), "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
    14: {"name": "Copper Coin",    "color": (200, 130, 50), "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "is_gun": False, "damage": 0,  "max_stack": 99},
}

# 默认快捷栏
DEFAULT_HOTBAR = [
    {"item_id": 0, "count": 1},
    {"item_id": 1, "count": 1},
    {"item_id": 2, "count": 99},
    {"item_id": 3, "count": 99},
    {"item_id": 4, "count": 99},
    {"item_id": 10, "count": 1},   # Musket
    {"item_id": 11, "count": 50},  # Musket Ball
    {"item_id": 12, "count": 10},  # Lamp
]

HOTBAR_SIZE = 8

# 挖掘/攻击/放置冷却
MINE_COOLDOWN = 0.25
ATTACK_COOLDOWN = 0.35
PLACE_COOLDOWN = 0.2

# 昼夜系统
DAY_DURATION = 30.0
NIGHT_DURATION = 15.0
DAY_NIGHT_CYCLE = DAY_DURATION + NIGHT_DURATION

# 颜色
SKY_COLOR = (135, 206, 235)
SLOT_BG_COLOR = (40, 40, 40)
SLOT_BORDER_COLOR = (80, 80, 80)
SLOT_SELECTED_COLOR = (255, 255, 255)
HEALTH_BAR_BG = (60, 60, 60)
HEALTH_BAR_FG = (220, 30, 30)

# 昼夜天空颜色
SKY_DAWN = (255, 180, 120)
SKY_DAY = (135, 206, 235)
SKY_SUNSET = (240, 130, 60)
SKY_NIGHT = (10, 10, 40)


def get_tile_surface(tile_id, size=BLOCKSIZE):
    """获取方块的绘制表面。优先使用精灵图，找不到则用纯色矩形备用。"""
    try:
        from assets import get_tile_surface as _get_sprite
        surf = _get_sprite(tile_id)
        if surf is not None:
            if surf.get_size() != (size, size):
                surf = pygame.transform.scale(surf, (size, size))
            return surf
    except Exception:
        pass
    tile = TILES.get(tile_id)
    if tile is None or tile["color"] is None:
        return None
    surf = pygame.Surface((size, size))
    surf.fill(tile["color"])
    return surf


def get_item_icon(item_id, size=32):
    """获取物品图标表面。已扣掉品红背景。"""
    try:
        from assets import get_item_surface
        surf = get_item_surface(item_id)
        if surf is not None:
            icon_size = min(size - 8, 32)
            scaled = pygame.transform.scale(surf, (icon_size, icon_size))
            scaled.set_colorkey((255, 0, 255))
            return scaled
    except Exception:
        pass
    item = ITEMS.get(item_id)
    if item is None:
        return None
    surf = pygame.Surface((min(size - 8, 32), min(size - 8, 32)))
    surf.fill(item["color"])
    return surf


def get_sky_color(game_time):
    """根据游戏时间计算天空颜色"""
    phase = (game_time % DAY_NIGHT_CYCLE) / DAY_NIGHT_CYCLE

    # 阶段划分（phase 0~1）:
    #   0.00 ~ 0.05  黎明过渡
    #   0.05 ~ 0.60  白天
    #   0.60 ~ 0.67  黄昏过渡
    #   0.67 ~ 1.00  黑夜（末尾黎明过渡回白天）
    if phase < 0.05:
        t = phase / 0.05
        return _lerp_color(SKY_NIGHT, SKY_DAWN, t)
    elif phase < 0.12:
        t = (phase - 0.05) / 0.07
        return _lerp_color(SKY_DAWN, SKY_DAY, t)
    elif phase < 0.58:
        return SKY_DAY
    elif phase < 0.65:
        t = (phase - 0.58) / 0.07
        return _lerp_color(SKY_DAY, SKY_SUNSET, t)
    elif phase < 0.70:
        t = (phase - 0.65) / 0.05
        return _lerp_color(SKY_SUNSET, SKY_NIGHT, t)
    else:
        return SKY_NIGHT


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )

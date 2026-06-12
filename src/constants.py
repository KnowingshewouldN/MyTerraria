# constants.py - 所有游戏常量和硬编码数据
import pygame

# 窗口
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

# 方块
BLOCKSIZE = 16

# 物理
GRAVITY = 9.8 * BLOCKSIZE * 0.666  # 与原项目一致
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
# drop_item 为 None 表示不掉落, 为 int 表示掉落的物品 id
TILES = {
    0: {"name": "Air",      "color": None,             "solid": False, "drop_item": None},
    1: {"name": "Grass",    "color": (76, 153, 0),     "solid": True,  "drop_item": 5},   # 掉落草方块物品
    2: {"name": "Dirt",     "color": (139, 90, 43),    "solid": True,  "drop_item": 2},   # 掉落泥土物品
    3: {"name": "Stone",    "color": (128, 128, 128),  "solid": True,  "drop_item": 3},   # 掉落石头物品
    4: {"name": "Wood",     "color": (181, 137, 72),   "solid": True,  "drop_item": 4},   # 掉落木头物品
    5: {"name": "CopperOre","color": (184, 115, 51),   "solid": True,  "drop_item": 6},   # 掉落铜矿石物品
    6: {"name": "Leaves",   "color": (34, 120, 15),    "solid": False, "drop_item": None},
    7: {"name": "Platform", "color": (160, 130, 80),   "solid": False, "drop_item": None},  # platform，只从上方阻挡
}

AIR = 0

# 物品定义: id -> {name, color, is_block, place_tile, is_pickaxe, is_sword, damage, max_stack}
ITEMS = {
    0: {"name": "Copper Pickaxe", "color": (184, 115, 51), "is_block": False, "place_tile": None, "is_pickaxe": True,  "is_sword": False, "damage": 0,  "max_stack": 1},
    1: {"name": "Copper Sword",   "color": (200, 80, 80),  "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": True,  "damage": 15, "max_stack": 1},
    2: {"name": "Dirt",           "color": (139, 90, 43),  "is_block": True,  "place_tile": 2,    "is_pickaxe": False, "is_sword": False, "damage": 0,  "max_stack": 99},
    3: {"name": "Stone",          "color": (128, 128, 128),"is_block": True,  "place_tile": 3,    "is_pickaxe": False, "is_sword": False, "damage": 0,  "max_stack": 99},
    4: {"name": "Wood",           "color": (181, 137, 72), "is_block": True,  "place_tile": 4,    "is_pickaxe": False, "is_sword": False, "damage": 0,  "max_stack": 99},
    5: {"name": "Grass",          "color": (76, 153, 0),   "is_block": True,  "place_tile": 1,    "is_pickaxe": False, "is_sword": False, "damage": 0,  "max_stack": 99},
    6: {"name": "Copper Ore",     "color": (184, 115, 51), "is_block": False, "place_tile": None, "is_pickaxe": False, "is_sword": False, "damage": 0,  "max_stack": 99},
}

# 默认快捷栏: list of {"item_id": int, "count": int} or None
DEFAULT_HOTBAR = [
    {"item_id": 0, "count": 1},   # 铜镐
    {"item_id": 1, "count": 1},   # 铜剑
    {"item_id": 2, "count": 99},  # 泥土
    {"item_id": 3, "count": 99},  # 石头
    {"item_id": 4, "count": 99},  # 木头
    None,
    None,
    None,
]

HOTBAR_SIZE = 8

# 挖掘冷却（秒）
MINE_COOLDOWN = 0.25
# 攻击冷却（秒）
ATTACK_COOLDOWN = 0.35

# 颜色常量
SKY_COLOR = (135, 206, 235)
SLOT_BG_COLOR = (40, 40, 40)
SLOT_BORDER_COLOR = (80, 80, 80)
SLOT_SELECTED_COLOR = (255, 255, 255)
HEALTH_BAR_BG = (60, 60, 60)
HEALTH_BAR_FG = (220, 30, 30)


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
    # 备用：纯色矩形
    tile = TILES.get(tile_id)
    if tile is None or tile["color"] is None:
        return None
    surf = pygame.Surface((size, size))
    surf.fill(tile["color"])
    return surf


def get_item_icon(item_id, size=32):
    """获取物品图标表面。优先使用精灵图，找不到则用纯色矩形备用。"""
    try:
        from assets import get_item_surface
        surf = get_item_surface(item_id)
        if surf is not None:
            icon_size = min(size - 8, 32)
            surf = pygame.transform.scale(surf, (icon_size, icon_size))
            return surf
    except Exception:
        pass
    # 备用：纯色矩形
    item = ITEMS.get(item_id)
    if item is None:
        return None
    surf = pygame.Surface((min(size - 8, 32), min(size - 8, 32)))
    surf.fill(item["color"])
    return surf

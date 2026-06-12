# assets.py - 统一加载和管理所有精灵图资源
import pygame
import os

# 基础路径
RES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "res")
IMAGES_PATH = os.path.join(RES_PATH, "images")
TILES_PATH = os.path.join(IMAGES_PATH, "tiles")
ITEMS_PATH = os.path.join(IMAGES_PATH, "items")
FONTS_PATH = os.path.join(RES_PATH, "fonts")

# 方块精灵缓存: tile_id -> pygame.Surface (16x16)
tile_surfaces = {}

# 物品精灵缓存: item_id -> pygame.Surface (16x16)
item_surfaces = {}

# GUI 精灵
gui_surfaces = []

# 玩家身体精灵（torso tileset: 19帧 x 4行，每帧 20x30，放大2x = 40x60）
torso_frames = []
# 玩家头发精灵（hair tileset: 10种，每种 22x24，放大2x）
hair_frames = []

# 字体
font_small = None
font_default = None
font_large = None


def init():
    """初始化加载所有资源，必须在 pygame.init() 之后调用"""
    global font_small, font_default, font_large

    _load_tile_surfaces()
    _load_item_surfaces()
    _load_gui_surfaces()
    _load_torso_surfaces()
    _load_hair_surfaces()
    _load_fonts()


def _load_tile_surfaces():
    """加载方块精灵图，8x8 -> 放大到 16x16"""
    global tile_surfaces

    # 方块 ID -> 文件名映射
    tile_files = {
        0: "air.png",
        1: "grass.png",
        2: "dirt.png",
        3: "stone.png",
        4: "wood.png",           # 放置的木头方块
        5: "copper.png",         # 铜矿
        6: "leaves.png",         # 树叶
        7: "platform_wood.png",  # 平台
        8: "trunk.png",          # 树干（可穿过）
        9: "silver.png",         # 银矿
    }

    for tile_id, filename in tile_files.items():
        filepath = os.path.join(TILES_PATH, filename)
        if os.path.exists(filepath):
            img = pygame.image.load(filepath).convert_alpha()
            # 原始 8x8，放大到 16x16
            if img.get_size() != (16, 16):
                img = pygame.transform.scale(img, (16, 16))
            tile_surfaces[tile_id] = img


def _load_item_surfaces():
    """加载物品精灵图"""
    global item_surfaces

    # 物品 ID -> 文件名映射
    item_files = {
        0: "copper_pickaxe.png",
        1: "sword_copper.png",
        2: "dirt.png",
        3: "stone.png",
        4: "wood.png",
        5: "grass.png",
        6: "copper.png",
        7: "silver.png",
    }

    for item_id, filename in item_files.items():
        filepath = os.path.join(ITEMS_PATH, filename)
        if os.path.exists(filepath):
            img = pygame.image.load(filepath).convert_alpha()
            item_surfaces[item_id] = img


def _load_gui_surfaces():
    """加载 GUI 精灵（物品栏槽位等）"""
    global gui_surfaces
    filepath = os.path.join(IMAGES_PATH, "miscGUI.png")
    if os.path.exists(filepath):
        gui_img = pygame.image.load(filepath).convert()
        gui_img.set_colorkey((255, 0, 255))
        gui_surfaces = []
        for i in range(11):
            surf = pygame.Surface((48, 48))
            surf.set_colorkey((255, 0, 255))
            surf.blit(gui_img, (-i * 48, 0))
            gui_surfaces.append(surf)


def _load_torso_surfaces():
    """加载玩家身体精灵表"""
    global torso_frames
    filepath = os.path.join(IMAGES_PATH, "torsoTileset.png")
    if not os.path.exists(filepath):
        return

    scale = 2
    torso_img = pygame.image.load(filepath).convert()
    torso_img.set_colorkey((255, 0, 255))
    torso_img = pygame.transform.scale(torso_img,
        (int(20 * 19 * scale), int(30 * 4 * scale)))

    torso_frames = []
    for row in range(4):
        for col in range(19):
            surf = pygame.Surface((int(20 * scale), int(30 * scale)))
            surf.set_colorkey((255, 0, 255))
            surf.blit(torso_img, (-col * 20 * scale, -row * 30 * scale))
            torso_frames.append(surf)


def _load_hair_surfaces():
    """加载头发精灵表"""
    global hair_frames
    filepath = os.path.join(IMAGES_PATH, "hairsTileset.png")
    if not os.path.exists(filepath):
        return

    scale = 2
    hair_img = pygame.image.load(filepath).convert()
    hair_img.set_colorkey((255, 0, 255))
    hair_img = pygame.transform.scale(hair_img,
        (int(22 * 10 * scale), int(24 * scale)))

    hair_frames = []
    for i in range(10):
        surf = pygame.Surface((int(22 * scale), int(24 * scale)))
        surf.set_colorkey((255, 0, 255))
        surf.blit(hair_img, (-i * 22 * scale, 0))
        surf = pygame.transform.scale(surf, (int(20 * scale), int(24 * scale)))
        surf.set_colorkey((255, 0, 255))
        hair_frames.append(surf)


def _load_fonts():
    """加载字体"""
    global font_small, font_default, font_large
    font_path = os.path.join(FONTS_PATH, "VCR_OSD_MONO_1.001.ttf")
    if os.path.exists(font_path):
        font_small = pygame.font.Font(font_path, 12)
        font_default = pygame.font.Font(font_path, 18)
        font_large = pygame.font.Font(font_path, 30)
    else:
        font_small = pygame.font.Font(None, 14)
        font_default = pygame.font.Font(None, 20)
        font_large = pygame.font.Font(None, 32)


def get_tile_surface(tile_id):
    """获取方块精灵，找不到则返回纯色矩形备用"""
    surf = tile_surfaces.get(tile_id)
    if surf is not None:
        return surf
    # 备用：纯色矩形
    import constants as C
    tile = C.TILES.get(tile_id)
    if tile and tile["color"]:
        s = pygame.Surface((16, 16))
        s.fill(tile["color"])
        return s
    return None


def get_item_surface(item_id):
    """获取物品精灵"""
    return item_surfaces.get(item_id)


def get_gui_slot_surface():
    """获取物品栏槽位精灵"""
    if gui_surfaces:
        return gui_surfaces[0]  # 第一个 GUI 元素是空槽位
    return None


def get_gui_selected_slot_surface():
    """获取选中的槽位精灵"""
    if len(gui_surfaces) > 1:
        return gui_surfaces[1]  # 第二个是选中状态
    return None

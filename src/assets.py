# assets.py - 统一加载和管理所有精灵图资源和音效
import pygame
import os
import random

# 基础路径
RES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "res")
IMAGES_PATH = os.path.join(RES_PATH, "images")
TILES_PATH = os.path.join(IMAGES_PATH, "tiles")
ITEMS_PATH = os.path.join(IMAGES_PATH, "items")
FONTS_PATH = os.path.join(RES_PATH, "fonts")
SOUNDS_PATH = os.path.join(RES_PATH, "sounds")

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

# 音效
sounds_enabled = True
sound_cache = {}


def init():
    """初始化加载所有资源，必须在 pygame.init() 之后调用"""
    global font_small, font_default, font_large

    _load_tile_surfaces()
    _load_item_surfaces()
    _load_gui_surfaces()
    _load_torso_surfaces()
    _load_hair_surfaces()
    _load_fonts()
    _init_sounds()


def _load_tile_surfaces():
    global tile_surfaces
    tile_files = {
        0: "air.png", 1: "grass.png", 2: "dirt.png", 3: "stone.png",
        4: "wood.png", 5: "copper.png", 6: "leaves.png", 7: "platform_wood.png",
        8: "trunk.png", 9: "silver.png",
    }
    for tile_id, filename in tile_files.items():
        filepath = os.path.join(TILES_PATH, filename)
        if os.path.exists(filepath):
            img = pygame.image.load(filepath).convert_alpha()
            if img.get_size() != (16, 16):
                img = pygame.transform.scale(img, (16, 16))
            tile_surfaces[tile_id] = img


def _load_item_surfaces():
    global item_surfaces
    item_files = {
        0: "copper_pickaxe.png", 1: "sword_copper.png", 2: "dirt.png",
        3: "stone.png", 4: "wood.png", 5: "grass.png", 6: "copper.png",
        7: "silver.png",
    }
    for item_id, filename in item_files.items():
        filepath = os.path.join(ITEMS_PATH, filename)
        if os.path.exists(filepath):
            img = pygame.image.load(filepath).convert_alpha()
            item_surfaces[item_id] = img


def _load_gui_surfaces():
    global gui_surfaces
    filepath = os.path.join(IMAGES_PATH, "miscGUI.png")
    if os.path.exists(filepath):
        gui_img = pygame.image.load(filepath).convert()
        gui_img.set_colorkey((255, 0, 255))
        for i in range(11):
            surf = pygame.Surface((48, 48))
            surf.set_colorkey((255, 0, 255))
            surf.blit(gui_img, (-i * 48, 0))
            gui_surfaces.append(surf)


def _load_torso_surfaces():
    """加载玩家身体精灵表 - 完全匹配原项目加载方式"""
    global torso_frames
    filepath = os.path.join(IMAGES_PATH, "torsoTileset.png")
    if not os.path.exists(filepath):
        return

    scale = 2
    # 关键：不调用 convert()，直接 load + scale，保留 PNG 透明通道
    torso_img = pygame.transform.scale(
        pygame.image.load(filepath),
        (int(20 * 19 * scale), int(30 * 4 * scale))
    )

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
    hair_img = pygame.transform.scale(
        pygame.image.load(filepath),
        (int(22 * 10 * scale), int(24 * scale))
    )

    hair_frames = []
    for i in range(10):
        surf = pygame.Surface((int(22 * scale), int(24 * scale)))
        surf.set_colorkey((255, 0, 255))
        surf.blit(hair_img, (-i * 22 * scale, 0))
        surf = pygame.transform.scale(surf, (int(20 * scale), int(24 * scale)))
        surf.set_colorkey((255, 0, 255))
        hair_frames.append(surf)


def _load_fonts():
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


def _init_sounds():
    """初始化音效系统"""
    try:
        pygame.mixer.init()
    except Exception:
        pass


def play_sound(name, volume=0.5):
    """播放音效，支持随机变体（如 dig_0, dig_1, dig_2）"""
    if not sounds_enabled:
        return

    # 查找可能的变体
    base_path = os.path.join(SOUNDS_PATH, name)
    if os.path.exists(base_path):
        filepath = base_path
    else:
        # 尝试随机变体: name_0, name_1, ...
        variants = []
        i = 0
        while True:
            vpath = os.path.join(SOUNDS_PATH, f"{name}_{i}.wav")
            if os.path.exists(vpath):
                variants.append(vpath)
                i += 1
            else:
                break
        if not variants:
            return
        filepath = random.choice(variants)

    if filepath not in sound_cache:
        try:
            sound_cache[filepath] = pygame.mixer.Sound(filepath)
            sound_cache[filepath].set_volume(volume)
        except Exception:
            return

    try:
        sound_cache[filepath].play()
    except Exception:
        pass


def get_tile_surface(tile_id):
    surf = tile_surfaces.get(tile_id)
    if surf is not None:
        return surf
    import constants as C
    tile = C.TILES.get(tile_id)
    if tile and tile["color"]:
        s = pygame.Surface((16, 16))
        s.fill(tile["color"])
        return s
    return None


def get_item_surface(item_id):
    return item_surfaces.get(item_id)


def get_gui_slot_surface():
    if gui_surfaces:
        return gui_surfaces[0]
    return None


def get_gui_selected_slot_surface():
    if len(gui_surfaces) > 1:
        return gui_surfaces[1]
    return None

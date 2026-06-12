# assets.py - 统一加载和管理所有精灵图资源和音效
import pygame
import os
import random
import math

# 基础路径
RES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "res")
IMAGES_PATH = os.path.join(RES_PATH, "images")
TILES_PATH = os.path.join(IMAGES_PATH, "tiles")
ITEMS_PATH = os.path.join(IMAGES_PATH, "items")
FONTS_PATH = os.path.join(RES_PATH, "fonts")
SOUNDS_PATH = os.path.join(RES_PATH, "sounds")

# 方块精灵缓存: tile_id -> pygame.Surface (16x16)
tile_surfaces = {}

# 物品精灵缓存: item_id -> pygame.Surface (16x16, colorkey applied)
item_surfaces = {}
# 物品世界渲染精灵（放大版，用于手持）
item_world_surfaces = {}

# GUI 精灵
gui_surfaces = []

# 玩家身体精灵（torso tileset: 76帧）
torso_frames = []
# 玩家头发精灵
hair_frames = []

# 玩家合成精灵（照搬原项目 render_sprites）
player_sprites = []      # 身体精灵（30帧：15朝右 + 15朝左）
player_arm_sprites = []  # 手臂精灵（40帧：20朝右 + 20朝左）

# 史莱姆精灵（5种×3帧 = 15帧，放大2x）
slime_surfaces = []

# 字体
font_small = None
font_default = None
font_large = None

# 音效
sounds_enabled = True
sound_cache = {}


def init():
    global font_small, font_default, font_large
    _load_tile_surfaces()
    _load_item_surfaces()
    _load_gui_surfaces()
    _load_torso_surfaces()
    _load_hair_surfaces()
    _load_slime_surfaces()
    _render_player_sprites()
    _load_fonts()
    try:
        pygame.mixer.init()
    except Exception:
        pass


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
    """加载物品精灵，扣掉品红背景"""
    global item_surfaces, item_world_surfaces
    item_files = {
        0: "copper_pickaxe.png", 1: "sword_copper.png", 2: "dirt.png",
        3: "stone.png", 4: "wood.png", 5: "grass.png", 6: "copper.png",
        7: "silver.png",
    }
    for item_id, filename in item_files.items():
        filepath = os.path.join(ITEMS_PATH, filename)
        if os.path.exists(filepath):
            img = pygame.image.load(filepath).convert()
            img.set_colorkey((255, 0, 255))
            item_surfaces[item_id] = img
            # 创建放大版用于手持渲染
            world_size = 32
            world_img = pygame.transform.scale(img, (world_size, world_size))
            world_img.set_colorkey((255, 0, 255))
            item_world_surfaces[item_id] = world_img


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
    """加载身体精灵表 - 不调用 convert，保留原始格式"""
    global torso_frames
    filepath = os.path.join(IMAGES_PATH, "torsoTileset.png")
    if not os.path.exists(filepath):
        return
    scale = 2
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


def _load_slime_surfaces():
    """加载史莱姆精灵表"""
    global slime_surfaces
    filepath = os.path.join(IMAGES_PATH, "slimeTileset.png")
    if not os.path.exists(filepath):
        return
    scale = 2
    slime_img = pygame.transform.scale(
        pygame.image.load(filepath),
        (int(16 * 3 * scale), int(12 * 5 * scale))
    )
    slime_surfaces = []
    for row in range(5):
        for col in range(3):
            surf = pygame.Surface((int(16 * scale), int(12 * scale)))
            surf.set_colorkey((255, 0, 255))
            surf.blit(slime_img, (-col * 16 * scale, -row * 12 * scale))
            surf.set_alpha(200)
            slime_surfaces.append(surf)


def play_music(filename, volume=0.5, loops=-1):
    """播放背景音乐"""
    try:
        filepath = os.path.join(RES_PATH, "music", filename)
        if os.path.exists(filepath):
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops)
    except Exception:
        pass


def stop_music():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


def _render_player_sprites():
    """照搬原项目 render_sprites，合成玩家身体精灵"""
    global player_sprites, player_arm_sprites
    if not torso_frames or not hair_frames:
        return

    # 默认颜色
    shirt_col = (70, 130, 180)
    trouser_col = (100, 70, 50)
    shoe_col = (60, 40, 30)
    under_shirt_col = (200, 200, 200)
    skin_col = (230, 190, 150)
    hair_col = (80, 50, 30)
    eye_col = (30, 30, 30)

    player_sprites = []
    player_arm_sprites = []

    for direction in range(2):
        hair_surf = colour_surface(hair_frames[0], hair_col)
        if direction == 1:
            hair_surf = pygame.transform.flip(hair_surf, True, False)

        # torso_frames[0] 是 shirt 静态帧
        shirt_surf = colour_surface(torso_frames[0], shirt_col)
        if direction == 0:
            shirt_surf = pygame.transform.flip(shirt_surf, True, False)

        # hair_frames[9] 用作头部（皮肤色）
        head_surf = colour_surface(hair_frames[min(9, len(hair_frames) - 1)], skin_col)
        pygame.draw.rect(head_surf, (255, 254, 255), pygame.Rect(20, 22, 4, 4))
        pygame.draw.rect(head_surf, eye_col, pygame.Rect(22, 22, 2, 4))
        if direction == 1:
            head_surf = pygame.transform.flip(head_surf, True, False)

        # 身体帧（15帧/方向）
        for i in range(15):
            body_surf = pygame.Surface((44, 75))
            body_surf.fill((255, 0, 255))
            body_surf.set_colorkey((255, 0, 255))

            trousers = colour_surface(torso_frames[i + 1], trouser_col)
            if direction == 0:
                trousers = pygame.transform.flip(trousers, True, False)

            shoes = colour_surface(torso_frames[i + 16], shoe_col)
            if direction == 0:
                shoes = pygame.transform.flip(shoes, True, False)

            body_surf.blit(shirt_surf, (0, 4))
            body_surf.blit(trousers, (0, 4))
            body_surf.blit(shoes, (0, 4))
            body_surf.blit(head_surf, (0, 0))
            body_surf.blit(hair_surf, (0, 0))

            player_sprites.append(body_surf)

        # 手臂帧（20帧/方向）
        for i in range(20):
            arm_surf = pygame.Surface((44, 75))
            arm_surf.fill((255, 0, 255))
            arm_surf.set_colorkey((255, 0, 255))

            arms = colour_surface(torso_frames[i + 31], under_shirt_col)
            if direction == 0:
                arms = pygame.transform.flip(arms, True, False)

            hands = colour_surface(torso_frames[i + 51], skin_col)
            if direction == 0:
                hands = pygame.transform.flip(hands, True, False)

            arm_surf.blit(arms, (0, 4))
            arm_surf.blit(hands, (0, 4))

            player_arm_sprites.append(arm_surf)


def colour_surface(grey_surf, col):
    """照搬原项目 shared_methods.colour_surface - 给灰度精灵上色"""
    if col == ():
        col = (0, 0, 0)
    x = grey_surf.get_width()
    y = grey_surf.get_height()
    surf = pygame.Surface((x, y))
    surf.fill((255, 255, 255))
    surf.set_colorkey((255, 255, 255))
    surf.blit(grey_surf, (0, 0))
    colour = pygame.Surface((x, y))
    colour.fill(col)
    surf.blit(colour, (0, 0), None, pygame.BLEND_RGB_ADD)
    return surf


def rotate_surface(image, angle):
    """照搬原项目 shared_methods.rotate_surface"""
    original_rect = image.get_rect()
    rotated_image = pygame.transform.rotate(image, angle)
    rotated_rect = original_rect.copy()
    rotated_rect.center = rotated_image.get_rect().center
    rotated_image = rotated_image.subsurface(rotated_rect).copy()
    return rotated_image


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


def play_sound(name, volume=0.5):
    if not sounds_enabled:
        return
    base_path = os.path.join(SOUNDS_PATH, name)
    if os.path.exists(base_path):
        filepath = base_path
    else:
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


def get_item_world_surface(item_id):
    """获取物品的放大版世界精灵（扣掉背景）"""
    return item_world_surfaces.get(item_id)


def get_gui_slot_surface():
    if gui_surfaces:
        return gui_surfaces[0]
    return None


def get_gui_selected_slot_surface():
    if len(gui_surfaces) > 1:
        return gui_surfaces[1]
    return None

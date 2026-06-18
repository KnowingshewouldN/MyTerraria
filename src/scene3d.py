# scene3d.py - 击败 Boss 后的 3D 体素胜利场景（PyOpenGL + pygame.OPENGL）
#
# 独立模块：切换显示模式到 OpenGL，渲染一个可飞行探索的小型体素世界，
# King Slime 的 gif 作为 billboard 立在中央当战利品。ESC 返回。
import pygame
import math
import random
from OpenGL.GL import *
import constants as C

# ---- 场景配置 ----
WORLD_SIZE = 40          # 地面边长（立方体数）
MAX_H = 8                # 最大高度
EYE_HEIGHT = 1.7
MOVE_SPEED = 7.0         # 单位/秒
LOOK_SENS = 0.15
KING_LIFT = 1.2          # 史莱姆王整体上移量（贴图底部有空边时会显得“沉地”，调大即升高）

# ---- 行走物理 ----
GRAVITY_3D = 28.0        # 下落加速度（单位/秒²）
JUMP_SPEED_3D = 9.0      # 起跳初速度（约能跳 ~1.4 格高）
WALK_SPEED = 5.0         # 水平行走速度
PLAYER_HALF_W = 0.3      # 玩家碰撞框半宽（共 0.6 宽）
PLAYER_HEIGHT_3D = 1.8   # 玩家碰撞框高度

# 图集槽位编号
SLOT_GRASS, SLOT_DIRT, SLOT_STONE, SLOT_WOOD, SLOT_LEAVES, SLOT_SAND, SLOT_SNOW = range(7)
ATLAS_COLS = 4
ATLAS_CELL = 16          # 每个槽 16x16
ATLAS_SIZE = ATLAS_COLS * ATLAS_CELL  # 64

# ---- 挖/放 ----
REACH_3D = 6.0           # 挖/放 reach（方块数）
# 数字键 1-6 选择的可放置方块
PLACEABLE_BLOCKS = [SLOT_DIRT, SLOT_STONE, SLOT_WOOD, SLOT_SAND, SLOT_SNOW, SLOT_GRASS]
PLACEABLE_NAMES = ["Dirt", "Stone", "Wood", "Sand", "Snow", "Grass"]
SLOT_COLORS = {
    SLOT_GRASS: (90, 160, 40), SLOT_DIRT: (139, 90, 43), SLOT_STONE: (128, 128, 128),
    SLOT_WOOD: (181, 137, 72), SLOT_LEAVES: (34, 120, 15), SLOT_SAND: (220, 200, 150),
    SLOT_SNOW: (240, 240, 255),
}

# 立方体 6 面：每面 4 个顶点偏移（按周长顺序），法线 + 亮度
# 关键：每个面的顶点必须真的落在该法线所指的平面上，否则剔除判定（看邻居）
# 与实际绘制几何会错位，导致相邻方块暴露的某一面被错误剔除（看起来透明）。
FACES = [
    # name, normal, brightness, [(dx,dy,dz)x4]
    ("top",    (0, 1, 0), 1.00, [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]),   # y=1
    ("bottom", (0, -1, 0), 0.50, [(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)]),   # y=0
    ("north",  (0, 0, -1), 0.80, [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),   # z=0
    ("south",  (0, 0, 1), 0.80, [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)]),    # z=1
    ("east",   (1, 0, 0), 0.65, [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),    # x=1
    ("west",   (-1, 0, 0), 0.65, [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),   # x=0
]
# 邻居偏移（与 FACES 同顺序：top,bottom,north,south,east,west）
NEIGHBORS = [(0, 1, 0), (0, -1, 0), (0, 0, -1), (0, 0, 1), (1, 0, 0), (-1, 0, 0)]


# ============================================================
# 资源构建
# ============================================================
def _build_atlas():
    """把需要的方块精灵拼成一张 64x64 图集 Surface，返回 (surface, slot_uv)"""
    import os
    tiles_dir = os.path.join("res", "images", "tiles")
    sources = {
        SLOT_GRASS: "grass.png",
        SLOT_DIRT: "dirt.png",
        SLOT_STONE: "stone.png",
        SLOT_WOOD: "wood.png",
        SLOT_LEAVES: "leaves.png",
        SLOT_SAND: "sand.png",
        SLOT_SNOW: "snow.png",
    }
    atlas = pygame.Surface((ATLAS_SIZE, ATLAS_SIZE))
    atlas.fill((0, 0, 0))
    for slot, fname in sources.items():
        path = os.path.join(tiles_dir, fname)
        col = slot % ATLAS_COLS
        row = slot // ATLAS_COLS
        try:
            img = pygame.image.load(path)
            img = pygame.transform.scale(img, (ATLAS_CELL, ATLAS_CELL))
            atlas.blit(img, (col * ATLAS_CELL, row * ATLAS_CELL))
        except Exception:
            # 备用纯色
            color = [(76, 153, 0), (139, 90, 43), (128, 128, 128),
                     (181, 137, 72), (34, 120, 15), (220, 200, 150), (240, 240, 255)][slot]
            pygame.draw.rect(atlas, color,
                             (col * ATLAS_CELL, row * ATLAS_CELL, ATLAS_CELL, ATLAS_CELL))
    slot_uv = {}
    for slot in range(ATLAS_COLS * ATLAS_COLS):
        col = slot % ATLAS_COLS
        row = slot // ATLAS_COLS
        u0 = col / ATLAS_COLS
        v0 = 1.0 - (row + 1) / ATLAS_COLS   # GL 的 v=0 在底部，翻转
        u1 = (col + 1) / ATLAS_COLS
        v1 = 1.0 - row / ATLAS_COLS
        slot_uv[slot] = (u0, v0, u1, v1)
    return atlas, slot_uv


def _surface_to_texture(surface, flip=True, opaque=False):
    """pygame Surface -> OpenGL 纹理 id（RGBA）。
    opaque=True 时强制所有像素 alpha=255，用于地形图集（彻底杜绝侧面透明）。
    """
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    rgba = pygame.image.tostring(surface, "RGBA", flip)
    if opaque:
        b = bytearray(rgba)
        for i in range(3, len(b), 4):
            b[i] = 255
        rgba = bytes(b)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(), surface.get_height(),
                 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    return tex


# ---- 手持物品 / 热栏 ----
# 热栏布局：槽 0=稿子，槽 1=剑，槽 2-7=方块（对应 PLACEABLE_BLOCKS）
HOTBAR_SLOTS = 8
BLOCK_SLOT_BASE = 2                       # 槽 2 开始是方块
HELD_ICON_PX = 96                         # 手持物品屏幕贴片边长（像素）
HELD_POS = (C.WINDOW_WIDTH - 160, C.WINDOW_HEIGHT - 160)   # 贴片左上角
SWING_DURATION = 0.28                     # 挥动动画时长（秒）
SWING_MAX_ANGLE = 42.0                    # 挥动最大角度（度）
HAND_COLOR = (224, 188, 144)              # 程序化手的肤色（占位，可后续换贴图）
HOTBAR_CELL = 54
HOTBAR_GAP = 4
HOTBAR_PAD = 6

# 工具图标（res/images/items/）
TOOL_ICON_FILES = ["copper_pickaxe.png", "sword_copper.png"]
# 方块图标（与 PLACEABLE_BLOCKS 顺序一致）
BLOCK_ICON_FILES = ["dirt.png", "stone.png", "wood.png", "sand.png", "snow.png", "grass.png"]


def _load_icon_surface(fname, scale=4):
    """从 res/images/items/ 加载图标，抠掉品红底，返回放大后的 SRCALPHA Surface。失败返回 None。"""
    import os
    path = os.path.join("res", "images", "items", fname)
    try:
        img = pygame.image.load(path).convert()
        img.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        w, h = img.get_size()
        big = pygame.transform.scale(img, (w * scale, h * scale))
        out = pygame.Surface(big.get_size(), pygame.SRCALPHA)
        out.blit(big, (0, 0))
        return out
    except Exception:
        return None


def _load_slime_cube_texture(path):
    """从 MC 史莱姆展开图裁出一个 8×8 身体面，放大并强制不透明，作为方块六面贴图。"""
    try:
        img = pygame.image.load(path).convert_alpha()
        face = pygame.Surface((8, 8), pygame.SRCALPHA)
        face.blit(img, (0, 0), area=pygame.Rect(8, 8, 8, 8))   # 侧面面板之一
        big = pygame.transform.scale(face, (32, 32))
        return _surface_to_texture(big, flip=True, opaque=True)
    except Exception:
        return None


def _build_hotbar_surface(font, inv_counts, sel_idx, tool_surfs):
    """构建 8 格热栏 Surface：稿子/剑 + 6 方块（带数量/序号/选中高亮）。"""
    n = HOTBAR_SLOTS
    inner_w = HOTBAR_CELL * n + HOTBAR_GAP * (n - 1) + HOTBAR_PAD * 2
    inner_h = HOTBAR_CELL + HOTBAR_PAD * 2
    surf = pygame.Surface((inner_w, inner_h), pygame.SRCALPHA)
    for i in range(n):
        cx = HOTBAR_PAD + i * (HOTBAR_CELL + HOTBAR_GAP)
        cy = HOTBAR_PAD
        rect = pygame.Rect(cx, cy, HOTBAR_CELL, HOTBAR_CELL)
        pygame.draw.rect(surf, (18, 18, 22, 210), rect)
        if i < BLOCK_SLOT_BASE:
            ic = tool_surfs[i]
            if ic is not None:
                surf.blit(ic, (cx + (HOTBAR_CELL - ic.get_width()) // 2,
                               cy + (HOTBAR_CELL - ic.get_height()) // 2))
            else:
                col = [(180, 150, 90), (200, 200, 220)][i]
                pygame.draw.rect(surf, col, rect.inflate(-12, -12))
        else:
            bi = i - BLOCK_SLOT_BASE
            col = SLOT_COLORS[PLACEABLE_BLOCKS[bi]]
            pygame.draw.rect(surf, col, rect.inflate(-8, -8))
            cnt_txt = font.render(str(inv_counts[bi]), True, (255, 255, 255))
            surf.blit(cnt_txt, (cx + HOTBAR_CELL - cnt_txt.get_width() - 4,
                                cy + HOTBAR_CELL - cnt_txt.get_height() - 2))
        num_txt = font.render(str(i + 1), True, (200, 200, 200))
        surf.blit(num_txt, (cx + 3, cy + 2))
        if i == sel_idx:
            pygame.draw.rect(surf, (255, 255, 255), rect, 2)
        else:
            pygame.draw.rect(surf, (80, 80, 80), rect, 1)
    return surf


# ============================================================
# 体素地形
# ============================================================
def _build_terrain():
    """生成体素占用网格 + 每个立方体的图集槽位；返回 (solid, type_grid)"""
    random.seed(7)
    W = WORLD_SIZE
    solid = [[[False] * MAX_H for _ in range(W)] for _ in range(W)]
    tgrid = [[[0] * MAX_H for _ in range(W)] for _ in range(W)]  # 0 = air marker

    # 高度图：基础 + 双正弦丘陵
    height = [[0] * W for _ in range(W)]
    for x in range(W):
        for z in range(W):
            h = 2
            h += int(1.6 * math.sin(x * 0.32) * math.cos(z * 0.27))
            h += int(1.1 * math.sin(x * 0.13 + 1.3))
            height[x][z] = max(0, min(MAX_H - 2, h))

    # 群系色带（森林 / 雪 / 沙漠）
    for x in range(W):
        for z in range(W):
            h = height[x][z]
            if x < W // 3:
                surface_slot, sub_slot, deep_slot = SLOT_GRASS, SLOT_DIRT, SLOT_STONE
            elif x < 2 * W // 3:
                surface_slot, sub_slot, deep_slot = SLOT_SNOW, SLOT_SNOW, SLOT_STONE
            else:
                surface_slot, sub_slot, deep_slot = SLOT_SAND, SLOT_SAND, SLOT_STONE
            for y in range(h + 1):
                solid[x][z][y] = True
                if y == h:
                    tgrid[x][z][y] = surface_slot
                elif y >= h - 1:
                    tgrid[x][z][y] = sub_slot
                else:
                    tgrid[x][z][y] = deep_slot

    # 森林带散布树木
    for _ in range(14):
        x = random.randint(2, W // 3 - 2)
        z = random.randint(2, W - 3)
        base = height[x][z]
        if base + 4 >= MAX_H:
            continue
        # 树干
        for ty in range(base + 1, base + 4):
            solid[x][z][ty] = True
            tgrid[x][z][ty] = SLOT_WOOD
        # 树冠（3x3x1 + 中心高一层）
        top = base + 3
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                lx, lz = x + dx, z + dz
                if 0 <= lx < W and 0 <= lz < W and top < MAX_H:
                    if dx == 0 and dz == 0:
                        continue
                    solid[lx][lz][top] = True
                    tgrid[lx][lz][top] = SLOT_LEAVES
        if top + 1 < MAX_H:
            solid[x][z][top + 1] = True
            tgrid[x][z][top + 1] = SLOT_LEAVES

    return solid, tgrid, height


def _face_slot_for(tgrid, x, y, z, face_name):
    """该立方体在该面应使用的图集槽位（顶面用自身类型；木头的顶/底也用木纹）"""
    slot = tgrid[x][z][y]
    if slot == SLOT_GRASS and face_name == "top":
        return SLOT_GRASS
    return slot


def _build_face_arrays(solid, tgrid, slot_uv):
    """遍历体素，收集所有外露面 -> 顶点/UV/颜色数组"""
    W = WORLD_SIZE
    positions = []
    uvs = []
    colors = []

    for x in range(W):
        for z in range(W):
            for y in range(MAX_H):
                if not solid[x][z][y]:
                    continue
                for i, (face_name, normal, bright, verts) in enumerate(FACES):
                    if face_name == "bottom":
                        continue  # 底面永远看不到，跳过
                    nx, ny, nz = x + NEIGHBORS[i][0], y + NEIGHBORS[i][1], z + NEIGHBORS[i][2]
                    # 邻居在网格内且 solid -> 不外露
                    if 0 <= nx < W and 0 <= nz < W and 0 <= ny < MAX_H:
                        if solid[nx][nz][ny]:
                            continue
                    slot = _face_slot_for(tgrid, x, y, z, face_name)
                    u0, v0, u1, v1 = slot_uv[slot]
                    face_uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                    # 用两个三角形 (0,1,2)+(0,2,3) 替代四边形——GL_TRIANGLES 在所有驱动上
                    # 都比 GL_QUADS 可靠，避免某些面被驱动错误地丢弃（看起来像“透明”）。
                    for ti in (0, 1, 2, 0, 2, 3):
                        dx, dy, dz = verts[ti]
                        u, v = face_uv[ti]
                        positions.append((x + dx, y + dy, z + dz))
                        uvs.append((u, v))
                        colors.append((bright, bright, bright))
    return positions, uvs, colors


def _upload_vbo(positions, uvs, colors):
    """把顶点数据装进 VBO，返回 vbo_id + 顶点数"""
    import numpy as np
    vbo_id = glGenBuffers(1)
    # 交错：pos(3) + uv(2) + color(3) = 8 floats / 顶点
    interleaved = []
    for p, uv, c in zip(positions, uvs, colors):
        interleaved.extend([p[0], p[1], p[2], uv[0], uv[1], c[0], c[1], c[2]])
    arr = np.array(interleaved, dtype="float32")
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glBufferData(GL_ARRAY_BUFFER, arr, GL_STATIC_DRAW)
    return vbo_id, len(positions)


# ============================================================
# 行走物理 + AABB 碰撞
# ============================================================
def _is_solid(solid, W, H, vx, vy, vz):
    """体素是否实心。
    y<0 视为空（可掉进虚空，由上层重生处理）；y>=H 视为空（天空）；
    水平越界视为实心墙（防止走出世界）。"""
    if vy < 0 or vy >= H:
        return False
    if not (0 <= vx < W and 0 <= vz < W):
        return True
    return solid[vx][vz][vy]


def _aabb_solid(pos, solid, W, H):
    """玩家 AABB（半宽 PLAYER_HALF_W，高 PLAYER_HEIGHT_3D，pos=脚位置）是否撞到实心体素"""
    px, py, pz = pos
    half = PLAYER_HALF_W
    x0 = math.floor(px - half); x1 = math.floor(px + half - 1e-5)
    y0 = math.floor(py + 1e-5);  y1 = math.floor(py + PLAYER_HEIGHT_3D - 1e-5)
    z0 = math.floor(pz - half); z1 = math.floor(pz + half - 1e-5)
    for vx in range(x0, x1 + 1):
        for vz in range(z0, z1 + 1):
            for vy in range(y0, y1 + 1):
                if _is_solid(solid, W, H, vx, vy, vz):
                    return True
    return False


def _voxel_overlaps_player(pos, vx, vy, vz):
    """玩家 AABB 是否与某个体素重叠（放置时防止把方块塞进自己身体）"""
    px, py, pz = pos
    half = PLAYER_HALF_W
    return (px - half < vx + 1 and px + half > vx and
            py < vy + 1 and py + PLAYER_HEIGHT_3D > vy and
            pz - half < vz + 1 and pz + half > vz)


def _physics_step(pos, vel, dt, solid, W, H):
    """轴分离移动 + 碰撞解算；返回是否 grounded（着地）"""
    half = PLAYER_HALF_W
    ph = PLAYER_HEIGHT_3D
    grounded = False

    # X 轴
    pos[0] += vel[0] * dt
    if _aabb_solid(pos, solid, W, H):
        if vel[0] > 0:
            pos[0] = math.floor(pos[0] + half) - half - 1e-4
        elif vel[0] < 0:
            pos[0] = math.floor(pos[0] - half) + 1 + half + 1e-4
        vel[0] = 0

    # Z 轴
    pos[2] += vel[2] * dt
    if _aabb_solid(pos, solid, W, H):
        if vel[2] > 0:
            pos[2] = math.floor(pos[2] + half) - half - 1e-4
        elif vel[2] < 0:
            pos[2] = math.floor(pos[2] - half) + 1 + half + 1e-4
        vel[2] = 0

    # Y 轴
    pos[1] += vel[1] * dt
    if _aabb_solid(pos, solid, W, H):
        if vel[1] > 0:          # 跳起撞顶
            pos[1] = math.floor(pos[1] + ph) - ph - 1e-4
        elif vel[1] < 0:        # 下落着地
            pos[1] = math.floor(pos[1]) + 1 + 1e-4
            grounded = True
        vel[1] = 0

    return grounded


def _probe_ground(pos, solid, W, H, dist=0.14):
    """脚下方 dist 内是否有地面。
    单独的稳定 grounded 探测：玩家正好贴在整数边界时 _physics_step 的碰撞会抖动
    （那一帧 AABB 不与地面重叠 → grounded=False），导致疾跑时按 Space 经常跳不起来。
    这里向下探测一小段，只要脚底下有方块就算 grounded。
    """
    px, py, pz = pos
    half = PLAYER_HALF_W
    y0 = math.floor(py - dist + 1e-5)
    y1 = math.floor(py - 1e-5)
    if y1 < y0:
        y0, y1 = y1, y0
    x0 = math.floor(px - half); x1 = math.floor(px + half - 1e-5)
    z0 = math.floor(pz - half); z1 = math.floor(pz + half - 1e-5)
    for vx in range(x0, x1 + 1):
        for vz in range(z0, z1 + 1):
            for vy in range(y0, y1 + 1):
                if _is_solid(solid, W, H, vx, vy, vz):
                    return True
    return False


def _raycast_block(solid, W, H, eye, direction, reach=REACH_3D, step=0.02):
    """从 eye 沿 direction 步进，返回 (命中方块, 放置位置)。
    命中方块 = 射线穿到的第一个实心体素；放置位置 = 命中前的最后一个空体素。
    没命中返回 (None, None)。"""
    px, py, pz = eye
    dx, dy, dz = direction
    L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    dx, dy, dz = dx / L, dy / L, dz / L
    prev = None
    t = 0.0
    while t <= reach:
        vx = int(math.floor(px + dx * t))
        vy = int(math.floor(py + dy * t))
        vz = int(math.floor(pz + dz * t))
        if _is_solid(solid, W, H, vx, vy, vz):
            return (vx, vy, vz), prev
        prev = (vx, vy, vz)
        t += step
    return None, prev


def _rebuild_vbo(solid, tgrid, slot_uv, vbo_id):
    """挖/放后重建整个地形 VBO（世界小，全量重建足够快）；返回新顶点数"""
    import numpy as np
    positions, uvs, colors = _build_face_arrays(solid, tgrid, slot_uv)
    interleaved = []
    for p, uv, c in zip(positions, uvs, colors):
        interleaved.extend([p[0], p[1], p[2], uv[0], uv[1], c[0], c[1], c[2]])
    arr = np.array(interleaved, dtype="float32")
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glBufferData(GL_ARRAY_BUFFER, arr, GL_DYNAMIC_DRAW)
    return len(positions)


def _draw_block_highlight(block):
    """目标方块黑色线框（不管明暗背景都可见）"""
    if block is None:
        return
    bx, by, bz = block
    x0, y0, z0 = float(bx), float(by), float(bz)
    x1, y1, z1 = x0 + 1.0, y0 + 1.0, z0 + 1.0
    glDisable(GL_TEXTURE_2D)
    glColor3f(0, 0, 0)
    glLineWidth(2.0)
    glBegin(GL_LINES)
    for (a, b) in (
        ((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y0, z1)),
        ((x1, y0, z1), (x0, y0, z1)), ((x0, y0, z1), (x0, y0, z0)),
        ((x0, y1, z0), (x1, y1, z0)), ((x1, y1, z0), (x1, y1, z1)),
        ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y1, z0)),
        ((x0, y0, z0), (x0, y1, z0)), ((x1, y0, z0), (x1, y1, z0)),
        ((x1, y0, z1), (x1, y1, z1)), ((x0, y0, z1), (x0, y1, z1)),
    ):
        glVertex3f(*a); glVertex3f(*b)
    glEnd()
    glEnable(GL_TEXTURE_2D)
    glColor3f(1, 1, 1)


# ============================================================
# 主入口
# ============================================================
def run_epilogue(font):
    """进入 3D 胜利场景，ESC 退出。返回后显示模式已切回普通 Surface。"""
    W = WORLD_SIZE
    # 切换到 OpenGL 显示
    pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT),
                            pygame.OPENGL | pygame.DOUBLEBUF)

    # 基本 GL 状态
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glDisable(GL_CULL_FACE)          # 关闭背面剔除，避免缠绕问题
    glDisable(GL_BLEND)              # 地形不使用混合，避免任何半透明
    glAlphaFunc(GL_GREATER, 0.5)
    glClearColor(*_sky_gl(C.get_sky_color(5.0)), 1.0)

    # 投影
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = C.WINDOW_WIDTH / C.WINDOW_HEIGHT
    _perspective(70.0, aspect, 0.1, 300.0)
    glMatrixMode(GL_MODELVIEW)

    # 资源
    atlas_surf, slot_uv = _build_atlas()
    atlas_tex = _surface_to_texture(atlas_surf, flip=True, opaque=True)
    solid, tgrid, height = _build_terrain()
    positions, uvs, colors = _build_face_arrays(solid, tgrid, slot_uv)
    vbo_id, vert_count = _upload_vbo(positions, uvs, colors)

    # King Slime billboard 纹理（gif 第一帧）
    king_tex = None
    king_size = (0, 0)
    try:
        from assets import king_slime_frames
        if king_slime_frames:
            kf = king_slime_frames[0]
            king_tex = _surface_to_texture(kf, flip=True)
            king_size = kf.get_size()
    except Exception:
        king_tex = None

    # MC 风方块史莱姆（裁展开图一个身体面贴六面）
    import os
    slime_tex = _load_slime_cube_texture(os.path.join("3dres", "slime.png"))

    # 起始玩家位置：在世界中央偏东 6 格的地面上出生，看向中心的史莱姆王
    spawn_ix = int(W * 0.5 + 6)
    spawn_iz = int(W * 0.5)
    spawn_ground = height[spawn_ix][spawn_iz] + 1   # 脚踩在顶块上方
    player_pos = [float(spawn_ix) + 0.5, float(spawn_ground), float(spawn_iz) + 0.5]
    spawn_pos = list(player_pos)
    player_vel = [0.0, 0.0, 0.0]
    grounded = False
    cam_yaw = math.atan2(W * 0.5 - player_pos[0], W * 0.5 - player_pos[2])
    cam_pitch = -0.08

    # 当前选中的可放置方块（数字键 1-6 切换）
    sel_idx = 0
    # 暂停界面 QUIT 按钮区域（屏幕中央偏下）
    quit_rect = pygame.Rect(0, 0, 160, 44)
    quit_rect.centerx = int(C.WINDOW_WIDTH * 0.5)
    quit_rect.y = int(C.WINDOW_HEIGHT * 0.5 + 30)

    # ---- 背包 + 手持物品 ----
    inv_counts = [16, 16, 16, 16, 16, 16]   # 6 种可放置方块各给 16 个起步
    # sel_idx: 0=稿子, 1=剑, 2-7=方块
    swing_timer = 0.0                        # 挥动动画剩余秒数
    # 热栏小图标（48px）+ 手持大图标（96px）
    tool_hotbar = [_load_icon_surface(f, scale=3) for f in TOOL_ICON_FILES]
    held_tool_tex = []
    for f in TOOL_ICON_FILES:
        s = _load_icon_surface(f, scale=6)
        held_tool_tex.append(_surface_to_texture(s, flip=False) if s else None)
    held_block_tex = []
    for f in BLOCK_ICON_FILES:
        s = _load_icon_surface(f, scale=6)
        held_block_tex.append(_surface_to_texture(s, flip=False) if s else None)
    hotbar_surf = _build_hotbar_surface(font, inv_counts, sel_idx, tool_hotbar)
    hotbar_tex = _surface_to_texture(hotbar_surf, flip=False)
    hotbar_size = hotbar_surf.get_size()

    def _refresh_hotbar():
        nonlocal hotbar_tex, hotbar_size
        try:
            glDeleteTextures([hotbar_tex])
        except Exception:
            pass
        ns = _build_hotbar_surface(font, inv_counts, sel_idx, tool_hotbar)
        hotbar_tex = _surface_to_texture(ns, flip=False)
        hotbar_size = ns.get_size()

    # ---- 史莱姆王攻击测试 ----
    SLIME_SIZE = 2.0
    king_ground_y = height[W // 2][W // 2]
    king_center = (W * 0.5, king_ground_y + 1 + SLIME_SIZE * 0.5, W * 0.5)
    king_max_hp = 100
    king_hp = 100
    king_alive = True
    king_hurt = 0.0       # 受击闪红计时
    king_respawn = 0.0    # 死亡后复活倒计时
    king_parts = []       # 死亡粒子

    # 眼睛/朝向初值（供事件处理命中判定，循环里每帧覆盖）
    eye = (player_pos[0], player_pos[1] + EYE_HEIGHT, player_pos[2])
    look_dir = (-math.sin(cam_yaw) * math.cos(cam_pitch),
                -math.sin(cam_pitch),
                -math.cos(cam_yaw) * math.cos(cam_pitch))
    walk_phase = 0.0
    moving = False

    # HUD 文字纹理
    hud_surf = font.render(
        "3D - WASD | SPACE jump | LMB mine | RMB place | 1-2 tool / 3-8 block | SHIFT/WW sprint | ESC pause",
        True, (255, 255, 255))
    hud_tex = _surface_to_texture(hud_surf, flip=False)
    pause_surf = font.render(
        "PAUSED  -  ESC / click resume   (mouse released, switch IME now)",
        True, (255, 230, 80))
    pause_tex = _surface_to_texture(pause_surf, flip=False)
    quit_surf = font.render("QUIT", True, (255, 255, 255))
    quit_tex = _surface_to_texture(quit_surf, flip=False)

    # 鼠标锁定
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    pygame.event.get()  # 清空旧事件

    clock = pygame.time.Clock()
    running = True
    paused = False
    target_block = None     # 准星命中的方块（左键挖）
    place_block = None      # 命中方块前的空格（右键放）
    last_w_tap = 0          # 上次按 W 的时间（双击 W 触发疾跑）
    sprint_toggle = False   # 双击 W 后保持疾跑，直到松开 W
    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    paused = not paused
                    if paused:
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                    else:
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                        pygame.event.get()  # 清空旧事件，避免累积位移
                elif event.key == pygame.K_q and paused:
                    running = False
                elif pygame.K_1 <= event.key <= pygame.K_8 and not paused:
                    sel_idx = event.key - pygame.K_1
                    _refresh_hotbar()
                elif event.key == pygame.K_w and not paused:
                    # 双击 W（300ms 内）触发疾跑
                    now = pygame.time.get_ticks()
                    if now - last_w_tap < 300:
                        sprint_toggle = True
                    last_w_tap = now
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_w:
                    sprint_toggle = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if paused:
                    if quit_rect.collidepoint(event.pos):
                        running = False
                    else:
                        # 点击别处恢复
                        paused = False
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                        pygame.event.get()
                else:
                    # 游戏中：左键攻击/挖 / 右键放
                    if event.button == 1:
                        swing_timer = SWING_DURATION
                        hit_king = False
                        # 拿剑（槽 1）且瞄准史莱姆王 → 攻击
                        if sel_idx == 1 and king_alive:
                            kx = king_center[0] - eye[0]
                            ky_ = king_center[1] - eye[1]
                            kz = king_center[2] - eye[2]
                            kdist = math.sqrt(kx * kx + ky_ * ky_ + kz * kz)
                            if kdist < 7.5:
                                cosang = (look_dir[0] * kx + look_dir[1] * ky_ + look_dir[2] * kz) / kdist
                                if cosang > 0.93:
                                    king_hp -= 25
                                    king_hurt = 0.18
                                    hit_king = True
                                    try:
                                        from assets import play_sound
                                        play_sound("npc_hit", 0.5)
                                    except Exception:
                                        pass
                                    if king_hp <= 0:
                                        king_hp = 0
                                        king_alive = False
                                        king_respawn = 5.0
                                        _spawn_king_particles(king_parts, king_center)
                                        try:
                                            from assets import play_sound
                                            play_sound("npc_killed", 0.6)
                                        except Exception:
                                            pass
                        # 没砍到王就尝试挖方块
                        if not hit_king and target_block is not None:
                            hx, hy, hz = target_block
                            if 0 <= hx < W and 0 <= hz < W and 0 <= hy < MAX_H:
                                mined = tgrid[hx][hz][hy]
                                solid[hx][hz][hy] = False
                                tgrid[hx][hz][hy] = 0
                                vert_count = _rebuild_vbo(solid, tgrid, slot_uv, vbo_id)
                                if mined in PLACEABLE_BLOCKS:
                                    inv_counts[PLACEABLE_BLOCKS.index(mined)] += 1
                                    _refresh_hotbar()
                    elif event.button == 3 and target_block is not None and place_block is not None:
                        # 必须瞄准实心方块才能放（杜绝悬空放置）
                        if sel_idx >= BLOCK_SLOT_BASE:
                            bi = sel_idx - BLOCK_SLOT_BASE
                            if inv_counts[bi] > 0:
                                px_, py_, pz_ = place_block
                                if (0 <= px_ < W and 0 <= pz_ < W and 0 <= py_ < MAX_H
                                        and not solid[px_][pz_][py_]):
                                    if not _voxel_overlaps_player(player_pos, px_, py_, pz_):
                                        solid[px_][pz_][py_] = True
                                        tgrid[px_][pz_][py_] = PLACEABLE_BLOCKS[bi]
                                        vert_count = _rebuild_vbo(solid, tgrid, slot_uv, vbo_id)
                                        inv_counts[bi] -= 1
                                        _refresh_hotbar()
                                        swing_timer = SWING_DURATION

        if not paused:
            if swing_timer > 0:
                swing_timer = max(0.0, swing_timer - dt)
            # 鼠标视角
            dx, dy = pygame.mouse.get_rel()
            cam_yaw -= dx * LOOK_SENS * 0.01
            cam_pitch += dy * LOOK_SENS * 0.01
            cam_pitch = max(-1.4, min(1.4, cam_pitch))

            # 水平前向/右向（仅由 yaw 决定，pitch 不影响行走方向）
            fwd = (math.sin(cam_yaw), 0.0, math.cos(cam_yaw))
            right = (math.cos(cam_yaw), 0.0, -math.sin(cam_yaw))

            keys = pygame.key.get_pressed()
            ix = iz = 0.0
            if keys[pygame.K_w]:
                ix -= fwd[0]; iz -= fwd[2]
            if keys[pygame.K_s]:
                ix += fwd[0]; iz += fwd[2]
            if keys[pygame.K_d]:
                ix += right[0]; iz += right[2]
            if keys[pygame.K_a]:
                ix -= right[0]; iz -= right[2]
            hl = math.sqrt(ix * ix + iz * iz)
            if hl > 1.0:
                ix /= hl; iz /= hl
            # 疾跑：按住 Shift，或双击 W 后保持（松开 W 取消）
            sprinting = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or sprint_toggle
            speed = WALK_SPEED * (1.8 if sprinting else 1.0)
            player_vel[0] = ix * speed
            player_vel[2] = iz * speed

            # 跳跃（用上一帧的 grounded 判定）
            if keys[pygame.K_SPACE] and grounded:
                player_vel[1] = JUMP_SPEED_3D
                grounded = False

            # 重力
            player_vel[1] -= GRAVITY_3D * dt
            if player_vel[1] < -55.0:
                player_vel[1] = -55.0

            # 积分 + 碰撞
            landed = _physics_step(player_pos, player_vel, dt, solid, W, MAX_H)
            # 稳定的 grounded 判定（贴边时不抖动），让疾跑中也能可靠起跳
            grounded = landed or _probe_ground(player_pos, solid, W, MAX_H)

            # 掉进虚空则回到出生点
            if player_pos[1] < -8:
                player_pos[:] = list(spawn_pos)
                player_vel[:] = [0.0, 0.0, 0.0]
                grounded = False

            # 准星射线：从眼睛朝看向方向打出，找命中的方块 + 放置空格
            eye = (player_pos[0], player_pos[1] + EYE_HEIGHT, player_pos[2])
            look_dir = (-math.sin(cam_yaw) * math.cos(cam_pitch),
                        -math.sin(cam_pitch),
                        -math.cos(cam_yaw) * math.cos(cam_pitch))
            target_block, place_block = _raycast_block(solid, W, MAX_H, eye, look_dir)

            # 走路摆动相位
            if grounded and (abs(player_vel[0]) + abs(player_vel[2])) > 0.5:
                walk_phase += dt * 10.0
                moving = True
            else:
                moving = False

            # 史莱姆王状态更新
            if king_hurt > 0:
                king_hurt = max(0.0, king_hurt - dt)
            if not king_alive:
                king_respawn -= dt
                for p in king_parts:
                    p['vy'] -= 18.0 * dt
                    p['x'] += p['vx'] * dt
                    p['y'] += p['vy'] * dt
                    p['z'] += p['vz'] * dt
                    p['life'] -= dt
                king_parts = [p for p in king_parts if p['life'] > 0]
                if king_respawn <= 0:
                    king_alive = True
                    king_hp = king_max_hp
                    king_parts = []
        else:
            pygame.mouse.get_rel()  # 暂停时仍消费位移，避免恢复瞬间跳变
            target_block = None
            place_block = None

        # 相机眼睛位置 = 玩家脚位置 + 眼高
        cam_pos = (player_pos[0], player_pos[1] + EYE_HEIGHT, player_pos[2])

        # ===== 渲染 =====
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        _look_at_yaw_pitch(cam_pos, cam_yaw, cam_pitch)

        # 地形 VBO（不透明，关闭 alpha-test 避免树叶/草地纹理软边被丢弃）
        glDisable(GL_ALPHA_TEST)
        glBindTexture(GL_TEXTURE_2D, atlas_tex)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
        stride = 8 * 4
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        glVertexPointer(3, GL_FLOAT, stride, ctypes.c_void_p(0))
        glTexCoordPointer(2, GL_FLOAT, stride, ctypes.c_void_p(3 * 4))
        glColorPointer(3, GL_FLOAT, stride, ctypes.c_void_p(5 * 4))
        glDrawArrays(GL_TRIANGLES, 0, vert_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)

        # 准星命中方块的线框高亮
        if not paused:
            _draw_block_highlight(target_block)

        # MC 风方块史莱姆（六面同贴图的立方体）+ 血条
        if king_alive and slime_tex is not None:
            tint = (1.0, 0.45, 0.45) if king_hurt > 0 else (1.0, 1.0, 1.0)
            _draw_textured_cube(slime_tex, king_center, SLIME_SIZE, tint)
            if king_hp < king_max_hp:
                bar_pos = (king_center[0], king_center[1] + SLIME_SIZE * 0.5 + 0.4, king_center[2])
                _draw_billboard_hp_bar(bar_pos, cam_pos, king_hp / king_max_hp, 2.6)
        if king_parts:
            _draw_king_particles(king_parts, cam_pos)

        # ---- 手持物品（世界空间 viewmodel：透视 + 走路摆动 + 挥动）----
        if sel_idx == 0:
            held_tex, is_hand = held_tool_tex[0], False
        elif sel_idx == 1:
            held_tex, is_hand = held_tool_tex[1], False
        else:
            bi = sel_idx - BLOCK_SLOT_BASE
            if inv_counts[bi] > 0 and held_block_tex[bi]:
                held_tex, is_hand = held_block_tex[bi], False
            else:
                held_tex, is_hand = None, True
        swing_progress = 1.0 - swing_timer / SWING_DURATION if swing_timer > 0 else 0.0
        if not paused and (held_tex is not None or is_hand):
            _draw_viewmodel(held_tex, is_hand, swing_progress, walk_phase, moving)

        # ---- HUD（正交投影）----
        _draw_hud(hud_tex, hud_surf.get_size(),
                  hotbar_tex, hotbar_size,
                  pause_tex if paused else None, pause_surf.get_size(),
                  quit_rect if paused else None, quit_tex, quit_surf.get_size())

        pygame.display.flip()

    # 清理
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    try:
        held_all = [t for t in held_tool_tex + held_block_tex if t is not None]
        texs = [atlas_tex, hud_tex, pause_tex, quit_tex, hotbar_tex]
        if slime_tex is not None:
            texs.append(slime_tex)
        glDeleteTextures(texs + ([king_tex] if king_tex else []) + held_all)
        glDeleteBuffers([vbo_id])
    except Exception:
        pass
    # 切回普通 Surface 模式（供菜单使用）
    pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT))
    return


# ============================================================
# GL 辅助
# ============================================================
def _perspective(fovy, aspect, near, far):
    """复制 gluPerspective 行为（某些环境没 GLU）"""
    f = 1.0 / math.tan(math.radians(fovy) / 2.0)
    m = (f / aspect, 0, 0, 0,
         0, f, 0, 0,
         0, 0, (far + near) / (near - far), -1,
         0, 0, (2 * far * near) / (near - far), 0)
    glMultMatrixf(m)


def _look_at_yaw_pitch(eye, yaw, pitch):
    """手动 view 变换：先平移再旋转（等价于相机绕 yaw/pitch）"""
    glRotatef(math.degrees(pitch), 1, 0, 0)
    glRotatef(-math.degrees(yaw), 0, 1, 0)
    glTranslatef(-eye[0], -eye[1], -eye[2])


def _sky_gl(color):
    return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)


def _draw_billboard(tex_id, world_pos, cam_pos, cam_yaw, height_world, tex_size):
    """圆柱形公告板：绕 Y 轴朝向相机"""
    glEnable(GL_ALPHA_TEST)      # billboard 需要透明边缘丢弃
    glBindTexture(GL_TEXTURE_2D, tex_id)
    aspect = tex_size[0] / max(1, tex_size[1])
    half_w = height_world * aspect * 0.5
    half_h = height_world * 0.5
    # 水平面朝向相机的方向
    dx = cam_pos[0] - world_pos[0]
    dz = cam_pos[2] - world_pos[2]
    length = math.sqrt(dx * dx + dz * dz) or 1.0
    # billboard 的水平“右”方向
    rx = -dz / length
    rz = dx / length
    cx, cy, cz = world_pos
    p1 = (cx - rx * half_w, cy - half_h, cz - rz * half_w)
    p2 = (cx + rx * half_w, cy - half_h, cz + rz * half_w)
    p3 = (cx + rx * half_w, cy + half_h, cz + rz * half_w)
    p4 = (cx - rx * half_w, cy + half_h, cz - rz * half_w)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex3f(*p1)
    glTexCoord2f(1, 0); glVertex3f(*p2)
    glTexCoord2f(1, 1); glVertex3f(*p3)
    glTexCoord2f(0, 1); glVertex3f(*p4)
    glEnd()
    glDisable(GL_ALPHA_TEST)


def _draw_cuboid(cx, cy, cz, sx, sy, sz, color):
    """轴对齐实色长方体，各面不同亮度制造立体感（用于程序化手）。"""
    x0, x1 = cx - sx * 0.5, cx + sx * 0.5
    y0, y1 = cy - sy * 0.5, cy + sy * 0.5
    z0, z1 = cz - sz * 0.5, cz + sz * 0.5
    faces = [
        ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), 0.75),  # -z
        ((x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), 0.75),  # +z
        ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), 1.00),  # +y top
        ((x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0), 0.55),  # -y bottom
        ((x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0), 0.88),  # +x
        ((x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), 0.88),  # -x
    ]
    glDisable(GL_TEXTURE_2D)
    for f in faces:
        b = f[4]
        glColor3f(color[0] / 255.0 * b, color[1] / 255.0 * b, color[2] / 255.0 * b)
        glBegin(GL_QUADS)
        for v in f[:4]:
            glVertex3f(*v)
        glEnd()
    glEnable(GL_TEXTURE_2D)


def _draw_textured_cube(tex, center, size, tint=(1.0, 1.0, 1.0)):
    """六面同贴图的实心立方体（MC 风方块史莱姆用）。center=几何中心，size=边长。
    复用 FACES 的法线/亮度做简单 shading；UV 按面方向取，保证贴图直立。"""
    cx, cy, cz = center
    glBindTexture(GL_TEXTURE_2D, tex)
    for name, normal, bright, verts in FACES:
        glColor3f(bright * tint[0], bright * tint[1], bright * tint[2])
        glBegin(GL_QUADS)
        for dx, dy, dz in verts:
            nx, ny, nz = normal
            if ny != 0:          # top/bottom：u=x, v=z
                u, v = dx, dz
            elif nx != 0:        # east/west：u=z, v=y
                u, v = dz, dy
            else:                # north/south：u=x, v=y
                u, v = dx, dy
            glTexCoord2f(u, v)
            glVertex3f(cx + (dx - 0.5) * size, cy + (dy - 0.5) * size, cz + (dz - 0.5) * size)
        glEnd()
    glColor3f(1, 1, 1)


def _draw_viewmodel(held_tex, is_hand, swing_progress, bob_phase, moving):
    """世界渲染后以相机空间绘制手持物品（贴片/程序化手），带走路摆动 + 挥动。
    先清深度缓冲保证手持物总在前，且保留透视感（比纯屏幕贴片更接近 MC 第一人称）。"""
    glClear(GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()                       # 相机空间：相机在原点看向 -Z
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_ALPHA_TEST)
    bob_y = math.sin(bob_phase) * 0.022 if moving else 0.0
    bob_x = math.cos(bob_phase * 0.5) * 0.012 if moving else 0.0
    swing = math.sin(swing_progress * math.pi) if swing_progress > 0 else 0.0
    glTranslatef(0.40 + bob_x, -0.36 + bob_y, -0.85)
    if is_hand:
        # 程序化手：肤色长方体（小臂+拳），绕腕部俯仰挥动
        glTranslatef(0.0, -0.18, 0.0)
        glRotatef(-18.0 + swing * 60.0, 1, 0, 0)
        glTranslatef(0.0, 0.18, 0.0)
        _draw_cuboid(0.0, -0.05, 0.02, 0.12, 0.34, 0.12, HAND_COLOR)
    else:
        glTranslatef(0.0, -0.16, 0.0)
        glRotatef(-12.0 + swing * 60.0, 1, 0, 0)
        glTranslatef(0.0, 0.16, 0.0)
        half = 0.20
        glBindTexture(GL_TEXTURE_2D, held_tex)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex3f(-half, half, 0)
        glTexCoord2f(1, 0); glVertex3f(half, half, 0)
        glTexCoord2f(1, 1); glVertex3f(half, -half, 0)
        glTexCoord2f(0, 1); glVertex3f(-half, -half, 0)
        glEnd()
    glDisable(GL_BLEND)
    glColor3f(1, 1, 1)
    glPopMatrix()


def _spawn_king_particles(parts, center, count=22, color=(60, 130, 230)):
    for _ in range(count):
        ang = random.random() * math.pi * 2
        spd = random.random() * 3.5 + 1.5
        parts.append({
            'x': center[0] + (random.random() - 0.5) * 1.6,
            'y': center[1] + (random.random() - 0.5) * 2.2,
            'z': center[2] + (random.random() - 0.5) * 1.6,
            'vx': math.cos(ang) * spd,
            'vy': random.random() * 4.0 + 1.0,
            'vz': math.sin(ang) * spd,
            'life': 0.5 + random.random() * 0.5,
            'size': 0.12 + random.random() * 0.12,
            'color': color,
        })


def _draw_king_particles(parts, cam_pos):
    if not parts:
        return
    glDisable(GL_TEXTURE_2D)
    for p in parts:
        dx = cam_pos[0] - p['x']; dz = cam_pos[2] - p['z']
        L = math.sqrt(dx * dx + dz * dz) or 1.0
        rx, rz = -dz / L, dx / L
        s = p['size']
        c = p['color']
        glColor3f(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
        glBegin(GL_QUADS)
        glVertex3f(p['x'] - rx * s, p['y'] - s, p['z'] - rz * s)
        glVertex3f(p['x'] + rx * s, p['y'] - s, p['z'] + rz * s)
        glVertex3f(p['x'] + rx * s, p['y'] + s, p['z'] + rz * s)
        glVertex3f(p['x'] - rx * s, p['y'] + s, p['z'] - rz * s)
        glEnd()
    glColor3f(1, 1, 1)
    glEnable(GL_TEXTURE_2D)


def _draw_billboard_hp_bar(world_pos, cam_pos, ratio, width_world, height_world=0.16):
    """在 world_pos 处画一个面向相机的血条（暗背景 + 左对齐前景）。"""
    dx = cam_pos[0] - world_pos[0]; dz = cam_pos[2] - world_pos[2]
    L = math.sqrt(dx * dx + dz * dz) or 1.0
    rx, rz = -dz / L, dx / L
    hw = width_world * 0.5
    hh = height_world * 0.5
    cx, cy, cz = world_pos
    glDisable(GL_TEXTURE_2D)
    glColor3f(0.12, 0.12, 0.12)
    glBegin(GL_QUADS)
    glVertex3f(cx - rx * hw, cy - hh, cz - rz * hw)
    glVertex3f(cx + rx * hw, cy - hh, cz + rz * hw)
    glVertex3f(cx + rx * hw, cy + hh, cz + rz * hw)
    glVertex3f(cx - rx * hw, cy + hh, cz - rz * hw)
    glEnd()
    r = max(0.0, min(1.0, ratio))
    fill_hw = hw * r
    off = hw - fill_hw
    cx2 = cx - rx * off; cz2 = cz - rz * off
    glColor3f(1 - r, r, 0.0)
    glBegin(GL_QUADS)
    glVertex3f(cx2 - rx * fill_hw, cy - hh + 0.03, cz2 - rz * fill_hw)
    glVertex3f(cx2 + rx * fill_hw, cy - hh + 0.03, cz2 + rz * fill_hw)
    glVertex3f(cx2 + rx * fill_hw, cy + hh - 0.03, cz2 + rz * fill_hw)
    glVertex3f(cx2 - rx * fill_hw, cy + hh - 0.03, cz2 - rz * fill_hw)
    glEnd()
    glColor3f(1, 1, 1)
    glEnable(GL_TEXTURE_2D)


def _draw_hud(hud_tex, hud_size,
              hotbar_tex, hotbar_size,
              pause_tex=None, pause_size=(0, 0),
              quit_rect=None, quit_tex=None, quit_size=(0, 0)):
    """正交投影：准星 + 顶部文字 + 热栏 + 暂停时画提示和 QUIT。"""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, C.WINDOW_WIDTH, C.WINDOW_HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    # 准星
    glColor3f(1, 1, 1)
    cx, cy = C.WINDOW_WIDTH * 0.5, C.WINDOW_HEIGHT * 0.5
    glBegin(GL_LINES)
    glVertex2f(cx - 8, cy); glVertex2f(cx + 8, cy)
    glVertex2f(cx, cy - 8); glVertex2f(cx, cy + 8)
    glEnd()

    # 文字 / 贴片都带透明背景，必须开 blend
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # 顶部说明文字
    hw, hh = hud_size
    glBindTexture(GL_TEXTURE_2D, hud_tex)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(12, 12)
    glTexCoord2f(1, 0); glVertex2f(12 + hw, 12)
    glTexCoord2f(1, 1); glVertex2f(12 + hw, 12 + hh)
    glTexCoord2f(0, 1); glVertex2f(12, 12 + hh)
    glEnd()

    # 热栏（底部居中）
    bw, bh = hotbar_size
    bx = (C.WINDOW_WIDTH - bw) * 0.5
    by = C.WINDOW_HEIGHT - bh - 14
    glBindTexture(GL_TEXTURE_2D, hotbar_tex)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(bx, by)
    glTexCoord2f(1, 0); glVertex2f(bx + bw, by)
    glTexCoord2f(1, 1); glVertex2f(bx + bw, by + bh)
    glTexCoord2f(0, 1); glVertex2f(bx, by + bh)
    glEnd()

    # 暂停提示 + QUIT 按钮
    if pause_tex is not None:
        pw, ph = pause_size
        bx = (C.WINDOW_WIDTH - pw) * 0.5
        by = (C.WINDOW_HEIGHT - ph) * 0.5
        glBindTexture(GL_TEXTURE_2D, pause_tex)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(bx, by)
        glTexCoord2f(1, 0); glVertex2f(bx + pw, by)
        glTexCoord2f(1, 1); glVertex2f(bx + pw, by + ph)
        glTexCoord2f(0, 1); glVertex2f(bx, by + ph)
        glEnd()

        if quit_rect is not None and quit_tex is not None:
            qw, qh = quit_size
            glDisable(GL_TEXTURE_2D)
            glColor3f(0.25, 0.25, 0.28)
            glBegin(GL_QUADS)
            glVertex2f(quit_rect.x, quit_rect.y)
            glVertex2f(quit_rect.right, quit_rect.y)
            glVertex2f(quit_rect.right, quit_rect.bottom)
            glVertex2f(quit_rect.x, quit_rect.bottom)
            glEnd()
            glColor3f(0.8, 0.8, 0.8)
            glBegin(GL_LINE_LOOP)
            glVertex2f(quit_rect.x, quit_rect.y)
            glVertex2f(quit_rect.right, quit_rect.y)
            glVertex2f(quit_rect.right, quit_rect.bottom)
            glVertex2f(quit_rect.x, quit_rect.bottom)
            glEnd()
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, quit_tex)
            glColor4f(1, 1, 1, 1)
            tx = quit_rect.centerx - qw * 0.5
            ty = quit_rect.centery - qh * 0.5
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(tx, ty)
            glTexCoord2f(1, 0); glVertex2f(tx + qw, ty)
            glTexCoord2f(1, 1); glVertex2f(tx + qw, ty + qh)
            glTexCoord2f(0, 1); glVertex2f(tx, ty + qh)
            glEnd()

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

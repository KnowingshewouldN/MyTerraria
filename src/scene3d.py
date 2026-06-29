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
WORLD_SIZE = 120         # 地面边长（立方体数）
MAX_H = 18               # 最大高度（地下厚度 ~10+，地表 ~5-7）
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
SLOT_COPPER, SLOT_SILVER = 7, 8     # 矿石（深地层散布）
SLOT_CHEST = 9                       # 木屋里的箱子（装饰性方块）
ATLAS_COLS = 4
ATLAS_CELL = 16          # 每个槽 16x16
ATLAS_SIZE = ATLAS_COLS * ATLAS_CELL  # 64

# ---- 挖/放 ----
REACH_3D = 6.0           # 挖/放 reach（方块数）
# 数字键 1-8 选择的可放置方块（前 6 个是普通地形，后 2 个铜/银矿石是"贵重"物品）
PLACEABLE_BLOCKS = [SLOT_DIRT, SLOT_STONE, SLOT_WOOD, SLOT_SAND, SLOT_SNOW, SLOT_GRASS,
                    SLOT_COPPER, SLOT_SILVER]
PLACEABLE_NAMES = ["Dirt", "Stone", "Wood", "Sand", "Snow", "Grass", "Copper", "Silver"]
SLOT_COLORS = {
    SLOT_GRASS: (90, 160, 40), SLOT_DIRT: (139, 90, 43), SLOT_STONE: (128, 128, 128),
    SLOT_WOOD: (181, 137, 72), SLOT_LEAVES: (34, 120, 15), SLOT_SAND: (220, 200, 150),
    SLOT_SNOW: (240, 240, 255),
    SLOT_COPPER: (180, 100, 50), SLOT_SILVER: (210, 210, 220),
    SLOT_CHEST: (140, 90, 50),
}
# 每种方块的挖掘耗时（秒）——参考 2D 的硬度感
TILE_MINE_TIME = {
    SLOT_GRASS: 0.30, SLOT_DIRT: 0.30, SLOT_SAND: 0.30, SLOT_SNOW: 0.30,
    SLOT_WOOD: 0.50, SLOT_LEAVES: 0.20,
    SLOT_STONE: 0.80,
    SLOT_COPPER: 1.10, SLOT_SILVER: 1.30,
    SLOT_CHEST: 0.80,
}
DEFAULT_MINE_TIME = 0.50

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
# 史莱姆实体（3D 场景的方块史莱姆——会跳跃追玩家）
# ============================================================
class Slime3D:
    """单只 3D 史莱姆。一个场景里可以有多只，每只独立 AI / 渲染 / HP / 复活。"""

    def __init__(self, pos, size, ground_top_y, hp=None):
        self.size = size
        # pos 为几何中心；脚踩地时 cy = ground_top_y + size*0.5
        self.pos = [pos[0], ground_top_y + size * 0.5, pos[2]]
        self.spawn_pos = list(self.pos)
        self.spawn_ground_top_y = ground_top_y
        self.vel = [0.0, 0.0, 0.0]
        self.grounded = True
        # 朝向（弧度，绕 Y）：用于渲染旋转 + 起跳水平方向
        self.heading = 0.0
        # 起跳倒计时
        import random as _r
        self.jump_timer = 0.6 + _r.random() * 1.0
        # HP 随大小缩放（0.6→60, 1.0→100, 1.5→150）
        self.max_hp = hp if hp is not None else int(50 + size * 50)
        self.hp = self.max_hp
        self.alive = True
        self.hurt = 0.0       # 受击闪红计时
        self.respawn = 0.0    # 死亡复活倒计时
        self.parts = []       # 死亡粒子

    def update(self, dt, target_pos, height_grid, W):
        """target_pos = 史莱姆追的目标位置（通常为玩家或滞后玩家位置）；
        height_grid = 地表顶 y 网格（height[x][z]），用于落地检测。"""
        import random as _r
        import math as _m

        # 受击计时
        if self.hurt > 0:
            self.hurt = max(0.0, self.hurt - dt)

        if not self.alive:
            # 死亡：粒子更新 + 复活倒计时
            self.respawn -= dt
            for p in self.parts:
                p['vy'] -= 18.0 * dt
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['z'] += p['vz'] * dt
                p['life'] -= dt
            self.parts = [p for p in self.parts if p['life'] > 0]
            if self.respawn <= 0:
                self.alive = True
                self.hp = self.max_hp
                self.parts = []
                # 复活时回到出生点
                self.pos = list(self.spawn_pos)
                self.vel = [0.0, 0.0, 0.0]
                self.grounded = True
                self.heading = 0.0
                self.jump_timer = 1.0
            return

        # 朝向追踪：每帧把 heading 平滑插值向"指向目标"的角度（带滞后感）
        dx_h = target_pos[0] - self.pos[0]
        dz_h = target_pos[2] - self.pos[2]
        if dx_h * dx_h + dz_h * dz_h > 1e-4:
            desired = _m.atan2(dx_h, dz_h)
            diff = (desired - self.heading + _m.pi) % (2 * _m.pi) - _m.pi
            step = SLIME_TURN_SPEED * dt
            if abs(diff) <= step:
                self.heading = desired
            else:
                self.heading += _m.copysign(step, diff)

        # 跳跃 AI：站定时倒计时，到点按 heading 起跳
        if self.grounded:
            self.vel[0] = 0.0
            self.vel[2] = 0.0
            self.jump_timer -= dt
            if self.jump_timer <= 0:
                self.jump_timer = SLIME_JUMP_INTERVAL + _r.random() * SLIME_JUMP_JITTER
                # 小史莱姆更敏捷（跳得快），大史莱姆更慢更重
                size_factor = 1.0 / max(0.6, self.size)
                self.vel[0] = _m.sin(self.heading) * SLIME_HSPEED * size_factor
                self.vel[2] = _m.cos(self.heading) * SLIME_HSPEED * size_factor
                self.vel[1] = SLIME_JUMP_VY
                self.grounded = False
        else:
            self.vel[1] -= SLIME_GRAVITY_3D * dt

        # 位置积分
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.pos[2] += self.vel[2] * dt

        # 落地检测：地表顶 + 半个身高
        sx_i = int(self.pos[0])
        sz_i = int(self.pos[2])
        if 0 <= sx_i < W and 0 <= sz_i < W:
            ground_top = height_grid[sx_i][sz_i] + 1
        else:
            ground_top = 0
        floor_y = ground_top + self.size * 0.5
        if self.pos[1] <= floor_y:
            self.pos[1] = floor_y
            self.vel = [0.0, 0.0, 0.0]
            self.grounded = True

    def damage(self, dmg):
        if not self.alive:
            return False
        self.hp -= dmg
        self.hurt = 0.18
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.respawn = 5.0
            _spawn_king_particles(self.parts, tuple(self.pos))
            return True   # 死亡
        return False

    def draw(self, body_tex, face_tex, cam_pos):
        """渲染：5 面身体贴图 + 南面带眼睛的贴图 + 绕 Y 转 heading + 血条/粒子。"""
        if self.alive and body_tex is not None:
            tint = (1.0, 0.45, 0.45) if self.hurt > 0 else (1.0, 1.0, 1.0)
            _draw_textured_cube(body_tex, tuple(self.pos), self.size, tint,
                                side_tex=face_tex, face_yaw=self.heading)
            if self.hp < self.max_hp:
                bar_pos = (self.pos[0], self.pos[1] + self.size * 0.5 + 0.35, self.pos[2])
                _draw_billboard_hp_bar(bar_pos, cam_pos, self.hp / self.max_hp,
                                       width_world=max(0.8, self.size * 1.2))
        if self.parts:
            _draw_king_particles(self.parts, cam_pos)

    def hit_test(self, eye, look_dir, sword_reach=7.5, cos_threshold=0.93):
        """玩家用剑攻击命中判定：返回 True 表示被击中。
        eye/look_dir 是玩家眼睛位置和单位朝向向量。"""
        if not self.alive:
            return False
        kx = self.pos[0] - eye[0]
        ky_ = self.pos[1] - eye[1]
        kz = self.pos[2] - eye[2]
        kdist = math.sqrt(kx * kx + ky_ * ky_ + kz * kz)
        if kdist > sword_reach or kdist < 1e-4:
            return False
        # 命中半径随大小放宽（小史莱姆更难瞄）
        eff_reach = sword_reach
        cosang = (look_dir[0] * kx + look_dir[1] * ky_ + look_dir[2] * kz) / kdist
        # 小史莱姆阈值更严格（cos 更高），大的更宽松
        thr = cos_threshold - (self.size - 1.0) * 0.04
        return cosang > thr


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
        SLOT_COPPER: "copper.png",
        SLOT_SILVER: "silver.png",
        SLOT_CHEST: "multitiles/chest_wood.png",
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
            # 备用纯色：从 SLOT_COLORS 取，避免索引越界
            color = SLOT_COLORS.get(slot, (128, 128, 128))
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


# 正交投影叠加层用：缓存文本→纹理，避免每帧 glTexImage2D/glDeleteTextures
# 键: (text, color)；值: (tex_id, (w, h))
_text_cache = {}


def _cached_text_texture(font, text, color):
    key = (text, tuple(color))
    ent = _text_cache.get(key)
    if ent is None:
        surf = font.render(text, True, color)
        tex = _surface_to_texture(surf, flip=False)
        ent = (tex, surf.get_size())
        _text_cache[key] = ent
    return ent


def _blit_textured_quad(tex, x, y, w, h):
    """画一个对齐屏幕坐标的贴图四边形（调用方需已启用 TEXTURE_2D + 正交投影）。"""
    glBindTexture(GL_TEXTURE_2D, tex)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x, y)
    glTexCoord2f(1, 0); glVertex2f(x + w, y)
    glTexCoord2f(1, 1); glVertex2f(x + w, y + h)
    glTexCoord2f(0, 1); glVertex2f(x, y + h)
    glEnd()


def _blit_text(font, text, x, y, color=(255, 230, 80)):
    """渲染文本（带纹理缓存）到正交屏幕。返回 (w, h)。"""
    tex, (tw, th) = _cached_text_texture(font, text, color)
    _blit_textured_quad(tex, x, y, tw, th)
    return tw, th


def _draw_drag_icon(inv_drag, held_block_tex, font):
    """拖拽中的物品：方块大图贴鼠标，右下角数量。复用文本缓存避免每帧分配。"""
    if inv_drag is None:
        return
    bi = inv_drag["block_idx"]
    mx, my = pygame.mouse.get_pos()
    tex = held_block_tex[bi] if bi < len(held_block_tex) else None
    cs = 48
    if tex is not None:
        _blit_textured_quad(tex, mx - cs // 2, my - cs // 2, cs, cs)
    cnt_str = str(inv_drag["count"])
    cw, chh = font.size(cnt_str)
    _blit_text(font, cnt_str, mx + cs // 2 - cw - 2, my + cs // 2 - chh - 2, (255, 255, 255))


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

# ---- 背包（E 键打开）----
INV_COLS = 8
INV_ROWS = 4                                       # 8×4 = 32 格 stash
INV_CELL = 44
INV_GAP = 4
INV_PAD = 8
INV_GRID_W = INV_COLS * INV_CELL + (INV_COLS - 1) * INV_GAP + INV_PAD * 2   # 396
INV_GRID_H = INV_ROWS * INV_CELL + (INV_ROWS - 1) * INV_GAP + INV_PAD * 2   # 204
INV_STACK_MAX = 99

# ---- 箱子（右键交互）----
CHEST_COLS = 5
CHEST_ROWS = 3                                     # 5×3 = 15 格
CHEST_W = CHEST_COLS * INV_CELL + (CHEST_COLS - 1) * INV_GAP + INV_PAD * 2
CHEST_H = CHEST_ROWS * INV_CELL + (CHEST_ROWS - 1) * INV_GAP + INV_PAD * 2

# 工具图标（res/images/items/）
TOOL_ICON_FILES = ["copper_pickaxe.png", "sword_copper.png"]
# 方块图标（与 PLACEABLE_BLOCKS 顺序一致）
BLOCK_ICON_FILES = ["dirt.png", "stone.png", "wood.png", "sand.png", "snow.png", "grass.png",
                    "copper.png", "silver.png"]


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


def _load_slime_body_texture(path):
    """从 MC 史莱姆展开图裁出 8×8 身体面（无眼睛），放大并强制不透明，用于立方体顶/底。"""
    try:
        img = pygame.image.load(path).convert_alpha()
        face = pygame.Surface((8, 8), pygame.SRCALPHA)
        face.blit(img, (0, 0), area=pygame.Rect(8, 8, 8, 8))   # 身体面板（无眼睛）
        big = pygame.transform.scale(face, (32, 32))
        return _surface_to_texture(big, flip=True, opaque=True)
    except Exception:
        return None


def _load_slime_face_texture(path):
    """直接加载预制作好的「正面贴图」（用户提供的 3dres/slime_face.png，
    32×32 已含绿色身体 + 黑色眼睛，无透明背景）。用于立方体单个侧面。"""
    try:
        img = pygame.image.load(path).convert_alpha()
        return _surface_to_texture(img, flip=True, opaque=True)
    except Exception:
        return None


# 史莱姆跳跃参数（3D 场景专用——比 2D 慢得多，避免太敏捷）
SLIME_GRAVITY_3D = 18.0      # 下落加速度（比玩家的 28 慢，更"漂浮"）
SLIME_JUMP_VY = 7.5          # 起跳向上速度（约能跳 ~1.5 格高）
SLIME_HSPEED = 4.0           # 跳跃时水平速度（块/秒，2D 是 14，3D 慢得多）
SLIME_JUMP_INTERVAL = 1.0    # 落地到下次起跳的最小间隔（秒）
SLIME_JUMP_JITTER = 0.5      # 间隔随机抖动范围（秒）
# 朝向追踪：通过指数平滑"史莱姆记忆的玩家位置"实现滞后感——
# 玩家移动后，记忆位置慢慢追上来（约 3×SLIME_LAG_TIME 秒完全追上），
# 史莱姆朝向读这个滞后位置而非实时，所以会有"等一下再开始转"的效果
SLIME_LAG_TIME = 0.5         # 滞后时间常数（秒）——越大反应越慢
SLIME_TURN_SPEED = 8.0       # 朝向插值速度（弧度/秒，滞后记忆变化已慢，转得快点没问题）


def _build_hotbar_surface(font, hotbar, sel_idx, tool_surfs, block_surfs):
    """构建 8 格热栏 Surface：稿子/剑 + 6 自由方块槽。
    hotbar: 长度 8 的列表，前 2 项是工具占位（None），后 6 项为 None 或 {"block_idx","count"}。
    block_surfs: 6 个方块的 pygame.Surface（与 PLACEABLE_BLOCKS 顺序一致），用于在槽里画真实图标。"""
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
            # 工具槽：稿子/剑
            ic = tool_surfs[i]
            if ic is not None:
                surf.blit(ic, (cx + (HOTBAR_CELL - ic.get_width()) // 2,
                               cy + (HOTBAR_CELL - ic.get_height()) // 2))
            else:
                col = [(180, 150, 90), (200, 200, 220)][i]
                pygame.draw.rect(surf, col, rect.inflate(-12, -12))
        else:
            # 方块槽：读 hotbar[i]，空槽不画图标；非空画真实图标 + 数量
            stack = hotbar[i]
            if stack is not None:
                bi = stack["block_idx"]
                ic = block_surfs[bi] if 0 <= bi < len(block_surfs) else None
                if ic is not None:
                    surf.blit(ic, (cx + (HOTBAR_CELL - ic.get_width()) // 2,
                                   cy + (HOTBAR_CELL - ic.get_height()) // 2))
                else:
                    col = SLOT_COLORS[PLACEABLE_BLOCKS[bi]]
                    pygame.draw.rect(surf, col, rect.inflate(-8, -8))
                cnt_txt = font.render(str(stack["count"]), True, (255, 255, 255))
                surf.blit(cnt_txt, (cx + HOTBAR_CELL - cnt_txt.get_width() - 4,
                                    cy + HOTBAR_CELL - cnt_txt.get_height() - 2))
        num_txt = font.render(str(i + 1), True, (200, 200, 200))
        surf.blit(num_txt, (cx + 3, cy + 2))
        if i == sel_idx:
            pygame.draw.rect(surf, (255, 255, 255), rect, 2)
        else:
            pygame.draw.rect(surf, (80, 80, 80), rect, 1)
    return surf


def _build_grid_surface(font, grid, cols, rows, w, h,
                        bg_color, border_color, cell_bg, cell_border):
    """通用网格 Surface 构建（背包/箱子共用）。
    bg_color=整体底色；border_color=None 不画外框，否则画 2px 外框；
    cell_bg/cell_border 是每格的底色与描边色。"""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, bg_color, surf.get_rect(), border_radius=6)
    if border_color is not None:
        pygame.draw.rect(surf, border_color, surf.get_rect(), 2, border_radius=6)
    for row in range(rows):
        for col in range(cols):
            cx = INV_PAD + col * (INV_CELL + INV_GAP)
            cy = INV_PAD + row * (INV_CELL + INV_GAP)
            rect = pygame.Rect(cx, cy, INV_CELL, INV_CELL)
            pygame.draw.rect(surf, cell_bg, rect)
            pygame.draw.rect(surf, cell_border, rect, 1)
            idx = row * cols + col
            stack = grid[idx]
            if stack:
                bi = stack["block_idx"]
                col_rgb = SLOT_COLORS[PLACEABLE_BLOCKS[bi]]
                pygame.draw.rect(surf, col_rgb, rect.inflate(-8, -8))
                cnt_txt = font.render(str(stack["count"]), True, (255, 255, 255))
                surf.blit(cnt_txt, (cx + INV_CELL - cnt_txt.get_width() - 4,
                                    cy + INV_CELL - cnt_txt.get_height() - 2))
    return surf


def _build_inventory_surface(font, inv_grid):
    return _build_grid_surface(font, inv_grid, INV_COLS, INV_ROWS, INV_GRID_W, INV_GRID_H,
                               (10, 10, 14, 235), None, (28, 28, 34, 230), (70, 70, 80))


def _build_chest_surface(font, chest_inv):
    return _build_grid_surface(font, chest_inv, CHEST_COLS, CHEST_ROWS, CHEST_W, CHEST_H,
                               (60, 38, 22, 240), (110, 75, 40), (40, 28, 18, 230), (90, 60, 30))


# 箱子 loot 用的 block_idx（PLACEABLE_BLOCKS 里的下标）——名字比魔法数字直观
_BI_COPPER = PLACEABLE_BLOCKS.index(SLOT_COPPER)
_BI_SILVER = PLACEABLE_BLOCKS.index(SLOT_SILVER)
_BI_WOOD = PLACEABLE_BLOCKS.index(SLOT_WOOD)
_BI_STONE = PLACEABLE_BLOCKS.index(SLOT_STONE)
_BI_SAND = PLACEABLE_BLOCKS.index(SLOT_SAND)
_BI_SNOW = PLACEABLE_BLOCKS.index(SLOT_SNOW)


def _make_chest_inventory(cx, cz):
    """根据坐标 seed 生成箱子 loot：固定有铜矿/银矿/木头，可能额外有石头/沙子等。"""
    rng = random.Random((cx * 73856093) ^ (cz * 19349663))
    inv = [None] * (CHEST_COLS * CHEST_ROWS)
    inv[0] = {"block_idx": _BI_COPPER, "count": rng.randint(15, 40)}
    inv[1] = {"block_idx": _BI_SILVER, "count": rng.randint(8, 25)}
    inv[2] = {"block_idx": _BI_WOOD, "count": rng.randint(10, 30)}
    # 随机额外的槽位（建材或更多矿石）
    extra_choices = [
        (_BI_STONE, 20, 50),
        (_BI_SAND, 10, 30),
        (_BI_SNOW, 10, 25),
        (_BI_COPPER, 5, 15),
        (_BI_SILVER, 3, 10),
    ]
    for slot in range(3, CHEST_COLS * CHEST_ROWS):
        if rng.random() < 0.35:
            bi, lo, hi = rng.choice(extra_choices)
            inv[slot] = {"block_idx": bi, "count": rng.randint(lo, hi)}
    return inv


def _inventory_grid_origin():
    """背包网格在屏幕上的左上角坐标（居中，略偏上给底部热栏让位）。"""
    x = (C.WINDOW_WIDTH - INV_GRID_W) // 2
    y = (C.WINDOW_HEIGHT - INV_GRID_H) // 2 - 60
    return x, y


def _hotbar_origin(hotbar_size):
    """底部热栏左上角（与 _draw_hud 内部一致）。"""
    bw, bh = hotbar_size
    return (C.WINDOW_WIDTH - bw) // 2, C.WINDOW_HEIGHT - bh - 14


def _chest_grid_origin():
    """箱子网格左上角（顶部居中）。"""
    x = (C.WINDOW_WIDTH - CHEST_W) // 2
    y = 40
    return x, y


def _chest_inv_origin():
    """箱子打开时玩家背包网格左上角（往下让位给箱子）。"""
    x = (C.WINDOW_WIDTH - INV_GRID_W) // 2
    y = 40 + CHEST_H + 16
    return x, y


def _grid_hit_test(mx, my, origin, w, h, cols, rows, area_name):
    """通用网格命中检测：返回 (area_name, idx) 或 None。"""
    ox, oy = origin
    if not (ox <= mx < ox + w and oy <= my < oy + h):
        return None
    lx = mx - ox - INV_PAD
    ly = my - oy - INV_PAD
    if lx < 0 or ly < 0:
        return None
    col = int(lx) // (INV_CELL + INV_GAP)
    row = int(ly) // (INV_CELL + INV_GAP)
    if not (0 <= col < cols and 0 <= row < rows):
        return None
    cell_lx = col * (INV_CELL + INV_GAP)
    cell_ly = row * (INV_CELL + INV_GAP)
    if not (cell_lx <= lx < cell_lx + INV_CELL and cell_ly <= ly < cell_ly + INV_CELL):
        return None
    return (area_name, int(row * cols + col))


def _slot_at_pos(pos, hotbar_size, inv_origin, chest_origin=None):
    """命中检测：返回 (区域, 索引) 或 None。
    区域："hotbar" 0..7 / "grid" 0..31 / "chest" 0..14（仅当 chest_origin 给出时检测）。"""
    mx, my = pos
    # 热栏
    bx, by = _hotbar_origin(hotbar_size)
    if bx <= mx < bx + hotbar_size[0] and by <= my < by + hotbar_size[1]:
        lx = mx - bx - HOTBAR_PAD
        ly = my - by - HOTBAR_PAD
        col = lx // (HOTBAR_CELL + HOTBAR_GAP) if lx >= 0 else -1
        if 0 <= col < HOTBAR_SLOTS and 0 <= ly < HOTBAR_CELL:
            return ("hotbar", int(col))
    # 背包网格
    g = _grid_hit_test(mx, my, inv_origin, INV_GRID_W, INV_GRID_H, INV_COLS, INV_ROWS, "grid")
    if g is not None:
        return g
    # 箱子网格（仅当提供 chest_origin 时）
    if chest_origin is not None:
        c = _grid_hit_test(mx, my, chest_origin, CHEST_W, CHEST_H, CHEST_COLS, CHEST_ROWS, "chest")
        if c is not None:
            return c
    return None


def _add_block_to_storage(hotbar, inv_grid, block_idx, count):
    """把 count 个方块塞进存储：先叠到热栏同种栈 → 热栏空槽 → 背宾同种栈 → 背宾空槽。
    返回没塞进去的剩余数量（满了才会剩）。"""
    # 1) 热栏同种栈
    for i in range(BLOCK_SLOT_BASE, HOTBAR_SLOTS):
        s = hotbar[i]
        if s and s["block_idx"] == block_idx and s["count"] < INV_STACK_MAX:
            room = INV_STACK_MAX - s["count"]
            move = min(room, count)
            s["count"] += move
            count -= move
            if count == 0:
                return 0
    # 2) 热栏空槽
    for i in range(BLOCK_SLOT_BASE, HOTBAR_SLOTS):
        if hotbar[i] is None:
            move = min(count, INV_STACK_MAX)
            hotbar[i] = {"block_idx": block_idx, "count": move}
            count -= move
            if count == 0:
                return 0
    # 3) 背包同种栈
    for cell in inv_grid:
        if cell and cell["block_idx"] == block_idx and cell["count"] < INV_STACK_MAX:
            room = INV_STACK_MAX - cell["count"]
            move = min(room, count)
            cell["count"] += move
            count -= move
            if count == 0:
                return 0
    # 4) 背包空槽
    for i in range(len(inv_grid)):
        if inv_grid[i] is None:
            move = min(count, INV_STACK_MAX)
            inv_grid[i] = {"block_idx": block_idx, "count": move}
            count -= move
            if count == 0:
                return 0
    return count


def _stash_or_drop(stack, hotbar, inv_grid):
    """把拖拽中的 stack 放回去（取消拖拽时用）。满了就丢弃剩余。"""
    bi = stack["block_idx"]
    leftover = _add_block_to_storage(hotbar, inv_grid, bi, stack["count"])
    stack["count"] = leftover


# ============================================================
# 体素地形
# ============================================================
def _build_terrain():
    """生成体素占用网格 + 每个立方体的图集槽位；返回 (solid, type_grid)"""
    random.seed(7)
    W = WORLD_SIZE
    solid = [[[False] * MAX_H for _ in range(W)] for _ in range(W)]
    tgrid = [[[0] * MAX_H for _ in range(W)] for _ in range(W)]  # 0 = air marker

    # 高度图：基础 + 双正弦丘陵（地表在 y=10 附近，地下 y=0..9 实心）
    BASE_SURFACE = 10
    height = [[0] * W for _ in range(W)]
    for x in range(W):
        for z in range(W):
            h = BASE_SURFACE
            h += int(1.6 * math.sin(x * 0.32) * math.cos(z * 0.27))
            h += int(1.1 * math.sin(x * 0.13 + 1.3))
            # 留出头顶 ~6 格给树冠 / 跳跃，不要顶到 MAX_H
            height[x][z] = max(4, min(MAX_H - 6, h))

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
            # y=0..h 全部填实（保证地下有 ~10 层厚度）
            for y in range(h + 1):
                solid[x][z][y] = True
                if y == h:
                    tgrid[x][z][y] = surface_slot
                elif y >= h - 1:
                    tgrid[x][z][y] = sub_slot
                else:
                    tgrid[x][z][y] = deep_slot

    # 矿脉：在深地层（y=0..h-3）随机散布。铜矿较浅较多，银矿更深更少
    for x in range(W):
        for z in range(W):
            h = height[x][z]
            for y in range(0, h - 2):
                # 铜矿：y <= h-4 概率 4%；银矿：y <= h-6 概率 2%
                if y <= h - 6 and random.random() < 0.020:
                    tgrid[x][z][y] = SLOT_SILVER
                elif y <= h - 4 and random.random() < 0.040:
                    tgrid[x][z][y] = SLOT_COPPER

    # 森林带散布树木（密度按面积放大）
    TREE_COUNT = max(20, W * W // 130)   # 40x40->12, 80x80->49
    for _ in range(TREE_COUNT):
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

    # 散布木屋：在森林带（x < W//3）随机找平坦位置放 1-2 栋；位置不合适就跳过
    HOUSES_TARGET = 2
    houses_placed = 0
    house_attempts = 0
    while houses_placed < HOUSES_TARGET and house_attempts < 30:
        house_attempts += 1
        hx = random.randint(3, W // 3 - 3)
        hz = random.randint(3, W - 4)
        if _place_house(solid, tgrid, height, W, MAX_H, hx, hz):
            houses_placed += 1

    return solid, tgrid, height


def _place_house(solid, tgrid, height, W, MAX_H, cx, cz, rng=None):
    """在 (cx,cz) 处盖一栋 5×5 简易木屋：木墙 + 木顶 + 一面墙开门洞 + 内部箱子。
    返回 True 表示放置成功（地表够平），False 表示位置不合适（已跳过）。"""
    import random as _r
    rng = rng or _r
    HALF = 2   # 5x5：从中心向四周 ±2
    # 地基检查：5x5 范围内地表高度差不超过 1
    base = height[cx][cz]
    for dx in range(-HALF, HALF + 1):
        for dz in range(-HALF, HALF + 1):
            x = cx + dx; z = cz + dz
            if not (0 <= x < W and 0 <= z < W):
                return False
            if abs(height[x][z] - base) > 1:
                return False
    WALL_H = 3   # 墙高 3 块
    if base + WALL_H + 1 >= MAX_H:
        return False

    # 把 5x5 范围整平到 base（移除上方树叶/树干等干扰）
    for dx in range(-HALF, HALF + 1):
        for dz in range(-HALF, HALF + 1):
            x = cx + dx; z = cz + dz
            for y in range(base + 1, MAX_H):
                solid[x][z][y] = False
                tgrid[x][z][y] = 0

    # 四面墙（高 WALL_H）；中间地板已经是地表，不动
    for dx in range(-HALF, HALF + 1):
        for dz in range(-HALF, HALF + 1):
            x = cx + dx; z = cz + dz
            on_edge = (abs(dx) == HALF or abs(dz) == HALF)
            if not on_edge:
                continue   # 内部不填墙
            for wy in range(1, WALL_H + 1):
                y = base + wy
                if 0 <= y < MAX_H:
                    solid[x][z][y] = True
                    tgrid[x][z][y] = SLOT_WOOD

    # 屋顶：5x5 平顶（铺一层 wood）
    roof_y = base + WALL_H + 1
    if roof_y < MAX_H:
        for dx in range(-HALF, HALF + 1):
            for dz in range(-HALF, HALF + 1):
                x = cx + dx; z = cz + dz
                solid[x][z][roof_y] = True
                tgrid[x][z][roof_y] = SLOT_WOOD

    # 门洞：在南墙正中（z = cz+HALF, x = cx）挖掉 y=base+1 和 base+2 两层
    door_x, door_z = cx, cz + HALF
    for dy in (1, 2):
        y = base + dy
        if 0 <= y < MAX_H:
            solid[door_x][door_z][y] = False
            tgrid[door_x][door_z][y] = 0

    # 内部放一个箱子（北墙内侧中央地面上）
    chest_x, chest_z = cx, cz - HALF + 1
    chest_y = base + 1
    if 0 <= chest_y < MAX_H:
        solid[chest_x][chest_z][chest_y] = True
        tgrid[chest_x][chest_z][chest_y] = SLOT_CHEST

    return True


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

    # MC 风方块史莱姆：身体贴图（顶/底 + 3 个侧面）+ 正面贴图（用户提供的 slime_face.png）
    import os
    slime_tex = _load_slime_body_texture(os.path.join("3dres", "slime.png"))
    slime_face_tex = _load_slime_face_texture(os.path.join("3dres", "slime_face.png"))

    # 起始玩家位置：在世界中央偏东 6 格的地面上出生，看向中心的史莱姆王
    spawn_ix = int(W * 0.5 + 6)
    spawn_iz = int(W * 0.5)
    spawn_ground = height[spawn_ix][spawn_iz] + 1   # 脚踩在顶块上方
    player_pos = [float(spawn_ix) + 0.5, float(spawn_ground), float(spawn_iz) + 0.5]
    spawn_pos = list(player_pos)
    # 史莱姆"记得的玩家位置"——指数平滑追当前 player_pos，制造滞后感
    player_pos_lagged = list(player_pos)
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
    # 热栏 8 格：0/1 = 工具占位（None），2-7 = 自由方块槽（任意方块可放任意槽）
    # 每个方块槽为 None 或 {"block_idx": 0..5, "count": int}
    hotbar = [
        None, None,
        {"block_idx": 0, "count": 16},   # dirt
        {"block_idx": 1, "count": 16},   # stone
        {"block_idx": 2, "count": 16},   # wood
        {"block_idx": 3, "count": 16},   # sand
        {"block_idx": 4, "count": 16},   # snow
        {"block_idx": 5, "count": 16},   # grass
    ]
    # 32 格 stash（背包），每格 None 或 {"block_idx": 0..7, "count": int}
    inv_grid = [None] * (INV_COLS * INV_ROWS)
    inventory_open = False                  # E 键开关
    inv_drag = None                         # 拖拽中的物品，None 或 {"block_idx","count"}
    # 箱子（右键 SLOT_CHEST 方块打开）：每个箱子有独立库存，存在 chest_invs 字典里
    chest_open = False
    chest_pos = None                        # 当前打开的箱子方块坐标 (x,y,z)
    chest_invs = {}                         # {(x,y,z): [15 个 stack 或 None]}
    # sel_idx: 0=稿子, 1=剑, 2-7=方块
    swing_timer = 0.0                        # 挥动动画剩余秒数
    # 热栏小图标（48px）+ 手持大图标（96px）
    tool_hotbar = [_load_icon_surface(f, scale=3) for f in TOOL_ICON_FILES]
    block_hotbar = [_load_icon_surface(f, scale=3) for f in BLOCK_ICON_FILES]
    held_tool_tex = []
    for f in TOOL_ICON_FILES:
        s = _load_icon_surface(f, scale=6)
        held_tool_tex.append(_surface_to_texture(s, flip=False) if s else None)
    held_block_tex = []
    for f in BLOCK_ICON_FILES:
        s = _load_icon_surface(f, scale=6)
        held_block_tex.append(_surface_to_texture(s, flip=False) if s else None)
    hotbar_surf = _build_hotbar_surface(font, hotbar, sel_idx, tool_hotbar, block_hotbar)
    hotbar_tex = _surface_to_texture(hotbar_surf, flip=False)
    hotbar_size = hotbar_surf.get_size()
    inv_surf = _build_inventory_surface(font, inv_grid)
    inv_tex = _surface_to_texture(inv_surf, flip=False)
    inv_size = inv_surf.get_size()
    # 箱子 Surface（按当前打开的 chest_invs[chest_pos] 构建；未开箱子时占位空网格）
    chest_tex = _surface_to_texture(_build_chest_surface(font, [None] * (CHEST_COLS * CHEST_ROWS)),
                                    flip=False)
    chest_size = (CHEST_W, CHEST_H)

    def _refresh_hotbar():
        nonlocal hotbar_tex, hotbar_size
        try:
            glDeleteTextures([hotbar_tex])
        except Exception:
            pass
        ns = _build_hotbar_surface(font, hotbar, sel_idx, tool_hotbar, block_hotbar)
        hotbar_tex = _surface_to_texture(ns, flip=False)
        hotbar_size = ns.get_size()

    def _refresh_chest():
        nonlocal chest_tex, chest_size
        try:
            glDeleteTextures([chest_tex])
        except Exception:
            pass
        contents = chest_invs.get(chest_pos) if chest_pos is not None else None
        if contents is None:
            contents = [None] * (CHEST_COLS * CHEST_ROWS)
        ns = _build_chest_surface(font, contents)
        chest_tex = _surface_to_texture(ns, flip=False)
        chest_size = ns.get_size()

    def _refresh_inventory():
        nonlocal inv_tex, inv_size
        try:
            glDeleteTextures([inv_tex])
        except Exception:
            pass
        ns = _build_inventory_surface(font, inv_grid)
        inv_tex = _surface_to_texture(ns, flip=False)
        inv_size = ns.get_size()

    # ---- 史莱姆群落（多只，大小各异，散布地图）----
    # 每只: (相对坐标 rx,rz, size, hp) —— rx/rz 是 0..1 比例（相对 W），size=方块边长
    SLIME_SPAWNS = [
        (0.50, 0.50, 1.5, 150),    # 中央大史莱姆（Boss 风）
        (0.32, 0.40, 0.8, 80),
        (0.68, 0.42, 0.8, 80),
        (0.42, 0.68, 1.0, 100),
        (0.62, 0.66, 0.6, 60),     # 小但快
    ]
    slimes = []
    for rx, rz, sz, hp in SLIME_SPAWNS:
        ix = int(W * rx); iz = int(W * rz)
        if 0 <= ix < W and 0 <= iz < W:
            ground_top = height[ix][iz] + 1
            slimes.append(Slime3D((float(ix) + 0.5, 0, float(iz) + 0.5),
                                  size=sz, ground_top_y=ground_top, hp=hp))

    # 眼睛/朝向初值（供事件处理命中判定，循环里每帧覆盖）
    eye = (player_pos[0], player_pos[1] + EYE_HEIGHT, player_pos[2])
    look_dir = (-math.sin(cam_yaw) * math.cos(cam_pitch),
                -math.sin(cam_pitch),
                -math.cos(cam_yaw) * math.cos(cam_pitch))
    walk_phase = 0.0
    moving = False

    # HUD 文字纹理
    hud_surf = font.render(
        "3D - WASD | SPACE jump | LMB mine | RMB place / open chest | E inventory | 1-2 tool / 3-8 block | SHIFT sprint | ESC pause",
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
    mining_target = None    # 正在持续挖的方块 (x,y,z)；None 表示未挖
    mining_progress = 0.0   # 0..1 当前进度
    last_w_tap = 0          # 上次按 W 的时间（双击 W 触发疾跑）
    sprint_toggle = False   # 双击 W 后保持疾跑，直到松开 W
    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if chest_open:
                        # ESC 先关箱子（不影响 paused）
                        chest_open = False
                        chest_pos = None
                        inv_drag = None
                        _refresh_chest()
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                        pygame.event.get()
                    elif inventory_open:
                        inventory_open = False
                        inv_drag = None
                        _refresh_inventory()
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                        pygame.event.get()
                    else:
                        paused = not paused
                        if paused:
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        else:
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            pygame.event.get()  # 清空旧事件，避免累积位移
                elif event.key == pygame.K_e and not paused:
                    if chest_open:
                        # E 在箱子打开时切换为"看背包"（关掉箱子继续显示背包）
                        chest_open = False
                        chest_pos = None
                        inv_drag = None
                        _refresh_chest()
                        inventory_open = True
                        _refresh_inventory()
                    else:
                        # 切换背包：开 → 释放鼠标；关 → 锁回鼠标
                        inventory_open = not inventory_open
                        inv_drag = None
                        _refresh_inventory()
                        if inventory_open:
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        else:
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            pygame.event.get()
                elif event.key == pygame.K_q and paused:
                    running = False
                elif (pygame.K_1 <= event.key <= pygame.K_8
                      and not paused and not inventory_open and not chest_open):
                    sel_idx = event.key - pygame.K_1
                    _refresh_hotbar()
                elif event.key == pygame.K_w and not paused and not inventory_open and not chest_open:
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
                elif (inventory_open or chest_open) and event.button == 1:
                    # ---- 背包/箱子拖拽（统一处理） ----
                    # 根据当前模式传给 _slot_at_pos 不同的 origin 和可选 chest 区域
                    if chest_open:
                        inv_origin_v = _chest_inv_origin()
                        slot = _slot_at_pos(event.pos, hotbar_size, inv_origin_v,
                                            chest_origin=_chest_grid_origin())
                    else:
                        inv_origin_v = _inventory_grid_origin()
                        slot = _slot_at_pos(event.pos, hotbar_size, inv_origin_v)
                    # 取出当前箱子库存引用（仅 chest_open 时非 None）
                    chest_list = chest_invs.get(chest_pos) if chest_open else None

                    def _slot_get(a, i):
                        if a == "hotbar": return hotbar[i]
                        if a == "grid":   return inv_grid[i]
                        if a == "chest" and chest_list is not None: return chest_list[i]
                        return None

                    def _slot_set(a, i, v):
                        if a == "hotbar":   hotbar[i] = v
                        elif a == "grid":   inv_grid[i] = v
                        elif a == "chest" and chest_list is not None: chest_list[i] = v

                    def _slot_refresh(a):
                        if a == "hotbar": _refresh_hotbar()
                        elif a == "grid": _refresh_inventory()
                        elif a == "chest": _refresh_chest()

                    if inv_drag is None:
                        # 拾起：从点击的槽位抓出整堆（工具槽 idx 0/1 不可拖）
                        if slot is not None:
                            area, idx = slot
                            if area == "hotbar" and idx < BLOCK_SLOT_BASE:
                                pass    # 工具槽：忽略
                            else:
                                cur = _slot_get(area, idx)
                                if cur is not None:
                                    inv_drag = dict(cur)
                                    _slot_set(area, idx, None)
                                    _slot_refresh(area)
                    else:
                        # 放下：合并 / 交换 / 进空槽
                        if slot is None or (slot[0] == "hotbar" and slot[1] < BLOCK_SLOT_BASE):
                            # 没点中槽位 / 点中工具槽：取消拖拽，物品归位
                            _stash_or_drop(inv_drag, hotbar, inv_grid)
                            inv_drag = None
                            _refresh_hotbar(); _refresh_inventory()
                        else:
                            area, idx = slot
                            target = _slot_get(area, idx)
                            if target is None:
                                _slot_set(area, idx, dict(inv_drag))
                                inv_drag = None
                                _slot_refresh(area)
                            elif target["block_idx"] == inv_drag["block_idx"]:
                                total = target["count"] + inv_drag["count"]
                                capped = min(total, INV_STACK_MAX)
                                target["count"] = capped       # 原地改（dict 是引用）
                                leftover = total - capped
                                if leftover > 0:
                                    _stash_or_drop({"block_idx": target["block_idx"],
                                                    "count": leftover}, hotbar, inv_grid)
                                    _refresh_hotbar(); _refresh_inventory()
                                inv_drag = None
                                _slot_refresh(area)
                            else:
                                # 不同种 → 交换（用户继续拿着原来那堆）
                                old = dict(target)
                                _slot_set(area, idx, dict(inv_drag))
                                inv_drag = old
                                _slot_refresh(area)
                else:
                    # 游戏中：左键攻击/挖 / 右键放
                    if event.button == 1:
                        swing_timer = SWING_DURATION
                        hit_slime = False
                        # 拿剑（槽 1）→ 遍历所有史莱姆，找命中的那只攻击
                        if sel_idx == 1:
                            for s in slimes:
                                if s.hit_test(eye, look_dir):
                                    died = s.damage(25)
                                    hit_slime = True
                                    try:
                                        from assets import play_sound
                                        play_sound("npc_hit", 0.5)
                                    except Exception:
                                        pass
                                    if died:
                                        try:
                                            from assets import play_sound
                                            play_sound("npc_killed", 0.6)
                                        except Exception:
                                            pass
                                    break   # 一击只砍一只
                        # 没砍到史莱姆就尝试挖方块——现在改成"开始挖"，实际破坏在主循环累计进度
                        if not hit_slime and target_block is not None:
                            mining_target = target_block
                            mining_progress = 0.0
                            swing_timer = SWING_DURATION
                    elif event.button == 3 and target_block is not None:
                        # 右键：先判断是否点中箱子（开箱子界面）；否则尝试放方块
                        bx_, by_, bz_ = target_block
                        if (0 <= bx_ < W and 0 <= bz_ < W and 0 <= by_ < MAX_H
                                and solid[bx_][bz_][by_]
                                and tgrid[bx_][bz_][by_] == SLOT_CHEST):
                            # 开箱子：lazy-init 该坐标的库存（每个箱子固定 loot，按位置 seed）
                            chest_pos = (bx_, by_, bz_)
                            if chest_pos not in chest_invs:
                                chest_invs[chest_pos] = _make_chest_inventory(bx_, bz_)
                            chest_open = True
                            inv_drag = None
                            _refresh_chest()
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        elif place_block is not None and sel_idx >= BLOCK_SLOT_BASE:
                            # 放方块（必须瞄准实心方块前的空格，杜绝悬空）
                            stack = hotbar[sel_idx]
                            if stack is not None and stack["count"] > 0:
                                bi = stack["block_idx"]
                                px_, py_, pz_ = place_block
                                if (0 <= px_ < W and 0 <= pz_ < W and 0 <= py_ < MAX_H
                                        and not solid[px_][pz_][py_]):
                                    if not _voxel_overlaps_player(player_pos, px_, py_, pz_):
                                        solid[px_][pz_][py_] = True
                                        tgrid[px_][pz_][py_] = PLACEABLE_BLOCKS[bi]
                                        vert_count = _rebuild_vbo(solid, tgrid, slot_uv, vbo_id)
                                        stack["count"] -= 1
                                        if stack["count"] == 0:
                                            hotbar[sel_idx] = None
                                        _refresh_hotbar()
                                        swing_timer = SWING_DURATION

        if not paused and not inventory_open and not chest_open:
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

            # 史莱姆"记忆中的玩家位置"——指数平滑，制造转向滞后感
            lag_alpha = min(1.0, dt / SLIME_LAG_TIME)
            player_pos_lagged[0] += (player_pos[0] - player_pos_lagged[0]) * lag_alpha
            player_pos_lagged[2] += (player_pos[2] - player_pos_lagged[2]) * lag_alpha

            # ---- 挖掘进度更新 ----
            # LMB 持续按住、目标没变、准星还指在同一格 → 累计进度；进度满才破坏
            lmb_held = pygame.mouse.get_pressed()[0]
            # 连续挖掘：如果 LMB 还按着但 mining_target 是 None（刚破坏完上一格），
            # 就从当前准星指向的方块续上，不用松开重按
            if lmb_held and mining_target is None and target_block is not None:
                mining_target = target_block
                mining_progress = 0.0
            if mining_target is not None:
                # 检查中断条件：松开 LMB、准星没指方块、或指到别的格子
                if (not lmb_held or target_block is None
                        or tuple(target_block) != tuple(mining_target)):
                    mining_target = None
                    mining_progress = 0.0
                else:
                    hx, hy, hz = target_block
                    if 0 <= hx < W and 0 <= hz < W and 0 <= hy < MAX_H and solid[hx][hz][hy]:
                        slot = tgrid[hx][hz][hy]
                        mt = TILE_MINE_TIME.get(slot, DEFAULT_MINE_TIME)
                        mining_progress += dt / mt
                        if mining_progress >= 1.0:
                            # 真的破坏
                            mined = tgrid[hx][hz][hy]
                            solid[hx][hz][hy] = False
                            tgrid[hx][hz][hy] = 0
                            vert_count = _rebuild_vbo(solid, tgrid, slot_uv, vbo_id)
                            if mined in PLACEABLE_BLOCKS:
                                _add_block_to_storage(hotbar, inv_grid,
                                                      PLACEABLE_BLOCKS.index(mined), 1)
                                _refresh_hotbar()
                                _refresh_inventory()
                            try:
                                from assets import play_sound
                                play_sound("dig", 0.35)
                            except Exception:
                                pass
                            # 准备挖下一格（如果还在按 LMB）
                            mining_target = target_block if target_block else None
                            mining_progress = 0.0
                            swing_timer = SWING_DURATION
                    else:
                        mining_target = None
                        mining_progress = 0.0

            # 走路摆动相位
            if grounded and (abs(player_vel[0]) + abs(player_vel[2])) > 0.5:
                walk_phase += dt * 10.0
                moving = True
            else:
                moving = False

            # 史莱姆群落 AI 更新（每只独立追玩家——读滞后位置 player_pos_lagged）
            for s in slimes:
                s.update(dt, player_pos_lagged, height, W)
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
            # 挖掘进度条：正在挖时在方块上方显示 0..1 的横条
            if mining_target is not None and mining_progress > 0:
                mx, my, mz = mining_target
                mpos = (mx + 0.5, my + 1.25, mz + 0.5)
                _draw_billboard_hp_bar(mpos, cam_pos, mining_progress, 0.8, height_world=0.12)

        # MC 风方块史莱姆群落：每只独立渲染（cube + 血条 + 粒子）
        for s in slimes:
            s.draw(slime_tex, slime_face_tex, cam_pos)

        # ---- 手持物品（世界空间 viewmodel：透视 + 走路摆动 + 挥动）----
        if sel_idx == 0:
            held_tex, is_hand = held_tool_tex[0], False
        elif sel_idx == 1:
            held_tex, is_hand = held_tool_tex[1], False
        else:
            stack = hotbar[sel_idx]
            if stack is not None and stack["count"] > 0 and held_block_tex[stack["block_idx"]]:
                held_tex, is_hand = held_block_tex[stack["block_idx"]], False
            else:
                held_tex, is_hand = None, True
        swing_progress = 1.0 - swing_timer / SWING_DURATION if swing_timer > 0 else 0.0
        if not paused and not inventory_open and not chest_open and (held_tex is not None or is_hand):
            _draw_viewmodel(held_tex, is_hand, swing_progress, walk_phase, moving)

        # ---- HUD（正交投影）----
        _draw_hud(hud_tex, hud_surf.get_size(),
                  hotbar_tex, hotbar_size,
                  pause_tex if paused else None, pause_surf.get_size(),
                  quit_rect if paused else None, quit_tex, quit_surf.get_size())
        # 背包叠加层（E 键打开时）
        if inventory_open:
            _draw_inventory_overlay(inv_tex, inv_size, inv_drag, held_block_tex, font,
                                    _inventory_grid_origin())
        # 箱子叠加层（右键箱子打开时）：箱子网格 + 玩家背包 + 热栏
        if chest_open:
            _draw_chest_overlay(chest_tex, chest_size, inv_tex, inv_size,
                                inv_drag, held_block_tex, font,
                                _chest_grid_origin(), _chest_inv_origin(),
                                hotbar_tex, hotbar_size)

        pygame.display.flip()

    # 清理
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    try:
        held_all = [t for t in held_tool_tex + held_block_tex if t is not None]
        texs = [atlas_tex, hud_tex, pause_tex, quit_tex, hotbar_tex, inv_tex, chest_tex]
        if slime_tex is not None:
            texs.append(slime_tex)
        if slime_face_tex is not None:
            texs.append(slime_face_tex)
        glDeleteTextures(texs + ([king_tex] if king_tex else []) + held_all)
        glDeleteBuffers([vbo_id])
        # 清掉文本贴图缓存（GL context 即将销毁，避免悬空 id 跨场景复用）
        cached = [t for t, _ in _text_cache.values()]
        _text_cache.clear()
        if cached:
            glDeleteTextures(cached)
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


def _draw_textured_cube(tex, center, size, tint=(1.0, 1.0, 1.0), side_tex=None, face_yaw=None):
    """六面贴图立方体（MC 风方块史莱姆用）。center=几何中心，size=边长。
    side_tex 可选：若提供，则"南面"(z=+1)用 side_tex（带眼睛的正面），
    其余 5 面用 tex（身体贴图，跟之前六面同图一样）。
    face_yaw 可选（弧度）：绕 Y 轴旋转整个立方体——传 slime→玩家方向角，
    可以让"脸"始终对着玩家。"""
    cx, cy, cz = center
    if face_yaw is not None:
        glPushMatrix()
        glTranslatef(cx, cy, cz)
        glRotatef(math.degrees(face_yaw), 0, 1, 0)
        glTranslatef(-cx, -cy, -cz)
    for name, normal, bright, verts in FACES:
        nx, ny, nz = normal
        # 只有南面（z=+1）用 side_tex，其余都用 tex（"再之前那个版本"的样子）
        if side_tex is not None and name == "south":
            glBindTexture(GL_TEXTURE_2D, side_tex)
        else:
            glBindTexture(GL_TEXTURE_2D, tex)
        glColor3f(bright * tint[0], bright * tint[1], bright * tint[2])
        glBegin(GL_QUADS)
        for dx, dy, dz in verts:
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
    if face_yaw is not None:
        glPopMatrix()


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


def _draw_inventory_overlay(inv_tex, inv_size, inv_drag, held_block_tex, font, inv_origin):
    """E 打开时画：半透明遮罩 + 背包网格贴片 + 拖拽中物品（贴鼠标）。"""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, C.WINDOW_WIDTH, C.WINDOW_HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # 半透明遮罩
    glColor4f(0.0, 0.0, 0.0, 0.55)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(C.WINDOW_WIDTH, 0)
    glVertex2f(C.WINDOW_WIDTH, C.WINDOW_HEIGHT)
    glVertex2f(0, C.WINDOW_HEIGHT)
    glEnd()

    gx, gy = inv_origin
    iw, ih = inv_size
    glEnable(GL_TEXTURE_2D)
    _blit_textured_quad(inv_tex, gx, gy, iw, ih)

    title_str = "Inventory  -  E/ESC close  -  click to pick up, click again to drop"
    tw, th = _cached_text_texture(font, title_str, (255, 230, 80))[1]
    _blit_text(font, title_str, (C.WINDOW_WIDTH - tw) // 2, gy - th - 8)

    _draw_drag_icon(inv_drag, held_block_tex, font)

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def _draw_chest_overlay(chest_tex, chest_size, inv_tex, inv_size,
                        inv_drag, held_block_tex, font,
                        chest_origin, inv_origin, hotbar_tex, hotbar_size):
    """右键箱子打开时画：半透明遮罩 + 箱子网格（上）+ 玩家背包（中）+ 热栏（下）+ 拖拽物品（贴鼠标）。"""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, C.WINDOW_WIDTH, C.WINDOW_HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # 半透明遮罩
    glColor4f(0.0, 0.0, 0.0, 0.6)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(C.WINDOW_WIDTH, 0)
    glVertex2f(C.WINDOW_WIDTH, C.WINDOW_HEIGHT)
    glVertex2f(0, C.WINDOW_HEIGHT)
    glEnd()

    glEnable(GL_TEXTURE_2D)
    # 箱子网格 / 玩家背包 / 底部热栏
    _blit_textured_quad(chest_tex, chest_origin[0], chest_origin[1], chest_size[0], chest_size[1])
    _blit_textured_quad(inv_tex, inv_origin[0], inv_origin[1], inv_size[0], inv_size[1])
    bx, by = _hotbar_origin(hotbar_size)
    _blit_textured_quad(hotbar_tex, bx, by, hotbar_size[0], hotbar_size[1])

    # 标题
    cx0, cy0 = chest_origin
    chest_title = "Chest  -  E/ESC close  -  drag to take items"
    ctw = _cached_text_texture(font, chest_title, (255, 230, 80))[1][0]
    _blit_text(font, chest_title, (C.WINDOW_WIDTH - ctw) // 2, cy0 - 22)
    ix0, iy0 = inv_origin
    inv_title = "Inventory"
    itw = _cached_text_texture(font, inv_title, (200, 200, 200))[1][0]
    _blit_text(font, inv_title, (C.WINDOW_WIDTH - itw) // 2, iy0 - 20, (200, 200, 200))

    _draw_drag_icon(inv_drag, held_block_tex, font)

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
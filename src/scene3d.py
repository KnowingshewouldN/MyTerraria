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

# 图集槽位编号
SLOT_GRASS, SLOT_DIRT, SLOT_STONE, SLOT_WOOD, SLOT_LEAVES, SLOT_SAND, SLOT_SNOW = range(7)
ATLAS_COLS = 4
ATLAS_CELL = 16          # 每个槽 16x16
ATLAS_SIZE = ATLAS_COLS * ATLAS_CELL  # 64

# 立方体 6 面：每面 4 个顶点偏移（CCW 朝外），亮度
FACES = [
    # name, normal, brightness, [(dx,dy,dz)x4]
    ("top",    (0, 1, 0), 1.00, [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]),
    ("bottom", (0, -1, 0), 0.50, [(0, 0, 1), (1, 0, 1), (1, 0, 0), (0, 0, 0)]),
    ("north",  (0, 0, -1), 0.80, [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ("south",  (0, 0, 1), 0.80, [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),
    ("east",   (1, 0, 0), 0.65, [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),  # +X 面
    ("west",   (-1, 0, 0), 0.65, [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)]),
]
# 邻居偏移（与 FACES 同顺序）
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


def _surface_to_texture(surface, flip=True):
    """pygame Surface -> OpenGL 纹理 id（RGBA）"""
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    rgba = pygame.image.tostring(surface, "RGBA", flip)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(), surface.get_height(),
                 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    return tex


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
                    for (dx, dy, dz), (u, v) in zip(verts, face_uv):
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
    glAlphaFunc(GL_GREATER, 0.5)
    glEnable(GL_ALPHA_TEST)          # billboard 透明边缘丢弃
    glClearColor(*_sky_gl(C.get_sky_color(5.0)), 1.0)

    # 投影
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = C.WINDOW_WIDTH / C.WINDOW_HEIGHT
    _perspective(70.0, aspect, 0.1, 300.0)
    glMatrixMode(GL_MODELVIEW)

    # 资源
    atlas_surf, slot_uv = _build_atlas()
    atlas_tex = _surface_to_texture(atlas_surf, flip=True)
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

    # 起始相机：世界中央上方，看向中心
    cam_pos = [W * 0.5, height[W // 2][W // 2] + EYE_HEIGHT + 0.5, W * 0.5 + 12]
    cam_yaw = math.pi       # 朝 -x？计算时调整：让初始看向中心
    cam_pitch = -0.08
    # 初始朝向中心
    cam_yaw = math.atan2(W * 0.5 - cam_pos[0], W * 0.5 - cam_pos[2])

    # HUD 文字纹理
    hud_surf = font.render(
        "3D Epilogue - WASD move | Mouse look | SPACE/SHIFT up/down | ESC exit",
        True, (255, 255, 255))
    hud_tex = _surface_to_texture(hud_surf, flip=False)

    # 鼠标锁定
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    pygame.event.get()  # 清空旧事件

    clock = pygame.time.Clock()
    running = True
    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # 鼠标视角
        dx, dy = pygame.mouse.get_rel()
        cam_yaw -= dx * LOOK_SENS * 0.01
        cam_pitch += dy * LOOK_SENS * 0.01
        cam_pitch = max(-1.4, min(1.4, cam_pitch))

        # 移动方向
        fwd = (math.sin(cam_yaw), 0.0, math.cos(cam_yaw))          # 水平前向
        right = (math.cos(cam_yaw), 0.0, -math.sin(cam_yaw))       # 水平右向

        keys = pygame.key.get_pressed()
        vx = vy = vz = 0.0
        if keys[pygame.K_w]:
            vx -= fwd[0]; vz -= fwd[2]
        if keys[pygame.K_s]:
            vx += fwd[0]; vz += fwd[2]
        if keys[pygame.K_d]:
            vx += right[0]; vz += right[2]
        if keys[pygame.K_a]:
            vx -= right[0]; vz -= right[2]
        if keys[pygame.K_SPACE]:
            vy += 1.0
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            vy -= 1.0
        # 归一化对角线速度
        horiz = math.sqrt(vx * vx + vz * vz)
        if horiz > 1.0:
            vx /= horiz; vz /= horiz
        speed = MOVE_SPEED * (2.2 if keys[pygame.K_LCTRL] else 1.0)
        cam_pos[0] += vx * speed * dt
        cam_pos[1] += vy * speed * dt
        cam_pos[2] += vz * speed * dt
        # 不允许穿地
        floor_y = 0.3
        if cam_pos[1] < floor_y:
            cam_pos[1] = floor_y

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
        glDrawArrays(GL_QUADS, 0, vert_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)

        # King Slime billboard（永远面向相机的圆柱公告板）
        # 底部贴地：center.y = ground + half_height
        if king_tex is not None:
            king_h = 4.5
            _draw_billboard(king_tex, (W * 0.5, height[W // 2][W // 2] + king_h * 0.5, W * 0.5),
                            cam_pos, cam_yaw, king_h, king_size)

        # ---- HUD（正交投影）----
        _draw_hud(hud_tex, hud_surf.get_size())

        pygame.display.flip()

    # 清理
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    try:
        glDeleteTextures([atlas_tex, hud_tex] + ([king_tex] if king_tex else []))
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


def _draw_hud(hud_tex, hud_size):
    """切换到正交投影画准星 + 文字，然后切回"""
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

    # 文字
    hw, hh = hud_size
    glBindTexture(GL_TEXTURE_2D, hud_tex)
    glColor3f(1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(12, 12)
    glTexCoord2f(1, 0); glVertex2f(12 + hw, 12)
    glTexCoord2f(1, 1); glVertex2f(12 + hw, 12 + hh)
    glTexCoord2f(0, 1); glVertex2f(12, 12 + hh)
    glEnd()

    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

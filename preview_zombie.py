"""
preview_zombie.py - 离线预览 3dres/zombie_villager 模型

用法:
    python preview_zombie.py

操作:
    鼠标左键拖拽  - 旋转视角
    鼠标滚轮      - 缩放
    1 / 2 / 3     - 切换 皮肤(92) / 衣服1(93) / 衣服2(96) 显示
    V             - 翻转贴图 V 轴（MC 贴图经常需要翻）
    N             - 切换光照（OBJ 没法线，手算面法线）
    A             - 自动旋转开关
    R             - 重置视角
    ESC           - 退出
"""
import os
import math
import sys
import pygame
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(HERE, "3dres", "zombie_villager")

WIN_W, WIN_H = 1024, 720
FOV = 45.0
NEAR, FAR = 0.05, 200.0


# ---------- OBJ 解析 ----------
def load_obj(path):
    verts, uvs, faces = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                parts = line[2:].split()
                verts.append(tuple(map(float, parts[:3])))
            elif line.startswith("vt "):
                parts = line[3:].split()
                uvs.append(tuple(map(float, parts[:2])))
            elif line.startswith("f "):
                # 支持 v/vt/vn 或 v//vn 或 v/vt 或 v
                idx = []
                for tok in line[2:].split():
                    bits = tok.split("/")
                    vi = int(bits[0]) - 1
                    vti = int(bits[1]) - 1 if len(bits) > 1 and bits[1] else vi
                    idx.append((vi, vti))
                # 三角形面直接加；四边面拆成 2 三角形
                if len(idx) == 3:
                    faces.append(idx)
                elif len(idx) == 4:
                    faces.append([idx[0], idx[1], idx[2]])
                    faces.append([idx[0], idx[2], idx[3]])
                else:
                    # 多边形 fan 三角化
                    for i in range(1, len(idx) - 1):
                        faces.append([idx[0], idx[i], idx[i + 1]])
    return verts, uvs, faces


def compute_face_normal(a, b, c):
    ax, ay, az = a
    bx, by, bz = b
    cx, cy, cz = c
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    L = math.sqrt(nx * nx + ny * ny + nz * nz)
    if L < 1e-9:
        return 0.0, 1.0, 0.0
    return nx / L, ny / L, nz / L


def center_model(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    # 让脚踩在 y=0：平移使 min(y)=0
    ymin = min(ys)
    return [(v[0] - cx, v[1] - ymin, v[2] - cz) for v in verts]


# ---------- 纹理 ----------
def load_texture(path):
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    data = img.tobytes("raw", "RGBA", 0, -1)  # 翻转 Y 适配 OpenGL
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    return tex, (w, h)


# ---------- 渲染 ----------
class Renderer:
    def __init__(self, verts, uvs, faces):
        self.verts = center_model(verts)
        self.uvs = uvs
        self.faces = faces
        # 预计算每面法线（用世界坐标）
        self.face_normals = []
        for f in faces:
            a = self.verts[f[0][0]]
            b = self.verts[f[1][0]]
            c = self.verts[f[2][0]]
            self.face_normals.append(compute_face_normal(a, b, c))

        # 纹理
        self.tex_skin, _ = load_texture(os.path.join(RES_DIR, "texture_92.png"))
        self.tex_cloth1, _ = load_texture(os.path.join(RES_DIR, "texture_93.png"))
        self.tex_cloth2, _ = load_texture(os.path.join(RES_DIR, "texture_96.png"))

        # 状态
        self.yaw = 0.6
        self.pitch = -0.2
        self.dist = 6.0
        self.show_skin = True
        self.show_cloth1 = True
        self.show_cloth2 = True
        self.v_flip = False
        self.light_on = True
        self.auto_rotate = True

    def draw_face_batch(self, tex_id, alpha_test=True):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        if alpha_test:
            glEnable(GL_ALPHA_TEST)
            glAlphaFunc(GL_GREATER, 0.5)
        else:
            glDisable(GL_ALPHA_TEST)
        glBegin(GL_TRIANGLES)
        for fidx, f in enumerate(self.faces):
            n = self.face_normals[fidx]
            glNormal3f(*n)
            for (vi, vti) in f:
                x, y, z = self.verts[vi]
                u, v = self.uvs[vti]
                if self.v_flip:
                    v = 1.0 - v
                glTexCoord2f(u, v)
                glVertex3f(x, y, z)
        glEnd()
        glDisable(GL_ALPHA_TEST)

    def render(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)

        # 光照
        if self.light_on:
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glLightfv(GL_LIGHT0, GL_POSITION, (5.0, 10.0, 7.0, 0.0))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (1.0, 1.0, 1.0, 1.0))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.45, 0.45, 0.45, 1.0))
            glMaterialfv(GL_FRONT, GL_DIFFUSE, (1.0, 1.0, 1.0, 1.0))
        else:
            glDisable(GL_LIGHTING)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # 相机：俯视看模型
        cx = self.dist * math.cos(self.pitch) * math.sin(self.yaw)
        cy = self.dist * math.sin(self.pitch)
        cz = self.dist * math.cos(self.pitch) * math.cos(self.yaw)
        # 模型中心约在 (0, height/2, 0)，所以眼睛往那里看
        target_y = 1.0  # 大约躯干中部
        gluLookAt(cx, cy + target_y, cz, 0, target_y, 0, 0, 1, 0)

        # 先画皮肤（不裁透明），再叠衣服（alpha test）
        if self.show_skin:
            self.draw_face_batch(self.tex_skin, alpha_test=False)
        if self.show_cloth1:
            self.draw_face_batch(self.tex_cloth1, alpha_test=True)
        if self.show_cloth2:
            self.draw_face_batch(self.tex_cloth2, alpha_test=True)

    def update_auto(self, dt):
        if self.auto_rotate:
            self.yaw += dt * 0.6


def setup_gl():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, WIN_W / WIN_H, NEAR, FAR)
    glMatrixMode(GL_MODELVIEW)
    glClearColor(0.18, 0.20, 0.24, 1.0)


def draw_hud(font, r):
    lines = [
        f"yaw={r.yaw:.2f} pitch={r.pitch:.2f} dist={r.dist:.2f}",
        f"[1] skin(92)={'ON' if r.show_skin else 'OFF'}  "
        f"[2] cloth(93)={'ON' if r.show_cloth1 else 'OFF'}  "
        f"[3] cloth2(96)={'ON' if r.show_cloth2 else 'OFF'}",
        f"[V] V-flip={'ON' if r.v_flip else 'OFF'}  "
        f"[N] light={'ON' if r.light_on else 'OFF'}  "
        f"[A] auto={'ON' if r.auto_rotate else 'OFF'}",
        "[R] reset  [ESC] quit   drag=rotate  wheel=zoom",
    ]
    y = 8
    for ln in lines:
        surf = font.render(ln, True, (255, 255, 255))
        screen = pygame.display.get_surface()
        screen.blit(surf, (10, y))
        y += surf.get_height() + 2


def main():
    pygame.init()
    pygame.display.set_mode((WIN_W, WIN_H), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("Zombie Villager Preview - 1/2/3 toggle, V flip, N light, A auto, R reset")
    setup_gl()

    obj_path = os.path.join(RES_DIR, "0.obj")
    verts, uvs, faces = load_obj(obj_path)
    print(f"Loaded {len(verts)} verts, {len(uvs)} uvs, {len(faces)} faces (after triangulation)")
    r = Renderer(verts, uvs, faces)

    font = pygame.font.Font(None, 18)  # 内置默认字体，绕过 SysFont 在 pygame 2.6.1+py3.13 的枚举 bug
    clock = pygame.time.Clock()
    dragging = False
    last = (0, 0)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_1:
                    r.show_skin = not r.show_skin
                elif e.key == pygame.K_2:
                    r.show_cloth1 = not r.show_cloth1
                elif e.key == pygame.K_3:
                    r.show_cloth2 = not r.show_cloth2
                elif e.key == pygame.K_v:
                    r.v_flip = not r.v_flip
                elif e.key == pygame.K_n:
                    r.light_on = not r.light_on
                elif e.key == pygame.K_a:
                    r.auto_rotate = not r.auto_rotate
                elif e.key == pygame.K_r:
                    r.yaw, r.pitch, r.dist = 0.6, -0.2, 6.0
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    dragging = True
                    last = e.pos
                    r.auto_rotate = False
                elif e.button == 4:
                    r.dist = max(1.5, r.dist - 0.4)
                elif e.button == 5:
                    r.dist = min(30.0, r.dist + 0.4)
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1:
                    dragging = False
            elif e.type == pygame.MOUSEMOTION:
                if dragging:
                    dx = e.pos[0] - last[0]
                    dy = e.pos[1] - last[1]
                    last = e.pos
                    r.yaw -= dx * 0.01
                    r.pitch = max(-1.4, min(1.4, r.pitch - dy * 0.01))

        r.update_auto(dt)
        r.render()

        # HUD（2D 覆盖在 GL 之上）
        glUseProgram(0)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, WIN_W, WIN_H, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glColor3f(1, 1, 1)
        # 切回 3D 投影
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        draw_hud(font, r)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()

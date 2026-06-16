# boss.py - King Slime Boss
import pygame
import math
import random
import constants as C
from pygame.locals import Rect


# Boss 显示尺寸（保持 gif 166:152 比例）
BOSS_W = C.BLOCKSIZE * 10          # 80
BOSS_H = int(BOSS_W * 152 / 166)  # ~73


class KingSlime:
    def __init__(self, position):
        self.position = [float(position[0]), float(position[1])]
        self.velocity = [0.0, 0.0]
        self.hp = C.BOSS_MAX_HP
        self.max_hp = C.BOSS_MAX_HP
        self.alive = True
        self.grounded = False
        self.direction = 1
        self.hurt_timer = 0.0

        # 碰撞框（比绘制稍小，便于移动）
        self.rect = Rect(0, 0, BOSS_W, BOSS_H)
        self.rect.centerx = int(self.position[0])
        self.rect.centery = int(self.position[1])

        self.block_x = 0
        self.block_y = 0
        self.anim_time = 0.0
        self.jump_tick = 1.2

        # 分裂技能
        self.split_stage = 0  # 已执行分裂次数（0,1,2）

        # 死亡
        self.dying = False
        self.death_timer = 0.0
        self.death_particles = []

        # 给 game.py 读取的队列
        self.drop_queue = []            # 死亡掉落
        self.spawn_minions_queue = []   # 分裂产生的小史莱姆

        # 缓存缩放后的帧
        self._frames = None

    def _get_frames(self):
        if self._frames is None:
            try:
                from assets import king_slime_frames
                if king_slime_frames:
                    self._frames = [pygame.transform.scale(f, (BOSS_W, BOSS_H))
                                    for f in king_slime_frames]
            except Exception:
                self._frames = []
            if not self._frames:
                self._frames = []
        return self._frames

    def update(self, world, player_pos, dt):
        if not self.alive:
            return

        # 死亡动画期间只更新粒子
        if self.dying:
            self.death_timer -= dt
            for p in self.death_particles:
                p['vy'] += C.GRAVITY * dt * 0.5
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['life'] -= dt
                p['size'] = max(0, p['size'] - dt * 14)
            self.death_particles = [p for p in self.death_particles if p['life'] > 0]
            if self.death_timer <= 0 and not self.death_particles:
                self.alive = False
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt

        self.anim_time += dt

        # 分裂技能：达到 HP 阈值则召唤小史莱姆
        ratio = self.hp / self.max_hp
        thresholds = C.BOSS_SPLIT_RATIO
        if self.split_stage == 0 and ratio < thresholds[0]:
            self._do_split(2)
            self.split_stage = 1
        elif self.split_stage == 1 and ratio < thresholds[1]:
            self._do_split(3)
            self.split_stage = 2

        # AI：朝玩家大跳
        if self.grounded:
            self.jump_tick -= dt
            if self.jump_tick <= 0:
                self.jump_tick = 1.0 + random.random() * 0.6
                if player_pos[0] < self.position[0]:
                    self.velocity[0] = -8
                    self.direction = -1
                else:
                    self.velocity[0] = 8
                    self.direction = 1
                self.velocity[1] = -48 + random.random() * 4

        # 重力 + 阻力
        if not self.grounded:
            self.velocity[1] += C.GRAVITY * dt
        drag = 1.0 - dt * 3
        self.velocity[0] *= drag
        self.velocity[1] *= (1.0 - dt)

        self.position[0] += self.velocity[0] * dt * C.BLOCKSIZE
        self.position[1] += self.velocity[1] * dt * C.BLOCKSIZE

        self.rect.centerx = int(self.position[0])
        self.rect.centery = int(self.position[1])
        self.block_x = int(self.position[0] // C.BLOCKSIZE)
        self.block_y = int(self.position[1] // C.BLOCKSIZE)

        self.grounded = False

        # 世界底
        border_down = world.height * C.BLOCKSIZE - BOSS_H * 0.5
        if self.position[1] > border_down:
            self.position[1] = border_down
            self.velocity[1] = 0
            self.grounded = True

        # 碰撞（Boss 较大，检查更宽范围）
        from world import tile_in_map
        for dy in range(-3, 4):
            for dx in range(-4, 5):
                tx = self.block_x + dx
                ty = self.block_y + dy
                if not tile_in_map(world, tx, ty) or ty < 0:
                    continue
                tile_id = world.tile_data[tx][ty]
                info = C.TILES.get(tile_id)
                if info is None or not info["solid"]:
                    continue
                block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE,
                                  C.BLOCKSIZE, C.BLOCKSIZE)
                if not block_rect.colliderect(self.rect):
                    continue
                delta_x = self.position[0] - block_rect.centerx
                delta_y = self.position[1] - block_rect.centery
                if abs(delta_x) > abs(delta_y):
                    if delta_x > 0:
                        self.position[0] = block_rect.right + self.rect.width * 0.5
                    else:
                        self.position[0] = block_rect.left - self.rect.width * 0.5
                    self.velocity[0] = 0
                else:
                    if delta_y > 0:
                        if self.velocity[1] < 0:
                            self.position[1] = block_rect.bottom + self.rect.height * 0.5
                            self.velocity[1] = 0
                    else:
                        if self.velocity[1] > 0:
                            self.position[1] = block_rect.top - self.rect.height * 0.5 + 1
                            self.velocity = [self.velocity[0] * 0.5, 0]
                            self.grounded = True
                self.rect.centerx = int(self.position[0])
                self.rect.centery = int(self.position[1])

    def damage(self, value, source_velocity=None):
        if not self.alive or self.dying:
            return
        self.hp -= value
        if self.hurt_timer <= 0:
            try:
                from assets import play_sound
                play_sound("npc_hit", 0.5)
            except Exception:
                pass
            self.hurt_timer = 0.25
        if self.hp <= 0:
            self.hp = 0
            self.dying = True
            self.death_timer = 0.9
            self._spawn_death_particles(source_velocity)
            self._generate_drops()
            try:
                from assets import play_sound
                play_sound("npc_killed", 0.6)
            except Exception:
                pass

    def _do_split(self, count):
        """分裂出 count 只小史莱姆，写入 spawn_minions_queue"""
        for _ in range(count):
            off_x = random.uniform(-BOSS_W * 0.5, BOSS_W * 0.5)
            self.spawn_minions_queue.append({
                "pos": (self.position[0] + off_x, self.position[1] - 4),
                "slime_type": random.randint(0, 2),
            })

    def _spawn_death_particles(self, source_velocity=None):
        color = (0, 180, 220)
        if source_velocity is not None:
            vel_angle = math.atan2(source_velocity[1], source_velocity[0])
            vel_mag = math.sqrt(source_velocity[0] ** 2 + source_velocity[1] ** 2)
        else:
            vel_angle = -math.pi * 0.5
            vel_mag = 40
        for _ in range(30):
            p_angle = vel_angle + (random.random() - 0.5) * math.pi * 1.5
            p_speed = random.random() * vel_mag * 0.6 + 25
            self.death_particles.append({
                'x': self.position[0] + random.random() * BOSS_W - BOSS_W * 0.5,
                'y': self.position[1] + random.random() * BOSS_H - BOSS_H * 0.5,
                'vx': math.cos(p_angle) * p_speed,
                'vy': math.sin(p_angle) * p_speed,
                'life': 0.4 + random.random() * 0.5,
                'size': 5 + random.random() * 8,
                'color': color,
            })

    def _generate_drops(self):
        # 击败 Boss 丰厚掉落
        self.drop_queue.append({"item_id": 13, "count": random.randint(8, 14)})  # Gel
        self.drop_queue.append({"item_id": 14, "count": random.randint(25, 45)})  # Copper Coin

    def draw(self, screen, cam_x, cam_y):
        if not self.alive:
            return

        # 死亡粒子始终绘制
        for p in self.death_particles:
            sx = p['x'] - cam_x + C.WINDOW_WIDTH * 0.5
            sy = p['y'] - cam_y + C.WINDOW_HEIGHT * 0.5
            size = int(p['size'])
            if size > 0:
                pygame.draw.rect(screen, p['color'], (int(sx), int(sy), size, size))

        if self.dying:
            return

        frames = self._get_frames()
        sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5 - BOSS_W * 0.5
        sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5 - BOSS_H * 0.5

        if frames:
            idx = int(self.anim_time * 8) % len(frames)
            surf = frames[idx]
            if self.direction == -1:
                surf = pygame.transform.flip(surf, True, False)
            if self.hurt_timer > 0:
                surf = surf.copy()
                white = pygame.Surface(surf.get_size())
                white.fill((255, 255, 255))
                surf.blit(white, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            screen.blit(surf, (sx, sy))
        else:
            # 备用：蓝色大矩形
            color = (0, 180, 220) if self.hurt_timer <= 0 else (255, 255, 255)
            pygame.draw.rect(screen, color, (sx, sy, BOSS_W, BOSS_H))
            pygame.draw.rect(screen, (255, 255, 255), (sx, sy, BOSS_W, BOSS_H), 2)

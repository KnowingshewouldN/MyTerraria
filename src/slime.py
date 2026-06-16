# slime.py - 史莱姆怪物
import pygame
import math
import random
import constants as C
from pygame.locals import Rect
from world import tile_in_map


# 史莱姆颜色
SLIME_COLORS = [
    (0, 200, 0),     # green
    (0, 100, 255),   # blue
    (200, 50, 50),   # red
    (200, 200, 0),   # yellow
    (200, 0, 200),   # purple
]


class Slime:
    def __init__(self, position, slime_type=0):
        self.position = list(position)
        self.velocity = [0.0, 0.0]
        self.slime_type = slime_type  # 0=green, 1=blue, 2=red...
        self.hp = 50 + slime_type * 15
        self.max_hp = self.hp
        self.alive = True
        self.grounded = False

        # 史莱姆大小：32x24（跟原项目一致，BLOCKSIZE*2 x BLOCKSIZE*1.5）
        self.rect = Rect(0, 0, C.BLOCKSIZE * 2, int(C.BLOCKSIZE * 1.5))
        self.rect.left = self.position[0] - self.rect.width * 0.5
        self.rect.top = self.position[1] - self.rect.height * 0.5

        self.block_x = 0
        self.block_y = 0
        self.animation_frame = 0
        self.jump_tick = 1.0
        self.direction = 1
        self.hurt_timer = 0.0

        # 死亡动画
        self.dying = False
        self.death_timer = 0
        self.death_particles = []

        # 掉落物队列（game.py 读取后清空）
        self.drop_queue = []
        # 死亡是否已计入击杀数（game.py 用）
        self._counted = False

    def update(self, world, player_pos, dt):
        if not self.alive:
            return

        # 更新死亡粒子
        if self.dying:
            self.death_timer -= dt
            for p in self.death_particles:
                p['vy'] += C.GRAVITY * dt * 0.5
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['life'] -= dt
                p['size'] = max(0, p['size'] - dt * 8)
            self.death_particles = [p for p in self.death_particles if p['life'] > 0]
            if self.death_timer <= 0 and not self.death_particles:
                self.alive = False
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt

        # AI：朝玩家跳跃
        if self.grounded:
            self.jump_tick -= dt
            if self.jump_tick <= 0:
                self.jump_tick = 0.5 + random.random() * 0.5
                if player_pos[0] < self.position[0]:
                    self.velocity[0] = -10
                    self.direction = -1
                else:
                    self.velocity[0] = 10
                    self.direction = 1
                self.velocity[1] = -45 + random.random() * 5

        # 重力
        if not self.grounded:
            self.velocity[1] += C.GRAVITY * dt

        drag = 1.0 - dt * 4
        self.velocity[0] *= drag
        self.velocity[1] *= (1.0 - dt)

        self.position[0] += self.velocity[0] * dt * C.BLOCKSIZE
        self.position[1] += self.velocity[1] * dt * C.BLOCKSIZE

        self.rect.left = self.position[0] - self.rect.width * 0.5
        self.rect.top = self.position[1] - self.rect.height * 0.5
        self.block_x = int(self.position[0] // C.BLOCKSIZE)
        self.block_y = int(self.position[1] // C.BLOCKSIZE)

        self.grounded = False

        # 边界
        border_down = world.height * C.BLOCKSIZE - int(C.BLOCKSIZE * 1.5)
        if self.position[1] > border_down:
            self.position[1] = border_down
            self.velocity[1] = 0
            self.grounded = True

        # 碰撞
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                tx = self.block_x + dx
                ty = self.block_y + dy
                if not tile_in_map(world, tx, ty) or ty < 0:
                    continue
                tile_id = world.tile_data[tx][ty]
                tile_info = C.TILES.get(tile_id)
                if tile_info is None or not tile_info["solid"]:
                    continue

                block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE, C.BLOCKSIZE, C.BLOCKSIZE)
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

                self.rect.left = self.position[0] - self.rect.width * 0.5
                self.rect.top = self.position[1] - self.rect.height * 0.5

        # 动画
        if not self.grounded:
            if self.velocity[1] > 2:
                self.animation_frame = 2
            elif self.velocity[1] < -2:
                self.animation_frame = 1
            else:
                self.animation_frame = 0
        else:
            self.animation_frame = 0

        # 检查距离玩家太远则消失
        dx = self.position[0] - player_pos[0]
        dy = self.position[1] - player_pos[1]
        if math.sqrt(dx * dx + dy * dy) > C.BLOCKSIZE * 60:
            self.alive = False

    def damage(self, value, source_velocity=None):
        if not self.alive or self.dying:
            return
        self.hp -= value
        if self.hurt_timer <= 0:
            try:
                from assets import play_sound
                play_sound("npc_hit", 0.4)
            except Exception:
                pass
            self.hurt_timer = 0.3
        if self.hp <= 0:
            self.hp = 0
            self.dying = True
            self.death_timer = 0.5
            self._spawn_death_particles(source_velocity)
            self._generate_drops()
            try:
                from assets import play_sound
                play_sound("npc_killed", 0.5)
            except Exception:
                pass

    def _spawn_death_particles(self, source_velocity=None):
        """生成死亡爆炸粒子（参考原项目 enemy.kill）"""
        color = SLIME_COLORS[self.slime_type % len(SLIME_COLORS)]
        # 击退方向作为粒子主方向
        if source_velocity is not None:
            vel_angle = math.atan2(source_velocity[1], source_velocity[0])
            vel_mag = math.sqrt(source_velocity[0] ** 2 + source_velocity[1] ** 2)
        else:
            vel_angle = -math.pi * 0.5
            vel_mag = 30
        for _ in range(15):
            p_angle = vel_angle + (random.random() - 0.5) * math.pi * 1.5
            p_speed = random.random() * vel_mag * 0.5 + 20
            self.death_particles.append({
                'x': self.position[0] + random.random() * self.rect.width - self.rect.width * 0.5,
                'y': self.position[1] + random.random() * self.rect.height - self.rect.height * 0.5,
                'vx': math.cos(p_angle) * p_speed,
                'vy': math.sin(p_angle) * p_speed,
                'life': 0.3 + random.random() * 0.4,
                'size': 4 + random.random() * 6,
                'color': color,
            })

    def _generate_drops(self):
        """生成掉落物（凝胶 + 金币）"""
        # 凝胶：1-2 个
        gel_count = random.randint(1, 2)
        self.drop_queue.append({"item_id": 13, "count": gel_count})
        # 铜币：1-5 个
        coin_count = random.randint(1, 5)
        self.drop_queue.append({"item_id": 14, "count": coin_count})

    def draw(self, screen, cam_x, cam_y):
        if not self.alive:
            return

        # 死亡粒子（在身体消失后仍要绘制）
        for p in self.death_particles:
            sx = p['x'] - cam_x + C.WINDOW_WIDTH * 0.5
            sy = p['y'] - cam_y + C.WINDOW_HEIGHT * 0.5
            size = int(p['size'])
            if size > 0:
                pygame.draw.rect(screen, p['color'], (int(sx), int(sy), size, size))

        if self.dying:
            return

        try:
            from assets import slime_surfaces
            if not slime_surfaces:
                return
            idx = self.slime_type * 3 + self.animation_frame
            if idx < len(slime_surfaces):
                surf = slime_surfaces[idx]
                sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5 - surf.get_width() * 0.5
                sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5 - surf.get_height() * 0.5
                # 受伤时闪烁
                if self.hurt_timer > 0:
                    surf = surf.copy()
                    white = pygame.Surface(surf.get_size())
                    white.fill((255, 255, 255))
                    surf.blit(white, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                screen.blit(surf, (sx, sy))
        except Exception:
            pass

        # 血条
        if self.hp < self.max_hp and self.hp > 0:
            sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5 - self.rect.width * 0.5
            sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5 - self.rect.height * 0.5
            bar_w = self.rect.width
            ratio = self.hp / self.max_hp
            pygame.draw.rect(screen, (60, 60, 60), (sx, sy - 6, bar_w, 4))
            pygame.draw.rect(screen, (int(255 * (1 - ratio)), int(255 * ratio), 0),
                             (sx + 1, sy - 5, int((bar_w - 2) * ratio), 2))

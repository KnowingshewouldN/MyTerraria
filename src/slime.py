# slime.py - 史莱姆怪物
import pygame
import math
import random
import constants as C
from pygame.locals import Rect
from world import tile_in_map


class Slime:
    def __init__(self, position, slime_type=0):
        self.position = list(position)
        self.velocity = [0.0, 0.0]
        self.slime_type = slime_type  # 0=green, 1=blue, 2=red...
        self.hp = 30 + slime_type * 10
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

    def update(self, world, player_pos, dt):
        if not self.alive:
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

    def damage(self, value):
        if not self.alive:
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
            self.alive = False

    def draw(self, screen, cam_x, cam_y):
        if not self.alive:
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

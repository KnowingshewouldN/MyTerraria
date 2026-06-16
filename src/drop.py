# drop.py - 物品掉落物实体（方块/怪物产出后落地、可被吸附、可拾取）
import pygame
import math
import random
import constants as C
from pygame.locals import Rect


VACUUM_RANGE = 4.0 * C.BLOCKSIZE     # 进入此范围开始被吸引
LIFETIME = 120.0                      # 2 分钟后自然消失
NO_PICKUP_DELAY = 0.35                # 刚生成时短暂不可拾取
POP_SPEED_MIN = 6.0
POP_SPEED_MAX = 11.0
MAX_VACUUM_SPEED = 30.0
VACUUM_ACCEL = 32.0


class Drop:
    def __init__(self, position, item_id, count=1):
        self.position = [float(position[0]), float(position[1])]
        # 向上弹出的初始速度（模拟方块/怪物被破坏时迸溅）
        angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
        speed = random.uniform(POP_SPEED_MIN, POP_SPEED_MAX)
        self.velocity = [math.cos(angle) * speed, math.sin(angle) * speed]
        self.item_id = item_id
        self.count = count
        self.age = 0.0
        self.alive = True
        self.grounded = False
        self.attracted = False
        self.bounce_count = 0
        # 小尺寸碰撞框（掉落物体积小）
        self.rect = Rect(0, 0, 10, 10)
        self._sync_rect()
        self._icon = None  # 懒加载图标

    def _sync_rect(self):
        self.rect.centerx = int(self.position[0])
        self.rect.centery = int(self.position[1])

    def _icon_surface(self):
        if self._icon is None:
            self._icon = C.get_item_icon(self.item_id, size=C.BLOCKSIZE)
        return self._icon

    def update(self, world, player_pos, player_rect, dt):
        from world import tile_in_map
        self.age += dt

        dx = player_pos[0] - self.position[0]
        dy = player_pos[1] - self.position[1]
        dist = math.sqrt(dx * dx + dy * dy)

        # 进入吸附范围且过了保护期 -> 向玩家加速
        self.attracted = (self.age > NO_PICKUP_DELAY) and (dist < VACUUM_RANGE)

        if self.attracted:
            if dist > 0.5:
                self.velocity[0] += (dx / dist) * VACUUM_ACCEL
                self.velocity[1] += (dy / dist) * VACUUM_ACCEL
            spd = math.sqrt(self.velocity[0] ** 2 + self.velocity[1] ** 2)
            if spd > MAX_VACUUM_SPEED:
                self.velocity[0] = self.velocity[0] / spd * MAX_VACUUM_SPEED
                self.velocity[1] = self.velocity[1] / spd * MAX_VACUUM_SPEED
        else:
            self.velocity[1] += C.GRAVITY * dt
            self.velocity[0] *= (1.0 - dt * 2.0)

        self.position[0] += self.velocity[0] * dt * C.BLOCKSIZE
        self.position[1] += self.velocity[1] * dt * C.BLOCKSIZE
        self._sync_rect()

        # 方块碰撞（主要处理落地与墙壁）
        bx = int(self.position[0] // C.BLOCKSIZE)
        by = int(self.position[1] // C.BLOCKSIZE)
        for ty in (by - 1, by, by + 1):
            for tx in (bx - 1, bx, bx + 1):
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
                    self.velocity[0] *= -0.3
                else:
                    if delta_y > 0:
                        self.position[1] = block_rect.bottom + self.rect.height * 0.5
                        if self.velocity[1] < 0:
                            self.velocity[1] = 0
                    else:
                        self.position[1] = block_rect.top - self.rect.height * 0.5
                        if self.velocity[1] > 0:
                            # 落地：前两次反弹，之后静止
                            if (self.bounce_count < 2
                                    and abs(self.velocity[1]) > 4
                                    and not self.attracted):
                                self.velocity[1] = -self.velocity[1] * 0.4
                                self.bounce_count += 1
                            else:
                                self.velocity[1] = 0
                                self.grounded = True
                        self.velocity[0] *= 0.7
                self._sync_rect()

        # 寿命到期
        if self.age > LIFETIME:
            self.alive = False

    def can_pickup(self):
        return self.age > NO_PICKUP_DELAY

    def nudge_away(self, player_pos):
        """库存满时把掉落物短暂推开，避免卡在玩家体内"""
        dx = self.position[0] - player_pos[0]
        dy = self.position[1] - player_pos[1]
        d = math.sqrt(dx * dx + dy * dy) or 1.0
        self.velocity[0] += (dx / d) * 18.0
        self.velocity[1] += (dy / d) * 18.0 - 6.0

    def draw(self, screen, cam_x, cam_y):
        # 即将消失时闪烁
        if self.age > LIFETIME - 10 and int(self.age * 8) % 2 == 0:
            return
        sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5
        sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5
        icon = self._icon_surface()
        if icon:
            screen.blit(icon, (sx - icon.get_width() * 0.5,
                               sy - icon.get_height() * 0.5))
        else:
            info = C.ITEMS.get(self.item_id)
            color = info["color"] if info else (255, 255, 0)
            pygame.draw.rect(screen, color, (sx - 5, sy - 5, 10, 10))

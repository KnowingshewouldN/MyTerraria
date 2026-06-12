# player.py - 玩家物理、快捷栏、方块交互、绘制
import pygame
import math
import constants as C
from pygame.locals import Rect


class Player:
    def __init__(self, position):
        self.position = list(position)  # [x, y] 像素坐标，中心点
        self.velocity = [0.0, 0.0]
        self.rect = Rect(0, 0, C.PLAYER_WIDTH, C.PLAYER_HEIGHT)
        self._update_rect()

        self.grounded = False
        self.direction = 1  # 1=右, -1=左
        self.hp = 100
        self.max_hp = 100
        self.alive = True

        # 移动状态
        self.moving_left = False
        self.moving_right = False
        self.moving_down = False

        # 快捷栏
        self.hotbar = []
        for slot in C.DEFAULT_HOTBAR:
            if slot is not None:
                self.hotbar.append({"item_id": slot["item_id"], "count": slot["count"]})
            else:
                self.hotbar.append(None)
        self.hotbar_index = 0

        # 攻击/使用状态
        self.use_cooldown = 0.0
        self.swinging = False
        self.swing_timer = 0.0
        self.swing_duration = 0.2

        # 方块坐标缓存
        self.block_x = 0
        self.block_y = 0

    def _update_rect(self):
        self.rect.left = self.position[0] - C.PLAYER_WIDTH * 0.5
        self.rect.top = self.position[1] - C.PLAYER_HEIGHT * 0.5

    def update(self, world, dt):
        if not self.alive:
            return

        # 冷却计时
        if self.use_cooldown > 0:
            self.use_cooldown -= dt
        if self.swinging:
            self.swing_timer -= dt
            if self.swing_timer <= 0:
                self.swinging = False

        # 水平移动
        if self.moving_left:
            speed = -5.0 if self.moving_down else -C.PLAYER_SPEED
            self.velocity[0] = speed
            self.direction = -1
        if self.moving_right:
            speed = 5.0 if self.moving_down else C.PLAYER_SPEED
            self.velocity[0] = speed
            self.direction = 1

        # 重力和阻力
        drag = 1.0 - dt
        self.velocity[0] *= drag
        self.velocity[1] = self.velocity[1] * drag + C.GRAVITY * dt

        # 更新位置
        self.position[0] += self.velocity[0] * dt * C.BLOCKSIZE
        self.position[1] += self.velocity[1] * dt * C.BLOCKSIZE
        self._update_rect()

        # 方块坐标
        self.block_x = int(self.position[0] // C.BLOCKSIZE)
        self.block_y = int(self.position[1] // C.BLOCKSIZE)

        self.grounded = False

        # 世界边界
        border_left = C.BLOCKSIZE
        border_right = world.width * C.BLOCKSIZE - C.BLOCKSIZE
        border_up = int(C.BLOCKSIZE * 1.5)
        border_down = world.height * C.BLOCKSIZE - int(C.BLOCKSIZE * 1.5)

        if self.position[0] < border_left:
            self.position[0] = border_left
        if self.position[0] > border_right:
            self.position[0] = border_right
        if self.position[1] < border_up:
            self.position[1] = border_up
            self.velocity[1] = 0
        if self.position[1] > border_down:
            self.position[1] = border_down
            self.velocity[1] = 0
            self.grounded = True

        # 碰撞检测 - 检查周围 5x5 格子
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                tx = self.block_x + dx
                ty = self.block_y + dy

                if not tile_in_map(world, tx, ty):
                    continue
                if ty < 0:
                    continue

                tile_id = world.tile_data[tx][ty]
                tile_info = C.TILES.get(tile_id)

                if tile_info is None or not tile_info["solid"]:
                    # 平台特殊处理
                    if tile_id == 7:  # Platform
                        block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE, C.BLOCKSIZE, C.BLOCKSIZE)
                        if block_rect.colliderect(self.rect):
                            # 只从上方碰撞
                            if self.velocity[1] > 0:
                                if self.position[1] + C.PLAYER_HEIGHT * 0.5 <= ty * C.BLOCKSIZE + 4:
                                    if not self.moving_down:
                                        self.position[1] = ty * C.BLOCKSIZE - C.PLAYER_HEIGHT * 0.5 + 1
                                        self.velocity[1] = 0
                                        self.grounded = True
                                        self._update_rect()
                    continue

                block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE, C.BLOCKSIZE, C.BLOCKSIZE)
                if not block_rect.colliderect(self.rect):
                    continue

                # 计算推离方向
                delta_x = self.position[0] - block_rect.centerx
                delta_y = self.position[1] - block_rect.centery

                if abs(delta_x) > abs(delta_y):
                    if delta_x > 0:
                        self.position[0] = block_rect.right + C.PLAYER_WIDTH * 0.5
                    else:
                        self.position[0] = block_rect.left - C.PLAYER_WIDTH * 0.5
                    self.velocity[0] = 0
                else:
                    if delta_y > 0:
                        # 头顶碰撞
                        if self.velocity[1] < 0:
                            self.position[1] = block_rect.bottom + C.PLAYER_HEIGHT * 0.5
                            self.velocity[1] = 0
                    else:
                        # 脚下碰撞（着地）
                        if self.velocity[1] > 0:
                            self.position[1] = block_rect.top - C.PLAYER_HEIGHT * 0.5 + 1
                            self.velocity = [self.velocity[0] * 0.5, 0]
                            self.grounded = True
                self._update_rect()

    def jump(self):
        if self.grounded:
            self.velocity[1] = C.JUMP_VELOCITY
            self.grounded = False

    def use_item(self, world, mouse_tile, terrain_surface):
        """根据手持物品执行操作"""
        if self.use_cooldown > 0:
            return

        slot = self.hotbar[self.hotbar_index]
        if slot is None:
            return

        item_id = slot["item_id"]
        item = C.ITEMS[item_id]
        tx, ty = mouse_tile

        if item["is_pickaxe"]:
            self._mine_block(world, tx, ty, terrain_surface)
        elif item["is_sword"]:
            self._swing_sword()
        elif item["is_block"]:
            self._place_block(world, tx, ty, item["place_tile"], terrain_surface)

    def _mine_block(self, world, tx, ty, terrain_surface):
        if not tile_in_map(world, tx, ty):
            return

        # 距离检查
        dx = tx - self.block_x
        dy = ty - self.block_y
        if math.sqrt(dx * dx + dy * dy) > C.PLAYER_REACH:
            return

        tile_id = world.tile_data[tx][ty]
        if tile_id == C.AIR:
            return

        tile_info = C.TILES[tile_id]
        drop_item_id = tile_info["drop_item"]

        # 移除方块
        world.tile_data[tx][ty] = C.AIR
        update_tile(terrain_surface, world, tx, ty)

        # 添加掉落物到快捷栏
        if drop_item_id is not None:
            self._add_item(drop_item_id, 1)

        self.use_cooldown = C.MINE_COOLDOWN
        self.swinging = True
        self.swing_timer = self.swing_duration

    def _place_block(self, world, tx, ty, place_tile, terrain_surface):
        if not tile_in_map(world, tx, ty):
            return

        # 距离检查
        dx = tx - self.block_x
        dy = ty - self.block_y
        if math.sqrt(dx * dx + dy * dy) > C.PLAYER_REACH:
            return

        # 目标格子必须为空
        if world.tile_data[tx][ty] != C.AIR:
            return

        # 必须有至少一个相邻实心方块
        if get_neighbor_count(world, tx, ty) == 0:
            return

        # 不能放在玩家身上
        block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE + 1, C.BLOCKSIZE, C.BLOCKSIZE)
        if block_rect.colliderect(self.rect):
            return

        # 放置方块
        world.tile_data[tx][ty] = place_tile
        update_tile(terrain_surface, world, tx, ty)

        # 减少物品数量
        slot = self.hotbar[self.hotbar_index]
        slot["count"] -= 1
        if slot["count"] <= 0:
            self.hotbar[self.hotbar_index] = None

        self.use_cooldown = C.MINE_COOLDOWN
        self.swinging = True
        self.swing_timer = self.swing_duration

    def _swing_sword(self):
        self.swinging = True
        self.swing_timer = self.swing_duration
        self.use_cooldown = C.ATTACK_COOLDOWN

    def _add_item(self, item_id, count):
        """添加物品到快捷栏"""
        # 先尝试堆叠到已有的同类物品
        for i, slot in enumerate(self.hotbar):
            if slot is not None and slot["item_id"] == item_id:
                item_info = C.ITEMS[item_id]
                if slot["count"] < item_info["max_stack"]:
                    can_add = min(count, item_info["max_stack"] - slot["count"])
                    slot["count"] += can_add
                    count -= can_add
                    if count <= 0:
                        return

        # 放到空槽位
        for i, slot in enumerate(self.hotbar):
            if slot is None:
                self.hotbar[i] = {"item_id": item_id, "count": count}
                return

    def draw(self, screen, cam_x, cam_y):
        """绘制玩家"""
        sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5
        sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5

        # 尝试使用精灵图
        try:
            from assets import torso_frames, hair_frames
            if torso_frames:
                self._draw_with_sprites(screen, sx, sy, torso_frames, hair_frames)
                return
        except Exception:
            pass

        # 备用：纯色矩形
        self._draw_fallback(screen, sx, sy)

    def _draw_with_sprites(self, screen, sx, sy, torso_frames, hair_frames):
        """使用精灵图绘制玩家"""
        # 身体帧选择
        # torso_frames: 19列 x 4行 = 76帧
        # 行 0-1: 朝右, 行 2-3: 朝左
        # 每行 19 帧: 站立(0), 走路动画(1-18)
        if self.direction == 1:  # 朝右
            row = 0 if self.grounded else 2
        else:  # 朝左
            row = 1 if self.grounded else 3

        # 简单走路动画：移动时在几帧间切换
        if abs(self.velocity[0]) > 1 and self.grounded:
            anim_frame = int(pygame.time.get_ticks() / 150) % 4 + 1
        else:
            anim_frame = 0

        frame_index = row * 19 + min(anim_frame, 18)
        if frame_index < len(torso_frames):
            torso_surf = torso_frames[frame_index]
            # 精灵大小约 40x60 (20x30 scale 2x)
            tw, th = torso_surf.get_size()
            # 翻转朝左
            if self.direction == -1:
                torso_surf = pygame.transform.flip(torso_surf, True, False)
            screen.blit(torso_surf, (sx - tw * 0.5, sy - th * 0.5))

        # 头发
        hair_index = 0  # 默认第一个发型
        if hair_index < len(hair_frames):
            hair_surf = hair_frames[hair_index]
            hw, hh = hair_surf.get_size()
            if self.direction == -1:
                hair_surf = pygame.transform.flip(hair_surf, True, False)
            screen.blit(hair_surf, (sx - hw * 0.5, sy - C.PLAYER_HEIGHT * 0.5 - hh + 4))

        # 挥剑动画
        if self.swinging:
            self._draw_sword_swing(screen, sx, sy)

    def _draw_fallback(self, screen, sx, sy):
        """备用纯色矩形绘制"""
        body_w = C.PLAYER_WIDTH
        body_h = C.PLAYER_HEIGHT

        pygame.draw.rect(screen, (70, 130, 180),
                         (sx - body_w * 0.5, sy - body_h * 0.5, body_w, body_h * 0.6))
        pygame.draw.rect(screen, (100, 70, 50),
                         (sx - body_w * 0.5, sy - body_h * 0.5 + body_h * 0.6, body_w, body_h * 0.4))
        pygame.draw.rect(screen, (230, 190, 150),
                         (sx - 8, sy - body_h * 0.5 - 10, 16, 12))
        eye_x = sx + 3 * self.direction
        pygame.draw.rect(screen, (0, 0, 0), (eye_x - 1, sy - body_h * 0.5 - 6, 3, 3))

        if self.swinging:
            self._draw_sword_swing(screen, sx, sy)

    def _draw_sword_swing(self, screen, sx, sy):
        """绘制挥剑动画"""
        sword_len = 30
        angle = -0.5 + (1.0 - self.swing_timer / self.swing_duration) * 1.5
        if self.direction == -1:
            angle = math.pi - angle
        arm_x = sx + 8 * self.direction
        arm_y = sy - C.PLAYER_HEIGHT * 0.25
        end_x = arm_x + math.cos(angle) * sword_len
        end_y = arm_y + math.sin(angle) * sword_len
        pygame.draw.line(screen, (200, 200, 200), (arm_x, arm_y), (end_x, end_y), 3)
        pygame.draw.line(screen, (255, 255, 100), (arm_x, arm_y), (end_x, end_y), 1)


# 从 world 模块导入需要的函数（放在文件末尾避免循环导入）
from world import tile_in_map, get_neighbor_count, update_tile

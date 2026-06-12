# player.py - 玩家物理、快捷栏、方块交互、绘制
import pygame
import math
import constants as C
from pygame.locals import Rect


class Player:
    def __init__(self, position):
        self.position = list(position)
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
        self.swing_duration = 0.3
        self.swing_progress = 0.0  # 0->1 挥动进度

        # 挖掘状态
        self.mining_target = None  # (tx, ty) 正在挖的方块
        self.mining_progress = 0.0  # 0->1 挖掘进度
        self.mining_time = 0.4  # 挖一个方块需要的秒数

        # 走路音效
        self.run_sound_timer = 0.0

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
            self.swing_progress = 1.0 - max(0, self.swing_timer) / self.swing_duration
            if self.swing_timer <= 0:
                self.swinging = False
                self.swing_progress = 0.0

        # 水平移动
        old_grounded = self.grounded
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

        # 碰撞检测
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                tx = self.block_x + dx
                ty = self.block_y + dy
                if not tile_in_map(world, tx, ty) or ty < 0:
                    continue

                tile_id = world.tile_data[tx][ty]
                tile_info = C.TILES.get(tile_id)

                if tile_info is None or not tile_info["solid"]:
                    if tile_id == 7:  # Platform
                        block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE, C.BLOCKSIZE, C.BLOCKSIZE)
                        if block_rect.colliderect(self.rect):
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
                        if self.velocity[1] < 0:
                            self.position[1] = block_rect.bottom + C.PLAYER_HEIGHT * 0.5
                            self.velocity[1] = 0
                    else:
                        if self.velocity[1] > 0:
                            # 着地时播放音效
                            if not old_grounded:
                                _play("tink", 0.3)
                            self.position[1] = block_rect.top - C.PLAYER_HEIGHT * 0.5 + 1
                            self.velocity = [self.velocity[0] * 0.5, 0]
                            self.grounded = True
                self._update_rect()

        # 走路音效
        if self.grounded and abs(self.velocity[0]) > 2:
            self.run_sound_timer -= dt
            if self.run_sound_timer <= 0:
                _play("run", 0.15)
                self.run_sound_timer = 0.35
        else:
            self.run_sound_timer = 0

    def jump(self):
        if self.grounded:
            self.velocity[1] = C.JUMP_VELOCITY
            self.grounded = False
            _play("jump", 0.3)

    def use_item(self, world, mouse_tile, terrain_surface, dt):
        """根据手持物品执行操作，dt 用于挖掘进度"""
        slot = self.hotbar[self.hotbar_index]
        if slot is None:
            return

        item_id = slot["item_id"]
        item = C.ITEMS[item_id]
        tx, ty = mouse_tile

        if item["is_pickaxe"]:
            self._mine_block(world, tx, ty, terrain_surface, dt)
        elif item["is_sword"]:
            if self.use_cooldown <= 0:
                self._swing_sword()
        elif item["is_block"]:
            if self.use_cooldown <= 0:
                self._place_block(world, tx, ty, item["place_tile"], terrain_surface)

    def _mine_block(self, world, tx, ty, terrain_surface, dt):
        if not tile_in_map(world, tx, ty):
            return
        dx = tx - self.block_x
        dy = ty - self.block_y
        if math.sqrt(dx * dx + dy * dy) > C.PLAYER_REACH:
            return

        tile_id = world.tile_data[tx][ty]
        if tile_id == C.AIR:
            self.mining_target = None
            self.mining_progress = 0
            return

        # 如果换了目标方块，重置进度
        if self.mining_target != (tx, ty):
            self.mining_target = (tx, ty)
            self.mining_progress = 0

        # 累积挖掘进度
        self.mining_progress += dt / self.mining_time
        self.swinging = True
        self.swing_timer = self.swing_duration
        self.swing_progress = min(1.0, self.mining_progress)

        # 挖掘中播放音效（每隔一段时间）
        if int(self.mining_progress * 5) != int((self.mining_progress - dt / self.mining_time) * 5):
            _play("dig", 0.3)

        # 挖掘完成
        if self.mining_progress >= 1.0:
            tile_info = C.TILES[tile_id]
            drop_item_id = tile_info["drop_item"]

            world.tile_data[tx][ty] = C.AIR
            update_tile(terrain_surface, world, tx, ty)

            if drop_item_id is not None:
                self._add_item(drop_item_id, 1)

            _play("tink", 0.4)
            self.mining_target = None
            self.mining_progress = 0
            self.use_cooldown = 0.1

    def _place_block(self, world, tx, ty, place_tile, terrain_surface):
        if not tile_in_map(world, tx, ty):
            return
        dx = tx - self.block_x
        dy = ty - self.block_y
        if math.sqrt(dx * dx + dy * dy) > C.PLAYER_REACH:
            return
        if world.tile_data[tx][ty] != C.AIR:
            return
        if get_neighbor_count(world, tx, ty) == 0:
            return

        block_rect = Rect(tx * C.BLOCKSIZE, ty * C.BLOCKSIZE + 1, C.BLOCKSIZE, C.BLOCKSIZE)
        if block_rect.colliderect(self.rect):
            return

        world.tile_data[tx][ty] = place_tile
        update_tile(terrain_surface, world, tx, ty)

        slot = self.hotbar[self.hotbar_index]
        slot["count"] -= 1
        if slot["count"] <= 0:
            self.hotbar[self.hotbar_index] = None

        self.use_cooldown = C.PLACE_COOLDOWN
        self.swinging = True
        self.swing_timer = self.swing_duration
        _play("tink", 0.25)

    def _swing_sword(self):
        self.swinging = True
        self.swing_timer = self.swing_duration
        self.swing_progress = 0.0
        self.use_cooldown = C.ATTACK_COOLDOWN
        _play("swing", 0.4)

    def _add_item(self, item_id, count):
        for i, slot in enumerate(self.hotbar):
            if slot is not None and slot["item_id"] == item_id:
                item_info = C.ITEMS[item_id]
                if slot["count"] < item_info["max_stack"]:
                    can_add = min(count, item_info["max_stack"] - slot["count"])
                    slot["count"] += can_add
                    count -= can_add
                    if count <= 0:
                        return
        for i, slot in enumerate(self.hotbar):
            if slot is None:
                self.hotbar[i] = {"item_id": item_id, "count": count}
                return

    def draw(self, screen, cam_x, cam_y):
        sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5
        sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5

        try:
            from assets import torso_frames, hair_frames
            if torso_frames:
                self._draw_with_sprites(screen, sx, sy, torso_frames, hair_frames)
                return
        except Exception:
            pass
        self._draw_fallback(screen, sx, sy)

    def _draw_with_sprites(self, screen, sx, sy, torso_frames, hair_frames):
        # 身体帧选择
        if self.direction == 1:
            row = 0 if self.grounded else 2
        else:
            row = 1 if self.grounded else 3

        if abs(self.velocity[0]) > 1 and self.grounded:
            anim_frame = int(pygame.time.get_ticks() / 150) % 4 + 1
        else:
            anim_frame = 0

        frame_index = row * 19 + min(anim_frame, 18)
        if frame_index < len(torso_frames):
            torso_surf = torso_frames[frame_index]
            tw, th = torso_surf.get_size()
            if self.direction == -1:
                torso_surf = pygame.transform.flip(torso_surf, True, False)
            # 匹配原项目偏移：身体中心偏上
            screen.blit(torso_surf, (sx - tw * 0.5, sy - th * 0.5))

        # 头发
        if len(hair_frames) > 0:
            hair_surf = hair_frames[0]
            hw, hh = hair_surf.get_size()
            if self.direction == -1:
                hair_surf = pygame.transform.flip(hair_surf, True, False)
            screen.blit(hair_surf, (sx - hw * 0.5, sy - C.PLAYER_HEIGHT * 0.5 - hh + 4))

        # 手持物品挥动动画（参考原项目的弧形旋转）
        self._draw_held_item(screen, sx, sy)

    def _draw_held_item(self, screen, sx, sy):
        """绘制手持物品，挥动时弧形旋转"""
        slot = self.hotbar[self.hotbar_index]
        if slot is None:
            return

        item_id = slot["item_id"]
        try:
            from assets import get_item_surface
            item_surf = get_item_surface(item_id)
        except Exception:
            return
        if item_surf is None:
            return

        # 放大到手持大小
        item_size = 24
        item_surf = pygame.transform.scale(item_surf.copy(), (item_size, item_size))

        if self.swinging:
            # 弧形挥动动画（参考原项目）
            progress = self.swing_progress
            # ease-out 曲线
            eased = 1.0 - (1.0 - progress) ** 2

            if self.direction == 1:
                swing_angle = -eased * 175 + 85
                hand_angle_deg = -130 + eased * 175
            else:
                swing_angle = eased * 175 + 5
                hand_angle_deg = 130 - eased * 175
                item_surf = pygame.transform.flip(item_surf, True, False)

            rotated = pygame.transform.rotate(item_surf, swing_angle)
            hand_angle_rad = hand_angle_deg * (math.pi / 180)
            arm_len = 20
            ox = math.cos(hand_angle_rad) * arm_len - rotated.get_width() * 0.5
            oy = math.sin(hand_angle_rad) * arm_len - rotated.get_height() * 0.5
            screen.blit(rotated, (sx + ox, sy + oy))
        else:
            # 静止时显示在身体侧边
            if self.direction == -1:
                item_surf = pygame.transform.flip(item_surf, True, False)
            screen.blit(item_surf, (sx + self.direction * 12 - item_surf.get_width() * 0.5,
                                     sy - 10 - item_surf.get_height() * 0.5))

    def _draw_fallback(self, screen, sx, sy):
        body_w = C.PLAYER_WIDTH
        body_h = C.PLAYER_HEIGHT
        pygame.draw.rect(screen, (70, 130, 180),
                         (sx - body_w * 0.5, sy - body_h * 0.5, body_w, body_h * 0.6))
        pygame.draw.rect(screen, (100, 70, 50),
                         (sx - body_w * 0.5, sy - body_h * 0.5 + body_h * 0.6, body_w, body_h * 0.4))
        self._draw_held_item(screen, sx, sy)

    def draw_mining_progress(self, screen, cam_x, cam_y):
        """绘制挖掘进度条"""
        if self.mining_target is None or self.mining_progress <= 0:
            return
        tx, ty = self.mining_target
        sx = tx * C.BLOCKSIZE - cam_x + C.WINDOW_WIDTH * 0.5
        sy = ty * C.BLOCKSIZE - cam_y + C.WINDOW_HEIGHT * 0.5

        # 背景
        bar_w = C.BLOCKSIZE
        bar_h = 3
        pygame.draw.rect(screen, (60, 60, 60), (sx, sy - 6, bar_w, bar_h))
        # 进度
        pw = int(bar_w * min(1.0, self.mining_progress))
        pygame.draw.rect(screen, (255, 255, 0), (sx, sy - 6, pw, bar_h))


def _play(name, volume=0.4):
    try:
        from assets import play_sound
        play_sound(name, volume)
    except Exception:
        pass


from world import tile_in_map, get_neighbor_count, update_tile

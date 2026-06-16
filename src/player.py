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
        self.invuln_timer = 0.0  # 受伤后无敌帧

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

        # 物品栏（ESC 打开时显示）
        self.inventory = [None] * 32  # 4行 × 8列

        # 攻击/使用状态
        self.use_cooldown = 0.0
        self.swinging = False
        self.swing_timer = 0.0
        self.swing_duration = 0.3
        self.swing_progress = 0.0

        # 动画状态（照搬原项目）
        self.animation_frame = 0  # 身体动画帧
        self.animation_tick = 0.0
        self.animation_speed = 0.025
        self.arm_animation_frame = 0
        self.arm_animation_tick = 0.0
        self.arm_animation_speed = 0.015
        self.swinging_arm = False

        # 挖掘状态
        self.mining_target = None  # (tx, ty) 正在挖的方块
        self.mining_progress = 0.0  # 0->1 挖掘进度
        self.mining_time = 0.1  # 挖一个方块需要的秒数

        # 走路音效
        self.run_sound_timer = 0.0

        # 待生成的掉落物（game.py 读取后清空，用于把挖掘产出变成实体掉落）
        self.pending_drops = []

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
        if self.invuln_timer > 0:
            self.invuln_timer -= dt
        if self.swinging:
            self.swing_timer -= dt
            self.swing_progress = 1.0 - max(0, self.swing_timer) / self.swing_duration
            if self.swing_timer <= 0:
                self.swinging = False
                self.swinging_arm = False
                self.swing_progress = 0.0

        # 动画更新（照搬原项目 animate 逻辑）
        self.animation_tick -= dt
        if self.animation_tick <= 0:
            self.animation_tick += self.animation_speed
            if self.grounded:
                if self.moving_left:
                    if self.animation_frame < 29:
                        self.animation_frame += 1
                    else:
                        self.animation_frame = 17
                elif self.moving_right:
                    if self.animation_frame < 14:
                        self.animation_frame += 1
                    else:
                        self.animation_frame = 2
                else:
                    if self.direction == -1:
                        self.animation_frame = 15
                    else:
                        self.animation_frame = 0
            else:
                if self.direction == -1:
                    self.animation_frame = 16
                else:
                    self.animation_frame = 1

        # 手臂动画
        if self.swinging_arm:
            self.arm_animation_tick -= dt
            if self.arm_animation_tick <= 0:
                self.arm_animation_tick += self.arm_animation_speed
                if self.direction == 1:
                    self.arm_animation_frame += 1
                    if self.arm_animation_frame > 19:
                        self.arm_animation_frame = 1
                else:
                    self.arm_animation_frame += 1
                    if self.arm_animation_frame > 39:
                        self.arm_animation_frame = 21

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

    def damage(self, amount, source_x=None, knockback=C.BOSS_CONTACT_KNOCK):
        """受到伤害；处于无敌帧则忽略。source_x 用于计算击退方向。"""
        if not self.alive or self.invuln_timer > 0:
            return
        self.hp -= amount
        self.invuln_timer = C.PLAYER_INVULN
        if source_x is not None:
            kb_dir = 1 if self.position[0] >= source_x else -1
            self.velocity[0] = kb_dir * knockback
            self.velocity[1] = -22
        _play("player_hit", 0.45)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            _play("player_killed", 0.5)

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
        elif item.get("is_gun"):
            return  # 枪在 game.py 中处理（需要鼠标方向）
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
                # 产出实体掉落物（由 game.py 读取 pending_drops 生成 Drop）
                self.pending_drops.append({
                    "item_id": drop_item_id,
                    "count": 1,
                    "pos": (tx * C.BLOCKSIZE + C.BLOCKSIZE * 0.5,
                            ty * C.BLOCKSIZE + C.BLOCKSIZE * 0.5),
                })

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
        self.swinging_arm = True
        self.swing_timer = self.swing_duration
        self.swing_progress = 0.0
        self.use_cooldown = C.ATTACK_COOLDOWN
        if self.direction == 1:
            self.arm_animation_frame = 1
        else:
            self.arm_animation_frame = 21
        _play("swing", 0.4)

    def _add_item(self, item_id, count):
        """添加物品，优先快捷栏，溢出进入物品栏"""
        remaining = self._add_to_list(self.hotbar, item_id, count)
        if remaining > 0:
            self._add_to_list(self.inventory, item_id, remaining)

    def _add_to_list(self, item_list, item_id, count):
        """向指定列表添加物品，返回剩余数量"""
        item_info = C.ITEMS[item_id]
        # 先尝试堆叠
        for slot in item_list:
            if slot is not None and slot["item_id"] == item_id:
                if slot["count"] < item_info["max_stack"]:
                    can_add = min(count, item_info["max_stack"] - slot["count"])
                    slot["count"] += can_add
                    count -= can_add
                    if count <= 0:
                        return 0
        # 填充空槽
        for i, slot in enumerate(item_list):
            if slot is None:
                add_count = min(count, item_info["max_stack"])
                item_list[i] = {"item_id": item_id, "count": add_count}
                count -= add_count
                if count <= 0:
                    return 0
        return count

    def add_item(self, item_id, count):
        """公开接口：添加物品"""
        self._add_item(item_id, count)

    def add_item_returning(self, item_id, count):
        """添加物品，返回未能装入的剩余数量（库存满时 > 0）"""
        remaining = self._add_to_list(self.hotbar, item_id, count)
        if remaining > 0:
            remaining = self._add_to_list(self.inventory, item_id, remaining)
        return remaining

    def find_ammo(self, ammo_name):
        """在快捷栏中查找指定弹药，返回 (slot_index, count) 或 None"""
        for i, slot in enumerate(self.hotbar):
            if slot is not None and C.ITEMS[slot["item_id"]]["name"] == ammo_name:
                return (i, slot["count"])
        return None

    def consume_ammo(self, slot_index):
        """消耗指定槽位的弹药 1 个"""
        slot = self.hotbar[slot_index]
        if slot and slot["count"] > 1:
            slot["count"] -= 1
        elif slot:
            self.hotbar[slot_index] = None

    def draw(self, screen, cam_x, cam_y):
        """照搬原项目 draw() 逻辑"""
        # 受伤无敌帧闪烁
        if self.alive and self.invuln_timer > 0 and int(self.invuln_timer * 12) % 2 == 0:
            return
        sx = self.position[0] - cam_x + C.WINDOW_WIDTH * 0.5
        sy = self.position[1] - cam_y + C.WINDOW_HEIGHT * 0.5

        try:
            from assets import player_sprites, player_arm_sprites, get_item_world_surface, rotate_surface
            if not player_sprites:
                self._draw_fallback(screen, sx, sy)
                return

            # 绘制身体（偏移跟原项目一致：-20, -33）
            if self.animation_frame < len(player_sprites):
                screen.blit(player_sprites[self.animation_frame], (sx - 20, sy - 33))

            # 绘制手持物品（在手臂之前，只在挥动时显示）
            if self.swinging:
                self._draw_held_item_v2(screen, sx, sy, get_item_world_surface, rotate_surface)

            # 绘制手臂
            if self.arm_animation_frame < len(player_arm_sprites):
                screen.blit(player_arm_sprites[self.arm_animation_frame], (sx - 20, sy - 33))
        except Exception:
            self._draw_fallback(screen, sx, sy)

    def _draw_held_item_v2(self, screen, sx, sy, get_item_world_surface, rotate_surface):
        """手持物品渲染 - 照搬原项目 item_swing 逻辑"""
        slot = self.hotbar[self.hotbar_index]
        if slot is None:
            return

        item_id = slot["item_id"]
        item_surf = get_item_world_surface(item_id)
        if item_surf is None:
            return

        if self.swinging:
            # ease-out 挥动
            progress = self.swing_progress
            eased = math.sin(progress * math.pi * 0.5)  # ease_out_zero_to_one
            less_eased = progress + (eased - progress) * 0.7

            if self.direction == 1:
                swing_angle = -less_eased * 175 + 85
            else:
                swing_angle = less_eased * 175 + 5

            rotated = rotate_surface(item_surf, swing_angle)
            arm_len = 20

            if self.direction == 1:
                hand_angle_deg = -130 + less_eased * 175
                hand_angle_rad = hand_angle_deg * (math.pi / 180)
                ox = math.cos(hand_angle_rad) * arm_len - rotated.get_width() * 0.5 - 5
                oy = math.sin(hand_angle_rad) * arm_len - rotated.get_height() * 0.5 + 2
            else:
                hand_angle_deg = 130 - less_eased * 175
                hand_angle_rad = hand_angle_deg * (math.pi / 180)
                ox = -math.cos(hand_angle_rad) * arm_len - rotated.get_width() * 0.5 + 5
                oy = -math.sin(hand_angle_rad) * arm_len - rotated.get_height() * 0.5 + 2

            screen.blit(rotated, (sx + ox, sy + oy))
        else:
            # 静止时手臂前伸
            if self.direction == -1:
                item_surf = pygame.transform.flip(item_surf, True, False)
            offset_x = -10 if self.direction == 1 else 10
            screen.blit(item_surf, (sx + offset_x - item_surf.get_width() * 0.5,
                                     sy - item_surf.get_height() * 0.5))

    def _draw_fallback(self, screen, sx, sy):
        body_w = C.PLAYER_WIDTH
        body_h = C.PLAYER_HEIGHT
        pygame.draw.rect(screen, (70, 130, 180),
                         (sx - body_w * 0.5, sy - body_h * 0.5, body_w, body_h * 0.6))
        pygame.draw.rect(screen, (100, 70, 50),
                         (sx - body_w * 0.5, sy - body_h * 0.5 + body_h * 0.6, body_w, body_h * 0.4))

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

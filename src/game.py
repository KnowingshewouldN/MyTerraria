# game.py - 主菜单、游戏循环、摄像机、输入处理、渲染管线
import pygame
import math
import random
import time
import constants as C
from pygame.locals import *
from world import World, generate_terrain, create_terrain_surface, tile_in_map
from player import Player
from slime import Slime


def run_menu(screen):
    """主菜单界面"""
    import assets
    assets.init()

    clock = pygame.time.Clock()
    font_title = assets.font_large if assets.font_large else pygame.font.Font(None, 60)
    font_default = assets.font_default if assets.font_default else pygame.font.Font(None, 36)

    # 播放主菜单音乐
    assets.play_music("Re-Logic - The Journey Begins.mp3", 0.5, -1)

    # Play 按钮
    button_w, button_h = 200, 50
    button_x = C.WINDOW_WIDTH * 0.5 - button_w * 0.5
    button_y = C.WINDOW_HEIGHT * 0.55
    button_rect = pygame.Rect(button_x, button_y, button_w, button_h)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        hover = button_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                return False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit()
                    return False
                elif event.key == K_RETURN:
                    return True
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1 and hover:
                    return True

        # 绘制
        screen.fill((20, 20, 60))

        # 标题
        title_surf = font_title.render("Terraria", True, (255, 255, 255))
        screen.blit(title_surf, (C.WINDOW_WIDTH * 0.5 - title_surf.get_width() * 0.5,
                                  C.WINDOW_HEIGHT * 0.25 - title_surf.get_height() * 0.5))

        # 副标题
        sub_surf = font_default.render("MyTerraria", True, (180, 180, 180))
        screen.blit(sub_surf, (C.WINDOW_WIDTH * 0.5 - sub_surf.get_width() * 0.5,
                                C.WINDOW_HEIGHT * 0.35))

        # Play 按钮
        btn_color = (80, 180, 80) if hover else (50, 130, 50)
        pygame.draw.rect(screen, btn_color, button_rect, border_radius=8)
        pygame.draw.rect(screen, (200, 255, 200), button_rect, 2, border_radius=8)
        play_text = font_default.render("Play", True, (255, 255, 255))
        screen.blit(play_text, (button_rect.centerx - play_text.get_width() * 0.5,
                                 button_rect.centery - play_text.get_height() * 0.5))

        pygame.display.flip()
        clock.tick(C.FPS)

    return False


def run(screen):
    """主游戏函数"""
    import assets

    clock = pygame.time.Clock()
    font = assets.font_default if assets.font_default else pygame.font.Font(None, 24)
    small_font = assets.font_small if assets.font_small else pygame.font.Font(None, 18)

    # 停止菜单音乐，等 3 秒后播放游戏音乐
    assets.stop_music()
    music_start_time = time.time() + 3.0
    music_started = False

    # 创建世界
    print("Generating world...")
    world = World()
    generate_terrain(world)
    print("Creating terrain surface...")
    terrain_surface = create_terrain_surface(world)
    print("World ready!")

    # 创建玩家
    player = Player(world.spawn_position)

    # 弹射体
    projectiles = []

    # 史莱姆管理
    slimes = []
    slime_spawn_timer = 3.0  # 首次 3 秒后生成
    max_slimes = 5

    # 摄像机
    cam_x = player.position[0]
    cam_y = player.position[1]

    old_ticks = pygame.time.get_ticks()
    game_time = 0.0  # 昼夜计时器
    running = True

    while running:
        # Delta time
        current_ticks = pygame.time.get_ticks()
        dt = (current_ticks - old_ticks) * 0.001
        if dt > 0.033:
            dt = 0.033
        old_ticks = current_ticks
        game_time += dt

        # 音乐延迟播放
        if not music_started and time.time() >= music_start_time:
            assets.play_music("Scott Lloyd Shelly - Overworld Day.mp3", 0.5, -1)
            music_started = True

        # 鼠标位置 -> 世界方块坐标
        mouse_pos = pygame.mouse.get_pos()
        mouse_world_x = cam_x + mouse_pos[0] - C.WINDOW_WIDTH * 0.5
        mouse_world_y = cam_y + mouse_pos[1] - C.WINDOW_HEIGHT * 0.5
        mouse_tile = (int(mouse_world_x // C.BLOCKSIZE), int(mouse_world_y // C.BLOCKSIZE))

        # 事件处理
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            elif event.type == KEYDOWN:
                if event.key == K_a:
                    player.moving_left = True
                elif event.key == K_d:
                    player.moving_right = True
                elif event.key == K_SPACE:
                    player.jump()
                elif event.key == K_s:
                    player.moving_down = True
                elif event.key == K_ESCAPE:
                    running = False
                elif event.key in (K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8):
                    player.hotbar_index = event.key - K_1

            elif event.type == KEYUP:
                if event.key == K_a:
                    player.moving_left = False
                elif event.key == K_d:
                    player.moving_right = False
                elif event.key == K_s:
                    player.moving_down = False

            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 4:  # 滚轮上
                    player.hotbar_index = (player.hotbar_index - 1) % C.HOTBAR_SIZE
                elif event.button == 5:  # 滚轮下
                    player.hotbar_index = (player.hotbar_index + 1) % C.HOTBAR_SIZE

        # 鼠标持续按下：持续使用物品（传递 dt 用于挖掘进度）
        if pygame.mouse.get_pressed()[0]:
            slot = player.hotbar[player.hotbar_index]
            if slot is not None:
                item = C.ITEMS[slot["item_id"]]
                if item.get("is_gun") and player.use_cooldown <= 0:
                    _shoot_gun(player, projectiles, mouse_world_x, mouse_world_y)
                else:
                    player.use_item(world, mouse_tile, terrain_surface, dt)
            else:
                player.use_item(world, mouse_tile, terrain_surface, dt)
        else:
            # 松开鼠标重置挖掘进度
            player.mining_target = None
            player.mining_progress = 0

        # 挥剑攻击史莱姆
        if player.swinging and player.use_cooldown > 0:
            slot = player.hotbar[player.hotbar_index]
            if slot is not None:
                item = C.ITEMS[slot["item_id"]]
                if item["is_sword"]:
                    _sword_hit_slimes(player, slimes)

        # 更新玩家
        player.update(world, dt)

        # 史莱姆生成
        slime_spawn_timer -= dt
        if slime_spawn_timer <= 0 and len(slimes) < max_slimes:
            slime_spawn_timer = 5.0 + random.random() * 5.0
            _spawn_slime(slimes, player, world)

        # 更新史莱姆
        player_pos = player.position
        for slime in slimes:
            slime.update(world, player_pos, dt)
            # 拾取掉落物
            if slime.drop_queue:
                for drop in slime.drop_queue:
                    player.add_item(drop["item_id"], drop["count"])
                slime.drop_queue = []
        slimes = [s for s in slimes if s.alive]

        # 更新弹射体
        for proj in projectiles:
            proj["x"] += proj["vx"] * dt
            proj["y"] += proj["vy"] * dt
            proj["life"] -= dt
            # 碰撞检测：方块
            tx = int(proj["x"] // C.BLOCKSIZE)
            ty = int(proj["y"] // C.BLOCKSIZE)
            if tile_in_map(world, tx, ty) and world.tile_data[tx][ty] != C.AIR:
                tile_info = C.TILES.get(world.tile_data[tx][ty])
                if tile_info and tile_info["solid"]:
                    proj["alive"] = False
            # 碰撞检测：史莱姆
            for slime in slimes:
                if not slime.alive or slime.dying:
                    continue
                proj_rect = pygame.Rect(proj["x"] - 3, proj["y"] - 3, 6, 6)
                if proj_rect.colliderect(slime.rect):
                    kb_dir = 1 if slime.position[0] > player.position[0] else -1
                    slime.damage(proj["damage"], source_velocity=(kb_dir * 80, -40))
                    proj["alive"] = False
                    break
            if proj["life"] <= 0:
                proj["alive"] = False
        projectiles = [p for p in projectiles if p["alive"]]

        # 更新摄像机（跟随玩家）
        cam_x = player.position[0]
        cam_y = player.position[1]

        # 摄像机边界
        half_w = C.WINDOW_WIDTH * 0.5
        half_h = C.WINDOW_HEIGHT * 0.5
        cam_x = max(half_w, min(cam_x, world.width * C.BLOCKSIZE - half_w))
        cam_y = max(half_h, min(cam_y, world.height * C.BLOCKSIZE - half_h))

        # ===== 渲染 =====
        sky_color = C.get_sky_color(game_time)
        screen.fill(sky_color)

        # 地形
        terrain_offset_x = C.WINDOW_WIDTH * 0.5 - cam_x
        terrain_offset_y = C.WINDOW_HEIGHT * 0.5 - cam_y
        screen.blit(terrain_surface, (terrain_offset_x, terrain_offset_y))

        # 灯光发光效果
        _draw_lamp_glow(screen, world, cam_x, cam_y, sky_color)

        # 弹射体
        for proj in projectiles:
            px = proj["x"] - cam_x + C.WINDOW_WIDTH * 0.5
            py = proj["y"] - cam_y + C.WINDOW_HEIGHT * 0.5
            pygame.draw.circle(screen, (255, 255, 100), (int(px), int(py)), 3)

        # 方块高亮（鼠标悬停）
        if tile_in_map(world, mouse_tile[0], mouse_tile[1]):
            hl_x = mouse_tile[0] * C.BLOCKSIZE + terrain_offset_x
            hl_y = mouse_tile[1] * C.BLOCKSIZE + terrain_offset_y
            # 距离检查 - 只有在范围内的才高亮
            dx = mouse_tile[0] - player.block_x
            dy = mouse_tile[1] - player.block_y
            if math.sqrt(dx * dx + dy * dy) <= C.PLAYER_REACH:
                pygame.draw.rect(screen, (255, 255, 255, 128),
                                 (hl_x, hl_y, C.BLOCKSIZE, C.BLOCKSIZE), 1)
            else:
                pygame.draw.rect(screen, (100, 100, 100),
                                 (hl_x, hl_y, C.BLOCKSIZE, C.BLOCKSIZE), 1)

        # 史莱姆
        for slime in slimes:
            slime.draw(screen, cam_x, cam_y)

        # 玩家
        player.draw(screen, cam_x, cam_y)

        # 挖掘进度条
        player.draw_mining_progress(screen, cam_x, cam_y)

        # ===== UI =====
        draw_hotbar(screen, player, font)
        draw_health_bar(screen, player, font)

        # FPS
        fps_text = small_font.render(f"FPS: {int(clock.get_fps())}", True, (255, 255, 255))
        screen.blit(fps_text, (5, 5))

        # 坐标信息 + 昼夜指示
        is_night = (game_time % C.DAY_NIGHT_CYCLE) > C.DAY_DURATION
        time_phase = (game_time % C.DAY_NIGHT_CYCLE) / C.DAY_NIGHT_CYCLE
        time_label = "Night" if is_night else "Day"
        coord_text = small_font.render(
            f"Pos: ({player.block_x}, {player.block_y})  Slimes: {len(slimes)}  {time_label}", True, (255, 255, 255))
        screen.blit(coord_text, (5, 22))

        pygame.display.flip()
        clock.tick(C.FPS)

    assets.stop_music()
    pygame.quit()


def _spawn_slime(slimes, player, world):
    """在玩家附近生成史莱姆"""
    # 在玩家左右 20-40 格范围、同一高度附近生成
    side = random.choice([-1, 1])
    dist = random.randint(20, 40)
    spawn_x = player.position[0] + side * dist * C.BLOCKSIZE

    # 从上往下找地面
    bx = int(spawn_x // C.BLOCKSIZE)
    by = 0
    for y in range(world.height):
        if 0 <= bx < world.width and world.tile_data[bx][y] != C.AIR:
            by = y
            break

    spawn_y = by * C.BLOCKSIZE - C.BLOCKSIZE
    if spawn_y <= 0:
        return

    slime_type = random.randint(0, min(4, 2))  # 0-2 类型（绿/蓝/红）
    slimes.append(Slime((spawn_x, spawn_y), slime_type))


def _sword_hit_slimes(player, slimes):
    """检测挥剑是否击中史莱姆"""
    if not player.swinging:
        return
    slot = player.hotbar[player.hotbar_index]
    if slot is None:
        return
    item = C.ITEMS[slot["item_id"]]
    if not item["is_sword"]:
        return

    # 挥剑判定：玩家前方一定范围内的矩形
    reach_px = C.PLAYER_REACH * C.BLOCKSIZE * 0.5
    if player.direction == 1:
        hit_x = player.position[0] + C.PLAYER_WIDTH * 0.5
        hit_rect = pygame.Rect(hit_x, player.position[1] - C.PLAYER_HEIGHT * 0.5,
                                reach_px, C.PLAYER_HEIGHT)
    else:
        hit_rect = pygame.Rect(player.position[0] - C.PLAYER_WIDTH * 0.5 - reach_px,
                                player.position[1] - C.PLAYER_HEIGHT * 0.5,
                                reach_px, C.PLAYER_HEIGHT)

    for slime in slimes:
        if not slime.alive:
            continue
        if hit_rect.colliderect(slime.rect):
            # 击退
            kb_dir = 1 if slime.position[0] > player.position[0] else -1
            kb_vel = (kb_dir * 80, -60)
            slime.velocity[0] = kb_dir * 15
            slime.velocity[1] = -20
            slime.damage(item["damage"], source_velocity=kb_vel)


def draw_hotbar(screen, player, font):
    """绘制快捷栏"""
    import assets

    slot_size = 44
    padding = 4
    start_x = C.WINDOW_WIDTH * 0.5 - (C.HOTBAR_SIZE * (slot_size + padding)) * 0.5
    start_y = C.WINDOW_HEIGHT - slot_size - 10

    for i in range(C.HOTBAR_SIZE):
        x = int(start_x + i * (slot_size + padding))
        y = int(start_y)

        # 尝试使用 GUI 精灵
        if i == player.hotbar_index and assets.get_gui_selected_slot_surface():
            screen.blit(assets.get_gui_selected_slot_surface(), (x - 2, y - 2))
        elif assets.get_gui_slot_surface():
            screen.blit(assets.get_gui_slot_surface(), (x - 2, y - 2))
        else:
            # 备用矩形
            bg_color = (60, 60, 60) if i != player.hotbar_index else (90, 90, 90)
            pygame.draw.rect(screen, bg_color, (x, y, slot_size, slot_size))
            border_color = C.SLOT_SELECTED_COLOR if i == player.hotbar_index else C.SLOT_BORDER_COLOR
            border_width = 2 if i == player.hotbar_index else 1
            pygame.draw.rect(screen, border_color, (x, y, slot_size, slot_size), border_width)

        # 物品图标
        slot = player.hotbar[i]
        if slot is not None:
            icon = C.get_item_icon(slot["item_id"], size=slot_size - 8)
            if icon:
                icon_x = x + (slot_size - icon.get_width()) * 0.5
                icon_y = y + (slot_size - icon.get_height()) * 0.5
                screen.blit(icon, (icon_x, icon_y))
            if slot["count"] > 1:
                count_text = font.render(str(slot["count"]), True, (255, 255, 255))
                screen.blit(count_text, (x + slot_size - count_text.get_width() - 2,
                                         y + slot_size - count_text.get_height() - 1))


def draw_health_bar(screen, player, font):
    """绘制血条"""
    bar_width = 200
    bar_height = 20
    x = C.WINDOW_WIDTH - bar_width - 10
    y = 10

    # 背景
    pygame.draw.rect(screen, C.HEALTH_BAR_BG, (x, y, bar_width, bar_height))

    # 血量
    hp_ratio = max(0, player.hp / player.max_hp)
    hp_width = int(bar_width * hp_ratio)
    hp_color = (220, 30, 30) if hp_ratio < 0.3 else (50, 200, 50)
    pygame.draw.rect(screen, hp_color, (x, y, hp_width, bar_height))

    # 边框
    pygame.draw.rect(screen, (200, 200, 200), (x, y, bar_width, bar_height), 1)

    # 数字
    hp_text = font.render(f"{player.hp}/{player.max_hp}", True, (255, 255, 255))
    screen.blit(hp_text, (x + bar_width * 0.5 - hp_text.get_width() * 0.5,
                           y + bar_height * 0.5 - hp_text.get_height() * 0.5))


def _shoot_gun(player, projectiles, mouse_world_x, mouse_world_y):
    """发射枪弹"""
    # 查找弹药
    ammo_slot = player.find_ammo("Musket Ball")
    if ammo_slot is None:
        return
    slot_idx, _ = ammo_slot

    # 计算方向
    dx = mouse_world_x - player.position[0]
    dy = mouse_world_y - player.position[1]
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1:
        return
    speed = 600
    vx = dx / dist * speed
    vy = dy / dist * speed

    gun_damage = C.ITEMS[player.hotbar[player.hotbar_index]["item_id"]]["damage"]
    ammo_damage = C.ITEMS[player.hotbar[slot_idx]["item_id"]]["damage"]

    projectiles.append({
        "x": player.position[0] + dx / dist * 20,
        "y": player.position[1] + dy / dist * 20,
        "vx": vx, "vy": vy,
        "damage": gun_damage + ammo_damage,
        "alive": True,
        "life": 2.0,
    })

    player.consume_ammo(slot_idx)
    player.use_cooldown = 0.5
    player.swinging = True
    player.swing_timer = 0.15
    player.swing_duration = 0.15
    player.swing_progress = 0.0

    try:
        from assets import play_sound
        play_sound("swing", 0.4)  # 临时用 swing 音效
    except Exception:
        pass


def _draw_lamp_glow(screen, world, cam_x, cam_y, sky_color):
    """绘制灯光发光效果"""
    # 只在较暗时绘制（非白天或天空不够亮时）
    brightness = (sky_color[0] + sky_color[1] + sky_color[2]) / 3
    if brightness > 180:
        return  # 白天不需要灯光

    # 计算可见区域
    half_w = C.WINDOW_WIDTH * 0.5
    half_h = C.WINDOW_HEIGHT * 0.5
    min_tx = max(0, int((cam_x - half_w) // C.BLOCKSIZE) - 5)
    max_tx = min(world.width, int((cam_x + half_w) // C.BLOCKSIZE) + 5)
    min_ty = max(0, int((cam_y - half_h) // C.BLOCKSIZE) - 5)
    max_ty = min(world.height, int((cam_y + half_h) // C.BLOCKSIZE) + 5)

    glow_radius = 60
    glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)

    for tx in range(min_tx, max_tx):
        for ty in range(min_ty, max_ty):
            if world.tile_data[tx][ty] == 15:  # Lamp
                px = tx * C.BLOCKSIZE + C.BLOCKSIZE * 0.5 - cam_x + half_w
                py = ty * C.BLOCKSIZE + C.BLOCKSIZE * 0.5 - cam_y + half_h
                glow_surf.fill((0, 0, 0, 0))
                alpha = max(30, int(160 * (1 - brightness / 180)))
                pygame.draw.circle(glow_surf, (255, 240, 180, alpha),
                                   (glow_radius, glow_radius), glow_radius)
                screen.blit(glow_surf, (px - glow_radius, py - glow_radius),
                            special_flags=pygame.BLEND_RGB_ADD)

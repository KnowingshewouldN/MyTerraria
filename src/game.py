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

        title_surf = font_title.render("Terraria", True, (255, 255, 255))
        screen.blit(title_surf, (C.WINDOW_WIDTH * 0.5 - title_surf.get_width() * 0.5,
                                  C.WINDOW_HEIGHT * 0.25 - title_surf.get_height() * 0.5))

        sub_surf = font_default.render("MyTerraria", True, (180, 180, 180))
        screen.blit(sub_surf, (C.WINDOW_WIDTH * 0.5 - sub_surf.get_width() * 0.5,
                                C.WINDOW_HEIGHT * 0.35))

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
    slime_spawn_timer = 3.0
    max_slimes = 5

    # 摄像机
    cam_x = player.position[0]
    cam_y = player.position[1]

    old_ticks = pygame.time.get_ticks()
    game_time = 0.0
    inventory_open = False
    running = True

    # Quit 按钮位置（固定）
    quit_rect = pygame.Rect(0, 0, 120, 36)
    quit_rect.centerx = int(C.WINDOW_WIDTH * 0.5)
    quit_rect.y = int(C.WINDOW_HEIGHT * 0.5 + 380 * 0.5 - 36 - 15)

    while running:
        # Delta time
        current_ticks = pygame.time.get_ticks()
        dt = (current_ticks - old_ticks) * 0.001
        if dt > 0.033:
            dt = 0.033
        old_ticks = current_ticks

        if not inventory_open:
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

        # ===== 事件处理 =====
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    inventory_open = not inventory_open
                elif not inventory_open:
                    if event.key == K_a:
                        player.moving_left = True
                    elif event.key == K_d:
                        player.moving_right = True
                    elif event.key == K_SPACE:
                        player.jump()
                    elif event.key == K_s:
                        player.moving_down = True
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
                if inventory_open:
                    if event.button == 1 and quit_rect.collidepoint(mouse_pos):
                        running = False
                else:
                    if event.button == 4:
                        player.hotbar_index = (player.hotbar_index - 1) % C.HOTBAR_SIZE
                    elif event.button == 5:
                        player.hotbar_index = (player.hotbar_index + 1) % C.HOTBAR_SIZE

        # ===== 游戏逻辑（暂停时跳过）=====
        if not inventory_open:
            # 鼠标持续按下
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
                tx = int(proj["x"] // C.BLOCKSIZE)
                ty = int(proj["y"] // C.BLOCKSIZE)
                if tile_in_map(world, tx, ty) and world.tile_data[tx][ty] != C.AIR:
                    tile_info = C.TILES.get(world.tile_data[tx][ty])
                    if tile_info and tile_info["solid"]:
                        proj["alive"] = False
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

        # 更新摄像机
        cam_x = player.position[0]
        cam_y = player.position[1]
        half_w = C.WINDOW_WIDTH * 0.5
        half_h = C.WINDOW_HEIGHT * 0.5
        cam_x = max(half_w, min(cam_x, world.width * C.BLOCKSIZE - half_w))
        cam_y = max(half_h, min(cam_y, world.height * C.BLOCKSIZE - half_h))

        # ===== 渲染 =====
        sky_color = C.get_sky_color(game_time)
        screen.fill(sky_color)

        terrain_offset_x = C.WINDOW_WIDTH * 0.5 - cam_x
        terrain_offset_y = C.WINDOW_HEIGHT * 0.5 - cam_y
        screen.blit(terrain_surface, (terrain_offset_x, terrain_offset_y))

        # 方块高亮
        if not inventory_open and tile_in_map(world, mouse_tile[0], mouse_tile[1]):
            hl_x = mouse_tile[0] * C.BLOCKSIZE + terrain_offset_x
            hl_y = mouse_tile[1] * C.BLOCKSIZE + terrain_offset_y
            dx = mouse_tile[0] - player.block_x
            dy = mouse_tile[1] - player.block_y
            if math.sqrt(dx * dx + dy * dy) <= C.PLAYER_REACH:
                pygame.draw.rect(screen, (255, 255, 255, 128),
                                 (hl_x, hl_y, C.BLOCKSIZE, C.BLOCKSIZE), 1)
            else:
                pygame.draw.rect(screen, (100, 100, 100),
                                 (hl_x, hl_y, C.BLOCKSIZE, C.BLOCKSIZE), 1)

        # 弹射体
        for proj in projectiles:
            px = proj["x"] - cam_x + C.WINDOW_WIDTH * 0.5
            py = proj["y"] - cam_y + C.WINDOW_HEIGHT * 0.5
            pygame.draw.circle(screen, (255, 255, 100), (int(px), int(py)), 3)

        # 史莱姆
        for slime in slimes:
            slime.draw(screen, cam_x, cam_y)

        # 玩家
        player.draw(screen, cam_x, cam_y)

        # 挖掘进度条
        if not inventory_open:
            player.draw_mining_progress(screen, cam_x, cam_y)

        # ===== UI =====
        draw_hotbar(screen, player, font)
        draw_health_bar(screen, player, font)

        # FPS + 坐标
        fps_text = small_font.render(f"FPS: {int(clock.get_fps())}", True, (255, 255, 255))
        screen.blit(fps_text, (5, 5))

        is_night = (game_time % C.DAY_NIGHT_CYCLE) > C.DAY_DURATION
        time_label = "Night" if is_night else "Day"
        coord_text = small_font.render(
            f"Pos: ({player.block_x}, {player.block_y})  Slimes: {len(slimes)}  {time_label}", True, (255, 255, 255))
        screen.blit(coord_text, (5, 22))

        # ===== 物品栏覆盖层 =====
        if inventory_open:
            draw_inventory(screen, player, font, quit_rect)

        pygame.display.flip()
        clock.tick(C.FPS)

    assets.stop_music()
    pygame.quit()


def _spawn_slime(slimes, player, world):
    side = random.choice([-1, 1])
    dist = random.randint(20, 40)
    spawn_x = player.position[0] + side * dist * C.BLOCKSIZE
    bx = int(spawn_x // C.BLOCKSIZE)
    by = 0
    for y in range(world.height):
        if 0 <= bx < world.width and world.tile_data[bx][y] != C.AIR:
            by = y
            break
    spawn_y = by * C.BLOCKSIZE - C.BLOCKSIZE
    if spawn_y <= 0:
        return
    slime_type = random.randint(0, min(4, 2))
    slimes.append(Slime((spawn_x, spawn_y), slime_type))


def _sword_hit_slimes(player, slimes):
    if not player.swinging:
        return
    slot = player.hotbar[player.hotbar_index]
    if slot is None:
        return
    item = C.ITEMS[slot["item_id"]]
    if not item["is_sword"]:
        return

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
            kb_dir = 1 if slime.position[0] > player.position[0] else -1
            kb_vel = (kb_dir * 80, -60)
            slime.velocity[0] = kb_dir * 15
            slime.velocity[1] = -20
            slime.damage(item["damage"], source_velocity=kb_vel)


def _shoot_gun(player, projectiles, mouse_world_x, mouse_world_y):
    ammo_slot = player.find_ammo("Musket Ball")
    if ammo_slot is None:
        return
    slot_idx, _ = ammo_slot

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
        play_sound("swing", 0.4)
    except Exception:
        pass


def draw_hotbar(screen, player, font):
    import assets

    slot_size = 44
    padding = 4
    start_x = C.WINDOW_WIDTH * 0.5 - (C.HOTBAR_SIZE * (slot_size + padding)) * 0.5
    start_y = C.WINDOW_HEIGHT - slot_size - 10

    for i in range(C.HOTBAR_SIZE):
        x = int(start_x + i * (slot_size + padding))
        y = int(start_y)

        if i == player.hotbar_index and assets.get_gui_selected_slot_surface():
            screen.blit(assets.get_gui_selected_slot_surface(), (x - 2, y - 2))
        elif assets.get_gui_slot_surface():
            screen.blit(assets.get_gui_slot_surface(), (x - 2, y - 2))
        else:
            bg_color = (60, 60, 60) if i != player.hotbar_index else (90, 90, 90)
            pygame.draw.rect(screen, bg_color, (x, y, slot_size, slot_size))
            border_color = C.SLOT_SELECTED_COLOR if i == player.hotbar_index else C.SLOT_BORDER_COLOR
            border_width = 2 if i == player.hotbar_index else 1
            pygame.draw.rect(screen, border_color, (x, y, slot_size, slot_size), border_width)

        slot = player.hotbar[i]
        _draw_slot_item(screen, slot, x, y, slot_size, font)


def draw_health_bar(screen, player, font):
    bar_width = 200
    bar_height = 20
    x = C.WINDOW_WIDTH - bar_width - 10
    y = 10

    pygame.draw.rect(screen, C.HEALTH_BAR_BG, (x, y, bar_width, bar_height))
    hp_ratio = max(0, player.hp / player.max_hp)
    hp_width = int(bar_width * hp_ratio)
    hp_color = (220, 30, 30) if hp_ratio < 0.3 else (50, 200, 50)
    pygame.draw.rect(screen, hp_color, (x, y, hp_width, bar_height))
    pygame.draw.rect(screen, (200, 200, 200), (x, y, bar_width, bar_height), 1)

    hp_text = font.render(f"{player.hp}/{player.max_hp}", True, (255, 255, 255))
    screen.blit(hp_text, (x + bar_width * 0.5 - hp_text.get_width() * 0.5,
                           y + bar_height * 0.5 - hp_text.get_height() * 0.5))


def _draw_slot_item(screen, slot, x, y, slot_size, font):
    """绘制单个槽位的物品图标和数量"""
    if slot is None:
        return
    icon = C.get_item_icon(slot["item_id"], size=slot_size - 8)
    if icon:
        screen.blit(icon, (x + (slot_size - icon.get_width()) * 0.5,
                           y + (slot_size - icon.get_height()) * 0.5))
    if slot["count"] > 1:
        count_text = font.render(str(slot["count"]), True, (255, 255, 255))
        screen.blit(count_text, (x + slot_size - count_text.get_width() - 2,
                                 y + slot_size - count_text.get_height() - 1))


def draw_inventory(screen, player, font, quit_rect):
    """绘制物品栏覆盖层（ESC 打开，游戏暂停）"""
    panel_w = 440
    panel_h = 380
    panel_x = int(C.WINDOW_WIDTH * 0.5 - panel_w * 0.5)
    panel_y = int(C.WINDOW_HEIGHT * 0.5 - panel_h * 0.5)

    # 半透明遮罩
    overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    # 面板背景
    pygame.draw.rect(screen, (35, 35, 45), (panel_x, panel_y, panel_w, panel_h), border_radius=8)
    pygame.draw.rect(screen, (100, 100, 120), (panel_x, panel_y, panel_w, panel_h), 2, border_radius=8)

    # 标题
    title = font.render("Inventory", True, (255, 255, 255))
    screen.blit(title, (panel_x + 15, panel_y + 12))

    slot_size = 44
    padding = 4
    cols = C.HOTBAR_SIZE
    grid_w = cols * (slot_size + padding) - padding
    start_x = int(panel_x + (panel_w - grid_w) * 0.5)

    # 快捷栏行
    hotbar_y = panel_y + 45
    for i in range(C.HOTBAR_SIZE):
        x = start_x + i * (slot_size + padding)
        y = hotbar_y
        bg = (50, 50, 50) if i != player.hotbar_index else (70, 70, 70)
        pygame.draw.rect(screen, bg, (x, y, slot_size, slot_size), border_radius=3)
        pygame.draw.rect(screen, (100, 100, 100), (x, y, slot_size, slot_size), 1, border_radius=3)
        _draw_slot_item(screen, player.hotbar[i], x, y, slot_size, font)

    # 物品栏网格（4行 × 8列 = 32槽）
    inv_label = font.render("Items", True, (200, 200, 200))
    screen.blit(inv_label, (start_x, hotbar_y + slot_size + padding + 8))

    inv_start_y = hotbar_y + slot_size + padding + 30
    inv_cols = cols
    inv_rows = len(player.inventory) // inv_cols
    for row in range(inv_rows):
        for col in range(inv_cols):
            idx = row * inv_cols + col
            x = start_x + col * (slot_size + padding)
            y = inv_start_y + row * (slot_size + padding)
            pygame.draw.rect(screen, (45, 45, 45), (x, y, slot_size, slot_size), border_radius=3)
            pygame.draw.rect(screen, (80, 80, 80), (x, y, slot_size, slot_size), 1, border_radius=3)
            _draw_slot_item(screen, player.inventory[idx], x, y, slot_size, font)

    # Quit 按钮
    mouse_pos = pygame.mouse.get_pos()
    hover = quit_rect.collidepoint(mouse_pos)
    btn_color = (180, 60, 60) if hover else (120, 40, 40)
    pygame.draw.rect(screen, btn_color, quit_rect, border_radius=6)
    pygame.draw.rect(screen, (200, 200, 200), quit_rect, 1, border_radius=6)
    quit_text = font.render("Quit", True, (255, 255, 255))
    screen.blit(quit_text, (quit_rect.centerx - quit_text.get_width() * 0.5,
                             quit_rect.centery - quit_text.get_height() * 0.5))

    # 提示
    hint = font.render("(ESC to close)", True, (150, 150, 150))
    screen.blit(hint, (quit_rect.right + 10, quit_rect.y + 8))

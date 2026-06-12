# game.py - 主游戏循环、摄像机、输入处理、渲染管线
import pygame
import math
import constants as C
from pygame.locals import *
from world import World, generate_terrain, create_terrain_surface, tile_in_map
from player import Player


def run(screen):
    """主游戏函数"""
    # 初始化资源加载
    import assets
    assets.init()

    clock = pygame.time.Clock()
    font = assets.font_default if assets.font_default else pygame.font.Font(None, 24)
    small_font = assets.font_small if assets.font_small else pygame.font.Font(None, 18)

    # 创建世界
    print("Generating world...")
    world = World()
    generate_terrain(world)
    print("Creating terrain surface...")
    terrain_surface = create_terrain_surface(world)
    print("World ready!")

    # 创建玩家
    player = Player(world.spawn_position)

    # 摄像机
    cam_x = player.position[0]
    cam_y = player.position[1]

    old_ticks = pygame.time.get_ticks()
    running = True

    while running:
        # Delta time
        current_ticks = pygame.time.get_ticks()
        dt = (current_ticks - old_ticks) * 0.001
        if dt > 0.033:
            dt = 0.033
        old_ticks = current_ticks

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

        # 鼠标持续按下：持续使用物品
        if pygame.mouse.get_pressed()[0]:
            player.use_item(world, mouse_tile, terrain_surface)

        # 更新玩家
        player.update(world, dt)

        # 更新摄像机（跟随玩家）
        cam_x = player.position[0]
        cam_y = player.position[1]

        # 摄像机边界
        half_w = C.WINDOW_WIDTH * 0.5
        half_h = C.WINDOW_HEIGHT * 0.5
        cam_x = max(half_w, min(cam_x, world.width * C.BLOCKSIZE - half_w))
        cam_y = max(half_h, min(cam_y, world.height * C.BLOCKSIZE - half_h))

        # ===== 渲染 =====
        screen.fill(C.SKY_COLOR)

        # 地形
        terrain_offset_x = C.WINDOW_WIDTH * 0.5 - cam_x
        terrain_offset_y = C.WINDOW_HEIGHT * 0.5 - cam_y
        screen.blit(terrain_surface, (terrain_offset_x, terrain_offset_y))

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

        # 玩家
        player.draw(screen, cam_x, cam_y)

        # ===== UI =====
        draw_hotbar(screen, player, font)
        draw_health_bar(screen, player, font)

        # FPS
        fps_text = small_font.render(f"FPS: {int(clock.get_fps())}", True, (255, 255, 255))
        screen.blit(fps_text, (5, 5))

        # 坐标信息
        coord_text = small_font.render(
            f"Pos: ({player.block_x}, {player.block_y})", True, (255, 255, 255))
        screen.blit(coord_text, (5, 22))

        pygame.display.flip()
        clock.tick(C.FPS)

    pygame.quit()


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

# world.py - 世界数据、地形生成、地形渲染
import pygame
import random
import math
import perlin
import constants as C


class World:
    def __init__(self, width=C.WORLD_WIDTH, height=C.WORLD_HEIGHT):
        self.width = width
        self.height = height
        # tile_data[x][y] = int (方块 ID)
        self.tile_data = [[C.AIR for _ in range(height)] for _ in range(width)]
        # wall_data[x][y] = int (背景墙 ID, 0=无)
        self.wall_data = [[0 for _ in range(height)] for _ in range(width)]
        self.spawn_position = (0, 0)


def tile_in_map(world, x, y):
    return 0 <= x < world.width and 0 <= y < world.height


def get_tile(world, x, y):
    if tile_in_map(world, x, y):
        return world.tile_data[x][y]
    return C.AIR


def set_tile(world, x, y, tile_id):
    if tile_in_map(world, x, y):
        world.tile_data[x][y] = tile_id


def is_solid(world, x, y):
    if not tile_in_map(world, x, y):
        return True
    tile_id = world.tile_data[x][y]
    tile = C.TILES.get(tile_id)
    return tile is not None and tile["solid"]


def is_platform(world, x, y):
    if not tile_in_map(world, x, y):
        return False
    return world.tile_data[x][y] == 7


def get_neighbor_count(world, x, y):
    """计算相邻实心方块数量（用于放置验证）"""
    count = 0
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        if is_solid(world, x + dx, y + dy):
            count += 1
    return count


def generate_terrain(world):
    """使用柏林噪声生成地形，包含三个群系"""
    noise_gen = perlin.SimplexNoise()
    offsets = [random.random() * 1000 for _ in range(3)]

    # 群系边界
    border1 = world.width // 3 + random.randint(-15, 15)   # 雪/森林分界
    border2 = 2 * world.width // 3 + random.randint(-15, 15)  # 森林/沙漠分界

    # 计算每列的地表高度
    surface_heights = []
    for x in range(world.width):
        val = noise_gen.noise2(x / 100 + offsets[2], 0.1)
        height = int(val * 25 + 65)
        surface_heights.append(height)

    # 填充地形（按群系）
    for x in range(world.width):
        # 确定群系
        if x < border1:
            biome_id = 1  # Snow
        elif x < border2:
            biome_id = 0  # Forest
        else:
            biome_id = 2  # Desert

        biome = C.BIOMES[biome_id]
        surface_y = surface_heights[x]

        for y in range(world.height):
            if y < surface_y:
                continue

            if y == surface_y:
                world.tile_data[x][y] = biome["surface"]
            elif y < surface_y + 12:
                world.tile_data[x][y] = biome["underground"]
                world.wall_data[x][y] = biome["ug_wall"]
            else:
                world.tile_data[x][y] = biome["deep"]
                world.wall_data[x][y] = biome["deep_wall"]

    # 铜矿脉（替换石头/冰/砂岩）
    num_copper = int(world.width * world.height / 1200)
    for _ in range(num_copper):
        vx = random.randint(0, world.width - 1)
        vy = random.randint(0, world.height - 1)
        create_vein(world, vx, vy, 5, random.randint(3, 6))

    # 银矿脉（更深层）
    num_silver = int(world.width * world.height / 1800)
    for _ in range(num_silver):
        vx = random.randint(0, world.width - 1)
        vy = random.randint(0, world.height - 1)
        create_vein(world, vx, vy, 9, random.randint(3, 5))

    # 树木（森林和雪地群系）
    x = 5
    while x < world.width - 5:
        gap = random.randint(4, 8)
        if random.random() < 0.6:
            # 确定群系
            if x < border1:
                biome_id = 1
            elif x < border2:
                biome_id = 0
            else:
                biome_id = 2  # 沙漠不生成树

            biome = C.BIOMES[biome_id]
            if biome["leaves"] is not None:
                surface_y = surface_heights[x]
                if tile_in_map(world, x, surface_y) and world.tile_data[x][surface_y] == biome["surface"]:
                    create_tree(world, x, surface_y, random.randint(5, 10), biome["leaves"])
        x += gap

    # 出生点：世界中间的地表上方
    spawn_x = world.width // 2
    spawn_y = surface_heights[spawn_x] - 3
    world.spawn_position = (spawn_x * C.BLOCKSIZE, spawn_y * C.BLOCKSIZE)


def create_vein(world, x, y, tile_id, size):
    """在指定位置生成一个矿石矿脉"""
    for _ in range(size):
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)
        nx, ny = x + dx, y + dy
        if tile_in_map(world, nx, ny):
            tile = world.tile_data[nx][ny]
            # 只替换石头、冰、砂岩（深层方块）
            if tile in (3, 11, 13):
                world.tile_data[nx][ny] = tile_id
                x, y = nx, ny


def create_tree(world, base_x, surface_y, height, leaves_tile):
    """在指定位置生成一棵树"""
    for dy in range(1, height + 1):
        ty = surface_y - dy
        if tile_in_map(world, base_x, ty):
            world.tile_data[base_x][ty] = 8  # Trunk

    top_y = surface_y - height
    for dx in range(-2, 3):
        for dy in range(-2, 2):
            tx = base_x + dx
            ty = top_y + dy
            if tile_in_map(world, tx, ty) and world.tile_data[tx][ty] == C.AIR:
                if dx * dx + (dy + 1) * (dy + 1) <= 5:
                    world.tile_data[tx][ty] = leaves_tile


def create_terrain_surface(world):
    """创建地形渲染 Surface（包含背景墙）"""
    import assets as _assets

    terrain = pygame.Surface((world.width * C.BLOCKSIZE, world.height * C.BLOCKSIZE))
    terrain.fill(C.SKY_COLOR)
    terrain.set_colorkey(C.SKY_COLOR)

    for x in range(world.width):
        for y in range(world.height):
            px = x * C.BLOCKSIZE
            py = y * C.BLOCKSIZE
            tile_id = world.tile_data[x][y]
            wall_id = world.wall_data[x][y]

            # 背景墙：仅当前景方块为空气时绘制
            if tile_id == C.AIR and wall_id != 0:
                wall_surf = _assets.get_wall_surface(wall_id)
                if wall_surf:
                    terrain.blit(wall_surf, (px, py))

            # 前景方块
            if tile_id != C.AIR:
                tile_surf = C.get_tile_surface(tile_id)
                if tile_surf:
                    terrain.blit(tile_surf, (px, py))

    return terrain


def update_tile(terrain_surface, world, x, y):
    """更新单个方块的渲染（含背景墙）"""
    if not tile_in_map(world, x, y):
        return

    import assets as _assets
    px = x * C.BLOCKSIZE
    py = y * C.BLOCKSIZE

    # 清除
    pygame.draw.rect(terrain_surface, C.SKY_COLOR, (px, py, C.BLOCKSIZE, C.BLOCKSIZE))

    tile_id = world.tile_data[x][y]
    wall_id = world.wall_data[x][y]

    # 背景墙
    if tile_id == C.AIR and wall_id != 0:
        wall_surf = _assets.get_wall_surface(wall_id)
        if wall_surf:
            terrain_surface.blit(wall_surf, (px, py))

    # 前景方块
    if tile_id != C.AIR:
        tile_surf = C.get_tile_surface(tile_id)
        if tile_surf:
            terrain_surface.blit(tile_surf, (px, py))

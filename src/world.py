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
        self.spawn_position = (0, 0)  # 像素坐标


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
        return True  # 世界边界视为实心
    tile_id = world.tile_data[x][y]
    tile = C.TILES.get(tile_id)
    return tile is not None and tile["solid"]


def is_platform(world, x, y):
    if not tile_in_map(world, x, y):
        return False
    return world.tile_data[x][y] == 7  # Platform


def get_neighbor_count(world, x, y):
    """计算相邻实心方块数量（用于放置验证）"""
    count = 0
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        if is_solid(world, x + dx, y + dy):
            count += 1
    return count


def generate_terrain(world):
    """使用柏林噪声生成地形"""
    noise_gen = perlin.SimplexNoise()
    offsets = [random.random() * 1000 for _ in range(3)]

    # 计算每列的地表高度（崎岖不平）
    surface_heights = []
    for x in range(world.width):
        val = noise_gen.noise2(x / 100 + offsets[2], 0.1)
        height = int(val * 25 + 65)  # 基础高度约 65，波动 ±25
        surface_heights.append(height)

    # 生成基础地形（地下完全填满，无洞穴）
    for x in range(world.width):
        surface_y = surface_heights[x]
        for y in range(world.height):
            if y < surface_y:
                continue  # 空气

            if y == surface_y:
                world.tile_data[x][y] = 1  # Grass
            elif y < surface_y + 12:
                world.tile_data[x][y] = 2  # Dirt
            else:
                world.tile_data[x][y] = 3  # Stone

    # 生成铜矿脉（地下石头层）
    num_copper = int(world.width * world.height / 2000)
    for _ in range(num_copper):
        vx = random.randint(0, world.width - 1)
        vy = random.randint(0, world.height - 1)
        create_vein(world, vx, vy, 5, random.randint(3, 6))  # CopperOre

    # 生成银矿脉（更深更多）
    num_silver = int(world.width * world.height / 3000)
    for _ in range(num_silver):
        vx = random.randint(0, world.width - 1)
        vy = random.randint(0, world.height - 1)
        create_vein(world, vx, vy, 9, random.randint(3, 5))  # SilverOre

    # 生成树木（树干用 Trunk id=8，可穿过）
    for x in range(5, world.width - 5, random.randint(4, 8)):
        if random.random() < 0.6:
            surface_y = surface_heights[x]
            if tile_in_map(world, x, surface_y) and world.tile_data[x][surface_y] == 1:
                create_tree(world, x, surface_y, random.randint(5, 10))

    # 确定出生点：世界中间的地表上方
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
            if world.tile_data[nx][ny] == 3:  # 只替换石头
                world.tile_data[nx][ny] = tile_id
                x, y = nx, ny


def create_tree(world, base_x, surface_y, height):
    """在指定位置生成一棵树"""
    # 树干（用 Trunk id=8，非实心，可穿过）
    for dy in range(1, height + 1):
        ty = surface_y - dy
        if tile_in_map(world, base_x, ty):
            world.tile_data[base_x][ty] = 8  # Trunk（非实心）

    # 树冠（树叶）
    top_y = surface_y - height
    for dx in range(-2, 3):
        for dy in range(-2, 2):
            tx = base_x + dx
            ty = top_y + dy
            if tile_in_map(world, tx, ty) and world.tile_data[tx][ty] == C.AIR:
                # 椭圆形树冠
                if dx * dx + (dy + 1) * (dy + 1) <= 5:
                    world.tile_data[tx][ty] = 6  # Leaves


def create_terrain_surface(world):
    """创建地形渲染 Surface（使用精灵图或纯色矩形）"""
    terrain = pygame.Surface((world.width * C.BLOCKSIZE, world.height * C.BLOCKSIZE))
    terrain.fill(C.SKY_COLOR)
    terrain.set_colorkey(C.SKY_COLOR)

    for x in range(world.width):
        for y in range(world.height):
            tile_id = world.tile_data[x][y]
            if tile_id != C.AIR:
                tile_surf = C.get_tile_surface(tile_id)
                if tile_surf:
                    terrain.blit(tile_surf, (x * C.BLOCKSIZE, y * C.BLOCKSIZE))

    return terrain


def update_tile(terrain_surface, world, x, y):
    """更新单个方块的渲染"""
    if not tile_in_map(world, x, y):
        return

    pixel_x = x * C.BLOCKSIZE
    pixel_y = y * C.BLOCKSIZE

    # 清除该区域（用透明色）
    pygame.draw.rect(terrain_surface, C.SKY_COLOR, (pixel_x, pixel_y, C.BLOCKSIZE, C.BLOCKSIZE))

    # 绘制新方块
    tile_id = world.tile_data[x][y]
    if tile_id != C.AIR:
        tile_surf = C.get_tile_surface(tile_id)
        if tile_surf:
            terrain_surface.blit(tile_surf, (pixel_x, pixel_y))

    # 也更新相邻方块（确保边缘正确）
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = x + dx, y + dy
        if tile_in_map(world, nx, ny):
            # 不需要重绘相邻方块，因为简单版本没有遮罩
            pass

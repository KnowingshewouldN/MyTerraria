import os, sys

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_path + "/src")

import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("MyTerraria")

import game

# 主菜单 <-> 游戏 循环：打完一局（含 3D 胜利场景）后回到菜单
while True:
    screen = pygame.display.get_surface()
    if not game.run_menu(screen):
        break
    game.run(screen)

pygame.quit()

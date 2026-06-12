import os, sys

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_path + "/src")

import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("MyTerraria")

import game
if game.run_menu(screen):
    game.run(screen)

"""
Auxiliar: abre spritesheet.png com grid para identificar coordenadas.
Clique em qualquer ponto para ver (x, y) no terminal.
Use seta esquerda/direita para ajustar tamanho do grid (G).
"""
import pygame, sys, os

IMG = os.path.join(os.path.dirname(__file__), "sprites", "spritesheet.png")

pygame.init()
sheet = pygame.image.load(IMG).convert_alpha()
SW, SH = sheet.get_size()
SCALE = max(1, min(6, 600 // max(SW, 1)))

win_w = max(SW * SCALE, 600)
win_h = max(SH * SCALE + 80, 400)
screen = pygame.display.set_mode((win_w, win_h))
pygame.display.set_caption(f"Analisador de Sprites  ({SW}×{SH}px)")
font = pygame.font.SysFont("Consolas", 16)

scaled = pygame.transform.scale(sheet, (SW * SCALE, SH * SCALE))

G = 16  # grid cell size (em px originais)
info = ""

clock = pygame.time.Clock()
while True:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            pygame.quit(); sys.exit()
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_RIGHT: G = min(G + 4, 64)
            if ev.key == pygame.K_LEFT:  G = max(G - 4, 4)
        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            ox = mx // SCALE
            oy = my // SCALE
            cx = (ox // G) * G
            cy = (oy // G) * G
            info = f"Pixel: ({ox},{oy})  |  Célula grid: x={cx} y={cy} w={G} h={G}"
            print(info)

    screen.fill((30, 30, 40))
    screen.blit(scaled, (0, 0))

    # Grid overlay
    for gx in range(0, SW, G):
        pygame.draw.line(screen, (0,200,0,100), (gx*SCALE, 0), (gx*SCALE, SH*SCALE), 1)
    for gy in range(0, SH, G):
        pygame.draw.line(screen, (0,200,0,100), (0, gy*SCALE), (SW*SCALE, gy*SCALE), 1)

    # Info bar
    pygame.draw.rect(screen, (10,10,20), (0, SH*SCALE, win_w, 80))
    screen.blit(font.render(info or "Clique na sprite para ver coordenadas", True, (200,200,200)), (8, SH*SCALE+8))
    screen.blit(font.render(f"Grid: {G}px  |  ←→ para ajustar  |  Imagem: {SW}×{SH}px  |  Escala: {SCALE}x", True, (120,180,120)), (8, SH*SCALE+30))
    screen.blit(font.render("ESC para sair", True, (120,120,120)), (8, SH*SCALE+52))

    pygame.display.flip()
    clock.tick(30)

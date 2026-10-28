import pygame
import random

TILE = 48


class Tile:
    def __init__(self, x, y, one_way=False):
        height = 16 if one_way else TILE
        self.rect = pygame.Rect(x, y, TILE, height)
        self.one_way = one_way


class Level:
    def __init__(self, layout, tileset, movers=()):
        self.layout = layout
        self.tiles = []
        self.key_spots = []
        self.spikes = []
        self.laser_spots = []
        self.enemy_spots = []
        self.pop_spots = []
        self.crusher_spots = []
        self.start = (0, 0)
        self.exit_spot = (0, 0)
        self.rows = len(layout)
        self.cols = len(layout[0])
        self.width = self.cols * TILE
        self.height = self.rows * TILE

        for r, row in enumerate(layout):
            for c, ch in enumerate(row):
                x, y = c * TILE, r * TILE
                if ch == "#":
                    self.tiles.append(Tile(x, y))
                elif ch == "-":
                    self.tiles.append(Tile(x, y, one_way=True))
                elif ch == "K":
                    self.key_spots.append((x, y))
                elif ch == "^":
                    self.spikes.append(pygame.Rect(x + 10, y + 34, TILE - 20, 14))
                elif ch == "v":
                    self.spikes.append(pygame.Rect(x + 10, y, TILE - 20, 14))
                elif ch == "L":
                    self.laser_spots.append((r, c))
                elif ch == "C":
                    self.crusher_spots.append((r, c))
                elif ch == "*":
                    self.pop_spots.append((x, y))
                elif ch in "bgy":
                    self.enemy_spots.append((ch, x, y))
                elif ch == "P":
                    self.start = (x, y + TILE)
                elif ch == "E":
                    self.exit_spot = (x + TILE // 2, y + TILE)

        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.paint_ground(tileset)
        self.paint_platforms(tileset)
        self.paint_spikes(tileset)
        self.make_crumble_pieces(tileset)

        self.lasers = []
        for r, c in self.laser_spots:
            bottom = r
            while bottom + 1 < self.rows and not self.solid(bottom + 1, c):
                bottom += 1
            top_y = r * TILE
            bottom_y = (bottom + 1) * TILE
            self.lasers.append(pygame.Rect(c * TILE + 14, top_y, 20, bottom_y - top_y))


        self.pop_spikes = []
        if "spike_up" in tileset:
            pop_img = pygame.transform.smoothscale(tileset["spike_up"], (TILE + 8, 46))
            self.pop_spikes = [PopSpike(x, y, pop_img) for x, y in self.pop_spots]


        self.crushers = []
        if "crusher" in tileset:
            for r, c in self.crusher_spots:
                floor = r
                while floor < self.rows and not self.solid(floor, c):
                    floor += 1
                delay = (c * 350) % 1500
                self.crushers.append(Crusher(c * TILE, r * TILE, floor * TILE,
                                             tileset["crusher"], delay))
        

        self.movers = []
        for col, row, w, mc, mr, speed, crumble in movers:
            width = w * TILE
            src = tileset["platforms"][(col + row) % len(tileset["platforms"])]
            img_w = width + 16
            img_h = int(img_w * src.get_height() / src.get_width() * tileset["squash"])
            img = pygame.transform.smoothscale(src, (img_w, img_h))
            self.movers.append(MovingPlatform(
                col * TILE, row * TILE, width, img,
                mc * TILE, mr * TILE, speed, crumble,
                -int(img_h * tileset["feet"])))
        

    def solid(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols and self.layout[r][c] == "#"

    def is_ground(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols and self.layout[r][c] in "#-"

    def border(self, r, c):
        return c == 0 or c == self.cols - 1

    def paint_ground(self, ts):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.layout[r][c] != "#" or self.border(r, c):
                    continue
                x, y = c * TILE, r * TILE

                if not self.solid(r - 1, c):
                    left_open = not self.solid(r, c - 1) or self.border(r, c - 1)
                    right_open = not self.solid(r, c + 1) or self.border(r, c + 1)
                    if left_open and not right_open:
                        img = ts["top_l"]
                    elif right_open and not left_open:
                        img = ts["top_r"]
                    else:
                        img = ts["top"][(c * 7 + r * 13) % len(ts["top"])]
                    self.surface.blit(img, (x, y - 10))
                else:
                    self.surface.blit(ts["fill"], (x, y))

                if r + 1 < self.rows and not self.solid(r + 1, c):
                    hang = ts["hang"][(c + r) % len(ts["hang"])]
                    self.surface.blit(hang, (x, y + TILE))

    def paint_platforms(self, ts):
        for r in range(self.rows):
            c = 0
            while c < self.cols:
                if self.layout[r][c] != "-":
                    c += 1
                    continue
                start = c
                while c < self.cols and self.layout[r][c] == "-":
                    c += 1
                width = (c - start) * TILE + 16
                src = ts["platforms"][(start + r) % len(ts["platforms"])]
                height = int(width * src.get_height() / src.get_width() * ts["squash"])
                img = pygame.transform.smoothscale(src, (width, height))
                y = r * TILE - int(height * ts["feet"])
                self.surface.blit(img, (start * TILE - 8, y))


    def paint_spikes(self, ts):
        for ch, key in (("^", "spike_up"), ("v", "spike_down")):
            if key not in ts:
                continue
            src = ts[key]
            for r in range(self.rows):
                c = 0
                while c < self.cols:
                    if self.layout[r][c] != ch:
                        c += 1
                        continue
                    start = c
                    while c < self.cols and self.layout[r][c] == ch:
                        c += 1
                    w = (c - start) * TILE
                    img = pygame.transform.smoothscale(src, (w + 8, 46))
                    if ch == "^":
                        y = r * TILE + TILE - img.get_height()
                    else:
                        y = r * TILE
                    self.surface.blit(img, (start * TILE - 4, y))

    def make_crumble_pieces(self, ts):
        self.crumble_pieces = []
        for r in range(self.rows):
            c = 0
            while c < self.cols:
                if self.layout[r][c] != "~":
                    c += 1
                    continue
                start = c
                while c < self.cols and self.layout[r][c] == "~":
                    c += 1
                count = c - start

                width = count * TILE + 16
                src = ts["platforms"][(start + r) % len(ts["platforms"])]
                height = int(width * src.get_height() / src.get_width() * ts["squash"])
                img = pygame.transform.smoothscale(src, (width, height))
                top = int(height * ts["feet"])

                for i in range(count):
                    x0 = 0 if i == 0 else 8 + i * TILE
                    x1 = width if i == count - 1 else 8 + (i + 1) * TILE
                    piece = img.subsurface((x0, 0, x1 - x0, height)).copy()
                    self.crumble_pieces.append(
                        ((start + i) * TILE, r * TILE, piece, x0 - 8 - i * TILE, -top))

    def draw(self, screen, cam):
        view = pygame.Rect(cam.x, cam.y, screen.get_width(), screen.get_height())
        screen.blit(self.surface, (0, 0), area=view)


class Camera:
    def __init__(self, world_w, world_h, screen_w, screen_h):
        self.world_w = world_w
        self.world_h = world_h
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.fx = 0.0
        self.fy = 0.0
        self.x = 0
        self.y = 0

    def _clamp(self):
        self.fx = max(0, min(self.fx, self.world_w - self.screen_w))
        self.fy = max(0, min(self.fy, self.world_h - self.screen_h))
        self.x = int(self.fx)
        self.y = int(self.fy)

    def follow(self, target, smooth=0.12):
        tx = target.centerx - self.screen_w // 2
        ty = target.centery - self.screen_h // 2
        self.fx += (tx - self.fx) * smooth
        self.fy += (ty - self.fy) * smooth
        self._clamp()

    def snap(self, target):
        self.fx = target.centerx - self.screen_w // 2
        self.fy = target.centery - self.screen_h // 2
        self._clamp()


class CrumblePlatform:
    SHAKE_TIME = 400      # ms before it falls
    RESPAWN_TIME = 3000   # ms until it comes back

    def __init__(self, x, y, image, dx=0, dy=0):
        self.rect = pygame.Rect(x, y, TILE, 16)
        self.one_way = True
        self.image = image
        self.dx = dx
        self.dy = dy
        self.state = "solid"
        self.timer = 0
        self.fall_y = 0

    @property
    def active(self):
        return self.state != "fallen"

    def touch(self):
        if self.state == "solid":
            self.state = "shaking"
            self.timer = pygame.time.get_ticks()

    def update(self):
        now = pygame.time.get_ticks()
        if self.state == "shaking" and now - self.timer > self.SHAKE_TIME:
            self.state = "fallen"
            self.timer = now
            self.fall_y = 0
        elif self.state == "fallen":
            self.fall_y += 8
            if now - self.timer > self.RESPAWN_TIME:
                self.state = "solid"

    def draw(self, screen, cam):
        x = self.rect.x - cam.x + self.dx
        y = self.rect.y - cam.y + self.dy
        if self.state == "shaking":
            x += random.randint(-2, 2)
        elif self.state == "fallen":
            if self.fall_y > 400:
                return
            y += self.fall_y
        screen.blit(self.image, (x, y))


class MovingPlatform:

    SHAKE_TIME = 900      # ms before it falls (longer than normal crumble)

    def __init__(self, x, y, width, image, move_x, move_y, speed, crumble, img_dy):
        self.start = pygame.Vector2(x, y)
        self.end = pygame.Vector2(x + move_x, y + move_y)
        self.pos = pygame.Vector2(x, y)
        self.rect = pygame.Rect(x, y, width, 16)
        self.one_way = True
        self.image = image
        self.img_dy = img_dy
        self.speed = speed
        self.going_to_end = True
        self.crumble = crumble
        self.state = "solid"
        self.timer = 0
        self.fall_y = 0
        self.last_move = (0, 0)

    @property
    def active(self):
        return self.state != "fallen"

    def touch(self):
        if self.crumble and self.state == "solid":
            self.state = "shaking"
            self.timer = pygame.time.get_ticks()

    def update(self):
        now = pygame.time.get_ticks()
        self.last_move = (0, 0)

        if self.state == "shaking" and now - self.timer > self.SHAKE_TIME:
            self.state = "fallen"
            self.timer = now
            self.fall_y = 0
        if self.state == "fallen":
            self.fall_y += 8
            if now - self.timer > CrumblePlatform.RESPAWN_TIME:
                self.state = "solid"
                self.pos = pygame.Vector2(self.start)
                self.rect.topleft = (round(self.pos.x), round(self.pos.y))
                self.going_to_end = True
            return

        target = self.end if self.going_to_end else self.start
        to_target = target - self.pos
        if to_target.length() <= self.speed:
            self.pos = pygame.Vector2(target)
            self.going_to_end = not self.going_to_end
        else:
            self.pos += to_target.normalize() * self.speed

        new_x, new_y = round(self.pos.x), round(self.pos.y)
        self.last_move = (new_x - self.rect.x, new_y - self.rect.y)
        self.rect.topleft = (new_x, new_y)

    def draw(self, screen, cam):
        x = self.rect.x - cam.x - 8
        y = self.rect.y - cam.y + self.img_dy
        if self.state == "shaking":
            x += random.randint(-2, 2)
        elif self.state == "fallen":
            if self.fall_y > 400:
                return
            y += self.fall_y
        screen.blit(self.image, (x, y))



class PopSpike:
    WARN = 350     # ms of warning before popping up
    UP = 1200      # ms the spikes stay up
    REST = 900     # ms hidden before they can trigger again

    def __init__(self, x, y, image):
        self.area = pygame.Rect(x, y, TILE, TILE)
        self.rect = pygame.Rect(x + 10, y + 34, TILE - 20, 14)
        self.image = image
        self.state = "hidden"
        self.timer = 0

    @property
    def dangerous(self):
        return self.state == "up"

    def update(self, player_rect):
        now = pygame.time.get_ticks()
        if self.state == "hidden":
            if self.area.inflate(120, 0).colliderect(player_rect):
                self.state = "warn"
                self.timer = now
        elif self.state == "warn" and now - self.timer > self.WARN:
            self.state = "up"
            self.timer = now
        elif self.state == "up" and now - self.timer > self.UP:
            self.state = "rest"
            self.timer = now
        elif self.state == "rest" and now - self.timer > self.REST:
            self.state = "hidden"

    def draw(self, screen, cam):
        if self.state in ("hidden", "rest"):
            return
        h = self.image.get_height()
        if self.state == "warn":
            show = 8
        else:
            show = min(h, int((pygame.time.get_ticks() - self.timer) / 60 * h))
        if show <= 0:
            return
        x = self.area.x - cam.x - 4
        y = self.area.bottom - cam.y - show
        screen.blit(self.image, (x, y), area=pygame.Rect(0, 0, self.image.get_width(), show))



class Crusher:
    WAIT_TOP = 900       # ms waiting up
    WAIT_BOTTOM = 400    # ms waiting down
    DOWN_SPEED = 6
    UP_SPEED = 3

    def __init__(self, x, top_y, floor_y, images, delay=0):
        self.head, self.pole, self.cap = images
        self.cx = x + TILE
        self.top_y = top_y
        self.min_y = top_y + self.cap.get_height()
        self.max_y = floor_y - self.head.get_height() - 2
        self.y = float(self.min_y)
        self.state = "wait_top"
        self.timer = pygame.time.get_ticks() + delay

    @property
    def rect(self):
        w = self.head.get_width()
        h = self.head.get_height()
        return pygame.Rect(self.cx - w // 2 + 8, int(self.y) + h - 24, w - 16, 24)

    def update(self):
        now = pygame.time.get_ticks()
        if self.state == "wait_top" and now >= self.timer:
            self.state = "down"
        elif self.state == "down":
            self.y += self.DOWN_SPEED
            if self.y >= self.max_y:
                self.y = self.max_y
                self.state = "wait_bottom"
                self.timer = now + self.WAIT_BOTTOM
        elif self.state == "wait_bottom" and now >= self.timer:
            self.state = "up"
        elif self.state == "up":
            self.y -= self.UP_SPEED
            if self.y <= self.min_y:
                self.y = self.min_y
                self.state = "wait_top"
                self.timer = now + self.WAIT_TOP

    def draw(self, screen, cam):
        cx = self.cx - cam.x
        top = self.top_y - cam.y
        head_top = int(self.y) - cam.y
        screen.blit(self.cap, (cx - self.cap.get_width() // 2, top))
        y = top + self.cap.get_height()
        while y < head_top + 10:
            screen.blit(self.pole, (cx - self.pole.get_width() // 2, y))
            y += self.pole.get_height()
        screen.blit(self.head, (cx - self.head.get_width() // 2, head_top))
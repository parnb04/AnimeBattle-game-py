import math
import random
import pygame

# Each room:
#   image   - background file in img/castle
#   floor   - points (x, y) of the floor line, left to right
#   left / right - can you leave through that screen edge?
#   spawn   - how far from the edge you appear when you arrive from a side
#   paths   - walk "into" the picture: floor point -> far point (x, y, scale)
ROOMS = [
    {"image": "room_0.jpg", "floor": [(0, 630), (1280, 630)],
     "left": False, "right": True, "walk": (20, 1260), "paths": [],
     "thought": "What happened to this forest?\nI've never seen it like this..."},

    {"image": "room_1.jpg", "floor": [(0, 712), (1280, 712)],
     "left": False, "right": False, "walk": (600, 680), "fixed": True,
     "paths": [{"floor": (640, 712), "end": (650, 628, 0.5), "to": 2, "kind": "depth"}],
     "thought": "Ruins... and what a palace.\nI should go inside."},

    {"image": "room_2.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (60, 1220), "paths": [], "thought": ""},

    {"image": "room_3.jpg",
     "floor": [(0, 690), (230, 640), (380, 625), (900, 625), (1000, 640), (1150, 605), (1280, 605)],
     "left": False, "right": True, "walk": (160, 1230),
     "paths": [{"floor": (230, 640), "end": (140, 365, 0.6), "to": 2, "kind": "stairs"}],
     "thought": ""},

    {"image": "room_4_closed.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (250, 1030), "paths": [],
     "thought": "Two sealed doors...\nand a tunnel that leads nowhere."},

    {"image": "room_5.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (80, 1200), "paths": [], "thought": ""},

    {"image": "room_6.jpg",
     "floor": [(0, 658), (130, 658), (131, 700), (1144, 700), (1145, 658), (1280, 658)],
     "left": True, "right": True, "walk": (40, 1240), "paths": [], "thought": ""},

    {"image": "room_7.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (100, 1180), "paths": [], "thought": ""},

    {"image": "room_8.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (110, 1170), "paths": [], "thought": ""},

    {"image": "room_9.jpg", "floor": [(0, 680), (1280, 680)],
     "left": True, "right": True, "walk": (90, 1190), "paths": [], "thought": ""},

    {"image": "room_10.jpg", "floor": [(0, 650), (1280, 650)],
     "left": True, "right": False, "walk": (170, 1110),
     "paths": [{"floor": (700, 650), "end": (700, 470, 0.45), "to": 11, "kind": "depth"}],
     "thought": ""},

    {"image": "room_11.jpg", "floor": [(0, 640), (250, 615), (1280, 615)],
     "left": False, "right": False, "walk": (310, 800),
     "paths": [{"floor": (640, 615), "end": (975, 505, 0.45), "to": 10, "kind": "depth"}],
     "thought": ""},
]


def floor_y_at(points, x):
    """Height of the floor line at x (straight lines between the points)."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


class NoWalls:
    """An empty 'platform' far away, so the player's normal move code
    keeps him inside the screen without bumping into anything."""
    rect = pygame.Rect(-5000, -5000, 1, 1)
    one_way = True


class KeysWithout:
    """The pressed keys, but pretending one key is not pressed."""
    def __init__(self, keys, blocked):
        self.keys = keys
        self.blocked = blocked

    def __getitem__(self, key):
        return False if key == self.blocked else self.keys[key]


class NoKeys:
    """Pretends that no key is pressed (for cutscenes)."""
    def __getitem__(self, key):
        return False


class PathWalk:
    """The player walking along a path into (or out of) the picture."""
    SPEED = 3        # pixels per frame along the path

    def __init__(self, path, t, auto):
        self.path = path
        self.t = t               # 0 = on the floor, 1 = at the far end
        self.auto = auto         # True = walking out by itself
        fx, fy = path["floor"]
        ex, ey, _ = path["end"]
        self.length = max(1, math.hypot(ex - fx, ey - fy))
        self.moving = 0          # +1 going in, -1 coming out, 0 standing

    def step(self, direction):
        self.moving = direction
        self.t += direction * self.SPEED / self.length
        self.t = max(0.0, min(1.0, self.t))

    def position(self):
        fx, fy = self.path["floor"]
        ex, ey, es = self.path["end"]
        x = fx + (ex - fx) * self.t
        y = fy + (ey - fy) * self.t
        scale = 1 + (es - 1) * self.t
        return x, y, scale


class Thought:
    """A short line the archaeologist thinks, typed letter by letter."""
    SPEED = 35        # letters per second
    STAY = 3500       # ms after typing finished

    def __init__(self, text, font):
        self.text = text
        self.font = font
        self.start = pygame.time.get_ticks()

    def letters(self):
        return int((pygame.time.get_ticks() - self.start) / 1000 * self.SPEED)

    @property
    def done(self):
        typed_at = self.start + len(self.text) / self.SPEED * 1000
        return pygame.time.get_ticks() > typed_at + self.STAY

    def draw(self, screen, head_x, head_y):
        """Speech bubble above the player's head."""
        shown = self.text[:self.letters()]
        all_lines = self.text.split("\n")
        lh = self.font.get_linesize() + 2
        w = max(self.font.size(line)[0] for line in all_lines) + 40
        h = len(all_lines) * lh + 22

        box = pygame.Rect(0, 0, w, h)
        box.midbottom = (head_x, head_y - 24)
        box.left = max(10, min(box.left, screen.get_width() - w - 10))
        box.top = max(10, box.top)
        tail_x = max(box.left + 20, min(head_x, box.right - 20))

        # shadow, bubble, border
        pygame.draw.rect(screen, (70, 70, 80), box.move(5, 5), border_radius=10)
        tail = [(tail_x - 12, box.bottom - 4), (tail_x + 6, box.bottom - 4), (tail_x - 6, box.bottom + 16)]
        pygame.draw.polygon(screen, (70, 70, 80), [(x + 5, y + 5) for x, y in tail])
        pygame.draw.rect(screen, (250, 248, 240), box, border_radius=10)
        pygame.draw.rect(screen, (20, 20, 25), box, 3, border_radius=10)
        pygame.draw.polygon(screen, (250, 248, 240), tail)
        pygame.draw.line(screen, (20, 20, 25), tail[0], tail[2], 3)
        pygame.draw.line(screen, (20, 20, 25), tail[1], tail[2], 3)

        y = box.y + 11
        for line in shown.split("\n"):
            surf = self.font.render(line, True, (25, 20, 20))
            screen.blit(surf, (box.centerx - surf.get_width() // 2, y))
            y += lh


class Hotspot:
    """Something in a room you can click on."""
    def __init__(self, name, room, image, center, glow=False):
        self.name = name
        self.room = room
        self.image = image
        self.rect = image.get_rect(center=center)
        self.click_rect = self.rect.inflate(16, 16)
        self.glow = glow
        self.visible = True
        mask = pygame.mask.from_surface(image)
        self.outline = [(x + self.rect.x, y + self.rect.y) for x, y in mask.outline()]

    def set_image(self, image):
        """Swap the picture, keeping the same centre (used for animations)."""
        self.image = image
        self.rect = image.get_rect(center=self.rect.center)
        mask = pygame.mask.from_surface(image)
        self.outline = [(x + self.rect.x, y + self.rect.y) for x, y in mask.outline()]

    def hovered(self, mouse):
        return self.visible and self.click_rect.collidepoint(mouse)

    def draw(self, screen, hover):
        if not self.visible:
            return
        if self.glow:
            strength = 0.6 + 0.4 * math.sin(pygame.time.get_ticks() / 400)
            area = self.rect.inflate(70, 50)
            g = pygame.Surface(area.size, pygame.SRCALPHA)
            for i in range(8):
                ring = g.get_rect().inflate(-i * 8, -i * 6)
                pygame.draw.ellipse(g, (255, 210, 120, int(12 * strength)), ring)
            screen.blit(g, area.topleft)
        screen.blit(self.image, self.rect)
        if hover and len(self.outline) > 2:
            pygame.draw.lines(screen, (255, 215, 60), True, self.outline, 2)


def clicked(events):
    for e in events:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            return True
    return False


def pressed(events, key):
    for e in events:
        if e.type == pygame.KEYDOWN and e.key == key:
            return True
    return False


class SignPopup:
    """The stone sign shown big, with words carved on it."""
    def __init__(self, image, text, font, close_key):
        h = 650
        w = int(image.get_width() * h / image.get_height())
        self.image = pygame.transform.smoothscale(image, (w, h))
        self.rect = self.image.get_rect(center=(640, 360))
        self.text = text
        self.font = font
        self.close_key = close_key
        self.start = pygame.time.get_ticks()
        self.done = False
        self.after = None

    def handle(self, events):
        if pygame.time.get_ticks() - self.start < 400:
            return
        if clicked(events) or pressed(events, self.close_key):
            self.done = True

    def draw(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        screen.blit(shade, (0, 0))
        screen.blit(self.image, self.rect)
        lines = self.text.split("\n")
        y = self.rect.centery - len(lines) * self.font.get_linesize() // 2 + 10
        for line in lines:
            dark = self.font.render(line, True, (40, 40, 45))
            light = self.font.render(line, True, (120, 230, 255))
            x = self.rect.centerx - light.get_width() // 2
            screen.blit(dark, (x + 2, y + 2))
            screen.blit(light, (x, y))
            y += self.font.get_linesize()


class CardPopup:
    """The tree card burns and becomes the fire card (frame animation)."""
    APPEAR = 600       # tree card fades in
    BURN = 1800        # the burning frames play
    HEIGHT = 600

    def __init__(self, frames, font, close_key):
        self.frames = []
        for f in frames:
            w = int(f.get_width() * self.HEIGHT / f.get_height())
            self.frames.append(pygame.transform.smoothscale(f, (w, self.HEIGHT)))
        self.rect = self.frames[0].get_rect(center=(640, 320))
        self.font = font
        self.close_key = close_key
        self.start = pygame.time.get_ticks()
        self.done = False
        self.after = None

    def handle(self, events):
        if pygame.time.get_ticks() - self.start > self.APPEAR + self.BURN + 500:
            self.done = True

    def draw(self, screen):
        t = pygame.time.get_ticks() - self.start
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        screen.blit(shade, (0, 0))

        if t < self.APPEAR:
            frame = self.frames[0].copy()
            frame.set_alpha(int(255 * t / self.APPEAR))
            screen.blit(frame, self.rect)
        else:
            # smooth: blend each frame into the next one
            p = min(1.0, (t - self.APPEAR) / self.BURN) * (len(self.frames) - 1)
            i = int(p)
            screen.blit(self.frames[i], self.rect)
            if i + 1 < len(self.frames):
                nxt = self.frames[i + 1]
                nxt.set_alpha(int((p - i) * 255))
                screen.blit(nxt, self.rect)
                nxt.set_alpha(255)


class AreaHotspot:
    """A clickable area of the background (no picture of its own).
    style "box"  = yellow frame on hover
    style "glow" = warm light on hover"""
    def __init__(self, name, room, rect, style="box"):
        self.name = name
        self.room = room
        self.rect = pygame.Rect(rect)
        self.click_rect = self.rect
        self.style = style
        self.visible = True
        self.light = None
        if style == "glow":
            self.light = pygame.Surface(self.rect.size)
            w, h = self.rect.size
            for i in range(14):
                k = i / 14
                ring = pygame.Rect(0, 0, int(w * (1.3 - k)), int(h * (1.2 - k)))
                ring.center = (w // 2, h // 2)
                pygame.draw.ellipse(self.light, (int(10 + 80 * k), int(6 + 55 * k), int(2 + 15 * k)), ring)

    def hovered(self, mouse):
        return self.visible and self.rect.collidepoint(mouse)

    def draw(self, screen, hover):
        if not hover:
            return
        if self.style == "glow":
            screen.blit(self.light, self.rect, special_flags=pygame.BLEND_RGB_ADD)
        else:
            pygame.draw.rect(screen, (255, 215, 60), self.rect, 3, border_radius=4)


class BookPopup:
    """The hidden book opens, words appear, then it bursts with light."""
    SPEED = 10          # letters per second
    APPEAR = 600
    WAIT = 2200         # after the words are written
    FLASH = 900
    INK = (165, 95, 10)

    def __init__(self, blank, glow, text, font):
        w = 720
        self.blank = pygame.transform.smoothscale(blank, (w, int(blank.get_height() * w / blank.get_width())))
        self.glow = pygame.transform.smoothscale(glow, (w, int(glow.get_height() * w / glow.get_width())))
        self.rect = self.blank.get_rect(center=(640, 360))
        self.text = text
        self.font = font
        self.start = pygame.time.get_ticks()
        self.write_time = len(text.replace("\n", "")) / self.SPEED * 1000
        self.done = False
        self.after = None

    def handle(self, events):
        t = pygame.time.get_ticks() - self.start
        if t > self.APPEAR + self.write_time + self.WAIT + self.FLASH:
            self.done = True

    def page_text(self, shown):
        """Draw the words on a see-through layer, then tilt it like the page."""
        lines = self.text.split("\n")
        lh = self.font.get_linesize()
        width = max(self.font.size(line)[0] for line in lines) + 20
        layer = pygame.Surface((width, lh * len(lines) + 10), pygame.SRCALPHA)
        left = shown
        y = 0
        for line in lines:
            part = line[:max(0, left)]
            left -= len(line)
            if part:
                glow = self.font.render(part, True, (255, 200, 60))
                glow.set_alpha(110)
                ink = self.font.render(part, True, self.INK)
                x = (width - self.font.size(line)[0]) // 2
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    layer.blit(glow, (x + dx, y + dy))
                layer.blit(ink, (x, y))
            y += lh
        max_w = int(self.rect.width * 0.30)
        if layer.get_width() > max_w:
            k = max_w / layer.get_width()
            layer = pygame.transform.smoothscale(layer, (max_w, int(layer.get_height() * k)))
        layer = pygame.transform.rotate(layer, 5)
        layer.set_alpha(225)
        return layer

    def draw(self, screen):
        t = pygame.time.get_ticks() - self.start
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        screen.blit(shade, (0, 0))

        burst_at = self.APPEAR + self.write_time + self.WAIT
        if t < burst_at:
            self.blank.set_alpha(min(255, int(255 * t / self.APPEAR)))
            screen.blit(self.blank, self.rect)
            shown = max(0, int((t - self.APPEAR) / 1000 * self.SPEED))
            layer = self.page_text(shown)
            center = (self.rect.x + int(self.rect.width * 0.70),
                      self.rect.y + int(self.rect.height * 0.42))
            screen.blit(layer, layer.get_rect(center=center))
        else:
            screen.blit(self.glow, self.glow.get_rect(center=self.rect.center))
            white = pygame.Surface(screen.get_size())
            white.fill((255, 245, 220))
            white.set_alpha(max(0, 255 - int(255 * (t - burst_at) / self.FLASH)))
            screen.blit(white, (0, 0))


class FallingRock:
    """A rock that warns with a shadow, falls from the ceiling and shatters."""
    WARN = 700         # ms of shadow before it drops
    DAMAGE = 12
    SHATTER_SPEED = 70 # ms per shatter frame

    def __init__(self, x, floor_y, image, shatter_frames):
        self.x = x
        self.floor_y = floor_y
        self.image = image
        self.shatter_frames = shatter_frames
        self.size = image.get_height() // 2
        self.y = -60.0
        self.vy = 0.0
        self.start = pygame.time.get_ticks()
        self.state = "warn"
        self.angle = random.uniform(0, 360)
        self.spin = random.choice([-4, -3, 3, 4])

    @property
    def rect(self):
        s = int(self.size * 0.8)
        return pygame.Rect(int(self.x - s), int(self.y - s), s * 2, s * 2)

    def update(self):
        """Returns 'landed' on the frame it hits the floor."""
        now = pygame.time.get_ticks()
        if self.state == "warn":
            if now - self.start > self.WARN:
                self.state = "fall"
        elif self.state == "fall":
            self.vy += 1.1
            self.y += self.vy
            self.angle += self.spin
            if self.y + self.size * 0.6 >= self.floor_y:
                self.shatter(now)
                return "landed"
        elif self.state == "shatter":
            if now - self.start > self.SHATTER_SPEED * len(self.shatter_frames):
                self.state = "gone"
        return None

    def shatter(self, now):
        self.state = "shatter"
        self.start = now

    def draw(self, screen):
        if self.state == "gone":
            return
        if self.state == "shatter":
            i = (pygame.time.get_ticks() - self.start) // self.SHATTER_SPEED
            frame = self.shatter_frames[min(i, len(self.shatter_frames) - 1)]
            screen.blit(frame, frame.get_rect(midbottom=(int(self.x), int(self.floor_y + 4))))
            return

        if self.state == "warn":
            k = (pygame.time.get_ticks() - self.start) / self.WARN * 0.5
        else:
            k = 0.5 + 0.5 * max(0.0, min(1.0, (self.y + 60) / (self.floor_y + 60)))
        w = int(self.size * 2.2 * k) + 4
        shadow = pygame.Surface((w, w // 3 + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(150 * k) + 40), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(int(self.x), int(self.floor_y - 4))))

        if self.state == "fall":
            img = pygame.transform.rotate(self.image, self.angle)
            screen.blit(img, img.get_rect(center=(int(self.x), int(self.y))))



class FancyBar:
    """HP bar drawn from two pictures: the full bar and the empty bar.
    x0..x1 = where the coloured part starts and ends inside the picture."""
    def __init__(self, full, empty, x0, x1, scale=1.0, thick=1.0):
        def size(im):
            return pygame.transform.smoothscale(
                im, (int(im.get_width() * scale), int(im.get_height() * scale * thick)))
        self.full = size(full)
        self.empty = size(empty)
        self.x0 = int(x0 * scale)
        self.x1 = int(x1 * scale)

    def draw(self, screen, ratio, **anchor):
        rect = self.empty.get_rect(**anchor)
        screen.blit(self.empty, rect)
        ratio = max(0.0, min(1.0, ratio))
        cut = self.x0 + int((self.x1 - self.x0) * ratio) if ratio > 0 else 0
        screen.blit(self.full, rect.topleft, (0, 0, cut, self.full.get_height()))
        return rect



class TranslateDesk:
    """The moon book (alphabet + drawing) next to the open journal.
    Left journal page: the Lunari pieces. Right page: the player types the English."""
    INK = (70, 38, 14)
    DONE_INK = (30, 70, 40)
    BAD = (190, 40, 30)
    CHOICE_DELAY = 1500

    def __init__(self, book, page, pieces, typed, runes, font, small_font):
        bw = 640
        self.book = pygame.transform.smoothscale(book, (bw, int(book.get_height() * bw / book.get_width())))
        self.book_rect = self.book.get_rect(midleft=(12, 360))
        self.page = pygame.transform.smoothscale(page, (300, 450))
        self.left = self.page.get_rect(topleft=(662, 110))
        self.right = self.page.get_rect(topleft=(self.left.right, 110))
        self.pieces = pieces
        self.typed = typed                     # list of strings, kept after closing
        self.solved = [self.same(t, p) for t, p in zip(typed, pieces)]
        self.runes = [runes.render_block(p, self.left.width - 40, line_gap=3) for p in pieces]
        self.font = font
        self.small = small_font
        self.active = self.first_open()
        self.caret = [len(t) for t in typed] 
        self.bad_until = 0
        self.solved_at = pygame.time.get_ticks() if all(self.solved) else None
        self.buttons = [pygame.Rect(0, 0, 360, 48), pygame.Rect(0, 0, 360, 48)]
        self.buttons[0].center = (640 - 200, 665)
        self.buttons[1].center = (640 + 200, 665)
        self.choice = None
        self.done = False
        self.after = None

    @staticmethod
    def clean(text):
        letters = "".join(c.lower() if c.isalnum() else " " for c in text)
        return " ".join(letters.split())

    def same(self, typed, piece):
        return self.clean(typed) == self.clean(piece)

    def first_open(self):
        for i, ok in enumerate(self.solved):
            if not ok:
                return i
        return None

    def slot(self, rect, i):
        h = (rect.height - 60) // len(self.pieces)
        return pygame.Rect(rect.x + 18, rect.y + 30 + h * i, rect.width - 36, h - 8)

    @property
    def choosing(self):
        return self.solved_at is not None and \
            pygame.time.get_ticks() - self.solved_at > self.CHOICE_DELAY

    def handle(self, events):
        mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and not self.choosing:
                self.done = True                # close, the typed words are kept
                return
            if self.choosing:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    for name, b in zip(("stay", "run"), self.buttons):
                        if b.collidepoint(mouse):
                            self.choice = name
                            self.done = True
                continue
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i in range(len(self.pieces)):
                    if self.slot(self.right, i).collidepoint(mouse) and not self.solved[i]:
                        self.active = i
                        self.caret[i] = len(self.typed[i])
            if e.type != pygame.KEYDOWN or self.active is None:
                continue
            i = self.active
            text, c = self.typed[i], self.caret[i]
            if e.key == pygame.K_BACKSPACE:
                if c > 0:
                    self.typed[i] = text[:c - 1] + text[c:]
                    self.caret[i] = c - 1
            elif e.key == pygame.K_DELETE:
                self.typed[i] = text[:c] + text[c + 1:]
            elif e.key == pygame.K_LEFT:
                self.caret[i] = max(0, c - 1)
            elif e.key == pygame.K_RIGHT:
                self.caret[i] = min(len(text), c + 1)
            elif e.key == pygame.K_HOME:
                self.caret[i] = 0
            elif e.key == pygame.K_END:
                self.caret[i] = len(text)
            elif e.key == pygame.K_RETURN:
                if self.same(self.typed[i], self.pieces[i]):
                    self.solved[i] = True
                    self.typed[i] = self.pieces[i]          # show it neat
                    self.active = self.first_open()
                    if self.active is not None:
                        self.caret[self.active] = len(self.typed[self.active])
                    if self.active is None:
                        self.solved_at = pygame.time.get_ticks()
                else:
                    self.bad_until = pygame.time.get_ticks() + 500
            elif e.key in (pygame.K_UP, pygame.K_DOWN):
                step = -1 if e.key == pygame.K_UP else 1
                j = i
                for _ in self.pieces:
                    j = (j + step) % len(self.pieces)
                    if not self.solved[j]:
                        self.active = j
                        self.caret[j] = len(self.typed[j])
                        break
            else:
                ch = self.letter_of(e)
                if ch and len(text) < len(self.pieces[i]) + 15:
                    self.typed[i] = text[:c] + ch + text[c:]
                    self.caret[i] = c + 1

    @staticmethod
    def letter_of(e):
        """The English letter of a key, even when the keyboard is set to another language."""
        if e.unicode and e.unicode.isascii() and e.unicode.isprintable():
            return e.unicode
        if pygame.K_a <= e.key <= pygame.K_z:
            return chr(e.key)
        if e.key == pygame.K_SPACE:
            return " "
        return ""

    def wrap(self, text, width):
        lines, line = [], ""
        for word in text.split(" "):
            test = word if not line else line + " " + word
            if self.font.size(test)[0] > width and line:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
        return lines

    def draw(self, screen):
        now = pygame.time.get_ticks()
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 210))
        screen.blit(shade, (0, 0))
        screen.blit(self.book, self.book_rect)
        screen.blit(self.page, self.left)
        screen.blit(self.page, self.right)
        pygame.draw.line(screen, (60, 35, 15), self.left.topright, self.left.bottomright, 3)

        title = self.small.render("Translate the pieces into your journal", True, (235, 215, 170))
        screen.blit(title, title.get_rect(midbottom=(self.left.right, self.left.top - 10)))

        for i in range(len(self.pieces)):
            ls = self.slot(self.left, i)
            screen.blit(self.runes[i], self.runes[i].get_rect(center=ls.center))

            rs = self.slot(self.right, i)
            if i == self.active and not self.choosing:
                box = pygame.Surface(rs.size, pygame.SRCALPHA)
                box.fill((255, 240, 200, 70))
                screen.blit(box, rs)
                color = self.BAD if now < self.bad_until else (120, 80, 40)
                shake = int(math.sin(now / 25) * 4) if now < self.bad_until else 0
                pygame.draw.rect(screen, color, rs.move(shake, 0), 2, border_radius=6)
            ink = self.DONE_INK if self.solved[i] else self.INK
            text = self.typed[i]
            if i == self.active and not self.choosing:
                c = self.caret[i]
                text = text[:c] + "|" + text[c:]
            lines = self.wrap(text, rs.width - 12)
            lh = self.font.get_linesize()
            y = rs.centery - lh * len(lines) // 2
            for line in lines:
                img = self.font.render(line, True, ink)
                screen.blit(img, img.get_rect(midtop=(rs.centerx, y)))
                y += lh

        if not self.choosing:
            hint = self.small.render("Type   LEFT/RIGHT move   ENTER check   UP/DOWN line   ESC close",
                                     True, (200, 185, 150))
            screen.blit(hint, hint.get_rect(midtop=(640, self.right.bottom + 12)))
            return

        # all four pieces translated: the choice
        q = self.small.render("Whoever breaks all four seals becomes the fifth guardian...",
                              True, (240, 220, 180))
        screen.blit(q, q.get_rect(center=(640, 605)))
        mouse = pygame.mouse.get_pos()
        for label, b in zip(("Stay - keep the doors sealed", "Run - break the seals"), self.buttons):
            hover = b.collidepoint(mouse)
            pygame.draw.rect(screen, (40, 25, 20), b, border_radius=10)
            pygame.draw.rect(screen, (255, 200, 60) if hover else (160, 120, 70), b, 2, border_radius=10)
            t = self.small.render(label, True, (240, 220, 180))
            screen.blit(t, t.get_rect(center=b.center))
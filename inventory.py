import pygame
from story import wrap_text

SCREEN_W, SCREEN_H = 1280, 720


# ---------- small pictures drawn with code (no image files needed) ----------
def draw_bag(size=56):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    body = pygame.Rect(size * 0.12, size * 0.30, size * 0.76, size * 0.62)
    pygame.draw.ellipse(s, (70, 40, 20), body.inflate(4, 4))
    pygame.draw.ellipse(s, (130, 80, 40), body)
    pygame.draw.ellipse(s, (160, 105, 55), body.inflate(-size * 0.25, -size * 0.30).move(-3, -4))
    pygame.draw.arc(s, (70, 40, 20), pygame.Rect(size * 0.30, size * 0.06, size * 0.40, size * 0.40),
                    0.2, 2.9, 4)                                     # handle
    flap = [(size * 0.18, size * 0.38), (size * 0.82, size * 0.38), (size * 0.62, size * 0.60),
            (size * 0.38, size * 0.60)]
    pygame.draw.polygon(s, (105, 62, 30), flap)
    pygame.draw.polygon(s, (60, 35, 18), flap, 2)
    pygame.draw.circle(s, (230, 190, 90), (size // 2, int(size * 0.58)), max(3, size // 14))
    return s


def draw_journal(size=56):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    book = pygame.Rect(size * 0.22, size * 0.10, size * 0.56, size * 0.80)
    pygame.draw.rect(s, (120, 30, 30), book, border_radius=4)
    pygame.draw.rect(s, (230, 190, 110), book, 2, border_radius=4)
    pygame.draw.line(s, (230, 190, 110), (book.x + 7, book.y + 4), (book.x + 7, book.bottom - 4), 2)
    return s


def draw_scroll(size=56):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    paper = pygame.Rect(size * 0.20, size * 0.14, size * 0.60, size * 0.72)
    pygame.draw.rect(s, (225, 200, 150), paper)
    for y in (paper.top, paper.bottom):                             # rolled ends
        r = pygame.Rect(paper.x - 5, y - 5, paper.width + 10, 10)
        pygame.draw.rect(s, (190, 160, 110), r, border_radius=5)
        pygame.draw.rect(s, (110, 80, 50), r, 2, border_radius=5)
    for n in range(4):
        y = paper.y + 10 + n * 8
        pygame.draw.line(s, (120, 90, 60), (paper.x + 6, y), (paper.right - 6, y), 2)
    return s


def fit(img, box):
    """Scale an image to fit in a box size, keeping its shape."""
    k = min(box[0] / img.get_width(), box[1] / img.get_height())
    return pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)),
                                              max(1, int(img.get_height() * k))))


class Inventory:
    """The bag: a small icon in the top-right corner, and a window with the items."""
    STATES = ("room", "castle", "exploration")
    KEY = pygame.K_b
    SLOT = 84

    def __init__(self, game):
        self.g = game
        self.open = False
        self.selected = "journal"
        load = lambda p: pygame.image.load(p).convert_alpha()
        self.icon = fit(load("img/ui/bag.png"), (54, 54))
        self.icon_rect = self.icon.get_rect(topright=(SCREEN_W - 12, 10))
        self.panel = pygame.Rect(0, 0, 880, 470)
        self.panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        self.pics = {
            "journal": load("img/ui/journal.png"),
            "status": load("img/ui/scroll.png"),
            "key": load("img/key.png"),
            "card": load("img/intro/card_tree.png"),
            "fire_card": load("img/intro/card_fire.png"),
            "potion": load("img/intro/potion.png"),
        }
        self.message = ""
        self.message_until = 0
        self.button = pygame.Rect(0, 0, 200, 44)

    # ---------- what is in the bag ----------
    def items(self):
        g = self.g
        items = ["journal", "status"]
        if g.has_key:
            items.append("key")
        if g.has_fire:
            items.append("fire_card")
        elif g.has_tree_card:
            items.append("card")
        if g.potions > 0:
            items.append("potion")
        return items

    def info(self, name):
        g = self.g
        if name == "journal":
            return "Journal", (f"Dr. {g.player_name or 'Archaeologist'}'s journal. "
                               f"The strange writing is copied inside. "
                               f"Pieces found: {g.fragments_found}/4."), "Open"
        if name == "status":
            p = g.player
            text = (f"Dr. {g.player_name or 'Archaeologist'}\n"
                    f"HP: {p.hp} / {p.max_hp}\n"
                    f"Strength: {p.strength}\n"
                    f"Speed: {p.speed}\n"
                    f"Stage: {g.stage}\n"
                    f"Enemies defeated: {g.enemies_defeated}")
            return "Status", text, None
        if name == "key":
            return "Small golden key", "It was resting in a statue's hand. It opened the old chest.", None
        if name == "card":
            return "Golden tree card", "A card with a golden tree. It feels warm in my hand.", None
        if name == "fire_card":
            return "Burned card", "The tree card burned in my hand. Since then, fire answers me.", None
        if name == "potion":
            return f"Red potion  x{g.potions}", "A red potion. Drinking it restores all HP.", "Drink"
        return name, "", None

    # ---------- input ----------
    def update(self):
        """Returns True while the bag is open (the game is paused)."""
        g = self.g
        if g.state not in self.STATES:
            self.open = False
            return False
        mouse = pygame.mouse.get_pos()
        keep = []
        for e in g.events:
            toggle = (e.type == pygame.KEYDOWN and e.key == self.KEY) or \
                     (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                      and self.icon_rect.collidepoint(mouse))
            if toggle and not g.journal_open:
                self.open = not self.open
                if self.open:
                    self.background = g.screen.copy()
                    if self.selected not in self.items():
                        self.selected = "journal"
                continue                        # the click does not reach the game
            if self.open:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self.open = False
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.click(mouse)
                continue
            keep.append(e)
        g.events = keep
        if self.open:
            self.draw()
        return self.open

    def slot_rects(self):
        rects = []
        for i, name in enumerate(self.items()):
            r = pygame.Rect(0, 0, self.SLOT, self.SLOT)
            r.topleft = (self.panel.x + 30 + (i % 3) * (self.SLOT + 14),
                         self.panel.y + 70 + (i // 3) * (self.SLOT + 14))
            rects.append((name, r))
        return rects

    def click(self, mouse):
        for name, r in self.slot_rects():
            if r.collidepoint(mouse):
                self.selected = name
                return
        if self.button.collidepoint(mouse):
            self.use(self.selected)

    def use(self, name):
        g = self.g
        if name == "journal":
            self.open = False
            g.journal_open = True
            g.journal_bg = self.background
        elif name == "potion":
            if g.player.hp >= g.player.max_hp:
                self.say("I'm not hurt. I'll keep it.")
                return
            g.potions -= 1
            g.player.hp = g.player.max_hp
            self.say("HP restored!")
            if g.potions == 0:
                self.selected = "journal"

    def say(self, text):
        self.message = text
        self.message_until = pygame.time.get_ticks() + 1800

    # ---------- drawing ----------
    def draw_icon(self):
        if self.g.state not in self.STATES or self.open or self.g.journal_open:
            return
        g = self.g
        hover = self.icon_rect.collidepoint(pygame.mouse.get_pos())
        c = self.icon_rect.center
        pygame.draw.circle(g.screen, (225, 200, 150), c, 31)                 # parchment disc
        pygame.draw.circle(g.screen, (255, 215, 60) if hover else (90, 60, 30), c, 31, 3)
        g.screen.blit(self.icon, self.icon_rect)

    def draw(self):
        g = self.g
        screen = g.screen
        screen.blit(self.background, (0, 0))
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        screen.blit(shade, (0, 0))

        paper = pygame.transform.smoothscale(g.page_image, self.panel.size)
        screen.blit(paper, self.panel)
        pygame.draw.rect(screen, (80, 50, 25), self.panel, 4, border_radius=6)
        title = g.font.render("Bag", True, (70, 40, 20))
        screen.blit(title, (self.panel.x + 30, self.panel.y + 18))
        hint = g.small_font.render("B / ESC  close", True, (90, 60, 35))
        screen.blit(hint, hint.get_rect(topright=(self.panel.right - 24, self.panel.y + 26)))

        mouse = pygame.mouse.get_pos()
        for name, r in self.slot_rects():
            box = pygame.Surface(r.size, pygame.SRCALPHA)
            box.fill((60, 35, 15, 70))
            screen.blit(box, r)
            border = (255, 200, 60) if name == self.selected else \
                     ((170, 120, 60) if r.collidepoint(mouse) else (110, 75, 40))
            pygame.draw.rect(screen, border, r, 3, border_radius=8)
            pic = fit(self.pics[name], (r.width - 16, r.height - 16))
            screen.blit(pic, pic.get_rect(center=r.center))
            if name == "potion" and g.potions > 1:
                n = g.small_font.render(f"x{g.potions}", True, (255, 240, 220))
                screen.blit(n, n.get_rect(bottomright=(r.right - 4, r.bottom - 2)))

        # details of the selected item, on the right half
        right = pygame.Rect(self.panel.x + 360, self.panel.y + 60, self.panel.width - 390, 360)
        name, text, action = self.info(self.selected)
        big = fit(self.pics[self.selected], (130, 150))
        screen.blit(big, big.get_rect(midtop=(right.centerx, right.y)))
        head = g.font.render(name, True, (70, 40, 20))
        y = right.y + 165
        screen.blit(head, head.get_rect(midtop=(right.centerx, y)))
        y += head.get_height() + 10
        for paragraph in text.split("\n"):
            for line in wrap_text(paragraph, g.thought_font, right.width - 20):
                img = g.thought_font.render(line, True, (80, 50, 28))
                screen.blit(img, img.get_rect(midtop=(right.centerx, y)))
                y += g.thought_font.get_linesize()

        if action:
            self.button.midbottom = (right.centerx, self.panel.bottom - 22)
            hover = self.button.collidepoint(mouse)
            pygame.draw.rect(screen, (60, 35, 20), self.button, border_radius=10)
            pygame.draw.rect(screen, (255, 200, 60) if hover else (160, 120, 70), self.button, 2,
                             border_radius=10)
            t = g.small_font.render(action, True, (240, 220, 180))
            screen.blit(t, t.get_rect(center=self.button.center))
        else:
            self.button.topleft = (-500, -500)

        if self.message and pygame.time.get_ticks() < self.message_until:
            m = g.small_font.render(self.message, True, (150, 30, 30))
            screen.blit(m, m.get_rect(midbottom=(self.panel.x + 180, self.panel.bottom - 30)))

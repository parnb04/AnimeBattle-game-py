import pygame

LETTER_1 = (
    "To Dr. {name},\n\n"
    "Deep in the Darkwood forest, our survey team found something that should "
    "not exist: ruins that appear only once a year, and only for a few days.\n\n"
    "No map marks this place. No archive mentions it. "
    "Not even the oldest legends speak of it."
)

LETTER_2 = (
    "We need you.\n\n"
    "The team we sent inside has not returned. We do not know what happened "
    "to them, and we will not risk sending anyone else.\n\n"
    "You must go alone. The forest is dangerous, and something in it has "
    "begun to change.\n\n"
    "The ruins will vanish again soon. Only you can do this."
)

INSTITUTE = "The Meridian Institute"


def wrap_text(text, font, width):
    """Split text into lines that fit inside width. Keeps \\n line breaks."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            test = (line + " " + word).strip()
            if font.size(test)[0] <= width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


class Letter:
    """One open letter: parchment image + text written letter by letter."""
    SPEED = 40          # letters per second
    INK = (60, 35, 20)
    SIGN_INK = (110, 25, 20)

    def __init__(self, image, text, font, sign=None, sign_font=None):
        h = 680
        w = int(image.get_width() * h / image.get_height())
        self.image = pygame.transform.smoothscale(image, (w, h))
        self.rect = self.image.get_rect(midtop=(640, 20))
        self.font = font
        self.sign = sign
        self.sign_font = sign_font
        self.lines = wrap_text(text, font, w - 140)
        self.total = sum(len(line) for line in self.lines)
        self.restart()

    def restart(self):
        self.start = pygame.time.get_ticks()

    def shown(self):
        return int((pygame.time.get_ticks() - self.start) / 1000 * self.SPEED)

    def finished(self):
        return self.shown() >= self.total

    def skip(self):
        self.start = -10 ** 9

    def draw(self, screen):
        screen.blit(self.image, self.rect)
        left = self.shown()
        y = self.rect.y + 130
        for line in self.lines:
            part = line[:max(0, left)]
            left -= len(line)
            if part:
                screen.blit(self.font.render(part, True, self.INK), (self.rect.x + 70, y))
            y += self.font.get_linesize() + 6

        if self.sign and self.finished():
            s = self.sign_font.render(self.sign, True, self.SIGN_INK)
            center = (self.rect.x + int(self.rect.width * 0.37),
                      self.rect.y + int(self.rect.height * 0.835))
            screen.blit(s, s.get_rect(center=center))


class AcceptBanner:
    """Ribbon asking 'Accept the mission?' with Yes / No buttons."""
    INK = (60, 35, 20)

    def __init__(self, image, font, button_font):
        w = 700
        h = int(image.get_height() * w / image.get_width())
        self.image = pygame.transform.smoothscale(image, (w, h))
        self.rect = self.image.get_rect(center=(640, 300))
        self.font = font
        self.button_font = button_font
        self.yes = pygame.Rect(0, 0, 150, 52)
        self.no = pygame.Rect(0, 0, 150, 52)
        self.yes.center = (640 - 110, self.rect.bottom + 50)
        self.no.center = (640 + 110, self.rect.bottom + 50)
        self.start = pygame.time.get_ticks()
        self.answer = None              # "yes" / "no" when chosen

    def handle(self, events, mouse):
        if pygame.time.get_ticks() - self.start < 300:
            return
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.yes.collidepoint(mouse):
                    self.answer = "yes"
                elif self.no.collidepoint(mouse):
                    self.answer = "no"
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_y:
                    self.answer = "yes"
                elif e.key == pygame.K_n:
                    self.answer = "no"

    def draw_button(self, screen, rect, text, hover):
        pygame.draw.rect(screen, (235, 215, 170), rect, border_radius=8)
        border = (255, 200, 60) if hover else (120, 80, 40)
        pygame.draw.rect(screen, border, rect, 3, border_radius=8)
        label = self.button_font.render(text, True, self.INK)
        screen.blit(label, label.get_rect(center=rect.center))

    def draw(self, screen, mouse):
        appear = min(1.0, (pygame.time.get_ticks() - self.start) / 300)
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, int(190 * appear)))
        screen.blit(shade, (0, 0))

        screen.blit(self.image, self.rect)
        text = self.font.render("Accept the mission?", True, self.INK)
        center = (self.rect.x + int(self.rect.width * 0.51), self.rect.y + int(self.rect.height * 0.47))
        screen.blit(text, text.get_rect(center=center))

        self.draw_button(screen, self.yes, "Yes", self.yes.collidepoint(mouse))
        self.draw_button(screen, self.no, "No", self.no.collidepoint(mouse))




# ---------------------------
# The ancient language (Lunari)
# ---------------------------
# What the 4 pieces really say (the player can only read them at the end)
FRAGMENTS = [
    "I built this place to hide what was lost.",
    "Four souls agreed to guard its doors forever.",
    "Their curse holds as long as no one passes.",
    "Whoever breaks all four seals becomes the fifth guardian.",
]


class Lunari:
    """Writes English text with the Lunari alphabet (one picture per letter)."""
    FILES = {".": "dot", ",": "comma", "?": "q", "!": "ex", ":": "colon", ";": "semi",
             '"': "quote", "(": "lp", ")": "rp", "-": "dash", "'": "apos"}
    BASE = 45            # letter height in the alphabet picture

    def __init__(self, height=26, color=(255, 210, 120), folder="img/lunari"):
        import json
        self.height = height
        scale = height / self.BASE
        offsets = json.load(open(f"{folder}/offsets.json"))
        self.glyphs = {}
        for name, top in offsets.items():
            img = pygame.image.load(f"{folder}/{name}.png").convert_alpha()
            img = pygame.transform.smoothscale(
                img, (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale))))
            img.fill(color + (255,), special_flags=pygame.BLEND_RGBA_MULT)    # white -> colour
            self.glyphs[name] = (img, int((top - 6) * scale))
        self.gap = max(2, int(height * 0.12))      # space between letters
        self.space = int(height * 0.6)             # space between words

    def glyph(self, ch):
        name = self.FILES.get(ch, ch.upper())
        return self.glyphs.get(name)

    def width(self, text):
        w = 0
        for ch in text:
            g = self.glyph(ch)
            w += (g[0].get_width() + self.gap) if g else self.space
        return w

    def render(self, text, count=None):
        """Returns a surface with the first `count` letters of `text` (all if None)."""
        if count is None:
            count = len(text)
        surf = pygame.Surface((self.width(text) + 4, int(self.height * 1.35) + 4), pygame.SRCALPHA)
        x = 2
        for i, ch in enumerate(text):
            if i >= count:
                break
            g = self.glyph(ch)
            if g:
                img, top = g
                surf.blit(img, (x, 2 + top))
                x += img.get_width() + self.gap
            else:
                x += self.space
        return surf

    def render_block(self, text, max_width, count=None, line_gap=8):
        """Several lines; `count` letters in total are shown (all if None)."""
        lines = self.wrap(text, max_width)
        if count is None:
            count = len(text)
        parts = []
        for line in lines:
            parts.append(self.render(line, max(0, count)))
            count -= len(line) + 1
        w = max(p.get_width() for p in parts)
        h = sum(p.get_height() for p in parts) + line_gap * (len(parts) - 1)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        y = 0
        for p in parts:
            surf.blit(p, ((w - p.get_width()) // 2, y))
            y += p.get_height() + line_gap
        return surf

    def wrap(self, text, max_width):
        """Splits text into lines that fit in max_width."""
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if self.width(test) > max_width and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines



# ---------------------------
# Ending: Run
# ---------------------------
RUN_LETTER = (
    "To The Meridian Institute,\n\n"
    "The castle in the Darkwood is not a ruin. It is a prison. Four guardians "
    "kept its doors sealed, and I broke the seals.\n\n"
    "Your team never came back because they were never meant to.\n\n"
    "Something is coming. Warn everyone.\n\n"
    "Dr. {name}"
)

RUN_REPLY = (
    "Dr. {name},\n\n"
    "Thank you. You did exactly what we hoped you would.\n\n"
    "The seals are broken, and what was locked away now belongs to us.\n\n"
    "Rest now. We will be in touch."
)


# ---------------------------
# Ending: Stay
# ---------------------------
STAY_LETTER = ("To whoever reads this: I came for answers and found a prison. "
               "Do not break the seals. I stayed, so they would sleep. "
               "Dr. {name}, the fifth guardian.")
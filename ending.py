import math
import pygame
from castle import ROOMS, floor_y_at, Thought
from story import Letter, RUN_LETTER, RUN_REPLY, INSTITUTE, STAY_LETTER, wrap_text

SCREEN_W, SCREEN_H = 1280, 720


class RunEnding:
    """The player breaks the seals and runs: a short film played scene by scene.
    Each scene: (kind, room, start x, end x, length in ms)."""
    FADE = 300
    SCENES = [
        ("walk", 10, 1050, 170, 3400),
        ("walk", 9, 1150, 100, 3400),
        ("walk", 8, 1150, 120, 3400),
        ("walk", 7, 1150, 110, 3400),
        ("walk", 6, 1200, 60, 3400),
        ("walk", 5, 1150, 90, 3400),
        ("doors", 4, 1000, 200, 8000),
        ("walk", 3, 1200, 170, 3400),
        ("walk", 2, 1200, 80, 3400),
        ("forest", 0, 1240, 640, 10000),
        ("legends", None, 0, 0, 6500),
        ("words", None, 0, 0, 6500),
        ("letters", None, 0, 0, 0),
    ]

    def __init__(self, game):
        self.g = game
        self.index = 0
        self.start = pygame.time.get_ticks()
        self.thought = None
        self.letters = None
        self.seal_start = None
        run = game.player.animator.animations["run"].frames
        self.walk_left = [pygame.transform.flip(f, True, False) for f in run]

    # ---------- helpers ----------
    @property
    def scene(self):
        return self.SCENES[self.index]

    def next_scene(self):
        self.index += 1
        self.start = pygame.time.get_ticks()
        self.thought = None

    def say(self, text):
        self.thought = Thought(text, self.g.thought_font)

    def draw_walker(self, x, room, moving=True, frame=None):
        y = floor_y_at(ROOMS[room]["floor"], x) if room is not None else 680
        if frame is None:
            if moving:
                frame = self.walk_left[(pygame.time.get_ticks() // 120) % len(self.walk_left)]
            else:
                frame = pygame.transform.flip(self.g.player.animator.animations["idle"].frames[0],
                                              True, False)
        self.g.screen.blit(frame, frame.get_rect(midbottom=(int(x), int(y))))
        if self.thought:
            self.thought.draw(self.g.screen, int(x), int(y) - frame.get_height())

    def fade(self, t, length):
        """Black at the start and end of a scene."""
        a = 0
        if t < self.FADE:
            a = 255 * (1 - t / self.FADE)
        elif length and t > length - self.FADE:
            a = 255 * (t - (length - self.FADE)) / self.FADE
        if a > 0:
            black = pygame.Surface((SCREEN_W, SCREEN_H))
            black.set_alpha(int(a))
            self.g.screen.blit(black, (0, 0))

    # ---------- scenes ----------
    def scene_walk(self, t, room, x0, x1, length):
        self.g.castle_room = room
        self.g.draw_room_image()
        p = min(1, t / length)
        self.draw_walker(x0 + (x1 - x0) * p, room)

    def scene_doors(self, t, room, x0, x1, length):
        g = self.g
        now = pygame.time.get_ticks()
        burst = 2000
        if t < burst:                                   # walks in and stops
            g.screen.blit(g.portal_room_image, (0, 0))
            x = x0 + (700 - x0) * min(1, t / 1700)
            self.draw_walker(x, room, moving=t < 1700)
            return
        if not getattr(self, "doors_burst", False):
            self.doors_burst = True
            g.effects.shake(16, 1500)
            self.say("The seals... they're breaking!")
        g.screen.blit(g.room_bg_unlocked, (0, 0))
        # the two vortexes blow light out of the doors
        k = (now // 90) % 8
        for side, (pos, _) in g.DOOR_TARGET.items():
            v = g.vortex[side][k]
            g.screen.blit(v, v.get_rect(center=pos), special_flags=pygame.BLEND_RGB_ADD)
        if t < burst + 300:                             # white flash
            flash = pygame.Surface((SCREEN_W, SCREEN_H))
            flash.fill((255, 245, 230))
            flash.set_alpha(int(255 * (1 - (t - burst) / 300)))
            g.screen.blit(flash, (0, 0))
        run_at = length - 2200
        if t < run_at:                                  # the wind pushes him back
            x = 700 + 60 * min(1, (t - burst) / 500)
            self.draw_walker(x, room, moving=False)
        else:
            x = 760 + (x1 - 760) * min(1, (t - run_at) / 2200)
            self.draw_walker(x, room)

    def scene_forest(self, t, room, x0, x1, length):
        g = self.g
        g.screen.blit(g.castle_images[0], (0, 0))
        if t < 3000:
            self.draw_walker(x0 + (x1 - x0) * t / 3000, room)
            return
        if t < 6500:
            if self.thought is None:
                self.say("I have to write to the Institute...\nThey need to know what's in there.")
            self.draw_walker(x1, room, moving=False)
            return
        t -= 2300
        if not getattr(self, "forest_rumble", False):    # a roar behind him
            self.forest_rumble = True
            self.thought = None
            g.effects.shake(10, 2500)
        i = min(3, int((t - 4200) / 400))
        self.draw_walker(x1, room, frame=g.look_frames[i])

    def scene_legends(self, t, length):
        g = self.g
        if t < 50:
            g.effects.shake(5, length)
        zoom = 1 + 0.08 * t / length
        img = g.legends_image
        w, h = int(SCREEN_W * zoom), int(SCREEN_H * zoom)
        img = pygame.transform.smoothscale(img, (w, h))
        g.screen.blit(img, ((SCREEN_W - w) // 2, (SCREEN_H - h) // 2))

    def scene_words(self, t, length):
        g = self.g
        g.screen.fill((0, 0, 0))
        for i, (line, at) in enumerate((("The legends are free...", 500),
                                        ("...and they will find you.", 2600))):
            if t < at:
                continue
            img = g.ending_font.render(line, True, (230, 215, 190))
            img.set_alpha(min(255, int(255 * (t - at) / 800)))
            g.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, 320 + i * 60)))

    def scene_letters(self):
        """Returns True when the film is over."""
        g = self.g
        if self.letters is None:
            name = g.player_name or "Archaeologist"
            self.letters = [Letter(g.letter_plain, RUN_LETTER.format(name=name), g.letter_font),
                            Letter(g.letter_sealed, RUN_REPLY.format(name=name), g.letter_font,
                                   INSTITUTE, g.sign_font)]
            self.letter_index = 0
            self.letters[0].restart()
        letter = self.letters[self.letter_index]
        if self.seal_start is None:
            for e in g.events:
                if (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE) or \
                   (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                    if not letter.finished():
                        letter.skip()
                    elif self.letter_index == 0:
                        self.letter_index = 1
                        self.letters[1].restart()
                    else:
                        self.seal_start = pygame.time.get_ticks()
                        g.effects.shake(6, 600)
                    break
        g.screen.blit(g.desk_dark, (0, 0))
        letter = self.letters[self.letter_index]
        letter.draw(g.screen)
        if self.seal_start is None:
            if letter.finished():
                hint = g.small_font.render("Click to continue", True, (220, 200, 170))
                g.screen.blit(hint, hint.get_rect(midbottom=(SCREEN_W // 2, SCREEN_H - 8)))
            return False
        # the Institute's name glows purple, then everything goes dark
        t = pygame.time.get_ticks() - self.seal_start
        cx = letter.rect.x + int(letter.rect.width * 0.36)      # the wax seal
        cy = letter.rect.y + int(letter.rect.height * 0.925)
        k = min(1, t / 800)
        glow = pygame.Surface((300, 200))
        for n in range(8):
            s = k * (n + 1) / 8
            pygame.draw.ellipse(glow, (int(70 * s), int(20 * s), int(100 * s)),
                                glow.get_rect().inflate(-n * 40, -n * 16))
        g.screen.blit(glow, glow.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)
        if t > 1600:
            black = pygame.Surface((SCREEN_W, SCREEN_H))
            black.set_alpha(min(255, int(255 * (t - 1600) / 1200)))
            g.screen.blit(black, (0, 0))
        return t > 3200

    # ---------- main ----------
    def update(self):
        """Plays the current scene. Returns True when everything is over."""
        kind, room, x0, x1, length = self.scene
        t = pygame.time.get_ticks() - self.start
        if kind == "letters":
            return self.scene_letters()
        if t >= length:
            self.next_scene()
            return False
        if kind == "walk":
            self.scene_walk(t, room, x0, x1, length)
        elif kind == "doors":
            self.scene_doors(t, room, x0, x1, length)
        elif kind == "forest":
            self.scene_forest(t, room, x0, x1, length)
        elif kind == "legends":
            self.scene_legends(t, length)
        elif kind == "words":
            self.scene_words(t, length)
        self.fade(t, length)
        return False


class StayEnding:
    """The player stays: writes for the next one, takes the crown,
    sits on the throne and turns to stone while the castle falls."""
    DESK = (1050, 553)                 # where he sits (feet, hidden by the desk)
    DESK_COVER = pygame.Rect(958, 519, 200, 74)   # the far desk drawn over him
    SIT_SCALE = 0.6
    WALK_END = (1050, 553)
    TUNNEL_FLOOR = (640, 615)
    TUNNEL_END = (975, 505, 0.45)
    STAIRS_FOOT = (640, 562)
    THRONE = (640, 462)                # feet on the top step
    TOP_SCALE = 0.68
    HUMAN = 172                        # player height in the normal frames

    SCENES = [("to_desk", 3600), ("write", 17000), ("read", 5000), ("leave", 5600),
              ("collapse", 2400), ("hall", 3200), ("hall", 3200), ("hall", 3200),
              ("crown", 6000), ("climb", 6500), ("turn", 2000),
              ("sit", 2200), ("stone", 6500), ("end", 8000)]
    HALLS = [10, 9, 8]

    def __init__(self, game):
        self.g = game
        self.index = 0
        self.hall_no = 0
        self.start = pygame.time.get_ticks()
        self.thought = None
        self.from_x = game.player.rect.centerx
        self.stage_shook = set()
        run = game.player.animator.animations["run"].frames
        self.walk_left = [pygame.transform.flip(f, True, False) for f in run]
        name = game.player_name or "Archaeologist"
        self.letter = STAY_LETTER.format(name=name)
        self.page = pygame.transform.smoothscale(game.page_image, (380, 560))

    # ---------- helpers ----------
    def blit(self, frame, scale, midbottom, flip=False):
        if flip:
            frame = pygame.transform.flip(frame, True, False)
        if scale != 1:
            frame = pygame.transform.smoothscale(
                frame, (max(1, int(frame.get_width() * scale)), max(1, int(frame.get_height() * scale))))
        self.g.screen.blit(frame, frame.get_rect(midbottom=(int(midbottom[0]), int(midbottom[1]))))
        return frame

    def cycle(self, frames, ms=110):
        return frames[(pygame.time.get_ticks() // ms) % len(frames)]

    def black(self, alpha):
        if alpha > 0:
            s = pygame.Surface((SCREEN_W, SCREEN_H))
            s.set_alpha(int(alpha))
            self.g.screen.blit(s, (0, 0))

    def dust(self, amount=1):
        import random
        for _ in range(amount):
            if random.random() < 0.25:
                self.g.effects.burst(random.randint(40, SCREEN_W - 40), random.randint(0, 220),
                                     [(120, 110, 120), (80, 75, 85), (160, 150, 150)], 4)

    def crossfade(self, a, b, p):
        self.g.screen.blit(a, (0, 0))
        if p > 0:
            b.set_alpha(int(255 * min(1, p)))
            self.g.screen.blit(b, (0, 0))
            b.set_alpha(255)

    # ---------- scenes ----------
    def to_desk(self, t, length):
        g = self.g
        g.screen.blit(g.castle_images[11], (0, 0))
        p = t / length
        x = self.from_x + (self.WALK_END[0] - self.from_x) * p
        y = 615 + (self.WALK_END[1] - 615) * p
        scale = 1 + (self.SIT_SCALE - 1) * p
        self.blit(self.cycle(g.player_back, 130), scale, (x, y))
        g.screen.blit(g.castle_images[11], self.DESK_COVER.topleft, self.DESK_COVER)

    def library_bg(self, p):
        """Healthy library, then cracking while he writes."""
        g = self.g
        if p < 0.45:
            return g.castle_images[11]
        if "lib_b" not in self.stage_shook:
            self.stage_shook.add("lib_b")
            g.effects.shake(16, 900)
        local = (p - 0.45) / 0.08
        if local < 1:
            self.crossfade(g.castle_images[11], g.lib_ruin[0], local)
            return None
        return g.lib_ruin[0]

    def write(self, t, length):
        g = self.g
        p = t / length
        bg = self.library_bg(p)
        if bg:
            g.screen.blit(bg, (0, 0))
        cover = bg or g.lib_ruin[0]
        k = 1 if p >= 0.45 else 0
        g.effects.shake(1 + k, 80)
        self.dust(1 + k)

        # sitting and writing frames
        if t < 900:
            i = t * 2 // 900
        elif t < 1900:
            i = 2 + (t - 900) * 2 // 1000
        elif t < 2500:
            i = 4
        elif t < length - 1200:
            i = 5 + (t // 220) % 4
        else:
            i = 9
        self.blit(g.write_frames[i], self.SIT_SCALE, self.DESK)
        g.screen.blit(cover, self.DESK_COVER.topleft, self.DESK_COVER)

        if t > 2500:
            write_len = length - 2500 - 1500
            self.draw_page(int(len(self.letter) * min(1, (t - 2500) / write_len)))

    def draw_page(self, letters):
        """The journal page: Lunari for the next one, English under it."""
        g = self.g
        page = self.page.get_rect(topleft=(30, 80))
        g.screen.blit(self.page, page)
        block = g.desk_runes.render_block(self.letter, page.width - 50, letters, line_gap=6)
        g.screen.blit(block, block.get_rect(midtop=(page.centerx, page.top + 34)))
        y = page.top + 60 + block.get_height()
        for line in wrap_text(self.letter[:letters], g.thought_font, page.width - 50):
            img = g.thought_font.render(line, True, (80, 50, 28))
            img.set_alpha(210)
            g.screen.blit(img, img.get_rect(midtop=(page.centerx, y)))
            y += g.thought_font.get_linesize()

    def read(self, t, length):
        """A calm moment to read the whole letter (no shaking)."""
        g = self.g
        g.screen.blit(g.lib_ruin[0], (0, 0))
        self.blit(g.write_frames[9], self.SIT_SCALE, self.DESK)
        g.screen.blit(g.lib_ruin[0], self.DESK_COVER.topleft, self.DESK_COVER)
        self.draw_page(len(self.letter))

    def leave(self, t, length):
        """Stands up, comes back to the tunnel and goes in before the library falls."""
        g = self.g
        g.screen.blit(g.lib_ruin[0], (0, 0))
        g.effects.shake(3, 80)
        self.dust(2)
        stand, come = 800, 2400
        if t < stand:                                   # stands up
            i = 1 if t < stand // 2 else 0
            self.blit(g.write_frames[i], self.SIT_SCALE, self.DESK)
        elif t < stand + come:                          # towards the camera
            p = (t - stand) / come
            x = self.WALK_END[0] + (self.TUNNEL_FLOOR[0] - self.WALK_END[0]) * p
            y = self.WALK_END[1] + (self.TUNNEL_FLOOR[1] - self.WALK_END[1]) * p
            frame = self.cycle(g.player_front_straight, 130)
            self.blit(frame, self.SIT_SCALE + (1 - self.SIT_SCALE) * p, (x, y), flip=True)
        else:                                           # into the tunnel
            p = min(1, (t - stand - come) / (length - stand - come - 200))
            ex, ey, es = self.TUNNEL_END
            x = self.TUNNEL_FLOOR[0] + (ex - self.TUNNEL_FLOOR[0]) * p
            y = self.TUNNEL_FLOOR[1] + (ey - self.TUNNEL_FLOOR[1]) * p
            frame = self.cycle(g.player_back, 130).copy()
            frame.set_alpha(int(255 * (1 - max(0, p - 0.8) / 0.2)))
            self.blit(frame, 1 + (es - 1) * p, (x, y))
        g.screen.blit(g.lib_ruin[0], self.DESK_COVER.topleft, self.DESK_COVER)

    def collapse(self, t, length):
        """Behind him, the library falls and closes the tunnel."""
        g = self.g
        if "lib_c" not in self.stage_shook:
            self.stage_shook.add("lib_c")
            g.effects.shake(22, 1200)
        self.crossfade(g.lib_ruin[0], g.lib_ruin[1], t / 500)
        self.dust(5)

    def hall(self, t, length):
        g = self.g
        room = self.HALLS[self.hall_no]
        g.castle_room = room
        g.draw_room_image()
        x = 1150 + (110 - 1150) * t / length
        self.blit(self.cycle(self.walk_left, 120), 1, (x, floor_y_at(ROOMS[room]["floor"], x)))
        self.black(110)
        g.effects.shake(5, 80)
        self.dust(2)

    def crown(self, t, length):
        g = self.g
        g.screen.blit(g.throne_rooms[0], (0, 0))
        g.effects.shake(3, 80)
        self.dust(1)
        stop = 2600
        if t < stop:                                    # walks in from the right
            x = 1150 + (683 - 1150) * t / stop
            self.blit(self.cycle(self.walk_left, 120), 1, (x, 680))
            self.floor_crown(t / stop)
            return
        i = min(7, (t - stop) * 8 // (length - stop - 400))
        self.blit(g.crown_frames[i], 1, (683, 682), flip=True)

    def floor_crown(self, _):
        """Before he reaches it, draw the crown lying on the floor."""
        g = self.g
        crown = pygame.transform.flip(g.floor_crown, True, False)   # same canvas as crown_01
        g.screen.blit(crown, crown.get_rect(midbottom=(683, 682)))

    def climb(self, t, length):
        g = self.g
        g.screen.blit(g.throne_rooms[0], (0, 0))
        g.effects.shake(4, 80)
        self.dust(2)
        walk = 1800
        human = self.HUMAN
        if t < walk:                                    # to the foot of the stairs
            p = t / walk
            x = 683 + (self.STAIRS_FOOT[0] - 683) * p
            y = 680 + (self.STAIRS_FOOT[1] - 680) * p
            scale = 1 + (0.8 - 1) * p
        else:
            p = (t - walk) / (length - walk)
            x = self.STAIRS_FOOT[0]
            y = self.STAIRS_FOOT[1] + (self.THRONE[1] - self.STAIRS_FOOT[1]) * p
            scale = 0.8 + (self.TOP_SCALE - 0.8) * p
        frames = g.stairs_frames
        self.blit(self.cycle(frames, 200), scale * 172 / human, (x, y))

    def turn(self, t, length):
        g = self.g
        g.screen.blit(g.throne_rooms[0], (0, 0))
        self.dust(1)
        i = min(5, t * 6 // length)
        self.blit(g.turn_frames[i], self.TOP_SCALE * self.HUMAN / 200, self.THRONE)

    def sit(self, t, length):
        g = self.g
        g.screen.blit(g.throne_rooms[0], (0, 0))
        self.dust(1)
        i = min(3, t * 4 // length)
        self.blit(g.stone_frames[i], self.TOP_SCALE * self.HUMAN / 200, self.THRONE)

    def stone(self, t, length):
        g = self.g
        p = t / length
        if not self.stage_shook.issuperset({"stone"}):
            self.stage_shook.add("stone")
            g.effects.shake(20, length)
        self.crossfade(g.throne_rooms[0], g.throne_rooms[1], (p - 0.35) / 0.5)
        self.dust(4)
        i = min(7, 4 + int(p * 4.5))
        self.blit(g.stone_frames[i], self.TOP_SCALE * self.HUMAN / 200, self.THRONE)
        if p > 0.85:                                     # the last stones fall: white dust
            dust = pygame.Surface((SCREEN_W, SCREEN_H))
            dust.fill((200, 195, 200))
            dust.set_alpha(int(200 * (p - 0.85) / 0.15))
            g.screen.blit(dust, (0, 0))

    def end(self, t, length):
        g = self.g
        g.screen.blit(g.throne_rooms[1], (0, 0))
        statue = self.blit(g.stone_frames[7], self.TOP_SCALE * self.HUMAN / 200, self.THRONE)
        if t < 1800:                                     # the dust settles
            dust = pygame.Surface((SCREEN_W, SCREEN_H))
            dust.fill((200, 195, 200))
            dust.set_alpha(int(200 * (1 - t / 1800)))
            g.screen.blit(dust, (0, 0))
        if t > 2000:
            img = g.ending_font.render("The fifth guardian.", True, (220, 225, 240))
            img.set_alpha(min(255, int(255 * (t - 2000) / 1200)))
            g.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, 640)))
        if t > length - 1200:
            self.black(255 * (t - (length - 1200)) / 1200)

    # ---------- main ----------
    def update(self):
        name, length = self.SCENES[self.index]
        t = pygame.time.get_ticks() - self.start
        if t >= length:
            if name == "hall":
                self.hall_no += 1
            self.index += 1
            self.start = pygame.time.get_ticks()
            if self.index >= len(self.SCENES):
                return True
            return False
        getattr(self, name)(t, length)
        # short black fades between places
        if name in ("to_desk", "hall", "crown") and t < 350:
            self.black(255 * (1 - t / 350))
        if name in ("collapse", "hall") and t > length - 250:
            self.black(255 * (t - (length - 250)) / 250)
        return False

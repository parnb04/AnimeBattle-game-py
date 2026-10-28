import pygame
import math
import random
from effects import white_silhouette


def load_anim(folder, name, count):
    """Loads folder/name_01.png ... name_NN.png"""
    return [pygame.image.load(f"{folder}/{name}_{i:02d}.png").convert_alpha()
            for i in range(1, count + 1)]


class CastleEnemy:
    """Base class for the monsters that chase you in the castle.
    Every child class sets TIMING: animation name -> (ms per frame, loop)."""
    TIMING = {}
    ATTACK = "attack"    # name of the attack animation
    COOLDOWN = 900       # ms between two attacks
    BODY = (50, 150)
    SCALE = 1.0          # 1.3 = 30% bigger     # size of the hit box (width, height)

    def __init__(self, x, floor_y, frames, hp, speed, damage, reach, hit_frame, start="walk"):
        if self.SCALE != 1.0:
            frames = {k: [pygame.transform.smoothscale(
                          f, (int(f.get_width() * self.SCALE), int(f.get_height() * self.SCALE)))
                          for f in v]
                      for k, v in frames.items()}
        self.frames = frames
        self.flipped = {k: [pygame.transform.flip(f, True, False) for f in v]
                        for k, v in frames.items()}
        self.x = float(x)
        self.floor_y = floor_y
        self.facing = -1
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.damage = damage
        self.reach = reach * self.SCALE          # how close it must be to attack
        self.hit_frame = hit_frame    # attack frame where the weapon hits
        self.next_attack = 0
        self.flash_until = 0
        self.set_anim(start)

    # ---------- animation ----------
    def set_anim(self, name):
        self.anim = name
        self.anim_start = pygame.time.get_ticks()
        self.hit_done = False

    def frame_index(self):
        ms, loop = self.TIMING[self.anim]
        i = (pygame.time.get_ticks() - self.anim_start) // ms
        n = len(self.frames[self.anim])
        return i % n if loop else min(i, n - 1)

    def anim_finished(self):
        ms, loop = self.TIMING[self.anim]
        return (not loop and
                pygame.time.get_ticks() - self.anim_start >= ms * len(self.frames[self.anim]))

    # ---------- state ----------
    @property
    def alive(self):
        return self.anim != "death"

    @property
    def rect(self):
        w, h = self.BODY[0] * self.SCALE, self.BODY[1] * self.SCALE
        return pygame.Rect(int(self.x - w / 2), int(self.floor_y - h), int(w), int(h))

    def take_hit(self, dmg, from_x):
        if not self.alive or self.anim == "rise":
            return False
        self.hp -= dmg
        self.flash_until = pygame.time.get_ticks() + 100
        self.x += 15 if from_x < self.x else -15
        self.set_anim("death" if self.hp <= 0 else "hurt")
        return True

    def update(self, player_rect, walk, floor_y):
        """Returns "hit" on the frame the attack touches the player."""
        self.floor_y = floor_y(self.x)
        if self.anim in ("rise", "hurt"):
            if self.anim_finished():
                self.set_anim("walk")
            return None
        if self.anim == "death":
            return None

        self.facing = 1 if player_rect.centerx > self.x else -1
        dist = abs(player_rect.centerx - self.x)

        if self.anim == self.ATTACK:
            result = None
            if not self.hit_done and self.frame_index() >= self.hit_frame:
                self.hit_done = True
                if dist <= self.reach + 25:
                    result = "hit"
            if self.anim_finished():
                self.set_anim("walk")
                self.next_attack = pygame.time.get_ticks() + self.COOLDOWN
            return result

        if dist <= self.reach and pygame.time.get_ticks() >= self.next_attack:
            self.set_anim(self.ATTACK)
        elif dist > self.reach * 0.7:
            self.x += self.speed * self.facing
            self.x = max(walk[0], min(walk[1], self.x))
        return None

    def draw(self, screen):
        frames = self.frames if self.facing == 1 else self.flipped
        img = frames[self.anim][self.frame_index()]
        if pygame.time.get_ticks() < self.flash_until:
            img = white_silhouette(img)
        screen.blit(img, img.get_rect(midbottom=(int(self.x), int(self.floor_y) + 2)))


class Skeleton(CastleEnemy):
    TIMING = {"rise": (110, False), "walk": (110, True), "attack": (90, False),
              "hurt": (120, False), "death": (110, False)}
    COOLDOWN = 900

    def __init__(self, x, floor_y, frames):
        super().__init__(x, floor_y, frames, hp=50, speed=2, damage=8,
                         reach=70, hit_frame=2, start="rise")





class Monk(CastleEnemy):
    """Hooded stone statue: punches up close, lunges from far away."""
    TIMING = {"walk": (120, True), "punch": (80, False), "lunge": (90, False),
              "hurt": (120, False), "death": (110, False)}
    ATTACK = "punch"
    SCALE = 1.25
    COOLDOWN = 1000
    LUNGE_COOLDOWN = 2500
    LUNGE_SPEED = 9

    def __init__(self, x, floor_y, frames):
        super().__init__(x, floor_y, frames, hp=90, speed=1.3, damage=12,
                         reach=75, hit_frame=3, start="walk")
        self.next_lunge = pygame.time.get_ticks() + 1500

    def update(self, player_rect, walk, floor_y):
        now = pygame.time.get_ticks()
        if self.anim == "lunge":
            self.floor_y = floor_y(self.x)
            self.x += self.LUNGE_SPEED * self.facing
            self.x = max(walk[0], min(walk[1], self.x))
            result = None
            if not self.hit_done and self.rect.colliderect(player_rect):
                self.hit_done = True
                result = "hit"
            if self.anim_finished():
                self.set_anim("walk")
                self.next_lunge = now + self.LUNGE_COOLDOWN
                self.next_attack = now + 400
            return result

        if self.anim == "walk":
            dist = abs(player_rect.centerx - self.x)
            if 160 < dist < 380 and now >= self.next_lunge:
                self.facing = 1 if player_rect.centerx > self.x else -1
                self.set_anim("lunge")
                return None
        return super().update(player_rect, walk, floor_y)





class King(CastleEnemy):
    """Stone king (boss): overhead slam up close, wide swing a bit further."""
    NAME = "THE STONE KING"
    TIMING = {"walk": (130, True), "slam": (95, False), "swing": (85, False),
              "hurt": (120, False), "death": (120, False)}
    ATTACK = "swing"
    SCALE = 1.35
    COOLDOWN = 1100
    BODY = (70, 190)

    def __init__(self, x, floor_y, frames):
        super().__init__(x, floor_y, frames, hp=220, speed=1.3, damage=18,
                         reach=150, hit_frame=2, start="walk")
        self.max_hp = self.hp
        self.shake_now = False

    def take_hit(self, dmg, from_x):
        # too heavy to be pushed back or stopped: only flashes
        if not self.alive:
            return False
        self.hp -= dmg
        self.flash_until = pygame.time.get_ticks() + 100
        if self.hp <= 0:
            self.set_anim("death")
        return True

    def update(self, player_rect, walk, floor_y):
        now = pygame.time.get_ticks()
        if self.anim == "walk" and now >= self.next_attack:
            dist = abs(player_rect.centerx - self.x)
            s = self.SCALE
            if dist <= 150 * s:
                self.facing = 1 if player_rect.centerx > self.x else -1
                if dist <= 105 * s and random.random() < 0.5:
                    self.ATTACK, self.hit_frame, self.damage, self.reach = "slam", 4, 22, 105 * s
                else:
                    self.ATTACK, self.hit_frame, self.damage, self.reach = "swing", 2, 18, 150 * s
                self.set_anim(self.ATTACK)
                return None
        was_done = self.hit_done
        result = super().update(player_rect, walk, floor_y)
        if self.anim == "slam" and self.hit_done and not was_done:
            self.shake_now = True          # the sword hits the ground
        return result




class DarkOrb:
    """The queen's dark magic ball."""
    SPEED = 6

    def __init__(self, x, y, target, frames, hit_frames):
        dx, dy = target[0] - x, target[1] - y
        d = max(1, math.hypot(dx, dy))
        self.vx, self.vy = dx / d * self.SPEED, dy / d * self.SPEED
        angle = math.degrees(math.atan2(-self.vy, self.vx))
        self.frames = [pygame.transform.rotate(f, angle) for f in frames]
        self.hit_frames = hit_frames
        self.x, self.y = x, y
        self.start = pygame.time.get_ticks()
        self.state = "fly"          # fly -> burst -> gone

    @property
    def rect(self):
        return pygame.Rect(int(self.x - 18), int(self.y - 18), 36, 36)

    def burst(self):
        self.state = "burst"
        self.start = pygame.time.get_ticks()

    def update(self, player_rect):
        """Returns True when it hits the player."""
        if self.state == "fly":
            self.x += self.vx
            self.y += self.vy
            if self.rect.colliderect(player_rect):
                self.burst()
                return True
            if not -100 < self.x < 1380 or self.y > 760:
                self.state = "gone"
        elif self.state == "burst":
            if pygame.time.get_ticks() - self.start > 70 * len(self.hit_frames):
                self.state = "gone"
        return False

    def draw(self, screen):
        t = pygame.time.get_ticks() - self.start
        if self.state == "fly":
            img = self.frames[(t // 80) % len(self.frames)]
        elif self.state == "burst":
            img = self.hit_frames[min(t // 70, len(self.hit_frames) - 1)]
        else:
            return
        screen.blit(img, img.get_rect(center=(int(self.x), int(self.y))))




class Queen(CastleEnemy):
    """Floating faceless queen: keeps her distance and throws dark orbs."""
    NAME = "THE FACELESS QUEEN"
    TIMING = {"hover": (110, True), "cast": (100, False), "death": (110, False)}
    ATTACK = "cast"
    COOLDOWN = 2200
    BODY = (60, 170)
    SCALE = 1.3
    FLOAT = 25            # how high above the floor she floats

    def __init__(self, x, floor_y, frames, orb_frames, orb_hit_frames):
        super().__init__(x, floor_y, frames, hp=140, speed=1.4, damage=14,
                         reach=0, hit_frame=4, start="hover")
        self.max_hp = self.hp
        self.orb_frames = orb_frames
        self.orb_hit_frames = orb_hit_frames
        self.orbs = []
        self.next_attack = pygame.time.get_ticks() + 1200

    @property
    def lift(self):
        return self.FLOAT + math.sin(pygame.time.get_ticks() / 300) * 6

    @property
    def rect(self):
        w, h = self.BODY[0] * self.SCALE, self.BODY[1] * self.SCALE
        return pygame.Rect(int(self.x - w / 2), int(self.floor_y - self.lift - h), int(w), int(h))

    def take_hit(self, dmg, from_x):
        if not self.alive:
            return False
        self.hp -= dmg
        self.flash_until = pygame.time.get_ticks() + 100
        if self.hp <= 0:
            self.set_anim("death")
        return True

    def update(self, player_rect, walk, floor_y):
        result = None
        for o in self.orbs:
            if o.update(player_rect):
                result = "hit"
        self.orbs = [o for o in self.orbs if o.state != "gone"]

        self.floor_y = floor_y(self.x)
        if self.anim == "death":
            return result
        now = pygame.time.get_ticks()
        self.facing = 1 if player_rect.centerx > self.x else -1
        dist = abs(player_rect.centerx - self.x)

        if self.anim == "cast":
            if not self.hit_done and self.frame_index() >= self.hit_frame:
                self.hit_done = True
                hand_x = self.x + self.facing * 70 * self.SCALE
                hand_y = self.floor_y - self.lift - 120 * self.SCALE
                self.orbs.append(DarkOrb(hand_x, hand_y, player_rect.center,
                                         self.orb_frames, self.orb_hit_frames))
            if self.anim_finished():
                self.set_anim("hover")
                self.next_attack = now + self.COOLDOWN
            return result

        # keep a distance of about 300-550 px
        if dist < 300:
            self.x -= self.speed * self.facing
        elif dist > 550:
            self.x += self.speed * self.facing
        self.x = max(walk[0], min(walk[1], self.x))
        if now >= self.next_attack:
            self.set_anim("cast")
        return result

    def draw(self, screen):
        frames = self.frames if self.facing == 1 else self.flipped
        img = frames[self.anim][self.frame_index()]
        if pygame.time.get_ticks() < self.flash_until:
            img = white_silhouette(img)
        lift = self.lift if self.anim != "death" else 0
        screen.blit(img, img.get_rect(midbottom=(int(self.x), int(self.floor_y - lift))))
        for o in self.orbs:
            o.draw(screen)
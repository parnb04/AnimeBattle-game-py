import pygame
import math
from level import TILE


def white_copy(img):
    mask = pygame.mask.from_surface(img)
    return mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))


class MonsterShot:
    def __init__(self, x, y, vx, image, damage, additive=False, vy=0):
        angle = -math.degrees(math.atan2(vy, vx))
        self.image = pygame.transform.rotate(image, angle)
        self.rect = self.image.get_rect(center=(x, y))
        self.fx = float(x)
        self.fy = float(y)
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.additive = additive
        self.alive = True
        self.life = 180

    def update(self, level):
        self.fx += self.vx
        self.fy += self.vy
        self.rect.center = (round(self.fx), round(self.fy))
        self.life -= 1
        r, c = self.rect.centery // TILE, self.rect.centerx // TILE
        if self.life <= 0 or level.solid(r, c):
            self.alive = False

    def draw(self, screen, cam):
        pos = (self.rect.x - cam.x, self.rect.y - cam.y)
        if self.additive:
            screen.blit(self.image, pos, special_flags=pygame.BLEND_ADD)
        else:
            screen.blit(self.image, pos)


class Monster:
    MAX_HP = 3
    IMAGE_FACES = 1      # which way the picture looks: 1 right, -1 left
    HOVER = 0            # pixels above the ground

    def __init__(self, x, y, image):
        self.image = image
        self.rect = image.get_rect(midbottom=(x + TILE // 2, y + TILE - self.HOVER))
        self.fx = float(self.rect.x)
        self.hp = self.MAX_HP
        self.facing = -1
        self.flash_until = 0
        self.stagger_until = 0
        self.alive = True

    def take_hit(self, dmg):
        self.hp -= dmg
        self.flash_until = pygame.time.get_ticks() + 90
        self.stagger_until = pygame.time.get_ticks() + 250
        if self.hp <= 0:
            self.alive = False

    def face(self, player):
        self.facing = 1 if player.rect.centerx > self.rect.centerx else -1

    def bob(self):
        return 0

    def update(self, level, player, shots, hits):
        pass

    def decorate(self, img):
        return img

    def draw_extra(self, screen, cam):
        pass

    def draw(self, screen, cam):
        img = self.image
        if self.facing != self.IMAGE_FACES:
            img = pygame.transform.flip(img, True, False)
        img = self.decorate(img)
        if pygame.time.get_ticks() < self.flash_until:
            img = white_copy(img)
        pos = img.get_rect(midbottom=(self.rect.centerx - cam.x,
                                      self.rect.bottom - cam.y + self.bob()))
        screen.blit(img, pos)
        self.draw_extra(screen, cam)


class Biter(Monster):
    MAX_HP = 3
    DAMAGE = 10
    HOVER = 24

    def __init__(self, x, y, image):
        super().__init__(x, y, image)
        self.bite_ready = 0

    def bob(self):
        return int(math.sin(pygame.time.get_ticks() / 120) * 4)

    def update(self, level, player, shots, hits):
        now = pygame.time.get_ticks()
        if now < self.stagger_until:
            return
        dx = player.rect.centerx - self.rect.centerx
        feet = self.rect.bottom + self.HOVER
        same_floor = abs(player.rect.bottom - feet) < 60
        chasing = same_floor and abs(dx) < 400

        if chasing:
            self.face(player)
            speed = 4.2
        else:
            speed = 2

        ahead_x = self.rect.centerx + self.facing * (self.rect.width // 2 + 4)
        c = int(ahead_x // TILE)
        wall = level.solid((feet - 10) // TILE, c)
        edge = not level.is_ground(feet // TILE, c)

        if wall or edge:
            if not chasing:
                self.facing *= -1
        else:
            self.fx += self.facing * speed
            self.rect.x = round(self.fx)

        if self.rect.colliderect(player.rect) and now >= self.bite_ready:
            hits.append((self.DAMAGE, self.rect.centerx))
            self.bite_ready = now + 900
            self.fx -= self.facing * 30
            self.rect.x = round(self.fx)


class Spitter(Monster):
    MAX_HP = 3
    IMAGE_FACES = 1
    HOVER = 6
    DAMAGE = 8
    RANGE = 520
    WINDUP = 450       # ms swelling before spitting
    COOLDOWN = 1600    # ms between spits

    def __init__(self, x, y, image, shot_image):
        super().__init__(x, y, image)
        self.shot_image = shot_image
        self.state = "idle"
        self.timer = 0

    def bob(self):
        return int(math.sin(pygame.time.get_ticks() / 300) * 5)

    def update(self, level, player, shots, hits):
        now = pygame.time.get_ticks()
        if now < self.stagger_until:
            self.state = "idle"
            self.timer = now + 500
            return

        dx = player.rect.centerx - self.rect.centerx
        dy = abs(player.rect.centery - self.rect.centery)
        sees = abs(dx) < self.RANGE and dy < 150

        if self.state == "idle":
            if sees:
                self.face(player)
                if now >= self.timer:
                    self.state = "windup"
                    self.timer = now + self.WINDUP
        elif self.state == "windup" and now >= self.timer:
            x = self.rect.centerx + self.facing * self.rect.width // 2
            y = self.rect.centery + 10
            shots.append(MonsterShot(x, y, 7 * self.facing, self.shot_image, self.DAMAGE))
            self.state = "idle"
            self.timer = now + self.COOLDOWN

    def decorate(self, img):
        if self.state == "windup":
            w, h = img.get_size()
            return pygame.transform.smoothscale(img, (int(w * 1.1), int(h * 1.15)))
        return img


class Eye(Monster):
    MAX_HP = 6
    IMAGE_FACES = -1
    DAMAGE = 15
    RANGE = 450
    KEEP_DISTANCE = 280
    HEIGHT_ABOVE = 200    
    FLY_SPEED = 2
    CHARGE = 700          # ms aiming before the laser
    COOLDOWN = 2200       # ms between lasers
    SHOT_SPEED = 14

    def __init__(self, x, y, image, shot_image):
        super().__init__(x, y, image)
        self.home_x = self.rect.x
        self.home_y = self.rect.y
        self.fy = float(self.rect.y)
        self.shot_image = shot_image
        self.state = "idle"
        self.timer = 0
        self.target = (0, 0)

    def eye_pos(self):
        off = int(self.rect.width * 0.17)
        return (self.rect.centerx + self.facing * off,
                self.rect.top + int(self.rect.height * 0.5))

    def fly_towards(self, tx, ty):
        if abs(tx - self.fx) > self.FLY_SPEED:
            self.fx += self.FLY_SPEED if tx > self.fx else -self.FLY_SPEED
        if abs(ty - self.fy) > self.FLY_SPEED:
            self.fy += self.FLY_SPEED if ty > self.fy else -self.FLY_SPEED

    def update(self, level, player, shots, hits):
        now = pygame.time.get_ticks()
        if now < self.stagger_until:
            self.state = "idle"
            self.timer = now + 600
            return

        dx = player.rect.centerx - self.rect.centerx
        near_home = abs(player.rect.bottom - (self.home_y + self.rect.height)) < 350
        sees = abs(dx) < self.RANGE + 150 and near_home

        if sees:
            side = 1 if dx > 0 else -1
            tx = player.rect.centerx - side * self.KEEP_DISTANCE - self.rect.width // 2
            ty = player.rect.bottom - self.HEIGHT_ABOVE - self.rect.height // 2
            self.face(player)
        else:
            tx = self.home_x + int(math.sin(now / 1250) * 120)
            ty = self.home_y

        if self.state == "idle":
            self.fly_towards(tx, ty)
        self.rect.x = round(self.fx)
        self.rect.y = round(self.fy + math.sin(now / 500) * 6)

        if self.state == "idle":
            if sees and abs(dx) < self.RANGE and now >= self.timer:
                self.state = "charge"
                self.timer = now + self.CHARGE
                self.target = player.rect.center
        elif self.state == "charge" and now >= self.timer:
            ex, ey = self.eye_pos()
            tx, ty = self.target
            dist = max(1, math.hypot(tx - ex, ty - ey))
            vx = (tx - ex) / dist * self.SHOT_SPEED
            vy = (ty - ey) / dist * self.SHOT_SPEED
            shots.append(MonsterShot(ex, ey, vx, self.shot_image, self.DAMAGE,
                                     additive=True, vy=vy))
            self.state = "idle"
            self.timer = now + self.COOLDOWN

    def draw_extra(self, screen, cam):
        if self.state != "charge":
            return
        now = pygame.time.get_ticks()
        progress = 1 - (self.timer - now) / self.CHARGE
        if progress < 0.7 and (now // 60) % 2:
            return
        ex, ey = self.eye_pos()
        tx, ty = self.target
        width = 1 + int(progress * 4)
        color = (255, 60 + int(progress * 120), 60)
        pygame.draw.line(screen, color, (ex - cam.x, ey - cam.y), (tx - cam.x, ty - cam.y), width)
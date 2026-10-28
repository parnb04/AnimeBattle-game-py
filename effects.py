import pygame
import random


def white_silhouette(surface):
    """Same shape as the image, but pure white."""
    mask = pygame.mask.from_surface(surface)
    return mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-6, 6)
        self.vy = random.uniform(-8, -2)
        self.life = random.randint(18, 32)
        self.max_life = self.life
        self.color = color
        self.size = random.randint(3, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.5        # gravity
        self.vx *= 0.95       # air friction
        self.life -= 1

    def draw(self, screen):
        size = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.rect(screen, self.color, (int(self.x), int(self.y), size, size))


class FloatingText:
    def __init__(self, x, y, text, color, font):
        self.image = font.render(text, True, color)
        self.x = x - self.image.get_width() // 2
        self.y = y
        self.life = 45

    def update(self):
        self.y -= 1.2
        self.life -= 1

    def draw(self, screen):
        self.image.set_alpha(min(255, self.life * 8))
        screen.blit(self.image, (self.x, int(self.y)))


class Effects:
    def __init__(self):
        self.particles = []
        self.texts = []
        self.shake_until = 0
        self.shake_power = 0
        self.hitstop_until = 0

    def shake(self, power, duration):
        now = pygame.time.get_ticks()
        if power >= self.shake_power or now > self.shake_until:
            self.shake_power = power
            self.shake_until = now + duration

    def get_shake_offset(self):
        if pygame.time.get_ticks() >= self.shake_until:
            return (0, 0)
        p = self.shake_power
        return (random.randint(-p, p), random.randint(-p, p))

    def hitstop(self, duration):
        self.hitstop_until = pygame.time.get_ticks() + duration

    def is_frozen(self):
        return pygame.time.get_ticks() < self.hitstop_until

    def burst(self, x, y, colors, count=14):
        for _ in range(count):
            self.particles.append(Particle(x, y, random.choice(colors)))

    def popup(self, x, y, text, color, font):
        self.texts.append(FloatingText(x, y, text, color, font))

    def update_and_draw(self, screen):
        for p in self.particles:
            p.update()
            p.draw(screen)
        self.particles = [p for p in self.particles if p.life > 0]

        for t in self.texts:
            t.update()
            t.draw(screen)
        self.texts = [t for t in self.texts if t.life > 0]

    def clear(self):
        self.particles = []
        self.texts = []
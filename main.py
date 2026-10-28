import pygame
import sys
import math
import random
from animation import Animation, Animator, load_frames
from effects import Effects, white_silhouette
from level import Level, Camera, CrumblePlatform, TILE
from levels import LEVEL_1, MOVERS_1, LEVEL_2, MOVERS_2
from monsters import Biter, Spitter, Eye
from inventory import Inventory
from enemies import Skeleton, Monk, King, Queen, load_anim
from ending import RunEnding, StayEnding
from story import LETTER_1, LETTER_2, INSTITUTE, Letter, AcceptBanner, FRAGMENTS, Lunari
from castle import (ROOMS, floor_y_at, NoWalls, PathWalk, Thought, KeysWithout,
                    Hotspot, SignPopup, CardPopup, clicked, FancyBar,
                    AreaHotspot, BookPopup, pressed, FallingRock, NoKeys, TranslateDesk)

# ---------------------------
# Screen Settings
# ---------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
GROUND_HEIGHT = 60

# ---------------------------
# Controls
# ---------------------------
KEY_LEFT = pygame.K_a
KEY_RIGHT = pygame.K_d
KEY_JUMP = pygame.K_w
KEY_DOWN = pygame.K_s
KEY_ATTACK = pygame.K_i
KEY_BLOCK = pygame.K_k
KEY_INTERACT = pygame.K_SPACE
KEY_SAVE = pygame.K_p
KEY_LOAD = pygame.K_o
KEY_JOURNAL = pygame.K_t

CONTROLS_TEXT = [
    ("A / D", "Move left / right"),
    ("W", "Jump"),
    ("S", "Drop down from a platform"),
    ("i", "Fire ball attack"),
    ("k", "Block"),
    ("SPACE", "Enter portals, doors and exits"),
    ("P", "Save game (in the hall)"),
    ("O", "Load game"),
    ("T", "Open the journal"),
    ("B", "Open the bag"),
    ("ESC", "Escape from battle"),
]

# ---------------------------
# Character Base Class
# ---------------------------
class Character:
    def __init__(self, x, y, width, height, hp=160, speed=5, strength=10):
        self.rect = pygame.Rect(x, y, width, height)
        self.max_hp = hp
        self.hp = hp
        self.speed = speed
        self.strength = strength

        # Jumping / gravity
        self.is_jumping = False
        self.vertical_speed = 0
        self.GRAVITY = 1
        self.JUMP_STRENGTH = 15
        self.ground_y = SCREEN_HEIGHT - GROUND_HEIGHT - self.rect.height
        self.rect.y = self.ground_y
        self.flash_until = 0
        
    def move(self, dx):
        """Only horizontal movement."""
        self.rect.x += dx
        if self.rect.right < 0:
            self.rect.x = SCREEN_WIDTH
        elif self.rect.left > SCREEN_WIDTH:
            self.rect.x = -self.rect.width

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp < 0:
            self.hp = 0

    def is_alive(self):
        return self.hp > 0

    def apply_gravity(self):
        if self.is_jumping or self.rect.y < self.ground_y:
            self.vertical_speed += self.GRAVITY

        self.rect.y += self.vertical_speed

        if self.rect.y >= self.ground_y:
            self.rect.y = self.ground_y
            self.is_jumping = False
            self.vertical_speed = 0

    def update(self):
        """Update character each frame."""
        self.apply_gravity()

    def draw(self, screen, color=None):
        img = self.image
        if pygame.time.get_ticks() < self.flash_until:
            if not hasattr(self, "white_image"):
                self.white_image = white_silhouette(self.image)
            img = self.white_image
        screen.blit(img, (self.rect.x, self.rect.y))

    def apply_knockback(self, direction, amount=20):
        """Push character left or right."""
        self.rect.x += direction * amount
        self.rect.x = max(0, min(self.rect.x, SCREEN_WIDTH - self.rect.width))

    def flash(self, duration=80):
        self.flash_until = pygame.time.get_ticks() + duration


# ---------------------------
# Player Class
# ---------------------------
class Player(Character):
    def __init__(self, x, y, image, frames=None):
        super().__init__(x, y, image.get_width(), image.get_height(), hp=180, speed=4, strength=20)
        self.image = image
        self.rect.width = image.get_width()
        self.rect.height = image.get_height()
        self.ground_y = SCREEN_HEIGHT - GROUND_HEIGHT - self.rect.height
        self.rect.y = self.ground_y
        self.facing = 1
        self.is_attacking = False
        
        # Energy system
        self.max_energy = 100
        self.energy = self.max_energy
        self.energy_regen_rate = 0.3

        # Animation
        self.is_moving = False
        self.anim_state = "idle"
        if frames is None:
            frames = {"idle": [image], "run": [image], "jump": [image]}
        self.is_blocking = False
        self.block_walk = False
        self.stun_until = 0
        self.drop_until = 0
        self.fall_start_y = None
        self.landed_fall = 0
        self.is_defeated = False
        self.has_fired = False
        self.animator = Animator({
            "idle":   Animation(frames["idle"], fps=1),
            "run":    Animation(frames["run"], fps=10),
            "jump":   Animation(frames["jump"], fps=1, loop=False),
            "land":   Animation(frames["jump"][5:7], fps=12, loop=False),
            "attack": Animation(frames.get("attack", [image]), fps=14, loop=False),
            "block_up":   Animation(frames.get("block", [image])[0:6], fps=20, loop=False),
            "block_down": Animation(frames.get("block", [image])[6:8], fps=14, loop=False),
            "defeat": Animation(frames.get("defeat", [image]), fps=8, loop=False),
        })

        
    def handle_input(self, keys, platforms=None, world_width=SCREEN_WIDTH):
        if self.is_defeated or pygame.time.get_ticks() < self.stun_until:
            self.is_moving = False
            return
        if self.is_attacking:
            self.is_moving = False
            return
        if self.is_blocking and not self.block_walk:
            self.is_moving = False
            return
        move_speed = int(self.speed * 1.5) if self.is_jumping else self.speed
        dx = 0
        if self.is_blocking:
            move_speed = 1.5
        if keys[KEY_LEFT]:
            dx = -move_speed
        if keys[KEY_RIGHT]:
            dx = move_speed

        if dx > 0:
            self.facing = 1
        elif dx < 0:
            self.facing = -1

        self.is_moving = dx != 0

        if keys[KEY_JUMP] and not self.is_jumping and not self.is_blocking:
            self.is_jumping = True
            self.vertical_speed = -self.JUMP_STRENGTH

        if keys[KEY_DOWN] and not self.is_jumping:
            self.drop_until = pygame.time.get_ticks() + 200

        # Move horizontally
        if platforms:
            self.move_with_platforms(dx, platforms, world_width)
        else:
            self.move(dx)
    
    def move_with_platforms(self, dx, platforms, world_width=SCREEN_WIDTH):
        """Move with platform collision detection"""
        if dx == 0:
            return
        
        # Try horizontal movement
        self.rect.x += dx
        
        # Check side collisions only
        for platform in platforms:
            if getattr(platform, "one_way", False):
                continue
            if self.rect.colliderect(platform.rect):
                # Determine if this is a side collision
                # Player is hitting side if their feet are above platform top
                # or their head is below platform bottom
                player_feet = self.rect.bottom
                player_head = self.rect.top
                platform_top = platform.rect.top
                platform_bottom = platform.rect.bottom
                
                # It's a side collision if player overlaps vertically with platform
                # but not landing on top or hitting head on bottom
                is_side_collision = (
                    player_feet > platform_top + 5 and  # Feet below platform top
                    player_head < platform_bottom - 5    # Head above platform bottom
                )
                
                if is_side_collision:
                    if dx > 0:  # Moving right
                        self.rect.right = platform.rect.left
                    elif dx < 0:  # Moving left
                        self.rect.left = platform.rect.right
        
        # Keep in screen bounds
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > world_width:
            self.rect.right = world_width
    
    def apply_gravity_with_platforms(self, platforms):
        """Gravity + landing on tiles and one-way platforms"""
        self.vertical_speed += self.GRAVITY
        self.vertical_speed = min(self.vertical_speed, 20)   # max fall speed
        if self.vertical_speed > 0 and self.fall_start_y is None:
            self.fall_start_y = self.rect.bottom

        old_y = self.rect.y
        self.rect.y += self.vertical_speed

        on_ground = False
        dropping = pygame.time.get_ticks() < self.drop_until

        for platform in platforms:
            one_way = getattr(platform, "one_way", False)
            if one_way and dropping:
                continue

            if self.rect.colliderect(platform.rect):
                if self.vertical_speed > 0:
                    if old_y + self.rect.height <= platform.rect.top + 10:
                        self.rect.bottom = platform.rect.top
                        self.vertical_speed = 0
                        self.is_jumping = False
                        on_ground = True
                        if self.fall_start_y is not None:
                            self.landed_fall = self.rect.bottom - self.fall_start_y
                        self.fall_start_y = None
                        break
                elif self.vertical_speed < 0 and not one_way:
                    if old_y >= platform.rect.bottom - 10:
                        self.rect.top = platform.rect.bottom
                        self.vertical_speed = 0

        if not on_ground and self.vertical_speed >= 0:
            self.is_jumping = True
    
    def update(self):
        super().update()
        # Regenerate energy
        self.energy = min(self.max_energy, self.energy + self.energy_regen_rate)
    
    def can_attack(self, cost=20):
        return self.energy >= cost
    
    def use_energy(self, cost=20):
        self.energy -= cost

    def start_attack(self):
        self.is_attacking = True
        self.has_fired = False
        self.anim_state = "attack"
        self.animator.play("attack", restart=True)

    def set_block(self, on):
        if on and not self.is_blocking:
            self.is_blocking = True
            self.anim_state = "block_up"
            self.animator.play("block_up", restart=True)
        elif not on and self.is_blocking:
            self.is_blocking = False
            self.anim_state = "block_down"
            self.animator.play("block_down", restart=True)

    def start_defeat(self):
        self.is_defeated = True
        self.is_attacking = False
        self.is_blocking = False
        self.anim_state = "defeat"
        self.animator.play("defeat", restart=True)

    def is_guarding(self):
        return self.is_blocking and self.animator.frame_index >= 2

    def take_damage(self, amount):
        if self.is_guarding():
            amount = int(amount * 0.2)
        super().take_damage(amount)

    def apply_knockback(self, direction, amount=20):
        if self.is_guarding():
            amount //= 3
        super().apply_knockback(direction, amount)

    def update_animation(self):
        if self.anim_state == "defeat":
            self.animator.update()
            return
        if self.anim_state == "attack":
            if not self.animator.finished:
                self.animator.update()
                return
            self.is_attacking = False
        if self.anim_state == "block_up" and self.is_blocking:
            self.animator.update()
            return
        if self.anim_state == "block_down" and not self.animator.finished:
            self.animator.update()
            return
        was_in_air = self.anim_state == "jump"

        if self.is_jumping:
            self.anim_state = "jump"
        elif was_in_air and not self.is_moving:
            self.anim_state = "land"
        elif self.anim_state == "land" and not self.animator.finished and not self.is_moving:
            pass  # keep playing landing
        elif self.is_moving:
            self.anim_state = "run"
        else:
            self.anim_state = "idle"

        self.animator.animations["run"].frame_duration = 1000 / (self.speed * 4)
        self.animator.play(self.anim_state)

        if self.anim_state == "jump":
            v = self.vertical_speed
            if v < -6:
                i = 1      # takeoff
            elif v < -1:
                i = 2      # rising
            elif v <= 3:
                i = 3      # peak
            else:
                i = 4      # falling
            self.animator.set_frame(i)
        else:
            self.animator.update()

    def draw(self, screen, color=None, cam=None):
        self.update_animation()
        frame = self.animator.get_frame()
        t = pygame.time.get_ticks()

        offset_y = 0
        angle = 0
        if self.anim_state == "idle":
            offset_y = math.sin(t / 250) * 3           # breathing
        elif self.anim_state == "run":
            angle = -2 * self.facing                   # slight lean
        elif self.anim_state == "block_up" and self.is_moving:
            offset_y = -abs(math.sin(t / 90)) * 3

        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
        if angle != 0:
            frame = pygame.transform.rotate(frame, angle)

        if t < self.flash_until:
            frame = white_silhouette(frame)

        ox, oy = (cam.x, cam.y) if cam else (0, 0)
        draw_rect = frame.get_rect(midbottom=(self.rect.centerx - ox, self.rect.bottom + offset_y - oy))
        screen.blit(frame, draw_rect)


# ---------------------------
# Enemy Class
# ---------------------------
class Enemy(Character):
    def __init__(self, x, y, image, name="Enemy"):
        self.image = image
        w, h = image.get_width(), image.get_height()
        super().__init__(x, y, w, h, hp=160, speed=3, strength=10)
        self.name = name
        self.ability_cooldown = 0
        self.dash_frames = 0
        self.dash_direction = 0
        
        # NEW: Attack charging system for enemy (similar to player energy)
        self.attack_charge = 0
        self.attack_charge_max = 60  # Frames to charge (1 second at 60fps)
        self.is_charging = False
        self.charge_started_at = 0
    
    def basic_chase(self, player):
        # Don't move while charging an attack
        if self.is_charging:
            return
            
        if player.rect.centerx < self.rect.centerx:
            self.move(-self.speed)
        elif player.rect.centerx > self.rect.centerx:
            self.move(self.speed)

    def update_ai(self, player):
        if self.ability_cooldown > 0:
            self.ability_cooldown -= 1

        if self.name == "Naruto":
            self.update_naruto_ai(player)
        elif self.name == "Luffy":
            self.update_luffy_ai(player)
        elif self.name == "Ichigo":
            self.update_ichigo_ai(player)
        elif self.name == "Goku":
            self.update_goku_ai(player)
        else:
            self.basic_chase(player)
        
    def update_naruto_ai(self, player):
        if self.dash_frames > 0:
            self.move(self.dash_direction * (self.speed * 2))
            self.dash_frames -= 1
            return

        self.basic_chase(player)

        distance = abs(player.rect.centerx - self.rect.centerx)
        if self.ability_cooldown == 0 and distance > 150:
            self.dash_direction = 1 if player.rect.centerx > self.rect.centerx else -1
            self.dash_frames = 20
            self.ability_cooldown = 120
        
    def update_luffy_ai(self, player):
        self.basic_chase(player)
    
    def update_ichigo_ai(self, player):
        self.basic_chase(player)
    
    def update_goku_ai(self, player):
        self.basic_chase(player)


# ---------------------------
# Door Class
# ---------------------------
class Door:
    def __init__(self, x, y, width, height, enemy_name):
        self.rect = pygame.Rect(x, y, width, height)
        self.enemy_name = enemy_name
        self.is_locked = True
        self.is_cleared = False

    def draw(self, screen):
        pass

    def is_player_in_front(self, player):
        distance = abs(self.rect.centerx - player.rect.centerx)
        return distance < 80 and abs(self.rect.bottom - player.rect.bottom) < 50


# ---------------------------
# Projectile Class
# ---------------------------
class Projectile:
    def __init__(self, x, y, direction, image, damage, speed=12):
        self.image = image if direction == 1 else pygame.transform.flip(image, True, False)
        self.rect = self.image.get_rect(center=(x, y))
        self.direction = direction
        self.damage = damage
        self.speed = speed
        self.alive = True
        self.life = 999

    def update(self, world_width=SCREEN_WIDTH):
        self.rect.x += self.speed * self.direction
        if self.rect.right < 0 or self.rect.left > world_width:
            self.alive = False

    def draw(self, screen, cam=None):
        ox, oy = (cam.x, cam.y) if cam else (0, 0)
        screen.blit(self.image, (self.rect.x - ox, self.rect.y - oy))

# ---------------------------
# Portal Class
# ---------------------------
class Portal:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 60, 80)
        self.animation_offset = 0
    
    def draw(self, screen, cam=None):
        ox, oy = (cam.x, cam.y) if cam else (0, 0)
        rect = self.rect.move(-ox, -oy)
        self.animation_offset = (self.animation_offset + 0.1) % (2 * math.pi)

        for i in range(3):
            radius = 30 - i * 8
            alpha = int(100 + 50 * math.sin(self.animation_offset + i))
            portal_surface = pygame.Surface((80, 100), pygame.SRCALPHA)
            pygame.draw.circle(portal_surface, (150, 50, 255, alpha), (40, 50), radius)
            screen.blit(portal_surface, (rect.x - 10, rect.y - 10))

        pygame.draw.ellipse(screen, (200, 100, 255), rect, 3)
    
    def check_collision(self, player):
        return self.rect.colliderect(player.rect)


# ---------------------------
# Exit Portal (image)
# ---------------------------
class ExitPortal:
    def __init__(self, feet_x, feet_y, image):
        self.image = image
        self.rect = image.get_rect(midbottom=(feet_x, feet_y))
        self.hit_rect = self.rect.inflate(-60, -40)
        self.visible = False
        self.appear_time = 0

    def show(self):
        if not self.visible:
            self.visible = True
            self.appear_time = pygame.time.get_ticks()

    def draw(self, screen, cam=None):
        if not self.visible:
            return
        ox, oy = (cam.x, cam.y) if cam else (0, 0)
        alpha = min(255, int((pygame.time.get_ticks() - self.appear_time) / 1000 * 255))
        self.image.set_alpha(alpha)
        screen.blit(self.image, (self.rect.x - ox, self.rect.y - oy))

    def check_collision(self, player):
        return self.visible and self.hit_rect.colliderect(player.rect)


# ---------------------------
# Key Class (UPDATED TO USE IMAGE)
# ---------------------------
class Key:
    def __init__(self, x, y, label="", key_image=None):
        self.rect = pygame.Rect(x, y, 50, 50)
        self.collected = False
        self.label = label
        self.float_offset = 0
        self.key_image = key_image
        
        # Scale the image if provided
        if self.key_image:
            self.key_image = pygame.transform.scale(self.key_image, (50, 50))

    def draw(self, screen, cam=None):
        if self.collected:
            return
        ox, oy = (cam.x, cam.y) if cam else (0, 0)
        rect = self.rect.move(-ox, -oy)

        self.float_offset = math.sin(pygame.time.get_ticks() / 200) * 5

        glow_surface = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (255, 215, 0, 60), (30, 30), 30)
        screen.blit(glow_surface, (rect.x - 5, rect.y - 5 + self.float_offset))

        if self.key_image:
            screen.blit(self.key_image, (rect.x, rect.y + self.float_offset))
        else:
            pygame.draw.rect(screen, (255, 215, 0), (rect.x, rect.y + self.float_offset, 40, 40))

        pygame.draw.circle(screen, (255, 255, 200),
                           (int(rect.centerx - 15), int(rect.centery - 15 + self.float_offset)), 3)
        pygame.draw.circle(screen, (255, 255, 200),
                           (int(rect.centerx + 15), int(rect.centery + 15 + self.float_offset)), 3)
        

    def check_pickup(self, player):
        if not self.collected and self.rect.colliderect(player.rect):
            self.collected = True
            return True
        return False


# ---------------------------
# Ancient Text Class
# ---------------------------
class AncientText:
    """Collectible lore items"""
    TEXTS = {
        "Naruto": "The Shadow Clone Warrior was sealed here by ancient shinobi. His determination echoes through time...",
        "Luffy": "The Rubber Pirate saw the ultimate treasure, but was trapped in this dimension. His will remains unbroken...",
        "Ichigo": "The Soul Reaper defended the balance between worlds. His blade still hungers for battle...",
        "Goku": "The Saiyan Warrior trained beyond mortal limits. Even sealed, his power shakes the foundations of reality..."
    }
    
    def __init__(self, enemy_name):
        self.enemy_name = enemy_name
        self.text = self.TEXTS.get(enemy_name, "Ancient knowledge lost to time...")


# ---------------------------
# Game Manager Class
# ---------------------------
class Game:
    def __init__(self):
        pygame.mixer.init()
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Anime Battle")
        self.clock = pygame.time.Clock()
        self.door_enter_cooldown_until = 0

        # Fonts
        self.font = pygame.font.SysFont(None, 36)
        self.small_font = pygame.font.SysFont(None, 24)
        self.big_font = pygame.font.SysFont(None, 80)
        self.tiny_font = pygame.font.SysFont(None, 20)
        self.thought_font = pygame.font.SysFont("georgia", 22, italic=True)
        self.letter_font = pygame.font.SysFont("georgia", 21, italic=True)
        self.sign_font = pygame.font.SysFont("georgia", 18, italic=True)
        self.damage_font = pygame.font.SysFont(None, 42)
        self.effects = Effects()
        self.invuln_until = 0
        self.defeat_in_maze = False
        self.defeat_in_castle = False
        self.safe_pos = (0, 0)

        self.player_image = pygame.image.load("img/player.png").convert_alpha()
        self.player_image = pygame.transform.scale(self.player_image, (70, 170))

        # Player img
        walk = load_frames("img/player/walk_{:02d}.png", 8)
        jump = load_frames("img/player/jump_{:02d}.png", 7)
        idle = pygame.image.load("img/player/idle.png").convert_alpha()
        attack = load_frames("img/player/attack_{:02d}.png", 7)
        self.block_frames = load_frames("img/player/block_{:02d}.png", 8)
        defeat = load_frames("img/player/defeat_{:02d}.png", 8)
        self.player_frames = {
            "idle":   [idle],
            "run":    walk,
            "jump":   jump,
            "attack": attack,
            "block":  self.block_frames,
            "defeat": defeat,
        }
        self.fireball_image = pygame.image.load("img/player/fireball.png").convert_alpha()
        self.fireball_image = pygame.transform.scale(self.fireball_image, (87, 51))

        # Load key image
        try:
            self.key_image = pygame.image.load("img/key.png").convert_alpha()
        except:
            print("Warning: Could not load img/key.png, using fallback drawing")
            self.key_image = None

        # Backgrounds
        self.battle_backgrounds = {
            "Naruto": pygame.transform.scale(pygame.image.load("img/bg_naruto.jpg"), (SCREEN_WIDTH, SCREEN_HEIGHT)),
            "Luffy": pygame.transform.scale(pygame.image.load("img/bg_luffy.jpg"), (SCREEN_WIDTH, SCREEN_HEIGHT)),
            "Ichigo": pygame.transform.scale(pygame.image.load("img/bg_ichigo.jpg"), (SCREEN_WIDTH, SCREEN_HEIGHT)),
            "Goku": pygame.transform.scale(pygame.image.load("img/bg_goku.jpg"), (SCREEN_WIDTH, SCREEN_HEIGHT)),
        }
        
        #img background
        self.room_bg_locked = pygame.image.load("img/castle/room_4_closed.jpg").convert()
        self.room_bg_unlocked = pygame.image.load("img/castle/room_4_unlock.jpg").convert()
        self.explor_bg_closed = pygame.transform.scale(
            pygame.image.load("img/explor_bg_closed.jpg").convert(),
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        self.explor_bg_open = pygame.transform.scale(
            pygame.image.load("img/explor_bg.jpg").convert(),
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )

        # Enemy images
        self.enemy_images = {
            "Naruto": pygame.transform.scale(pygame.image.load("img/enemy_naruto.png"), (120, 180)),
            "Luffy": pygame.transform.scale(pygame.image.load("img/enemy_luffy.png"), (120, 180)),
            "Ichigo": pygame.transform.scale(pygame.image.load("img/enemy_ichigo.png"), (220, 180)),
            "Goku": pygame.transform.scale(pygame.image.load("img/enemy_goku.png"), (220, 180)),
        }

        # Attack images
        self.enemy_attack_images = {
            "Luffy": pygame.transform.scale(
                pygame.image.load("img/luffy_attack.png").convert_alpha(), (240, 140)),
            "Goku": pygame.transform.scale(
                pygame.image.load("img/goku_attack.png").convert_alpha(), (260, 140)),
            "Ichigo": pygame.transform.scale(
                pygame.image.load("img/ichigo_attack.png").convert_alpha(), (300, 160)),
            "Naruto": pygame.transform.scale(
                pygame.image.load("img/naruto_attack.png").convert_alpha(), (160, 180)),
        }

        self.slash_image = pygame.image.load("img/player_attack.png").convert_alpha()
        self.slash_image = pygame.transform.scale(self.slash_image, (120, 180))

        def tile(name):
            return pygame.image.load("img/tiles/" + name).convert_alpha()

        def s2(name):
            return pygame.image.load("img/stage2/" + name).convert_alpha()

        cave_ground = {
            "top":   [tile(f"cave/top_{i}.png") for i in range(1, 5)],
            "top_l": tile("cave/top_l.png"),
            "top_r": tile("cave/top_r.png"),
            "fill":  tile("cave/fill.png"),
            "hang":  [tile("cave/hang_1.png"), tile("cave/hang_2.png")],
        }
        self.tilesets = {
            1: {**cave_ground,
                "platforms": [tile(f"moss/platform_{i}.png") for i in (1, 2, 3)],
                "feet": 0.22, "squash": 0.8},
            2: {**cave_ground,
                "platforms": [tile("cave/platform.png")],
                "feet": 0.15, "squash": 0.6,
                "spike_up": s2("spikes_up.png"),
                "spike_down": s2("spikes_down.png"),
                "crusher": (s2("crusher_head.png"), s2("crusher_pole.png"), s2("crusher_cap.png"))},
        }
        portal_img = pygame.image.load("img/tiles/portal.png").convert_alpha()
        self.exit_portal_image = pygame.transform.smoothscale(portal_img, (186, 422))

        self.monster_images = {
            "b": s2("biter.png"),
            "g": s2("spitter.png"),
            "y": s2("eye.png"),
        }

        self.spit_image = s2("spit.png")
        self.eye_laser_image = pygame.transform.smoothscale(s2("laser_shot.png"), (150, 34))


        # Visual effect timers
        self.attack_effect_until = 0
        self.enemy_attack_effect_until = 0

        self.game_over_text = "Game Over - Press R to Restart"
        self.info_message = ""
        self.info_message_until = 0

        self.state = "menu"

        self.events = []

        # Intro: name, desk and letters
        self.player_name = ""
        self.desk_bg = pygame.image.load("img/intro/desk.jpg").convert()
        self.desk_dark = self.desk_bg.copy()
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        shade.set_alpha(175)
        self.desk_dark.blit(shade, (0, 0))
        self.letter_plain = pygame.image.load("img/intro/letter_plain.jpg").convert()
        self.letter_sealed = pygame.image.load("img/intro/letter_sealed.jpg").convert()
        small = pygame.transform.smoothscale(self.letter_plain.convert_alpha(), (150, 195))
        self.desk_letter = pygame.transform.rotate(small, -12)
        self.desk_letter_rect = self.desk_letter.get_rect(topleft=(470, 250))
        self.letters = []
        self.letter_index = 0


        self.banner_image = pygame.image.load("img/intro/banner.png").convert_alpha()
        self.banner_font = pygame.font.SysFont("georgia", 32, italic=True)
        self.button_font = pygame.font.SysFont("georgia", 26, bold=True)
        self.accept_banner = None


        # Castle walk
        self.castle_images = [
            pygame.image.load("img/castle/" + room["image"]).convert() for room in ROOMS
        ]
        self.castle_room = 0
        self.path_walk = None
        self.need_w_release = False
        self.castle_seen = set()
        self.thought = None
        self.fade_until = 0

        self.player_back = load_frames("img/player/back_{:02d}.png", 8)
        self.player_front = load_frames("img/player/front_{:02d}.png", 8)
        self.player_front_straight = load_frames("img/player/front_straight_{:02d}.png", 8)


        # Things you can click in the castle
        def intro_img(name, height, alpha=255):
            img = pygame.image.load("img/intro/" + name).convert_alpha()
            img = pygame.transform.smoothscale(img, (int(img.get_width() * height / img.get_height()), height))
            img.set_alpha(alpha)
            return img
        self.item_images = {
            "sign": intro_img("obelisk.png", 200),
            "key": intro_img("key_small.png", 12, 170),
            "card": intro_img("card_tree.png", 44),
            "chest": intro_img("chest_dark.png", 46),
        }
        self.sign_big = pygame.image.load("img/intro/stone_tablet.png").convert_alpha()
        self.card_burn = load_frames("img/intro/card_burn_{:02d}.png", 8)
        self.carve_font = pygame.font.SysFont("georgia", 30, bold=True)
        self.book_font = pygame.font.SysFont("gabriola,monotypecorsiva,palatinolinotype,georgia", 40)
        self.closeup_image = pygame.image.load("img/castle/room_12.jpg").convert()
        self.book_blank = pygame.image.load("img/intro/book_blank.png").convert_alpha()
        self.book_glow = pygame.image.load("img/intro/book_glow.png").convert_alpha()
        self.back_button = pygame.Rect(30, 650, 150, 46)
        self.portal_room_image = pygame.image.load("img/castle/room_4_portal.jpg").convert()
        self.PORTAL_PATH = {"floor": (640, 680), "end": (640, 490, 0.45), "to": "maze", "kind": "depth"}
        self.ESCAPE_TIME = 60000
        self.chest_frames = load_frames("img/intro/chest_open_{:02d}.png", 9)
        def bar(name, x0, x1, scale, thick):
            full = pygame.image.load(f"img/ui/bar_{name}_full.png").convert_alpha()
            empty = pygame.image.load(f"img/ui/bar_{name}_empty.png").convert_alpha()
            return FancyBar(full, empty, x0, x1, scale, thick)
        self.player_bar = bar("orange", 25, 303, 1.3, 1.7)
        self.boss_bar = bar("purple", 27, 334, 1.2, 1.7)
        self.enemy_bar = bar("red", 3, 334, 0.45, 2.2)
        potion = pygame.image.load("img/intro/potion.png").convert_alpha()
        h = 40           
        self.potion_image = pygame.transform.smoothscale(
            potion, (int(potion.get_width() * h / potion.get_height()), h))
        self.skeleton_frames = {
            name: load_anim("img/enemies/skeleton", name, count)
            for name, count in [("walk", 8), ("attack", 5), ("hurt", 2), ("death", 6), ("rise", 6)]
        }
        self.monk_frames = {
            name: load_anim("img/enemies/monk", name, count)
            for name, count in [("walk", 8), ("punch", 8), ("lunge", 5), ("hurt", 2), ("death", 7)]
        }
        self.king_frames = {
            name: load_anim("img/enemies/king", name, count)
            for name, count in [("walk", 8), ("slam", 8), ("swing", 5), ("hurt", 2), ("death", 7)]
        }
        self.queen_frames = {
            name: load_anim("img/enemies/queen", name, count)
            for name, count in [("hover", 8), ("cast", 8), ("death", 8)]
        }
        self.orb_frames = [pygame.transform.smoothscale(f, (90, 50))
                           for f in load_anim("img/enemies/queen", "orb", 5)]
        self.orb_hit_frames = [pygame.transform.smoothscale(f, (115, 95))
                               for f in load_anim("img/enemies/queen", "orb_hit", 4)]
        self.CHEST_SPEED = 120
        self.hall_exit_start = None
        self.hall_thought = None
        self.hall_said = set()
        self.door_pull = None
        self.hall_walk = None    
        self.pull_frames = load_frames("img/player/pull_{:02d}.png", 8)
        flame = pygame.image.load("img/fx/torch_flame.png").convert_alpha()
        self.torch_flame = pygame.transform.smoothscale(flame, (flame.get_width() * 3 // 2,
                                                                flame.get_height() * 3 // 2))
        self.torch_start = None
        self.torch_lit = False
        self.vortex = [[pygame.image.load(f"img/fx/vortex_{c}_{i:02d}.png").convert()
                        for i in range(1, 9)] for c in ("orange", "cyan")]
        self.fire_pose = load_frames("img/player/fire_hand_{:02d}.png", 8)
        self.small_fireball = pygame.transform.smoothscale(self.fireball_image, (40, 24))
        self.power_start = None
        self.rock_images = [pygame.image.load(f"img/fx/rocks/rock_{i:02d}.png").convert_alpha()
                            for i in range(1, 7)]
        self.shatter_frames = load_frames("img/fx/rocks/shatter_{:02d}.png", 4)
        self.escape_images = {
            4: self.portal_room_image,
            5: pygame.image.load("img/castle/room_5_empty.jpg").convert(),
            8: pygame.image.load("img/castle/room_8_empty.jpg").convert(),
        }
        self.swords_image = pygame.image.load("img/castle/room_6_swords.jpg").convert()
        self.sign_carve_font = pygame.font.SysFont("georgia", 38, bold=True)
        self.reset_castle_items()

        self.player = Player(100, SCREEN_HEIGHT - GROUND_HEIGHT, self.player_image, self.player_frames)

        # Doors
        self.doors = []
        self.doors_revealed = False

        # Keys - will be in exploration room
        self.keys = []
        self.keys_collected = 0
        self.total_keys = 2
        
        # Exploration room setup
        self.exploration_platforms = []
        self.exploration_portal = None
        
        # Portal in hub room to enter exploration
        self.hub_portal = Portal(SCREEN_WIDTH // 2 - 30, SCREEN_HEIGHT - GROUND_HEIGHT - 300)

        self.current_enemy = None
        self.current_door = None

        self.projectiles = []

        self.player_attack_cooldown = 0
        self.enemy_attack_cooldown = 0
        
        # NEW: Enemy melee attack charging
        self.enemy_melee_charge = 0
        self.enemy_melee_charge_max = 45  # 0.75 seconds to charge melee
        self.enemy_is_charging_melee = False

        self.difficulty_level = 1
        self.enemies_defeated = 0

        # Sounds
        self.room_bgm = "sound/room_bgm.mp3"
        self.naruto_bgm = "sound/naruto_bgm.mp3"
        self.luffy_bgm = "sound/luffy_bgm.mp3"
        self.ichigo_bgm = "sound/ichigo_bgm.mp3"
        self.goku_bgm = "sound/goku_bgm.mp3"
        self.current_music = None

        self.snd_punch = pygame.mixer.Sound("sound/punch.wav")
        self.snd_fight = pygame.mixer.Sound("sound/fight.wav")

        # Stage progression
        self.stage = 1
        self.ancient_texts = []

        self.runes = Lunari(height=30)
        self.frag_runes = Lunari(height=28, color=(70, 38, 14))
        self.desk_runes = Lunari(height=14, color=(70, 38, 14))
        self.legends_image = pygame.image.load("img/castle/legends.jpg").convert()
        self.look_frames = load_frames("img/player/look_{:02d}.png", 4)
        self.ending_font = pygame.font.SysFont("georgia", 38, italic=True)
        self.run_ending = None
        self.inventory = Inventory(self)
        self.journal_icon = pygame.transform.smoothscale(self.inventory.pics["journal"], (64, 63))
        self.stay_ending = None
        self.write_frames = load_frames("img/player/write_{:02d}.png", 10)
        self.crown_frames = load_frames("img/player/crown_{:02d}.png", 8)
        self.floor_crown = pygame.image.load("img/player/floor_crown.png").convert_alpha()
        self.stairs_frames = load_frames("img/player/stairs_{:02d}.png", 8)
        self.turn_frames = load_frames("img/player/turn_{:02d}.png", 6)
        self.stone_frames = load_frames("img/player/stone_{:02d}.png", 8)
        self.lib_ruin = [pygame.image.load(f"img/castle/room_11_{c}.jpg").convert() for c in "bc"]
        self.throne_rooms = [pygame.image.load(f"img/castle/room_7_{c}.jpg").convert() for c in "bc"]
        self.puzzle_book = pygame.image.load("img/intro/book_puzzle.png").convert_alpha()
        self.desk_font = pygame.font.SysFont("georgia", 17, italic=True)
        self.page_image = pygame.image.load("img/intro/lunari_page.jpg").convert()
        self.translating = False
        self.ending_at = None
        self.translation = ["", "", "", ""]
        self.journal_runes = Lunari(height=19, color=(70, 38, 14))
        page = pygame.image.load("img/intro/lunari_page.jpg").convert()
        ph = 640
        self.journal_page = pygame.transform.smoothscale(
            page, (int(page.get_width() * ph / page.get_height()), ph))
        self.fragments_found = 0
        self.journal_open = False
        self.potions = 0
        self.frag_start = None
        
        # Stat upgrade state
        self.waiting_for_stat_choice = False
        self.stat_choice_options = ["HP", "Strength", "Speed"]
        self.selected_stat = 0
        
        # Save cooldown to prevent multiple saves
        self.save_cooldown_until = 0

        # --- DARK ROOM (Stage 1 exploration) ---
        self.dark_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        # --- CHAOS ROOM (Stage 2 exploration) ---
        self.chaos_speed_timer  = 0      # frames until next speed shuffle
        self.chaos_gravity_timer = 0     # frames until next gravity shuffle
        self.chaos_base_speed   = 6      # snapshot of base speed
        self.chaos_base_gravity = 1      # snapshot of base gravity

        # NOW setup exploration room after everything is initialized
        self.setup_exploration_room()
    
    def setup_exploration_room(self):
        """Build the maze from the text map"""
        layouts = {1: (LEVEL_1, MOVERS_1), 2: (LEVEL_2, MOVERS_2)}
        layout, movers = layouts[self.stage]
        self.level = Level(layout, self.tilesets[self.stage], movers)
        self.spikes = self.level.spikes
        self.lasers = self.level.lasers
        self.pop_spikes = self.level.pop_spikes
        self.crushers = self.level.crushers
        self.monsters = []
        for kind, x, y in self.level.enemy_spots:
            img = self.monster_images[kind]
            if kind == "b":
                self.monsters.append(Biter(x, y, img))
            elif kind == "g":
                self.monsters.append(Spitter(x, y, img, self.spit_image))
            elif kind == "y":
                self.monsters.append(Eye(x, y, img, self.eye_laser_image))
        self.maze_shots = []
        self.projectiles = []
        self.movers = self.level.movers
        self.exploration_platforms = self.level.tiles
        self.crumbles = [CrumblePlatform(x, y, img, dx, dy)
                        for x, y, img, dx, dy in self.level.crumble_pieces]

        self.keys = [Key(x, y, key_image=self.key_image) for x, y in self.level.key_spots]
        self.total_keys = len(self.keys)

        ex, ey = self.level.exit_spot
        self.exploration_portal = ExitPortal(ex, ey + 4, self.exit_portal_image)

        self.camera = Camera(self.level.width, self.level.height, SCREEN_WIDTH, SCREEN_HEIGHT)

        # --- Stage 2: initialise chaos timers & controls ---
        if self.stage == 2:
            self.chaos_speed_timer   = random.randint(60, 180)
            self.chaos_gravity_timer = random.randint(60, 180)
            # Store player's actual base values to scale from
            self.chaos_base_speed   = self.player.speed
            self.chaos_base_gravity = self.player.GRAVITY

    def play_music(self, path):
        """Change background music only if different."""
        if self.current_music == path:
            return
        
        pygame.mixer.music.stop()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)
        self.current_music = path

    # ---------------------------
    # Save/Load System
    # ---------------------------
    def save_game(self):
        """Save current progress to file"""
        import json
        save_data = {
            "stage": self.stage,
            "player_name": self.player_name,
            "player_max_hp": self.player.max_hp,
            "player_hp": self.player.hp,
            "player_strength": self.player.strength,
            "player_speed": self.player.speed,
            "difficulty_level": self.difficulty_level,
            "enemies_defeated": self.enemies_defeated,
            "fragments": self.fragments_found,
            "potions": self.potions,
        }
        
        with open("savegame.json", "w") as f:
            json.dump(save_data, f, indent=2)
        
        print("Game Saved!")

    def load_game(self):
        """Load progress from file"""
        import json
        import os
        if not os.path.exists("savegame.json"):
            self.info_message = "No save file found!"
            self.info_message_until = pygame.time.get_ticks() + 2000
            return False
        
        try:
            with open("savegame.json", "r") as f:
                save_data = json.load(f)
            
            self.stage = save_data.get("stage", 1)
            self.fragments_found = save_data.get("fragments", 0)
            self.potions = save_data.get("potions", 0)
            self.player_name = save_data.get("player_name", "")
            self.player.max_hp = save_data.get("player_max_hp", 180)
            self.player.hp = save_data.get("player_hp", self.player.max_hp)
            self.player.strength = save_data.get("player_strength", 20)
            self.player.speed = save_data.get("player_speed", 4)
            self.difficulty_level = save_data.get("difficulty_level", 1)
            self.enemies_defeated = save_data.get("enemies_defeated", 0)
            
            # Reset doors for the current stage
            self.doors = []
            self.doors_revealed = False
            self.keys_collected = 0
            self.setup_exploration_room()
            
            # Reset player position
            self.player.rect.x = 100
            self.player.rect.y = self.player.ground_y
            self.player.energy = self.player.max_energy

            self.player.is_defeated = False
            self.player.anim_state = "idle"
            
            self.info_message = f"Game Loaded! Stage {self.stage}"
            self.info_message_until = pygame.time.get_ticks() + 2000
            
            self.return_to_hall()
            return True
            
        except Exception as e:
            print(f"Load error: {e}")
            self.info_message = "Failed to load save!"
            self.info_message_until = pygame.time.get_ticks() + 2000
            return False

    # ---------------------------
    # Main Loop
    # ---------------------------
    def run(self):
        while True:
            self.clock.tick(FPS)
            self.handle_events()

            # The bag (B) and the journal (T) pause the game
            if self.inventory.update():
                pygame.display.flip()
                continue
            if self.update_journal():
                pygame.display.flip()
                continue

            # Hit-stop: freeze the last frame
            if self.effects.is_frozen():
                pygame.display.flip()
                continue

            if self.state == "menu":
                self.update_menu()
            elif self.state == "name":
                self.update_name()
            elif self.state == "desk":
                self.update_desk()
            elif self.state == "letters":
                self.update_letters()
            elif self.state == "castle":
                self.update_castle()
            elif self.state == "controls":
                self.update_controls()
            elif self.state == "room":
                self.update_room()
            elif self.state == "exploration":
                self.update_exploration()
            elif self.state == "battle":
                self.update_battle()
            elif self.state == "defeat":
                self.update_defeat()
            elif self.state == "stat_choice":
                self.update_stat_choice()
            elif self.state == "ancient_text":
                self.update_ancient_text()
            elif self.state == "game_over":
                self.update_game_over()
            elif self.state == "ending_stay":
                if self.stay_ending.update():
                    self.game_over_text = "THE END"
                    self.state = "game_over"
            elif self.state == "ending_run":
                if self.run_ending.update():
                    self.game_over_text = "THE END...?"
                    self.state = "game_over"

            # Screen shake: redraw the whole frame shifted
            ox, oy = self.effects.get_shake_offset()
            if ox or oy:
                frame = self.screen.copy()
                self.screen.fill((0, 0, 0))
                self.screen.blit(frame, (ox, oy))
            self.inventory.draw_icon()

            pygame.display.flip()

    # ---------------------------
    # JOURNAL
    # ---------------------------
    JOURNAL_STATES = ("room", "castle", "exploration")

    def update_journal(self):
        """Returns True while the journal is open (the game is paused)."""
        for e in self.events:
            if e.type != pygame.KEYDOWN:
                continue
            typing = self.closeup and self.castle_popup is not None
            if e.key == KEY_JOURNAL and self.state in self.JOURNAL_STATES and not typing:
                self.journal_open = not self.journal_open
                if self.journal_open:
                    self.journal_bg = self.screen.copy()
            elif e.key == pygame.K_ESCAPE:
                self.journal_open = False
        if not self.journal_open:
            return False
        self.draw_journal()
        return True

    def draw_journal(self):
        self.screen.blit(self.journal_bg, (0, 0))
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        self.screen.blit(shade, (0, 0))

        page = self.journal_page
        rect = page.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(page, rect)

        slot_h = (rect.height - 80) // len(FRAGMENTS)
        for i, text in enumerate(FRAGMENTS):
            cy = rect.top + 40 + slot_h * i + slot_h // 2
            if i < self.fragments_found:
                block = self.journal_runes.render_block(text, rect.width - 60)
                self.screen.blit(block, block.get_rect(center=(rect.centerx, cy)))
            else:
                for n in range(-1, 2):                     # an empty place: three faint dots
                    pygame.draw.circle(self.screen, (150, 115, 70), (rect.centerx + n * 22, cy), 3)

        hint = self.small_font.render(f"Pieces: {self.fragments_found}/{len(FRAGMENTS)}    ESC  close",
                                      True, (230, 210, 170))
        self.screen.blit(hint, hint.get_rect(midtop=(SCREEN_WIDTH // 2, rect.bottom + 6)))

    # ---------------------------
    # Event Handling
    # ---------------------------
    def handle_events(self):
        self.events = pygame.event.get()
        for event in self.events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

    # ---------------------------
    # MENU
    # ---------------------------
    def update_menu(self):
        self.play_music(self.room_bgm)
        keys = pygame.key.get_pressed()
        
        now = pygame.time.get_ticks()
        
        if keys[pygame.K_RETURN]:
            self.player_name = ""
            self.reset_castle_items()
            self.state = "name"

        if keys[pygame.K_c]:
            self.state = "controls"
        
        # Load game when L is pressed
        if keys[KEY_LOAD] and now >= self.save_cooldown_until:
            if self.load_game():
                self.save_cooldown_until = now + 500
            else:
                self.save_cooldown_until = now + 500

        self.screen.fill((0, 0, 0))
        
        title = self.big_font.render("ANIME BATTLE", True, (255, 215, 0))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
        
        start_text = self.font.render("Press ENTER to Start New Game", True, (255, 255, 255))
        self.screen.blit(start_text, (SCREEN_WIDTH//2 - start_text.get_width()//2, 350))
        
        load_text = self.font.render("Press O to Load Game", True, (200, 200, 200))
        self.screen.blit(load_text, (SCREEN_WIDTH//2 - load_text.get_width()//2, 420))
        

        ctrl_text = self.font.render("Press C for Controls", True, (200, 200, 200))
        self.screen.blit(ctrl_text, (SCREEN_WIDTH//2 - ctrl_text.get_width()//2, 470))
        
        if self.info_message and now < self.info_message_until:
            msg = self.small_font.render(self.info_message, True, (255, 255, 0))
            self.screen.blit(msg, (SCREEN_WIDTH//2 - msg.get_width()//2, 500))


    # ---------------------------
    # NAME, DESK AND LETTERS
    # ---------------------------
    def update_name(self):
        for e in self.events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key == pygame.K_RETURN and self.player_name.strip():
                self.player_name = self.player_name.strip()
                self.state = "desk"
            elif e.key == pygame.K_BACKSPACE:
                self.player_name = self.player_name[:-1]
            elif (e.unicode.isalpha() or e.unicode == " ") and len(self.player_name) < 14:
                self.player_name += e.unicode

        self.screen.blit(self.desk_dark, (0, 0))
        q = self.big_font.render("What is your name, archaeologist?", True, (235, 215, 170))
        self.screen.blit(q, (SCREEN_WIDTH // 2 - q.get_width() // 2, 220))

        box = pygame.Rect(0, 0, 520, 70)
        box.center = (SCREEN_WIDTH // 2, 360)
        pygame.draw.rect(self.screen, (25, 18, 14), box, border_radius=8)
        pygame.draw.rect(self.screen, (170, 130, 70), box, 2, border_radius=8)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
        name = self.font.render("Dr. " + self.player_name + cursor, True, (255, 240, 210))
        self.screen.blit(name, (box.x + 20, box.centery - name.get_height() // 2))

        hint = self.small_font.render("Type your name and press ENTER", True, (170, 150, 120))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 430))


    def update_desk(self):
        mouse = pygame.mouse.get_pos()
        hover = self.desk_letter_rect.collidepoint(mouse)
        clicked = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in self.events)
        space = any(e.type == pygame.KEYDOWN and e.key == KEY_INTERACT for e in self.events)

        if (hover and clicked) or space:
            self.letters = [
                Letter(self.letter_plain, LETTER_1.format(name=self.player_name), self.letter_font),
                Letter(self.letter_sealed, LETTER_2, self.letter_font, INSTITUTE, self.sign_font),
            ]
            self.letter_index = 0
            self.state = "letters"
            return

        self.screen.blit(self.desk_bg, (0, 0))
        pulse = 0.6 + 0.4 * math.sin(pygame.time.get_ticks() / 400)
        strength = 1.6 if hover else pulse
        area = self.desk_letter_rect.inflate(90, 90)
        glow = pygame.Surface(area.size, pygame.SRCALPHA)
        for i in range(10):
            ring = glow.get_rect().inflate(-i * 9, -i * 9)
            pygame.draw.ellipse(glow, (255, 200, 110, int(14 * strength)), ring)
        self.screen.blit(glow, area.topleft)
        self.screen.blit(self.desk_letter, self.desk_letter_rect)



    def update_letters(self):
        mouse = pygame.mouse.get_pos()

        if self.accept_banner:
            self.accept_banner.handle(self.events, mouse)
            if self.accept_banner.answer == "yes":
                self.accept_banner = None
                self.castle_seen = set()
                self.castle_room = 0
                self.enter_castle_room(0, came_from=None)
                self.state = "castle"
                return
            if self.accept_banner.answer == "no":
                self.accept_banner = None
                self.state = "desk"
                return
        else:
            letter = self.letters[self.letter_index]
            for e in self.events:
                pressed = (e.type == pygame.KEYDOWN and e.key == KEY_INTERACT) or \
                          (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1)
                if not pressed:
                    continue
                if not letter.finished():
                    letter.skip()
                elif self.letter_index < len(self.letters) - 1:
                    self.letter_index += 1
                    self.letters[self.letter_index].restart()
                else:
                    self.accept_banner = AcceptBanner(self.banner_image, self.banner_font,
                                                      self.button_font)
                break

        self.screen.blit(self.desk_dark, (0, 0))
        self.letters[self.letter_index].draw(self.screen)
        if self.accept_banner:
            self.accept_banner.draw(self.screen, mouse)

    # ---------------------------
    # CASTLE ITEMS
    # ---------------------------
    def reset_castle_items(self):
        img = self.item_images
        self.hotspots = [
            Hotspot("sign", 4, img["sign"], (1008, 512)),
            Hotspot("key", 8, img["key"], (402, 352)),
            Hotspot("card", 9, img["card"], (632, 608), glow=True),
            Hotspot("chest", 3, self.chest_frames[0], (640, 500)),
            Hotspot("potion", 5, self.potion_image, (640, 440), glow=True),
            AreaHotspot("shelf", 11, (0, 130, 300, 440), style="glow"),
            AreaHotspot("book", 12, (909, 388, 24, 80)),
            AreaHotspot("moon_book", 12, (150, 140, 20, 86)),
        ]
        self.has_key = False
        self.has_tree_card = False
        self.has_fire = False
        self.castle_popup = None
        self.closeup = False
        self.escaping = False
        self.portal_open = False
        self.escape_end = 0
        self.rocks = []
        self.next_rock = 0
        self.chest_anim = None
        self.power_start = None
        self.torch_lit = False
        self.fragments_found = 0
        self.postions = 0
        self.translating = False
        self.ending_at = None
        self.translation = ["", "", "", ""]
        for h in self.hotspots:
            if h.name == "moon_book":
                h.visible = False                  
        self.room_enemies = {}
        self.castle_shots = []
        self.swords_start = -10000
        self.swords_shake = False

    def say(self, text):
        self.thought = Thought(text, self.thought_font)

    def click_hotspot(self, mouse):
        for h in self.hotspots:
            if h.room != self.castle_room or not h.hovered(mouse):
                continue
            if abs(h.rect.centerx - self.player.rect.centerx) > 320:
                self.say("I need to get closer.")
            else:
                self.use_hotspot(h)
            return

    def use_hotspot(self, h):
        if h.name == "sign":
            self.castle_popup = SignPopup(self.sign_big, "Beyond these doors\nthe legends sleep.\nTurn back, stranger.",
                                          self.sign_carve_font, KEY_INTERACT)
        elif h.name == "key":
            h.visible = False
            self.has_key = True
            self.say("The statue's hand opened...\nIt was holding this key for me.")
        elif h.name == "card":
            h.visible = False
            self.has_tree_card = True
            self.say("A card with a golden tree.\nIt feels warm in my hand.")
        elif h.name == "chest":
            if self.has_fire:
                self.say("Nothing is left inside.")
            elif not self.has_key:
                self.say("It's locked.")
            elif not self.has_tree_card:
                self.say("Empty...\nbut there's a small slot.")
            else:
                self.has_fire = True
                self.chest_anim = (h, pygame.time.get_ticks())
                self.thought = None

        elif h.name == "potion":
            h.visible = False
            self.potions += 1
            self.say("A red potion...\nI'll keep it in my bag.")
        elif h.name == "shelf":
            self.closeup = True
            self.thought = None
        elif h.name == "moon_book":
            self.thought = None
            self.castle_popup = TranslateDesk(self.puzzle_book, self.page_image, FRAGMENTS,
                                              self.translation, self.desk_runes,
                                              self.desk_font, self.small_font)
        elif h.name == "book":
            if not self.has_fire:
                self.say("The pages are blank...\nI'm not ready yet.")
            else:
                h.visible = False
                self.castle_popup = BookPopup(self.book_blank, self.book_glow,
                                              "Where power\nand myth\nare born.\nThey will wake.", self.book_font)
                

    def update_chest_anim(self):
        chest, start = self.chest_anim
        i = (pygame.time.get_ticks() - start) // self.CHEST_SPEED
        if i == 2 and chest.image is not self.chest_frames[2]:
            self.effects.shake(4, 150)          # the lock drops
        if i < len(self.chest_frames):
            chest.set_image(self.chest_frames[i])
            return
        if i < len(self.chest_frames) + 6:      # hold the bright frame a moment
            return
        chest.set_image(self.chest_frames[6])   # stays open
        self.chest_anim = None
        self.castle_popup = CardPopup(self.card_burn, self.carve_font, KEY_INTERACT)
        self.castle_popup.after = "power"


    # The fire from the card flies into the player's hand
    FLY = 500      # fireball flight (frames 1-3: he raises his hand)
    GROW = 800     # frames 4-8: the flame grows
    POSE = 1600    # total time after the hit
    LOWER = 600    # the fire goes out, the hand comes down
    HAND = [(0.68, 0.27), (0.68, 0.27), (0.68, 0.27), (0.70, 0.24),
            (0.69, 0.24), (0.68, 0.22), (0.67, 0.11), (0.65, 0.28)]

    def power_frame(self):
        t = pygame.time.get_ticks() - self.power_start
        if t < self.FLY:
            return min(2, t * 3 // self.FLY)
        if t >= self.FLY + self.POSE:                   # play the frames backwards
            return max(0, 7 - (t - self.FLY - self.POSE) * 8 // self.LOWER)
        return min(7, 3 + (t - self.FLY) * 5 // self.GROW)

    def fire_pose_rect(self):
        return self.fire_pose[0].get_rect(midbottom=self.player.rect.midbottom)

    def hand_pos(self, index):
        r = self.fire_pose_rect()
        fx, fy = self.HAND[index]
        if self.player.facing == -1:
            fx = 1 - fx
        return r.x + int(r.width * fx), r.y + int(r.height * fy)

    def update_power(self):
        t = pygame.time.get_ticks() - self.power_start
        if t >= self.FLY and not self.power_hit:
            self.power_hit = True
            hx, hy = self.hand_pos(3)
            self.effects.shake(8, 300)
            self.effects.burst(hx, hy, [(255, 200, 80), (255, 120, 30), (255, 240, 180)], 20)
        if t >= self.FLY + self.POSE and not self.power_out:
            self.power_out = True
            self.fire_goes_out(self.hand_pos(7))
        if t >= self.FLY + self.POSE + self.LOWER:
            self.power_start = None
            self.say("My hand is burning...\nbut it doesn't hurt.")


    def draw_power(self):
        t = pygame.time.get_ticks() - self.power_start
        i = self.power_frame()
        pose = self.fire_pose[i]
        if self.player.facing == -1:
            pose = pygame.transform.flip(pose, True, False)
        self.screen.blit(pose, self.fire_pose_rect())

        if t < self.FLY:
            hx, hy = self.hand_pos(3)
            p = t / self.FLY
            p = p * p                                 # speeds up
            x = 640 + (hx - 640) * p
            y = 320 + (hy - 320) * p - math.sin(p * math.pi) * 80
            angle = math.degrees(math.atan2(-(hy - 320), hx - 640))
            ball = pygame.transform.rotate(self.small_fireball, angle)
            self.screen.blit(ball, ball.get_rect(center=(int(x), int(y))))
        elif i >= 4:                                    # only while there is fire
            hx, hy = self.hand_pos(i)
            glow = pygame.Surface((90, 90))
            k = 0.7 + 0.3 * math.sin(t / 60)
            for n in range(6):
                s = k * (n + 1) / 6
                pygame.draw.circle(glow, (int(70 * s), int(38 * s), int(8 * s)), (45, 45), 45 - n * 7)
            self.screen.blit(glow, (hx - 45, hy - 45), special_flags=pygame.BLEND_RGB_ADD)


    def fire_goes_out(self, pos, cam=None):
        """A little puff of smoke where the fire was."""
        x, y = pos
        if cam:
            x, y = x - cam.x, y - cam.y
        self.effects.burst(int(x), int(y), [(90, 90, 95), (130, 130, 135), (255, 150, 60)], 12)


    def start_translation_trip(self):
        """After the last battle: back to the hall of the castle, to the library."""
        self.translating = True
        self.escaping = False
        self.portal_open = True
        self.rocks = []
        self.room_enemies = {}
        self.castle_popup = None
        self.closeup = False
        self.path_walk = None
        self.player.hp = self.player.max_hp
        for h in self.hotspots:
            if h.name == "moon_book":
                h.visible = True
            elif h.name in ("key", "card", "potion", "book"):
                h.visible = False                  # already taken / already read
            elif h.name == "chest":
                h.set_image(self.chest_frames[6])  # stays open
        self.has_key = self.has_tree_card = self.has_fire = True
        self.state = "castle"
        self.enter_castle_room(4, came_from=3)
        self.player.rect.centerx = SCREEN_WIDTH // 2
        self.player.facing = 1
        self.say("Four pieces... and I can't read a word.\nThe library! There must be a key there.")


    def start_escape(self):
        self.closeup = False
        self.escaping = True
        self.portal_open = True
        self.escape_end = pygame.time.get_ticks() + self.ESCAPE_TIME
        self.rocks = []
        self.next_rock = pygame.time.get_ticks() + 1500
        self.castle_room = 11
        self.player.rect.midbottom = (640, 615)
        self.effects.shake(12, 1500)
        self.say("What have I done...?\nI have to get out of here!")

    def update_closeup(self):
        mouse = pygame.mouse.get_pos()
        if self.castle_popup:
            self.castle_popup.handle(self.events)
            if self.castle_popup.done:
                is_book = isinstance(self.castle_popup, BookPopup)
                choice = getattr(self.castle_popup, "choice", None)
                self.castle_popup = None
                if is_book:
                    self.start_escape()
                    return
                if choice:
                    self.final_choice = choice
                    for h in self.hotspots:
                        if h.name == "moon_book":
                            h.visible = False
                    if choice == "stay":
                        self.say("If I stay... no one else\nwill ever be trapped here.")
                        self.ending_at = pygame.time.get_ticks() + 4500
                    else:
                        self.say("I'm not staying here forever.\nLet the seals break!")
                        self.ending_at = pygame.time.get_ticks() + 3000
        else:
            back = (clicked(self.events) and self.back_button.collidepoint(mouse)) or \
                   pressed(self.events, KEY_DOWN) or pressed(self.events, pygame.K_ESCAPE)
            if back:
                self.closeup = False
                self.thought = None
                return
            if clicked(self.events):
                for h in self.hotspots:
                    if h.room == 12 and h.hovered(mouse):
                        self.use_hotspot(h)

        self.screen.blit(self.closeup_image, (0, 0))
        for h in self.hotspots:
            if h.room == 12:
                h.draw(self.screen, h.hovered(mouse) and not self.castle_popup)

        hover = self.back_button.collidepoint(mouse)
        pygame.draw.rect(self.screen, (30, 22, 18), self.back_button, border_radius=8)
        pygame.draw.rect(self.screen, (255, 200, 60) if hover else (150, 110, 60),
                         self.back_button, 2, border_radius=8)
        label = self.small_font.render("<  Back", True, (235, 215, 170))
        self.screen.blit(label, label.get_rect(center=self.back_button.center))

        if self.thought:
            self.thought.draw(self.screen, 640, 680)
            if self.thought.done:
                self.thought = None
        if self.castle_popup:
            self.castle_popup.draw(self.screen)
        if self.ending_at and pygame.time.get_ticks() >= self.ending_at:
            self.ending_at = None
            self.closeup = False
            if self.final_choice == "run":
                self.thought = None
                self.run_ending = RunEnding(self)
                self.state = "ending_run"
                return
            if self.final_choice == "stay":
                self.thought = None
                self.stay_ending = StayEnding(self)
                self.state = "ending_stay"
                return
            if self.final_choice == "stay":
                self.game_over_text = "You stayed. The doors will stay sealed forever... (To be continued)"
            else:
                self.game_over_text = "You ran. The seals are broken... (To be continued)"
            self.state = "game_over"
            return

    # ---------------------------
    # CASTLE WALK
    # ---------------------------
    def enter_castle_room(self, index, came_from):
        self.castle_room = index
        room = ROOMS[index]
        self.player.vertical_speed = 0
        self.path_walk = None
        self.fade_until = pygame.time.get_ticks() + 250

        back_path = None
        if came_from is not None:
            for p in room["paths"]:
                if p["to"] == came_from:
                    back_path = p

        if back_path:
            # Arrive at the far end of the path and walk out by yourself
            self.path_walk = PathWalk(back_path, 1.0, auto=True)
            x, y, _ = self.path_walk.position()
            self.player.rect.midbottom = (int(x), int(y))
        else:
            min_x, max_x = room["walk"]
            if room.get("fixed"):
                self.player.rect.centerx = (min_x + max_x) // 2
            elif came_from is None or came_from < index:
                self.player.rect.left = min_x
                self.player.facing = 1
            else:
                self.player.rect.right = max_x
                self.player.facing = -1
            self.player.rect.bottom = int(floor_y_at(room["floor"], self.player.rect.centerx))
            self.player.is_jumping = False

        self.rocks = []
        self.castle_shots = []
        if self.escaping and index not in self.room_enemies:
            self.room_enemies[index] = self.spawn_room_enemies(index, floor_y_at(room["floor"], 640))
        if index == 4 and self.escaping and "portal" not in self.castle_seen:
            self.castle_seen.add("portal")
            self.thought = Thought("The tunnel...! A portal!\nThat's my way out!", self.thought_font)
        elif index == 6 and self.escaping and "swords" not in self.castle_seen:
            self.castle_seen.add("swords")
            self.swords_start = pygame.time.get_ticks()
            self.swords_shake = True
        elif index == 6 and self.escaping and "swords" not in self.castle_seen:
            self.castle_seen.add("swords")
            self.swords_start = pygame.time.get_ticks()
            self.swords_shake = True
        elif room["thought"] and index not in self.castle_seen:
            self.thought = Thought(room["thought"], self.thought_font)
        self.castle_seen.add(index)

    def draw_room_image(self):
        room = self.castle_room
        if self.portal_open and room in self.escape_images:
            self.screen.blit(self.escape_images[room], (0, 0))
        elif self.portal_open and room == 6:
            self.screen.blit(self.castle_images[6], (0, 0))
            elapsed = pygame.time.get_ticks() - self.swords_start
            alpha = max(0, min(255, (elapsed - 600) * 255 // 400))
            if alpha > 0:
                self.swords_image.set_alpha(alpha)
                self.screen.blit(self.swords_image, (0, 0))
        else:
            self.screen.blit(self.castle_images[room], (0, 0))


    def room_paths(self):
        paths = list(ROOMS[self.castle_room]["paths"])
        if self.castle_room == 4 and self.portal_open and not self.translating:
            paths.append(self.PORTAL_PATH)
        return paths


    def path_at_feet(self):
        for p in self.room_paths():
            fx, fy = p["floor"]
            if abs(self.player.rect.centerx - fx) < 45 and not self.player.is_jumping:
                return p
        return None


    def update_path_walk(self, keys):
        pw = self.path_walk
        if pw.auto:
            pw.step(-1)
        elif keys[KEY_JUMP]:
            pw.step(1)
        elif keys[KEY_DOWN]:
            pw.step(-1)
        else:
            pw.moving = 0

        x, y, _ = pw.position()
        self.player.rect.midbottom = (int(x), int(y))

        if pw.t >= 1.0 and not pw.auto and pw.path["to"] == "maze":
            self.enter_maze()
            return

        if pw.t >= 1.0 and not pw.auto:
            self.enter_castle_room(pw.path["to"], came_from=self.castle_room)
            self.need_w_release = True
        elif pw.t <= 0.0:
            self.path_walk = None
            self.need_w_release = True
            self.player.rect.bottom = int(pw.path["floor"][1])
            self.player.is_jumping = False


    def draw_path_walker(self):
        pw = self.path_walk
        x, y, scale = pw.position()
        if pw.path["kind"] == "stairs" or pw.moving == 0:
            frame = self.player.animator.animations["run"].frames[
                (pygame.time.get_ticks() // 100) % 8] if pw.moving else \
                self.player.animator.animations["idle"].frames[0]
            going_left = (pw.path["end"][0] < pw.path["floor"][0]) == (pw.moving >= 0)
            if going_left:
                frame = pygame.transform.flip(frame, True, False)
        else:
            frames = self.player_back if pw.moving > 0 else self.player_front
            frame = frames[(pygame.time.get_ticks() // 110) % len(frames)]
        if pw.moving < 0 and pw.path["end"][0] > pw.path["floor"][0] + 20:
            frame = pygame.transform.flip(frame, True, False)
        w = max(1, int(frame.get_width() * scale))
        h = max(1, int(frame.get_height() * scale))
        frame = pygame.transform.smoothscale(frame, (w, h))
        bob = -abs(math.sin(pygame.time.get_ticks() / 110)) * 4 * scale if pw.moving else 0
        self.screen.blit(frame, frame.get_rect(midbottom=(int(x), int(y + bob))))


    # ---------------------------
    # ESCAPE
    # ---------------------------
    def hurt_in_castle(self, dmg, from_x):
        now = pygame.time.get_ticks()
        if now < self.invuln_until:
            return
        self.player.hp = max(0, self.player.hp - dmg)
        self.thought = None
        self.player.flash(150)
        self.effects.shake(10, 250)
        self.invuln_until = now + 900
        self.effects.popup(self.player.rect.centerx, self.player.rect.top,
                           f"-{dmg}", (255, 80, 80), self.damage_font)
        push = 1 if from_x < self.player.rect.centerx else -1
        self.player.rect.x += push * 30
        if self.player.hp == 0:
            self.castle_defeat()

    def castle_defeat(self):
        self.escaping = False
        self.rocks = []
        self.player.start_defeat()
        self.defeat_start = pygame.time.get_ticks()
        self.defeat_in_maze = False
        self.defeat_in_castle = True
        pygame.mixer.music.fadeout(3500)
        self.current_music = None
        self.state = "defeat"

    def update_escape(self):
        now = pygame.time.get_ticks()
        self.effects.shake(3, 100)
        if now >= self.escape_end:
            self.effects.shake(20, 1500)
            self.player.hp = 0
            self.castle_defeat()
            return

        if self.swords_shake and now - self.swords_start > 600:
            self.swords_shake = False
            self.effects.shake(14, 500)
            self.thought = Thought("The statues... they moved!", self.thought_font)

        room = ROOMS[self.castle_room]
        if self.castle_room != 4 and now >= self.next_rock:
            self.next_rock = now + random.randint(550, 1000)
            min_x, max_x = room["walk"]
            if random.random() < 0.45:
                x = self.player.rect.centerx + random.randint(-70, 70)
            else:
                x = random.randint(min_x, max_x)
            x = max(min_x, min(max_x, x))
            self.rocks.append(FallingRock(x, floor_y_at(room["floor"], x),
                                        random.choice(self.rock_images), self.shatter_frames))

        for r in self.rocks:
            if r.update() == "landed":
                self.effects.burst(int(r.x), int(r.floor_y) - 10,
                                   [(90, 80, 100), (60, 55, 70), (150, 140, 150)], 12)
                self.effects.shake(5, 120)
            if r.state == "fall" and not self.path_walk and r.rect.colliderect(self.player.rect):
                self.hurt_in_castle(r.DAMAGE, r.x)
                r.floor_y = r.y + r.size
                r.shatter(now)
                self.effects.burst(int(r.x), int(r.y), [(90, 80, 100), (150, 140, 150)], 10)
        self.rocks = [r for r in self.rocks if r.state != "gone"]
        
        floor = lambda x: floor_y_at(room["floor"], x)
        for e in self.room_enemies.get(self.castle_room, []):
            if e.update(self.player.rect, room["walk"], floor) == "hit" and not self.path_walk:
                self.hurt_in_castle(e.damage, e.x)
            if getattr(e, "shake_now", False):
                e.shake_now = False
                self.effects.shake(12, 300)

    def draw_escape_hud(self):
        left = max(0, self.escape_end - pygame.time.get_ticks()) // 1000
        color = (255, 80, 60) if left <= 10 else (255, 230, 180)
        t = self.font.render(f"ESCAPE  {left}", True, color)
        self.screen.blit(t, t.get_rect(midtop=(SCREEN_WIDTH // 2, 16)))
        self.player_bar.draw(self.screen, self.player.hp / self.player.max_hp, topleft=(16, 14))

    def spawn_room_enemies(self, index, floor):
        if index == 5:
            return [Skeleton(x, floor, self.skeleton_frames) for x in (330, 950)]
        if index == 8:
            self.effects.shake(10, 400)
            return [Monk(150, floor, self.monk_frames)]
        if index == 7:
            self.effects.shake(14, 600)
            return [King(300, floor, self.king_frames)]
        if index == 9:
            return [Queen(250, floor, self.queen_frames, self.orb_frames, self.orb_hit_frames)]
        return []

    def castle_fire_shot(self):
        p = self.player
        if p.is_attacking and not p.has_fired and p.animator.frame_index >= 4:
            p.has_fired = True
            x = p.rect.centerx + p.facing * 30
            y = p.rect.bottom - 95
            shot = Projectile(x, y, p.facing, self.fireball_image, p.strength)
            shot.life = 50
            self.castle_shots.append(shot)

    def update_castle_shots(self):
        enemies = self.room_enemies.get(self.castle_room, [])
        for s in self.castle_shots:
            s.update()
            s.life -= 1
            if s.life <= 0:
                s.alive = False
            for e in enemies:
                if s.alive and e.alive and s.rect.colliderect(e.rect):
                    if e.take_hit(s.damage, s.rect.centerx):
                        s.alive = False
                        self.effects.burst(s.rect.centerx, s.rect.centery,
                                           [(255, 200, 80), (255, 120, 30)], 10)
        self.castle_shots = [s for s in self.castle_shots if s.alive]

    def draw_enemy_bars(self):
        for e in self.room_enemies.get(self.castle_room, []):
            if not e.alive:
                continue
            ratio = e.hp / e.max_hp
            if hasattr(e, "NAME"):
                rect = self.boss_bar.draw(self.screen, ratio, topright=(SCREEN_WIDTH - 80, 14))
                name = self.small_font.render(e.NAME, True, (230, 210, 245))
                self.screen.blit(name, name.get_rect(topright=(rect.right - 10, rect.bottom + 2)))
            elif e.anim != "rise":
                self.enemy_bar.draw(self.screen, ratio, midbottom=(int(e.x), e.rect.top - 10))

    def enter_maze(self):
        self.escaping = False
        self.rocks = []
        self.path_walk = None
        self.thought = None
        self.state = "exploration"
        sx, sy = self.level.start
        self.player.rect.x = sx
        self.player.rect.bottom = sy
        self.safe_pos = (sx, sy)
        self.camera.snap(self.player.rect)
        self.effects.clear()
        self.player.is_jumping = False
        self.player.vertical_speed = 0
        self.start_torch()


    STEP_UP = 20      # higher floor steps than this need a jump

    def castle_physics(self, keys):
        p = self.player
        points = ROOMS[self.castle_room]["floor"]
        old_x = p.rect.x
        p.handle_input(keys, [NoWalls], SCREEN_WIDTH)

        min_x, max_x = ROOMS[self.castle_room]["walk"]
        p.rect.left = max(p.rect.left, min_x)
        p.rect.right = min(p.rect.right, max_x)

        # Too high to walk up? Then it is a wall.
        new_floor = floor_y_at(points, p.rect.centerx)
        if new_floor < p.rect.bottom - self.STEP_UP:
            p.rect.x = old_x

        # Gravity and landing on the floor line
        p.vertical_speed = min(p.vertical_speed + p.GRAVITY, 20)
        p.rect.y += p.vertical_speed
        floor = floor_y_at(points, p.rect.centerx)
        if p.rect.bottom >= floor and p.vertical_speed >= 0:
            p.rect.bottom = int(floor)
            p.vertical_speed = 0
            p.is_jumping = False
        elif not p.is_jumping and floor - p.rect.bottom < 12:
            p.rect.bottom = int(floor)          # walking down a gentle slope
            p.vertical_speed = 0
        else:
            p.is_jumping = True


    def update_castle(self):
        if self.closeup:
            self.update_closeup()
            return
        if self.escaping:
            self.update_escape()
            if self.state != "castle":
                return
        keys = pygame.key.get_pressed()
        self.player.is_blocking = False
        room = ROOMS[self.castle_room]
        mouse = pygame.mouse.get_pos()

        if self.chest_anim:
            self.update_chest_anim()
        elif self.power_start is not None:
            self.update_power()
        elif self.castle_popup:
            self.castle_popup.handle(self.events)
            if self.castle_popup.done:
                if self.castle_popup.after == "power":
                    self.power_start = pygame.time.get_ticks()
                    self.power_hit = False
                    self.power_out = False
                elif self.castle_popup.after:
                    self.say(self.castle_popup.after)
                self.castle_popup = None
        elif self.path_walk:
            self.update_path_walk(keys)
        else:
            if not keys[KEY_JUMP]:
                self.need_w_release = False
            path = self.path_at_feet()
            if path and keys[KEY_JUMP] and not self.need_w_release:
                self.path_walk = PathWalk(path, 0.0, auto=False)
                self.player.vertical_speed = 0
            else:
                if self.need_w_release:
                    keys = KeysWithout(keys, KEY_JUMP)
                min_x, max_x = room["walk"]

                if room.get("fixed"):
                    # Only forward (W) or back (S) in this room
                    self.player.is_moving = False
                    self.player.update_animation()
                    if keys[KEY_DOWN]:
                        self.enter_castle_room(self.castle_room - 1, came_from=self.castle_room)
                else:
                    if self.has_fire and keys[KEY_ATTACK] and not self.player.is_attacking:
                        self.player.start_attack()
                    self.castle_physics(keys)
                    self.castle_fire_shot()
                    if keys[KEY_RIGHT] and self.player.rect.right >= max_x and room["right"]:
                        self.enter_castle_room(self.castle_room + 1, came_from=self.castle_room)
                    elif keys[KEY_LEFT] and self.player.rect.left <= min_x and room["left"]:
                        self.enter_castle_room(self.castle_room - 1, came_from=self.castle_room)
                
                if clicked(self.events):
                    self.click_hotspot(mouse)

        self.update_castle_shots()

        # Draw
        self.draw_room_image()
        for e in self.room_enemies.get(self.castle_room, []):
            e.draw(self.screen)
        for h in self.hotspots:
            if h.room == self.castle_room:
                h.draw(self.screen, h.hovered(mouse) and not self.castle_popup
                       and not self.chest_anim and self.power_start is None)
        if self.path_walk:
            self.draw_path_walker()
        elif self.power_start is not None:
            self.draw_power()
        else:
            self.player.draw(self.screen)
            if self.path_at_feet():
                hint = self.small_font.render("W", True, (255, 230, 150))
                hx = self.player.rect.centerx - hint.get_width() // 2
                self.screen.blit(hint, (hx, self.player.rect.top - 30))

        for s in self.castle_shots:
            s.draw(self.screen)

        if self.escaping:
            for r in self.rocks:
                r.draw(self.screen)
            self.effects.update_and_draw(self.screen)
            self.draw_escape_hud()
            self.draw_enemy_bars()

        if self.thought:
            if self.path_walk:
                x, y, scale = self.path_walk.position()
                head = (int(x), int(y - 172 * scale))
            else:
                head = (self.player.rect.centerx, self.player.rect.top)
            self.thought.draw(self.screen, *head)
            if self.thought.done:
                self.thought = None

        if self.castle_popup:
            self.castle_popup.draw(self.screen)

        left = self.fade_until - pygame.time.get_ticks()
        if left > 0:
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(int(255 * left / 250))
            self.screen.blit(fade, (0, 0))

    # ---------------------------
    # CONTROLS SCREEN
    # ---------------------------
    def update_controls(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE] or keys[pygame.K_BACKSPACE]:
            self.state = "menu"
            return

        self.screen.fill((15, 10, 25))
        title = self.big_font.render("CONTROLS", True, (255, 215, 0))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 70))

        y = 200
        for key_name, action in CONTROLS_TEXT:
            k = self.font.render(key_name, True, (255, 215, 0))
            a = self.font.render(action, True, (230, 230, 230))
            self.screen.blit(k, (SCREEN_WIDTH // 2 - 40 - k.get_width(), y))
            self.screen.blit(a, (SCREEN_WIDTH // 2 + 40, y))
            y += 50

        hint = self.small_font.render("Press ESC to go back", True, (150, 150, 150))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 640))


    # The player comes out of the portal after a maze or a battle
    HALL_EXIT = 1300
    HALL_PORTAL = (648, 448, 0.35)

    def return_to_hall(self):
        self.state = "room"
        self.hall_exit_start = pygame.time.get_ticks()
        self.player.rect.centerx = SCREEN_WIDTH // 2
        self.player.rect.y = self.player.ground_y
        self.player.is_jumping = False
        self.player.vertical_speed = 0
        self.player.facing = 1
        self.door_enter_cooldown_until = pygame.time.get_ticks() + self.HALL_EXIT + 400

    def draw_hall_exit(self):
        """Returns False when the walk out of the portal is finished."""
        now = pygame.time.get_ticks()
        t = (now - self.hall_exit_start) / self.HALL_EXIT
        if t >= 1:
            self.hall_exit_start = None
            return False
        x0, y0, s0 = self.HALL_PORTAL
        x1, y1 = self.player.rect.centerx, self.player.rect.bottom
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        scale = s0 + (1 - s0) * t
        frame = self.player_front_straight[(now // 110) % 8]
        frame = pygame.transform.smoothscale(
            frame, (int(frame.get_width() * scale), int(frame.get_height() * scale)))
        if t < 0.3:                                   # flash at the portal
            k = 1 - t / 0.3
            glow = pygame.Surface((160, 160))
            for n in range(8):
                s = k * (n + 1) / 8
                pygame.draw.circle(glow, (int(30 * s), int(60 * s), int(90 * s)), (80, 80), 80 - n * 10)
            self.screen.blit(glow, (x0 - 80, y0 - 120), special_flags=pygame.BLEND_RGB_ADD)
        self.screen.blit(frame, frame.get_rect(midbottom=(int(x), int(y))))
        return True


    # The hall: where the player may walk, and where each door pulls him in
    HALL_WALK = (300, 985)
    DOOR_PULL = 1100
    DOOR_TARGET = {0: ((300, 430), (255, 170, 80)),     # left door: x, y, colour
                   1: ((990, 430), (90, 230, 230))}     # right door
    HALL_LINES = {1: "The doors are open...\nI can feel something behind them.",
                  2: "They're open again...\nThis time it feels much stronger."}

    def hall_arrived(self):
        """Called once the walk out of the portal is over."""
        if self.doors_revealed and self.stage not in self.hall_said:
            self.hall_said.add(self.stage)
            self.hall_thought = Thought(self.HALL_LINES[self.stage], self.thought_font)

    def draw_door_pull(self):
        door, start, (sx, sy) = self.door_pull
        t = (pygame.time.get_ticks() - start) / self.DOOR_PULL
        if t >= 1:
            self.door_pull = None
            self.start_battle(door)
            return
        side = self.doors.index(door)                  # 0 = left door, 1 = right door
        (tx, ty), color = self.DOOR_TARGET[side]
        i = min(7, int(t * 8))                          # frame number for this moment

        # the vortex in the door (black = transparent with additive blending)
        v = self.vortex[side][i]
        self.screen.blit(v, v.get_rect(center=(tx, ty)), special_flags=pygame.BLEND_RGB_ADD)

        # the player flies into it
        e = t * t                                       # slow first, then fast
        x = sx + (tx - sx) * e
        y = sy + (ty - sy) * e
        frame = self.pull_frames[i]
        if tx < sx:                                     # pulled to the left
            frame = pygame.transform.flip(frame, True, False)
        self.screen.blit(frame, frame.get_rect(center=(int(x), int(y))))

        if t > 0.8:                                     # flash into the battle
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            flash.fill(color)
            flash.set_alpha(int(255 * (t - 0.8) / 0.2))
            self.screen.blit(flash, (0, 0))


    HALL_WALK_SPEED = 0.012

    def near_hall_portal(self):
        return (not self.doors_revealed
                and abs(self.player.rect.centerx - SCREEN_WIDTH // 2) < 70)

    def update_hall_walk(self, keys):
        """W walks into the portal, S walks back. Returns True when inside."""
        if keys[KEY_JUMP]:
            self.hall_walk += self.HALL_WALK_SPEED
            self.hall_walk_dir = 1
        elif keys[KEY_DOWN]:
            self.hall_walk -= self.HALL_WALK_SPEED
            self.hall_walk_dir = -1
        else:
            self.hall_walk_dir = 0
        if self.hall_walk <= 0:
            self.hall_walk = None
        elif self.hall_walk >= 1:
            self.hall_walk = None
            return True
        return False

    def draw_hall_walk(self):
        t = self.hall_walk
        x0, y0 = SCREEN_WIDTH // 2, self.player.rect.bottom
        x1, y1, s1 = self.HALL_PORTAL
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        scale = 1 + (s1 - 1) * t
        now = pygame.time.get_ticks()
        if self.hall_walk_dir == 0:
            frame = self.player_back[0]
        else:
            frames = self.player_back if self.hall_walk_dir > 0 else self.player_front_straight
            frame = frames[(now // 110) % 8]
        frame = pygame.transform.smoothscale(
            frame, (int(frame.get_width() * scale), int(frame.get_height() * scale)))
        self.screen.blit(frame, frame.get_rect(midbottom=(int(x), int(y))))

    # ---------------------------
    # ROOM (HUB)
    # ---------------------------
    def update_room(self):
        keys = pygame.key.get_pressed()
        self.play_music(self.room_bgm)
        
        exiting = self.hall_exit_start is not None
        busy = exiting or self.door_pull is not None or self.hall_walk is not None
        if not busy:
            if self.near_hall_portal():
                keys = KeysWithout(keys, KEY_JUMP)       # W walks in, no jump here
            self.player.handle_input(keys)
            self.player.update()
            min_x, max_x = self.HALL_WALK
            self.player.rect.left = max(self.player.rect.left, min_x)
            self.player.rect.right = min(self.player.rect.right, max_x)

        # Draw background (fills entire screen)
        # Change background based on key progress
        if self.doors_revealed:
            self.screen.blit(self.room_bg_unlocked, (0, 0))
        else:
            self.screen.blit(self.portal_room_image, (0, 0))


        # Don't draw ground rectangle - use the background's floor instead
        
        if not self.doors_revealed:
            title_text = f"Enter Portal to Find Keys: {self.keys_collected}/{self.total_keys}"
        elif self.stage == 1:
            title_text = "Stage 1: Choose a Door"
        else:
            title_text = "Stage 2: Stronger Foes Await"
        
        title = self.font.render(title_text, True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 20))
        
        # Show save hint
        save_hint = self.tiny_font.render("Press P to Save", True, (255, 255, 255))
        self.screen.blit(save_hint, (10, 10))

        now = pygame.time.get_ticks()
        
        # Save game when S is pressed (with cooldown)
        if keys[KEY_SAVE] and now >= self.save_cooldown_until:
            self.save_game()
            self.info_message = "Game Saved!"
            self.info_message_until = now + 2000
            self.save_cooldown_until = now + 1000  # 1 second cooldown
        if self.info_message and now < self.info_message_until:
            msg = self.small_font.render(self.info_message, True, (255, 255, 0))
            msg_x = SCREEN_WIDTH // 2 - msg.get_width() // 2
            msg_y = 70
            self.screen.blit(msg, (msg_x, msg_y))
        else:
            self.info_message = ""

        if exiting:
            if self.draw_hall_exit():
                return
            self.hall_arrived()
        if self.door_pull:
            self.draw_door_pull()
            return

        # Draw portal to exploration room (if doors not revealed)
        if not self.doors_revealed:
            if self.hall_walk is not None:
                if self.update_hall_walk(pygame.key.get_pressed()):
                    self.player.rect.centerx = SCREEN_WIDTH // 2
                    self.enter_maze()
                    return
                if self.hall_walk is not None:
                    self.draw_hall_walk()
                    return
                self.player.rect.centerx = SCREEN_WIDTH // 2   # walked back out
            elif self.near_hall_portal():
                hint = self.small_font.render("W", True, (255, 230, 150))
                self.screen.blit(hint, hint.get_rect(midbottom=(self.player.rect.centerx,
                                                                self.player.rect.top - 8)))
                if pressed(self.events, KEY_JUMP) and now >= self.door_enter_cooldown_until:
                    self.hall_walk = self.HALL_WALK_SPEED
                    self.hall_walk_dir = 1
                    self.player.vertical_speed = 0
                    self.draw_hall_walk()
                    return

        # Draw doors ONLY if revealed
        if self.doors_revealed:
            for door in self.doors:
                door.draw(self.screen)

        self.player.draw(self.screen)

        if self.hall_thought:
            self.hall_thought.draw(self.screen, self.player.rect.centerx, self.player.rect.top)
            if self.hall_thought.done:
                self.hall_thought = None

        # Door interaction
        if self.doors_revealed:
            for door in self.doors:
                if (not door.is_locked) and (not door.is_cleared) and door.is_player_in_front(self.player):
                    msg = self.font.render("Press SPACE to enter the door", True, (255, 255, 255))
                    self.screen.blit(msg, (485, 100))

                    if now >= self.door_enter_cooldown_until and keys[KEY_INTERACT]:
                        self.hall_thought = None
                        self.door_pull = (door, now, self.player.rect.center)
                        return
    
    # ---------------------------
    # EXPLORATION ROOM
    # ---------------------------
       # ---------- Maze 1 torch ----------
    DARKNESS = 238            # 255 = pure black
    LIGHT_RADIUS = 150
    TORCH_DARK = 500           # ms of darkness before he speaks
    TORCH_SAY = 2300           # the thought bubble
    TORCH_CAST = 900           # fire_hand frames 1-7
    TORCH_RISE = 600           # the flame flies over his head
    TORCH_LOWER = 500          # the hand comes down

    def start_torch(self):
        """Called every time the player enters a maze."""
        self.torch_start = None
        if self.stage == 1 and not self.torch_lit:
            self.torch_start = pygame.time.get_ticks()
            self.torch_hand_out = False

    def torch_phase(self):
        """Returns (phase, progress 0..1)."""
        if self.torch_start is None:
            return ("lit", 1.0) if self.torch_lit else ("dark", 0.0)
        t = pygame.time.get_ticks() - self.torch_start
        for name, length in (("dark", self.TORCH_DARK), ("say", self.TORCH_SAY),
                             ("cast", self.TORCH_CAST), ("rise", self.TORCH_RISE),
                             ("lower", self.TORCH_LOWER)):
            if t < length:
                return name, t / length
            t -= length
        self.torch_start = None
        self.torch_lit = True
        return "lit", 1.0

    def update_torch(self):
        phase, p = self.torch_phase()
        if phase == "say" and self.thought is None and p < 0.1:
            self.thought = Thought("It's so dark in here...\nI can't see a thing.", self.thought_font)
        if phase in ("cast", "rise", "lower", "lit"):
            self.thought = None
        if phase == "lower" and not self.torch_hand_out:
            self.torch_hand_out = True
            self.fire_goes_out(self.hand_pos(4), self.camera)
        return phase, p

    def torch_head(self):
        """World position of the flame floating over the head."""
        bob = math.sin(pygame.time.get_ticks() / 250) * 4
        return self.player.rect.centerx, self.player.rect.top - 28 + bob

    def draw_torch_player(self, phase, p):
        """Draws the player in the fire-hand pose while casting."""
        if phase == "cast":
            i = min(6, int(p * 7))
        elif phase == "lower":                     
            i = max(0, 6 - int(p * 7))
        else:
            i = 6
        pose = self.fire_pose[i]
        if self.player.facing == -1:
            pose = pygame.transform.flip(pose, True, False)
        rect = self.fire_pose_rect().move(-self.camera.x, -self.camera.y)
        self.screen.blit(pose, rect)

    def draw_torch_flame(self, phase, p):
        if phase not in ("rise", "lower", "lit"):
            return
        hx, hy = self.torch_head()
        if phase == "rise":
            ax, ay = self.hand_pos(6)
            e = 1 - (1 - p) * (1 - p)                     # fast first, then slow
            hx = ax + (hx - ax) * e
            hy = ay + (hy - ay) * e - math.sin(p * math.pi) * 40
        flicker = 1 + math.sin(pygame.time.get_ticks() / 70) * 0.08
        f = self.torch_flame
        f = pygame.transform.smoothscale(f, (f.get_width(), int(f.get_height() * flicker)))
        x, y = hx - self.camera.x, hy - self.camera.y
        glow = pygame.Surface((70, 70))
        for n in range(5):
            s = (n + 1) / 5
            pygame.draw.circle(glow, (int(60 * s), int(30 * s), int(5 * s)), (35, 35), 35 - n * 6)
        self.screen.blit(glow, (x - 35, y - 35), special_flags=pygame.BLEND_RGB_ADD)
        self.screen.blit(f, f.get_rect(midbottom=(int(x), int(y + f.get_height() // 2))))

    def _draw_dark_overlay(self, radius):
        """Stage 1: everything is dark except a glow around the player."""
        cx = self.player.rect.centerx - self.camera.x
        cy = self.player.rect.centery - self.camera.y - 20

        self.dark_overlay.fill((0, 0, 0, self.DARKNESS))
        if radius > 4:
            radius = int(radius * (1 + math.sin(pygame.time.get_ticks() / 90) * 0.03))
            steps = 40
            for i in range(steps, 0, -1):
                r = int(radius * i / steps)
                alpha = int(self.DARKNESS * (i / steps) ** 0.8)
                pygame.draw.circle(self.dark_overlay, (0, 0, 0, alpha), (cx, cy), r)

        self.screen.blit(self.dark_overlay, (0, 0))


    def _update_chaos(self):
        """Stage 2: tick chaos timers – inverted controls,
           random speed and random gravity."""

        # --- Random speed ---
        self.chaos_speed_timer -= 1
        if self.chaos_speed_timer <= 0:
            self.chaos_speed_timer  = random.randint(300, 600)
            new_speed = random.choice([3 , 4 , 6])
            self.player.speed = new_speed
            self.info_message      = f"Speed shift! ({new_speed})"
            self.info_message_until = pygame.time.get_ticks() + 1500

        # --- Random gravity ---
        self.chaos_gravity_timer -= 1
        if self.chaos_gravity_timer <= 0:
            self.chaos_gravity_timer = random.randint(360, 600)
            new_grav = random.choice([0.8, 1, 2])
            self.player.GRAVITY = new_grav
            self.info_message      = f"Gravity shift! ({new_grav})"
            self.info_message_until = pygame.time.get_ticks() + 1500


    def hurt_in_maze(self, dmg):
        self.player.hp = max(0, self.player.hp - dmg)
        self.player.flash(150)
        self.effects.shake(10, 250)
        self.effects.hitstop(40)
        self.invuln_until = pygame.time.get_ticks() + 1000
        sx = self.player.rect.centerx - self.camera.x
        sy = self.player.rect.top - self.camera.y
        self.effects.popup(sx, sy, f"-{dmg}", (255, 80, 80), self.damage_font)

        if self.player.hp == 0:
            self.player.start_defeat()
            self.defeat_start = pygame.time.get_ticks()
            self.defeat_in_maze = True
            pygame.mixer.music.fadeout(3500)
            self.current_music = None
            self.state = "defeat"


    def hit_player_maze(self, dmg, from_x, platforms):
        now = pygame.time.get_ticks()
        if now < self.invuln_until:
            return
        direction = 1 if from_x < self.player.rect.centerx else -1
        sx = self.player.rect.centerx - self.camera.x
        sy = self.player.rect.top - self.camera.y
        if self.player.is_guarding():
            self.player.move_with_platforms(direction * 15, platforms, self.level.width)
            self.effects.popup(sx, sy, "BLOCK", (150, 200, 255), self.damage_font)
            self.invuln_until = now + 300
        else:
            self.player.move_with_platforms(direction * 40, platforms, self.level.width)
            self.hurt_in_maze(dmg)


    def update_exploration(self):
        keys = pygame.key.get_pressed()
        torch, torch_p = self.update_torch() if self.stage == 1 else ("lit", 1.0)
        if torch != "lit":
            keys = NoKeys()
        self.player.block_walk = True
        self.player.set_block(keys[KEY_BLOCK] and not self.player.is_jumping
                              and not self.player.is_attacking)


        # Moving platforms carry the player standing on them
        feet = pygame.Rect(self.player.rect.x, self.player.rect.bottom, self.player.rect.width, 2)
        riding = [m for m in self.movers if m.active and feet.colliderect(m.rect)]
        for m in self.movers:
            m.update()
        for m in riding:
            self.player.rect.x += m.last_move[0]
            self.player.rect.y += m.last_move[1]

        for c in self.crumbles:
            c.update()
        visible_platforms = (self.exploration_platforms
                             + [c for c in self.crumbles if c.active]
                             + [m for m in self.movers if m.active])

        # Handle player input and movement with (visible) platforms
        self.player.handle_input(keys, visible_platforms, self.level.width)
        self.player.apply_gravity_with_platforms(visible_platforms)
        self.camera.follow(self.player.rect)

        feet = pygame.Rect(self.player.rect.x, self.player.rect.bottom, self.player.rect.width, 2)
        for c in self.crumbles:
            if c.active and feet.colliderect(c.rect):
                c.touch()

        for m in self.movers:
            if m.active and feet.colliderect(m.rect):
                m.touch()

        # ── Spikes & lasers ─────────────────────────────────────────────────
        now = pygame.time.get_ticks()
        for p in self.pop_spikes:
            p.update(self.player.rect)

        for cr in self.crushers:
            cr.update()

        hazards = self.spikes + [p.rect for p in self.pop_spikes if p.dangerous]
        body = self.player.rect.inflate(-16, -10)
        on_spikes = any(body.colliderect(s) for s in hazards)
        crushed = any(body.colliderect(cr.rect) for cr in self.crushers)
        near = self.player.rect.inflate(80, 0)
        near_spikes = (any(near.colliderect(s) for s in self.spikes)
                       or any(near.colliderect(p.area) for p in self.pop_spikes))
        on_tile = any(feet.colliderect(t.rect) for t in self.exploration_platforms)
        if on_tile and not self.player.is_jumping and not near_spikes:
            self.safe_pos = (self.player.rect.x, self.player.rect.bottom)

        if on_spikes or crushed:
            if now >= self.invuln_until:
                self.hurt_in_maze(15 if crushed else 5)
            self.player.rect.x, self.player.rect.bottom = self.safe_pos
            self.player.vertical_speed = 0
            self.player.stun_until = now + 350

        for beam in self.lasers:
            if self.player.rect.colliderect(beam) and not self.player.is_guarding():
                if now >= self.invuln_until:
                    self.hurt_in_maze(max(1, self.player.hp // 2))
                if self.player.rect.centerx < beam.centerx:
                    self.player.rect.right = beam.left - 2
                else:
                    self.player.rect.left = beam.right + 2
                break

        # Fall damage
        fall = self.player.landed_fall
        self.player.landed_fall = 0
        if fall > 300:
            self.hurt_in_maze(5 + (fall - 300) // 10)


        # ── Player attack ───────────────────────────────────────────────────
        self.player.energy = min(self.player.max_energy,
                                 self.player.energy + self.player.energy_regen_rate)
        if (keys[KEY_ATTACK] and not self.player.is_attacking
                and not self.player.is_blocking
                and self.player.can_attack(20)):
            self.player.start_attack()
            self.player.use_energy(20)

        if (self.player.is_attacking and not self.player.has_fired
                and self.player.animator.frame_index >= 4):
            self.player.has_fired = True
            pygame.mixer.Sound.play(self.snd_punch)
            x = self.player.rect.centerx + self.player.facing * 30
            y = self.player.rect.bottom - 95
            shot = Projectile(x, y, self.player.facing, self.fireball_image, self.player.strength)
            shot.life = 35
            self.projectiles.append(shot)

        # ── Monsters ────────────────────────────────────────────────────────
        hits = []
        for mon in self.monsters:
            mon.update(self.level, self.player, self.maze_shots, hits)

        for p in self.projectiles:
            p.update(self.level.width)
            p.life -= 1
            if p.life <= 0:
                p.alive = False
            if self.level.solid(p.rect.centery // TILE, p.rect.centerx // TILE):
                p.alive = False
            for mon in self.monsters:
                if p.alive and p.rect.colliderect(mon.rect):
                    mon.take_hit(1)
                    p.alive = False
                    self.effects.burst(p.rect.centerx - self.camera.x, p.rect.centery - self.camera.y,
                                       [(255, 200, 50), (255, 120, 20)], 12)
        self.projectiles = [p for p in self.projectiles if p.alive]

        for mon in self.monsters:
            if not mon.alive:
                self.effects.burst(mon.rect.centerx - self.camera.x, mon.rect.centery - self.camera.y,
                                   [(40, 40, 60), (120, 60, 160), (255, 255, 255)], 24)
        self.monsters = [m for m in self.monsters if m.alive]

        for shot in self.maze_shots:
            shot.update(self.level)
            if shot.alive and shot.rect.colliderect(self.player.rect):
                hits.append((shot.damage, shot.rect.centerx))
                shot.alive = False
        self.maze_shots = [s for s in self.maze_shots if s.alive]

        for dmg, from_x in hits:
            self.hit_player_maze(dmg, from_x, visible_platforms)
    

        # ── Draw background ──────────────────────────────────────────────────
        self.screen.blit(self.explor_bg_closed, (0, 0))
        if self.exploration_portal.visible:
            t = pygame.time.get_ticks() - self.exploration_portal.appear_time
            self.explor_bg_open.set_alpha(min(255, int(t / 1000 * 255)))
            self.screen.blit(self.explor_bg_open, (0, 0))


        # ── Title ────────────────────────────────────────────────────────────
        if self.stage == 1:
            title_str = f"Find the Keys: {self.keys_collected}/{self.total_keys}"
        else:
            title_str = f"CHAOS ROOM – Find the Keys: {self.keys_collected}/{self.total_keys}"
        title = self.font.render(title_str, True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 20))

        # ── Draw platforms ───────────────────────────────────────────────────
        self.level.draw(self.screen, self.camera)
        t = pygame.time.get_ticks()
        for beam in self.lasers:
            full = beam.move(-self.camera.x, -self.camera.y)
            r = full.clip(self.screen.get_rect())
            if r.height == 0:
                continue
            glow = 8 + int(4 * math.sin(t / 60))
            self.screen.fill((90, 0, 30), r.inflate(glow * 2, 0), special_flags=pygame.BLEND_ADD)
            self.screen.fill((160, 20, 60), r, special_flags=pygame.BLEND_ADD)
            self.screen.fill((255, 220, 230), r.inflate(-12, 0))
            pygame.draw.rect(self.screen, (50, 50, 60), (full.x - 10, full.y, full.width + 20, 14))

        for p in self.pop_spikes:                      
            p.draw(self.screen, self.camera)

        for cr in self.crushers:
            cr.draw(self.screen, self.camera)
        
        for c in self.crumbles:
            c.draw(self.screen, self.camera)

        for m in self.movers:
            m.draw(self.screen, self.camera)

        # ── Draw keys ────────────────────────────────────────────────────────
        for key in self.keys:
            key.draw(self.screen, self.camera)

        # ── Check key collection ─────────────────────────────────────────────
        for key in self.keys:
            if key.check_pickup(self.player):
                self.keys_collected += 1
                if self.keys_collected >= self.total_keys:
                    self.exploration_portal.show()
                    self.effects.shake(12, 600)
                    self.info_message = "The portal has awakened! Return to it!"
                    self.info_message_until = pygame.time.get_ticks() + 3000


        # ── Draw player ───────────────────────────────────────────────────────
        if torch in ("cast", "rise", "lower"):
            self.draw_torch_player(torch, torch_p)
        else:
            self.player.draw(self.screen, cam=self.camera)
        for mon in self.monsters:
            mon.draw(self.screen, self.camera)
        for p in self.projectiles:
            p.draw(self.screen, self.camera)
        for shot in self.maze_shots:
            shot.draw(self.screen, self.camera)

        # ── Stage 1: Dark overlay (drawn AFTER player so they're in the light) ─
        if self.stage == 1:
            radius = {"dark": 0, "say": 0, "cast": 60 * torch_p,
                      "rise": self.LIGHT_RADIUS * torch_p}.get(torch, self.LIGHT_RADIUS)
            self._draw_dark_overlay(radius)
            self.draw_torch_flame(torch, torch_p)
            if self.thought:
                self.thought.draw(self.screen, self.player.rect.centerx - self.camera.x,
                                  self.player.rect.top - self.camera.y)
                if self.thought.done:
                    self.thought = None

        self.effects.update_and_draw(self.screen)

        # HP bar
        self.player_bar.draw(self.screen, self.player.hp / self.player.max_hp, topleft=(16, 14))


        # ── Portal return ────────────────────────────────────────────────────
        if self.exploration_portal.check_collision(self.player):
            hint = self.font.render("Press SPACE to leave the cave", True, (255, 255, 255))
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 100))

            if keys[KEY_INTERACT]:
                if self.keys_collected >= self.total_keys:
                    self.doors_revealed = True

                    if self.stage == 1:
                        self.doors = [
                            Door(280, 300, 110, 340, "Naruto"),
                            Door(895, 300, 110, 340, "Luffy"),
                        ]
                    else:
                        self.doors = [
                            Door(280, 300, 110, 340, "Ichigo"),
                            Door(895, 300, 110, 340, "Goku"),
                        ]

                    for door in self.doors:
                        door.is_locked = False

                    self.info_message = "All keys found! The doors have appeared!"
                    self.info_message_until = pygame.time.get_ticks() + 3000

                # Restore player to normal physics when leaving chaos room
                if self.stage == 2:
                    self.player.speed   = self.chaos_base_speed
                    self.player.GRAVITY = self.chaos_base_gravity

                self.return_to_hall()
                return

        # ── Info message ─────────────────────────────────────────────────────
        now = pygame.time.get_ticks()
        if self.info_message and now < self.info_message_until:
            msg = self.small_font.render(self.info_message, True, (255, 255, 0))
            self.screen.blit(msg, (SCREEN_WIDTH//2 - msg.get_width()//2, 60))

    def start_battle(self, door):
        self.current_door = door
        enemy_img = self.enemy_images[door.enemy_name]
        enemy_y = SCREEN_HEIGHT - GROUND_HEIGHT - enemy_img.get_height()
        self.current_enemy = Enemy(600, enemy_y, enemy_img, name=door.enemy_name)
        
        # INCREASED BASE HP
        base_hp = {
            "Naruto": 250,
            "Luffy": 280,
            "Ichigo": 350,
            "Goku": 420
        }
        
        scale = 1 + 0.4 * (self.difficulty_level - 1)
        self.current_enemy.max_hp = int(base_hp[door.enemy_name] * scale)
        self.current_enemy.hp = self.current_enemy.max_hp
        self.current_enemy.speed = int(3 * (1 + 0.15 * (self.difficulty_level - 1)))
        self.current_enemy.strength = int(12 * (1 + 0.25 * (self.difficulty_level - 1)))

        self.current_battle_bg = self.battle_backgrounds[door.enemy_name]
        
        music_map = {
            "Naruto": self.naruto_bgm,
            "Luffy": self.luffy_bgm,
            "Ichigo": self.ichigo_bgm,
            "Goku": self.goku_bgm
        }
        self.play_music(music_map.get(door.enemy_name, self.room_bgm))

        self.player_attack_cooldown = 0
        self.enemy_attack_cooldown = 0

        self.projectiles = []
        self.effects.clear()
        self.player.is_attacking = False
        
        # Reset enemy melee charging
        self.enemy_melee_charge = 0
        self.enemy_is_charging_melee = False

        self.player.block_walk = False

        self.player.rect.x = 100
        self.player.rect.y = self.player.ground_y
        self.player.energy = self.player.max_energy

        self.battle_start_time = pygame.time.get_ticks()
        self.enemy_move_delay = self.INTRO_SAY + self.INTRO_DOTS + self.INTRO_COUNT
        self.intro_lines = None
        self.fight_started = False

        self.show_fight_text = False

        self.state = "battle"

        self.enemy_attack_effect_until = 0


    # ---------- before the fight ----------
    INTRO_SAY = 2600      # the player asks
    INTRO_DOTS = 1600     # the enemy only answers "..."
    INTRO_COUNT = 3000    
    INTRO_LINES = ["Where am I...?\nWho are you?",
                   "You again...?\nNo... you're just like the last one.",
                   "Another one...\nWho are all of you?",
                   "You're the last one...\naren't you?"]

    def battle_number(self):
        """0 = first fight of the game, 3 = the last one."""
        cleared = sum(1 for d in self.doors if d.is_cleared)
        return (self.stage - 1) * 2 + cleared

    def draw_battle_intro(self, now):
        t = now - self.battle_start_time
        enemy = self.current_enemy

        if t < self.INTRO_SAY + self.INTRO_DOTS:
            if self.intro_lines is None:
                line = self.INTRO_LINES[min(self.battle_number(), len(self.INTRO_LINES) - 1)]
                self.intro_lines = Thought(line, self.thought_font)
            if t >= self.INTRO_SAY and not getattr(self.intro_lines, "enemy", False):
                self.intro_lines = Thought(". . .", self.thought_font)
                self.intro_lines.SPEED = 4              # dots appear slowly
                self.intro_lines.enemy = True
            if getattr(self.intro_lines, "enemy", False):
                self.intro_lines.draw(self.screen, enemy.rect.centerx, enemy.rect.top)
            else:
                self.intro_lines.draw(self.screen, self.player.rect.centerx, self.player.rect.top)
            return

        t -= self.INTRO_SAY + self.INTRO_DOTS
        if t < self.INTRO_COUNT:
            n = 3 - t // 1000                            # 3, 2, 1
            p = (t % 1000) / 1000                        # 0..1 inside this second
            size = 1.6 - 0.6 * min(1, p * 4)             # pops in big, settles
            text = self.big_font.render(str(n), True, (255, 230, 180))
            text = pygame.transform.rotozoom(text, 0, size * 1.6)
            text.set_alpha(int(255 * (1 - max(0, p - 0.7) / 0.3)))
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            return

        if not self.fight_started:                       # 0: FIGHT!
            self.fight_started = True
            pygame.mixer.Sound.play(self.snd_fight)
            self.effects.shake(8, 300)
            self.show_fight_text = True
            self.fight_text_until = now + 900



    def hit_player(self, amount, from_x):
        before = self.player.hp
        guarded = self.player.is_guarding()
        self.player.take_damage(amount)
        dealt = before - self.player.hp

        direction = 1 if from_x < self.player.rect.centerx else -1
        self.player.apply_knockback(direction)

        cx, cy = self.player.rect.centerx, self.player.rect.centery
        if guarded:
            self.effects.burst(cx, cy, [(150, 200, 255), (255, 255, 255)], 10)
            self.effects.shake(3, 100)
            self.effects.popup(cx, self.player.rect.top, "BLOCK", (150, 200, 255), self.damage_font)
        else:
            self.player.flash()
            self.effects.hitstop(90)
            self.effects.shake(10, 220)
            self.effects.burst(cx, cy, [(255, 60, 60), (255, 255, 255)], 14)
            self.effects.popup(cx, self.player.rect.top, str(dealt), (255, 80, 80), self.damage_font)

    # ---------------------------
    # BATTLE
    # ---------------------------
    def update_battle(self):
        keys = pygame.key.get_pressed()

        if self.player_attack_cooldown > 0:
            self.player_attack_cooldown -= 1
        if self.enemy_attack_cooldown > 0:
            self.enemy_attack_cooldown -= 1
        if self.current_enemy.ability_cooldown > 0:
            self.current_enemy.ability_cooldown -= 1

        now = pygame.time.get_ticks()
        can_act = now - self.battle_start_time > self.enemy_move_delay

        # Enemy special attacks (ranged)
        if (can_act and self.enemy_attack_cooldown == 0
            and self.current_enemy.name in ("Luffy", "Goku", "Ichigo", "Naruto")
            and self.current_enemy.ability_cooldown == 0
            and not self.enemy_is_charging_melee):  # Don't use special while charging melee


            distance = abs(self.current_enemy.rect.centerx - self.player.rect.centerx)

            ranges = {"Luffy": 220, "Naruto": 200, "Ichigo": 180, "Goku": 260}
            cooldowns = {"Luffy": 90, "Naruto": 80, "Ichigo": 100, "Goku": 120}
            bonus_damage = {"Luffy": 0, "Naruto": 2, "Ichigo": 3, "Goku": 4}

            max_range = ranges[self.current_enemy.name]

            if distance < max_range and not self.current_enemy.rect.colliderect(self.player.rect):
                self.hit_player(self.current_enemy.strength + bonus_damage[self.current_enemy.name],
                                self.current_enemy.rect.centerx)

                self.current_enemy.ability_cooldown = cooldowns[self.current_enemy.name]
                self.enemy_attack_effect_until = now + 350

        self.player.set_block(
            can_act and keys[KEY_BLOCK]
            and not self.player.is_attacking
            and not self.player.is_jumping)
            

        if can_act:
            self.player.handle_input(keys)
        self.player.update()

        if can_act and self.current_enemy.is_alive():
            if not self.player.is_attacking and not self.enemy_is_charging_melee:
                self.current_enemy.update_ai(self.player)
            self.current_enemy.update()


        # Player fireball attack
        attack_cost = 20
        if (can_act and keys[KEY_ATTACK] and not self.player.is_attacking
                and not self.player.is_blocking
                and self.player.can_attack(attack_cost)):
            self.player.start_attack()
            self.player.use_energy(attack_cost)

        if (self.player.is_attacking and not self.player.has_fired
                and self.player.animator.frame_index >= 4):
            self.player.has_fired = True
            pygame.mixer.Sound.play(self.snd_punch)
            x = self.player.rect.centerx + self.player.facing * 60
            y = self.player.rect.bottom - 110
            self.projectiles.append(
                Projectile(x, y, self.player.facing, self.fireball_image, self.player.strength))

        # Update projectiles
        for p in self.projectiles:
            p.update()
            if p.rect.colliderect(self.current_enemy.rect):
                self.current_enemy.take_damage(p.damage)
                self.current_enemy.apply_knockback(p.direction, 30)
                self.current_enemy.flash()
                self.effects.hitstop(60)
                self.effects.shake(6, 150)
                self.effects.burst(p.rect.centerx, p.rect.centery,
                                   [(255, 200, 50), (255, 120, 20), (255, 255, 180)], 16)
                self.effects.popup(self.current_enemy.rect.centerx, self.current_enemy.rect.top,
                                   str(p.damage), (255, 220, 80), self.damage_font)
                if self.enemy_is_charging_melee:
                    self.enemy_is_charging_melee = False
                    self.enemy_melee_charge = 0
                p.alive = False
        self.projectiles = [p for p in self.projectiles if p.alive]


        # Enemy melee attack with CHARGING system
        if can_act and self.enemy_attack_cooldown == 0:
            # Check if enemy is in melee range
            if self.current_enemy.rect.colliderect(self.player.rect):
                if not self.enemy_is_charging_melee:
                    # Start charging
                    self.enemy_is_charging_melee = True
                    self.enemy_melee_charge = 0
                else:
                    # Continue charging
                    self.enemy_melee_charge += 1
                    
                    # Check if charge is complete
                    if self.enemy_melee_charge >= self.enemy_melee_charge_max:
                        # Execute the attack!
                        self.hit_player(self.current_enemy.strength, self.current_enemy.rect.centerx)

                        self.enemy_attack_cooldown = 60  # Longer cooldown after attack
                        self.enemy_is_charging_melee = False
                        self.enemy_melee_charge = 0
            else:
                # Player moved out of range, reset charge
                if self.enemy_is_charging_melee:
                    self.enemy_is_charging_melee = False
                    self.enemy_melee_charge = 0
       
        # Check lose
        if not self.player.is_alive():
            self.player.start_defeat()
            self.defeat_start = pygame.time.get_ticks()
            self.defeat_in_maze = False
            pygame.mixer.music.fadeout(3500)
            self.current_music = None
            self.state = "defeat"
            return

        # Check win
        if not self.current_enemy.is_alive():
            self.enemies_defeated += 1
            if self.enemies_defeated % 2 == 0:
                self.difficulty_level += 1
            
            self.current_door.is_cleared = True
            
            # Collect ancient text
            text = AncientText(self.current_enemy.name)
            self.ancient_texts.append(text)
            self.fragments_found = min(len(FRAGMENTS), self.fragments_found + 1)
            self.current_ancient_text = text

            all_cleared = all(door.is_cleared for door in self.doors)

            if all_cleared:
                # Completed all enemies in current stage - show stat choice then ancient text
                self.waiting_for_stat_choice = True
                self.selected_stat = 0
                self.state = "stat_choice"
            else:
                # More enemies to defeat - just show ancient text
                self.state = "ancient_text"
            return

        # Draw battle
        self.screen.blit(self.current_battle_bg, (0, 0))
        dark_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        dark_surface.set_alpha(150)
        dark_surface.fill((0, 0, 0))
        self.screen.blit(dark_surface, (0, 0))
        
        self.player.draw(self.screen)

        for p in self.projectiles:
            p.draw(self.screen)

        # Draw enemy or special attack
        is_special_active = (
            self.current_enemy
            and self.current_enemy.name in self.enemy_attack_images
            and now < self.enemy_attack_effect_until
        )

        if is_special_active:
            attack_img = self.enemy_attack_images[self.current_enemy.name]

            if self.current_enemy.rect.centerx > self.player.rect.centerx:
                attack_img = pygame.transform.flip(attack_img, True, False)

            mid_x = (self.current_enemy.rect.centerx + self.player.rect.centerx) // 2
            attack_x = mid_x - attack_img.get_width() // 2
            attack_y = self.current_enemy.rect.centery - attack_img.get_height() // 2

            self.screen.blit(attack_img, (attack_x, attack_y))
        else:
            self.current_enemy.draw(self.screen)

        info = self.small_font.render("SPACE attack | DOWN block | ESC escape", True, (255, 255, 255))
        self.screen.blit(info, (480, 18))

        if can_act and keys[pygame.K_ESCAPE]:
            self.return_to_hall()
            return

        pygame.draw.rect(
            self.screen,
            (20, 100, 20),
            (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))
        

        self.draw_battle_intro(now)
        
            
        if self.show_fight_text and now < self.fight_text_until:
            fight_txt = self.big_font.render("FIGHT!", True, (255, 255, 255))
            fight_x = SCREEN_WIDTH // 2 - fight_txt.get_width() // 2
            fight_y = SCREEN_HEIGHT // 2 - fight_txt.get_height() // 2
            self.screen.blit(fight_txt, (fight_x, fight_y))
        else:
            self.show_fight_text = False

        self.effects.update_and_draw(self.screen)

        # HP bars
        rect = self.player_bar.draw(self.screen, self.player.hp / self.player.max_hp,
                                    topleft=(16, 14))
        p_name = self.small_font.render("PLAYER", True, (255, 230, 200))
        self.screen.blit(p_name, (rect.x + 10, rect.bottom + 2))

        rect = self.boss_bar.draw(self.screen, self.current_enemy.hp / self.current_enemy.max_hp,
                                  topright=(SCREEN_WIDTH - 16, 14))
        e_name = self.small_font.render(self.current_enemy.name.upper(), True, (230, 210, 245))
        self.screen.blit(e_name, e_name.get_rect(topright=(rect.right - 10, rect.bottom + 2)))

        # Energy bar
        energy_ratio = self.player.energy / self.player.max_energy
        energy_bar_width = 400
        energy_bar_height = 15
        energy_bar_x = 40
        energy_bar_y = 70

        pygame.draw.rect(self.screen, (255, 255, 255),
            (energy_bar_x, energy_bar_y, energy_bar_width, energy_bar_height), 2)
        pygame.draw.rect(self.screen, (255, 215, 0),
            (energy_bar_x, energy_bar_y, energy_bar_width * energy_ratio, energy_bar_height))
        
        energy_text = self.tiny_font.render(f"ENERGY: {int(self.player.energy)}/{self.player.max_energy}", True, (255, 255, 255))
        self.screen.blit(energy_text, (energy_bar_x, energy_bar_y + 18))
        
        # NEW: Draw enemy charge bar (same position as player energy bar, but on enemy side)
        charge_ratio = self.enemy_melee_charge / self.enemy_melee_charge_max
        charge_bar_width = 400
        charge_bar_height = 15
        charge_bar_x = SCREEN_WIDTH - 40 - charge_bar_width  # Same x as enemy HP bar
        charge_bar_y = 70  # Same y as player energy bar
        
        # Border
        pygame.draw.rect(self.screen, (255, 255, 255),
            (charge_bar_x, charge_bar_y, charge_bar_width, charge_bar_height), 2)
        # Fill (red/orange when charging)
        pygame.draw.rect(self.screen, (255, 100, 50),
            (charge_bar_x, charge_bar_y, charge_bar_width * charge_ratio, charge_bar_height))
        
        # Label
        charge_text = self.tiny_font.render(f"CHARGE: {int(charge_ratio * 100)}%", True, (255, 255, 255))
        self.screen.blit(charge_text, (charge_bar_x, charge_bar_y + 18))


    # ---------------------------
    # DEFEAT
    # ---------------------------
    def update_defeat(self):
        now = pygame.time.get_ticks()
        elapsed = now - self.defeat_start

        ANIM_TIME = 1000   # kneel animation
        HOLD_TIME = 1800   # stay on screen after kneeling
        FADE_TIME = 1200   # fade to black
        fade_start = ANIM_TIME + HOLD_TIME
        fade_end = fade_start + FADE_TIME

        if self.defeat_in_castle:
            self.draw_room_image()
            self.player.draw(self.screen)
        elif self.defeat_in_maze:
            # Frozen maze scene
            self.screen.blit(self.explor_bg_closed, (0, 0))
            self.level.draw(self.screen, self.camera)
            self.player.draw(self.screen, cam=self.camera)
        else:
            # Frozen battle scene
            self.screen.blit(self.current_battle_bg, (0, 0))
            dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            dark.set_alpha(150)
            dark.fill((0, 0, 0))
            self.screen.blit(dark, (0, 0))
            pygame.draw.rect(
                self.screen,
                (20, 100, 20),
                (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))
            self.current_enemy.draw(self.screen)
            self.player.draw(self.screen)
        self.effects.update_and_draw(self.screen)

        # Fade to black after holding
        if elapsed > fade_start:
            alpha = min(255, int((elapsed - fade_start) / FADE_TIME * 255))
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(alpha)
            self.screen.blit(fade, (0, 0))

        if elapsed > fade_end + 300:
            self.game_over_text = "YOU LOSE"
            self.state = "game_over"
            if self.defeat_in_castle:
                self.retry_from = "castle"
            elif self.defeat_in_maze:
                self.retry_from = "maze"
            else:
                self.retry_from = "battle"
            self.defeat_in_castle = False

    # ---------------------------
    # STAT CHOICE SCREEN
    # ---------------------------
    def update_stat_choice(self):
        keys = pygame.key.get_pressed()
        now = pygame.time.get_ticks()
        
        # Initialize delay timer if not set (prevents immediate skip from battle)
        if not hasattr(self, 'stat_choice_ready_time'):
            self.stat_choice_ready_time = now + 500  # 0.5 second delay
        
        # Don't accept input until delay is over
        if now < self.stat_choice_ready_time:
            # Still draw the screen
            self.screen.fill((20, 20, 40))
            title = self.big_font.render("VICTORY!", True, (255, 215, 0))
            self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
            subtitle = self.font.render("Choose a stat to upgrade:", True, (255, 255, 255))
            self.screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 200))
            wait_text = self.small_font.render("Please wait...", True, (150, 150, 150))
            self.screen.blit(wait_text, (SCREEN_WIDTH//2 - wait_text.get_width()//2, 580))
            return
        
        if keys[KEY_LEFT] or keys[KEY_JUMP]:
            self.selected_stat = (self.selected_stat - 1) % 3
            pygame.time.wait(150)
        if keys[KEY_RIGHT] or keys[KEY_DOWN]:
            self.selected_stat = (self.selected_stat + 1) % 3
            pygame.time.wait(150)
        
        if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
            chosen = self.stat_choice_options[self.selected_stat]
            
            if chosen == "HP":
                self.player.max_hp += 20
                self.player.hp = self.player.max_hp
            elif chosen == "Strength":
                self.player.strength += 5
            elif chosen == "Speed":
                self.player.speed += 1
            
            self.waiting_for_stat_choice = False
            
            # Reset for next time and set delay for ancient text
            del self.stat_choice_ready_time
            self.ancient_text_ready_time = now + 300
            
            self.state = "ancient_text"
            return

        self.screen.fill((20, 20, 40))
        
        title = self.big_font.render("VICTORY!", True, (255, 215, 0))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
        
        subtitle = self.font.render("Choose a stat to upgrade:", True, (255, 255, 255))
        self.screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 200))
        
        option_y = 300
        for i, stat in enumerate(self.stat_choice_options):
            color = (255, 255, 0) if i == self.selected_stat else (200, 200, 200)
            
            if stat == "HP":
                bonus_text = f"+20 Max HP"
            elif stat == "Strength":
                bonus_text = f"+5 Damage"
            else:
                bonus_text = f"+1 Speed"
            
            text = self.font.render(f"{stat} ({bonus_text})", True, color)
            x = SCREEN_WIDTH//2 - text.get_width()//2
            self.screen.blit(text, (x, option_y + i * 80))
            
            if i == self.selected_stat:
                arrow = self.font.render(">>>", True, (255, 215, 0))
                self.screen.blit(arrow, (x - 80, option_y + i * 80))
        
        hint = self.small_font.render("Use Arrow Keys to select, ENTER to confirm", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, 580))

    # ---------- after a win: a piece of the ancient language ----------
    FRAG_FADE = 900        # the enemy disappears
    FRAG_WRITE = 1600      # the runes appear over the player's head
    FRAG_THINK = 2600      # "I can't read it"
    FRAG_SAVE = 900        # the runes fly into the journal
    JOURNAL_POS = (SCREEN_WIDTH - 60, 50)

    def frag_scroll(self, words, letters):
        """The runes in dark ink on a piece of parchment (easy to read on any background)."""
        runes = self.frag_runes.render_block(words, 560, letters)
        full = self.frag_runes.render_block(words, 560)          # size of the whole text
        w, h = full.get_width() + 70, full.get_height() + 44
        paper = pygame.transform.smoothscale(self.page_image, (w, h)).convert_alpha()
        edge = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(edge, (255, 255, 255, 255), edge.get_rect(), border_radius=14)
        paper.blit(edge, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)    # round corners
        pygame.draw.rect(paper, (90, 55, 25), paper.get_rect(), 3, border_radius=14)
        paper.blit(runes, runes.get_rect(center=(w // 2, h // 2)))
        return paper

    def draw_fragment_scene(self, t):
        words = FRAGMENTS[max(0, min(self.fragments_found, len(FRAGMENTS)) - 1)]

        self.screen.blit(self.current_battle_bg, (0, 0))
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        dark.set_alpha(min(170, int(170 * t / self.FRAG_FADE)))
        self.screen.blit(dark, (0, 0))
        pygame.draw.rect(self.screen, (20, 100, 20),
                           (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))

        # the defeated enemy fades away
        if t < self.FRAG_FADE:
            enemy = self.current_enemy.image.copy()
            enemy.set_alpha(int(255 * (1 - t / self.FRAG_FADE)))
            self.screen.blit(enemy, self.current_enemy.rect)
        self.player.draw(self.screen)

        t -= self.FRAG_FADE
        if t < 0:
            return
        head_x, head_y = self.player.rect.centerx, self.player.rect.top
        letters = int(len(words) * min(1, t / self.FRAG_WRITE))
        runes = self.frag_scroll(words, letters)
        pos = [SCREEN_WIDTH // 2, head_y - 60 - runes.get_height() // 2]

        # after thinking, the runes fly into the journal in the corner
        fly = (t - self.FRAG_WRITE - self.FRAG_THINK) / self.FRAG_SAVE
        if fly > 0:
            e = min(1, fly) ** 2
            pos = [pos[0] + (self.JOURNAL_POS[0] - pos[0]) * e,
                   pos[1] + (self.JOURNAL_POS[1] - pos[1]) * e]
            runes = pygame.transform.rotozoom(runes, 0, max(0.05, 1 - e))

        if fly < 1:
            glow = pygame.Surface((runes.get_width() + 60, runes.get_height() + 40))
            k = 0.6 + 0.4 * math.sin(pygame.time.get_ticks() / 200)
            for n in range(6):
                s = k * (n + 1) / 6
                r = glow.get_rect().inflate(-n * 10, -n * 6)
                pygame.draw.ellipse(glow, (int(40 * s), int(28 * s), int(8 * s)), r)
            self.screen.blit(glow, glow.get_rect(center=pos), special_flags=pygame.BLEND_RGB_ADD)
            self.screen.blit(runes, runes.get_rect(center=pos))

        # the thought bubble
        if self.FRAG_WRITE <= t < self.FRAG_WRITE + self.FRAG_THINK:
            if self.frag_thought is None:
                  if self.fragments_found <= 1:
                      line = "What is this writing...?\nI can't read it."
                  else:
                      line = "These words again..."
                  self.frag_thought = Thought(line, self.thought_font)
            self.frag_thought.draw(self.screen, head_x, head_y)

        # the journal in the corner
        if fly > -0.5:
            jx, jy = self.JOURNAL_POS
            book = self.journal_icon.get_rect(center=(jx, jy))
            self.screen.blit(self.journal_icon, book)
            if fly >= 1:
                saved = self.small_font.render("Saved to journal", True, (240, 210, 150))
                self.screen.blit(saved, saved.get_rect(midright=(book.left - 12, jy)))

    # ---------------------------
    # ANCIENT TEXT SCREEN
    # ---------------------------
    def update_ancient_text(self):
        keys = pygame.key.get_pressed()
        now = pygame.time.get_ticks()

        if self.frag_start is None:
            self.frag_start = now
            self.frag_thought = None
            self.ancient_text_ready_time = now + (self.FRAG_FADE + self.FRAG_WRITE
                                                  + self.FRAG_THINK + self.FRAG_SAVE + 300)

        self.draw_fragment_scene(now - self.frag_start)

        if now >= self.ancient_text_ready_time:
            hint = self.small_font.render("Press ENTER to continue", True, (200, 200, 200))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40)))
        
        # Don't accept input until delay is over
        if now < self.ancient_text_ready_time:
            return
        
        if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
            # Reset for next time
            self.frag_start = None
            
            all_cleared = all(door.is_cleared for door in self.doors)
            
            if all_cleared and self.stage == 1:
                # Move to stage 2
                self.stage = 2
                
                self.player.max_hp += 30
                self.player.hp = self.player.max_hp
                self.player.strength += 8
                
                # RESET for Stage 2
                self.doors = []
                self.doors_revealed = False
                self.keys_collected = 0
                
                self.setup_exploration_room()
                
                self.info_message = "STAGE 2! Find the new keys to reveal stronger enemies!"
                self.info_message_until = pygame.time.get_ticks() + 3000
                
                self.return_to_hall()
                
            elif all_cleared and self.stage == 2:
                # All four pieces: back to the castle to find a way to read them
                self.start_translation_trip()
                
            else:
                # More enemies to defeat in current stage
                # Restore player HP only in Stage 1
                if self.stage == 1:
                    self.player.hp = self.player.max_hp
                
                self.info_message = f"You defeated {self.current_enemy.name}!"
                self.info_message_until = pygame.time.get_ticks() + 2000

                self.return_to_hall()
                
            return

    def revive_player(self):
        p = self.player
        p.hp = p.max_hp
        p.energy = p.max_energy
        p.is_defeated = False
        p.is_attacking = False
        p.is_blocking = False
        p.is_jumping = False
        p.vertical_speed = 0
        p.stun_until = 0
        p.anim_state = "idle"
        p.animator.play("idle", restart=True)

    def try_again(self):
        """Start the part you lost again, with full HP."""
        self.revive_player()
        self.defeat_in_maze = False
        self.defeat_in_castle = False
        self.effects.clear()
        if self.retry_from == "castle":
            self.room_enemies = {}
            self.castle_popup = None
            self.path_walk = None
            self.thought = None
            self.state = "castle"
            self.start_escape()
        elif self.retry_from == "maze":
            self.enter_maze()
        else:
            self.start_battle(self.current_door)


    # ---------------------------
    # GAME OVER
    # ---------------------------
    def update_game_over(self):
        self.screen.fill((0, 0, 0))

        if self.game_over_text == "YOU LOSE":
            text = self.big_font.render(self.game_over_text, True, (200, 30, 30))
        else:
            text = self.font.render(self.game_over_text, True, (255, 255, 255))
        self.screen.blit(
            text,
            (SCREEN_WIDTH // 2 - text.get_width() // 2,
             SCREEN_HEIGHT // 2 - text.get_height() // 2))

        if self.game_over_text == "YOU LOSE":
            hint_text = "T  Try again   |   R  Menu   |   O  Load save"
        else:
            hint_text = "Press R to restart | Press O to load save"
        hint = self.small_font.render(hint_text, True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

        keys = pygame.key.get_pressed()
        if self.game_over_text == "YOU LOSE" and keys[pygame.K_t]:
            self.try_again()
            return
        if keys[KEY_LOAD]:
            self.load_game()
        if keys[pygame.K_r]:
            # Full reset
            self.player = Player(100, SCREEN_HEIGHT - GROUND_HEIGHT, self.player_image, self.player_frames)
            
            self.doors = []
            self.doors_revealed = False
            self.keys_collected = 0
            
            self.setup_exploration_room()
            
            self.current_enemy = None
            self.current_door = None
            self.info_message = ""
            self.stage = 1
            self.difficulty_level = 1
            self.enemies_defeated = 0
            self.ancient_texts = []
            self.fragments_found = 0
            self.state = "menu"

# Run Game
if __name__ == "__main__":
    game = Game()
    game.run()
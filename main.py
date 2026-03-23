import pygame
import sys
import math
import random

# ---------------------------
# Screen Settings
# ---------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
GROUND_HEIGHT = 60

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
        screen.blit(self.image, (self.rect.x, self.rect.y))

    def apply_knockback(self, direction, amount=20):
        """Push character left or right."""
        self.rect.x += direction * amount
        self.rect.x = max(0, min(self.rect.x, SCREEN_WIDTH - self.rect.width))


# ---------------------------
# Player Class
# ---------------------------
class Player(Character):
    def __init__(self, x, y, image):
        super().__init__(x, y, image.get_width(), image.get_height(), hp=180, speed=6, strength=20)
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
        self.energy_regen_rate = 0.3  # energy per frame
        
    def handle_input(self, keys, platforms=None):
        dx = 0
        if keys[pygame.K_LEFT]:
            dx = -self.speed
        if keys[pygame.K_RIGHT]:
            dx = self.speed

        if dx > 0:
            self.facing = 1
        elif dx < 0:
            self.facing = -1

        if keys[pygame.K_UP] and not self.is_jumping:
            self.is_jumping = True
            self.vertical_speed = -self.JUMP_STRENGTH

        # Move horizontally
        if platforms:
            self.move_with_platforms(dx, platforms)
        else:
            self.move(dx)
    
    def move_with_platforms(self, dx, platforms):
        """Move with platform collision detection"""
        if dx == 0:
            return
        
        # Try horizontal movement
        self.rect.x += dx
        
        # Check side collisions only
        for platform in platforms:
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
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH
    
    def apply_gravity_with_platforms(self, platforms):
        """Apply gravity with platform collision"""
        # Always apply gravity
        self.vertical_speed += self.GRAVITY

        # Move vertically
        old_y = self.rect.y
        self.rect.y += self.vertical_speed

        # Check platform collisions
        on_ground = False
        
        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.vertical_speed > 0:  # Falling down
                    # Landing on top of platform
                    # Only land if we were above the platform before
                    if old_y + self.rect.height <= platform.rect.top + 10:
                        self.rect.bottom = platform.rect.top
                        self.vertical_speed = 0
                        self.is_jumping = False
                        on_ground = True
                        break
                        
                elif self.vertical_speed < 0:  # Jumping up
                    # Hitting head on bottom of platform
                    if old_y >= platform.rect.bottom - 10:
                        self.rect.top = platform.rect.bottom
                        self.vertical_speed = 0

        # Check ground collision (y = 640 is ground level)
        if self.rect.bottom >= 640:
            self.rect.bottom = 640
            self.vertical_speed = 0
            self.is_jumping = False
            on_ground = True
        
        # If not on ground and moving down, we're falling/jumping
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
# Platform Class
# ---------------------------
class Platform:
    def __init__(self, x, y, w, h, image):
        self.rect = pygame.Rect(x, y, w, h)

        # Scale image ONLY by height
        img_ratio = image.get_width() / image.get_height()
        new_height = h
        new_width = int(img_ratio * new_height)

        self.tile_image = pygame.transform.scale(image, (new_width, new_height))

    def draw(self, screen):
        x = self.rect.x
        while x < self.rect.right:
            screen.blit(self.tile_image, (x, self.rect.y))
            x += self.tile_image.get_width()

# ---------------------------
# Portal Class
# ---------------------------
class Portal:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 60, 80)
        self.animation_offset = 0
    
    def draw(self, screen):
        self.animation_offset = (self.animation_offset + 0.1) % (2 * math.pi)
        
        # Swirling portal effect
        for i in range(3):
            radius = 30 - i * 8
            alpha = int(100 + 50 * math.sin(self.animation_offset + i))
            color = (150, 50, 255, min(255, alpha))
            
            portal_surface = pygame.Surface((80, 100), pygame.SRCALPHA)
            pygame.draw.circle(portal_surface, (*color[:3], alpha), (40, 50), radius)
            screen.blit(portal_surface, (self.rect.x - 10, self.rect.y - 10))
        
        # Portal outline
        pygame.draw.ellipse(screen, (200, 100, 255), self.rect, 3)
    
    def check_collision(self, player):
        return self.rect.colliderect(player.rect)


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

    def draw(self, screen):
        if not self.collected:
            # Floating animation
            self.float_offset = math.sin(pygame.time.get_ticks() / 200) * 5
            
            # Draw glow effect
            glow_rect = pygame.Rect(self.rect.x - 5, self.rect.y - 5 + self.float_offset, 60, 60)
            glow_surface = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (255, 215, 0, 60), (30, 30), 30)
            screen.blit(glow_surface, glow_rect)
            
            # Draw the key image if available
            if self.key_image:
                key_rect = pygame.Rect(self.rect.x, self.rect.y + self.float_offset, 50, 50)
                screen.blit(self.key_image, key_rect)
            else:
                # Fallback to the original rectangle drawing
                key_rect = pygame.Rect(self.rect.x, self.rect.y + self.float_offset, 40, 40)
                pygame.draw.rect(screen, (255, 215, 0), key_rect)
            
            # Draw sparkles
            sparkle_y_offset = self.float_offset
            pygame.draw.circle(screen, (255, 255, 200), 
                             (int(self.rect.centerx - 15), int(self.rect.centery - 15 + sparkle_y_offset)), 3)
            pygame.draw.circle(screen, (255, 255, 200), 
                             (int(self.rect.centerx + 15), int(self.rect.centery + 15 + sparkle_y_offset)), 3)

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
        "Luffy": "The Rubber Pirate sought the ultimate treasure, but was trapped in this dimension. His will remains unbroken...",
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

        # Player img
        self.player_image = pygame.image.load("img/player.png").convert_alpha()
        self.player_image = pygame.transform.scale(self.player_image, (120, 180))

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
        self.room_bg_locked = pygame.transform.scale(
            pygame.image.load("img/room_bg.jpg"),
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )

        self.room_bg_unlocked = pygame.transform.scale(
            pygame.image.load("img/room_bg_unlocked.jpg"),
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        self.explor_bg = pygame.transform.scale(
            pygame.image.load("img/explor_bg.jpg"),
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
                pygame.image.load("img/naruto_attack.png").convert_alpha(), (180, 120)),
        }

        self.slash_image = pygame.image.load("img/player_attack.png").convert_alpha()
        self.slash_image = pygame.transform.scale(self.slash_image, (80, 80))

        self.platform_images = [
            pygame.image.load("img/platform1.png").convert_alpha(),
            pygame.image.load("img/platform2.png").convert_alpha(),
            pygame.image.load("img/platform3.png").convert_alpha(),
        ]


        # Visual effect timers
        self.attack_effect_until = 0
        self.enemy_attack_effect_until = 0

        self.game_over_text = "Game Over - Press R to Restart"
        self.info_message = ""
        self.info_message_until = 0

        self.state = "menu"
        self.player = Player(100, SCREEN_HEIGHT - GROUND_HEIGHT, self.player_image)

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
        
        # Stat upgrade state
        self.waiting_for_stat_choice = False
        self.stat_choice_options = ["HP", "Strength", "Speed"]
        self.selected_stat = 0
        
        # Save cooldown to prevent multiple saves
        self.save_cooldown_until = 0
                
        # NOW setup exploration room after everything is initialized
        self.setup_exploration_room()
    
    def setup_exploration_room(self):
        """Create platforming level for key exploration"""
        self.exploration_platforms = [
            # Ground level - wider platforms with good spacing
           
            
            # Level 2 - Medium height (can jump from ground)
            Platform(170, 600, 180, 40, random.choice(self.platform_images)),
            Platform(940, 560, 100, 30, random.choice(self.platform_images)),
            Platform(1100, 500, 200, 50, random.choice(self.platform_images)),
            Platform(940, 260, 100, 30, random.choice(self.platform_images)),
            Platform(0, 370, 50, 30, random.choice(self.platform_images)),
            
            # Level 3 - Higher (need to jump from level 2)
            Platform(80, 260, 16, 30, random.choice(self.platform_images)),
            Platform(340, 280, 80, 30, random.choice(self.platform_images)),
            Platform(320, 500, 130, 30, random.choice(self.platform_images)),
            Platform(580, 400, 230, 30, random.choice(self.platform_images)),
            Platform(640, 300, 80, 30, random.choice(self.platform_images)),
            
            
            # Key platforms (tiny platforms just for keys)
            Platform(30, 210, 50, 30, random.choice(self.platform_images)),
            Platform(1130, 150, 120, 25, random.choice(self.platform_images)),
        ]
        
        # Place keys on highest platforms - NOW WITH IMAGE
        self.keys = [
            Key(30, 80, key_image=self.key_image),      # Top left
            Key(1160, 100, key_image=self.key_image),    # Top right
        ] 
        
        # Exit portal at ground level
        self.exploration_portal = Portal(SCREEN_WIDTH // 2 - 30, 520)

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
            "player_max_hp": self.player.max_hp,
            "player_hp": self.player.hp,
            "player_strength": self.player.strength,
            "player_speed": self.player.speed,
            "difficulty_level": self.difficulty_level,
            "enemies_defeated": self.enemies_defeated,
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
            self.player.max_hp = save_data.get("player_max_hp", 180)
            self.player.hp = save_data.get("player_hp", self.player.max_hp)
            self.player.strength = save_data.get("player_strength", 20)
            self.player.speed = save_data.get("player_speed", 6)
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
            
            self.info_message = f"Game Loaded! Stage {self.stage}"
            self.info_message_until = pygame.time.get_ticks() + 2000
            
            self.state = "room"
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

            if self.state == "menu":
                self.update_menu()
            elif self.state == "room":
                self.update_room()
            elif self.state == "exploration":
                self.update_exploration()
            elif self.state == "battle":
                self.update_battle()
            elif self.state == "stat_choice":
                self.update_stat_choice()
            elif self.state == "ancient_text":
                self.update_ancient_text()
            elif self.state == "game_over":
                self.update_game_over()

            pygame.display.flip()

    # ---------------------------
    # Event Handling
    # ---------------------------
    def handle_events(self):
        for event in pygame.event.get():
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
            self.state = "room"
        
        # Load game when L is pressed
        if keys[pygame.K_l] and now >= self.save_cooldown_until:
            if self.load_game():
                self.save_cooldown_until = now + 500
            else:
                self.save_cooldown_until = now + 500

        self.screen.fill((0, 0, 0))
        
        title = self.big_font.render("ANIME BATTLE", True, (255, 215, 0))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
        
        start_text = self.font.render("Press ENTER to Start New Game", True, (255, 255, 255))
        self.screen.blit(start_text, (SCREEN_WIDTH//2 - start_text.get_width()//2, 350))
        
        load_text = self.font.render("Press L to Load Game", True, (200, 200, 200))
        self.screen.blit(load_text, (SCREEN_WIDTH//2 - load_text.get_width()//2, 420))
        
        if self.info_message and now < self.info_message_until:
            msg = self.small_font.render(self.info_message, True, (255, 255, 0))
            self.screen.blit(msg, (SCREEN_WIDTH//2 - msg.get_width()//2, 500))

    # ---------------------------
    # ROOM (HUB)
    # ---------------------------
    def update_room(self):
        keys = pygame.key.get_pressed()
        self.play_music(self.room_bgm)
        
        self.player.handle_input(keys)
        self.player.update()

        # Draw background (fills entire screen)
        # Change background based on key progress
        if self.doors_revealed:
            self.screen.blit(self.room_bg_unlocked, (0, 0))
        else:
            self.screen.blit(self.room_bg_locked, (0, 0))


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
        save_hint = self.tiny_font.render("Press S to Save", True, (255, 255, 255))
        self.screen.blit(save_hint, (10, 10))

        now = pygame.time.get_ticks()
        
        # Save game when S is pressed (with cooldown)
        if keys[pygame.K_s] and now >= self.save_cooldown_until:
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

        # Draw portal to exploration room (if doors not revealed)
        if not self.doors_revealed:
            
            if self.hub_portal.check_collision(self.player):
                hint = self.small_font.render("Press SPACE to enter exploration", True, (255, 255, 255))
                self.screen.blit(hint, (505, 100))
                
                if keys[pygame.K_SPACE]:
                    self.state = "exploration"
                    # Start on first platform
                    self.player.rect.x = 50
                    self.player.rect.y = 560  # Just above first platform
                    self.player.is_jumping = False
                    self.player.vertical_speed = 0
                    return

        # Draw doors ONLY if revealed
        # Draw doors ONLY if revealed
        if self.doors_revealed:
            for door in self.doors:
                door.draw(self.screen)


        self.player.draw(self.screen)

        # Door interaction
        if self.doors_revealed:
            for door in self.doors:
                if (not door.is_locked) and (not door.is_cleared) and door.is_player_in_front(self.player):
                    msg = self.font.render("Press SPACE to enter battle", True, (255, 255, 255))
                    self.screen.blit(msg, (485, 100))

                    if now >= self.door_enter_cooldown_until and keys[pygame.K_SPACE]:
                        self.start_battle(door)
                        return
    
    # ---------------------------
    # EXPLORATION ROOM
    # ---------------------------
    def update_exploration(self):
        keys = pygame.key.get_pressed()
        
        # Handle player input and movement with platforms
        self.player.handle_input(keys, self.exploration_platforms)
        self.player.apply_gravity_with_platforms(self.exploration_platforms)
        
        # Draw background
        self.screen.blit(self.explor_bg, (0, 0))
        
        # Draw title
        title = self.font.render(f"Find the Keys: {self.keys_collected}/{self.total_keys}", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 20))
        
        # Draw platforms
        for platform in self.exploration_platforms:
            platform.draw(self.screen)
        
        # Draw ground
        pygame.draw.rect(self.screen, (60, 40, 20), (0, 640, SCREEN_WIDTH, 80))
        
        # Draw keys
        for key in self.keys:
            key.draw(self.screen)
        
        # Check key collection
        for key in self.keys:
            if key.check_pickup(self.player):
                self.keys_collected += 1
                
                if self.keys_collected >= self.total_keys:
                    self.info_message = " All keys found! Return through the portal!"
                    self.info_message_until = pygame.time.get_ticks() + 3000
        
        
        # Draw player
        self.player.draw(self.screen)
        
        # Check portal collision
        if self.exploration_portal.check_collision(self.player):
            hint = self.small_font.render("Press SPACE to return to hub", True, (255, 255, 255))
            self.screen.blit(hint, (530, 100))
            
            if keys[pygame.K_SPACE]:
                if self.keys_collected >= self.total_keys:
                    # Reveal doors in hub
                    self.doors_revealed = True
                    
                    if self.stage == 1:
                        self.doors = [
                            Door(120, 300, 110, 340, "Naruto"),
                            Door(1050, 300, 110, 340, "Luffy"),
                        ]
                    else:
                        self.doors = [
                            Door(120, 300, 110, 340, "Ichigo"),
                            Door(1050, 300, 110, 340, "Goku"),
                        ]
                    
                    for door in self.doors:
                        door.is_locked = False
                    
                    self.info_message = " All keys found! The doors have appeared!"
                    self.info_message_until = pygame.time.get_ticks() + 3000
                
                # Return to hub
                self.state = "room"
                self.player.rect.x = 100
                self.player.rect.y = self.player.ground_y
                self.door_enter_cooldown_until = pygame.time.get_ticks() + 500
                return
        
        # Show message
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

        pygame.mixer.Sound.play(self.snd_fight)

        self.player_attack_cooldown = 0
        self.enemy_attack_cooldown = 0
        
        # Reset enemy melee charging
        self.enemy_melee_charge = 0
        self.enemy_is_charging_melee = False

        self.player.rect.x = 100
        self.player.rect.y = self.player.ground_y
        self.player.energy = self.player.max_energy

        self.battle_start_time = pygame.time.get_ticks()
        self.enemy_move_delay = 1000

        self.show_fight_text = True
        self.fight_text_until = pygame.time.get_ticks() + 1000

        self.state = "battle"

        self.enemy_attack_effect_until = 0

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
                self.player.take_damage(self.current_enemy.strength + bonus_damage[self.current_enemy.name])

                if self.current_enemy.rect.centerx < self.player.rect.centerx:
                    self.player.apply_knockback(1)
                else:
                    self.player.apply_knockback(-1)

                self.current_enemy.ability_cooldown = cooldowns[self.current_enemy.name]
                self.enemy_attack_effect_until = now + 350

        if can_act:
            self.player.handle_input(keys)
        self.player.update()

        if can_act and self.current_enemy.is_alive():
            if not self.player.is_attacking and not self.enemy_is_charging_melee:
                self.current_enemy.update_ai(self.player)
            self.current_enemy.update()


        # Reset player attacking state when cooldown expires
        if self.player_attack_cooldown == 0:
            self.player.is_attacking = False

        # Player attack with energy cost
        attack_cost = 20
        if (can_act and keys[pygame.K_SPACE] and self.player_attack_cooldown == 0 and self.player.can_attack(attack_cost)):
            self.player.is_attacking = True
            pygame.mixer.Sound.play(self.snd_punch)
            self.player.use_energy(attack_cost)
            self.attack_effect_until = now + 120
            
            # Create attack hitbox (slightly larger than player, extends in facing direction)
            if self.player.facing == 1:
                attack_rect = pygame.Rect(
                    self.player.rect.right - 20,
                    self.player.rect.top,
                    80,
                    self.player.rect.height
                )
            else:
                attack_rect = pygame.Rect(
                    self.player.rect.left - 60,
                    self.player.rect.top,
                    80,
                    self.player.rect.height
                )
            
            # Check if attack hitbox hits enemy
            if attack_rect.colliderect(self.current_enemy.rect):
                self.current_enemy.take_damage(self.player.strength)
                print(f"Hit! Enemy HP: {self.current_enemy.hp}/{self.current_enemy.max_hp}")  # Debug

                # Knockback enemy
                if self.player.rect.centerx < self.current_enemy.rect.centerx:
                    self.current_enemy.apply_knockback(1, 30)
                else:
                    self.current_enemy.apply_knockback(-1, 30)
                
                # Interrupt enemy charging if hit
                if self.enemy_is_charging_melee:
                    self.enemy_is_charging_melee = False
                    self.enemy_melee_charge = 0

            self.player_attack_cooldown = 20


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
                        self.player.take_damage(self.current_enemy.strength)
                        print(f"Enemy hit player! Player HP: {self.player.hp}/{self.player.max_hp}")  # Debug

                        if self.current_enemy.rect.centerx < self.player.rect.centerx:
                            self.player.apply_knockback(1)
                        else:
                            self.player.apply_knockback(-1)

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
            self.game_over_text = "Game Over - Press R to Restart"
            self.state = "game_over"
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

        info = self.small_font.render("SPACE to attack | ESC to escape", True, (255, 255, 255))
        self.screen.blit(info, (480, 18))

        if can_act and keys[pygame.K_ESCAPE]:
            self.state = "room"
            self.player.rect.x = 100
            self.player.rect.y = self.player.ground_y
            self.door_enter_cooldown_until = pygame.time.get_ticks() + 400
            return

        pygame.draw.rect(
            self.screen,
            (20, 100, 20),
            (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))
        
        # Player slash effect
        if now < self.attack_effect_until:
            if self.player.facing == 1:
                slash_img = self.slash_image
                x = self.player.rect.right - 10
            else:
                slash_img = pygame.transform.flip(self.slash_image, True, False)
                x = self.player.rect.left - 60

            y = self.player.rect.centery - slash_img.get_height() // 2
            self.screen.blit(slash_img, (x, y))
            
        if self.show_fight_text and now < self.fight_text_until:
            fight_txt = self.big_font.render("FIGHT!", True, (255, 255, 255))
            fight_x = SCREEN_WIDTH // 2 - fight_txt.get_width() // 2
            fight_y = SCREEN_HEIGHT // 2 - fight_txt.get_height() // 2
            self.screen.blit(fight_txt, (fight_x, fight_y))
        else:
            self.show_fight_text = False

        # HP bars
        player_ratio = self.player.hp / self.player.max_hp
        player_bar_width = 400
        player_bar_height = 20
        player_bar_x = 40
        player_bar_y = 40

        pygame.draw.rect(self.screen, (255, 255, 255),
            (player_bar_x, player_bar_y, player_bar_width, player_bar_height), 2)
        pygame.draw.rect(self.screen, (0, 200, 255),
            (player_bar_x, player_bar_y, player_bar_width * player_ratio, player_bar_height))
        
        p_name = self.small_font.render("PLAYER", True, (255, 255, 255))
        self.screen.blit(p_name, (player_bar_x, player_bar_y - 25))

        enemy_ratio = self.current_enemy.hp / self.current_enemy.max_hp
        enemy_bar_width = 400
        enemy_bar_height = 20
        enemy_bar_x = SCREEN_WIDTH - 40 - enemy_bar_width
        enemy_bar_y = 40

        pygame.draw.rect(self.screen, (255, 255, 255),
            (enemy_bar_x, enemy_bar_y, enemy_bar_width, enemy_bar_height), 2)
        pygame.draw.rect(self.screen, (255, 150, 150),
            (enemy_bar_x, enemy_bar_y, enemy_bar_width * enemy_ratio, enemy_bar_height))
        
        e_name = self.small_font.render(self.current_enemy.name.upper(), True, (255, 255, 255))
        self.screen.blit(e_name, (enemy_bar_x, enemy_bar_y - 25))

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
        
        if keys[pygame.K_LEFT] or keys[pygame.K_UP]:
            self.selected_stat = (self.selected_stat - 1) % 3
            pygame.time.wait(150)
        if keys[pygame.K_RIGHT] or keys[pygame.K_DOWN]:
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

    # ---------------------------
    # ANCIENT TEXT SCREEN
    # ---------------------------
    def update_ancient_text(self):
        keys = pygame.key.get_pressed()
        now = pygame.time.get_ticks()
        
        # Initialize delay timer if not set
        if not hasattr(self, 'ancient_text_ready_time'):
            self.ancient_text_ready_time = now + 500
        
        # Draw the screen first
        self.screen.fill((10, 10, 20))
        
        title = self.big_font.render("ANCIENT TEXT", True, (255, 215, 0))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 80))
        
        box_rect = pygame.Rect(100, 200, SCREEN_WIDTH - 200, 300)
        pygame.draw.rect(self.screen, (40, 40, 60), box_rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 215, 0), box_rect, 3, border_radius=10)
        
        text_content = self.current_ancient_text.text
        words = text_content.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + word + " "
            if self.small_font.size(test_line)[0] < box_rect.width - 40:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)
        
        y_offset = box_rect.y + 30
        for line in lines:
            line_surf = self.small_font.render(line, True, (255, 255, 255))
            self.screen.blit(line_surf, (box_rect.x + 20, y_offset))
            y_offset += 35
        
        # Show wait or continue hint
        if now < self.ancient_text_ready_time:
            hint = self.font.render("Please wait...", True, (150, 150, 150))
        else:
            hint = self.font.render("Press ENTER to continue", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, 580))
        
        # Don't accept input until delay is over
        if now < self.ancient_text_ready_time:
            return
        
        if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
            # Reset for next time
            del self.ancient_text_ready_time
            
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
                
                self.state = "room"
                self.player.rect.x = 100
                self.player.rect.y = self.player.ground_y
                self.door_enter_cooldown_until = pygame.time.get_ticks() + 400
                
            elif all_cleared and self.stage == 2:
                # Game victory!
                self.game_over_text = "You defeated all enemies! Press R to Restart"
                self.state = "game_over"
                
            else:
                # More enemies to defeat in current stage
                # Restore player HP only in Stage 1
                if self.stage == 1:
                    self.player.hp = self.player.max_hp
                
                self.info_message = f"You defeated {self.current_enemy.name}!"
                self.info_message_until = pygame.time.get_ticks() + 2000
                
                self.state = "room"
                self.player.rect.x = 100
                self.player.rect.y = self.player.ground_y
                self.door_enter_cooldown_until = pygame.time.get_ticks() + 400
            return

    # ---------------------------
    # GAME OVER
    # ---------------------------
    def update_game_over(self):
        self.screen.fill((0, 0, 0))

        text = self.font.render(self.game_over_text, True, (255, 255, 255))
        self.screen.blit(
            text,
            (SCREEN_WIDTH // 2 - text.get_width() // 2,
             SCREEN_HEIGHT // 2 - text.get_height() // 2))

        hint = self.small_font.render("Press R to restart | Press L to load save", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

        keys = pygame.key.get_pressed()
        if keys[pygame.K_l]:
            self.load_game()
        if keys[pygame.K_r]:
            # Full reset
            self.player = Player(100, SCREEN_HEIGHT - GROUND_HEIGHT, self.player_image)
            
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
            self.state = "menu"

# Run Game
if __name__ == "__main__":
    game = Game()
    game.run()
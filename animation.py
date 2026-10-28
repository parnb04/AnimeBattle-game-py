import pygame 


class Animation:
    """A list of frames + playback speed."""
    def __init__(self, frames, fps=10, loop=True):
        self.frames = frames
        self.frame_duration = 1000 / fps
        self.loop = loop


class Animator:
    """Holds all animations of a character and plays the active one."""
    def __init__(self, animations, start="idle"):
        self.animations = animations
        self.current = start
        self.frame_index = 0
        self.last_tick = pygame.time.get_ticks()
        self.finished = False

    def play(self, name, restart=False):
        if (name == self.current and not restart) or name not in self.animations:
            return
        self.current = name
        self.frame_index = 0
        self.finished = False
        self.last_tick = pygame.time.get_ticks()

    def update(self):
        anim = self.animations[self.current]
        now = pygame.time.get_ticks()
        if now - self.last_tick >= anim.frame_duration:
            self.last_tick = now
            self.frame_index += 1
            if self.frame_index >= len(anim.frames):
                if anim.loop:
                    self.frame_index = 0
                else:
                    self.frame_index = len(anim.frames) - 1
                    self.finished = True

    def get_frame(self):
        return self.animations[self.current].frames[self.frame_index]

    def set_frame(self, index):
        frames = self.animations[self.current].frames
        self.frame_index = max(0, min(index, len(frames) - 1))


def load_frames(pattern, count, size=None):
    """Load numbered images: pattern like 'img/player/walk_{:02d}.png'."""
    frames = []
    for i in range(1, count + 1):
        img = pygame.image.load(pattern.format(i)).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        frames.append(img)
    return frames

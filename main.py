import pygame
import sounddevice as sd
import numpy as np
import random
import sys
import math
import json
import os
from typing import List, Tuple, Dict
from enum import Enum

# ================= INIT =================
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 900, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(".EXE – Haunted")
clock = pygame.time.Clock()

# ================= COLORS - HORROR THEME =================
BLACK = (0, 0, 0)
BLOOD_RED = (103, 7, 21)
DARK_RED = (100, 0, 0)
DARK_GRAY = (40, 40, 45)
FOG_GRAY = (60, 60, 70)
GHOST_WHITE = (200, 200, 220)
MOON_YELLOW = (255, 250, 205)
GRAVE_STONE = (80, 80, 90)
DEAD_TREE = (50, 40, 30)
TOXIC_GREEN = (0, 255, 100)
PURPLE_MIST = (75, 0, 130)
WHITE = (255, 255, 255)
GRAY = (180, 180, 180)
PURPLE = (138, 43, 226)
LIGHT_PURPLE = (186, 85, 211)
CYAN = (0, 255, 255)
PINK = (255, 105, 180)
GREEN = (0, 255, 0)
RED = (255, 50, 50)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
BONE_WHITE = (245, 245, 220)
SHADOW_BLACK = (20, 20, 25)

# ================= DIFFICULTY SCALING CONSTANTS =================
# Easy mode lasts until this score
DIFFICULTY_START_SCORE = 5

# Gap between obstacles (vertical opening)
BASE_GAP = 250           # Large gap for score < 5
MIN_GAP = 140            # Minimum gap at high scores
GAP_DECREASE_RATE = 5    # Gap decreases by 5px per score point after 5

# Obstacle movement speed
BASE_OBSTACLE_SPEED = 3.0      # Slow speed for score < 5
MAX_OBSTACLE_SPEED = 7.5       # Maximum speed cap
SPEED_INCREASE_RATE = 0.15     # Speed increases by 0.15 per score point

# Horizontal spacing between obstacles
BASE_HORIZONTAL_DISTANCE = 450  # Large spacing for score < 5
MIN_HORIZONTAL_DISTANCE = 280   # Minimum spacing at high scores
DISTANCE_DECREASE_RATE = 7      # Distance decreases by 7px per score point

# ================= GAME STATE ENUM =================
class GameState(Enum):
    SPLASH_SCREEN = 0
    SETUP_ATTEMPTS = 1
    USERNAME_INPUT = 2
    DIFFICULTY_SELECT = 3
    WAITING = 4
    PLAYING = 5
    GAME_OVER = 6
    ATTEMPT_SUMMARY = 7
    SESSION_LEADERBOARD = 8

# ================= DIFFICULTY CONFIG =================
class DifficultyConfig:
    """Complete difficulty configuration"""
    def __init__(self, name: str, bird_scale: float, obstacle_speed: float, 
                 noise_threshold: float, gravity: float, easy_mode: bool = True):
        self.name = name
        self.bird_scale = bird_scale
        self.obstacle_speed = obstacle_speed
        self.noise_threshold = noise_threshold
        self.gravity = gravity
        self.easy_mode = easy_mode  # NEW: Whether to apply easy mode at start
        self.bird_width = int(40 * bird_scale)
        self.bird_height = int(30 * bird_scale)
    
    def get_bird_dimensions(self) -> Tuple[int, int]:
        return (self.bird_width, self.bird_height)

class DifficultyManager:
    """Manages all difficulty presets"""
    DIFFICULTIES = {
        "SLOW": DifficultyConfig(
            name="SLOW",
            bird_scale=0.8,
            obstacle_speed=3.0,
            noise_threshold=0.015,
            gravity=0.35,
            easy_mode=True  # Easy mode enabled
        ),
        "MEDIUM": DifficultyConfig(
            name="MEDIUM",
            bird_scale=1.0,
            obstacle_speed=5.0,
            noise_threshold=0.012,
            gravity=0.4,
            easy_mode=True  # Easy mode enabled
        ),
        "FAST": DifficultyConfig(
            name="FAST",
            bird_scale=1.2,
            obstacle_speed=6.0,
            noise_threshold=0.010,
            gravity=0.45,
            easy_mode=False  # NO easy mode - hard from start
        ),
        "GODLIKE": DifficultyConfig(
            name="GODLIKE",
            bird_scale=1.2,
            obstacle_speed=9.0,
            noise_threshold=0.008,
            gravity=0.5,
            easy_mode=False  # NO easy mode - hard from start
        )
    }
    
    @classmethod
    def get_config(cls, difficulty_name: str):
        return cls.DIFFICULTIES.get(difficulty_name, cls.DIFFICULTIES["MEDIUM"])
    
    @classmethod
    def get_all_names(cls) -> List[str]:
        return list(cls.DIFFICULTIES.keys())

# ================= DYNAMIC DIFFICULTY CALCULATOR =================
def calculate_difficulty_params(score: int, difficulty_config: DifficultyConfig) -> dict:
    """
    Calculate difficulty parameters based on current score and difficulty mode.
    
    NEW BEHAVIOR:
    - SLOW/MEDIUM: Easy mode until score 5, then scales up
    - FAST/GODLIKE: Hard from the start (no easy mode)
    
    Returns:
        dict with keys: gap, speed, horizontal_distance
    """
    # For FAST and GODLIKE modes - use their preset speed immediately
    if not difficulty_config.easy_mode:
        # Hard modes: start at full difficulty
        gap = MIN_GAP + 50  # Slightly more forgiving gap
        speed = difficulty_config.obstacle_speed
        h_distance = MIN_HORIZONTAL_DISTANCE + 100
        
        # Still scale with score, but from already-hard baseline
        if score >= DIFFICULTY_START_SCORE:
            score_above = score - DIFFICULTY_START_SCORE
            gap = max(MIN_GAP, gap - (score_above * 3))
            speed = min(MAX_OBSTACLE_SPEED, speed + (score_above * 0.1))
            h_distance = max(MIN_HORIZONTAL_DISTANCE, h_distance - (score_above * 5))
        
        return {
            'gap': gap,
            'speed': speed,
            'horizontal_distance': h_distance
        }
    
    # For SLOW and MEDIUM modes - use easy mode scaling
    if score < DIFFICULTY_START_SCORE:
        # Easy mode - return base values
        return {
            'gap': BASE_GAP,
            'speed': BASE_OBSTACLE_SPEED,
            'horizontal_distance': BASE_HORIZONTAL_DISTANCE
        }
    
    # Calculate score-based difficulty increase
    score_above_threshold = score - DIFFICULTY_START_SCORE
    
    # Gap: decreases linearly, clamped to minimum
    gap = BASE_GAP - (score_above_threshold * GAP_DECREASE_RATE)
    gap = max(MIN_GAP, gap)
    
    # Speed: increases linearly, clamped to maximum
    speed = BASE_OBSTACLE_SPEED + (score_above_threshold * SPEED_INCREASE_RATE)
    speed = min(MAX_OBSTACLE_SPEED, speed)
    
    # Horizontal distance: decreases linearly, clamped to minimum
    h_distance = BASE_HORIZONTAL_DISTANCE - (score_above_threshold * DISTANCE_DECREASE_RATE)
    h_distance = max(MIN_HORIZONTAL_DISTANCE, h_distance)
    
    return {
        'gap': gap,
        'speed': speed,
        'horizontal_distance': h_distance
    }

# ================= PLAYER SESSION =================
class PlayerSession:
    """Manages individual player data and turn tracking"""
    def __init__(self, username: str, max_attempts: int):
        self.username = username
        self.max_attempts = max_attempts
        self.current_attempt = 0
        self.scores = []
        self.best_score = 0
        self.difficulty = "MEDIUM"
        self.is_complete = False
    
    def record_score(self, score: int):
        self.scores.append(score)
        self.current_attempt += 1
        self.best_score = max(self.best_score, score)
        if self.current_attempt >= self.max_attempts:
            self.is_complete = True
    
    def get_remaining_attempts(self) -> int:
        return self.max_attempts - self.current_attempt

# ================= SESSION MANAGER =================
class GameSessionManager:
    """Orchestrates multiple players taking turns"""
    def __init__(self):
        self.players: List[PlayerSession] = []
        self.current_player_index = 0
        self.max_attempts_per_player = 3
        self.session_active = False
    
    def start_new_session(self, max_attempts: int):
        self.players = []
        self.current_player_index = 0
        self.max_attempts_per_player = max_attempts
        self.session_active = True
    
    def add_player(self, username: str) -> PlayerSession:
        player = PlayerSession(username, self.max_attempts_per_player)
        self.players.append(player)
        return player
    
    def get_current_player(self):
        if self.players:
            return self.players[self.current_player_index]
        return None
    
    def move_to_next_player(self) -> bool:
        """Move to next player with attempts left"""
        if not self.players:
            return False
        
        # Check if current player has attempts left
        current = self.get_current_player()
        if current and not current.is_complete:
            return True
        
        # Find next player with attempts
        start_idx = self.current_player_index
        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            if self.current_player_index == start_idx:
                # Looped back - check if anyone has attempts
                if all(p.is_complete for p in self.players):
                    self.session_active = False
                    return False
            
            if not self.players[self.current_player_index].is_complete:
                return True
        
        return False
    
    def all_players_finished(self) -> bool:
        return all(p.is_complete for p in self.players) if self.players else False
    
    def get_session_leaderboard(self) -> List[Dict]:
        leaderboard = []
        for player in self.players:
            leaderboard.append({
                'username': player.username,
                'best_score': player.best_score,
                'attempts_used': player.current_attempt,
                'all_scores': player.scores,
                'difficulty': player.difficulty
            })
        return sorted(leaderboard, key=lambda x: x['best_score'], reverse=True)

# ================= LEADERBOARD MANAGER =================
class LeaderboardManager:
    def __init__(self):
        self.filename = "leaderboard.json"
        self.scores = self.load_scores()
    
    def load_scores(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_scores(self):
        with open(self.filename, 'w') as f:
            json.dump(self.scores, f)
    
    def add_score(self, username, score, difficulty):
        self.scores.append({
            'username': username,
            'score': score,
            'difficulty': difficulty
        })
        self.scores = sorted(self.scores, key=lambda x: x['score'], reverse=True)[:10]
        self.save_scores()
    
    def get_top_10(self):
        return self.scores

# ================= HORROR FONT RENDERER =================
class HorrorFontRenderer:
    """Creates horror-style text effects without external fonts"""
    
    @staticmethod
    def create_horror_text(text: str, size: int, color, style='dripping'):
        """
        Create horror-styled text with effects
        Styles: 'dripping', 'jagged', 'shaky', 'cracked'
        """
        base_font = pygame.font.Font(None, size)
        base_surf = base_font.render(text, True, color)
        w, h = base_surf.get_size()
        
        # Create larger surface for effects
        effect_surf = pygame.Surface((w + 20, h + 40), pygame.SRCALPHA)
        
        if style == 'dripping':
            # Main text
            effect_surf.blit(base_surf, (10, 10))
            
            # Add blood drips
            for i in range(0, w, max(1, w // len(text))):
                if random.random() > 0.3:
                    drip_length = random.randint(5, 20)
                    drip_x = i + 10
                    drip_y = h + 10
                    
                    # Draw dripping effect
                    for dy in range(drip_length):
                        alpha = int(255 * (1 - dy / drip_length))
                        drip_color = (*color[:3], alpha)
                        width = max(1, 3 - dy // 7)
                        pygame.draw.circle(effect_surf, drip_color, 
                                         (drip_x, drip_y + dy), width)
        
        elif style == 'jagged':
            # Draw multiple offset copies for jagged effect
            offsets = [(0, 0), (-2, -2), (2, 2), (-1, 1), (1, -1)]
            for ox, oy in offsets:
                effect_surf.blit(base_surf, (10 + ox, 10 + oy))
        
        elif style == 'shaky':
            # Multiple slightly offset copies
            for _ in range(5):
                ox = random.randint(-2, 2)
                oy = random.randint(-2, 2)
                effect_surf.blit(base_surf, (10 + ox, 10 + oy))
        
        elif style == 'cracked':
            # Main text
            effect_surf.blit(base_surf, (10, 10))
            
            # Add crack lines
            for _ in range(random.randint(3, 7)):
                x1 = random.randint(0, w)
                y1 = random.randint(0, h)
                x2 = x1 + random.randint(-15, 15)
                y2 = y1 + random.randint(-15, 15)
                pygame.draw.line(effect_surf, SHADOW_BLACK, 
                               (x1 + 10, y1 + 10), (x2 + 10, y2 + 10), 2)
        
        return effect_surf

# ================= UI THEME =================
class UITheme:
    """Centralized UI styling with horror fonts"""
    BG_COLOR = (0, 0, 0)
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (180, 180, 180)
    TEXT_DISABLED = (100, 100, 100)
    ACCENT_PRIMARY = (138, 43, 226)
    ACCENT_SECONDARY = (0, 255, 255)
    
    _fonts = {}
    _horror_renderer = HorrorFontRenderer()
    
    @classmethod
    def get_font(cls, size: int, bold: bool = False):
        key = (size, bold)
        if key not in cls._fonts:
            cls._fonts[key] = pygame.font.Font(None, size)
        return cls._fonts[key]
    
    @classmethod
    def draw_text(cls, screen, text: str, x: int, y: int, 
                  size: int = 32, color=None, center: bool = True, 
                  horror_style: str = None):
        """
        Draw text with optional horror styling
        horror_style: None, 'dripping', 'jagged', 'shaky', 'cracked'
        """
        if color is None:
            color = cls.TEXT_PRIMARY
        
        if horror_style:
            surf = cls._horror_renderer.create_horror_text(text, size, color, horror_style)
            if center:
                rect = surf.get_rect(center=(x, y))
            else:
                rect = surf.get_rect(topleft=(x, y))
        else:
            font = cls.get_font(size)
            surf = font.render(text, True, color)
            if center:
                rect = surf.get_rect(center=(x, y))
            else:
                rect = surf.get_rect(topleft=(x, y))
        
        screen.blit(surf, rect)

# ================= PIXELATED RENDERER =================
class PixelatedRenderer:
    """Handles pixelated/Minecraft-style rendering"""
    
    @staticmethod
    def draw_pixelated_mountain(screen, x: int, height: int, width: int, 
                                color, outline_color, is_top=True):
        """Draw Minecraft-style blocky mountain"""
        block_size = 10
        peak_heights = [10, 8, 9, 7, 5, 6, 4, 10]
        
        for px in range(0, width, block_size):
            pattern_idx = (px // block_size) % len(peak_heights)
            
            if is_top:
                local_height = height - (peak_heights[pattern_idx] * block_size)
                for py in range(0, int(height), block_size):
                    if py >= local_height:
                        rect = pygame.Rect(x + px, py, block_size, block_size)
                        pygame.draw.rect(screen, color, rect)
                        pygame.draw.rect(screen, outline_color, rect, 1)
            else:
                local_height = height + (peak_heights[pattern_idx] * block_size)
                for py in range(int(height), HEIGHT, block_size):
                    if py <= local_height:
                        rect = pygame.Rect(x + px, py, block_size, block_size)
                        pygame.draw.rect(screen, color, rect)
                        pygame.draw.rect(screen, outline_color, rect, 1)

# ================= HORROR ATMOSPHERE =================
class FogParticle:
    """Slow-moving fog particles for atmospheric horror"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = random.randint(-50, WIDTH + 50)
        self.y = random.randint(0, HEIGHT)
        self.size = random.randint(60, 150)
        self.speed = random.uniform(0.1, 0.3)
        self.opacity = random.randint(10, 30)
    
    def update(self):
        self.x -= self.speed
        if self.x < -self.size:
            self.x = WIDTH + 50
            self.y = random.randint(0, HEIGHT)
    
    def draw(self):
        fog_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(fog_surface, (*FOG_GRAY, self.opacity), 
                          (self.size // 2, self.size // 2), self.size // 2)
        screen.blit(fog_surface, (int(self.x - self.size // 2), int(self.y - self.size // 2)))


class Bat:
    """Flying bats in background"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = WIDTH + random.randint(0, 200)
        self.y = random.randint(50, HEIGHT - 50)
        self.speed = random.uniform(2, 4)
        self.wing_flap = 0
        self.size = random.randint(8, 14)
    
    def update(self):
        self.x -= self.speed
        self.wing_flap += 0.3
        if self.x < -50:
            self.reset()
    
    def draw(self):
        wing_offset = int(math.sin(self.wing_flap) * 4)
        
        # Draw outline first
        pygame.draw.circle(screen, BLACK, (int(self.x), int(self.y)), self.size // 2 + 2)
        
        left_wing = [(int(self.x - self.size), int(self.y - wing_offset)),
                     (int(self.x - self.size // 2), int(self.y)),
                     (int(self.x), int(self.y + wing_offset))]
        right_wing = [(int(self.x + self.size), int(self.y - wing_offset)),
                      (int(self.x + self.size // 2), int(self.y)),
                      (int(self.x), int(self.y + wing_offset))]
        
        # Draw wing outlines
        pygame.draw.polygon(screen, BLACK, left_wing, 3)
        pygame.draw.polygon(screen, BLACK, right_wing, 3)
        
        # Draw filled wings
        pygame.draw.circle(screen, (50, 50, 60), (int(self.x), int(self.y)), self.size // 2)
        pygame.draw.polygon(screen, (50, 50, 60), left_wing)
        pygame.draw.polygon(screen, (50, 50, 60), right_wing)


class Ghost:
    """Floating transparent ghosts"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = WIDTH + random.randint(0, 300)
        self.y = random.randint(100, HEIGHT - 100)
        self.speed = random.uniform(0.5, 1.5)
        self.float_offset = random.uniform(0, math.pi * 2)
        self.opacity = random.randint(30, 70)
    
    def update(self):
        self.x -= self.speed
        self.float_offset += 0.05
        if self.x < -80:
            self.reset()
    
    def draw(self):
        float_y = self.y + math.sin(self.float_offset) * 10
        ghost_surface = pygame.Surface((60, 80), pygame.SRCALPHA)
        
        # Draw outline
        pygame.draw.circle(ghost_surface, (*BLACK, self.opacity + 80), (30, 30), 27)
        
        points_outline = []
        for i in range(0, 61, 10):
            wave = math.sin((i + self.float_offset * 10) * 0.3) * 3
            points_outline.append((i, 50 + wave))
        points_outline.append((60, 80))
        points_outline.append((0, 80))
        pygame.draw.polygon(ghost_surface, (*BLACK, self.opacity + 80), points_outline, 3)
        
        # Draw main ghost
        pygame.draw.circle(ghost_surface, (*GHOST_WHITE, self.opacity), (30, 30), 25)
        
        points = []
        for i in range(0, 61, 10):
            wave = math.sin((i + self.float_offset * 10) * 0.3) * 3
            points.append((i, 50 + wave))
        points.append((60, 80))
        points.append((0, 80))
        pygame.draw.polygon(ghost_surface, (*GHOST_WHITE, self.opacity), points)
        
        pygame.draw.circle(ghost_surface, (*BLACK, self.opacity + 50), (20, 25), 4)
        pygame.draw.circle(ghost_surface, (*BLACK, self.opacity + 50), (40, 25), 4)
        
        screen.blit(ghost_surface, (int(self.x - 30), int(float_y - 40)))


class LightningFlash:
    """Random lightning effect"""
    def __init__(self):
        self.active = False
        self.timer = 0
        self.next_flash = random.randint(300, 600)
    
    def update(self):
        if self.active:
            self.timer += 1
            if self.timer > 10:
                self.active = False
                self.timer = 0
                self.next_flash = random.randint(300, 600)
        else:
            self.next_flash -= 1
            if self.next_flash <= 0:
                self.active = True
    
    def draw(self):
        if self.active:
            flash_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = 100 if self.timer < 5 else 50
            flash_surface.fill((*GHOST_WHITE, alpha))
            screen.blit(flash_surface, (0, 0))


class HorrorBackground:
    """Renders haunted forest/graveyard background"""
    def __init__(self):
        self.moon_glow = 0
    
    def draw(self):
        for y in range(0, HEIGHT, 10):
            darkness = int(20 + (y / HEIGHT) * 30)
            color = (darkness, darkness, darkness + 10)
            pygame.draw.rect(screen, color, (0, y, WIDTH, 10))
        
        self.moon_glow += 0.02
        moon_size = 70 + int(math.sin(self.moon_glow) * 5)
        pygame.draw.circle(screen, MOON_YELLOW, (WIDTH - 150, 100), moon_size)
        pygame.draw.circle(screen, (200, 200, 150), (WIDTH - 150, 100), moon_size - 10)
        
        grave_positions = [100, 280, 460, 640, 820]
        for i, x in enumerate(grave_positions):
            h = 60 + (i % 3) * 20
            # Outline
            pygame.draw.rect(screen, BLACK, (x - 2, HEIGHT - h - 42, 44, h + 4))
            pygame.draw.ellipse(screen, BLACK, (x - 7, HEIGHT - h - 64, 54, 44))
            # Fill
            pygame.draw.rect(screen, GRAVE_STONE, (x, HEIGHT - h - 40, 40, h))
            pygame.draw.ellipse(screen, GRAVE_STONE, (x - 5, HEIGHT - h - 60, 50, 40))
        
        for i in range(3):
            x = 50 + i * 350
            self.draw_dead_tree(x, HEIGHT - 150)
    
    def draw_dead_tree(self, x, y):
        # Trunk outline
        pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 24, 154))
        # Trunk
        pygame.draw.rect(screen, DEAD_TREE, (x, y, 20, 150))
        
        branches = [
            ((x + 10, y + 30), (x - 40, y - 20)),
            ((x + 10, y + 30), (x + 60, y - 10)),
            ((x + 10, y + 70), (x - 30, y + 50)),
            ((x + 10, y + 70), (x + 50, y + 60))
        ]
        # Draw branch outlines
        for start, end in branches:
            pygame.draw.line(screen, BLACK, start, end, 11)
        # Draw branches
        for start, end in branches:
            pygame.draw.line(screen, DEAD_TREE, start, end, 8)


class Star:
    """Dark atmospheric particles"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.size = random.choice([1, 2])
        self.speed = self.size * 0.2
        self.color = random.choice([GRAY, DARK_GRAY, FOG_GRAY])

    def update(self):
        self.x -= self.speed
        if self.x < -10:
            self.x = WIDTH + 10
            self.y = random.randint(0, HEIGHT)

    def draw(self):
        pygame.draw.rect(screen, self.color, (int(self.x), int(self.y), self.size, self.size))

# ================= BIRD =================
class Bird:
    def __init__(self, difficulty_config: DifficultyConfig):
        self.config = difficulty_config
        self.x = 150
        self.y = 250
        self.vel = 0
        self.gravity = difficulty_config.gravity
        self.lift = -4.5
        self.max_fall = 7
        self.angle = 0
        self.target_angle = 0
        
        try:
            loaded_img = pygame.image.load("images/bird.png").convert_alpha()
            self.original_img = pygame.transform.scale(
                loaded_img, 
                difficulty_config.get_bird_dimensions()
            )
        except:
            self.original_img = pygame.Surface(difficulty_config.get_bird_dimensions())
            self.original_img.fill(BLOOD_RED)
        
        self.img = self.original_img
        self.w, self.h = difficulty_config.get_bird_dimensions()
        self.collision_margin = max(4, int(12 - (difficulty_config.bird_scale * 4)))
        
        self.trail = []
        try:
            self.die_sound = pygame.mixer.Sound("sounds/die.mp3")
        except:
            self.die_sound = None

    def flap(self):
        self.vel = self.lift
        self.target_angle = 60

    def update(self):
        self.vel += self.gravity
        self.vel = min(self.vel, self.max_fall)
        self.y += self.vel
        
        if self.vel < -2:
            self.target_angle = 60
        elif self.vel < 0:
            self.target_angle = 30
        elif self.vel > 2:
            self.target_angle = -60
        else:
            self.target_angle = -30
        
        angle_diff = self.target_angle - self.angle
        self.angle += angle_diff * 0.2
        self.angle = max(-60, min(60, self.angle))
        
        if self.y < 0:
            self.y = 0
            self.vel = 0
        
        self.trail.append((self.x + self.w // 2, self.y + self.h // 2))
        if len(self.trail) > 5:
            self.trail.pop(0)
        
        self.img = pygame.transform.rotate(self.original_img, self.angle)

    def draw(self):
        for i, pos in enumerate(self.trail):
            alpha = int(150 * (i / len(self.trail)))
            size = 4 - i
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            surf.fill((*BLOOD_RED, alpha))
            screen.blit(surf, (pos[0] - size // 2, pos[1] - size // 2))
        
        rotated_rect = self.img.get_rect(center=(self.x + self.w // 2, self.y + self.h // 2))
        screen.blit(self.img, rotated_rect)

    def get_collision_rect(self):
        return pygame.Rect(
            self.x + self.collision_margin,
            self.y + self.collision_margin,
            self.w - (self.collision_margin * 2),
            self.h - (self.collision_margin * 2)
        )

    def hit_ground(self):
        return self.y + self.h >= HEIGHT - 5

# ================= BASE OBSTACLE =================
class Obstacle:
    def __init__(self, x, speed):
        self.x = x
        self.speed = speed
        self.scored = False
    
    def update(self):
        self.x -= self.speed
        return self.x < -150
    
    def passed_bird(self, bird):
        if not self.scored and bird.x > self.x + 100:
            self.scored = True
            return True
        return False

# ================= GRAVE PILLAR OBSTACLE =================
class GravePillarObstacle(Obstacle):
    """Haunted grave pillars"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 70
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.gap = difficulty_params['gap']
        
        max_height = int((HEIGHT - self.gap) // 2 - 50)
        self.height = random.randint(100, max(100, max_height))
        
        self.crack_pattern = [(random.randint(0, self.width), random.randint(0, 100)) 
                              for _ in range(5)]
    
    def draw(self):
        block_size = 10
        
        for py in range(0, int(self.height), block_size):
            for px in range(0, self.width, block_size):
                rect = pygame.Rect(self.x + px, py, block_size, block_size)
                pygame.draw.rect(screen, GRAVE_STONE, rect)
                pygame.draw.rect(screen, DARK_GRAY, rect, 1)
        
        for crack_x, crack_y in self.crack_pattern:
            if crack_y < self.height:
                pygame.draw.line(screen, BLACK, 
                               (self.x + crack_x, crack_y), 
                               (self.x + crack_x + 10, crack_y + 20), 2)
        
        bottom_y = self.height + self.gap
        for py in range(int(bottom_y), HEIGHT, block_size):
            for px in range(0, self.width, block_size):
                rect = pygame.Rect(self.x + px, py, block_size, block_size)
                pygame.draw.rect(screen, GRAVE_STONE, rect)
                pygame.draw.rect(screen, DARK_GRAY, rect, 1)
        
        for _ in range(3):
            moss_x = self.x + random.randint(0, self.width - 10)
            moss_y = random.randint(int(bottom_y), min(int(bottom_y) + 50, HEIGHT - 10))
            pygame.draw.rect(screen, TOXIC_GREEN, (moss_x, moss_y, 8, 8))
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        if collision_rect.right > self.x and collision_rect.left < self.x + self.width:
            if collision_rect.top < self.height or collision_rect.bottom > self.height + self.gap:
                return True
        return False

# ================= NEW: SKULL TOWER OBSTACLE =================
class SkullTowerObstacle(Obstacle):
    """Tower of stacked skulls"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 60
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.gap = difficulty_params['gap']
        
        max_height = int((HEIGHT - self.gap) // 2 - 50)
        self.height = random.randint(120, max(120, max_height))
        
        self.skull_wobble = random.uniform(0, math.pi * 2)
    
    def draw(self):
        self.skull_wobble += 0.05
        
        # Top tower of skulls
        skull_size = 30
        num_skulls_top = int(self.height / skull_size)
        
        for i in range(num_skulls_top):
            skull_y = i * skull_size
            skull_x = self.x + 15 + int(math.sin(self.skull_wobble + i) * 3)
            
            # Skull (simplified)
            pygame.draw.ellipse(screen, BONE_WHITE, (skull_x, skull_y, skull_size, skull_size))
            pygame.draw.ellipse(screen, BONE_WHITE, (skull_x, skull_y + 15, skull_size, 20))
            
            # Eye sockets
            pygame.draw.ellipse(screen, BLACK, (skull_x + 7, skull_y + 8, 8, 10))
            pygame.draw.ellipse(screen, BLACK, (skull_x + 17, skull_y + 8, 8, 10))
            
            # Glowing red eyes
            pygame.draw.circle(screen, BLOOD_RED, (skull_x + 11, skull_y + 12), 3)
            pygame.draw.circle(screen, BLOOD_RED, (skull_x + 21, skull_y + 12), 3)
        
        # Bottom tower of skulls
        bottom_y = self.height + self.gap
        num_skulls_bottom = int((HEIGHT - bottom_y) / skull_size)
        
        for i in range(num_skulls_bottom):
            skull_y = bottom_y + i * skull_size
            skull_x = self.x + 15 + int(math.sin(self.skull_wobble - i) * 3)
            
            pygame.draw.ellipse(screen, BONE_WHITE, (skull_x, skull_y, skull_size, skull_size))
            pygame.draw.ellipse(screen, BONE_WHITE, (skull_x, skull_y + 15, skull_size, 20))
            
            pygame.draw.ellipse(screen, BLACK, (skull_x + 7, skull_y + 8, 8, 10))
            pygame.draw.ellipse(screen, BLACK, (skull_x + 17, skull_y + 8, 8, 10))
            
            pygame.draw.circle(screen, BLOOD_RED, (skull_x + 11, skull_y + 12), 3)
            pygame.draw.circle(screen, BLOOD_RED, (skull_x + 21, skull_y + 12), 3)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        if collision_rect.right > self.x and collision_rect.left < self.x + self.width:
            if collision_rect.top < self.height or collision_rect.bottom > self.height + self.gap:
                return True
        return False

# ================= NEW: CREEPING VINES OBSTACLE =================
class CreepingVinesObstacle(Obstacle):
    """Animated creeping vines that sway"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 50
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.gap = difficulty_params['gap']
        
        self.vine_length = random.randint(150, 250)
        self.sway_offset = random.uniform(0, math.pi * 2)
        self.thorns = []
        
        # Generate thorn positions
        for i in range(0, self.vine_length, 20):
            self.thorns.append((random.randint(-10, 10), i))
    
    def draw(self):
        self.sway_offset += 0.03
        
        # Top vines hanging down
        base_x = self.x + 25
        
        for segment in range(0, int(self.vine_length), 8):
            sway = math.sin(self.sway_offset + segment * 0.1) * 15
            x_pos = base_x + sway
            y_pos = segment
            
            # Vine segment
            pygame.draw.circle(screen, TOXIC_GREEN, (int(x_pos), int(y_pos)), 6)
            pygame.draw.circle(screen, (0, 180, 50), (int(x_pos), int(y_pos)), 4)
        
        # Draw thorns
        for thorn_x, thorn_y in self.thorns:
            sway = math.sin(self.sway_offset + thorn_y * 0.1) * 15
            tx = base_x + sway + thorn_x
            ty = thorn_y
            
            # Thorn triangle
            thorn_points = [
                (tx, ty),
                (tx - 5, ty + 8),
                (tx + 5, ty + 8)
            ]
            pygame.draw.polygon(screen, DARK_RED, thorn_points)
        
        # Bottom vines growing up
        bottom_base = HEIGHT - 150
        
        for segment in range(0, 150, 8):
            sway = math.sin(self.sway_offset - segment * 0.1) * 15
            x_pos = base_x + sway
            y_pos = bottom_base + segment
            
            pygame.draw.circle(screen, TOXIC_GREEN, (int(x_pos), int(y_pos)), 6)
            pygame.draw.circle(screen, (0, 180, 50), (int(x_pos), int(y_pos)), 4)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        base_x = self.x + 25
        
        # Check collision with top vines
        for segment in range(0, int(self.vine_length), 8):
            sway = math.sin(self.sway_offset + segment * 0.1) * 15
            x_pos = base_x + sway
            y_pos = segment
            
            if collision_rect.collidepoint(int(x_pos), int(y_pos)):
                return True
        
        # Check collision with bottom vines
        bottom_base = HEIGHT - 150
        for segment in range(0, 150, 8):
            sway = math.sin(self.sway_offset - segment * 0.1) * 15
            x_pos = base_x + sway
            y_pos = bottom_base + segment
            
            if collision_rect.collidepoint(int(x_pos), int(y_pos)):
                return True
        
        return False

# ================= NEW: FLOATING EYEBALL OBSTACLE =================
class FloatingEyeballObstacle(Obstacle):
    """Giant floating eyeball that tracks the player"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 80
        self.eye_y = random.randint(150, HEIGHT - 150)
        self.eye_radius = 40
        self.pupil_angle = 0
        self.blink_timer = 0
        self.is_blinking = False
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.collision_radius = self.eye_radius + int((250 - difficulty_params['gap']) * 0.08)
    
    def update(self):
        result = super().update()
        
        # Blinking animation
        self.blink_timer += 1
        if self.blink_timer > 120:
            self.is_blinking = True
        if self.blink_timer > 130:
            self.is_blinking = False
            self.blink_timer = 0
        
        return result
    
    def draw(self):
        center = (self.x + 40, int(self.eye_y))
        
        # Bloodshot veins in the white
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            vein_end_x = center[0] + math.cos(angle) * (self.eye_radius - 5)
            vein_end_y = center[1] + math.sin(angle) * (self.eye_radius - 5)
            pygame.draw.line(screen, BLOOD_RED, center, (vein_end_x, vein_end_y), 1)
        
        # White of eye
        pygame.draw.circle(screen, GHOST_WHITE, center, self.eye_radius)
        
        if not self.is_blinking:
            # Iris (toxic green)
            pygame.draw.circle(screen, TOXIC_GREEN, center, 20)
            
            # Pupil (follows player - tracks left)
            pupil_offset = 8
            pupil_x = center[0] - pupil_offset
            pupil_y = center[1]
            pygame.draw.circle(screen, BLACK, (pupil_x, pupil_y), 10)
            
            # Glint
            pygame.draw.circle(screen, WHITE, (pupil_x + 3, pupil_y - 3), 3)
        else:
            # Closed eye (horizontal line)
            pygame.draw.line(screen, DARK_GRAY, 
                           (center[0] - self.eye_radius, center[1]),
                           (center[0] + self.eye_radius, center[1]), 3)
        
        # Eyelids
        pygame.draw.arc(screen, DARK_GRAY, 
                       (center[0] - self.eye_radius, center[1] - self.eye_radius,
                        self.eye_radius * 2, self.eye_radius * 2),
                       0, math.pi, 3)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        center = (self.x + 40, int(self.eye_y))
        bird_center = (collision_rect.centerx, collision_rect.centery)
        distance = math.sqrt((bird_center[0] - center[0])**2 + (bird_center[1] - center[1])**2)
        return distance < self.collision_radius

# ================= NEW: PENDULUM AXE OBSTACLE =================
class PendulumAxeObstacle(Obstacle):
    """Swinging axe pendulum"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 80
        self.pendulum_length = 150
        self.anchor_y = 50
        self.angle = random.uniform(-math.pi/3, math.pi/3)
        self.angular_velocity = 0
        self.angular_acceleration = 0.001
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.collision_radius = 35 + int((250 - difficulty_params['gap']) * 0.06)
    
    def update(self):
        result = super().update()
        
        # Pendulum physics
        self.angular_acceleration = -0.001 * math.sin(self.angle)
        self.angular_velocity += self.angular_acceleration
        self.angular_velocity *= 0.99  # Damping
        self.angle += self.angular_velocity
        
        # Limit swing
        if abs(self.angle) > math.pi / 2:
            self.angle = math.copysign(math.pi / 2, self.angle)
            self.angular_velocity *= -0.8
        
        return result
    
    def draw(self):
        anchor = (self.x + 40, self.anchor_y)
        
        # Calculate axe position
        axe_x = anchor[0] + math.sin(self.angle) * self.pendulum_length
        axe_y = anchor[1] + math.cos(self.angle) * self.pendulum_length
        
        # Chain/rope
        pygame.draw.line(screen, GRAY, anchor, (int(axe_x), int(axe_y)), 3)
        
        # Draw chain links
        num_links = 8
        for i in range(num_links):
            t = i / num_links
            link_x = anchor[0] + math.sin(self.angle) * self.pendulum_length * t
            link_y = anchor[1] + math.cos(self.angle) * self.pendulum_length * t
            pygame.draw.circle(screen, DARK_GRAY, (int(link_x), int(link_y)), 4)
        
        # Axe head (rotated)
        axe_angle = self.angle + math.pi / 2
        
        # Blade
        blade_length = 40
        blade_width = 20
        
        blade_points = [
            (axe_x - math.cos(axe_angle) * blade_width, 
             axe_y - math.sin(axe_angle) * blade_width),
            (axe_x + math.cos(axe_angle) * blade_width,
             axe_y + math.sin(axe_angle) * blade_width),
            (axe_x + math.sin(axe_angle) * blade_length,
             axe_y - math.cos(axe_angle) * blade_length)
        ]
        
        pygame.draw.polygon(screen, DARK_GRAY, [(int(p[0]), int(p[1])) for p in blade_points])
        pygame.draw.polygon(screen, BLOOD_RED, [(int(p[0]), int(p[1])) for p in blade_points], 3)
        
        # Handle
        handle_start = (axe_x, axe_y)
        handle_end = (axe_x - math.sin(axe_angle) * 30,
                     axe_y + math.cos(axe_angle) * 30)
        pygame.draw.line(screen, DEAD_TREE, handle_start, handle_end, 8)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        
        # Axe position
        anchor = (self.x + 40, self.anchor_y)
        axe_x = anchor[0] + math.sin(self.angle) * self.pendulum_length
        axe_y = anchor[1] + math.cos(self.angle) * self.pendulum_length
        
        bird_center = (collision_rect.centerx, collision_rect.centery)
        distance = math.sqrt((bird_center[0] - axe_x)**2 + (bird_center[1] - axe_y)**2)
        return distance < self.collision_radius

# ================= NEW: COFFIN OBSTACLE =================
class CoffinObstacle(Obstacle):
    """Vertical coffins with opening lids"""
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 60
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.gap = difficulty_params['gap']
        
        max_height = int((HEIGHT - self.gap) // 2 - 50)
        self.height = random.randint(120, max(120, max_height))
        
        self.lid_open = 0
        self.lid_direction = 1
    
    def update(self):
        result = super().update()
        
        # Animate lid opening/closing
        self.lid_open += self.lid_direction * 0.5
        if self.lid_open >= 15:
            self.lid_direction = -1
        elif self.lid_open <= 0:
            self.lid_direction = 1
        
        return result
    
    def draw(self):
        coffin_width = 50
        coffin_x = self.x + 5
        
        # Top coffin
        # Main body
        pygame.draw.rect(screen, DEAD_TREE, (coffin_x, 0, coffin_width, int(self.height)))
        pygame.draw.rect(screen, BLACK, (coffin_x, 0, coffin_width, int(self.height)), 2)
        
        # Lid (opening)
        lid_offset = int(self.lid_open)
        pygame.draw.rect(screen, DARK_GRAY, 
                        (coffin_x - lid_offset, 0, coffin_width, 20))
        
        # Cross on coffin
        cross_x = coffin_x + 20
        cross_y = int(self.height) - 40
        pygame.draw.line(screen, BONE_WHITE, (cross_x, cross_y - 10), (cross_x, cross_y + 10), 3)
        pygame.draw.line(screen, BONE_WHITE, (cross_x - 7, cross_y), (cross_x + 7, cross_y), 3)
        
        # Bottom coffin
        bottom_y = self.height + self.gap
        pygame.draw.rect(screen, DEAD_TREE, 
                        (coffin_x, int(bottom_y), coffin_width, HEIGHT - int(bottom_y)))
        pygame.draw.rect(screen, BLACK, 
                        (coffin_x, int(bottom_y), coffin_width, HEIGHT - int(bottom_y)), 2)
        
        # Bottom lid
        pygame.draw.rect(screen, DARK_GRAY, 
                        (coffin_x - lid_offset, int(bottom_y), coffin_width, 20))
        
        # Cross on bottom coffin
        cross_y_bottom = int(bottom_y) + 40
        pygame.draw.line(screen, BONE_WHITE, 
                        (cross_x, cross_y_bottom - 10), (cross_x, cross_y_bottom + 10), 3)
        pygame.draw.line(screen, BONE_WHITE, 
                        (cross_x - 7, cross_y_bottom), (cross_x + 7, cross_y_bottom), 3)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        coffin_x = self.x + 5
        coffin_width = 50
        
        if collision_rect.right > coffin_x and collision_rect.left < coffin_x + coffin_width:
            if collision_rect.top < self.height or collision_rect.bottom > self.height + self.gap:
                return True
        return False

# ================= EXISTING OBSTACLES (kept) =================
class LaserGateObstacle(Obstacle):
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 15
        self.gate_height = random.randint(150, HEIGHT - 150)
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.laser_thickness = int(difficulty_params['gap'] * 0.35)
        
        self.flash_counter = 0
        self.block_size = 5
    
    def draw(self):
        self.flash_counter += 1
        flash = (self.flash_counter // 8) % 2 == 0
        
        emitter_top = pygame.Rect(self.x, self.gate_height - self.laser_thickness // 2 - 20, self.width, 20)
        emitter_bottom = pygame.Rect(self.x, self.gate_height + self.laser_thickness // 2, self.width, 20)
        
        for rect in [emitter_top, emitter_bottom]:
            for bx in range(0, self.width, self.block_size):
                for by in range(0, 20, self.block_size):
                    block_rect = pygame.Rect(rect.x + bx, rect.y + by, self.block_size, self.block_size)
                    pygame.draw.rect(screen, DARK_GRAY, block_rect)
                    pygame.draw.rect(screen, BLOOD_RED, block_rect, 1)
        
        if flash:
            laser_rect = pygame.Rect(self.x, self.gate_height - self.laser_thickness // 2, self.width, self.laser_thickness)
            pygame.draw.rect(screen, BLOOD_RED, laser_rect)
            inner = pygame.Rect(self.x + 3, laser_rect.y + 3, self.width - 6, self.laser_thickness - 6)
            pygame.draw.rect(screen, RED, inner)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        laser_rect = pygame.Rect(self.x, self.gate_height - self.laser_thickness // 2, self.width, self.laser_thickness)
        return collision_rect.colliderect(laser_rect)

class ElectricCoilObstacle(Obstacle):
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 40
        self.coil_y = random.randint(150, HEIGHT - 150)
        self.spark_counter = 0
        self.spark_particles = []
        self.block_size = 4
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.collision_radius = 30 + int((250 - difficulty_params['gap']) * 0.1)
    
    def update(self):
        result = super().update()
        self.spark_counter += 1
        
        if self.spark_counter % 5 == 0:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 3)
            self.spark_particles.append({
                'x': self.x + 20,
                'y': self.coil_y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 20
            })
        
        for particle in self.spark_particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['life'] -= 1
            if particle['life'] <= 0:
                self.spark_particles.remove(particle)
        
        return result
    
    def draw(self):
        center = (self.x + 20, self.coil_y)
        
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            for radius in [10, 15, 20]:
                x = center[0] + int(math.cos(rad) * radius)
                y = center[1] + int(math.sin(rad) * radius)
                x = (x // self.block_size) * self.block_size
                y = (y // self.block_size) * self.block_size
                color = TOXIC_GREEN if radius == 20 else DARK_GRAY
                pygame.draw.rect(screen, color, (x, y, self.block_size, self.block_size))
        
        for i in range(3):
            angle = (self.spark_counter + i * 120) % 360
            end_x = center[0] + math.cos(math.radians(angle)) * 25
            end_y = center[1] + math.sin(math.radians(angle)) * 25
            pygame.draw.line(screen, TOXIC_GREEN, center, (end_x, end_y), 2)
        
        for particle in self.spark_particles:
            alpha = int(255 * (particle['life'] / 20))
            size = max(1, int(3 * (particle['life'] / 20)))
            surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*TOXIC_GREEN, alpha), (size, size), size)
            screen.blit(surf, (int(particle['x']) - size, int(particle['y']) - size))
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        center = (self.x + 20, self.coil_y)
        bird_center = (collision_rect.centerx, collision_rect.centery)
        distance = math.sqrt((bird_center[0] - center[0])**2 + (bird_center[1] - center[1])**2)
        return distance < self.collision_radius

class SpinningBladeObstacle(Obstacle):
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 60
        self.blade_y = random.randint(150, HEIGHT - 150)
        self.rotation = 0
        self.blade_length = 35
        self.block_size = 4
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.collision_radius = 35 + int((250 - difficulty_params['gap']) * 0.08)
    
    def draw(self):
        self.rotation += 8
        center = (self.x + 30, self.blade_y)
        
        for i in range(4):
            angle = math.radians(self.rotation + i * 90)
            
            for dist in range(10, self.blade_length, self.block_size):
                x = center[0] + math.cos(angle) * dist
                y = center[1] + math.sin(angle) * dist
                x = int(x // self.block_size) * self.block_size
                y = int(y // self.block_size) * self.block_size
                
                width = self.block_size * 2 if dist > 20 else self.block_size
                pygame.draw.rect(screen, DARK_GRAY, (x, y, width, width))
                pygame.draw.rect(screen, BLOOD_RED, (x, y, width, width), 1)
        
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            for radius in [6, 9, 12]:
                x = center[0] + int(math.cos(rad) * radius)
                y = center[1] + int(math.sin(rad) * radius)
                pygame.draw.rect(screen, DARK_GRAY if radius < 12 else BLOOD_RED, 
                               (x - 2, y - 2, 4, 4))
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        center = (self.x + 30, self.blade_y)
        bird_center = (collision_rect.centerx, collision_rect.centery)
        distance = math.sqrt((bird_center[0] - center[0])**2 + (bird_center[1] - center[1])**2)
        return distance < self.collision_radius

class BouncingBallObstacle(Obstacle):
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 50
        self.ball_x = x + 25
        self.ball_y = random.randint(100, HEIGHT - 100)
        self.ball_vy = random.choice([-4, 4])
        self.radius = 25
        self.block_size = 4
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.collision_radius = self.radius + 10 + int((250 - difficulty_params['gap']) * 0.05)
    
    def update(self):
        result = super().update()
        
        self.ball_x -= self.speed
        self.ball_y += self.ball_vy
        
        if self.ball_y - self.radius < 50 or self.ball_y + self.radius > HEIGHT - 50:
            self.ball_vy *= -1
        
        return result
    
    def draw(self):
        center = (int(self.ball_x), int(self.ball_y))
        
        for angle in range(0, 360, 10):
            rad = math.radians(angle)
            for radius in range(self.radius - 10, self.radius, 5):
                x = center[0] + int(math.cos(rad) * radius)
                y = center[1] + int(math.sin(rad) * radius)
                x = (x // self.block_size) * self.block_size
                y = (y // self.block_size) * self.block_size
                color = TOXIC_GREEN if radius > self.radius - 5 else DARK_GRAY
                pygame.draw.rect(screen, color, (x, y, self.block_size, self.block_size))
        
        for i in range(4):
            angle = math.radians(pygame.time.get_ticks() * 0.5 + i * 90)
            end_x = center[0] + math.cos(angle) * 10
            end_y = center[1] + math.sin(angle) * 10
            pygame.draw.line(screen, BLOOD_RED, center, (end_x, end_y), 2)
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        bird_center = (collision_rect.centerx, collision_rect.centery)
        distance = math.sqrt((bird_center[0] - self.ball_x)**2 + (bird_center[1] - self.ball_y)**2)
        return distance < self.collision_radius

class PortalObstacle(Obstacle):
    def __init__(self, x, speed, score, difficulty_config):
        super().__init__(x, speed)
        self.width = 50
        
        difficulty_params = calculate_difficulty_params(score, difficulty_config)
        self.gap = difficulty_params['gap']
        
        self.portal_y = random.randint(150, HEIGHT - 150)
        self.rotation = 0
        self.block_size = 3
    
    def draw(self):
        self.rotation += 3
        
        top_y = max(50, int(self.portal_y - self.gap // 2))
        top_center = (self.x + 25, top_y)
        for angle in range(0, 360, 20):
            rad = math.radians(angle + self.rotation)
            for radius in range(15, 30, 5):
                x = top_center[0] + int(math.cos(rad) * radius)
                y = top_center[1] + int(math.sin(rad) * radius)
                x = (x // self.block_size) * self.block_size
                y = (y // self.block_size) * self.block_size
                color = PURPLE_MIST if radius > 20 else DARK_GRAY
                pygame.draw.rect(screen, color, (x, y, self.block_size, self.block_size))
        
        bottom_y = min(HEIGHT - 50, int(self.portal_y + self.gap // 2))
        bottom_center = (self.x + 25, bottom_y)
        for angle in range(0, 360, 20):
            rad = math.radians(angle - self.rotation)
            for radius in range(15, 30, 5):
                x = bottom_center[0] + int(math.cos(rad) * radius)
                y = bottom_center[1] + int(math.sin(rad) * radius)
                x = (x // self.block_size) * self.block_size
                y = (y // self.block_size) * self.block_size
                color = BLOOD_RED if radius > 20 else DARK_GRAY
                pygame.draw.rect(screen, color, (x, y, self.block_size, self.block_size))
    
    def collide(self, bird):
        collision_rect = bird.get_collision_rect()
        
        top_y = max(50, int(self.portal_y - self.gap // 2))
        bottom_y = min(HEIGHT - 50, int(self.portal_y + self.gap // 2))
        
        if collision_rect.right > self.x and collision_rect.left < self.x + self.width:
            if collision_rect.top < top_y + 30 or collision_rect.bottom > bottom_y - 30:
                return True
        return False

# ================= SCORE =================
class Score:
    def __init__(self):
        self.value = 0

    def add(self):
        self.value += 1

    def draw(self):
        box_rect = pygame.Rect(WIDTH // 2 - 70, 15, 140, 50)
        pygame.draw.rect(screen, BLACK, box_rect)
        pygame.draw.rect(screen, BLOOD_RED, box_rect, 3)
        
        UITheme.draw_text(screen, str(self.value), WIDTH // 2, 40, 48, WHITE)

# ================= MAIN GAME =================
class NoisyBird:
    loud = False

    def __init__(self):
        self.session_manager = GameSessionManager()
        self.leaderboard_manager = LeaderboardManager()
        self.difficulty_manager = DifficultyManager()
        self.state = GameState.SPLASH_SCREEN
        self.theme = UITheme()
        
        self.attempts_input = ""
        self.username_input = ""
        self.selected_difficulty_index = 1
        
        self.bird = None
        self.score = None
        self.obstacles = []
        self.game_over_timer = 0
        self.current_difficulty_config = None
        self.current_difficulty_params = None
        
        self.horror_background = HorrorBackground()
        self.fog_particles = [FogParticle() for _ in range(15)]
        self.bats = [Bat() for _ in range(5)]
        self.ghosts = [Ghost() for _ in range(3)]
        self.lightning = LightningFlash()
        self.stars = [Star() for _ in range(30)]
        
        try:
            self.logo = pygame.image.load("images/logoexe.png").convert_alpha()
            self.logo = pygame.transform.scale(self.logo, (500, 350))
            self.logo.set_alpha(500)
        except:
            self.logo = None

    def reset_game(self):
        """Reset game for new attempt with dynamic difficulty"""
        player = self.session_manager.get_current_player()
        if player:
            self.current_difficulty_config = self.difficulty_manager.get_config(player.difficulty)
            self.bird = Bird(self.current_difficulty_config)
            self.score = Score()
            
            difficulty_params = calculate_difficulty_params(0, self.current_difficulty_config)
            speed = difficulty_params['speed']
            h_dist = difficulty_params['horizontal_distance']
            
            self.obstacles = [
                GravePillarObstacle(WIDTH + 200, speed, 0, self.current_difficulty_config),
                GravePillarObstacle(WIDTH + 200 + h_dist, speed, 0, self.current_difficulty_config)
            ]
            self.game_over_timer = 0
            self.current_difficulty_params = difficulty_params

    def spawn_obstacle(self, score_value):
        """Spawn obstacles with dynamic difficulty scaling and NEW obstacles"""
        difficulty_params = calculate_difficulty_params(score_value, self.current_difficulty_config)
        speed = difficulty_params['speed']
        
        self.current_difficulty_params = difficulty_params
        
        # Progressive obstacle variety with NEW obstacles
        if score_value >= 20:
            obstacle_class = random.choice([
                GravePillarObstacle,
                LaserGateObstacle,
                ElectricCoilObstacle,
                SpinningBladeObstacle,
                BouncingBallObstacle,
                PortalObstacle,
                SkullTowerObstacle,      # NEW
                CreepingVinesObstacle,   # NEW
                FloatingEyeballObstacle, # NEW
                PendulumAxeObstacle,     # NEW
                CoffinObstacle           # NEW
            ])
        elif score_value >= 15:
            obstacle_class = random.choice([
                GravePillarObstacle,
                LaserGateObstacle,
                ElectricCoilObstacle,
                SpinningBladeObstacle,
                BouncingBallObstacle,
                PortalObstacle,
                SkullTowerObstacle,      # NEW
                FloatingEyeballObstacle  # NEW
            ])
        elif score_value >= 10:
            obstacle_class = random.choice([
                GravePillarObstacle,
                LaserGateObstacle,
                ElectricCoilObstacle,
                SpinningBladeObstacle,
                SkullTowerObstacle       # NEW
            ])
        elif score_value >= 5:
            obstacle_class = random.choice([
                GravePillarObstacle,
                LaserGateObstacle,
                SkullTowerObstacle       # NEW
            ])
        else:
            obstacle_class = GravePillarObstacle
        
        return obstacle_class(WIDTH + 100, speed, score_value, self.current_difficulty_config)

    def draw_button(self, text, x, y, width, height, selected=False):
        rect = pygame.Rect(x, y, width, height)
        color = PURPLE_MIST if selected else DARK_GRAY
        border_color = BLOOD_RED if selected else PURPLE
        
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, border_color, rect, 3)
        
        UITheme.draw_text(screen, text, rect.centerx, rect.centery, 32, WHITE)
        return rect

    def draw_splash_screen(self):
        """Draw the intro splash screen with logo and title"""
        # Logo centered
        if self.logo:
            logo_rect = self.logo.get_rect(center=(WIDTH // 2, 100))
            screen.blit(self.logo, logo_rect)
        
        # PRESENTS text
        UITheme.draw_text(screen, "PRESENTS", WIDTH // 2, 220, 48, BLOOD_RED, horror_style='dripping')
        
        # SCREAMING FLAPPY text with horror style
        UITheme.draw_text(screen, "SCREAMING FLAPPY", WIDTH // 2, 320, 52, TOXIC_GREEN, horror_style='shaky')
        
        # Press ENTER text at bottom
        UITheme.draw_text(screen, "Press ENTER to continue", WIDTH // 2, 480, 24, GRAY)

    def draw_setup_attempts(self):
        UITheme.draw_text(screen, "WELCOME ", WIDTH // 2, 150, 64, BLOOD_RED, horror_style='dripping')
        UITheme.draw_text(screen, "HOW MANY ATTEMPTS PER PLAYER?", WIDTH // 2, 230, 36, TOXIC_GREEN, horror_style='shaky')
        
        input_rect = pygame.Rect(WIDTH // 2 - 100, 280, 200, 50)
        pygame.draw.rect(screen, BLACK, input_rect)
        pygame.draw.rect(screen, BLOOD_RED, input_rect, 3)
        
        display_text = self.attempts_input + "_" if self.attempts_input else "3_"
        UITheme.draw_text(screen, display_text, WIDTH // 2, 305, 36, WHITE)
        
        UITheme.draw_text(screen, "Press ENTER to continue", WIDTH // 2, 380, 24, GRAY)
        UITheme.draw_text(screen, "(Enter number 1-9, default is 3)", WIDTH // 2, 410, 20, GRAY)

    def draw_username_input(self):
        player = self.session_manager.get_current_player()
        player_num = self.session_manager.current_player_index + 1
        
        if player and player.current_attempt > 0:
            UITheme.draw_text(screen, f"{player.username} - ATTEMPT {player.current_attempt + 1}", 
                            WIDTH // 2, 150, 48, BLOOD_RED, horror_style='jagged')
        else:
            UITheme.draw_text(screen, f"PLAYER {player_num}", WIDTH // 2, 150, 48, BLOOD_RED, horror_style='jagged')
        
        UITheme.draw_text(screen, "ENTER USERNAME", WIDTH // 2, 230, 36, TOXIC_GREEN, horror_style='shaky')
        
        input_rect = pygame.Rect(WIDTH // 2 - 150, 280, 300, 50)
        pygame.draw.rect(screen, BLACK, input_rect)
        pygame.draw.rect(screen, BLOOD_RED, input_rect, 3)
        
        UITheme.draw_text(screen, self.username_input + "_", WIDTH // 2, 305, 36, WHITE)
        
        UITheme.draw_text(screen, "Press ENTER to continue", WIDTH // 2, 380, 24, GRAY)
        UITheme.draw_text(screen, "(Max 10 characters)", WIDTH // 2, 410, 20, GRAY)

    def draw_difficulty_select(self):
        player = self.session_manager.get_current_player()
        UITheme.draw_text(screen, f"{player.username} - SELECT DIFFICULTY", WIDTH // 2, 120, 42, BLOOD_RED, horror_style='cracked')
        
        difficulties = DifficultyManager.get_all_names()
        y_pos = 200
        
        for i, diff in enumerate(difficulties):
            config = DifficultyManager.get_config(diff)
            selected = i == self.selected_difficulty_index
            
            self.draw_button(diff, WIDTH // 2 - 120, y_pos + i * 70, 240, 55, selected)
            
            if selected:
                # Show easy mode status
                easy_status = "EASY MODE ON" if config.easy_mode else "HARD FROM START"
                stats = f"Bird: {int(config.bird_scale * 100)}% | Speed: {config.obstacle_speed:.1f} | {easy_status}"
                UITheme.draw_text(screen, stats, WIDTH // 2, y_pos + i * 70 + 75, 16, GRAY)
        
        UITheme.draw_text(screen, "Use UP/DOWN arrows, ENTER to continue", WIDTH // 2, 530, 24, GRAY)

    def draw_waiting(self):
        if self.bird:
            self.bird.draw()
        
        player = self.session_manager.get_current_player()
        attempt_text = f"Attempt {player.current_attempt + 1}/{player.max_attempts}"
        
        UITheme.draw_text(screen, "SCREAMING FLAPPY BIRD", WIDTH // 2, 180, 56, BLOOD_RED, horror_style='dripping')
        UITheme.draw_text(screen, "MAKE NOISE TO FLY", WIDTH // 2, 250, 42, TOXIC_GREEN, horror_style='shaky')
        UITheme.draw_text(screen, f"{player.username} | {player.difficulty}", WIDTH // 2, 300, 28, GHOST_WHITE)
        UITheme.draw_text(screen, attempt_text, WIDTH // 2, 330, 24, GRAY)
        UITheme.draw_text(screen, "Press SPACE to start", WIDTH // 2, 380, 28, WHITE)

    def draw_attempt_summary(self):
        player = self.session_manager.get_current_player()
        remaining = player.get_remaining_attempts()
        
        UITheme.draw_text(screen, f"Score: {self.score.value}", WIDTH // 2, 200, 56, WHITE, horror_style='dripping')
        UITheme.draw_text(screen, f"{player.username}", WIDTH // 2, 260, 36, TOXIC_GREEN, horror_style='shaky')
        
        if remaining > 0:
            UITheme.draw_text(screen, f"{remaining} Attempt(s) Remaining", WIDTH // 2, 320, 32, BLOOD_RED)
            UITheme.draw_text(screen, "Press SPACE to continue", WIDTH // 2, 400, 28, WHITE)
        else:
            UITheme.draw_text(screen, "All attempts used!", WIDTH // 2, 320, 32, BLOOD_RED)
            
            if not self.session_manager.all_players_finished():
                UITheme.draw_text(screen, "Press SPACE for next player", WIDTH // 2, 400, 28, WHITE)
            else:
                UITheme.draw_text(screen, "Press SPACE for final results", WIDTH // 2, 400, 28, WHITE)

    def draw_session_leaderboard(self):
        UITheme.draw_text(screen, "SESSION RESULTS", WIDTH // 2, 60, 48, BLOOD_RED, horror_style='cracked')
        
        board_rect = pygame.Rect(WIDTH // 2 - 300, 120, 600, 400)
        pygame.draw.rect(screen, BLACK, board_rect)
        pygame.draw.rect(screen, BLOOD_RED, board_rect, 3)
        
        leaderboard = self.session_manager.get_session_leaderboard()
        
        y = 150
        for i, entry in enumerate(leaderboard):
            rank_color = [TOXIC_GREEN, PURPLE_MIST, BLOOD_RED, WHITE, GRAY][min(i, 4)]
            rank_text = f"{i+1}. {entry['username'][:10]}"
            score_text = f"{entry['best_score']} ({entry['difficulty'][:3]})"
            
            UITheme.draw_text(screen, rank_text, WIDTH // 2 - 200, y, 28, rank_color, center=False)
            UITheme.draw_text(screen, score_text, WIDTH // 2 + 150, y, 28, WHITE, center=False)
            
            all_scores = " | ".join(str(s) for s in entry['all_scores'])
            UITheme.draw_text(screen, f"Scores: {all_scores}", WIDTH // 2 - 200, y + 25, 18, GRAY, center=False)
            
            y += 70
        
        UITheme.draw_text(screen, "Press SPACE to start new session", WIDTH // 2, 550, 24, GRAY)

    def play(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                if event.type == pygame.KEYDOWN:
                    if self.state == GameState.SPLASH_SCREEN:
                        if event.key == pygame.K_RETURN:
                            self.state = GameState.SETUP_ATTEMPTS
                    
                    elif self.state == GameState.SETUP_ATTEMPTS:
                        if event.key == pygame.K_RETURN:
                            attempts = int(self.attempts_input) if self.attempts_input.isdigit() else 3
                            attempts = max(1, min(9, attempts))
                            self.session_manager.start_new_session(attempts)
                            self.state = GameState.USERNAME_INPUT
                        elif event.key == pygame.K_BACKSPACE:
                            self.attempts_input = self.attempts_input[:-1]
                        elif event.unicode.isdigit() and len(self.attempts_input) < 1:
                            self.attempts_input += event.unicode
                    
                    elif self.state == GameState.USERNAME_INPUT:
                        if event.key == pygame.K_RETURN and len(self.username_input) > 0:
                            player = self.session_manager.get_current_player()
                            if not player or player.is_complete:
                                self.session_manager.add_player(self.username_input)
                                player = self.session_manager.get_current_player()
                            
                            self.username_input = ""
                            self.state = GameState.DIFFICULTY_SELECT
                        elif event.key == pygame.K_BACKSPACE:
                            self.username_input = self.username_input[:-1]
                        elif len(self.username_input) < 10 and event.unicode.isalnum():
                            self.username_input += event.unicode.upper()
                    
                    elif self.state == GameState.DIFFICULTY_SELECT:
                        difficulties = DifficultyManager.get_all_names()
                        if event.key == pygame.K_UP:
                            self.selected_difficulty_index = max(0, self.selected_difficulty_index - 1)
                        elif event.key == pygame.K_DOWN:
                            self.selected_difficulty_index = min(len(difficulties) - 1, self.selected_difficulty_index + 1)
                        elif event.key == pygame.K_RETURN:
                            player = self.session_manager.get_current_player()
                            player.difficulty = difficulties[self.selected_difficulty_index]
                            self.reset_game()
                            self.state = GameState.WAITING
                    
                    elif self.state == GameState.WAITING:
                        if event.key == pygame.K_SPACE:
                            self.state = GameState.PLAYING
                    
                    elif self.state == GameState.GAME_OVER:
                        if self.game_over_timer > 40:
                            if event.key == pygame.K_SPACE:
                                player = self.session_manager.get_current_player()
                                player.record_score(self.score.value)
                                self.leaderboard_manager.add_score(
                                    player.username, 
                                    self.score.value, 
                                    player.difficulty
                                )
                                self.state = GameState.ATTEMPT_SUMMARY
                    
                    elif self.state == GameState.ATTEMPT_SUMMARY:
                        if event.key == pygame.K_SPACE:
                            player = self.session_manager.get_current_player()
                            
                            if player.get_remaining_attempts() > 0:
                                self.reset_game()
                                self.state = GameState.WAITING
                            elif not self.session_manager.all_players_finished():
                                self.session_manager.move_to_next_player()
                                self.state = GameState.USERNAME_INPUT
                            else:
                                self.state = GameState.SESSION_LEADERBOARD
                    
                    elif self.state == GameState.SESSION_LEADERBOARD:
                        if event.key == pygame.K_SPACE:
                            self.attempts_input = ""
                            self.state = GameState.SPLASH_SCREEN

            screen.fill(BLACK)
            
            self.horror_background.draw()
            
            for fog in self.fog_particles:
                fog.update()
                fog.draw()
            
            for star in self.stars:
                star.update()
                star.draw()
            
            for ghost in self.ghosts:
                ghost.update()
                ghost.draw()
            
            for bat in self.bats:
                bat.update()
                bat.draw()

            if self.state == GameState.SPLASH_SCREEN:
                self.draw_splash_screen()
            
            elif self.state == GameState.SETUP_ATTEMPTS:
                self.draw_setup_attempts()
            
            elif self.state == GameState.USERNAME_INPUT:
                self.draw_username_input()
            
            elif self.state == GameState.DIFFICULTY_SELECT:
                self.draw_difficulty_select()
            
            elif self.state == GameState.WAITING:
                self.draw_waiting()
            
            elif self.state == GameState.PLAYING:
                if NoisyBird.loud:
                    self.bird.flap()
                
                self.bird.update()
                
                obstacles_to_remove = []
                for i, obs in enumerate(self.obstacles):
                    obs.draw()
                    if obs.passed_bird(self.bird):
                        self.score.add()
                        
                        difficulty_params = calculate_difficulty_params(self.score.value, self.current_difficulty_config)
                        h_distance = difficulty_params['horizontal_distance']
                        
                        new_obstacle = self.spawn_obstacle(self.score.value)
                        
                        if self.obstacles:
                            last_x = max(o.x for o in self.obstacles)
                            new_obstacle.x = last_x + h_distance
                        
                        self.obstacles.append(new_obstacle)
                    
                    if obs.update():
                        obstacles_to_remove.append(i)
                    if obs.collide(self.bird):
                        if self.bird.die_sound:
                            self.bird.die_sound.play()
                        self.state = GameState.GAME_OVER
                        self.game_over_timer = 0
                
                for i in reversed(obstacles_to_remove):
                    self.obstacles.pop(i)
                
                if self.bird.hit_ground():
                    if self.bird.die_sound:
                        self.bird.die_sound.play()
                    self.state = GameState.GAME_OVER
                    self.game_over_timer = 0
                
                self.bird.draw()
                self.score.draw()
            
            elif self.state == GameState.GAME_OVER:
                self.game_over_timer += 1
                
                self.bird.draw()
                for obs in self.obstacles:
                    obs.draw()
                self.score.draw()
                
                UITheme.draw_text(screen, "GAME OVER", WIDTH // 2, 220, 64, BLOOD_RED, horror_style='dripping')
                UITheme.draw_text(screen, f"Score: {self.score.value}", WIDTH // 2, 300, 42, WHITE)
                
                if self.game_over_timer > 40:
                    UITheme.draw_text(screen, "Press SPACE to continue", WIDTH // 2, 400, 28, GRAY)
            
            elif self.state == GameState.ATTEMPT_SUMMARY:
                self.draw_attempt_summary()
            
            elif self.state == GameState.SESSION_LEADERBOARD:
                self.draw_session_leaderboard()

            self.lightning.update()
            self.lightning.draw()

            pygame.display.flip()
            clock.tick(60)

# ================= ENTRY =================
def main():
    try:
        def sound_callback(indata, frames, time, status):
            volume = np.sqrt(np.mean(indata**2))
            NoisyBird.loud = volume > 0.02
        
        stream = sd.InputStream(
            channels=1,
            samplerate=44100,
            blocksize=1024,
            callback=sound_callback
        )
        stream.start()

        NoisyBird().play()
    except Exception as e:
        print(f"Error: {e}")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()
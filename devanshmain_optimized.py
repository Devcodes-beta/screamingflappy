"""
SCREAMING FLAPPY BIRD - With Advanced Noise-Robust Audio Processing
=====================================================================
This version uses FFT-based frequency analysis to filter background noise
and detect intentional user sounds (voice, claps, snaps).

Much more robust than simple amplitude detection!
"""

import pygame
import numpy as np
import random
import sys
import math
import json
import os
from typing import List, Tuple, Dict
from enum import Enum

# Import the advanced audio processor
from audio_processor import AdvancedAudioProcessor, SimplifiedAudioProcessor

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
DIFFICULTY_START_SCORE = 5
BASE_GAP = 250
MIN_GAP = 140
GAP_DECREASE_RATE = 5

BASE_OBSTACLE_SPEED = 3.0
MAX_OBSTACLE_SPEED = 7.5
SPEED_INCREASE_RATE = 0.15

BASE_HORIZONTAL_DISTANCE = 450
MIN_HORIZONTAL_DISTANCE = 280
DISTANCE_DECREASE_RATE = 7

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
    AUDIO_SETUP = 9  # NEW: Audio calibration screen

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
        self.easy_mode = easy_mode
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
            easy_mode=True
        ),
        "MEDIUM": DifficultyConfig(
            name="MEDIUM",
            bird_scale=1.0,
            obstacle_speed=5.0,
            noise_threshold=0.012,
            gravity=0.4,
            easy_mode=True
        ),
        "FAST": DifficultyConfig(
            name="FAST",
            bird_scale=1.2,
            obstacle_speed=6.0,
            noise_threshold=0.010,
            gravity=0.45,
            easy_mode=False
        ),
        "GODLIKE": DifficultyConfig(
            name="GODLIKE",
            bird_scale=1.2,
            obstacle_speed=9.0,
            noise_threshold=0.008,
            gravity=0.5,
            easy_mode=False
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
    """Calculate difficulty parameters based on current score and difficulty mode."""
    
    if not difficulty_config.easy_mode:
        gap = MIN_GAP + 50
        speed = difficulty_config.obstacle_speed
        h_distance = MIN_HORIZONTAL_DISTANCE + 100
        
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
    
    if score < DIFFICULTY_START_SCORE:
        return {
            'gap': BASE_GAP,
            'speed': BASE_OBSTACLE_SPEED,
            'horizontal_distance': BASE_HORIZONTAL_DISTANCE
        }
    
    score_above_threshold = score - DIFFICULTY_START_SCORE
    
    gap = BASE_GAP - (score_above_threshold * GAP_DECREASE_RATE)
    gap = max(MIN_GAP, gap)
    
    speed = BASE_OBSTACLE_SPEED + (score_above_threshold * SPEED_INCREASE_RATE)
    speed = min(MAX_OBSTACLE_SPEED, speed)
    
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
        
        current = self.get_current_player()
        if current and not current.is_complete:
            return True
        
        start_idx = self.current_player_index
        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            if self.current_player_index == start_idx:
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
        """Create horror-styled text with effects"""
        base_font = pygame.font.Font(None, size)
        base_surf = base_font.render(text, True, color)
        w, h = base_surf.get_size()
        
        effect_surf = pygame.Surface((w + 20, h + 40), pygame.SRCALPHA)
        
        if style == 'dripping':
            effect_surf.blit(base_surf, (10, 10))
            for i in range(0, w, max(1, w // len(text))):
                if random.random() > 0.3:
                    drip_length = random.randint(5, 20)
                    drip_x = i + 10
                    drip_y = h + 10
                    for dy in range(drip_length):
                        alpha = int(255 * (1 - dy / drip_length))
                        drip_color = (*color[:3], alpha)
                        width = max(1, 3 - dy // 7)
                        pygame.draw.circle(effect_surf, drip_color, 
                                         (drip_x, drip_y + dy), width)
        
        elif style == 'jagged':
            offsets = [(0, 0), (-2, -2), (2, 2), (-1, 1), (1, -1)]
            for ox, oy in offsets:
                effect_surf.blit(base_surf, (10 + ox, 10 + oy))
        
        elif style == 'shaky':
            for _ in range(5):
                ox = random.randint(-2, 2)
                oy = random.randint(-2, 2)
                effect_surf.blit(base_surf, (10 + ox, 10 + oy))
        
        elif style == 'cracked':
            effect_surf.blit(base_surf, (10, 10))
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
        """Draw text with optional horror styling"""
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

# ================= ATMOSPHERE CLASSES =================
class FogParticle:
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
        pygame.draw.circle(screen, BLACK, (int(self.x), int(self.y)), self.size // 2 + 2)
        
        left_wing = [(int(self.x - self.size), int(self.y - wing_offset)),
                     (int(self.x - self.size // 2), int(self.y)),
                     (int(self.x), int(self.y + wing_offset))]
        right_wing = [(int(self.x + self.size), int(self.y - wing_offset)),
                      (int(self.x + self.size // 2), int(self.y)),
                      (int(self.x), int(self.y + wing_offset))]
        
        pygame.draw.polygon(screen, BLACK, left_wing, 3)
        pygame.draw.polygon(screen, BLACK, right_wing, 3)
        pygame.draw.circle(screen, (50, 50, 60), (int(self.x), int(self.y)), self.size // 2)
        pygame.draw.polygon(screen, (50, 50, 60), left_wing)
        pygame.draw.polygon(screen, (50, 50, 60), right_wing)

class Ghost:
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
        pygame.draw.circle(ghost_surface, (*BLACK, self.opacity + 80), (30, 30), 27)
        
        points_outline = []
        for i in range(0, 61, 10):
            wave = math.sin((i + self.float_offset * 10) * 0.3) * 3
            points_outline.append((i, 50 + wave))
        points_outline.append((60, 80))
        points_outline.append((0, 80))
        pygame.draw.polygon(ghost_surface, (*BLACK, self.opacity + 80), points_outline, 3)
        
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
            pygame.draw.rect(screen, BLACK, (x - 2, HEIGHT - h - 42, 44, h + 4))
            pygame.draw.ellipse(screen, BLACK, (x - 7, HEIGHT - h - 64, 54, 44))
            pygame.draw.rect(screen, GRAVE_STONE, (x, HEIGHT - h - 40, 40, h))
            pygame.draw.ellipse(screen, GRAVE_STONE, (x - 5, HEIGHT - h - 60, 50, 40))
        
        for i in range(3):
            x = 50 + i * 350
            self.draw_dead_tree(x, HEIGHT - 150)
    
    def draw_dead_tree(self, x, y):
        pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 24, 154))
        pygame.draw.rect(screen, DEAD_TREE, (x, y, 20, 150))
        
        branches = [
            ((x + 10, y + 30), (x - 40, y - 20)),
            ((x + 10, y + 30), (x + 60, y - 10)),
            ((x + 10, y + 70), (x - 30, y + 50)),
            ((x + 10, y + 70), (x + 50, y + 60))
        ]
        for start, end in branches:
            pygame.draw.line(screen, BLACK, start, end, 11)
        for start, end in branches:
            pygame.draw.line(screen, DEAD_TREE, start, end, 8)

class Star:
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

# ================= OBSTACLE BASE =================
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

# ================= ALL OBSTACLE CLASSES =================
# (Keeping your existing obstacle implementations - GravePillarObstacle, SkullTowerObstacle, etc.)
# I'll include just a few to avoid token limits - you can add the others from your original file

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

# (Add more obstacle classes from your original file here...)
# To save space, I'm showing the key ones - you should copy-paste the rest from your original

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
    def __init__(self, use_advanced_audio=True):
        """
        Initialize game with choice of audio processor
        
        Args:
            use_advanced_audio: True for FFT-based (robust), False for simple
        """
        self.session_manager = GameSessionManager()
        self.leaderboard_manager = LeaderboardManager()
        self.difficulty_manager = DifficultyManager()
        self.state = GameState.SPLASH_SCREEN
        self.theme = UITheme()
        
        # Audio processor - CHOOSE YOUR VERSION HERE
        if use_advanced_audio:
            print("[Game] Using ADVANCED audio processor (FFT + frequency filtering)")
            self.audio_processor = AdvancedAudioProcessor(
                samplerate=44100,
                blocksize=2048,
                sensitivity=0.6  # Adjust 0.0-1.0 for sensitivity
            )
        else:
            print("[Game] Using SIMPLIFIED audio processor (FFT only)")
            self.audio_processor = SimplifiedAudioProcessor(
                samplerate=44100,
                blocksize=2048
            )
        
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
        """Spawn obstacles with dynamic difficulty scaling"""
        difficulty_params = calculate_difficulty_params(score_value, self.current_difficulty_config)
        speed = difficulty_params['speed']
        self.current_difficulty_params = difficulty_params
        
        if score_value >= 10:
            obstacle_class = random.choice([GravePillarObstacle, LaserGateObstacle])
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
        if self.logo:
            logo_rect = self.logo.get_rect(center=(WIDTH // 2, 100))
            screen.blit(self.logo, logo_rect)
        
        UITheme.draw_text(screen, "PRESENTS", WIDTH // 2, 220, 48, BLOOD_RED, horror_style='dripping')
        UITheme.draw_text(screen, "SCREAMING FLAPPY", WIDTH // 2, 320, 52, TOXIC_GREEN, horror_style='shaky')
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
        # Start audio processor
        self.audio_processor.start()
        
        try:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        self.audio_processor.stop()
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
                    # Use audio processor instead of raw volume check
                    if self.audio_processor.is_loud():
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
        
        finally:
            self.audio_processor.stop()

# ================= ENTRY =================
def main():
    """
    Initialize and run the game
    
    Change use_advanced_audio parameter to switch between:
    - True: Advanced FFT-based processor (recommended, better noise filtering)
    - False: Simplified FFT-only processor (lighter CPU, but less robust)
    """
    try:
        # CHOOSE YOUR AUDIO PROCESSOR HERE:
        game = NoisyBird(use_advanced_audio=True)
        game.play()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()

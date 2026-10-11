#!/usr/bin/env python3
"""missile.py: Missile Command (Atari, 1980) en un solo archivo de Python.

Núcleo fiel a la recreativa: las reglas y las tablas salen del fuente original
de Atari (rev. 1) y del listado desensamblado de la rev. 3. El README cuenta de
dónde sale cada número. Encima va una capa de mejoras que se apaga con
--classic: brillo y máscara CRT, partículas, humo, temblor de cámara, puntos
flotantes, cadenas, sonido estéreo sintetizado, mando, estadísticas y récords
que sobreviven al cierre.

    pip install pygame-ce
    python missile.py              # jugar
    python missile.py --help       # todas las opciones
    python missile.py --test       # comprobaciones internas, sin pygame
    python missile.py --headless   # partida simulada por el piloto automático

Licencia MIT. Missile Command es una marca de Atari. Esto es un homenaje que no
copia código ni gráficos del original.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import pairwise
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:  # --test y --headless funcionan sin pygame
    pygame = None

__version__ = "1.1.0"

# =============================================================================
# Constantes y tablas del original
# La lógica usa las coordenadas de la recreativa: x de 0 a 255 y la y hacia
# arriba, de 0 (abajo) a 230 (arriba). Solo el render invierte el eje.
# =============================================================================

W, H = 256, 231
Y_MAX = H - 1
FPS = 60
TOP = 222  # TOPSCR: por aquí entran los ICBM
CURSOR_X = (8, 247)  # IHMIN, IHMAX
CURSOR_Y = (45, 206)  # IVMIN, IVMAX
LOWEST = 33  # por debajo, una explosión no daña y un ICBM no puntúa
EXPLOSION_CEILING = 210  # DETONA: no se crean explosiones en y >= 210

ABMS_PER_SILO = 10  # MAXMIS
MAX_ABMS = 8  # NABMS
MAX_INCOMING = 8  # NICBMS: huecos compartidos por ICBM y smart bombs
MAX_EXPLOSIONS = 20  # NEXPLO
MAX_DEFENSE = 16  # MAXDEX: ABM en vuelo más explosiones defensivas
MXICON = 7
LAUNCH_HEIGHT, LAUNCH_LOW = 202, 180  # LAUHGT, LAULOW
MIRV_LO, MIRV_HI = 128, 160  # MIRVLO, MIRVHI
MIRV_MAX_EXPLOSIONS = 12
MAX_SMART_ON_SCREEN = 3
SMART_CLIMB_WAVE = 9  # STUPID: antes de la oleada 9 no esquivan hacia arriba
FIRST_FLIER_WAVE = 2  # SPUTWV
FLIER_FIRE_X = (48, 208)
SIZE_ICBM, SIZE_SMART, SIZE_FLIER = 1, 3, 6  # se suman al radio de la explosión
EXPLOSION_STEPS = 27  # EXDONE
EXPLOSION_GROUPS = 5  # 20 huecos en 5 grupos de 4: un grupo por frame
ABM_STEPS = (3, 7, 3)  # pasos por frame de cada silo

# Escenario de izquierda a derecha (W3COMN; tablas $60e2 y $60eb de la rev. 3)
CITIES = ((44, 18), (71, 17), (95, 16), (148, 18), (180, 21), (208, 17))
SILOS = ((20, 22), (123, 22), (240, 22))
SILO_TOP = 24  # de aquí salen los ABM (MBCPVA)
# Ciudades iniciales según el DIP (STCITY, STCIMA). Con 7, una queda en reserva.
START_CITIES = {
    4: (1, 2, 3, 4),
    5: (0, 1, 2, 3, 4),
    6: (0, 1, 2, 3, 4, 5),
    7: (0, 1, 2, 3, 4, 5),
}
# El recuento retira las ciudades en el orden de su índice interno original
TALLY_ORDER = (2, 4, 3, 0, 1, 5)
# Pirámide de munición sobre cada silo (tabla $6810 de la rev. 3)
ABM_ICONS = (
    (0, 2), (-3, -1), (3, -1), (-6, -4), (0, -4),
    (6, -4), (-3, -7), (3, -7), (-9, -7), (9, -7),
)  # fmt: skip

# Oleadas 1 a 19; de la 20 en adelante se repite la 19 (tablas $6090 y $60c1)
ICBM_COUNT = (
    12,
    15,
    18,
    12,
    16,
    14,
    17,
    10,
    13,
    16,
    19,
    12,
    14,
    16,
    18,
    14,
    17,
    19,
    22,
)
SMART_COUNT = (0, 0, 0, 0, 0, 1, 1, 2, 3, 4, 4, 5, 5, 6, 6, 7, 7, 7, 7)
# Retardo entre pasos de ICBM, en frames y punto fijo 8.8 (WICSPH, WICSPL)
ICBM_DELAY = (
    0x04D0, 0x02E0, 0x01C0, 0x0108, 0x00A0, 0x0060, 0x0040, 0x0020,
    0x0010, 0x000A, 0x0006, 0x0004, 0x0002, 0x0001, 0x0000,
)  # fmt: skip
# Voladores, oleadas 2 a 8; de la 9 en adelante se repite la 8 (WSPLAU, WSPFIR)
FLIER_RECHARGE = (240, 160, 128, 128, 96, 64, 32)  # frames hasta el siguiente
FLIER_FIRE_GAP = (128, 96, 64, 48, 32, 32, 16)  # píxeles recorridos entre disparos
FLIER_MOVE_EVERY = (2, 3)  # satélite: 1 píxel cada 2 frames; bombardero: cada 3
EXPLOSION_RADIUS = (
    0, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0,
)  # fmt: skip
BONUS_CHOICES = (8000, 10000, 12000, 14000, 15000, 18000, 20000)  # BONINL
POINTS_ICBM, POINTS_FLIER, POINTS_SMART = 25, 100, 125
BONUS_ABM, BONUS_CITY = 5, 100

# Sondas de peligro de la smart bomb (tabla $6382): arriba y en sentido antihorario
PROBES = ((0, 8), (-6, 6), (-8, 0), (-6, -6), (0, -8), (6, -6), (8, 0), (6, 6))
# 16 direcciones de esquiva (DEVIVL/DEVIHL): 0 arriba, 4 izquierda, 8 abajo
DEVIATIONS = tuple(
    (-math.sin(d * math.pi / 8), math.cos(d * math.pi / 8)) for d in range(16)
)

COLOR_NAMES = ("white", "yellow", "magenta", "red", "cyan", "green", "blue", "black")
RGB_ARCADE = {
    "white": (255, 255, 255),
    "yellow": (255, 255, 0),
    "magenta": (255, 0, 255),
    "red": (255, 0, 0),
    "cyan": (0, 255, 255),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "black": (0, 0, 0),
}
# Mismos ocho colores, con el tono de un fósforo de tubo (modo mejorado)
RGB_PHOSPHOR = {
    "white": (236, 240, 255),
    "yellow": (255, 226, 64),
    "magenta": (255, 72, 220),
    "red": (255, 58, 48),
    "cyan": (64, 236, 255),
    "green": (72, 255, 112),
    "blue": (70, 110, 255),
    "black": (5, 6, 16),
}
# (fondo, terreno, ICBM, ciudad 1, ABM y ciudad 2); tabla $694e de la rev. 3
WAVE_COLORS = (
    ("black", "yellow", "red", "cyan", "blue"),
    ("black", "yellow", "green", "cyan", "blue"),
    ("black", "blue", "red", "yellow", "green"),
    ("black", "red", "yellow", "yellow", "blue"),
    ("blue", "yellow", "red", "magenta", "black"),
    ("cyan", "yellow", "red", "black", "blue"),
    ("magenta", "green", "black", "black", "yellow"),
    ("yellow", "green", "black", "white", "red"),
    ("white", "red", "magenta", "yellow", "green"),
    ("red", "yellow", "black", "green", "blue"),
)

DEFAULT_SCORES = (
    ("ABM", 7500),
    ("ICB", 7000),
    ("SAT", 6500),
    ("RAD", 6000),
    ("DEF", 5500),
)
AMMO_MODES = ("arcade", "infinite")  # cada modo de munición tiene su tabla de récords
INITIALS_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ "

# =============================================================================
# Tipografía y sprites: diseño propio, no copiado de la ROM
# =============================================================================

# Glifos de 7 x 7 en una celda de 8 x 8, con la fila de arriba y la columna de
# la derecha libres, como en el original. Una línea por carácter. Las mayúsculas
# acentuadas usan 8 filas: la tilde ocupa la fila libre y la letra baja a 6.
_GLYPHS = """
A ..###.. .##.##. ##...## ##...## ####### ##...## ##...##
B ######. ##...## ##...## ######. ##...## ##...## ######.
C ..####. .##..## ##..... ##..... ##..... .##..## ..####.
D #####.. ##..##. ##...## ##...## ##...## ##..##. #####..
E ####### ##..... ##..... ######. ##..... ##..... #######
F ####### ##..... ##..... ######. ##..... ##..... ##.....
G ..##### .##.... ##..... ##..### ##...## .##..## ..#####
H ##...## ##...## ##...## ####### ##...## ##...## ##...##
I .###### ...##.. ...##.. ...##.. ...##.. ...##.. .######
J ....### .....## .....## .....## ##...## ##...## .#####.
K ##...## ##..##. ##.##.. ####... #####.. ##.###. ##..###
L ##..... ##..... ##..... ##..... ##..... ##..... #######
M ##...## ###.### ####### ####### ##.#.## ##...## ##...##
N ##...## ###..## ####.## ####### ##.#### ##..### ##...##
O .#####. ##...## ##...## ##...## ##...## ##...## .#####.
P ######. ##...## ##...## ##...## ######. ##..... ##.....
Q .#####. ##...## ##...## ##...## ##.#### ##..##. .####.#
R ######. ##...## ##...## ##..### #####.. ##.###. ##..###
S .####.. ##..##. ##..... .#####. .....## ##...## .#####.
T .###### ...##.. ...##.. ...##.. ...##.. ...##.. ...##..
U ##...## ##...## ##...## ##...## ##...## ##...## .#####.
V ##...## ##...## ##...## ###.### .#####. ..###.. ...#...
W ##...## ##...## ##.#.## ####### ####### ###.### ##...##
X ##...## ###.### .#####. ..###.. .#####. ###.### ##...##
Y .##..## .##..## .##..## ..####. ...##.. ...##.. ...##..
Z ####### ....### ...###. ..###.. .###... ###.... #######
0 ..###.. .##.##. ##...## ##...## ##...## .##.##. ..###..
1 ...##.. ..###.. ...##.. ...##.. ...##.. ...##.. .######
2 .#####. ##...## .....## ...###. .###... ##..... #######
3 ####### ....##. ...##.. ..####. .....## ##...## .#####.
4 ...###. ..####. .##.##. ##..##. ####### ....##. ....##.
5 ######. ##..... ######. .....## .....## ##...## .#####.
6 ..####. .##.... ##..... ######. ##...## ##...## .#####.
7 ####### ##...## ....##. ...##.. ..##... ..##... ..##...
8 .#####. ##...## ##...## .#####. ##...## ##...## .#####.
9 .#####. ##...## ##...## .###### .....## ....##. .####..
. ....... ....... ....... ....... ....... ..##... ..##...
, ....... ....... ....... ....... ..##... ..##... .##....
: ....... ..##... ..##... ....... ..##... ..##... .......
- ....... ....... ....... .#####. ....... ....... .......
_ ....... ....... ....... ....... ....... ....... #######
! ..##... ..##... ..##... ..##... ..##... ....... ..##...
? .#####. ##...## ....##. ...##.. ...##.. ....... ...##..
/ ......# .....## ....##. ...##.. ..##... .##.... ##.....
+ ....... ...#... ...#... .#####. ...#... ...#... .......
= ....... ....... ####### ....... ####### ....... .......
% ##....# ##...#. ....#.. ...#... ..#.... .#...## #....##
' ..##... ..##... .##.... ....... ....... ....... .......
( ...##.. ..##... .##.... .##.... .##.... ..##... ...##..
) ..##... ...##.. ....##. ....##. ....##. ...##.. ..##...
< ....##. ...##.. ..##... .##.... ..##... ...##.. ....##.
> .##.... ..##... ...##.. ....##. ...##.. ..##... .##....
* ....... ##...## .##.##. ..###.. .##.##. ##...## .......
© .#####. #.....# #..##.# #.#...# #..##.# #.....# .#####.
Á ....##. ....... ..###.. .##.##. ##...## ####### ##...## ##...##
É ....##. ....... ####### ##..... ######. ##..... ##..... #######
Í ....##. ....... .###### ...##.. ...##.. ...##.. ...##.. .######
Ó ....##. ....... .#####. ##...## ##...## ##...## ##...## .#####.
Ú ....##. ....... ##...## ##...## ##...## ##...## ##...## .#####.
Ñ ..####. ....... ##...## ###..## ####.## ##.#### ##..### ##...##
¡ ..##... ....... ..##... ..##... ..##... ..##... ..##...
¿ ...##.. ....... ...##.. ..##... .##.... ##...## .#####.
"""
FONT: dict[str, tuple[str, ...]] = {" ": ("." * 7,) * 7}
for _line in _GLYPHS.strip().splitlines():
    _char, *_rows = _line.split()
    FONT[_char] = tuple(_rows)

# Sprites: "1" y "2" son los dos colores que reciba cada uno; "." es vacío.
CITY_SPRITES = (
    (
        "......2........",
        "......1.....2..",
        "..2..111....1..",
        "..1..121...111.",
        ".111.111.1.121.",
        ".121.121.1.111.",
        "111111111111111",
        "121112111211121",
    ),
    (
        "..........2....",
        "..2.......1....",
        "..1...2..111...",
        ".111..1..121...",
        ".121.111.111.1.",
        ".111.121.121.1.",
        "111111111111111",
        "112111211121111",
    ),
    (
        "....2..........",
        "....1.....2....",
        "...111....1..2.",
        "...121...111.1.",
        ".1.111.1.121111",
        ".1.121.1.111121",
        "111111111111111",
        "211121112111211",
    ),
)
ABM_ICON = (".1.", ".1.", "1.1")
SMART_SPRITE = ("..1..", ".121.", "12221", ".121.", "..1..")
BOMBER_SPRITE = (
    "....1......",
    "....11.....",
    "1...111....",
    "11111111112",
    "1...111....",
    "....11.....",
    "....1......",
)
SATELLITE_SPRITE = (
    "111.....111",
    "111..1..111",
    "11111211111",
    "111..1..111",
    "111.....111",
)
ARROW_SPRITE = ("..1..", "..1..", "1.1.1", ".111.", "..1..")
X_MARK = ("1...1", ".1.1.", "..1..", ".1.1.", "1...1")


# =============================================================================
# Utilidades puras
# =============================================================================


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def wave_row(wave: int) -> int:
    """Fila de las tablas de oleada: de la 19 en adelante, la última."""
    return min(wave, len(ICBM_COUNT)) - 1


def multiplier(wave: int) -> int:
    return min((wave + 1) // 2, 6)


def icbm_delay(wave: int) -> int:
    return ICBM_DELAY[min(wave, len(ICBM_DELAY)) - 1]


def flier_row(wave: int) -> int:
    return min(wave, 8) - FIRST_FLIER_WAVE


def wave_colors(wave: int) -> tuple[str, str, str, str, str]:
    return WAVE_COLORS[((wave - 1) // 2) % len(WAVE_COLORS)]


def approx_dist(dx: float, dy: float) -> float:
    """Distancia del original: el mayor más 3/8 del menor."""
    a, b = abs(dx), abs(dy)
    return max(a, b) + 0.375 * min(a, b)


def octagon_hit(dx: int, dy: int, reach: int) -> bool:
    """Colisión de DELTA (W3MAIN), en aritmética entera como la ROM."""
    dx, dy = abs(dx), abs(dy)
    if dx >= reach or dy >= reach:
        return False
    j, k = (dx, dy) if dx < dy else (dy, dx)
    return k + ((j + (j >> 1)) >> 2) < reach


def octagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Vértices del octógono de radio r: la curva de nivel de octagon_hit."""
    d = r * 8 / 11
    return [
        (cx + r, cy),
        (cx + d, cy + d),
        (cx, cy + r),
        (cx - d, cy + d),
        (cx - r, cy),
        (cx - d, cy - d),
        (cx, cy - r),
        (cx + d, cy - d),
    ]


def angle16(dx: float, dy: float) -> int:
    """Dirección de 0 a 15 hacia (dx, dy): 0 arriba, en sentido antihorario."""
    return round(math.atan2(-dx, dy) / (math.pi / 8)) % 16


def opening_mask(a: int, big: bool) -> int:
    """Sondas que deben estar libres para salir en la dirección a (BIGHOL, SMAHOL)."""
    i = a // 2
    if not big:
        return 1 << i
    span = (i - 1, i, i + 1, i + 2) if a % 2 else (i - 1, i, i + 1)
    mask = 0
    for p in span:
        mask |= 1 << (p % 8)
    return mask


def find_opening(want: int, danger: int) -> int | None:
    """Primero un hueco grande cerca del rumbo deseado; si no, uno pequeño."""
    offsets = [0]
    for n in range(1, 9):
        offsets += [n, -n]
    for big in (True, False):
        for off in offsets:
            a = (want + off) % 16
            if not big and a % 2:
                continue
            if not danger & opening_mask(a, big):
                return a
    return None


def build_terrain() -> tuple[int, ...]:
    """Altura del suelo en cada columna: llanura, montículos de silo y peanas."""
    heights = []
    for x in range(W):
        h = 10
        for sx, sy in SILOS:
            h = max(h, sy - max(0, abs(x - sx) - 8))
        for cx, cy in CITIES:
            h = max(h, cy - 5 - max(0, abs(x - cx) - 8))
        heights.append(h)
    return tuple(heights)


TERRAIN = build_terrain()


def clean_table(rows) -> list[tuple[str, int]]:
    """Cinco récords ordenados; si no hay datos válidos, los de fábrica."""
    try:
        table = [(str(n)[:3].upper(), int(s)) for n, s in rows or ()]
    except (TypeError, ValueError):
        table = []
    return sorted(table or DEFAULT_SCORES, key=lambda e: -e[1])[:5]


def icbm_clock(clock: int, delay: int) -> tuple[int, bool]:
    """Temporizador 8.8 de UPICBM: devuelve el nuevo reloj y si los ICBM avanzan."""
    if clock >= 0x100:
        return clock - 0x100, False
    return (clock + delay) & 0xFFFF, True


# =============================================================================
# Entidades
# =============================================================================

ABM, ICBM, SMART = 0, 1, 2
SATELLITE, BOMBER = 0, 1
KILL_ICBM, KILL_SMART, KILL_FLIER = 1, 2, 3


@dataclass(slots=True)
class Missile:
    """ABM, ICBM o smart bomb. Avanza en línea recta, una unidad por paso."""

    kind: int
    x: float
    y: float
    tx: float
    ty: float
    ox: float = 0.0  # inicio de la estela
    oy: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    silo: int = -1  # ABM: silo de origen
    target: int = -1  # ataque: 0-5 ciudad, 6-8 silo
    serial: int = 0  # orden de aparición
    chain: int = 0  # ABM: cadena que inicia su explosión

    def aim(self) -> None:
        """GENVEL: rumbo al objetivo con la distancia aproximada, topada en 255."""
        dx, dy = self.tx - self.x, self.ty - self.y
        d = min(approx_dist(dx, dy), 255.0)
        if d < 1e-9:
            self.vx = self.vy = 0.0
        else:
            self.vx, self.vy = dx / d, dy / d

    def step(self) -> bool:
        """UPDPOS: avanza un paso y dice si ya ha rebasado el objetivo."""
        self.x += self.vx
        self.y += self.vy
        vx, vy = self.vx, self.vy
        if vx == 0 and vy == 0:
            return True
        return (
            (vx > 0 and self.x >= self.tx)
            or (vx < 0 and self.x <= self.tx)
            or (vy > 0 and self.y >= self.ty)
            or (vy < 0 and self.y <= self.ty)
        )


@dataclass(slots=True)
class Explosion:
    x: int
    y: int
    offensive: bool
    chain: int = 0
    step: int = 0
    updated: int = 0  # frame de la última actualización, para el dibujo suave

    @property
    def radius(self) -> int:
        return EXPLOSION_RADIUS[self.step + 1] if self.step else 0

    @property
    def previous_radius(self) -> int:
        return EXPLOSION_RADIUS[self.step] if self.step else 0


@dataclass(slots=True)
class Flier:
    kind: int  # SATELLITE o BOMBER
    x: int
    y: int
    direction: int  # +1 derecha, -1 izquierda
    move_ctr: int = 0
    fire_ctr: int = 0  # píxeles recorridos desde el último disparo


@dataclass(slots=True)
class City:
    x: int
    y: int
    alive: bool = True
    targeted: bool = False


@dataclass(slots=True)
class Silo:
    x: int
    y: int
    abms: int = ABMS_PER_SILO
    alive: bool = True
    targeted: bool = False


@dataclass(slots=True)
class Inputs:
    """Lo que el jugador (o el piloto automático) pide en un frame."""

    dx: float = 0.0
    dy: float = 0.0
    abs_xy: tuple[float, float] | None = None
    fire: tuple[bool, bool, bool] = (False, False, False)
    start: bool = False
    start2: bool = False  # partida a dos jugadores
    nav: int = 0  # cambiar de letra en las iniciales
    spin: float = 0.0  # giro vertical del trackball, también para las iniciales
    letter: str = ""
    back: bool = False


@dataclass(slots=True)
class FX:
    """Suceso para el sonido y los efectos; la lógica no sabe quién lo escucha."""

    name: str
    x: float = 0.0
    y: float = 0.0
    a: int = 0
    b: int = 0
    c: int = 0


@dataclass(slots=True)
class Stats:
    shots: int = 0
    icbms: int = 0
    smarts: int = 0
    fliers: int = 0
    best_chain: int = 0
    cities_lost: int = 0
    silos_lost: int = 0
    bonus_cities: int = 0
    waves: int = 0
    mirvs: int = 0
    frames: int = 0

    @property
    def kills(self) -> int:
        return self.icbms + self.smarts + self.fliers


@dataclass(slots=True)
class Tally:
    """Recuento de fin de oleada (ENDWV1 a ENDWV5)."""

    abms: int = 0
    abm_points: int = 0
    cities: list[int] = field(default_factory=list)
    city_points: int = 0
    stage: int = 0
    wait: int = 20


@dataclass(slots=True)
class Player:
    """Lo que cada jugador conserva entre turnos en la partida a dos."""

    score: int = 0
    wave: int = 1
    alive: tuple[bool, ...] = ()
    reserve: int = 0
    bonus_level: int = 0
    stats: Stats = field(default_factory=Stats)
    out: bool = False


class Phase(Enum):
    TITLE = auto()
    DEMO = auto()
    SCORES = auto()
    INTRO = auto()
    PLAY = auto()
    TALLY = auto()
    REGEN = auto()
    PLAYER_OUT = auto()
    THE_END = auto()
    STATS = auto()
    INITIALS = auto()


INTRO_FRAMES = 2 * FPS
REGEN_FRAMES = 3 * FPS
THE_END_FRAMES = 5 * FPS
TITLE_FRAMES = 540
DEMO_FRAMES = 40 * FPS
SCORES_FRAMES = 7 * FPS
STATS_FRAMES = 25 * FPS
INITIALS_FRAMES = 60 * FPS


# =============================================================================
# Lógica de juego
# =============================================================================


class Game:
    """Todo el estado de la partida. No toca pygame, así que se puede simular."""

    def __init__(
        self,
        seed: int | None = None,
        cities: int = 6,
        bonus: int = 10000,
        start_wave: int = 1,
        scores: dict | list | None = None,
        stats_screen: bool = True,
        infinite_ammo: bool = False,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.cosmetic = random.Random()
        self.n_cities = cities if cities in START_CITIES else 6
        self.bonus_every = max(0, bonus)
        self.start_wave = max(1, start_wave)
        self.stats_screen = stats_screen
        source = scores if isinstance(scores, dict) else {"arcade": scores}
        self.tables = {mode: clean_table(source.get(mode)) for mode in AMMO_MODES}
        self.infinite = infinite_ammo
        self.high_scores = self.tables[self.ammo_mode]
        self.scores_changed = False
        self.new_rank = -1
        self.fx: list[FX] = []
        self.frame = 0
        self.timer = 0
        self.phase = Phase.TITLE
        self.attract = True
        self.serial = 0
        self.chain_seq = 0
        self.chains: dict[int, int] = {}
        self.cursor = [128.0, 128.0]
        self.pilot = Autopilot()
        self.title_booms: list[tuple[int, int, int]] = []
        self.tally: Tally | None = None
        self.regen_cities: list[int] = []
        self.entry = [0, 0, 0]
        self.entry_pos = 0
        self.entry_spin = 0.0
        self.entry_player = 0
        self.entry_queue: list[int] | None = None
        self.players: list[Player] = []
        self.n_players = 1
        self.current = 0
        self.next_player = 0
        self.stats_index = 0
        self._reset_player()
        self._start_title()

    # --- arranque y fases -----------------------------------------------------

    @property
    def ammo_mode(self) -> str:
        return "infinite" if self.infinite else "arcade"

    def set_infinite(self, on: bool) -> None:
        """Munición infinita o la del original; cada modo con su tabla de récords."""
        self.infinite = on
        self.high_scores = self.tables[self.ammo_mode]
        self.new_rank = -1

    def _reset_player(self) -> None:
        self.score = 0
        self.wave = self.start_wave
        alive = START_CITIES[self.n_cities]
        self.cities = [City(x, y, i in alive) for i, (x, y) in enumerate(CITIES)]
        self.reserve = 1 if self.n_cities == 7 else 0
        self.bonus_level = 0
        self.silos = [Silo(x, y) for x, y in SILOS]
        self.stats = Stats()
        self._clear_field()

    def _clear_field(self) -> None:
        self.abms: list[Missile] = []
        self.incoming: list[Missile | None] = [None] * MAX_INCOMING
        self.explosions: list[Explosion | None] = [None] * MAX_EXPLOSIONS
        self.exp_ptr = MAX_EXPLOSIONS - 1
        self.exp_group = 0
        self.flier: Flier | None = None
        self.mirv: int | None = None
        self.hiicbv = 0
        self.icb_clock = 0
        self.delay = icbm_delay(self.wave)
        self.speed_off = False
        self.icbm_left = 0
        self.smart_left = 0
        self.cities_down = 0
        self.flier_charge = 0
        self.chains.clear()

    def _set_phase(self, phase: Phase) -> None:
        self.phase = phase
        self.timer = 0

    def start_game(self, players: int = 1) -> None:
        if self.seed is not None:
            self.rng.seed(self.seed)
        self.attract = False
        self.n_players = 2 if players == 2 else 1
        self._reset_player()
        self.players = [self._snapshot() for _ in range(self.n_players)]
        for p in self.players:
            p.stats = Stats()
        self.current = 0
        self.stats = self.players[0].stats
        self.entry_queue = None
        self.cursor = [128.0, 128.0]
        self.fx.append(FX("start", a=self.n_players))
        self._begin_wave()

    def _snapshot(self) -> Player:
        alive = tuple(c.alive for c in self.cities)
        return Player(
            self.score, self.wave, alive, self.reserve, self.bonus_level, self.stats
        )

    def _store_player(self, out: bool = False) -> None:
        p = self.players[self.current]
        p.score, p.wave, p.reserve = self.score, self.wave, self.reserve
        p.bonus_level, p.stats = self.bonus_level, self.stats
        p.alive = tuple(c.alive for c in self.cities)
        p.out = p.out or out

    def _load_player(self, i: int) -> None:
        self.current = i
        p = self.players[i]
        self.score, self.wave, self.reserve = p.score, p.wave, p.reserve
        self.bonus_level, self.stats = p.bonus_level, p.stats
        for c, alive in zip(self.cities, p.alive):
            c.alive = alive

    def _next_player(self) -> int | None:
        for k in range(1, self.n_players + 1):
            i = (self.current + k) % self.n_players
            if not self.players[i].out:
                return i
        return None

    def player_scores(self) -> list[int]:
        """Puntuación de cada jugador; la del que juega, en vivo."""
        if not self.players:
            return [self.score]
        scores = [p.score for p in self.players]
        if not self.attract:
            scores[self.current] = self.score
        return scores

    def _begin_wave(self) -> None:
        """NEWWV1: silos recargados, contadores a cero y tablas de la oleada."""
        self._clear_field()
        row = wave_row(self.wave)
        self.icbm_left = ICBM_COUNT[row]
        self.smart_left = SMART_COUNT[row]
        if self.wave >= FIRST_FLIER_WAVE:
            self.flier_charge = FLIER_RECHARGE[flier_row(self.wave)]
        for s in self.silos:
            s.abms, s.alive, s.targeted = ABMS_PER_SILO, True, False
        for c in self.cities:
            c.targeted = False
        self.tally = None
        self._set_phase(Phase.DEMO if self.attract else Phase.INTRO)
        if not self.attract:
            self.fx.append(FX("wave", a=self.wave))

    def _start_title(self) -> None:
        self.attract = True
        self._clear_field()
        self._set_phase(Phase.TITLE)
        r = (
            self.cosmetic
        )  # un bombardeo que barre las dos palabras de izquierda a derecha
        self.title_booms = sorted(
            (
                110 + i * 16 + row * 8 + r.randrange(3),
                30 + i * 12 + r.randrange(-1, 2),
                y + (5 if (i + row) % 2 else -5),
            )
            for i in range(18)
            for row, y in enumerate((147, 99))
        )

    def _start_demo(self) -> None:
        self.attract = True
        self.wave = 1
        self.cities = [City(x, y) for x, y in CITIES]
        self.silos = [Silo(x, y) for x, y in SILOS]
        self.reserve = 0
        self.pilot = Autopilot()
        self.cursor = [128.0, 128.0]
        self._begin_wave()

    def _start_scores(self) -> None:
        self.attract = True
        self._clear_field()
        self._set_phase(Phase.SCORES)

    # --- un frame -------------------------------------------------------------

    def step(self, inp: Inputs) -> None:
        self.frame += 1
        self.timer += 1
        phase = self.phase
        if phase is Phase.PLAY:
            self._play(inp)
            self.stats.frames += 1
        elif phase is Phase.INTRO:
            self._move_cursor(inp)
            if self.timer >= INTRO_FRAMES:
                self._set_phase(Phase.PLAY)
        elif phase is Phase.TALLY:
            self._tally_frame()
        elif phase is Phase.REGEN:
            if self.timer >= REGEN_FRAMES:
                self._after_regen()
        elif phase is Phase.PLAYER_OUT:
            if self.timer >= REGEN_FRAMES:
                self._load_player(self.next_player)
                self._begin_wave()
        elif phase is Phase.THE_END:
            if self.timer >= THE_END_FRAMES:
                self.stats_index = 0
                if self.stats_screen:
                    self._set_phase(Phase.STATS)
                else:
                    self._check_high_score()
        elif phase is Phase.STATS:
            pressed = inp.start or any(inp.fire)
            if (pressed and self.timer > FPS) or self.timer >= STATS_FRAMES:
                self.stats_index += 1
                if self.stats_index < len(self.players):
                    self._set_phase(Phase.STATS)
                else:
                    self._check_high_score()
        elif phase is Phase.INITIALS:
            self._initials_frame(inp)
        elif phase is Phase.TITLE:
            self._title_frame(inp)
        elif phase is Phase.DEMO:
            if inp.start or inp.start2:
                self.start_game(2 if inp.start2 else 1)
                return
            self._play(self.pilot.inputs(self))
            if self.phase is Phase.DEMO and self.timer >= DEMO_FRAMES:
                self._start_scores()
        elif phase is Phase.SCORES:
            if inp.start or inp.start2:
                self.start_game(2 if inp.start2 else 1)
            elif self.timer >= SCORES_FRAMES:
                self._start_title()

    def _title_frame(self, inp: Inputs) -> None:
        if inp.start or inp.start2:
            self.start_game(2 if inp.start2 else 1)
            return
        while self.title_booms and self.title_booms[0][0] <= self.timer:
            _, x, y = self.title_booms.pop(0)
            self._detonate(x, y, False, 0)
        self._update_explosions()
        if self.timer >= TITLE_FRAMES:
            self._start_demo()

    def _play(self, inp: Inputs) -> None:
        self._move_cursor(inp)
        self._fire(inp.fire)
        self._update_abms()
        self._update_incoming()
        self._update_flier()
        self._update_explosions()
        self._launch()
        self._check_alive()

    # --- defensa --------------------------------------------------------------

    def _move_cursor(self, inp: Inputs) -> None:
        if inp.abs_xy is not None:
            x, y = inp.abs_xy
        else:
            x, y = self.cursor[0] + inp.dx, self.cursor[1] + inp.dy
        self.cursor[0] = clamp(x, *CURSOR_X)
        self.cursor[1] = clamp(y, *CURSOR_Y)

    def threats(self) -> bool:
        """¿Queda algo a lo que disparar?"""
        if self.icbm_left or self.smart_left or self.flier is not None:
            return True
        return any(m is not None for m in self.incoming)

    @property
    def cursor_visible(self) -> bool:
        if self.phase is Phase.INTRO:
            return True
        if self.phase not in (Phase.PLAY, Phase.DEMO) or self.speed_off:
            return False
        return self.threats()

    def _incoming_counts(self) -> tuple[int, int]:
        icbms = smarts = 0
        for m in self.incoming:
            if m is not None:
                if m.kind == SMART:
                    smarts += 1
                else:
                    icbms += 1
        return icbms, smarts

    def _explosion_counts(self) -> tuple[int, int]:
        defensive = offensive = 0
        for e in self.explosions:
            if e is not None:
                if e.offensive:
                    offensive += 1
                else:
                    defensive += 1
        return defensive, offensive

    def explosion_total(self) -> int:
        return sum(1 for e in self.explosions if e is not None)

    def _fire(self, pressed: tuple[bool, bool, bool]) -> None:
        """ABMLAU: un disparo por pulsación, si hay sitio en pantalla y munición."""
        if not any(pressed) or not self.threats():
            return
        icbms, smarts = self._incoming_counts()
        defensive, offensive = self._explosion_counts()
        busy = defensive + len(self.abms)
        flier = 1 if self.flier is not None else 0
        room = busy < MAX_DEFENSE and (
            busy + icbms + smarts + flier + offensive < MAX_EXPLOSIONS
        )
        for i in (2, 1, 0):
            if not pressed[i]:
                continue
            silo = self.silos[i]
            if room and silo.abms > 0:
                if len(self.abms) < MAX_ABMS:
                    self._launch_abm(i)
            else:
                self.fx.append(FX("no_fire", silo.x, SILO_TOP))

    def _launch_abm(self, i: int) -> None:
        silo = self.silos[i]
        self.chain_seq += 1
        self.serial += 1
        tx, ty = float(round(self.cursor[0])), float(round(self.cursor[1]))
        m = Missile(ABM, float(silo.x), float(SILO_TOP), tx, ty, silo.x, SILO_TOP)
        m.silo, m.serial, m.chain = i, self.serial, self.chain_seq
        m.aim()
        self.abms.append(m)
        if not self.infinite:
            silo.abms -= 1
        if not self.attract:
            self.stats.shots += 1
        low = silo.abms == 3 and not self.infinite
        self.fx.append(FX("low" if low else "abm", silo.x, SILO_TOP, silo.abms))

    def _update_abms(self) -> None:
        """UPABMS: 3 pasos por frame en los laterales, 7 en el central."""
        for m in list(self.abms):
            for _ in range(ABM_STEPS[m.silo]):
                if m.step():
                    self.abms.remove(m)
                    self._detonate(m.x, m.y, False, m.chain)
                    break

    def _detonate(self, x: float, y: float, offensive: bool, chain: int) -> None:
        """DETONA: ocupa el siguiente hueco de explosión, aunque esté en uso."""
        ix, iy = int(x), int(y)
        if iy >= EXPLOSION_CEILING:
            return
        slot = self.exp_ptr
        self.exp_ptr = (slot - 1) % MAX_EXPLOSIONS
        self.explosions[slot] = Explosion(ix, iy, offensive, chain, 0, self.frame)
        self.fx.append(FX("boom", ix, iy, int(offensive), chain))

    # --- ataque ---------------------------------------------------------------

    def _update_incoming(self) -> None:
        """UPICBM: los ataques avanzan al ritmo del retardo 8.8 de la oleada."""
        delay = 0 if self.speed_off else self.delay
        self.icb_clock, moving = icbm_clock(self.icb_clock, delay)
        if not moving:
            return
        self.mirv = None
        highest = 0
        for i in range(MAX_INCOMING - 1, -1, -1):
            m = self.incoming[i]
            if m is None:
                continue
            height = int(m.y)
            highest = max(highest, height)
            if m.kind == SMART:
                arrived = self._move_smart(m)
            else:
                if not self.attract and MIRV_LO <= height < MIRV_HI:
                    self.mirv = i
                arrived = m.step()
            if arrived:
                self.incoming[i] = None
                if self.mirv == i:
                    self.mirv = None
                self._detonate(m.x, m.y, True, 0)
                self._impact(m.target)
        self.hiicbv = highest
        if self.explosion_total() >= MIRV_MAX_EXPLOSIONS:
            self.mirv = None

    def _impact(self, t: int) -> None:
        """DESTROY: el ataque llega a su objetivo."""
        if t >= 6:
            s = self.silos[t - 6]
            s.targeted = False
            s.abms = 0
            if s.alive:
                s.alive = False
                if not self.attract:
                    self.stats.silos_lost += 1
                self.fx.append(FX("silo", s.x, s.y, t - 6))
        else:
            c = self.cities[t]
            c.targeted = False
            if c.alive:
                c.alive = False
                self.cities_down += 1
                if not self.attract:
                    self.stats.cities_lost += 1
                self.fx.append(FX("city", c.x, c.y, t))

    def _move_smart(self, bomb: Missile) -> bool:
        """CMNEWP: como un ICBM, salvo que haya peligro cerca; entonces esquiva."""
        danger = self._danger_bits(bomb)
        if danger in (0, 0xFF):
            return bomb.step()
        want = angle16(bomb.tx - bomb.x, bomb.ty - bomb.y)
        if self.wave < SMART_CLIMB_WAVE:
            danger |= 1  # finge peligro arriba para que no suba
        d = find_opening(want, danger)
        if d is None:
            return bomb.step()
        dx, dy = DEVIATIONS[d]
        nx, ny = bomb.x + dx, bomb.y + dy
        if 0 <= nx <= W - 1 and 0 < ny <= TOP:
            bomb.x, bomb.y = nx, ny
            bomb.aim()
            return False
        return bomb.step()

    def _danger_bits(self, bomb: Missile) -> int:
        """ANDANG: qué sondas caen sobre algo que parpadea."""
        bx, by = int(bomb.x), int(bomb.y)
        hot = [(e.x, e.y, e.radius + 1) for e in self.explosions if e and e.radius]
        marks = [(int(a.tx), int(a.ty)) for a in self.abms]
        heads = {(int(a.x), int(a.y)) for a in self.abms}
        heads.update((int(m.x), int(m.y)) for m in self.incoming if m and m is not bomb)
        bits = 0
        for i, (ox, oy) in enumerate(PROBES):
            px, py = bx + ox, by + oy
            if (
                (px, py) in heads
                or any(abs(px - mx) <= 2 and abs(py - my) <= 2 for mx, my in marks)
                or any(octagon_hit(px - ex, py - ey, r) for ex, ey, r in hot)
            ):
                bits |= 1 << i
        return bits

    def _update_flier(self) -> None:
        """UpdateFlier: recarga, movimiento y salida por el otro lado."""
        self.flier_charge = min(self.flier_charge + 1, 255)
        f = self.flier
        if f is None:
            return
        f.move_ctr -= 1
        if f.move_ctr < 0 or self.speed_off:
            f.fire_ctr += 1
            f.move_ctr = FLIER_MOVE_EVERY[f.kind] - 1
            f.x += f.direction
            if not 0 <= f.x <= W - 1:
                self.flier = None
                self.flier_charge = 0

    def _update_explosions(self) -> None:
        """PREXPL: un grupo de 4 huecos por frame, así que cada uno cada 5 frames."""
        self.exp_group -= 1
        if self.exp_group < 0:
            self.exp_group = EXPLOSION_GROUPS - 1
        base = self.exp_group * 4
        for slot in range(base + 3, base - 1, -1):
            e = self.explosions[slot]
            if e is None:
                continue
            e.step += 1
            e.updated = self.frame
            if e.step >= EXPLOSION_STEPS:
                self.explosions[slot] = None
                continue
            self._damage(e)

    def _damage(self, e: Explosion) -> None:
        """DAMAGE: solo sufren los atacantes; los ABM atraviesan las explosiones."""
        if e.y < LOWEST:
            return
        r = e.radius
        f = self.flier
        if f is not None and octagon_hit(f.x - e.x, f.y - e.y, r + SIZE_FLIER):
            self._kill_flier(e)
        for i in range(MAX_INCOMING - 1, -1, -1):
            m = self.incoming[i]
            if m is None:
                continue
            size = SIZE_SMART if m.kind == SMART else SIZE_ICBM
            if octagon_hit(int(m.x) - e.x, int(m.y) - e.y, r + size):
                self._kill_incoming(i, e)

    def _kill_incoming(self, i: int, e: Explosion) -> None:
        m = self.incoming[i]
        self.incoming[i] = None
        if self.mirv == i:
            self.mirv = None
        self._release_target(m.target)
        if m.kind == SMART:
            points, kind = POINTS_SMART, KILL_SMART
            if not self.attract:
                self.stats.smarts += 1
        else:
            kind = KILL_ICBM
            points = POINTS_ICBM if int(m.y) >= LOWEST else 0
            if not self.attract:
                self.stats.icbms += 1
        self._award(points, m.x, m.y, kind, e.chain)
        self._detonate(m.x, m.y, True, e.chain)

    def _kill_flier(self, e: Explosion) -> None:
        f = self.flier
        self.flier = None
        self.flier_charge = 0
        if not self.attract:
            self.stats.fliers += 1
        self._award(POINTS_FLIER, f.x, f.y, KILL_FLIER, e.chain)
        self._detonate(f.x, f.y, True, e.chain)

    def _award(self, points: int, x: float, y: float, kind: int, chain: int) -> None:
        total = points * multiplier(self.wave)
        length = 0
        if chain:
            length = self.chains.get(chain, 0) + 1
            self.chains[chain] = length
        if not self.attract:
            self.score += total
            self.stats.best_chain = max(self.stats.best_chain, length)
        self.fx.append(FX("kill", x, y, total, length, kind))

    # --- objetivos y lanzamientos ---------------------------------------------

    def _set_targeted(self, t: int, value: bool) -> None:
        if t >= 6:
            self.silos[t - 6].targeted = value
        else:
            self.cities[t].targeted = value

    def _release_target(self, t: int) -> None:
        """DETARG: libera el objetivo si ningún otro ataque apunta a él."""
        if not any(m is not None and m.target == t for m in self.incoming):
            self._set_targeted(t, False)

    def _target_xy(self, t: int) -> tuple[float, float]:
        obj = self.silos[t - 6] if t >= 6 else self.cities[t]
        return float(obj.x), float(obj.y)

    def _pick_target(self) -> int:
        """GUICBM: nunca más de 3 ciudades caídas o apuntadas por oleada."""
        rng = self.rng
        free_cities = [
            i for i, c in enumerate(self.cities) if c.alive and not c.targeted
        ]
        free_silos = [j for j, s in enumerate(self.silos) if s.alive and not s.targeted]
        aimed = sum(1 for c in self.cities if c.alive and c.targeted)
        if self.cities_down + aimed < 3:
            if free_cities:
                t = rng.choice(free_cities)
            elif free_silos:
                t = 6 + rng.choice(free_silos)
            else:
                t = rng.randrange(9)  # ANYTHG
        elif free_silos:
            t = 6 + rng.choice(free_silos)
        else:  # NOTLCI: cualquier ciudad salvo una viva sin apuntar, o dos silos
            options = [
                i for i, c in enumerate(self.cities) if not c.alive or c.targeted
            ]
            t = rng.choice(options + [6, 7])
        self._set_targeted(t, True)
        return t

    def _open_slot(self) -> int | None:
        for i in range(MAX_INCOMING - 1, -1, -1):
            if self.incoming[i] is None:
                return i
        return None

    def _spawn(self, kind: int, slot: int, x: float, y: float) -> None:
        t = self._pick_target()
        tx, ty = self._target_xy(t)
        self.serial += 1
        m = Missile(kind, float(x), float(y), tx, ty, float(x), float(y))
        m.target, m.serial = t, self.serial
        m.aim()
        self.incoming[slot] = m
        if kind == SMART:
            self.smart_left -= 1
        else:
            self.icbm_left -= 1

    def _launch(self) -> None:
        """ICBLAU: cuántos ataques nuevos caben en este frame, y de qué tipo."""
        if not (self.icbm_left or self.smart_left):
            return
        if max(LAUNCH_HEIGHT - 2 * self.wave, LAUNCH_LOW) < self.hiicbv:
            return
        icbms, smarts = self._incoming_counts()
        defensive, offensive = self._explosion_counts()
        flier = 1 if self.flier is not None else 0
        potent = MXICON - offensive - icbms - smarts - flier
        if potent < 0:
            return
        room = potent + (MAX_EXPLOSIONS - MXICON - 1) - defensive - len(self.abms)
        if room < 0:
            return
        potent = self._maybe_create_flier(min(potent, room))
        if potent < 0:
            return
        if not self.smart_left or smarts >= MAX_SMART_ON_SCREEN:
            self._icnorm(potent)
        elif smarts + icbms < 5:
            if not self.icbm_left or self.rng.randrange(4) == 0:
                self._launch_top(SMART)
            else:
                self._icnorm(potent)

    def _maybe_create_flier(self, potent: int) -> int:
        """ACTPLA: un bombardero o un satélite, si la oleada y la recarga lo permiten."""
        if not self.icbm_left or self.flier is not None or self.wave < FIRST_FLIER_WAVE:
            return potent
        if self.flier_charge < FLIER_RECHARGE[flier_row(self.wave)]:
            return potent
        rng = self.rng
        direction = 1 if rng.randrange(2) else -1
        kind = rng.randrange(2)
        y = 100 + rng.randrange(33)
        if self.wave < 6:
            y += 32
        if self.wave < 4:
            y += 16
        self.flier = Flier(kind, 0 if direction > 0 else W - 1, y, direction)
        self.fx.append(FX("flier_on", self.flier.x, y, kind))
        return potent - 1

    def _icnorm(self, potent: int) -> None:
        """ICNORM: hasta 4 ICBM, desde el volador, un MIRV o lo alto."""
        launches = 0
        if self.icbm_left:
            icbms, smarts = self._incoming_counts()
            free = MXICON - 2 * smarts - icbms - (1 if self.flier is not None else 0)
            if free >= 0:
                launches = min(free + 1, 4, self.icbm_left, potent + 1)
        if launches <= 0:
            return
        f = self.flier
        if (
            f is not None
            and f.fire_ctr >= FLIER_FIRE_GAP[flier_row(self.wave)]
            and FLIER_FIRE_X[0] <= f.x < FLIER_FIRE_X[1]
        ):
            f.fire_ctr = 0
            self._split(
                f.x + (4 if f.direction > 0 else -4), f.y, launches, "flier_fire"
            )
        elif self.mirv is not None and self.incoming[self.mirv] is not None:
            m = self.incoming[self.mirv]
            self._split(m.x, m.y, launches, "mirv")
        else:
            for _ in range(launches):
                self._launch_top(ICBM)

    def _split(self, x: float, y: float, launches: int, source: str) -> None:
        """MIRVER: hasta 3 cabezas nuevas desde un punto, cada una a su objetivo."""
        made = 0
        for _ in range(min(launches, 3)):
            slot = self._open_slot()
            if slot is None or not self.icbm_left:
                break
            self._spawn(ICBM, slot, x, y)
            made += 1
        if made:
            if source == "mirv" and not self.attract:
                self.stats.mirvs += 1
            self.fx.append(FX(source, x, y, made))

    def _launch_top(self, kind: int) -> None:
        """LAUICB: entra por arriba, en una columna que no use otro ataque."""
        slot = self._open_slot()
        if slot is None:
            return
        used = {int(m.ox) for m in self.incoming if m is not None}
        x = self.rng.randrange(W)
        while x in used:
            x = self.rng.randrange(W)
        self._spawn(kind, slot, x, TOP)
        self.hiicbv = 0xFF
        if kind == SMART:
            self.fx.append(FX("smart_on", x, TOP))

    # --- final de oleada y de partida -------------------------------------------

    def _check_alive(self) -> None:
        """TALIVE: fin de oleada, y aceleración final cuando ya no hay defensa."""
        abms_left = sum(s.abms for s in self.silos)
        explosions = self.explosion_total()
        if abms_left == 0 and (
            self.cities_down >= 3 or not any(c.alive for c in self.cities)
        ):
            self.icbm_left = self.smart_left = 0
            if self.flier is None and not self.abms and not explosions:
                self._end_wave()
                return
        if abms_left == 0 and not self.abms and not explosions:
            self.speed_off = True
        if self.speed_off:
            self.icb_clock = 0
        if not (self.threats() or self.abms or explosions):
            self._end_wave()

    def _end_wave(self) -> None:
        self.incoming = [None] * MAX_INCOMING
        self.abms.clear()
        self.flier = None
        self.explosions = [None] * MAX_EXPLOSIONS
        self.fx.append(FX("wave_end"))
        if self.attract:
            self._start_scores()
            return
        self.tally = Tally()
        self._set_phase(Phase.TALLY)

    def _tally_frame(self) -> None:
        """ENDWV2 a ENDWV4: un ABM cada 6 frames y luego ciudad a ciudad."""
        t = self.tally
        if t.wait > 0:
            t.wait -= 1
            return
        mult = multiplier(self.wave)
        if t.stage == 0:
            for s in reversed(self.silos):
                if (
                    s.abms and not self.infinite
                ):  # con munición infinita no hay sobrantes
                    s.abms -= 1
                    t.abms += 1
                    t.abm_points += BONUS_ABM * mult
                    t.wait = 5
                    self.fx.append(FX("tick_abm", s.x, s.y))
                    return
            t.stage = 1
            t.wait = 0 if any(c.alive for c in self.cities) else FPS
            return
        if t.stage == 1:
            for i in TALLY_ORDER:
                c = self.cities[i]
                if c.alive and i not in t.cities:
                    t.cities.append(i)
                    t.city_points += BONUS_CITY * mult
                    t.wait = 16
                    self.fx.append(FX("tick_city", c.x, c.y))
                    return
            t.stage = 2
            t.wait = FPS
            return
        self.score += t.abm_points + t.city_points
        self._regen()

    def _regen(self) -> None:
        """REGEN y CHEKBO: ciudades bonus ganadas y colocadas en cráteres al azar."""
        if self.bonus_every:
            level = self.score // self.bonus_every
            if level > self.bonus_level:
                gained = level - self.bonus_level
                self.reserve += gained
                self.stats.bonus_cities += gained
                self.bonus_level = level
        dead = [i for i, c in enumerate(self.cities) if not c.alive]
        self.regen_cities = []
        while dead and self.reserve > 0:
            i = self.rng.choice(dead)
            dead.remove(i)
            self.cities[i].alive = True
            self.reserve -= 1
            self.regen_cities.append(i)
        self.tally = None
        if self.regen_cities:
            self._set_phase(Phase.REGEN)
            for i in self.regen_cities:
                self.fx.append(FX("bonus_city", self.cities[i].x, self.cities[i].y))
            return
        self._after_regen()

    def _after_regen(self) -> None:
        out = not any(c.alive for c in self.cities) and self.reserve == 0
        if not out:
            self.stats.waves += 1
            self.wave += 1
        self._store_player(out)
        nxt = self._next_player()
        if nxt is None:
            self._set_phase(Phase.THE_END)
            self.fx.append(FX("game_over"))
        elif out:  # a dos: este jugador se queda sin ciudades y el otro sigue
            self.next_player = nxt
            self._set_phase(Phase.PLAYER_OUT)
            self.fx.append(FX("player_out", a=self.current))
        else:
            if nxt != self.current:
                self._load_player(nxt)
            self._begin_wave()

    def _check_high_score(self) -> None:
        if self.entry_queue is None:
            self.entry_queue = list(range(len(self.players)))
            self.new_rank = -1
        while self.entry_queue:
            i = self.entry_queue.pop(0)
            score = self.players[i].score
            if score > 0 and score > self.high_scores[-1][1]:
                self.entry_player = i
                self.entry, self.entry_pos, self.entry_spin = [0, 0, 0], 0, 0.0
                self._set_phase(Phase.INITIALS)
                return
        self.entry_queue = None
        self._start_scores()

    def _initials_frame(self, inp: Inputs) -> None:
        if self.timer >= INITIALS_FRAMES:
            self._commit_initials()
            return
        n = len(INITIALS_ALPHABET)
        if inp.letter and inp.letter.upper() in INITIALS_ALPHABET:
            self.entry[self.entry_pos] = INITIALS_ALPHABET.index(inp.letter.upper())
            self._next_initial()
            return
        if inp.back and self.entry_pos > 0:
            self.entry_pos -= 1
            self.fx.append(FX("select"))
            return
        step = inp.nav
        self.entry_spin += inp.spin
        while self.entry_spin >= 6:
            step += 1
            self.entry_spin -= 6
        while self.entry_spin <= -6:
            step -= 1
            self.entry_spin += 6
        if step:
            self.entry[self.entry_pos] = (self.entry[self.entry_pos] + step) % n
            self.fx.append(FX("select"))
        if any(inp.fire) or inp.start:
            self._next_initial()

    def _next_initial(self) -> None:
        self.fx.append(FX("select"))
        self.entry_pos += 1
        if self.entry_pos >= 3:
            self._commit_initials()

    def _commit_initials(self) -> None:
        name = "".join(INITIALS_ALPHABET[i] for i in self.entry)
        mine = (name, self.players[self.entry_player].score)
        table = sorted(self.high_scores + [mine], key=lambda e: -e[1])[:5]
        self.new_rank = next((i for i, e in enumerate(table) if e is mine), -1)
        self.high_scores = self.tables[self.ammo_mode] = table
        self.scores_changed = True
        self._check_high_score()


# =============================================================================
# Piloto automático
# =============================================================================


class Autopilot:
    """El ordenador juega. En el attract imita al original: ataca los ICBM por
    orden de aparición, apunta a donde estarán dentro de 16 frames, mueve el
    cursor a 2 píxeles por frame (AUTSPD) y nunca tiene más de 2 ABM en vuelo.
    Con skilled=True calcula la interceptación y se usa en --headless."""

    def __init__(self, skilled: bool = False) -> None:
        self.skilled = skilled
        self.speed = 6.0 if skilled else 2.0
        self.max_in_flight = 4 if skilled else 2
        self.ticks = 0

    def inputs(self, g: Game) -> Inputs:
        inp = Inputs()
        self.ticks += 1
        if g.phase is Phase.INITIALS:
            inp.fire = (self.ticks % 20 == 0, False, False)
            return inp
        if g.phase is Phase.STATS:
            inp.start = g.timer > 2 * FPS
            return inp
        if g.phase not in (Phase.PLAY, Phase.DEMO):
            return inp
        aim = self._choose(g)
        if aim is None:
            return inp
        ax, ay = aim
        cx, cy = g.cursor
        inp.dx = clamp(ax - cx, -self.speed, self.speed)
        inp.dy = clamp(ay - cy, -self.speed, self.speed)
        close = abs(ax - cx) <= self.speed and abs(ay - cy) <= self.speed
        if close and len(g.abms) < self.max_in_flight:
            silo = self._silo_for(g, ax, ay)
            if silo is not None:
                inp.fire = tuple(i == silo for i in range(3))
        return inp

    def _choose(self, g: Game) -> tuple[float, float] | None:
        rate = 1.0 if g.speed_off else 256.0 / (256.0 + g.delay)
        for m in sorted(
            (m for m in g.incoming if m is not None), key=lambda m: m.serial
        ):
            p = self._lead(g, m, rate)
            if p is not None and not self._covered(g, p):
                return p
        f = g.flier
        if self.skilled and f is not None:
            ahead = 30 / FLIER_MOVE_EVERY[f.kind]
            p = (clamp(f.x + f.direction * ahead, *CURSOR_X), clamp(f.y, *CURSOR_Y))
            if not self._covered(g, p):
                return p
        return None

    def _lead(self, g: Game, m: Missile, rate: float) -> tuple[float, float] | None:
        if self.skilled:
            t = 20.0
            for _ in range(4):
                x, y = m.x + m.vx * rate * t, m.y + m.vy * rate * t
                flights = [
                    approx_dist(x - s.x, y - SILO_TOP) / ABM_STEPS[i]
                    for i, s in enumerate(g.silos)
                    if s.abms
                ]
                if not flights:
                    return None
                travel = max(abs(x - g.cursor[0]), abs(y - g.cursor[1])) / self.speed
                t = min(flights) + travel + 10
        else:
            x, y = m.x + m.vx * rate * 16, m.y + m.vy * rate * 16
        if y < CURSOR_Y[0] - 8:
            return None
        return clamp(x, *CURSOR_X), clamp(y, *CURSOR_Y)

    @staticmethod
    def _covered(g: Game, p: tuple[float, float]) -> bool:
        px, py = p
        if any(abs(a.tx - px) < 9 and abs(a.ty - py) < 9 for a in g.abms):
            return True
        return any(
            e is not None and e.step < 14 and abs(e.x - px) < 11 and abs(e.y - py) < 11
            for e in g.explosions
        )

    def _silo_for(self, g: Game, x: float, y: float) -> int | None:
        best, best_cost = None, 0.0
        for i, s in enumerate(g.silos):
            if s.abms <= 0:
                continue
            if self.skilled:
                cost = approx_dist(x - s.x, y - SILO_TOP) / ABM_STEPS[i]
            else:
                cost = abs(s.x - x)
            if best is None or cost < best_cost:
                best, best_cost = i, cost
        return best


# =============================================================================
# Simulación sin ventana y comprobaciones internas
# =============================================================================


def simulate(
    seed: int | None,
    start_wave: int = 1,
    frames: int = 60 * 60 * 90,
    cities: int = 6,
    bonus: int = 10000,
    infinite: bool = False,
) -> Game:
    """Una partida completa con el piloto hábil, sin pygame."""
    g = Game(
        seed, cities, bonus, start_wave, stats_screen=False, infinite_ammo=infinite
    )
    g.start_game()
    pilot = Autopilot(skilled=True)
    while g.frame < frames and g.phase is not Phase.THE_END:
        g.step(pilot.inputs(g))
        g.fx.clear()
    return g


def run_headless(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    infinite = args.ammo == "infinite"  # sin --ammo, la munición del original
    g = simulate(args.seed, args.wave, args.frames, args.cities, args.bonus, infinite)
    elapsed = time.perf_counter() - started
    s = g.stats
    minutes, seconds = divmod(g.frame // FPS, 60)
    over = "sí" if g.phase is Phase.THE_END else "no, se agotó el tiempo"
    print(f"missile.py {__version__}, partida simulada con semilla {args.seed}")
    print(f"  fin de partida:       {over}")
    print(f"  munición:             {'infinita' if infinite else 'la del original'}")
    print(f"  oleada alcanzada:     {g.wave}")
    print(f"  oleadas superadas:    {s.waves}")
    print(f"  puntuación:           {g.score}")
    print(f"  ABM disparados:       {s.shots}")
    print(
        f"  derribos:             {s.kills} ({s.icbms} ICBM, {s.smarts} smart bombs, {s.fliers} voladores)"
    )
    print(f"  mejor cadena:         {s.best_chain}")
    print(f"  MIRV divididos:       {s.mirvs}")
    print(f"  ciudades perdidas:    {s.cities_lost}")
    print(f"  ciudades bonus:       {s.bonus_cities}")
    print(f"  tiempo de juego:      {minutes}:{seconds:02d} a 60 Hz ({g.frame} frames)")
    print(f"  simulado en:          {elapsed:.2f} s")
    return 0


def self_test() -> int:
    """Comprobaciones de las reglas del original. No necesita pygame."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - informe, no aborto
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append((name, bool(ok), detail))

    def tables():
        lengths = (
            len(ICBM_COUNT),
            len(SMART_COUNT),
            len(ICBM_DELAY),
            len(FLIER_RECHARGE),
        )
        sizes = lengths + (len(FLIER_FIRE_GAP), len(EXPLOSION_RADIUS))
        return sizes == (19, 19, 15, 7, 7, 29) and max(EXPLOSION_RADIUS) == 13, str(
            sizes
        )

    def multipliers():
        got = [multiplier(w) for w in range(1, 13)]
        return got == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6], str(got)

    def collision():
        cases = {(13, 0): True, (14, 0): False, (10, 10): True, (11, 11): False}
        got = {k: octagon_hit(k[0], k[1], 13 + SIZE_ICBM) for k in cases}
        return got == cases, str(got)

    def clock():
        c, moves = 0, []
        for frame in range(1, 14):
            c, moved = icbm_clock(c, 0x180)
            if moved:
                moves.append(frame)
        return moves == [1, 3, 6, 8, 11, 13], str(moves)

    def abm_speed():
        frames = []
        for silo in (0, 1):
            g = Game(seed=1)
            g.start_game()
            g._set_phase(Phase.PLAY)
            g.icbm_left = 1  # algo a lo que disparar
            g.cursor = [float(SILOS[silo][0]), 124.0]
            fire = tuple(i == silo for i in range(3))
            g._fire(fire)
            n = 0
            while g.abms and n < 200:
                g._update_abms()
                n += 1
            frames.append(n)
        return frames == [34, 15], f"lateral {frames[0]} frames, central {frames[1]}"

    def explosion_life():
        g = Game(seed=1)
        g._detonate(128, 128, False, 0)
        n = 0
        while g.explosion_total() and n < 400:
            g.frame += 1
            g._update_explosions()
            n += 1
        return 131 <= n <= 135, f"{n} frames"

    def target_cap():
        g = Game(seed=3)
        g.start_game()
        g.cities[0].alive = g.cities[1].alive = False
        g.cities_down = 2
        picks = [g._pick_target() for _ in range(6)]
        cities = [t for t in picks if t < 6]
        return len(cities) <= 1, f"objetivos {picks}"

    def smart_climb():
        all_but_up = 0xFF & ~1
        early = find_opening(0, all_but_up | 1)
        late = find_opening(0, all_but_up)
        return early is None and late == 0, f"oleada<9: {early}, oleada>=9: {late}"

    def scoring():
        g = Game(seed=1)
        g.start_game()
        g.wave = 3
        g._set_phase(Phase.PLAY)
        g.incoming[7] = Missile(ICBM, 100.0, 100.0, 95.0, 16.0, target=2)
        g._kill_incoming(7, Explosion(100, 100, False))
        return g.score == 50, f"{g.score} puntos"

    def bonus_city():
        g = Game(seed=1)
        g.start_game()
        g.cities[3].alive = False
        g.score = 10050
        g._regen()
        return g.cities[3].alive and g.reserve == 0, f"reserva {g.reserve}"

    def determinism():
        a, b = simulate(7, frames=6000), simulate(7, frames=6000)
        sig_a = (a.score, a.wave, a.serial, a.stats.shots)
        sig_b = (b.score, b.wave, b.serial, b.stats.shots)
        return sig_a == sig_b, str(sig_a)

    def full_games():
        out = []
        for seed in (1, 2, 3):
            g = simulate(seed)
            out.append((g.phase is Phase.THE_END, g.wave, g.score))
        return all(o[0] for o in out), str(out)

    def late_waves():
        g = simulate(5, start_wave=15)
        ok = g.phase is Phase.THE_END and g.stats.smarts + g.stats.fliers > 0
        return (
            ok,
            f"oleada {g.wave}, {g.stats.smarts} smart bombs y {g.stats.fliers} voladores derribados",
        )

    def mirvs():
        total = sum(
            simulate(seed, frames=60 * 60 * 20).stats.mirvs for seed in (11, 12)
        )
        return total > 0, f"{total} divisiones"

    def glyphs():
        missing = sorted(
            {ch for text in UI_TEXTS for ch in text.upper() if ch not in FONT}
        )
        return not missing, "faltan: " + "".join(missing) if missing else "completos"

    def text_widths():
        too_long = [
            s for pair in TEXTS.values() for s in pair if len(s.format(n=99)) > 32
        ]
        boxes = [
            s
            for table in (PAUSE_LINES, HELP_LINES)
            for lines in table.values()
            for s in lines
            if len(s) > 29
        ]
        bad = too_long + boxes
        return not bad, "caben" if not bad else f"demasiado largos: {bad}"

    def two_players():
        g = Game(seed=8, stats_screen=False)
        g.start_game(players=2)
        pilot, turns = Autopilot(skilled=True), []
        while g.frame < 60 * 60 * 120 and g.phase is not Phase.THE_END:
            if g.phase is Phase.INTRO and g.timer == 1:
                turns.append((g.current, g.wave))
            g.step(pilot.inputs(g))
            g.fx.clear()
        first = [c for c, _ in turns[:6]]
        alternates = first[:4] == [0, 1, 0, 1]
        ended = g.phase is Phase.THE_END and all(pl.out for pl in g.players)
        return (
            alternates and ended,
            f"turnos {turns[:6]}..., puntos {[pl.score for pl in g.players]}",
        )

    def storage():
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "v1.json"
            old.write_text(
                json.dumps({"version": 1, "scores": [["OLD", 42]]}), encoding="utf-8"
            )
            legacy = ScoreStore(True, old).load() == {"arcade": [("OLD", 42)]}
            scores = ScoreStore(True, Path(tmp) / "scores.json")
            tables = {"arcade": [("ABC", 1234), ("XYZ", 99)], "infinite": [("INF", 5)]}
            scores.save(tables)
            settings = SettingsStore(True, Path(tmp) / "settings.json")
            settings.set(style="retro", effects=False)
            reread = SettingsStore(True, Path(tmp) / "settings.json")
            ok = legacy and scores.load() == tables
            ok = ok and reread.get("style", "hd") == "retro"
            ok = ok and reread.get("effects", True) is False
            ok = ok and reread.get("lang", "auto") == "auto"
            return ok, "récords v1 y v2, y ajustes"

    def infinite_ammo():
        g = Game(seed=4, stats_screen=False, infinite_ammo=True)
        g.start_game()
        pilot, lowest, abm_bonus = Autopilot(skilled=True), ABMS_PER_SILO, 0
        while g.frame < 60 * 60 * 30 and g.phase is not Phase.THE_END:
            g.step(pilot.inputs(g))
            g.fx.clear()
            lowest = min([lowest] + [s.abms for s in g.silos if s.alive])
            if g.tally is not None:
                abm_bonus = max(abm_bonus, g.tally.abm_points)
        g.set_infinite(False)
        separate = g.high_scores is g.tables["arcade"]
        ok = (
            lowest == ABMS_PER_SILO
            and abm_bonus == 0
            and g.stats.shots > 300
            and separate
        )
        return (
            ok,
            f"munición mínima {lowest}, {g.stats.shots} disparos, oleada {g.wave}",
        )

    check("tablas del original completas", tables)
    check("multiplicador por oleada", multipliers)
    check("colisión octogonal de DELTA", collision)
    check("reloj 8.8 de los ICBM (reparto 1-2-1-2)", clock)
    check("ABM central más rápido que los laterales", abm_speed)
    check("explosión de 27 pasos, uno cada 5 frames", explosion_life)
    check("nunca más de 3 ciudades por oleada", target_cap)
    check("smart bombs: no suben antes de la oleada 9", smart_climb)
    check("puntuación con multiplicador", scoring)
    check("ciudad bonus a los 10.000 puntos", bonus_city)
    check("misma semilla, misma partida", determinism)
    check("partidas completas sin errores", full_games)
    check("oleadas altas: smart bombs y voladores", late_waves)
    check("los MIRV se dividen", mirvs)
    check("tipografía completa, también en español", glyphs)
    check("ningún texto se sale de la pantalla", text_widths)
    check("dos jugadores: turnos alternos y final", two_players)
    check("récords y ajustes en disco", storage)
    check("munición infinita: silos llenos y su propia tabla", infinite_ammo)
    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        print(f"{'OK   ' if ok else 'FALLO'}  {name:<{width}}  {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"{len(results) - failed} de {len(results)} comprobaciones superadas")
    return 1 if failed else 0


# =============================================================================
# Textos en pantalla: en inglés, como la recreativa, o en español
# =============================================================================

TEXTS: dict[str, tuple[str, str]] = {
    "press": ("CLICK OR PRESS ENTER", "HAZ CLIC O PULSA ENTER"),
    "two": ("PRESS 2 FOR TWO PLAYERS", "PULSA 2 PARA DOS JUGADORES"),
    "tribute": ("A PYTHON TRIBUTE", "UN HOMENAJE EN PYTHON"),
    "player": ("PLAYER  {n}", "JUGADOR  {n}"),
    "points": ("{n} X POINTS", "{n} X PUNTOS"),
    "defend": ("DEFEND       CITIES", "DEFIENDE   CIUDADES"),
    "bonus_points": ("BONUS POINTS", "PUNTOS EXTRA"),
    "bonus_city": ("BONUS CITY", "CIUDAD EXTRA"),
    "low": ("LOW", "BAJO"),
    "out": ("OUT", "VACÍO"),
    "the_end": ("THE END", "FIN"),
    "game_over": ("GAME OVER", "FIN DE PARTIDA"),
    "great": ("GREAT SCORE", "GRAN PUNTUACIÓN"),
    "enter": ("ENTER YOUR INITIALS", "ESCRIBE TUS INICIALES"),
    "change": ("MOVE OR TYPE TO CHANGE LETTERS", "MUEVE O TECLEA PARA CAMBIAR"),
    "select": ("FIRE TO SELECT", "DISPARA PARA ELEGIR"),
    "high": ("HIGH SCORES", "MEJORES PUNTUACIONES"),
    "wave": ("WAVE {n}", "OLEADA {n}"),
    "chain": ("CHAIN {n}", "CADENA {n}"),
    "report": ("MISSION REPORT", "INFORME DE MISIÓN"),
    "press_fire": ("PRESS FIRE", "PULSA DISPARO"),
    "style_hd": ("HD GRAPHICS", "GRÁFICOS HD"),
    "style_retro": ("RETRO CRT", "RETRO CRT"),
    "style_arcade": ("ARCADE PIXELS", "PÍXELES ARCADE"),
    "inf_on": ("INFINITE AMMO", "MUNICIÓN INFINITA"),
    "inf_off": ("LIMITED AMMO", "MUNICIÓN LIMITADA"),
    "fx_on": ("EFFECTS ON", "EFECTOS SÍ"),
    "fx_off": ("EFFECTS OFF", "EFECTOS NO"),
    "sound_on": ("SOUND ON", "SONIDO SÍ"),
    "sound_off": ("SOUND OFF", "SONIDO NO"),
    "trackball": ("TRACKBALL", "TRACKBALL"),
    "mouse": ("MOUSE", "RATÓN"),
    "shot": ("SCREENSHOT SAVED", "CAPTURA GUARDADA"),
    "lang": ("ENGLISH", "ESPAÑOL"),
    "st_waves": ("WAVES CLEARED", "OLEADAS SUPERADAS"),
    "st_score": ("SCORE", "PUNTUACIÓN"),
    "st_shots": ("ABMS FIRED", "ABM DISPARADOS"),
    "st_kills": ("ENEMIES DOWN", "DERRIBOS"),
    "st_icbms": ("  ICBMS", "  ICBM"),
    "st_smarts": ("  SMART BOMBS", "  BOMBAS INTELIGENTES"),
    "st_fliers": ("  FLIERS", "  VOLADORES"),
    "st_chain": ("BEST CHAIN", "MEJOR CADENA"),
    "st_mirvs": ("MIRVS SPLIT", "MIRV DIVIDIDOS"),
    "st_lost": ("CITIES LOST", "CIUDADES PERDIDAS"),
    "st_bonus": ("BONUS CITIES", "CIUDADES EXTRA"),
    "st_ratio": ("KILLS PER ABM", "DERRIBOS POR ABM"),
    "st_time": ("TIME", "TIEMPO"),
}
HELP_ROWS = {
    "en": ("CONTROLS", (
        ("MOUSE", "AIM"), ("L M R", "FIRE"), ("Z X C", "FIRE"), ("ARROWS", "AIM"),
        ("SHIFT", "FINE AIM"), ("PAD", "STICK, X A B"), ("1  2", "ONE OR TWO PLAYERS"),
        ("I", "INFINITE AMMO"), ("P  ESC", "PAUSE"), ("F2  F3", "STYLE  EFFECTS"),
        ("F11  F12", "FULLSCREEN  SHOT"), ("M  T  L", "SOUND MOUSE LANG"),
    )),
    "es": ("CONTROLES", (
        ("RATÓN", "APUNTAR"), ("BOTONES", "DISPARAR"), ("Z X C", "DISPARAR"),
        ("FLECHAS", "APUNTAR"), ("MAYÚS", "PRECISIÓN"), ("MANDO", "STICK, X A B"),
        ("1  2", "UNO O DOS JUGADORES"), ("I", "MUNICIÓN INFINITA"), ("P  ESC", "PAUSA"),
        ("F2  F3", "ESTILO  EFECTOS"), ("F11  F12", "PANTALLA  CAPTURA"),
        ("M  T  L", "SONIDO RATÓN IDIOMA"),
    )),
}  # fmt: skip
PAUSE_ROWS = {
    "en": ("PAUSED", (("P", "RESUME"), ("ESC", "QUIT"), ("F1", "HELP"))),
    "es": ("PAUSA", (("P", "SEGUIR"), ("ESC", "SALIR"), ("F1", "AYUDA"))),
}


def box_lines(rows) -> tuple[str, ...]:
    """Las filas (tecla, acción) en líneas de ancho fijo para la fuente de píxel."""
    title, items = rows
    return (title, "") + tuple(f"{key:<10}{action}" for key, action in items)


HELP_LINES = {lang: box_lines(rows) for lang, rows in HELP_ROWS.items()}
PAUSE_LINES = {lang: box_lines(rows) for lang, rows in PAUSE_ROWS.items()}
LANGS = ("en", "es")


def tr(key: str, lang: str, **values) -> str:
    text = TEXTS[key][1 if lang == "es" else 0]
    return text.format(**values) if values else text


def detect_lang() -> str:
    """Español si el sistema está en español; si no, inglés, como la recreativa."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var, "")
        if value:
            return "es" if value.lower().startswith("es") else "en"
    try:
        import locale

        name = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        name = ""
    return "es" if name.startswith(("es", "spanish")) else "en"


def ui_texts() -> list[str]:
    """Todo lo que puede llegar a pantalla, para comprobar la tipografía."""
    out = [INITIALS_ALPHABET, "0123456789", "MISSILE", "COMMAND"]
    for pair in TEXTS.values():
        out.extend(s.format(n=1) for s in pair)
    for table in (PAUSE_LINES, HELP_LINES):
        for lines in table.values():
            out.extend(lines)
    return out


UI_TEXTS = ui_texts()


# =============================================================================
# Render (pygame)
# =============================================================================

# Cifras de 3 x 5 para los puntos flotantes
_MINI = """
0 ### #.# #.# #.# ###
1 .#. ##. .#. .#. ###
2 ### ..# ### #.. ###
3 ### ..# .## ..# ###
4 #.# #.# ### ..# ..#
5 ### #.. ### ..# ###
6 ### #.. ### #.# ###
7 ### ..# .#. .#. .#.
8 ### #.# ### #.# ###
9 ### #.# ### ..# ###
+ ... .#. ### .#. ...
"""
MINI_FONT = {
    line.split()[0]: tuple(line.split()[1:]) for line in _MINI.strip().splitlines()
}

SPARK, DEBRIS, EMBER = 0, 1, 2
POPUP_CEILING = TOP - 16  # los puntos flotantes no tapan el marcador
FIELD_PHASES = (Phase.INTRO, Phase.PLAY, Phase.TALLY, Phase.DEMO)


def sy(y: float) -> float:
    """De la y del juego (hacia arriba) a la fila de pantalla (hacia abajo)."""
    return Y_MAX - y


def scaled(color: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * f))) for c in color)


@dataclass(slots=True, frozen=True)
class Palette:
    bg: tuple[int, int, int]
    terrain: tuple[int, int, int]
    icbm: tuple[int, int, int]
    city: tuple[int, int, int]
    abm: tuple[int, int, int]
    flash: tuple[int, int, int]
    dark: bool


class PixelRenderer:
    """Estilos retro y arcade: dibuja la partida en 256 x 231, como el hardware,
    y la amplía al mayor múltiplo entero que quepa en la ventana."""

    FILTERS = ("crt", "glow", "off")

    def __init__(self, fx: str = "crt", juice: bool = True, lang: str = "en") -> None:
        self.k = 0
        self.rect = pygame.Rect(0, 0, W, H)
        self.fx_mode = fx if fx in self.FILTERS else "crt"
        self.juice = juice
        self.lang = lang if lang in LANGS else "en"
        self.logical = pygame.Surface((W, H))
        self.glow = pygame.Surface((W, H))
        self.smoke_layer = pygame.Surface((W, H), pygame.SRCALPHA)
        self.hi = None
        self.mask = None
        self._blur = getattr(pygame.transform, "gaussian_blur", None)
        self._glyphs: dict = {}
        self._sprites: dict = {}
        self._terrains: dict = {}
        self.rng = random.Random(1980)
        self.stars = [
            (
                self.rng.randrange(W),
                self.rng.randrange(64, 216),
                self.rng.random() * math.tau,
            )
            for _ in range(80)
        ]
        self.particles: list[list] = []
        self.puffs: list[list[float]] = []
        self.popups: list[list] = []
        self.rings: list[list[float]] = []
        self.smoking: set[tuple[int, int]] = set()
        self.shake = 0.0
        self.flash = 0.0
        self.flash_rgb = (255, 255, 255)
        self.toast = ""
        self.toast_frames = 0
        self.palette: Palette | None = None
        self.title_layers: tuple | None = None
        self.title_clock = -1

    def t(self, key: str, **values) -> str:
        return tr(key, self.lang, **values)

    # --- utilidades de dibujo ---------------------------------------------------

    def rgb(self, name: str) -> tuple[int, int, int]:
        return (RGB_PHOSPHOR if self.juice else RGB_ARCADE)[name]

    def _glyph(self, ch: str, color, sx: int = 1, sy_: int = 1):
        key = (ch, color, sx, sy_)
        surf = self._glyphs.get(key)
        if surf is None:
            if sx == 1 and sy_ == 1:
                surf = pygame.Surface((8, 8), pygame.SRCALPHA)
                rows = FONT.get(ch, FONT["?"])
                top = 8 - len(rows)
                for r, row in enumerate(rows):
                    for c, v in enumerate(row):
                        if v == "#":
                            surf.set_at((c, r + top), color)
            else:
                surf = pygame.transform.scale(self._glyph(ch, color), (8 * sx, 8 * sy_))
            self._glyphs[key] = surf
        return surf

    def text(self, s, x, y, color, sx=1, sy_=1, glow=False, surf=None) -> None:
        targets = [surf or self.logical]
        if glow and self.juice and surf is None:
            targets.append(self.glow)
        for n, target in enumerate(targets):
            col = color if n == 0 else scaled(color, 0.55)
            for i, ch in enumerate(s.upper()):
                if ch != " ":
                    target.blit(
                        self._glyph(ch, col, sx, sy_), (int(x) + i * 8 * sx, int(y))
                    )

    def text_at(self, s, h, v, color, sx=1, sy_=1, glow=False) -> None:
        """Texto en coordenadas del original: (h, v) es el centro del primer carácter."""
        self.text(s, h - 4, Y_MAX - (v + 4), color, sx, sy_, glow)

    def text_center(self, s, cx, y, color, sx=1, sy_=1, glow=False, surf=None) -> None:
        self.text(s, cx - len(s) * 4 * sx, y, color, sx, sy_, glow, surf)

    def mini(self, s: str, cx: float, y: float, color, surf=None) -> None:
        target = surf or self.logical
        x = int(cx) - len(s) * 2
        for i, ch in enumerate(s):
            for r, row in enumerate(MINI_FONT.get(ch, ())):
                for c, v in enumerate(row):
                    if v == "#":
                        target.set_at((x + i * 4 + c, int(y) + r), color)

    def _sprite(self, rows, c1, c2=None, flip=False):
        key = (rows, c1, c2, flip)
        surf = self._sprites.get(key)
        if surf is None:
            surf = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    if v == "1":
                        surf.set_at((c, r), c1)
                    elif v == "2":
                        surf.set_at((c, r), c2 or c1)
            if flip:
                surf = pygame.transform.flip(surf, True, False)
            self._sprites[key] = surf
        return surf

    def _blit_c(self, sprite, x: float, y: float, glow: bool = False) -> None:
        pos = (
            round(x) - sprite.get_width() // 2,
            round(sy(y)) - sprite.get_height() // 2,
        )
        self.logical.blit(sprite, pos)
        if glow and self.juice:
            self.glow.blit(sprite, pos)

    def _terrain_surface(self, color):
        key = (color, self.juice)
        surf = self._terrains.get(key)
        if surf is None:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            light, shade = scaled(color, 1.25), scaled(color, 0.7)
            for x, h in enumerate(TERRAIN):
                pygame.draw.line(surf, color, (x, Y_MAX - h), (x, Y_MAX))
                if self.juice:
                    surf.set_at((x, Y_MAX - h), light)
                    pygame.draw.line(surf, shade, (x, Y_MAX - 3), (x, Y_MAX))
            self._terrains[key] = surf
        return surf

    def _crt_mask(self):
        """Viñeta, líneas de barrido y rejilla de apertura en una sola capa."""
        w, h = W * self.k, H * self.k
        vig = pygame.Surface((64, 58))
        for y in range(58):
            for x in range(64):
                nx, ny = (x + 0.5) / 32 - 1, (y + 0.5) / 29 - 1
                v = int(
                    255
                    * clamp(1.06 - 0.32 * (nx * nx * 0.8 + ny * ny) ** 1.4, 0.55, 1.0)
                )
                vig.set_at((x, y), (v, v, v))
        mask = pygame.transform.smoothscale(vig, (w, h))
        if self.k >= 2:
            lines = pygame.Surface((w, h))
            lines.fill((255, 255, 255))
            dark = (172, 172, 172) if self.k >= 3 else (205, 205, 205)
            for y in range(self.k - 1, h, self.k):
                pygame.draw.line(lines, dark, (0, y), (w - 1, y))
            mask.blit(lines, (0, 0), special_flags=pygame.BLEND_MULT)
        if self.k >= 3:
            grille = pygame.Surface((w, h))
            tints = ((255, 228, 228), (228, 255, 228), (228, 228, 255))
            for x in range(w):
                pygame.draw.line(grille, tints[x % 3], (x, 0), (x, h - 1))
            mask.blit(grille, (0, 0), special_flags=pygame.BLEND_MULT)
        return mask

    # --- conmutadores -------------------------------------------------------------

    def say(self, key: str) -> None:
        self.toast, self.toast_frames = key, 100

    @property
    def style(self) -> str:
        return "retro" if self.fx_mode != "off" else "arcade"

    def _fit(self, size) -> None:
        sw, sh = size
        k = max(1, min(sw // W, sh // H))
        if k != self.k:
            self.k = k
            self.hi = pygame.Surface((W * k, H * k))
            self.mask = self._crt_mask()
        self.rect = pygame.Rect((sw - W * k) // 2, (sh - H * k) // 2, W * k, H * k)

    def to_game(self, pos) -> tuple[float, float]:
        k = max(1, self.k)
        return ((pos[0] - self.rect.x) / k, Y_MAX - (pos[1] - self.rect.y) / k)

    @property
    def unit(self) -> float:
        return float(max(1, self.k))

    def set_juice(self, on: bool) -> None:
        self.juice = on
        for bucket in (self.particles, self.puffs, self.popups, self.rings):
            bucket.clear()
        self.shake = self.flash = 0.0
        self.say("fx_on" if on else "fx_off")

    def toggle_lang(self) -> None:
        self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        self.say("lang")

    # --- efectos: se alimentan de los sucesos del juego, un frame cada vez --------

    def tick(self, g: Game) -> None:
        if self.juice:
            for f in g.fx:
                self._on_fx(f, g)
        self.shake *= 0.86
        self.flash *= 0.84
        if self.toast_frames:
            self.toast_frames -= 1
        if g.phase is Phase.TITLE and self.title_layers is not None:
            for e in g.explosions:
                if e is not None and e.radius:
                    pts = [(x, sy(y)) for x, y in octagon(e.x, e.y, e.radius)]
                    for layer in self.title_layers:
                        pygame.draw.polygon(layer, (0, 0, 0, 0), pts)
        if not self.juice:
            return
        alive = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] -= 0.06 if p[6] == DEBRIS else 0.025
            p[4] -= 1
            if p[6] == DEBRIS:
                ground = TERRAIN[int(clamp(p[0], 0, W - 1))]
                if p[1] <= ground:
                    p[1], p[3], p[2] = ground, -p[3] * 0.35, p[2] * 0.6
            if p[4] > 0:
                alive.append(p)
        self.particles = alive[-1500:]
        for q in self.puffs:
            q[0] += q[2]
            q[1] += q[3]
            q[4] -= 1
        self.puffs = [q for q in self.puffs if q[4] > 0][-500:]
        for pop in self.popups:
            pop[1] = min(pop[1] + 0.35, POPUP_CEILING)
            pop[3] -= 1
        self.popups = [pop for pop in self.popups if pop[3] > 0]
        for ring in self.rings:
            ring[2] += 1
        self.rings = [ring for ring in self.rings if ring[2] < 16]
        if g.phase in FIELD_PHASES:
            for x, y in self.smoking:
                if self.rng.random() < 0.25:
                    self.puffs.append([
                        x + self.rng.uniform(-5, 5), y + self.rng.uniform(1, 5),
                        self.rng.uniform(-0.05, 0.12), self.rng.uniform(0.12, 0.3),
                        self.rng.randrange(110, 180), 180,
                    ])  # fmt: skip

    def _burst(
        self, x, y, n, speed, kind=SPARK, colors=None, life=(18, 40), up=0.0
    ) -> None:
        r = self.rng
        for _ in range(n):
            a = r.random() * math.tau
            v = speed * (0.3 + r.random())
            ttl = r.randrange(*life)
            color = r.choice(colors) if colors else None
            self.particles.append(
                [x, y, math.cos(a) * v, math.sin(a) * v + up, ttl, ttl, kind, color]
            )

    def _flash(self, rgb, amount) -> None:
        if amount > self.flash:
            self.flash, self.flash_rgb = amount, rgb

    def _on_fx(self, f: FX, g: Game) -> None:
        p = self.palette
        name = f.name
        if name == "boom" and not f.a and g.phase is not Phase.TITLE:
            self.rings.append([f.x, f.y, 0])
        elif name == "kill":
            self._burst(
                f.x, f.y, (12, 20, 30)[f.c - 1], 1.5 if f.c == KILL_ICBM else 2.0
            )
            if f.a:
                self.popups.append(
                    [f.x, min(f.y + 5, POPUP_CEILING), str(f.a), 48, False]
                )
            if f.b >= 3:
                label = self.t("chain", n=f.b)
                self.popups.append([f.x, min(f.y + 14, POPUP_CEILING), label, 80, True])
                self.shake = max(self.shake, min(0.8 + f.b * 0.35, 3.0))
            if f.c == KILL_FLIER:
                self.shake = max(self.shake, 2.0)
        elif name in ("city", "silo") and p is not None:
            colors = (
                [p.city, p.abm, p.terrain] if name == "city" else [p.abm, p.terrain]
            )
            self._burst(f.x, f.y + 2, 46, 1.9, DEBRIS, colors, (60, 120), up=1.2)
            self._burst(f.x, f.y + 3, 30, 2.4, SPARK, life=(20, 50), up=0.8)
            self._burst(f.x, f.y + 4, 14, 0.7, EMBER, life=(50, 90), up=0.9)
            self.shake = max(self.shake, 4.0 if name == "city" else 5.0)
            self._flash((255, 120, 40), 0.42)
            self.smoking.add((int(f.x), int(f.y) - 2))
        elif name in ("abm", "low"):
            self._burst(f.x, f.y + 1, 4, 0.8, SPARK, life=(6, 14), up=0.9)
        elif name in ("mirv", "flier_fire"):
            self._burst(f.x, f.y, 8, 0.9, SPARK, life=(8, 18))
        elif name == "bonus_city":
            self._burst(f.x, f.y + 6, 24, 0.8, EMBER, life=(40, 80), up=0.6)
            self._flash((120, 255, 140), 0.25)
        elif name == "game_over":
            self.shake = 7.0
            self._flash((255, 255, 255), 0.85)
        elif name in ("wave", "start", "player_out"):
            self.smoking.clear()
            self.puffs.clear()

    # --- dibujo -------------------------------------------------------------------

    def draw(self, g: Game, screen, overlay: str | None = None) -> None:
        self._fit(screen.get_size())
        menu = g.phase in (Phase.TITLE, Phase.SCORES, Phase.INITIALS, Phase.STATS)
        names = wave_colors(1 if menu else g.wave)
        bg, terrain, icbm, city, abm = (self.rgb(n) for n in names)
        flash = self.rgb(COLOR_NAMES[(g.frame // 2) % 8])
        p = self.palette = Palette(
            bg, terrain, icbm, city, abm, flash, names[0] == "black"
        )
        self.logical.fill(bg)
        if self.juice:
            self.glow.fill((0, 0, 0))
        if g.phase is Phase.TITLE:
            self._draw_title(g, p)
        elif g.phase is Phase.SCORES:
            self._draw_scores(g, p)
        elif g.phase is Phase.INITIALS:
            self._draw_initials(g, p)
        elif g.phase is Phase.STATS:
            self._draw_stats(g, p)
        else:
            self._draw_field(g, p)
        self._draw_hud(g, p)
        if overlay:
            table = HELP_LINES if overlay == "help" else PAUSE_LINES
            self._draw_box(table[self.lang], p)
        self._compose()
        self._present(screen)

    def _draw_field(self, g: Game, p: Palette) -> None:
        L = self.logical
        if self.juice and p.dark:
            for x, y, phase in self.stars:
                v = int(70 + 60 * math.sin(phase + g.frame * 0.03))
                L.set_at((x, y), (v, v, v + 30))
        if self.juice and self.puffs:
            self._draw_smoke(p)
        L.blit(self._terrain_surface(p.terrain), (0, 0))
        self._draw_cities(g, p)
        self._draw_silos(g, p)
        for m in g.incoming:
            if m is not None and m.kind == ICBM:
                self._trail(m, p.icbm, p.flash)
        for a in g.abms:
            self._trail(a, p.abm, p.flash)
            self._blit_c(self._sprite(X_MARK, p.flash), a.tx, a.ty, glow=True)
        if self.juice:
            for x, y, age in self.rings:
                pts = [(px, sy(py)) for px, py in octagon(x, y, 5 + age * 1.5)]
                pygame.draw.polygon(
                    self.glow, scaled(p.flash, 0.5 * (1 - age / 16)), pts, 1
                )
        self._draw_explosions(g, p)
        for m in g.incoming:
            if m is not None and m.kind == SMART:
                self._blit_c(
                    self._sprite(SMART_SPRITE, p.icbm, p.flash), m.x, m.y, glow=True
                )
        f = g.flier
        if f is not None:
            rows = BOMBER_SPRITE if f.kind == BOMBER else SATELLITE_SPRITE
            self._blit_c(
                self._sprite(rows, p.icbm, p.flash, f.direction < 0),
                f.x,
                f.y,
                glow=True,
            )
        if self.juice:
            self._draw_particles(g, p)
        if g.cursor_visible:
            cx, cy = round(g.cursor[0]), round(sy(g.cursor[1]))
            for target, color in (
                (L, p.abm),
                (self.glow if self.juice else None, scaled(p.abm, 0.6)),
            ):
                if target is not None:
                    pygame.draw.line(target, color, (cx - 3, cy), (cx + 3, cy))
                    pygame.draw.line(target, color, (cx, cy - 3), (cx, cy + 3))
        phase = g.phase
        if phase is Phase.INTRO:
            self._draw_intro(g, p)
        elif phase is Phase.TALLY:
            self._draw_tally(g, p)
        elif phase is Phase.REGEN:
            if (g.timer // 15) % 3:
                self.text_center(
                    self.t("bonus_city"), 128, Y_MAX - 68, p.icbm, glow=True
                )
        elif phase is Phase.PLAYER_OUT:
            self.text_center(
                self.t("player", n=g.current + 1), 128, 70, p.icbm, glow=True
            )
            self.text_center(self.t("game_over"), 128, 90, p.abm, 2, 2, glow=True)
        elif phase is Phase.THE_END:
            self._draw_the_end(g, p)
        elif phase is Phase.DEMO and (g.frame // 30) % 2:
            self.text_center(self.t("press"), 128, 40, p.abm, glow=True)
        if phase in (Phase.PLAY, Phase.DEMO):
            for s in g.silos:
                key = "out" if s.abms == 0 else "low" if s.abms <= 3 else ""
                if key:
                    word = self.t(key)
                    x = clamp(s.x - len(word) * 4, 0, W - len(word) * 8)
                    self.text(word, x, Y_MAX - 7, p.bg)

    def _trail(self, m: Missile, color, head) -> None:
        start, end = (m.ox, sy(m.oy)), (m.x, sy(m.y))
        pygame.draw.line(self.logical, color, start, end)
        hx, hy = int(m.x), int(sy(m.y))
        self.logical.set_at((hx, hy), head)
        if self.juice:
            pygame.draw.line(self.glow, scaled(color, 0.35), start, end)
            pygame.draw.rect(self.glow, head, (hx - 1, hy - 1, 3, 3))

    def _draw_cities(self, g: Game, p: Palette) -> None:
        hidden = set(g.tally.cities) if g.tally is not None else set()
        blinking = set(g.regen_cities) if g.phase is Phase.REGEN else set()
        for i, c in enumerate(g.cities):
            if i in hidden:
                continue
            rows = CITY_SPRITES[i % 3]
            if not c.alive:
                sprite = self._sprite(
                    rows, p.terrain
                )  # ruinas: la silueta en el color del suelo
            elif i in blinking and (g.timer // 6) % 2:
                sprite = self._sprite(rows, p.flash)
            else:
                sprite = self._sprite(rows, p.city, p.abm)
            self.logical.blit(sprite, (c.x - 7, round(sy(c.y + 2))))

    def _draw_silos(self, g: Game, p: Palette) -> None:
        icon = self._sprite(ABM_ICON, p.abm)
        for s in g.silos:
            for dx, dy in ABM_ICONS[: s.abms]:
                self.logical.blit(icon, (s.x + dx - 1, round(sy(s.y + dy))))
            if not s.alive:
                pygame.draw.line(
                    self.logical, p.bg, (s.x - 5, sy(s.y)), (s.x + 5, sy(s.y))
                )
                pygame.draw.line(
                    self.logical, p.bg, (s.x - 3, sy(s.y - 1)), (s.x + 3, sy(s.y - 1))
                )

    def _draw_explosions(self, g: Game, p: Palette) -> None:
        for e in g.explosions:
            if e is None or not e.step:
                continue
            r = float(e.radius)
            if self.juice:  # dibujo suave entre actualizaciones; la colisión no cambia
                prev = e.previous_radius
                r = prev + (e.radius - prev) * clamp(
                    (g.frame - e.updated + 1) / 5, 0.0, 1.0
                )
            if r < 0.5:
                continue
            pts = [(x, sy(y)) for x, y in octagon(e.x, e.y, r)]
            pygame.draw.polygon(self.logical, p.flash, pts)
            if self.juice:
                pygame.draw.polygon(self.glow, p.flash, pts)
                if e.step < 12 and p.dark:
                    core = [(x, sy(y)) for x, y in octagon(e.x, e.y, r * 0.5)]
                    pygame.draw.polygon(self.glow, (255, 255, 255), core)

    def _draw_smoke(self, p: Palette) -> None:
        layer = self.smoke_layer
        layer.fill((0, 0, 0, 0))
        base = (120, 120, 136) if p.dark else (40, 40, 48)
        for x, y, _, _, life, ttl in self.puffs:
            k = life / ttl
            pygame.draw.circle(
                layer, (*base, int(48 * k)), (int(x), int(sy(y))), 1.5 + (1 - k) * 4.5
            )
        self.logical.blit(layer, (0, 0))

    def _draw_particles(self, g: Game, p: Palette) -> None:
        L, G = self.logical, self.glow
        for x, y, _, _, life, ttl, kind, color in self.particles:
            px, py = int(x), int(sy(y))
            if not (0 <= px < W and 0 <= py < H):
                continue
            k = life / ttl
            if kind == DEBRIS:
                L.set_at((px, py), color)
                continue
            if kind == EMBER:
                c = (255, int(120 + 120 * k), 40)
            elif k > 0.75:
                c = (255, 255, 255)
            elif k > 0.5:
                c = (255, 230, 90)
            elif k > 0.25:
                c = (255, 140, 40)
            else:
                c = (200, 50, 25)
            L.set_at((px, py), c)
            G.fill(c, (px - 1, py - 1, 2, 2))
        for x, y, label, life, chain in self.popups:
            if chain:
                self.text_center(label, x, sy(y), p.flash, glow=True)
            else:
                color = (255, 255, 255) if life % 8 < 6 else p.icbm
                self.mini(label, x, sy(y), color)
                self.mini(label, x, sy(y), scaled(color, 0.6), self.glow)

    def _draw_intro(self, g: Game, p: Palette) -> None:
        self.text_center(
            self.t("player", n=g.current + 1), 128, Y_MAX - 148, p.icbm, glow=True
        )
        self.text_center(
            self.t("points", n=multiplier(g.wave)), 128, Y_MAX - 116, p.icbm, glow=True
        )
        if self.juice:
            self.text_center(
                self.t("wave", n=g.wave), 128, Y_MAX - 184, p.abm, glow=True
            )
        if g.wave <= 3:
            self.text_at(self.t("defend"), 56, 56, p.abm, glow=True)
            if (g.timer // 12) % 2:
                arrow = self._sprite(ARROW_SPRITE, p.abm)
                for c in g.cities:
                    if c.alive:
                        self._blit_c(arrow, c.x, c.y + 10, glow=True)

    def _draw_tally(self, g: Game, p: Palette) -> None:
        t = g.tally
        if t is None:
            return
        pending = any(s.abms for s in g.silos) or any(c.alive for c in g.cities)
        if not (t.abms or t.cities or pending):
            return
        self.text_center(self.t("bonus_points"), 128, Y_MAX - 164, p.icbm, glow=True)
        if t.abms:
            label = str(t.abm_points)
            self.text(label, 96 - len(label) * 8, Y_MAX - 134, p.icbm)
            icon = self._sprite(ABM_ICON, p.abm)
            for i in range(t.abms):
                self.logical.blit(icon, (104 + i * 4, round(sy(131))))
        if t.cities:
            label = str(t.city_points)
            self.text(label, 96 - len(label) * 8, Y_MAX - 100, p.icbm)
            for j, i in enumerate(t.cities):
                sprite = self._sprite(CITY_SPRITES[i % 3], p.city, p.abm)
                self.logical.blit(sprite, (104 + j * 18, round(sy(99))))

    def _draw_the_end(self, g: Game, p: Palette) -> None:
        t = g.timer
        r = 118 * min(1.0, t / 45)
        if t > THE_END_FRAMES - 50:
            r *= max(0.0, (THE_END_FRAMES - t) / 50)
        if r > 1:
            pts = [(x, sy(y)) for x, y in octagon(134, 124, r)]
            pygame.draw.polygon(self.logical, p.flash, pts)
            if self.juice:
                pygame.draw.polygon(self.glow, scaled(p.flash, 0.7), pts)
        if r > 92:
            word = self.t("the_end")
            x, y = 134 - len(word) * 12, 66
            self.text(word, x, y, p.bg, 3, 10)
            if self.juice:
                self.text(word, x, y, (0, 0, 0), 3, 10, surf=self.glow)

    def _title_layers(self, g: Game, p: Palette):
        """Las letras del título viven en capas propias que las explosiones van comiendo."""
        if self.title_layers is None or g.timer < self.title_clock:
            layers = []
            for color in (p.icbm, scaled(p.icbm, 0.55)):
                layer = pygame.Surface((W, H), pygame.SRCALPHA)
                self.text("MISSILE", 28, Y_MAX - 164, color, 4, 4, surf=layer)
                self.text("COMMAND", 28, Y_MAX - 116, color, 4, 4, surf=layer)
                layers.append(layer)
            self.title_layers = tuple(layers)
        self.title_clock = g.timer
        return self.title_layers

    def _draw_title(self, g: Game, p: Palette) -> None:
        layers = self._title_layers(g, p)
        if g.timer < 520:
            self.logical.blit(layers[0], (0, 0))
            if self.juice:
                self.glow.blit(layers[1], (0, 0))
        self._draw_explosions(g, p)
        if g.timer > 30:
            self.text_center(self.t("tribute"), 128, Y_MAX - 60, p.abm, glow=True)
        if (g.frame // 30) % 2:
            self.text_center(self.t("press"), 128, 200, p.city, glow=True)
        else:
            self.text_center(self.t("two"), 128, 214, scaled(p.city, 0.7))

    def _draw_scores(self, g: Game, p: Palette) -> None:
        self.text_center(self.t("high"), 128, Y_MAX - 212, p.icbm, glow=True)
        for i, (name, score) in enumerate(g.high_scores):
            color = p.flash if i == g.new_rank else p.abm
            line = f"{i + 1}   {name:<3}   {score:>7}"
            self.text_center(
                line, 128, Y_MAX - (180 - i * 20), color, glow=i == g.new_rank
            )
        if (g.frame // 30) % 2:
            self.text_center(self.t("press"), 128, 206, p.city, glow=True)

    def _draw_initials(self, g: Game, p: Palette) -> None:
        score = str(g.players[g.entry_player].score if g.players else g.score)
        if g.n_players > 1:
            self.text_center(self.t("player", n=g.entry_player + 1), 128, 2, p.abm)
        self.text_center(score, 128, Y_MAX - 214, p.icbm, 2, 2, glow=True)
        great = self.t("great")
        self.text_center(
            great, 128, Y_MAX - 168, p.icbm, 2 if len(great) <= 15 else 1, 1, glow=True
        )
        for i, letter in enumerate(g.entry):
            ch = INITIALS_ALPHABET[letter]
            x = 84 + i * 32
            current = i == g.entry_pos
            color = p.flash if current else p.abm
            if not current or (g.frame // 8) % 4:
                self.text(
                    ch if ch != " " else "_", x, Y_MAX - 140, color, 3, 3, glow=current
                )
            if current:
                pygame.draw.line(
                    self.logical, p.icbm, (x, Y_MAX - 112), (x + 22, Y_MAX - 112)
                )
        self.text_center(self.t("enter"), 128, Y_MAX - 96, p.icbm)
        self.text_center(self.t("change"), 128, Y_MAX - 80, p.abm)
        self.text_center(self.t("select"), 128, Y_MAX - 64, p.abm)

    def _draw_stats(self, g: Game, p: Palette) -> None:
        player = (
            g.players[min(g.stats_index, len(g.players) - 1)] if g.players else None
        )
        s = player.stats if player else g.stats
        score = player.score if player else g.score
        minutes, seconds = divmod(s.frames // FPS, 60)
        ratio = f"{s.kills / s.shots:.2f}" if s.shots else "-"
        rows = (
            ("st_waves", s.waves), ("st_score", score), ("st_shots", s.shots),
            ("st_kills", s.kills), ("st_icbms", s.icbms), ("st_smarts", s.smarts),
            ("st_fliers", s.fliers), ("st_chain", s.best_chain), ("st_mirvs", s.mirvs),
            ("st_lost", s.cities_lost), ("st_bonus", s.bonus_cities),
            ("st_ratio", ratio), ("st_time", f"{minutes}:{seconds:02d}"),
        )  # fmt: skip
        title = self.t("report")
        if g.n_players > 1:
            title = self.t("player", n=g.stats_index + 1)
        self.text_center(title, 128, 14, p.icbm, glow=True)
        for n, (key, value) in enumerate(rows):
            y = 32 + n * 13
            value = str(value)
            self.text(self.t(key), 12, y, p.abm)
            self.text(value, 244 - len(value) * 8, y, p.city)
        if g.timer > FPS and (g.frame // 30) % 2:
            self.text_center(self.t("press_fire"), 128, 210, p.icbm, glow=True)

    def _draw_hud(self, g: Game, p: Palette) -> None:
        scores = g.player_scores()
        two = len(scores) > 1
        dim = scaled(p.icbm, 0.5)
        for i, value in enumerate(scores):
            label = str(value)
            color = p.icbm if not two or g.attract or i == g.current else dim
            x = 72 - len(label) * 8 if i == 0 else 248 - len(label) * 8
            self.text(label, x, 0, color)
        best = str(max([g.high_scores[0][1] if g.high_scores else 0] + scores))
        self.text(best, 136 - len(best) * 4, 0, p.icbm)
        playing = not g.attract and g.phase in (Phase.PLAY, Phase.INTRO, Phase.TALLY)
        if self.juice and playing and not two:
            label = self.t("wave", n=g.wave)
            self.text(label, 252 - len(label) * 8, 0, p.abm)
        if self.juice and playing and g.reserve:
            self.mini(f"+{g.reserve}", 236 if not two else 20, 10, p.city)
        if self.toast_frames and (self.toast_frames > 20 or self.toast_frames % 4 < 2):
            self.text_center(self.t(self.toast), 128, 12, (255, 255, 255))

    def _draw_box(self, lines: tuple[str, ...], p: Palette) -> None:
        width = max(len(s) for s in lines) * 8 + 24
        height = len(lines) * 12 + 14
        x, y = (W - width) // 2, (H - height) // 2
        box = pygame.Surface((width, height), pygame.SRCALPHA)
        box.fill((0, 0, 0, 205))
        self.logical.blit(box, (x, y))
        pygame.draw.rect(self.logical, p.abm, (x, y, width, height), 1)
        for n, line in enumerate(lines):
            color = p.icbm if n == 0 else (230, 230, 240)
            self.text(line, x + 12, y + 7 + n * 12, color)

    # --- composición ----------------------------------------------------------------

    def _compose(self) -> None:
        size = self.hi.get_size()
        pygame.transform.scale(self.logical, size, self.hi)
        if self.fx_mode == "off" or not self.juice:
            return
        if self.fx_mode == "crt":
            self.hi.blit(self.mask, (0, 0), special_flags=pygame.BLEND_MULT)
        for div, gain in ((2, 0.85), (6, 0.6)):
            small = pygame.transform.smoothscale(self.glow, (W // div, H // div))
            if self._blur is not None:
                small = self._blur(small, 2)
            g = int(255 * gain)
            small.fill((g, g, g), special_flags=pygame.BLEND_MULT)
            self.hi.blit(
                pygame.transform.smoothscale(small, size),
                (0, 0),
                special_flags=pygame.BLEND_ADD,
            )

    def _present(self, screen) -> None:
        ox = oy = 0
        if self.juice and self.shake > 0.3:
            ox = round(self.rng.uniform(-self.shake, self.shake) * self.k)
            oy = round(self.rng.uniform(-self.shake, self.shake) * self.k)
        screen.fill((0, 0, 0))
        screen.blit(self.hi, (self.rect.x + ox, self.rect.y + oy))
        if self.juice and self.flash > 0.02:
            color = scaled(self.flash_rgb, self.flash)
            screen.fill(color, self.rect, special_flags=pygame.BLEND_ADD)


def make_icon():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    for r, color in ((14, (255, 226, 64)), (8, (255, 90, 48)), (3, (255, 255, 255))):
        pygame.draw.polygon(
            icon, color, [(16 + x, 16 - y) for x, y in octagon(0, 0, r)]
        )
    return icon


# =============================================================================
# Render HD: alta resolución, luz suave y nada de píxeles a la vista
# =============================================================================

HD_MAX_HEIGHT = 1080  # el campo se dibuja como mucho a esta altura y luego se escala
HD_PANEL_MIN = 150  # ancho mínimo para mostrar los paneles laterales
HD_MOON = (233, 204)  # arriba a la derecha, lejos de los títulos; ilumina desde ahí

# Cielo y suelo por pareja de oleadas: los cambios de color del original, de noche
HD_SKIES = (
    ((5, 8, 22), (38, 32, 70)),
    ((4, 13, 20), (20, 54, 64)),
    ((12, 6, 26), (58, 30, 74)),
    ((16, 6, 12), (78, 32, 36)),
    ((6, 12, 28), (34, 58, 96)),
    ((4, 16, 15), (24, 64, 52)),
    ((16, 5, 19), (78, 26, 72)),
    ((14, 10, 7), (94, 62, 28)),
    ((13, 15, 22), (74, 78, 92)),
    ((15, 4, 5), (98, 30, 22)),
)
HD_GROUND = (
    ((96, 80, 48), (24, 19, 14)),
    ((88, 82, 50), (21, 21, 14)),
    ((56, 70, 104), (11, 15, 27)),
    ((110, 54, 44), (27, 12, 10)),
    ((100, 84, 50), (27, 21, 12)),
    ((92, 86, 58), (23, 21, 14)),
    ((52, 92, 62), (10, 23, 14)),
    ((66, 96, 56), (13, 23, 10)),
    ((112, 52, 52), (29, 12, 12)),
    ((108, 90, 52), (29, 21, 10)),
)
HD_ENEMY = {
    "red": (255, 106, 74),
    "green": (132, 236, 112),
    "yellow": (255, 206, 94),
    "magenta": (232, 108, 240),
    "black": (214, 218, 234),
}
HD_PLAYER = (112, 214, 255)
HD_TEXT = (236, 234, 228)
HD_MUTED = (140, 150, 172)
HD_WARM = (255, 190, 116)
HD_DANGER = (255, 112, 92)
FIRE_STOPS = (
    (
        (0.0, (255, 244, 220, 255)),
        (0.2, (255, 218, 150, 250)),
        (0.48, (255, 150, 64, 236)),
        (0.74, (226, 82, 36, 196)),
        (0.92, (150, 40, 24, 96)),
        (1.0, (96, 26, 18, 0)),
    ),
    (
        (0.0, (255, 206, 132, 246)),
        (0.3, (252, 152, 70, 232)),
        (0.62, (214, 82, 40, 196)),
        (0.86, (124, 42, 30, 104)),
        (1.0, (70, 32, 26, 0)),
    ),
    (
        (0.0, (206, 112, 66, 206)),
        (0.38, (152, 70, 46, 170)),
        (0.72, (90, 54, 50, 112)),
        (1.0, (56, 50, 54, 0)),
    ),
)
SPARK_RAMP = (
    (0.0, (255, 246, 214)),
    (0.35, (255, 196, 96)),
    (0.7, (240, 110, 40)),
    (1.0, (120, 40, 24)),
)
SMOKE_STOPS = (
    (0.0, (98, 98, 110, 150)),
    (0.55, (82, 82, 94, 90)),
    (1.0, (74, 74, 84, 0)),
)

# Textos que solo usa el render HD: su fuente sí tiene el signo ×
HD_TEXTS: dict[str, tuple[str, str]] = {
    "score": ("SCORE", "PUNTOS"),
    "hi": ("HIGH SCORE", "RÉCORD"),
    "wave_label": ("WAVE", "OLEADA"),
    "mult_label": ("MULTIPLIER", "MULTIPLICADOR"),
    "cities_label": ("CITIES", "CIUDADES"),
    "ammo_label": ("AMMO", "MUNICIÓN"),
    "ammo_inf": ("UNLIMITED", "ILIMITADA"),
    "chain_label": ("BEST CHAIN", "MEJOR CADENA"),
    "help_hint": ("F1  HELP", "F1  AYUDA"),
    "defend": ("DEFEND THE CITIES", "DEFIENDE LAS CIUDADES"),
    "points": ("×{n} POINTS", "PUNTOS ×{n}"),
    "cleared": ("WAVE {n} CLEARED", "OLEADA {n} SUPERADA"),
    "new_high": ("NEW HIGH SCORE", "NUEVO RÉCORD"),
    "demo": ("DEMO", "DEMOSTRACIÓN"),
    "ammo_on": ("I   INFINITE AMMO: ON", "I   MUNICIÓN INFINITA: SÍ"),
    "ammo_off": ("I   INFINITE AMMO: OFF", "I   MUNICIÓN INFINITA: NO"),
    "player": ("PLAYER {n}", "JUGADOR {n}"),
    "abm_bonus": ("UNUSED ABMS", "ABM SOBRANTES"),
    "city_bonus": ("CITIES SAVED", "CIUDADES SALVADAS"),
    "table_inf": ("INFINITE AMMO", "MUNICIÓN INFINITA"),
    "table_arcade": ("ARCADE RULES", "REGLAS DE RECREATIVA"),
}


def mix(a, b, t: float) -> tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def ramp(stops, t: float) -> tuple[int, ...]:
    """Color en la posición t de una rampa [(t0, color), (t1, color), ...]."""
    t = clamp(t, 0.0, 1.0)
    for (t0, c0), (t1, c1) in pairwise(stops):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
    return tuple(stops[-1][1])


def gradient(size, stops):
    """Degradado vertical opaco del tamaño pedido."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    column = pygame.Surface((1, h))
    for y in range(h):
        column.set_at((0, y), ramp(stops, y / max(1, h - 1))[:3])
    return pygame.transform.scale(column, (w, h))


def soft_disc(radius: float, stops, alpha: bool = True):
    """Disco con degradado radial. Con alpha=False es luz para sumar."""
    r = max(1.0, radius)
    size = int(r * 2) + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA if alpha else 0)
    if not alpha:
        surf.fill((0, 0, 0))
    c = size / 2
    steps = max(4, min(int(r), 160))  # anillos de un píxel o poco más: sin bandas
    for i in range(steps, 0, -1):
        t = i / steps
        color = ramp(stops, t)
        pygame.draw.circle(surf, color if alpha else color[:3], (c, c), r * t)
    return surf


def hd_texts() -> list[str]:
    out = []
    for pair in HD_TEXTS.values():
        out.extend(s.format(n=1) for s in pair)
    return out


@dataclass(slots=True, frozen=True)
class HDPalette:
    index: int
    sky_top: tuple[int, int, int]
    sky_mid: tuple[int, int, int]
    horizon: tuple[int, int, int]
    crest: tuple[int, int, int]
    ground: tuple[int, int, int]
    enemy: tuple[int, int, int]
    city: tuple[int, int, int]


def hd_palette(wave: int) -> HDPalette:
    i = ((wave - 1) // 2) % len(WAVE_COLORS)
    names = WAVE_COLORS[i]
    top, horizon = HD_SKIES[i]
    crest, ground = HD_GROUND[i]
    enemy = HD_ENEMY.get(names[2], HD_ENEMY["red"])
    city = mix((30, 34, 48), RGB_PHOSPHOR[names[3]], 0.2)
    return HDPalette(
        i, top, mix(top, horizon, 0.45), horizon, crest, ground, enemy, city
    )


class HDRenderer:
    """Render en alta resolución: cielo nocturno, luz suave, bolas de fuego con
    humo, ciudades con ventanas encendidas y torretas que siguen a la mira."""

    style = "hd"
    # Piezas de la caché que dependen de la paleta; el índice va siempre al final
    palette_pieces = frozenset(
        ("bg", "terrain", "city", "bunker", "cloud", "mini", "panel_city")
    )

    def __init__(self, juice: bool = True, lang: str = "en") -> None:
        self.juice = juice
        self.lang = lang if lang in LANGS else "en"
        self.size = (0, 0)
        self.rect = pygame.Rect(0, 0, W, H)
        self.s = 1.0
        self.ls = 0.25
        self.pf = None
        self.light = self.light_big = None
        self.side = False
        self.cache: dict = {}
        self.fonts: dict = {}
        self.rooms: dict = {}
        self.texts: dict = {}
        self.rng = random.Random(2026)
        self.particles: list[
            list
        ] = []  # x, y, vx, vy, vida, total, tipo, color, x0, y0
        self.puffs: list[list] = []  # x, y, vx, vy, vida, total, tamaño, alfa
        self.popups: list[list] = []  # x, y, texto, vida, total, grande
        self.rings: list[list] = []  # x, y, edad
        self.muzzles: list[list] = []  # x, y, vida
        self.smoking: dict[tuple[int, int], float] = {}
        self.scorches: list[tuple[float, float, float]] = []
        self.bomb_trails: dict[int, list[tuple[float, float]]] = {}
        self.shake = 0.0
        self.flash = 0.0
        self.flash_rgb = (255, 170, 100)
        self.toast, self.toast_frames = "", 0
        self.title_layers: tuple | None = None
        self.title_clock = -1
        self.palette = hd_palette(1)
        self.prep: tuple[int, list] = (-1, [])
        self.recent = [self.palette.index]
        r = random.Random(11)
        self.twinkles = [
            (
                r.uniform(4, W - 4),
                r.uniform(70, 226),
                r.random() * math.tau,
                r.uniform(0.5, 1.0),
            )
            for _ in range(36)
        ]
        self.clouds = [
            (
                n * (W + 90) / 4 + r.uniform(0, 30),
                r.uniform(120, 192),
                r.uniform(0.012, 0.036),
                n,
            )
            for n in range(4)
        ]
        self.heights = list(TERRAIN)
        for _ in range(2):  # el mismo relieve del original, suavizado
            h = self.heights
            self.heights = [
                (
                    h[max(0, i - 2)]
                    + 4 * h[max(0, i - 1)]
                    + 6 * h[i]
                    + 4 * h[min(W - 1, i + 1)]
                    + h[min(W - 1, i + 2)]
                )
                / 16
                for i in range(W)
            ]

    # --- textos, conmutadores y coordenadas ------------------------------------

    def t(self, key: str, **values) -> str:
        return tr(key, self.lang, **values)

    def ht(self, key: str, **values) -> str:
        text = HD_TEXTS[key][1 if self.lang == "es" else 0]
        return text.format(**values) if values else text

    def say(self, key: str) -> None:
        self.toast, self.toast_frames = key, 110

    def set_juice(self, on: bool) -> None:
        self.juice = on
        for bucket in (
            self.particles,
            self.puffs,
            self.popups,
            self.rings,
            self.muzzles,
        ):
            bucket.clear()
        self.shake = self.flash = 0.0
        self.say("fx_on" if on else "fx_off")

    def toggle_lang(self) -> None:
        self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        self.title_layers = None
        self.say("lang")

    def to_game(self, pos) -> tuple[float, float]:
        r = self.rect
        return ((pos[0] - r.x) * W / r.w, Y_MAX - (pos[1] - r.y) * H / r.h)

    @property
    def unit(self) -> float:
        """Píxeles de pantalla por unidad del juego, para el ratón relativo."""
        return self.rect.h / H

    def P(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.s, (Y_MAX - y) * self.s)

    def L(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.ls, (Y_MAX - y) * self.ls)

    def _layout(self, size) -> None:
        if size == self.size and self.pf is not None:
            return
        self.size = sw, sh = size
        ph, pw = sh, round(sh * W / H)
        if pw > sw:
            pw, ph = sw, round(sw * H / W)
        self.rect = pygame.Rect((sw - pw) // 2, (sh - ph) // 2, max(1, pw), max(1, ph))
        rh = max(H, min(ph, HD_MAX_HEIGHT))
        rw = round(rh * W / H)
        self.pf = pygame.Surface((rw, rh)).convert()
        self.light = pygame.Surface((max(1, rw // 4), max(1, rh // 4))).convert()
        self.light_big = pygame.Surface((rw, rh)).convert()
        self.s = rh / H
        self.ls = self.light.get_height() / H
        self.side = self.rect.x >= HD_PANEL_MIN
        self.cache.clear()
        self.texts.clear()
        self.title_layers = None
        self.prep = (-1, [])
        for temp in range(3):  # las bolas de fuego de todos los tamaños, ya hechas:
            for b in range(1, 28):  # sin tirones en la primera explosión de cada uno
                self._fireball(temp, b / 2)
        for b in range(1, 11):
            self._puff(b / 2)

    # --- tipografía ------------------------------------------------------------

    def font(self, px: float):
        px = max(9, int(px))
        f = self.fonts.get(px)
        if f is None:
            f = self.fonts[px] = pygame.font.Font(None, px)
        return f

    def label(self, text: str, px: float, color, shadow: bool = True):
        key = (text, int(px), color, shadow)
        surf = self.texts.get(key)
        if surf is None:
            if len(self.texts) > 900:
                self.texts.clear()
            f = self.font(px)
            body = f.render(text, True, color)
            # SDL_ttf baja la línea base cuando una tilde sobresale por arriba. Aquí
            # todas las etiquetas de un tamaño comparten alto y línea base: RATÓN
            # queda alineada con APUNTAR sea cual sea el anclaje.
            room, box = self._font_box(f)
            tops = [g[3] for g in f.metrics(text) if g]
            top = room - max(0, max(tops, default=0) - f.get_ascent())
            off = max(1, int(px) // 16) if shadow else 0
            h = max(box, top + body.get_height()) + off
            surf = pygame.Surface((body.get_width() + off, h), pygame.SRCALPHA)
            if shadow:
                back = f.render(text, True, (0, 0, 0))
                back.set_alpha(150)
                surf.blit(back, (off, top + off))
            surf.blit(body, (0, top))
            self.texts[key] = surf
        return surf

    def _font_box(self, f) -> tuple[int, int]:
        """Lo que una mayúscula con tilde sobresale por encima del ascent y el alto
        común de las etiquetas de esa fuente, con sitio para la tilde."""
        box = self.rooms.get(f)
        if box is None:
            top = max(g[3] for g in f.metrics("ÁÉÍÓÚÑÜ") if g)
            room = max(0, top - f.get_ascent())
            box = self.rooms[f] = (
                room,
                f.render("A", True, (0, 0, 0)).get_height() + room + 1,
            )
        return box

    def put(
        self, target, text, px, color, pos, anchor="center", alpha=255, shadow=True
    ):
        surf = self.label(text, px, color, shadow)
        if alpha < 255:
            surf = surf.copy()
            surf.set_alpha(max(0, int(alpha)))
        rect = surf.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
        target.blit(surf, rect)
        return rect

    # --- piezas cacheadas --------------------------------------------------------

    def _sky_stops(self):
        p = self.palette
        return (
            (0.0, p.sky_top),
            (0.62, p.sky_mid),
            (0.92, p.horizon),
            (1.0, p.horizon),
        )

    def _sky_at(self, y: float) -> tuple[int, int, int]:
        return ramp(self._sky_stops(), (Y_MAX - y) / H)[:3]

    def _background(self):
        p = self.palette
        key = ("bg", p.index)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        rw, rh = self.pf.get_size()
        surf = gradient((rw, rh), self._sky_stops()).convert()
        rng = random.Random(5)
        band = pygame.Surface((64, 58))
        for yy in range(58):  # la Vía Láctea, una banda tenue en diagonal
            for xx in range(64):
                d = abs(yy / 57 - 0.08 - xx / 63 * 0.62)
                k = max(0.0, 1.0 - d * 5.5) ** 2 * (0.7 + 0.3 * rng.random())
                band.set_at((xx, yy), (int(20 * k), int(18 * k), int(28 * k)))
        surf.blit(
            pygame.transform.smoothscale(band, (rw, rh)),
            (0, 0),
            special_flags=pygame.BLEND_ADD,
        )
        for _ in range(520):
            x, y = rng.random() * rw, rng.random() * rh * 0.8
            if abs(y / rh - 0.08 - x / rw * 0.62) > 0.12 and rng.random() < 0.5:
                continue
            b = 40 + rng.random() ** 3 * 170
            size = 2 if b > 165 and self.s > 2.5 else 1
            surf.fill(
                (int(b), int(b * 0.96), int(min(255, b * 1.1))),
                (int(x), int(y), size, size),
            )
        self._moon(surf)
        for layer, (base, amp, freq, dark) in enumerate(
            ((22, 26, 0.045, 0.42), (13, 17, 0.07, 0.7))
        ):
            pts = [(0, rh)]
            for x in range(0, W + 2, 2):
                wave = 0.55 + 0.25 * math.sin(x * freq + layer * 1.7)
                wave += 0.2 * math.sin(x * freq * 2.7 + layer * 4.1)
                pts.append(self.P(x, base + amp * wave))
            pts.append((rw, rh))
            color = mix(p.horizon, (6, 7, 12), dark)
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.aalines(surf, mix(color, p.horizon, 0.35), False, pts[1:-1])
        self.cache[key] = surf
        return surf

    def _moon(self, surf) -> None:
        """Luna creciente: cara iluminada a la derecha y el resto casi negro, con
        la luz cenicienta justa para adivinar el disco."""
        cx, cy = self.P(*HD_MOON)
        r = 6.5 * self.s
        halo = soft_disc(
            r * 1.5,
            ((0, (34, 38, 52)), (0.22, (16, 18, 26)), (1, (0, 0, 0))),
            alpha=False,
        )
        halo = pygame.transform.smoothscale(
            halo, (halo.get_width() * 4, halo.get_height() * 4)
        )
        surf.blit(
            halo,
            (cx - halo.get_width() / 2, cy - halo.get_height() / 2),
            special_flags=pygame.BLEND_ADD,
        )
        k = 3  # dibujada a triple tamaño y reducida: bordes y terminador suaves
        big_r = r * k
        size = int(big_r * 2) + 4 * k
        c = size / 2
        disc = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(disc, (214, 214, 202, 255), (c, c), big_r)
        rng = random.Random(9)
        for _ in range(9):  # mares
            a, d = rng.random() * math.tau, rng.random() * big_r * 0.7
            spot = (c + math.cos(a) * d, c + math.sin(a) * d)
            pygame.draw.circle(
                disc, (192, 192, 182, 255), spot, big_r * rng.uniform(0.08, 0.22)
            )
        shade = pygame.Surface((size, size))
        shade.fill((255, 255, 255))
        pygame.draw.circle(
            shade, (40, 44, 62), (c - big_r * 0.5, c - big_r * 0.12), big_r * 0.98
        )
        blur = max(1, size // 5)
        shade = pygame.transform.smoothscale(
            pygame.transform.smoothscale(shade, (blur, blur)), (size, size)
        )
        disc.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        out = int(size / k)
        disc = pygame.transform.smoothscale(disc, (out, out))
        surf.blit(disc, (cx - out / 2, cy - out / 2))

    def _cloud(self, n: int):
        """Cúmulo nocturno: base plana, cumbres redondas, cuerpo en sombra y un
        filo plateado en el lado de la luna."""
        p = self.palette
        key = ("cloud", n, p.index)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        rng = random.Random(100 + n)
        scale = (0.85, 1.15, 0.7, 1.0)[n % 4]
        w, h = 66 * scale * self.s, 26 * scale * self.s
        surf = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        body = mix(p.sky_mid, (8, 10, 18), 0.3)
        rim = mix(p.horizon, (176, 184, 210), 0.42)
        base, count = h * 0.7, 9 + n % 3
        puffs = []
        for j in range(count):
            f = (j + 0.5) / count
            rr = (
                h
                * (0.13 + 0.2 * math.sin(math.pi * f) ** 1.3)
                * rng.uniform(0.85, 1.15)
            )
            x = w * (0.16 + 0.68 * f + rng.uniform(-0.025, 0.025))
            puffs.append((x, base - rr * rng.uniform(0.3, 0.75), rr))
        for x, y, rr in puffs:  # el filo de luz, algo desplazado hacia la luna
            blob = soft_disc(
                rr * 1.3, ((0, (*rim, 84)), (0.7, (*rim, 44)), (1, (*rim, 0)))
            )
            surf.blit(
                blob,
                (
                    x + rr * 0.2 - blob.get_width() / 2,
                    y - rr * 0.24 - blob.get_height() / 2,
                ),
            )
        for x, y, rr in puffs:  # el cuerpo tapa casi todo el filo: solo queda el borde
            blob = soft_disc(
                rr * 1.22, ((0, (*body, 150)), (0.62, (*body, 104)), (1, (*body, 0)))
            )
            surf.blit(blob, (x - blob.get_width() / 2, y - blob.get_height() / 2))
        self.cache[key] = surf
        return surf

    def _terrain(self):
        p = self.palette
        key = ("terrain", p.index)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        rw, rh = self.pf.get_size()
        hs = self.heights
        top = [(0.0, self.P(0, hs[0])[1])] + [self.P(x + 0.5, hs[x]) for x in range(W)]
        top.append((float(rw), self.P(W, hs[-1])[1]))
        surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
        pygame.draw.polygon(surf, (255, 255, 255, 255), top + [(rw, rh), (0, rh)])
        crest_y = self.P(0, max(hs))[1] / rh
        grad = gradient(
            (rw, rh), ((0.0, p.crest), (crest_y, p.crest), (1.0, p.ground))
        ).convert_alpha()
        surf.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        shade, glint, mottle = self._relief()
        surf.blit(mottle, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(glint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        rng = random.Random(3)
        for _ in range(int(rw * 2.4)):  # grano del suelo
            x = rng.random() * (rw - 1)
            y0 = self.P(0, hs[min(W - 1, int(x / self.s))])[1] + 2
            y = rng.uniform(y0, rh - 1)
            c = surf.get_at((int(x), int(y)))
            if c.a:
                k = rng.uniform(0.8, 1.2)
                surf.set_at(
                    (int(x), int(y)),
                    (
                        min(255, int(c.r * k)),
                        min(255, int(c.g * k)),
                        min(255, int(c.b * k)),
                        255,
                    ),
                )
        pygame.draw.aalines(surf, mix(p.crest, (255, 255, 255), 0.16), False, top)
        y0 = max(0, int(min(y for _, y in top)) - 2)  # solo la franja con suelo
        surf = self.cache[key] = (surf.subsurface((0, y0, rw, rh - y0)).copy(), y0)
        return surf

    def _relief(self):
        """Luz de luna sobre el relieve: las laderas que miran a la luna se platean,
        las otras se hunden en sombra, y unas manchas rompen el color plano."""
        maps = self.cache.get(("relief",))
        if maps is not None:
            return maps
        size = self.pf.get_size()
        hs = self.heights
        shade, glint = pygame.Surface((W, H)), pygame.Surface((W, H))
        shade.fill((255, 255, 255))
        glint.fill((0, 0, 0))
        for x in range(W):
            slope = (
                hs[max(0, x - 2)] - hs[min(W - 1, x + 2)]
            ) / 4  # > 0: baja hacia la luna
            light = clamp(0.2 + slope * 0.9, -1.0, 1.0)
            row = int(Y_MAX - hs[x])
            for y in range(max(0, row), H):
                d = y - row
                if light > 0:
                    v = 64 * light * math.exp(-d / 3.2)
                    glint.set_at((x, y), (int(v * 0.72), int(v * 0.8), int(v)))
                else:
                    m = int(255 * (1 + 0.5 * light * math.exp(-d / 6)))
                    shade.set_at((x, y), (m, m, m))
        rng = random.Random(21)
        small = pygame.Surface((48, 44))
        for y in range(44):
            for x in range(48):
                m = int(255 * rng.uniform(0.8, 1.0))
                small.set_at((x, y), (m, m, int(m * rng.uniform(0.97, 1.0))))
        maps = (
            pygame.transform.smoothscale(shade, size),
            pygame.transform.smoothscale(glint, size),
            pygame.transform.smoothscale(small, size),
        )
        self.cache[("relief",)] = maps
        return maps

    def _city(self, i: int, alive: bool):
        """Silueta de ciudad dibujada a triple resolución y reducida: bordes suaves."""
        p = self.palette
        key = ("city", i, alive, p.index)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        k = self.s * 3
        bw, bh = 18, 15
        big = pygame.Surface(
            (max(1, int(bw * k)), max(1, int(bh * k))), pygame.SRCALPHA
        )
        ground = bh * k
        rng = random.Random(i * 7919 + 17)
        if alive:
            x, tallest = -8.4, (0.0, 1.0, 0.0)
            face = mix(p.city, (118, 128, 158), 0.2)
            shade = mix(p.city, (0, 0, 0), 0.45)
            while x < 8.0:
                w = min(rng.uniform(1.9, 3.6), 8.4 - x)
                if w < 1.1:
                    break
                centre = 1 - abs(x + w / 2) / 9
                h = rng.uniform(3.2, 5.6) + 6.4 * centre * rng.uniform(0.4, 1.0)
                rect = pygame.Rect(
                    int((x + 9) * k),
                    int(ground - h * k),
                    max(1, int(w * k)),
                    int(h * k) + 1,
                )
                big.blit(gradient(rect.size, ((0, face), (1, shade))), rect)
                edge = mix(face, (210, 220, 245), 0.35)
                pygame.draw.line(
                    big, edge, rect.topleft, rect.bottomleft, max(1, int(k * 0.12))
                )
                cols, rows = max(1, int(w / 0.95)), max(1, int(h / 1.15))
                for row in range(rows):
                    for col in range(cols):
                        wx = rect.x + (col + 0.3) * rect.w / cols
                        wy = rect.y + (row + 0.35) * rect.h / rows * 0.96
                        if wy + 0.5 * k >= rect.bottom - 0.4 * k:
                            continue
                        if rng.random() < 0.52:
                            warm = (
                                255,
                                int(rng.uniform(168, 214)),
                                int(rng.uniform(88, 140)),
                            )
                            lit = warm if rng.random() < 0.86 else (172, 212, 255)
                            color = mix(lit, face, rng.uniform(0.0, 0.35))
                        else:
                            color = mix(shade, (10, 12, 20), 0.5)
                        big.fill(
                            color,
                            (
                                int(wx),
                                int(wy),
                                max(1, int(0.42 * k)),
                                max(1, int(0.5 * k)),
                            ),
                        )
                if rng.random() < 0.5:
                    roof = (
                        int(rect.x + rect.w * 0.2),
                        int(rect.y - 0.6 * k),
                        max(1, int(rect.w * 0.35)),
                        int(0.6 * k) + 1,
                    )
                    big.fill(shade, roof)
                if h > tallest[2]:
                    tallest = (x + w * 0.55, w, h)
                x += w + rng.uniform(0.12, 0.45)
            ax = (tallest[0] + 9) * k
            mast = mix(p.city, (180, 190, 214), 0.4)
            pygame.draw.line(
                big,
                mast,
                (ax, ground - tallest[2] * k),
                (ax, ground - (tallest[2] + 2.4) * k),
                max(1, int(k * 0.16)),
            )
            self.cache[("antenna", i)] = (tallest[0], tallest[2] + 2.4)
        else:
            pts, x = [(0.0, ground)], 0.4
            while x < bw - 0.4:
                pts.append((x * k, ground - rng.uniform(0.4, 2.6) * k))
                x += rng.uniform(0.6, 1.4)
            pts.append(((bw - 0.4) * k, ground))
            pygame.draw.polygon(big, (36, 31, 31), pts)
            for _ in range(4):
                sx, w, h = (
                    rng.uniform(1.5, bw - 3) * k,
                    rng.uniform(1.0, 2.0) * k,
                    rng.uniform(1.5, 4.2) * k,
                )
                stub = [
                    (sx, ground),
                    (sx, ground - h),
                    (sx + w * 0.4, ground - h * 0.74),
                    (sx + w, ground - h * 0.9),
                    (sx + w, ground),
                ]
                pygame.draw.polygon(big, (48, 42, 42), stub)
            self.cache[("embers", i)] = [
                (rng.uniform(-7, 7), rng.uniform(0.3, 2.4), rng.random() * math.tau)
                for _ in range(8)
            ]
        surf = pygame.transform.smoothscale(
            big, (max(1, int(bw * self.s)), max(1, int(bh * self.s)))
        )
        self.cache[key] = surf
        return surf

    def _bunker(self):
        key = ("bunker", self.palette.index)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        k = self.s * 3
        bw, bh = 12, 6
        big = pygame.Surface((int(bw * k), int(bh * k)), pygame.SRCALPHA)
        cx, base = bw * k / 2, bh * k
        slab = pygame.Rect(
            int(cx - 5.2 * k), int(base - 1.3 * k), int(10.4 * k), int(1.3 * k)
        )
        big.blit(gradient(slab.size, ((0, (126, 128, 136)), (1, (62, 64, 72)))), slab)
        r = 3.6 * k
        dome = pygame.Surface((int(2 * r) + 2, int(r) + 2), pygame.SRCALPHA)
        pygame.draw.circle(dome, (255, 255, 255, 255), (r + 1, r + 1), r)
        tint = gradient(
            dome.get_size(), ((0, (176, 180, 190)), (1, (82, 86, 96)))
        ).convert_alpha()
        dome.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        big.blit(dome, (cx - r - 1, base - 1.3 * k - r - 1))
        pygame.draw.line(
            big,
            (60, 62, 70),
            (cx - r * 0.9, base - 1.3 * k),
            (cx + r * 0.9, base - 1.3 * k),
            max(1, int(k * 0.2)),
        )
        pygame.draw.arc(
            big,
            (210, 214, 224),
            (cx - r, base - 1.3 * k - r, 2 * r, 2 * r),
            math.pi * 0.25,
            math.pi * 0.75,
            max(1, int(k * 0.18)),
        )
        surf = pygame.transform.smoothscale(big, (int(bw * self.s), int(bh * self.s)))
        self.cache[key] = surf
        return surf

    def _crater(self):
        key = ("crater",)
        surf = self.cache.get(key)
        if surf is None:
            k = self.s * 3
            big = pygame.Surface((int(14 * k), int(5 * k)), pygame.SRCALPHA)
            pygame.draw.ellipse(big, (22, 18, 18, 255), (k * 1, k * 1.6, k * 12, k * 3))
            pygame.draw.ellipse(big, (10, 8, 8, 255), (k * 3, k * 2.4, k * 8, k * 1.8))
            rng = random.Random(4)
            for _ in range(7):
                x, y = rng.uniform(1.5, 12.5) * k, rng.uniform(1.0, 2.5) * k
                pygame.draw.circle(
                    big, (54, 46, 44, 255), (x, y), k * rng.uniform(0.4, 0.8)
                )
            surf = pygame.transform.smoothscale(
                big, (int(14 * self.s), int(5 * self.s))
            )
            self.cache[key] = surf
        return surf

    def _flier(self, kind: int, left: bool):
        key = ("flier", kind, left)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        k = self.s * 3
        w, h = (16, 9) if kind == BOMBER else (15, 8)
        big = pygame.Surface((int(w * k), int(h * k)), pygame.SRCALPHA)

        def pt(x, y):
            return (x * k, y * k)

        if kind == BOMBER:  # vista cenital, morro a la derecha
            wing = [pt(6.4, 4.5), pt(9.6, 4.5), pt(6.0, 0.4), pt(4.4, 0.4)]
            pygame.draw.polygon(big, (70, 76, 92), wing)
            pygame.draw.polygon(big, (70, 76, 92), [(x, h * k - y) for x, y in wing])
            pygame.draw.polygon(
                big,
                (64, 70, 86),
                [pt(1.0, 4.5), pt(2.6, 4.5), pt(1.2, 2.2), pt(0.4, 2.2)],
            )
            pygame.draw.polygon(
                big,
                (64, 70, 86),
                [pt(1.0, 4.5), pt(2.6, 4.5), pt(1.2, 6.8), pt(0.4, 6.8)],
            )
            pygame.draw.ellipse(
                big, (98, 104, 122), (k * 0.6, k * 3.6, k * 14.6, k * 1.8)
            )
            pygame.draw.ellipse(
                big, (150, 158, 178), (k * 3.0, k * 3.75, k * 10.0, k * 0.5)
            )
            pygame.draw.ellipse(
                big, (70, 150, 196), (k * 12.2, k * 3.9, k * 2.0, k * 1.2)
            )
        else:  # satélite: cuerpo dorado y dos paneles solares
            for x0 in (0.4, 9.6):
                panel = pygame.Rect(
                    int(x0 * k), int(2.6 * k), int(5.0 * k), int(2.8 * k)
                )
                pygame.draw.rect(big, (34, 58, 116), panel)
                for gx in range(1, 4):
                    pygame.draw.line(
                        big,
                        (70, 110, 190),
                        (panel.x + panel.w * gx / 4, panel.y),
                        (panel.x + panel.w * gx / 4, panel.bottom),
                        max(1, int(k * 0.1)),
                    )
                pygame.draw.line(
                    big,
                    (70, 110, 190),
                    (panel.x, panel.centery),
                    (panel.right, panel.centery),
                    max(1, int(k * 0.1)),
                )
            body = pygame.Rect(int(5.4 * k), int(1.8 * k), int(4.2 * k), int(4.4 * k))
            big.blit(
                gradient(body.size, ((0, (214, 180, 96)), (1, (130, 98, 46)))), body
            )
            pygame.draw.line(
                big,
                (190, 190, 200),
                (7.5 * k, 1.8 * k),
                (7.5 * k, 0.3 * k),
                max(1, int(k * 0.15)),
            )
        surf = pygame.transform.smoothscale(big, (int(w * self.s), int(h * self.s)))
        if left:
            surf = pygame.transform.flip(surf, True, False)
        self.cache[key] = surf
        return surf

    def _fireball(self, temp: int, r: float):
        b = max(1, round(r * 2))
        key = ("fire", temp, b)
        surf = self.cache.get(key)
        if surf is None:
            surf = self.cache[key] = soft_disc(b / 2 * self.s * 1.06, FIRE_STOPS[temp])
        return surf

    def _puff(self, r: float):
        b = max(1, round(r * 2))
        key = ("puff", b)
        surf = self.cache.get(key)
        if surf is None:
            surf = self.cache[key] = soft_disc(b / 2 * self.s, SMOKE_STOPS)
        return surf

    def _glow(self, color, r: float):
        b = max(1, round(r * 4))
        key = ("glow", color, b)
        surf = self.cache.get(key)
        if surf is None:
            stops = ((0, (255, 255, 255, 255)), (0.25, (*color, 220)), (1, (*color, 0)))
            surf = self.cache[key] = soft_disc(b / 4 * self.s, stops)
        return surf

    def _light_sprite(self, color, radius_px: float):
        b = max(1, int(radius_px / 2))
        color = tuple(c & ~3 for c in color)  # pocos colores distintos: caché acotada
        key = ("light", color, b)
        surf = self.cache.get(key)
        if surf is None:
            stops = ((0, color), (0.4, mix(color, (0, 0, 0), 0.55)), (1, (0, 0, 0)))
            surf = self.cache[key] = soft_disc(b * 2, stops, alpha=False)
        return surf

    def _add_light(self, x: float, y: float, color, r: float) -> None:
        spr = self._light_sprite(color, r * self.ls)
        lx, ly = self.L(x, y)
        self.light.blit(
            spr,
            (lx - spr.get_width() / 2, ly - spr.get_height() / 2),
            special_flags=pygame.BLEND_ADD,
        )

    def _vignette(self):
        key = ("vignette",)
        surf = self.cache.get(key)
        if surf is None:
            small = pygame.Surface((64, 58))
            for y in range(58):
                for x in range(64):
                    d = ((x + 0.5) / 32 - 1) ** 2 * 0.9 + ((y + 0.5) / 29 - 1) ** 2
                    v = int(255 * clamp(1.08 - 0.42 * d**1.25, 0.6, 1.0))
                    small.set_at((x, y), (v, v, v))
            surf = self.cache[key] = pygame.transform.smoothscale(
                small, self.pf.get_size()
            )
        return surf

    # --- efectos: se alimentan de los sucesos del juego, un frame cada vez --------

    def tick(self, g: Game) -> None:
        if self.juice:
            for f in g.fx:
                self._on_fx(f, g)
        self.shake *= 0.85
        self.flash *= 0.85
        if self.toast_frames:
            self.toast_frames -= 1
        if g.phase is Phase.TITLE and self.title_layers is not None:
            for e in g.explosions:  # las explosiones se comen las letras del título
                if e is not None and e.radius:
                    for layer in self.title_layers:
                        pygame.draw.circle(
                            layer,
                            (0, 0, 0, 0),
                            self.P(e.x, e.y),
                            e.radius * self.s * 1.05,
                        )
        if g.phase is Phase.TALLY and self.pf is not None:
            self._prepare(hd_palette(g.wave + 1))
        if not self.juice:
            return
        alive = []
        for p in self.particles:
            p[8], p[9] = p[0], p[1]
            p[0] += p[2]
            p[1] += p[3]
            if p[6] == SPARK:
                p[2] *= 0.985
                p[3] = p[3] * 0.985 - 0.03
            elif p[6] == DEBRIS:
                p[3] -= 0.06
                ground = self.heights[int(clamp(p[0], 0, W - 1))]
                if p[1] <= ground:
                    p[1], p[3], p[2] = ground, -p[3] * 0.3, p[2] * 0.55
            else:
                p[2] *= 0.99
                p[3] = p[3] * 0.99 - 0.004
            p[4] -= 1
            if p[4] > 0:
                alive.append(p)
        self.particles = alive[-1600:]
        for q in self.puffs:
            q[0] += q[2]
            q[1] += q[3]
            q[4] -= 1
        self.puffs = [q for q in self.puffs if q[4] > 0][-700:]
        for pop in self.popups:
            pop[1] = min(pop[1] + 0.3, POPUP_CEILING)
            pop[3] -= 1
        self.popups = [pop for pop in self.popups if pop[3] > 0]
        for ring in self.rings:
            ring[2] += 1
        self.rings = [ring for ring in self.rings if ring[2] < 18]
        for m in self.muzzles:
            m[2] -= 1
        self.muzzles = [m for m in self.muzzles if m[2] > 0]
        rng = self.rng
        if g.phase in FIELD_PHASES or g.phase in (
            Phase.REGEN,
            Phase.PLAYER_OUT,
            Phase.THE_END,
        ):
            for x, y in self.smoking:
                if rng.random() < 0.32:
                    self.puffs.append([
                        x + rng.uniform(-4, 4), y + rng.uniform(1, 4), rng.uniform(-0.03, 0.08),
                        rng.uniform(0.12, 0.26), rng.randrange(130, 200), 200, rng.uniform(1.1, 1.8), 70,
                    ])  # fmt: skip
            for m in g.incoming:
                if (
                    m is not None
                    and m.kind == ICBM
                    and (g.frame + m.serial * 3) % 4 == 0
                ):
                    self.puffs.append(
                        [m.x, m.y, rng.uniform(-0.02, 0.02), 0.015, 70, 70, 0.7, 38]
                    )
        live = set()
        for m in g.incoming:
            if m is not None and m.kind == SMART:
                live.add(m.serial)
                trail = self.bomb_trails.setdefault(m.serial, [])
                if g.frame % 2 == 0:
                    trail.append((m.x, m.y))
                    del trail[:-8]
        for serial in list(self.bomb_trails):
            if serial not in live:
                del self.bomb_trails[serial]

    def _use_palette(self, palette: HDPalette) -> None:
        """Cambia de paleta y suelta las piezas de las viejas. Guarda las tres
        últimas, porque a dos jugadores las oleadas se alternan."""
        if palette.index != self.palette.index:
            self.recent = [palette.index] + [
                i for i in self.recent if i != palette.index
            ][:2]
            keep = {*self.recent, self.prep[0]}
            for key in [
                k
                for k in self.cache
                if k[0] in self.palette_pieces and k[-1] not in keep
            ]:
                del self.cache[key]
        self.palette = palette

    def _prepare(self, palette: HDPalette) -> None:
        """Durante el recuento deja hecha, una pieza por frame, la escena con los
        colores de la oleada siguiente: el cambio de paleta llega sin tirón."""
        if palette.index == self.palette.index:
            return
        if self.prep[0] != palette.index:
            jobs = [self._background, self._terrain, self._bunker]
            jobs += [
                lambda i=i, a=a: self._city(i, a)
                for i in range(len(CITIES))
                for a in (True, False)
            ]
            jobs += [lambda n=n: self._cloud(n) for n in range(len(self.clouds))]
            self.prep = (palette.index, jobs)
        if self.prep[1]:
            current, self.palette = self.palette, palette
            try:
                self.prep[1].pop(0)()
            finally:
                self.palette = current

    def _burst(
        self, x, y, n, speed, kind=SPARK, colors=None, life=(18, 40), up=0.0
    ) -> None:
        r = self.rng
        for _ in range(n):
            a = r.random() * math.tau
            v = speed * (0.3 + r.random())
            ttl = r.randrange(*life)
            color = r.choice(colors) if colors else None
            vx, vy = math.cos(a) * v, math.sin(a) * v + up
            self.particles.append([x, y, vx, vy, ttl, ttl, kind, color, x, y])

    def _flash(self, rgb, amount) -> None:
        if amount > self.flash:
            self.flash, self.flash_rgb = amount, rgb

    def _on_fx(self, f: FX, g: Game) -> None:
        name, rng = f.name, self.rng
        if name == "boom":
            if not f.a and g.phase is not Phase.TITLE:
                self.rings.append([f.x, f.y, 0])
            if f.a and f.y < LOWEST:  # impacto en el suelo: una nube de polvo
                for _ in range(6):
                    self.puffs.append([
                        f.x + rng.uniform(-3, 3), f.y + rng.uniform(0, 3), rng.uniform(-0.12, 0.12),
                        rng.uniform(0.04, 0.16), rng.randrange(80, 140), 140, rng.uniform(1.2, 2.2), 80,
                    ])  # fmt: skip
        elif name == "kill":
            self._burst(
                f.x,
                f.y,
                (10, 18, 26)[f.c - 1],
                1.2 if f.c == KILL_ICBM else 1.6,
                life=(14, 34),
            )
            self._burst(
                f.x,
                f.y,
                4 if f.c == KILL_ICBM else 9,
                0.5,
                EMBER,
                life=(40, 80),
                up=0.25,
            )
            for _ in range(3):
                self.puffs.append([
                    f.x + rng.uniform(-2, 2), f.y + rng.uniform(-2, 2), rng.uniform(-0.05, 0.05),
                    rng.uniform(0.02, 0.08), rng.randrange(70, 120), 120, rng.uniform(1.0, 1.8), 55,
                ])  # fmt: skip
            if f.a:
                small = [pop for pop in self.popups if not pop[5]]
                if len(small) >= 6:  # en las cadenas largas, sin muro de números
                    self.popups.remove(small[0])
                self.popups.append(
                    [f.x, min(f.y + 8, POPUP_CEILING), f"+{f.a}", 48, 48, False]
                )
            if f.b >= 3:
                label = self.t("chain", n=f.b)
                self.popups.append(
                    [f.x, min(f.y + 15, POPUP_CEILING), label, 84, 84, True]
                )
                self.shake = max(self.shake, min(0.5 + f.b * 0.22, 2.0))
            if f.c == KILL_FLIER:
                self.shake = max(self.shake, 1.2)
        elif name in ("city", "silo"):
            tint = self.palette.city if name == "city" else (110, 112, 120)
            colors = [mix(tint, (0, 0, 0), 0.3), (52, 46, 44), (84, 76, 72)]
            self._burst(f.x, f.y + 2, 44, 1.6, DEBRIS, colors, (70, 140), up=1.1)
            self._burst(f.x, f.y + 3, 26, 2.0, SPARK, life=(20, 46), up=0.7)
            self._burst(f.x, f.y + 4, 18, 0.6, EMBER, life=(60, 120), up=0.5)
            for _ in range(10):
                self.puffs.append([
                    f.x + rng.uniform(-5, 5), f.y + rng.uniform(0, 6), rng.uniform(-0.1, 0.1),
                    rng.uniform(0.06, 0.2), rng.randrange(120, 200), 200, rng.uniform(1.6, 3.0), 90,
                ])  # fmt: skip
            self.shake = max(self.shake, 2.6 if name == "city" else 3.0)
            self._flash((255, 140, 70), 0.16)
            ground = f.y - 5 if name == "city" else f.y
            self.smoking[(int(f.x), int(ground) + 2)] = 1.0
            self.scorches.append((f.x, ground + 1, 9 if name == "city" else 7))
        elif name in ("abm", "low"):
            self.muzzles.append([f.x, f.y, 8])
            self._burst(f.x, f.y + 3, 4, 0.7, SPARK, life=(6, 14), up=0.8)
        elif name in ("mirv", "flier_fire"):
            self._burst(f.x, f.y, 8, 0.8, SPARK, life=(8, 18))
        elif name == "bonus_city":
            self._burst(f.x, f.y + 6, 26, 0.6, EMBER, None, (50, 90), up=0.5)
            self.rings.append([f.x, f.y + 3, 0])
        elif name == "game_over":
            self.shake = 4.0
            self._flash((255, 120, 60), 0.3)
        elif name in ("wave", "start", "player_out"):
            self.smoking.clear()
            self.scorches.clear()
            self.puffs.clear()

    # --- dibujo -------------------------------------------------------------------

    def draw(self, g: Game, screen, overlay: str | None = None) -> None:
        self._layout(screen.get_size())
        menu = g.phase in (Phase.TITLE, Phase.SCORES, Phase.INITIALS, Phase.STATS)
        self._use_palette(hd_palette(1 if menu else g.wave))
        self.pf.blit(self._background(), (0, 0))
        self.light.fill((0, 0, 0))
        field = not menu or g.phase is Phase.TITLE
        if field:
            self._trail_glow(g)
        if self.juice:
            self._searchlights(g, menu)
        self._sky_life(g)
        self._ground(g, menu)
        if self.juice:
            self._smoke()
        if g.phase is Phase.TITLE:
            self._title_art(g)
        if field:
            self._field(g)
        if g.phase is Phase.THE_END:
            self._the_end_fire(g)
        pygame.transform.smoothscale(self.light, self.pf.get_size(), self.light_big)
        self.pf.blit(self.light_big, (0, 0), special_flags=pygame.BLEND_ADD)
        self.pf.blit(self._vignette(), (0, 0), special_flags=pygame.BLEND_MULT)
        self._phase_text(g)
        if self.juice:
            self._popups()
        if not self.side:
            self._hud_top(g)
        if overlay:
            self._overlay(overlay)
        self._present(screen, g)

    def _beam(self):
        """Haz de foco a la resolución de la capa de luz: se abre y se apaga con la
        distancia y no tiene bordes duros. Apunta hacia arriba desde el pie."""
        surf = self.cache.get(("beam",))
        if surf is None:
            length = 170 * self.ls
            w, h = int(length * 0.24) + 4, int(length) + 2
            surf = pygame.Surface((w, h))
            surf.fill((0, 0, 0))
            for y in range(h):
                d = (h - 1 - y) / (h - 1)  # 0 en el foco, 1 en la punta
                along = (1 - d) ** 1.6 * min(1.0, d * 14)
                half = 0.7 + 0.11 * d * length
                for x in range(w):
                    u = abs(x + 0.5 - w / 2) / half
                    if u < 1:
                        k = along * (1 - u * u) ** 1.5
                        surf.set_at((x, y), (int(24 * k), int(30 * k), int(44 * k)))
            self.cache[("beam",)] = surf
        return surf

    def _searchlights(self, g: Game, menu: bool) -> None:
        """Dos focos antiaéreos barren el cielo despacio, tenues como en la niebla."""
        beam = self._beam()
        half = beam.get_height() / 2
        for i, side, phase in ((1, 1, 0.0), (4, -1, 2.3)):
            c = g.cities[i]
            if not (menu or c.alive):
                continue
            angle = side * 0.2 + 0.34 * math.sin(g.frame * 0.0065 + phase)
            spr = pygame.transform.rotozoom(beam, -math.degrees(angle), 1.0)
            sx, sy = self.L(c.x + side * 2, c.y + 3)
            cx, cy = sx + half * math.sin(angle), sy - half * math.cos(angle)
            pos = (cx - spr.get_width() / 2, cy - spr.get_height() / 2)
            self.light.blit(spr, pos, special_flags=pygame.BLEND_ADD)

    def _trail_glow(self, g: Game) -> None:
        """Halo tenue a lo largo de cada estela, más vivo cerca de la cabeza. Va el
        primero en la capa de luz: sobre negro, pintar es sumar."""
        enemy = self.palette.enemy
        trails = [(m, enemy) for m in g.incoming if m is not None and m.kind == ICBM]
        trails += [(a, HD_PLAYER) for a in g.abms]
        for m, color in trails:
            a, b = self.L(m.ox, m.oy), self.L(m.x, m.y)
            mid = (a[0] + (b[0] - a[0]) * 0.6, a[1] + (b[1] - a[1]) * 0.6)
            pygame.draw.aaline(self.light, scaled(color, 0.07), a, b)
            pygame.draw.aaline(self.light, scaled(color, 0.14), mid, b)

    def _sky_life(self, g: Game) -> None:
        pf = self.pf
        for x, y, phase, b in self.twinkles:
            v = b * (0.55 + 0.45 * math.sin(phase + g.frame * 0.045))
            px, py = self.P(x, y)
            pf.fill(
                (int(196 * v), int(202 * v), int(232 * v)), (int(px), int(py), 2, 2)
            )
            if b > 0.9 and v > 0.82:
                arm = self.s * 1.1
                glint = (int(120 * v), int(126 * v), int(150 * v))
                pygame.draw.aaline(
                    pf, glint, (px - arm, py + 1), (px + arm + 2, py + 1)
                )
                pygame.draw.aaline(
                    pf, glint, (px + 1, py - arm), (px + 1, py + arm + 2)
                )
        for x0, y, speed, n in self.clouds:
            x = (x0 + g.frame * speed) % (W + 90) - 45
            spr = self._cloud(n)
            cx, cy = self.P(x, y)
            pf.blit(spr, (cx - spr.get_width() / 2, cy - spr.get_height() / 2))

    def _ground(self, g: Game, menu: bool) -> None:
        pf = self.pf
        ground, y0 = self._terrain()
        pf.blit(ground, (0, y0))
        for x, y, r in self.scorches:
            spr = self._scorch(r)
            cx, cy = self.P(x, y)
            pf.blit(spr, (cx - spr.get_width() / 2, cy - spr.get_height() / 2))
        hidden = set(g.tally.cities) if g.tally is not None and not menu else set()
        regen = set(g.regen_cities) if g.phase is Phase.REGEN else set()
        for i, c in enumerate(g.cities):
            if i in hidden:
                continue
            alive = menu or c.alive
            pf.blit(self._city(i, alive), self.P(c.x - 9, c.y + 10))
            base = c.y - 5
            if alive:
                self._add_light(c.x, c.y - 1, (34, 26, 14), 11)
                ax, ah = self.cache.get(("antenna", i), (0.0, 8.0))
                if (g.frame + i * 23) % 90 < 45:
                    pygame.draw.circle(
                        pf,
                        (255, 74, 62),
                        self.P(c.x + ax, base + ah),
                        max(1.0, 0.32 * self.s),
                    )
                    self._add_light(c.x + ax, base + ah, (90, 20, 14), 2.4)
                if i in regen:
                    pulse = 0.5 + 0.5 * math.sin(g.frame * 0.25)
                    self._add_light(c.x, c.y, scaled((70, 110, 60), pulse), 14)
            else:
                for ex, ey, ph in self.cache.get(("embers", i), ()):
                    v = 0.5 + 0.5 * math.sin(ph + g.frame * 0.15)
                    pos = self.P(c.x + ex, base + ey)
                    pygame.draw.circle(
                        pf,
                        mix((120, 30, 10), (255, 150, 60), v),
                        pos,
                        max(1.0, 0.28 * self.s),
                    )
                    self._add_light(c.x + ex, base + ey, scaled((90, 40, 14), v), 2.4)
        for s in g.silos:
            self._silo(g, s, menu)

    def _scorch(self, r: float):
        key = ("scorch", int(r))
        surf = self.cache.get(key)
        if surf is None:
            disc = soft_disc(
                r * self.s,
                ((0, (8, 6, 6, 170)), (0.6, (14, 10, 8, 100)), (1, (20, 14, 10, 0))),
            )
            size = (disc.get_width(), max(1, int(disc.get_height() * 0.38)))
            surf = self.cache[key] = pygame.transform.smoothscale(disc, size)
        return surf

    def _silo(self, g: Game, s: Silo, menu: bool) -> None:
        pf = self.pf
        if not (menu or s.alive):
            pf.blit(self._crater(), self.P(s.x - 7, s.y + 2.5))
            for n in range(4):
                v = 0.5 + 0.5 * math.sin(g.frame * 0.13 + n * 1.7 + s.x)
                ex, ey = s.x - 4 + n * 2.6, s.y + 0.6
                pygame.draw.circle(
                    pf,
                    mix((120, 30, 10), (255, 140, 50), v),
                    self.P(ex, ey),
                    max(1.0, 0.3 * self.s),
                )
                self._add_light(ex, ey, scaled((90, 40, 14), v), 2.6)
            return
        bx, by = s.x, s.y + 2.2
        angle = 0.0
        if not menu and g.phase in (Phase.PLAY, Phase.INTRO, Phase.DEMO):
            dx, dy = g.cursor[0] - bx, g.cursor[1] - by
            angle = clamp(math.atan2(dx, max(0.5, dy)), -1.3, 1.3)
        ux, uy = math.sin(angle), math.cos(angle)
        nx, ny = uy, -ux
        tip = (bx + ux * 5.2, by + uy * 5.2)
        quad = [
            (bx + nx * 0.7, by + ny * 0.7),
            (tip[0] + nx * 0.56, tip[1] + ny * 0.56),
            (tip[0] - nx * 0.56, tip[1] - ny * 0.56),
            (bx - nx * 0.7, by - ny * 0.7),
        ]
        pts = [self.P(*q) for q in quad]
        pygame.draw.polygon(pf, (124, 130, 146), pts)
        pygame.draw.aalines(pf, (190, 198, 214), True, pts)
        pf.blit(self._bunker(), self.P(s.x - 6, s.y + 6))
        if menu or g.infinite or s.abms > 3:
            color = (90, 255, 150)
        else:
            color = (255, 190, 70) if s.abms else (255, 80, 70)
        lamp = (s.x, s.y + 4.9)
        pygame.draw.circle(pf, color, self.P(*lamp), max(1.0, 0.32 * self.s))
        self._add_light(*lamp, scaled(color, 0.3), 2.0)
        for mx, _, life in self.muzzles:
            if abs(mx - s.x) < 1:
                glow = self._glow((150, 210, 255), 1.6 * life / 8 + 0.4)
                cx, cy = self.P(*tip)
                pf.blit(glow, (cx - glow.get_width() / 2, cy - glow.get_height() / 2))
                self._add_light(*tip, scaled((120, 170, 210), life / 8), 6)
        playing = g.phase in (Phase.PLAY, Phase.INTRO, Phase.DEMO, Phase.TALLY)
        if not menu and not g.infinite and playing:
            col = HD_TEXT if s.abms > 3 else HD_WARM if s.abms else HD_DANGER
            self.put(pf, str(s.abms), 4.6 * self.s, col, self.P(s.x, s.y - 6.2))

    def _smoke(self) -> None:
        pf = self.pf
        for x, y, _, _, life, ttl, size, alpha in self.puffs:
            k = life / ttl
            spr = self._puff(size * (1.6 - 0.6 * k))
            spr.set_alpha(int(alpha * k))
            cx, cy = self.P(x, y)
            pf.blit(spr, (cx - spr.get_width() / 2, cy - spr.get_height() / 2))

    def _field(self, g: Game) -> None:
        enemy = self.palette.enemy
        for m in g.incoming:
            if m is not None and m.kind == ICBM:
                self._trail(m, enemy)
        for a in g.abms:
            self._trail(a, HD_PLAYER)
            self._marker(a.tx, a.ty, g.frame)
        for x, y, age in self.rings:
            f = age / 18
            col = mix(self._sky_at(y), (200, 236, 255), 0.6 * (1 - f))
            ring_line(self.pf, col, self.P(x, y), (4 + age * 1.4) * self.s)
        self._explosions(g)
        for m in g.incoming:
            if m is not None and m.kind == SMART:
                self._bomb(g, m)
        if g.flier is not None:
            self._flier_draw(g, g.flier)
        if self.juice:
            self._particles()
        if g.cursor_visible:
            self._crosshair(g)

    def _trail(self, m: Missile, color) -> None:
        pf = self.pf
        x0, y0, x1, y1 = m.ox, m.oy, m.x, m.y
        prev = self.P(x0, y0)
        for k in range(1, 7):
            f = k / 6
            y = y0 + (y1 - y0) * f
            cur = self.P(x0 + (x1 - x0) * f, y)
            pygame.draw.aaline(
                pf, mix(self._sky_at(y), color, 0.12 + 0.88 * f**1.7), prev, cur
            )
            prev = cur
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1.0
        back = min(10.0, n)
        tail = self.P(x1 - dx / n * back, y1 - dy / n * back)
        ox, oy = dy / n * 0.8, dx / n * 0.8
        pygame.draw.aaline(
            pf, color, (tail[0] + ox, tail[1] + oy), (prev[0] + ox, prev[1] + oy)
        )
        glow = self._glow(color, 1.3)
        pf.blit(glow, (prev[0] - glow.get_width() / 2, prev[1] - glow.get_height() / 2))
        self._add_light(x1, y1, scaled(color, 0.4), 3.5)

    def _marker(self, tx: float, ty: float, frame: int) -> None:
        x, y = self.P(tx, ty)
        r = (1.8 + 0.4 * math.sin(frame * 0.3)) * self.s
        ring_line(self.pf, HD_PLAYER, (x, y), r)
        d = r * 0.55
        pygame.draw.aaline(self.pf, HD_PLAYER, (x - d, y - d), (x + d, y + d))
        pygame.draw.aaline(self.pf, HD_PLAYER, (x - d, y + d), (x + d, y - d))

    def _explosions(self, g: Game) -> None:
        pf = self.pf
        for e in g.explosions:
            if e is None or not e.step:
                continue
            prev = e.previous_radius
            r = prev + (e.radius - prev) * clamp(
                (g.frame - e.updated + 1) / 5, 0.0, 1.0
            )
            if r < 0.3:
                continue
            temp = 0 if e.step < 9 else 1 if e.step < 18 else 2
            cx, cy = self.P(e.x, e.y)
            if r > 2:  # bolsas de fuego alrededor: forma irregular y viva
                seed = (e.x * 37 + e.y * 11) % 100 / 16
                for j in range(3):
                    a = seed + j * 2.094 + g.frame * 0.03
                    blob = self._fireball(
                        min(2, temp + 1) if j == 2 else temp, r * 0.55
                    )
                    bx, by = (
                        cx + math.cos(a) * r * 0.42 * self.s,
                        cy + math.sin(a) * r * 0.42 * self.s,
                    )
                    pf.blit(
                        blob, (bx - blob.get_width() / 2, by - blob.get_height() / 2)
                    )
            spr = self._fireball(temp, r)
            pf.blit(spr, (cx - spr.get_width() / 2, cy - spr.get_height() / 2))
            level = max(1, 8 - e.step // 4)
            self._add_light(e.x, e.y, scaled((150, 92, 44), level / 8), r * 3.2)

    def _bomb(self, g: Game, m: Missile) -> None:
        pf = self.pf
        trail = self.bomb_trails.get(m.serial, [])
        for n, (tx, ty) in enumerate(trail):
            f = (n + 1) / (len(trail) + 1)
            col = mix(self._sky_at(ty), (196, 96, 255), 0.55 * f)
            pygame.draw.circle(pf, col, self.P(tx, ty), max(1.0, 1.3 * self.s * f))
        cx, cy = self.P(m.x, m.y)
        rot = g.frame * 0.15 + m.serial
        pts = []
        for j in range(8):
            a = rot + j * math.pi / 4
            rr = (3.6 if j % 2 == 0 else 1.4) * self.s
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        pygame.draw.polygon(pf, (150, 70, 222), pts)
        pygame.draw.aalines(pf, (232, 176, 255), True, pts)
        pygame.draw.circle(pf, (255, 232, 255), (cx, cy), max(1.0, 1.0 * self.s))
        self._add_light(m.x, m.y, (90, 36, 120), 7)

    def _flier_draw(self, g: Game, f: Flier) -> None:
        pf = self.pf
        spr = self._flier(f.kind, f.direction < 0)
        cx, cy = self.P(f.x, f.y)
        pf.blit(spr, (cx - spr.get_width() / 2, cy - spr.get_height() / 2))
        dot = max(1.0, 0.32 * self.s)
        if f.kind == BOMBER:
            for side, color in ((1, (255, 72, 60)), (-1, (80, 255, 124))):
                wx, wy = f.x - 0.5 * f.direction, f.y + side * 4.1
                pygame.draw.circle(pf, color, self.P(wx, wy), dot)
                self._add_light(wx, wy, scaled(color, 0.25), 2.0)
            if g.frame % 50 < 4:
                tail = (f.x - 7 * f.direction, f.y)
                pygame.draw.circle(pf, (255, 255, 255), self.P(*tail), dot * 1.3)
                self._add_light(*tail, (110, 110, 110), 3)
            self._add_light(f.x - 6 * f.direction, f.y, (90, 50, 20), 3)
        else:
            if g.frame % 60 < 30:
                pygame.draw.circle(pf, (255, 80, 70), self.P(f.x, f.y + 3.7), dot)
                self._add_light(f.x, f.y + 3.7, (100, 24, 18), 2.4)
            self._add_light(f.x, f.y, (36, 46, 76), 6)

    def _particles(self) -> None:
        pf = self.pf
        for x, y, _, _, life, ttl, kind, color, x0, y0 in self.particles:
            k = life / ttl
            here = self.P(x, y)
            if kind == SPARK:
                pygame.draw.aaline(pf, ramp(SPARK_RAMP, 1 - k), self.P(x0, y0), here)
                if k > 0.5:
                    self._add_light(x, y, scaled((120, 80, 40), k), 1.6)
            elif kind == DEBRIS:
                pygame.draw.circle(pf, color, here, max(1.0, 0.45 * self.s))
            else:
                pygame.draw.circle(
                    pf,
                    mix((255, 90, 30), (255, 210, 110), k),
                    here,
                    max(1.0, 0.3 * self.s),
                )
                self._add_light(x, y, scaled((110, 50, 20), k), 1.8)

    def _crosshair(self, g: Game) -> None:
        pf = self.pf
        x, y = self.P(*g.cursor)
        r = 3.4 * self.s
        ring_line(pf, HD_PLAYER, (x, y), r)
        rot = g.frame * 0.04
        for j in range(4):
            a = rot + j * math.pi / 2
            ca, sa = math.cos(a), math.sin(a)
            pygame.draw.aaline(
                pf,
                HD_PLAYER,
                (x + ca * r * 0.55, y + sa * r * 0.55),
                (x + ca * r * 1.45, y + sa * r * 1.45),
            )
        pygame.draw.circle(pf, (220, 244, 255), (x, y), max(1.0, 0.35 * self.s))
        self._add_light(*g.cursor, (20, 50, 70), 4)

    # --- título, fases y paneles ---------------------------------------------------

    def _title_word(self, word: str, px: float):
        f = self.font(px)
        chars = [f.render(ch, True, (255, 255, 255)) for ch in word]
        gap = px * 0.06
        width = sum(c.get_width() for c in chars) + gap * (len(chars) - 1)
        surf = pygame.Surface(
            (int(width) + 2, max(c.get_height() for c in chars)), pygame.SRCALPHA
        )
        x = 0.0
        for c in chars:
            surf.blit(c, (round(x), 0))
            x += c.get_width() + gap
        stops = ((0, (255, 228, 172)), (0.5, (255, 152, 76)), (1, (192, 62, 42)))
        surf.blit(
            gradient(surf.get_size(), stops).convert_alpha(),
            (0, 0),
            special_flags=pygame.BLEND_RGBA_MULT,
        )
        return surf

    def _title_art(self, g: Game) -> None:
        if self.title_layers is None or g.timer < self.title_clock:
            rw, rh = self.pf.get_size()
            text = pygame.Surface((rw, rh), pygame.SRCALPHA)
            for word, y in (("MISSILE", 147), ("COMMAND", 99)):
                surf = self._title_word(word, rh * 0.155)
                text.blit(surf, surf.get_rect(center=self.P(128, y)))
            halo = pygame.Surface((rw, rh))
            halo.fill((0, 0, 0))
            halo.blit(text, (0, 0))
            halo = pygame.transform.smoothscale(
                pygame.transform.smoothscale(halo, (rw // 10, rh // 10)), (rw, rh)
            )
            halo.fill((150, 150, 150), special_flags=pygame.BLEND_MULT)
            self.title_layers = (text, halo)
        self.title_clock = g.timer
        if g.timer < 520:
            self.pf.blit(self.title_layers[1], (0, 0), special_flags=pygame.BLEND_ADD)
            self.pf.blit(self.title_layers[0], (0, 0))

    def _dim(self, alpha: int) -> None:
        key = ("dim", alpha)
        surf = self.cache.get(key)
        if surf is None:
            surf = pygame.Surface(self.pf.get_size(), pygame.SRCALPHA)
            surf.fill((4, 5, 10, alpha))
            self.cache[key] = surf
        self.pf.blit(surf, (0, 0))

    def _panel(self, rect, alpha: int = 215) -> None:
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = int(min(rect.w, rect.h) * 0.06)
        pygame.draw.rect(
            surf, (10, 12, 22, alpha), surf.get_rect(), border_radius=radius
        )
        width = max(1, int(self.s * 0.35))
        pygame.draw.rect(
            surf, (*HD_PLAYER, 110), surf.get_rect(), width=width, border_radius=radius
        )
        self.pf.blit(surf, rect)

    def _phase_text(self, g: Game) -> None:
        handler = {
            Phase.INTRO: self._intro,
            Phase.TALLY: self._tally,
            Phase.REGEN: self._regen,
            Phase.PLAYER_OUT: self._player_out,
            Phase.THE_END: self._the_end_text,
            Phase.DEMO: self._demo,
            Phase.TITLE: self._title_text,
            Phase.SCORES: self._scores,
            Phase.INITIALS: self._initials,
            Phase.STATS: self._stats,
        }.get(g.phase)
        if handler is not None:
            handler(g)

    def _fade(self, t: int, total: int, edge: int = 16) -> int:
        return int(
            255 * clamp(t / edge, 0.0, 1.0) * clamp((total - t) / edge, 0.0, 1.0)
        )

    def _intro(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        a = self._fade(g.timer, INTRO_FRAMES)
        y = rh * 0.34
        if g.n_players > 1:
            self.put(
                pf,
                self.ht("player", n=g.current + 1),
                rh * 0.04,
                HD_PLAYER,
                (rw / 2, y - rh * 0.09),
                alpha=a,
            )
        self.put(pf, self.t("wave", n=g.wave), rh * 0.1, HD_WARM, (rw / 2, y), alpha=a)
        self.put(
            pf,
            self.ht("points", n=multiplier(g.wave)),
            rh * 0.045,
            HD_TEXT,
            (rw / 2, y + rh * 0.075),
            alpha=a,
        )
        if g.wave <= 3:
            self.put(
                pf,
                self.ht("defend"),
                rh * 0.04,
                HD_PLAYER,
                (rw / 2, self.P(0, 64)[1]),
                alpha=a,
            )
            bob = math.sin(g.frame * 0.15) * 1.2
            for c in g.cities:
                if c.alive:
                    x, y0 = self.P(c.x, c.y + 15 + bob)
                    d = 1.6 * self.s
                    pygame.draw.aaline(pf, HD_PLAYER, (x - d, y0 - d), (x, y0))
                    pygame.draw.aaline(pf, HD_PLAYER, (x, y0), (x + d, y0 - d))

    def _tally(self, g: Game) -> None:
        t = g.tally
        if t is None:
            return
        pf, (rw, rh) = self.pf, self.pf.get_size()
        self.put(
            pf,
            self.ht("cleared", n=g.wave),
            rh * 0.07,
            HD_WARM,
            (rw / 2, rh * 0.25),
            alpha=self._fade(g.timer, 10**6, 12),
        )
        rows = []
        if not g.infinite:
            rows.append(("abm_bonus", t.abm_points, t.abms, None))
        if t.cities or t.stage >= 1:
            rows.append(("city_bonus", t.city_points, len(t.cities), t.cities))
        for n, (key, points, count, cities) in enumerate(rows):
            y = rh * (0.4 + n * 0.14)
            self.put(
                pf,
                self.ht(key),
                rh * 0.03,
                HD_MUTED,
                (rw * 0.08, y - rh * 0.045),
                "midleft",
            )
            self.put(pf, str(points), rh * 0.055, HD_TEXT, (rw * 0.92, y), "midright")
            if cities is None:
                for j in range(count):
                    x = rw * 0.08 + j * rh * 0.019
                    pygame.draw.line(
                        pf,
                        HD_PLAYER,
                        (x, y + rh * 0.018),
                        (x, y - rh * 0.012),
                        max(1, int(self.s * 0.5)),
                    )
                    pygame.draw.circle(
                        pf,
                        (220, 244, 255),
                        (x, y - rh * 0.014),
                        max(1.0, self.s * 0.35),
                    )
            else:
                for j, i in enumerate(cities):
                    icon = self._mini_city(i)
                    pf.blit(
                        icon,
                        icon.get_rect(
                            midleft=(rw * 0.08 + j * icon.get_width() * 1.05, y)
                        ),
                    )

    def _mini_city(self, i: int):
        key = ("mini", i, self.palette.index)
        surf = self.cache.get(key)
        if surf is None:
            big = self._city(i, True)
            surf = pygame.transform.smoothscale(
                big, (int(big.get_width() * 0.75), int(big.get_height() * 0.75))
            )
            self.cache[key] = surf
        return surf

    def _panel_city(self, i: int, alive: bool, width: float):
        """La misma ciudad del campo, en miniatura para el panel; las caídas, en ruinas."""
        w = max(8, int(width))
        key = ("panel_city", i, alive, w, self.palette.index)
        surf = self.cache.get(key)
        if surf is None:
            big = self._city(i, alive)
            h = max(6, round(w * big.get_height() / big.get_width()))
            surf = self.cache[key] = pygame.transform.smoothscale(big, (w, h))
        return surf

    def _regen(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        a = int(160 + 95 * math.sin(g.timer * 0.18))
        self.put(
            pf,
            self.t("bonus_city"),
            rh * 0.075,
            (140, 255, 170),
            (rw / 2, rh * 0.3),
            alpha=a,
        )

    def _player_out(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        a = self._fade(g.timer, REGEN_FRAMES)
        self.put(
            pf,
            self.ht("player", n=g.current + 1),
            rh * 0.045,
            HD_PLAYER,
            (rw / 2, rh * 0.3),
            alpha=a,
        )
        self.put(
            pf, self.t("game_over"), rh * 0.09, HD_WARM, (rw / 2, rh * 0.39), alpha=a
        )

    def _the_end_fire(self, g: Game) -> None:
        t = g.timer
        grow = clamp(t / 50, 0.0, 1.0)
        fade = clamp((THE_END_FRAMES - t) / 60, 0.0, 1.0)
        a = 120 * grow / 255  # velo rojizo: mezcla con (20, 4, 2) al 47 % como mucho
        if a > 0:
            k = int(255 * (1 - a))
            self.pf.fill((k, k, k), special_flags=pygame.BLEND_MULT)
            self.pf.fill(
                (int(20 * a), int(4 * a), int(2 * a)), special_flags=pygame.BLEND_ADD
            )
        r = 118 * grow * fade
        if r > 1:
            base = self.cache.get(("end_fire",))
            if base is None:
                base = self.cache[("end_fire",)] = soft_disc(160, FIRE_STOPS[0])
            size = int(r * 2 * self.s)
            spr = pygame.transform.smoothscale(base, (size, size))
            cx, cy = self.P(128, 118)
            self.pf.blit(spr, (cx - size / 2, cy - size / 2))
            self._add_light(128, 118, (120, 60, 24), r * 1.6)

    def _the_end_text(self, g: Game) -> None:
        if g.timer > 28:
            a = self._fade(g.timer - 28, THE_END_FRAMES - 60, 24)
            rh = self.pf.get_height()
            self.put(
                self.pf,
                self.t("the_end"),
                rh * 0.17,
                (44, 10, 6),
                self.P(128, 118),
                alpha=a,
                shadow=False,
            )

    def _demo(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        self.put(pf, self.ht("demo"), rh * 0.03, HD_MUTED, (rw / 2, rh * 0.075))
        if (g.frame // 30) % 2:
            self.put(pf, self.t("press"), rh * 0.04, HD_TEXT, (rw / 2, rh * 0.13))

    def _title_text(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        if g.timer > 30:
            self.put(pf, self.t("tribute"), rh * 0.04, HD_PLAYER, (rw / 2, rh * 0.64))
        if (g.frame // 30) % 2:
            self.put(pf, self.t("press"), rh * 0.045, HD_TEXT, (rw / 2, rh * 0.72))
        else:
            self.put(pf, self.t("two"), rh * 0.036, HD_MUTED, (rw / 2, rh * 0.72))
        key = "ammo_on" if g.infinite else "ammo_off"
        self.put(
            pf,
            self.ht(key),
            rh * 0.03,
            HD_WARM if g.infinite else HD_MUTED,
            (rw / 2, rh * 0.78),
        )

    def _scores(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        self._dim(150)
        self.put(pf, self.t("high"), rh * 0.075, HD_WARM, (rw / 2, rh * 0.16))
        table = self.ht("table_inf" if g.infinite else "table_arcade")
        self.put(pf, table, rh * 0.032, HD_MUTED, (rw / 2, rh * 0.225))
        medals = ((255, 214, 110), (214, 218, 230), (220, 156, 100))
        for i, (name, score) in enumerate(g.high_scores):
            y = rh * (0.33 + i * 0.085)
            color = HD_WARM if i == g.new_rank else HD_TEXT
            self.put(
                pf,
                str(i + 1),
                rh * 0.05,
                medals[i] if i < 3 else HD_MUTED,
                (rw * 0.22, y),
            )
            self.put(pf, name, rh * 0.05, color, (rw * 0.34, y), "midleft")
            self.put(pf, str(score), rh * 0.05, color, (rw * 0.8, y), "midright")
        if (g.frame // 30) % 2:
            self.put(pf, self.t("press"), rh * 0.04, HD_TEXT, (rw / 2, rh * 0.84))

    def _initials(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        self._dim(150)
        if g.n_players > 1:
            self.put(
                pf,
                self.ht("player", n=g.entry_player + 1),
                rh * 0.04,
                HD_PLAYER,
                (rw / 2, rh * 0.1),
            )
        score = g.players[g.entry_player].score if g.players else g.score
        self.put(pf, self.ht("new_high"), rh * 0.07, HD_WARM, (rw / 2, rh * 0.18))
        self.put(pf, str(score), rh * 0.085, HD_TEXT, (rw / 2, rh * 0.28))
        box, gap = rh * 0.13, rh * 0.04
        x0 = rw / 2 - 1.5 * box - gap
        for i, letter in enumerate(g.entry):
            rect = pygame.Rect(
                int(x0 + i * (box + gap)), int(rh * 0.38), int(box), int(box * 1.15)
            )
            current = i == g.entry_pos
            pygame.draw.rect(pf, (14, 16, 28), rect, border_radius=int(box * 0.12))
            pulse = 2 + (g.frame // 8) % 2 if current else 1
            border = HD_PLAYER if current else (70, 80, 102)
            pygame.draw.rect(
                pf,
                border,
                rect,
                width=max(1, int(pulse * self.s * 0.3)),
                border_radius=int(box * 0.12),
            )
            ch = INITIALS_ALPHABET[letter]
            self.put(
                pf,
                ch if ch != " " else "_",
                box * 0.8,
                HD_PLAYER if current else HD_TEXT,
                rect.center,
            )
        for n, key in enumerate(("enter", "change", "select")):
            self.put(
                pf,
                self.t(key),
                rh * 0.034,
                HD_TEXT if n == 0 else HD_MUTED,
                (rw / 2, rh * (0.64 + n * 0.055)),
            )

    def _stats(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        self._dim(150)
        player = (
            g.players[min(g.stats_index, len(g.players) - 1)] if g.players else None
        )
        s = player.stats if player else g.stats
        score = player.score if player else g.score
        minutes, seconds = divmod(s.frames // FPS, 60)
        rows = (
            ("st_waves", s.waves), ("st_score", score), ("st_shots", s.shots),
            ("st_kills", s.kills), ("st_icbms", s.icbms), ("st_smarts", s.smarts),
            ("st_fliers", s.fliers), ("st_chain", s.best_chain), ("st_mirvs", s.mirvs),
            ("st_lost", s.cities_lost), ("st_bonus", s.bonus_cities),
            ("st_ratio", f"{s.kills / s.shots:.2f}" if s.shots else "-"),
            ("st_time", f"{minutes}:{seconds:02d}"),
        )  # fmt: skip
        panel = pygame.Rect(
            int(rw * 0.08), int(rh * 0.06), int(rw * 0.84), int(rh * 0.86)
        )
        self._panel(panel)
        title = (
            self.ht("player", n=g.stats_index + 1)
            if g.n_players > 1
            else self.t("report")
        )
        self.put(pf, title, rh * 0.055, HD_WARM, (rw / 2, panel.y + rh * 0.06))
        for n, (key, value) in enumerate(rows):
            y = panel.y + rh * (0.14 + n * 0.052)
            self.put(
                pf,
                self.t(key).strip(),
                rh * 0.032,
                HD_MUTED,
                (
                    panel.x
                    + rh * 0.05
                    + (rh * 0.03 if self.t(key).startswith(" ") else 0),
                    y,
                ),
                "midleft",
            )
            self.put(
                pf,
                str(value),
                rh * 0.036,
                HD_TEXT,
                (panel.right - rh * 0.05, y),
                "midright",
            )
        if g.timer > FPS and (g.frame // 30) % 2:
            self.put(
                pf,
                self.t("press_fire"),
                rh * 0.036,
                HD_WARM,
                (rw / 2, panel.bottom - rh * 0.04),
            )

    def _popups(self) -> None:
        rh = self.pf.get_height()
        for x, y, text, life, ttl, big in self.popups:
            a = min(1.0, life / (ttl * 0.4))
            if big:
                self.put(self.pf, text, rh * 0.05, HD_WARM, self.P(x, y), alpha=255 * a)
            else:
                self.put(
                    self.pf,
                    text,
                    rh * 0.026,
                    (226, 228, 236),
                    self.P(x, y),
                    alpha=210 * a,
                )

    def _hud_top(self, g: Game) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        px, y = rh * 0.04, rh * 0.035
        scores = g.player_scores()
        for i, value in enumerate(scores):
            active = g.attract or len(scores) == 1 or i == g.current
            pos, anchor = (
                ((rw * 0.03, y), "midleft") if i == 0 else ((rw * 0.97, y), "midright")
            )
            self.put(pf, str(value), px, HD_TEXT if active else HD_MUTED, pos, anchor)
        best = max([g.high_scores[0][1] if g.high_scores else 0] + scores)
        self.put(pf, str(best), px, HD_WARM, (rw / 2, y))
        if (
            len(scores) == 1
            and not g.attract
            and g.phase in (Phase.PLAY, Phase.INTRO, Phase.TALLY)
        ):
            self.put(
                pf,
                self.t("wave", n=g.wave),
                px * 0.8,
                HD_MUTED,
                (rw * 0.97, y),
                "midright",
            )

    def _overlay(self, kind: str) -> None:
        pf, (rw, rh) = self.pf, self.pf.get_size()
        small = pygame.transform.smoothscale(pf, (max(1, rw // 10), max(1, rh // 10)))
        pf.blit(pygame.transform.smoothscale(small, (rw, rh)), (0, 0))
        self._dim(110)
        title, rows = (HELP_ROWS if kind == "help" else PAUSE_ROWS)[self.lang]
        px = rh * (0.036 if kind == "help" else 0.05)
        line = px * 1.3
        f = self.font(px)
        col = max(f.size(k)[0] for k, _ in rows) + px * 1.2
        width = col + max(f.size(v)[0] for _, v in rows) + px * 2
        rect = pygame.Rect(0, 0, int(width), int(line * (len(rows) + 2) + px))
        rect.center = (rw // 2, rh // 2)
        self._panel(rect, 230)
        self.put(
            pf, title, px * 1.15, HD_WARM, (rect.x + px, rect.y + px * 0.6), "topleft"
        )
        for n, (key, value) in enumerate(rows):
            y = rect.y + px * 0.6 + line * (n + 2)
            self.put(pf, key, px, HD_PLAYER, (rect.x + px, y), "topleft")
            self.put(pf, value, px, HD_TEXT, (rect.x + px + col, y), "topleft")

    def _side_panels(self, screen, g: Game) -> None:
        sw, sh = screen.get_size()
        r = self.rect
        key = ("panels", sw, sh)
        bg = self.cache.get(key)
        if bg is None:
            bg = gradient((sw, sh), ((0, (15, 16, 27)), (1, (6, 7, 12)))).convert()
            for x in (r.x - 2, r.right):
                pygame.draw.line(bg, (40, 54, 82), (x, 0), (x, sh), 2)
            self.cache[key] = bg
        screen.blit(bg, (0, 0), (0, 0, r.x, sh))  # solo las franjas: el campo va encima
        screen.blit(bg, (r.right, 0), (r.right, 0, sw - r.right, sh))
        lab, val = sh * 0.024, sh * 0.056
        lx, rx = r.x / 2, r.right + (sw - r.right) / 2

        def block(x, y, label, value, color=HD_TEXT, size=val):
            self.put(screen, label, lab, HD_MUTED, (x, y))
            self.put(screen, value, size, color, (x, y + lab * 1.8))

        scores = g.player_scores()
        y = sh * 0.1
        if len(scores) == 1:
            block(lx, y, self.ht("score"), str(scores[0]))
        else:
            for i, value in enumerate(scores):
                active = not g.attract and i == g.current
                block(
                    lx,
                    y,
                    self.ht("player", n=i + 1),
                    str(value),
                    HD_PLAYER if active else HD_MUTED,
                )
                y += sh * 0.13
        best = max([g.high_scores[0][1] if g.high_scores else 0] + scores)
        block(lx, sh * 0.42, self.ht("hi"), str(best), HD_WARM, val * 0.8)
        if not g.attract:
            y = sh * 0.1
            block(rx, y, self.ht("wave_label"), str(g.wave))
            y += sh * 0.14
            block(
                rx,
                y,
                self.ht("mult_label"),
                f"×{multiplier(g.wave)}",
                HD_WARM,
                val * 0.8,
            )
            y += sh * 0.14
            head = self.put(screen, self.ht("cities_label"), lab, HD_MUTED, (rx, y))
            if g.reserve:
                self.put(
                    screen,
                    f"+{g.reserve}",
                    lab,
                    HD_WARM,
                    (head.right + lab * 0.5, y),
                    "midleft",
                )
            iw = min((sw - r.right) * 0.24, sh * 0.05)
            for i, c in enumerate(g.cities):  # las seis ciudades en dos filas de tres
                icon = self._panel_city(i, c.alive, iw)
                col, row = i % 3, i // 3
                pos = (
                    rx + (col - 1) * iw * 1.14,
                    y + lab * 1.2 + row * icon.get_height() * 1.06,
                )
                screen.blit(icon, icon.get_rect(midtop=(round(pos[0]), round(pos[1]))))
            y += sh * 0.15
            ammo = (
                self.ht("ammo_inf")
                if g.infinite
                else "   ".join(str(s.abms) for s in g.silos)
            )
            block(rx, y, self.ht("ammo_label"), ammo, HD_PLAYER, val * 0.55)
            y += sh * 0.13
            block(
                rx,
                y,
                self.ht("chain_label"),
                str(g.stats.best_chain),
                HD_TEXT,
                val * 0.7,
            )
        else:
            key = "table_inf" if g.infinite else "table_arcade"
            self.put(
                screen,
                self.ht(key),
                lab,
                HD_WARM if g.infinite else HD_MUTED,
                (rx, sh * 0.12),
            )
        self.put(
            screen, self.ht("help_hint"), lab * 0.9, (96, 106, 130), (rx, sh * 0.95)
        )

    def _present(self, screen, g: Game) -> None:
        r = self.rect
        ox = oy = 0
        if self.juice and self.shake > 0.25:
            amp = self.shake * self.unit
            ox, oy = (
                round(self.rng.uniform(-amp, amp)),
                round(self.rng.uniform(-amp, amp)),
            )
        if self.side:
            self._side_panels(screen, g)
        if ox or oy or not self.side:  # el temblor destapa el borde del campo
            screen.fill((5, 6, 10), r if self.side else None)
        self._blit_field(screen, r.move(ox, oy))
        if self.juice and self.flash > 0.02:
            screen.fill(
                scaled(self.flash_rgb, self.flash), r, special_flags=pygame.BLEND_ADD
            )
        if self.toast_frames:
            px = r.h * 0.032
            body = self.label(self.t(self.toast), px, HD_TEXT, False)
            pill = body.get_rect(midtop=(r.centerx, r.y + px * 1.4)).inflate(
                px * 1.4, px * 0.7
            )
            box = pygame.Surface(pill.size, pygame.SRCALPHA)
            pygame.draw.rect(
                box, (10, 12, 22, 220), box.get_rect(), border_radius=pill.h // 2
            )
            pygame.draw.rect(
                box,
                (*HD_PLAYER, 140),
                box.get_rect(),
                width=1,
                border_radius=pill.h // 2,
            )
            screen.blit(box, pill)
            screen.blit(body, body.get_rect(center=pill.center))

    def _blit_field(self, screen, dest) -> None:
        """El campo en pantalla: tal cual, duplicando píxeles si el factor es entero
        (en 4K es justo 2: exacto y cuatro veces más barato) o con escalado suave."""
        pw, ph = self.pf.get_size()
        r = self.rect
        if (pw, ph) == r.size:
            screen.blit(self.pf, dest)
            return
        exact = r.w % pw == 0 and r.h % ph == 0 and r.w // pw == r.h // ph
        scale = pygame.transform.scale if exact else pygame.transform.smoothscale
        if screen.get_rect().contains(dest):  # escalar directamente en la pantalla
            scale(self.pf, r.size, screen.subsurface(dest))
        else:
            screen.blit(scale(self.pf, r.size), dest)


def ring_line(surface, color, center, radius: float) -> None:
    """Circunferencia suavizada; con pygame clásico, sin suavizar."""
    if hasattr(pygame.draw, "aacircle"):
        pygame.draw.aacircle(surface, color, center, radius, 1)
    else:
        pygame.draw.circle(surface, color, center, radius, 1)


# =============================================================================
# Sonido sintetizado al arrancar: ondas cuadradas y ruido, al estilo del POKEY
# =============================================================================


def _tone(
    rate: int,
    dur: float,
    f0: float,
    f1: float | None = None,
    shape: str = "square",
    decay: float = 0.0,
    vol: float = 1.0,
    vib: tuple[float, float] = (0.0, 0.0),
    am: tuple[float, float] = (0.0, 0.0),
    loop: bool = False,
) -> list[float]:
    """Tono con barrido exponencial de f0 a f1, vibrato y trémolo opcionales."""
    n = int(rate * dur)
    ratio = (f1 if f1 is not None else f0) / f0
    tau, sin, exp = math.tau, math.sin, math.exp
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / rate
        f = f0 * ratio ** (i / n) if ratio != 1.0 else f0
        if vib[1]:
            f *= 1.0 + vib[1] * sin(tau * vib[0] * t)
        phase += f / rate
        phase -= int(phase)
        if shape == "square":
            v = 1.0 if phase < 0.5 else -1.0
        elif shape == "tri":
            v = 4.0 * abs(phase - 0.5) - 1.0
        else:
            v = sin(tau * phase)
        env = vol * exp(-decay * t) if decay else vol
        if am[1]:
            env *= 1.0 - am[1] * (0.5 + 0.5 * sin(tau * am[0] * t))
        if not loop:
            if i < 40:
                env *= i / 40
            elif i > n - 200:
                env *= (n - i) / 200
        out[i] = v * env
    return out


def _noise(
    rate: int, dur: float, hold0: float, hold1: float, decay: float, seed: int
) -> list[float]:
    """Ruido binario retenido a una frecuencia que barre, como los contadores del POKEY."""
    rng = random.Random(seed)
    n = int(rate * dur)
    ratio = hold1 / hold0
    out = [0.0] * n
    acc, v = 0.0, 0.0
    for i in range(n):
        acc += hold0 * ratio ** (i / n) / rate
        if acc >= 1.0:
            acc -= int(acc)
            v = 1.0 if rng.random() < 0.5 else -1.0
        env = math.exp(-decay * i / rate)
        out[i] = v * env * (i / 30 if i < 30 else 1.0)
    return out


def _mix(*parts: tuple[list[float], float]) -> list[float]:
    out = [0.0] * max(len(s) for s, _ in parts)
    for samples, gain in parts:
        for i, v in enumerate(samples):
            out[i] += v * gain
    return out


def _cat(*parts: list[float]) -> list[float]:
    out: list[float] = []
    for samples in parts:
        out.extend(samples)
    return out


def _silence(rate: int, dur: float) -> list[float]:
    return [0.0] * int(rate * dur)


class Audio:
    """Banco de sonidos generado en memoria, con paneo según la x del suceso."""

    def __init__(self, enabled: bool = True, juice: bool = True) -> None:
        self.ok = False
        self.muted = False
        self.juice = juice
        self.sounds: dict = {}
        self.loops: list[str | None] = [None, None]
        self.rng = random.Random(5)
        self.rate, self.channels = 22050, 2
        if pygame is None or not enabled:
            return
        try:
            init = pygame.mixer.get_init()
            if init is None:
                pygame.mixer.init(22050, -16, 2, 512)
                init = pygame.mixer.get_init()
            self.rate, size, self.channels = init
            if size != -16:
                raise pygame.error(f"formato de audio {size} sin soporte")
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(2)
            self.loop_channels = (pygame.mixer.Channel(0), pygame.mixer.Channel(1))
            self._build()
            self.ok = True
        except pygame.error as exc:
            print(f"Sin sonido: {exc}", file=sys.stderr)

    def _build(self) -> None:
        r = self.rate
        beep = [_tone(r, 0.0625, 1180, vol=0.22), _silence(r, 0.0625)]
        bank = {
            "abm": _mix(
                (_noise(r, 0.24, 6000, 700, 11, seed=1), 0.45),
                (_tone(r, 0.16, 1100, 260, decay=14), 0.3),
            ),
            "boom": _mix(
                (_noise(r, 0.9, 2600, 160, 4.0, seed=2), 0.8),
                (_tone(r, 0.5, 92, 38, "tri", 6), 0.45),
            ),
            "boom_big": _mix(
                (_noise(r, 1.7, 1600, 60, 2.1, seed=3), 0.9),
                (_tone(r, 1.3, 70, 26, "tri", 2.4), 0.6),
                (_noise(r, 0.35, 8000, 2500, 9, seed=4), 0.25),
            ),
            "low": _cat(
                _tone(r, 0.07, 1040, vol=0.35),
                _silence(r, 0.05),
                _tone(r, 0.07, 1040, vol=0.35),
            ),
            "no_fire": _mix(
                (_tone(r, 0.13, 150, 105, decay=8), 0.4),
                (_noise(r, 0.13, 900, 700, 8, seed=5), 0.25),
            ),
            "tick_abm": _tone(r, 0.035, 1500, decay=20, vol=0.35),
            "tick_city": _cat(
                _tone(r, 0.045, 880, decay=8, vol=0.35),
                _tone(r, 0.065, 1320, decay=10, vol=0.35),
            ),
            "wave": _tone(r, 1.8, 560, decay=0.35, vol=0.32, vib=(5.0, 0.3)),
            "game_over": _mix(
                (_tone(r, 3.0, 720, 52, decay=0.8), 0.4),
                (_noise(r, 3.0, 900, 50, 1.0, seed=6), 0.5),
            ),
            "flier_0": _cat(*(beep * 4)),
            "flier_1": _tone(r, 0.5, 92, vol=0.3, am=(8.0, 0.6), loop=True),
            "smart": _tone(r, 0.5, 1050, vol=0.18, vib=(14.0, 0.22), loop=True),
            "select": _tone(r, 0.04, 1250, decay=18, vol=0.3),
        }
        notes = (
            523.25,
            587.33,
            659.25,
            783.99,
            880.0,
            1046.5,
            1174.7,
            1318.5,
            1568.0,
            1760.0,
        )
        for v in range(3):
            tune = [
                _tone(r, 0.065, self.rng.choice(notes), decay=5, vol=0.32)
                for _ in range(14)
            ]
            bank[f"bonus_city_{v}"] = _cat(*tune)
        for n in range(2, 10):
            f = 520 * 2 ** ((n - 2) / 6)
            bank[f"chain_{n}"] = _mix(
                (_tone(r, 0.16, f, shape="tri", decay=9, vol=0.5), 1.0),
                (_tone(r, 0.12, f * 2, shape="sine", decay=14, vol=0.25), 1.0),
            )
        for name, samples in bank.items():
            self.sounds[name] = self._make(samples)

    def _make(self, samples: list[float]):
        """Cuantiza a 31 niveles, como un mezclador de pocos bits, y crea el Sound."""
        mono = array.array(
            "h", (int(max(-1.0, min(1.0, round(v * 15) / 15)) * 30000) for v in samples)
        )
        if self.channels == 2:
            stereo = array.array("h", bytes(len(mono) * 4))
            stereo[0::2] = mono
            stereo[1::2] = mono
            mono = stereo
        return pygame.mixer.Sound(buffer=mono.tobytes())

    @staticmethod
    def _pan(channel, x: float | None, volume: float = 1.0) -> None:
        if x is None:
            channel.set_volume(volume, volume)
            return
        a = clamp(x / (W - 1), 0.0, 1.0) * math.pi / 2
        channel.set_volume(
            volume * min(1.0, math.cos(a) * 1.41), volume * min(1.0, math.sin(a) * 1.41)
        )

    def play(self, name: str, x: float | None = None, volume: float = 1.0) -> None:
        if not self.ok or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            channel = sound.play()
            if channel is not None:
                self._pan(channel, x, volume)

    def handle(self, g: Game) -> None:
        """Convierte los sucesos del frame en sonidos. El attract va sin sonido."""
        if not self.ok or self.muted or g.attract:
            return
        booms = 0
        for f in g.fx:
            name = f.name
            if name in ("abm", "low", "no_fire", "tick_abm", "tick_city"):
                self.play(name, f.x)
            elif name == "select":
                self.play(name)
            elif name == "boom":
                booms += 1
                if booms <= 2:
                    self.play("boom", f.x)
            elif name in ("city", "silo"):
                self.play("boom_big", f.x)
            elif name == "kill" and self.juice and f.b >= 2:
                self.play(f"chain_{min(f.b, 9)}", f.x)
            elif name == "wave":
                self.play("wave")
            elif name == "bonus_city":
                self.play(f"bonus_city_{self.rng.randrange(3)}", f.x)
            elif name in ("game_over", "player_out"):
                self.stop_loops()
                self.play("game_over")

    def update_loops(self, g: Game, frozen: bool) -> None:
        """Volador y smart bomb suenan en bucle; si coinciden, solo la bomba."""
        if not self.ok:
            return
        want: list[str | None] = [None, None]
        pans: list[float | None] = [None, None]
        if not (frozen or self.muted or g.attract) and g.phase is Phase.PLAY:
            bombs = [m.x for m in g.incoming if m is not None and m.kind == SMART]
            if bombs:
                want[1], pans[1] = "smart", sum(bombs) / len(bombs)
            elif g.flier is not None:
                want[0], pans[0] = f"flier_{g.flier.kind}", g.flier.x
        for i, channel in enumerate(self.loop_channels):
            if want[i] != self.loops[i]:
                channel.stop()
                if want[i]:
                    channel.play(self.sounds[want[i]], loops=-1)
                self.loops[i] = want[i]
            if want[i]:
                self._pan(channel, pans[i])

    def stop_loops(self) -> None:
        if self.ok:
            for channel in self.loop_channels:
                channel.stop()
        self.loops = [None, None]

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted and self.ok:
            pygame.mixer.stop()
            self.loops = [None, None]
        return self.muted


# =============================================================================
# Controles, récords y bucle principal
# =============================================================================


class Controls:
    """Traduce ratón, teclado y mando a un Inputs por frame."""

    def __init__(self, mouse: str = "abs", sens: float = 1.0) -> None:
        self.relative = mouse == "rel"
        self.sens = sens
        self.mouse_xy: tuple[float, float] | None = None
        self.mouse_moved = False
        self.rel = [0.0, 0.0]
        self.spin = 0.0
        self.fire = [False, False, False]
        self.start = False
        self.start2 = False
        self.nav = 0
        self.letter = ""
        self.back = False
        self.held = 0
        self.pads: dict[int, object] = {}
        pg = pygame
        self.fire_keys = {
            pg.K_z: 0,
            pg.K_x: 1,
            pg.K_c: 2,
            pg.K_a: 0,
            pg.K_s: 1,
            pg.K_d: 2,
        }
        self.start_keys = {pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE, pg.K_1, pg.K_KP1}
        self.commands = {
            pg.K_ESCAPE: "escape",
            pg.K_F1: "help",
            pg.K_F2: "style",
            pg.K_F3: "juice",
            pg.K_F11: "fullscreen",
            pg.K_F12: "shot",
        }
        self.letter_commands = {
            pg.K_p: "pause",
            pg.K_m: "mute",
            pg.K_t: "mouse",
            pg.K_l: "lang",
            pg.K_i: "ammo",
        }
        # Mando con distribución Xbox: X, A y B son izquierda, centro y derecha
        self.pad_fire = {2: 0, 4: 0, 0: 1, 3: 1, 1: 2, 5: 2}
        self.pad_start = {6, 7, 9, 10, 11}

    def _mouse_at(self, pos, view) -> None:
        if not self.relative:
            self.mouse_xy = view.to_game(pos)
            self.mouse_moved = True

    def handle(self, ev, game: Game, view) -> str | None:
        t = ev.type
        if t == pygame.MOUSEMOTION:
            self._mouse_at(ev.pos, view)
            rx, ry = ev.rel
            unit = view.unit
            if self.relative:
                self.rel[0] += rx / unit * self.sens
                self.rel[1] -= ry / unit * self.sens
            self.spin -= ry / unit
        elif t == pygame.MOUSEBUTTONDOWN and ev.button in (1, 2, 3):
            self._mouse_at(ev.pos, view)
            self.fire[ev.button - 1] = True
            self.start = True
        elif t == pygame.MOUSEWHEEL:
            self.nav += ev.y
        elif t == pygame.KEYDOWN:
            return self._key(ev, game)
        elif t == pygame.JOYDEVICEADDED:
            try:
                pad = pygame.joystick.Joystick(ev.device_index)
                self.pads[pad.get_instance_id()] = pad
            except pygame.error:
                pass
        elif t == pygame.JOYDEVICEREMOVED:
            self.pads.pop(ev.instance_id, None)
        elif t == pygame.JOYBUTTONDOWN:
            if ev.button in self.pad_fire:
                self.fire[self.pad_fire[ev.button]] = True
                self.start = True
            elif ev.button in self.pad_start:
                if game.phase in (Phase.PLAY, Phase.INTRO):
                    return "pause"
                self.start = True
        elif t == pygame.JOYHATMOTION and game.phase is Phase.INITIALS:
            self.nav += ev.value[1]
            self.back = self.back or ev.value[0] < 0
        return None

    def _key(self, ev, game: Game) -> str | None:
        key = ev.key
        if key in self.commands:
            return self.commands[key]
        if game.phase is Phase.INITIALS:  # aquí las letras son letras
            if key in (pygame.K_BACKSPACE, pygame.K_LEFT):
                self.back = True
            elif key == pygame.K_UP:
                self.nav += 1
            elif key == pygame.K_DOWN:
                self.nav -= 1
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start = True
            elif ev.unicode and ev.unicode.upper() in INITIALS_ALPHABET:
                self.letter = ev.unicode
            return None
        if key in self.letter_commands:
            return self.letter_commands[key]
        if key in self.fire_keys:
            self.fire[self.fire_keys[key]] = True
        if key in self.start_keys:
            self.start = True
        if key in (pygame.K_2, pygame.K_KP2):
            self.start2 = True
        return None

    def build(self, game: Game) -> Inputs:
        keys = pygame.key.get_pressed()
        dx, dy = self.rel
        kx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        ky = keys[pygame.K_UP] - keys[pygame.K_DOWN]
        if (kx or ky) and game.phase is not Phase.INITIALS:
            self.held += 1
            fine = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            speed = 1.0 if fine else min(1.5 + self.held * 0.12, 5.0)
            dx += kx * speed
            dy += ky * speed
        else:
            self.held = 0
        for pad in list(self.pads.values()):
            try:
                ax, ay = pad.get_axis(0), pad.get_axis(1)
                hx, hy = pad.get_hat(0) if pad.get_numhats() else (0, 0)
            except pygame.error:
                continue
            mag = math.hypot(ax, ay)
            if mag > 0.2:
                gain = ((mag - 0.2) / 0.8) ** 1.7 * 6.0 / mag
                dx += ax * gain
                dy -= ay * gain
            if game.phase is not Phase.INITIALS:
                dx += hx * 2.5
                dy += hy * 2.5
        abs_xy = self.mouse_xy if self.mouse_moved and not self.relative else None
        inp = Inputs(
            dx, dy, abs_xy, tuple(self.fire), self.start, self.start2,
            self.nav, self.spin, self.letter, self.back,
        )  # fmt: skip
        self.rel = [0.0, 0.0]
        self.spin = 0.0
        self.fire = [False, False, False]
        self.start = self.start2 = self.back = self.mouse_moved = False
        self.nav = 0
        self.letter = ""
        return inp


def data_dir() -> Path:
    """Carpeta de datos del usuario, fuera del repositorio."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "missile-py"


class ScoreStore:
    """Tabla de récords en JSON, escrita de forma atómica."""

    def __init__(self, enabled: bool = True, path: Path | None = None) -> None:
        self.enabled = enabled
        self.path = path or data_dir() / "scores.json"

    def load(self) -> dict[str, list[tuple[str, int]]] | None:
        """Lee la versión 2 (una tabla por modo) y también la 1 (una sola tabla)."""
        if not self.enabled:
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            raw = data["tables"] if "tables" in data else {"arcade": data["scores"]}
            tables = {
                mode: [(str(name)[:3], int(score)) for name, score in rows][:5]
                for mode, rows in raw.items()
                if mode in AMMO_MODES
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return tables or None

    def save(self, tables: dict[str, list[tuple[str, int]]]) -> None:
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            rows = {mode: [list(e) for e in table] for mode, table in tables.items()}
            payload = {"version": 2, "tables": rows}
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            print(f"No se pudieron guardar los récords: {exc}", file=sys.stderr)


class SettingsStore:
    """Filtro, efectos, ratón, sonido e idioma elegidos, para la próxima vez."""

    def __init__(self, enabled: bool = True, path: Path | None = None) -> None:
        self.enabled = enabled
        self.path = path or data_dir() / "settings.json"
        self.values: dict = {}
        if enabled:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.values = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self.values = {}

    def get(self, key: str, default):
        value = self.values.get(key, default)
        return value if isinstance(value, type(default)) else default

    def set(self, **values) -> None:
        self.values.update(values)
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.values, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            print(f"No se pudieron guardar los ajustes: {exc}", file=sys.stderr)


STYLES = ("hd", "retro", "arcade")


def initial_window(scale: int = 0) -> tuple[int, int]:
    """Ventana apaisada que cabe en el escritorio, con sitio para los paneles."""
    try:
        dw, dh = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError, AttributeError):
        dw, dh = 1280, 800
    h = H * scale if scale else int(min(dh * 0.85, 1000))
    w = int(min(dw * 0.95, h * 1.6))
    return max(W, w), max(H, h)


def set_display(size: tuple[int, int], fullscreen: bool):
    if fullscreen:
        try:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        except pygame.error:
            pass
    return pygame.display.set_mode(size, pygame.RESIZABLE)


def make_renderer(style: str, effects: bool, lang: str):
    if style == "hd":
        return HDRenderer(effects, lang)
    if style == "retro":
        return PixelRenderer("crt", effects, lang)
    return PixelRenderer("off", False, lang)


def set_relative_mouse(on: bool) -> None:
    fn = getattr(pygame.mouse, "set_relative_mode", None)
    try:
        if fn is not None:
            fn(on)
        else:
            pygame.event.set_grab(on)
    except pygame.error:
        pass
    pygame.mouse.set_visible(False)


def run_game(args: argparse.Namespace) -> int:
    if pygame is None:
        print("Falta pygame-ce. Instálalo con:  pip install pygame-ce", file=sys.stderr)
        return 1
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    windowed = initial_window(args.scale)
    fullscreen = args.fullscreen
    screen = set_display(windowed, fullscreen)
    pygame.display.set_caption(f"missile.py {__version__}")
    pygame.display.set_icon(make_icon())
    pygame.mouse.set_visible(False)
    settings = SettingsStore(not args.no_save)
    store = ScoreStore(not args.no_save)
    if args.classic:
        style, effects, infinite = "arcade", False, False
    else:
        style = args.style or settings.get("style", "hd")
        style = style if style in STYLES else "hd"
        effects = settings.get("effects", True)
        infinite = (
            args.ammo == "infinite" if args.ammo else settings.get("infinite", True)
        )
    lang = args.lang or settings.get("lang", "auto")
    lang = detect_lang() if lang not in LANGS else lang
    mouse = args.mouse or settings.get("mouse", "abs")
    game = Game(
        args.seed, args.cities, args.bonus, args.wave, store.load(), effects, infinite
    )
    renderer = make_renderer(style, effects, lang)
    audio = Audio(True, effects)
    if args.mute or settings.get("muted", False):
        audio.toggle_mute()  # arranca en silencio, pero M lo devuelve
    controls = Controls(mouse if mouse in ("abs", "rel") else "abs", args.sens)
    clock = pygame.time.Clock()
    paused = help_on = relative_on = False
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                continue
            if ev.type == pygame.WINDOWFOCUSLOST and game.phase in (
                Phase.PLAY,
                Phase.INTRO,
            ):
                paused = True
            cmd = controls.handle(ev, game, renderer)
            if cmd == "escape":
                if help_on:
                    help_on = False
                elif paused or game.attract:
                    running = False
                else:
                    paused = True
            elif cmd == "pause" and not game.attract:
                paused = not paused
            elif cmd == "help":
                help_on = not help_on
            elif cmd == "style":
                style = STYLES[(STYLES.index(style) + 1) % len(STYLES)]
                renderer = make_renderer(style, effects, renderer.lang)
                renderer.say(f"style_{style}")
                settings.set(style=style)
            elif cmd == "juice":
                effects = not effects
                renderer.set_juice(effects)
                audio.juice = game.stats_screen = effects
                settings.set(effects=effects)
            elif cmd == "ammo" and game.attract:
                game.set_infinite(not game.infinite)
                renderer.say("inf_on" if game.infinite else "inf_off")
                settings.set(infinite=game.infinite)
            elif cmd == "lang":
                renderer.toggle_lang()
                settings.set(lang=renderer.lang)
            elif cmd == "fullscreen":
                fullscreen = not fullscreen
                screen = set_display(windowed, fullscreen)
            elif cmd == "shot":
                stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
                name = f"missile-{stamp}.png"
                while os.path.exists(name):  # dos capturas en el mismo segundo
                    n += 1
                    name = f"missile-{stamp}-{n}.png"
                pygame.image.save(screen, name)
                renderer.say("shot")
            elif cmd == "mute":
                muted = audio.toggle_mute()
                renderer.say("sound_off" if muted else "sound_on")
                settings.set(muted=muted)
            elif cmd == "mouse":
                controls.relative = not controls.relative
                renderer.say("trackball" if controls.relative else "mouse")
                settings.set(mouse="rel" if controls.relative else "abs")
        screen = pygame.display.get_surface()
        if not fullscreen:
            windowed = screen.get_size()
        frozen = paused or help_on
        inp = controls.build(game)
        if not frozen:
            game.step(inp)
            renderer.tick(game)
            audio.handle(game)
            game.fx.clear()
        audio.update_loops(game, frozen)
        want_relative = (
            controls.relative and not frozen and game.phase in (Phase.PLAY, Phase.INTRO)
        )
        if want_relative != relative_on:
            set_relative_mouse(want_relative)
            relative_on = want_relative
        renderer.draw(game, screen, "help" if help_on else "pause" if paused else None)
        pygame.display.flip()
        if game.scores_changed:
            store.save(game.tables)
            game.scores_changed = False
        clock.tick(FPS)
    pygame.quit()
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="missile.py",
        description="Missile Command (Atari, 1980) en un solo archivo de Python.",
        epilog="Ratón para apuntar; botones izquierdo, central y derecho (o Z, X, C) "
        "para disparar desde cada silo. P pausa, F1 ayuda.",
    )
    p.add_argument(
        "--cities",
        type=int,
        choices=(4, 5, 6, 7),
        default=6,
        help="ciudades iniciales, como el DIP del original",
    )
    p.add_argument(
        "--bonus", type=int, choices=(0,) + BONUS_CHOICES, default=10000, metavar="N",
        help="puntos por ciudad bonus: 8000 a 20000; 0 las desactiva (modo torneo)",
    )  # fmt: skip
    p.add_argument("--wave", type=int, default=1, metavar="N", help="oleada inicial")
    p.add_argument(
        "--seed", type=int, default=None, help="semilla: misma semilla, misma partida"
    )
    p.add_argument(
        "--classic",
        action="store_true",
        help="recreativa pura: píxeles, munición limitada, sin efectos ni estadísticas",
    )
    p.add_argument(
        "--style",
        choices=STYLES,
        default=None,
        help="gráficos: hd, retro o arcade (F2 los alterna)",
    )
    p.add_argument(
        "--ammo",
        choices=("infinite", "limited"),
        default=None,
        help="munición infinita o la del original (I la alterna en el menú)",
    )
    p.add_argument(
        "--mouse", choices=("abs", "rel"), default=None,
        help="abs: la mira sigue al ratón; rel: el ratón actúa como trackball (T lo cambia)",
    )  # fmt: skip
    p.add_argument(
        "--lang",
        choices=LANGS,
        default=None,
        help="idioma de los textos: en o es (L lo cambia)",
    )
    p.add_argument(
        "--sens", type=float, default=1.0, help="sensibilidad del modo trackball"
    )
    p.add_argument(
        "--scale",
        type=int,
        default=0,
        choices=range(9),
        metavar="N",
        help="altura inicial de la ventana en múltiplos de 231 píxeles; 0 la elige sola",
    )
    p.add_argument(
        "--fullscreen", action="store_true", help="pantalla completa (F11 la alterna)"
    )
    p.add_argument("--mute", action="store_true", help="sin sonido (M lo alterna)")
    p.add_argument(
        "--no-save", action="store_true", help="no leer ni guardar récords ni ajustes"
    )
    p.add_argument(
        "--headless", action="store_true", help="simular una partida sin ventana"
    )
    p.add_argument(
        "--frames",
        type=int,
        default=60 * 60 * 90,
        metavar="N",
        help="límite de frames de --headless",
    )
    p.add_argument(
        "--test", action="store_true", help="ejecutar las comprobaciones internas"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)
    if args.wave < 1:
        p.error("--wave tiene que ser 1 o más")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.test:
        return self_test()
    if args.headless:
        return run_headless(args)
    return run_game(args)


if __name__ == "__main__":
    sys.exit(main())

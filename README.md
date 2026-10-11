# missile.py

**Missile Command** (Atari, 1980, Dave Theurer) recreado en Python moderno y en **un único archivo: `missile.py`**.

No hay paquetes, ni módulos auxiliares, ni carpeta de assets. Los gráficos se dibujan en tiempo real y el sonido se sintetiza en el propio código. Las tablas de juego salen del fuente original de Atari. Se juega con `python missile.py`.

> **Estado:** especificación. `missile.py` aún no existe; este README es el contrato que debe cumplir.

---

## 1. De dónde salen los números

Este README no está escrito de memoria. Cada valor lleva una etiqueta con su procedencia:

| Etiqueta | Fuente | Qué se ha sacado de ella |
|---|---|---|
| `W3COMN` | [historicalsource/missile-command](https://github.com/historicalsource/missile-command), archivo `W3COMN.XX` | Constantes globales del fuente rev. 1: posiciones de ciudades y silos, límites del cursor, ventana de MIRV, diámetro de explosión. |
| `W3MAIN` | El mismo repositorio, archivo `A35820.1D` | Lógica de juego: tablas por oleada, radios de explosión, colisión, puntuación, selección de objetivos. |
| `McFadden` | [6502disassembly.com](https://6502disassembly.com/va-missile-command/), de Andy McFadden (2021) | Desensamblado comentado de la rev. 3: guía de oleadas, paleta, mensajes, sonido, límites. |
| **Diseño** | — | Decisión propia de `missile.py` allí donde el original depende del hardware. |

El fuente original está en ensamblador 6502 con `.RADIX 16`. Los números sin punto son hexadecimales (`5F` = 95) y los que llevan punto son decimales (`10.` = 10). Todas las cifras de este README ya están convertidas a decimal.

Si la rev. 1 (el fuente) y la rev. 3 (el desensamblado) no coinciden, manda la rev. 3, que es la versión final de Atari.

Referencias consultadas sin sacar cifras de ellas: el driver de MAME [`missile.cpp`](https://github.com/mamedev/mame/blob/master/src/mame/atari/missile.cpp), el core FPGA de [MiSTer](https://github.com/MiSTer-devel/Arcade-MissileCommand_MiSTer) y el [Missile de Robert Munafo](https://www.mrob.com/pub/source/missile.html) para Mac (1984).

---

## 2. Requisitos y arranque

- **Python 3.12 o superior.** Verificado con Python 3.13 y pygame-ce 2.5.8.
- **pygame-ce** es la única dependencia. NumPy no hace falta: el audio se sintetiza con el módulo `array` de la biblioteca estándar.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pygame-ce
python missile.py
```

Opciones de línea de comandos:

| Opción | Efecto | Por defecto |
|---|---|---|
| `--cities N` | Ciudades iniciales, de 4 a 7, como el DIP switch del original. | 6 |
| `--bonus N` | Puntos por ciudad bonus: 8000, 10000, 12000, 14000, 15000, 18000 o 20000 (`W3MAIN BONINL`). `0` las desactiva, que es el modo torneo. | 10000 |
| `--seed N` | Semilla del generador aleatorio. Misma semilla, misma partida. | aleatoria |
| `--sens F` | Sensibilidad del ratón usado como trackball. | 1.0 |
| `--headless` | Simula sin ventana, con el piloto automático, y vuelca la puntuación final. | — |
| `--test` | Ejecuta las comprobaciones internas y sale. | — |

---

## 3. Reglas del archivo único

1. **Un archivo: `missile.py`.** Ni `assets/`, ni `config.json`, ni `utils.py`.
2. **Cero recursos externos.** La tipografía, las ciudades, las explosiones y el sonido se generan por código.
3. **Un solo dueño del estado.** Una instancia de `Game` lo guarda todo. No hay globales mutables.
4. **Lógica sin pygame.** `update()` no toca pygame, así que se puede probar sin ventana.
5. **Determinismo.** `Game` tiene su propio `random.Random(seed)`. Nunca se usa el `random` global.
6. **Orden fijo dentro del archivo:**
   1. docstring y licencia
   2. imports
   3. constantes y tablas del original
   4. entidades (`@dataclass(slots=True)`)
   5. lógica pura
   6. piloto automático
   7. render
   8. audio
   9. bucle principal, argumentos y `main()`
7. **Techo orientativo de 1.500 líneas.** Pasarse suele ser señal de abstracción sobrante.
8. **Estilo:** `ruff check missile.py` y `ruff format --check missile.py` pasan limpios.

---

## 4. Pantalla, coordenadas y tiempo

| Parámetro | Valor | Fuente |
|---|---|---|
| Resolución lógica | 256 × 231 | McFadden |
| Eje vertical | línea 0 abajo, línea 230 arriba | McFadden |
| Ritmo de la lógica | 60 frames por segundo; todas las tablas cuentan en frames | McFadden |
| Techo de juego (`TOPSCR`) | 222 | W3COMN |
| Cursor, eje horizontal | de 8 a 247 | W3COMN `IHMIN`, `IHMAX` |
| Cursor, eje vertical | de 45 a 206 | W3COMN `IVMIN`, `IVMAX` |
| Línea sin daño (`LOWEST`) | 33 | W3COMN |

**Diseño.** La lógica trabaja en las coordenadas del original, con la y hacia arriba, para copiar las constantes tal cual. Solo el render convierte, con `pantalla_y = 230 - y`.

**Diseño.** La ventana se abre con `pygame.display.set_mode((256, 231), pygame.SCALED)` y SDL se encarga de escalar. `F11` llama a `pygame.display.toggle_fullscreen()`.

**Diseño.** Paso fijo: una llamada a `update()` por frame, con `clock.tick(60)` y sin `dt`. Si el ordenador no llega, el juego se ralentiza, como la recreativa, en lugar de saltarse frames.

---

## 5. Escenario

Seis ciudades y tres silos, con las coordenadas del original (`W3COMN`) ordenadas de izquierda a derecha:

| Objeto | x | y |
|---|---|---|
| Silo izquierdo | 20 | 22 |
| Ciudad | 44 | 18 |
| Ciudad | 71 | 17 |
| Ciudad | 95 | 16 |
| Silo central | 123 | 22 |
| Ciudad | 148 | 18 |
| Ciudad | 180 | 21 |
| Ciudad | 208 | 17 |
| Silo derecho | 240 | 22 |

Los ABM salen dos líneas por encima de su silo, en y = 24 (`W3MAIN MBCPVA`). El terreno y las ciudades ocupan las 32 líneas inferiores, la franja que en el hardware tenía un bit de color extra (McFadden).

---

## 6. Reglas del juego

Vocabulario de McFadden: **ABM** es el misil del jugador, **ICBM** el misil enemigo, **MIRV** el ICBM que se divide y **volador** el bombardero o el satélite.

### 6.1 Defensa: los ABM

- **Munición.** 10 ABM por silo (`W3COMN MAXMIS`). Los silos se reparan y recargan al empezar cada oleada.
- **Disparo.** Los botones izquierdo, central y derecho disparan desde el silo izquierdo, central y derecho. Un silo vacío o destruido no dispara y suena el aviso de "no puede disparar". El juego nunca pasa el disparo a otro silo.
- **Límites.** Como mucho hay 8 ABM en vuelo (`W3COMN NABMS`). Además, los ABM en vuelo más las explosiones defensivas no pueden pasar de 16 (`W3COMN MAXDEX`).
- **Destino.** Al disparar, el punto de destino se marca con una X parpadeante. El ABM detona al llegar.
- **Velocidad.** Los silos laterales avanzan 3 pasos por frame y el central 7 (`W3MAIN UPABMS`). Cada paso es una unidad sobre la trayectoria.
- **Avisos.** Cuando a un silo le quedan 3 ABM aparece LOW debajo de él. Cuando se queda a cero, OUT.

### 6.2 Explosiones y colisiones

- **Huecos.** Hay 20 explosiones simultáneas como máximo (`W3COMN NEXPLO`).
- **Radio.** Sigue la tabla `OLDRAD` de `W3MAIN`: sube de 0 a 13 y vuelve a 0. Las cifras exactas están en la sección 7.
- **Ritmo.** Cada explosión avanza un paso cada 5 frames. Las 20 se reparten en 5 grupos de 4 y en cada frame se actualiza un grupo (`W3MAIN PREXPL`). Una explosión dura unos 135 frames, algo más de 2 segundos.
- **Forma.** Es un octógono, no un círculo. Para un radio r, sus vértices son (±r, 0), (0, ±r) y (±8r/11, ±8r/11). Es exactamente la figura que define la fórmula de colisión de abajo.
- **Colisión** (`W3MAIN DELTA` y `DAMAGE`). Sean dx y dy las distancias absolutas entre la explosión y el atacante. El alcance R es el radio actual más el tamaño del blanco: 1 para un ICBM, 3 para una smart bomb y 6 para un volador. Hay impacto si se cumplen las tres condiciones:

  ```
  dx < R    y    dy < R    y    max(dx, dy) + 3/8 · min(dx, dy) < R
  ```

- **Túnel.** La colisión solo se comprueba cuando la explosión se actualiza, cada 5 frames. Un ICBM rápido puede atravesar una explosión pequeña. Se replica tal cual.
- **Blancos.** Solo reciben daño los atacantes. Los ABM atraviesan las explosiones sin daño.
- **Suelo.** Una explosión por debajo de la línea 33 no hace daño. Un ICBM destruido por debajo de la línea 33 no da puntos (`W3MAIN ICKILL`).
- **Cadenas.** Todo atacante destruido detona a su vez (`W3MAIN DETONA`), y su explosión destruye a otros. Las reacciones en cadena son parte del juego.
- **Techo.** No se crean explosiones por encima de la línea 209 (`W3MAIN DETONA`).

### 6.3 ICBM y MIRV

- **Huecos.** Hay 8 huecos compartidos por ICBM y smart bombs (`W3COMN NICBMS`).
- **Origen y objetivo.** Los ICBM entran por arriba o los suelta un volador. Cada uno apunta a una ciudad o a un silo que sigan en pie.
- **Movimiento.** Avanzan en línea recta, una unidad por paso. El ritmo de pasos depende de la oleada: es el retardo en frames de la sección 7, guardado en punto fijo 8.8. Se reproduce con un acumulador, que da el reparto irregular del original (con 1,5 frames de retardo, espera 1, luego 2, luego 1...):

  ```python
  acc += 0x100                    # en cada frame
  if acc > delay_8_8:
      acc -= delay_8_8 + 0x100
      mover_todos_los_icbm_un_paso()
  ```

- **Llegada.** El ICBM llega cuando sobrepasa su objetivo en x o en y. No hace falta que coincida al píxel (McFadden).
- **Ritmo de ataque.** No sale ningún ataque nuevo mientras el ICBM más alto esté por encima de `max(202 - 2 × oleada, 180)` (`W3COMN LAUHGT`, `LAULOW`). En un mismo frame salen como mucho 4 (McFadden).
- **MIRV** (`W3COMN MIRVLO`, `MIRVHI`, `MIRVWV`). Puede ocurrir desde la oleada 1. Se recorren los 8 huecos en orden, llevando la altura máxima vista hasta el momento. Un ICBM es candidato si se cumplen tres cosas:
  1. esa altura máxima está entre 128 y 159;
  2. el propio candidato está por debajo de 160;
  3. quedan huecos libres e ICBM sin gastar en la oleada.

  Un ICBM puede soltar hasta 3 cabezas nuevas, cada una hacia un objetivo distinto. Todas cuentan para el total de la oleada.
- **Impacto.** Una ciudad alcanzada queda destruida. Un silo alcanzado queda destruido y pierde todos sus ABM (`W3MAIN DESTROY`).

### 6.4 Smart bombs

- **Aparición.** Desde la oleada 6. El número por oleada está en la sección 7.
- **Límites.** Comparten huecos y velocidad con los ICBM. Hay 3 en pantalla como máximo.
- **Lanzamiento** (`W3MAIN ICBLAU`). Solo sale una smart bomb si hay menos de 3 en pantalla y la suma de smart bombs e ICBM en pantalla es menor que 5. Mientras queden ICBM por lanzar, cada lanzamiento tiene una probabilidad de 1 entre 4 de ser una smart bomb. Cuando ya no quedan ICBM, solo salen smart bombs.
- **Movimiento.** Se mueven como un ICBM mientras no haya peligro cerca. Ante una amenaza, se apartan sin acercarse a ella y sin dejar de ir hacia su objetivo. Nunca cambian de objetivo.
- **Oleada 9.** Desde la oleada 9 ya no pueden esquivar hacia arriba. El fuente lo llama `STUPID`, con el comentario "MAKE IT STUPID (NO UP)".
- **Diseño.** El original detecta el peligro leyendo los píxeles del color parpadeante: explosiones, marcas X y cabezas de misil. `missile.py` lo aproxima buscando esos objetos dentro de un radio. Después elige, de las 8 direcciones posibles, la que avanza hacia el objetivo sin acercarse a la amenaza más próxima.

### 6.5 Voladores: bombarderos y satélites

- **Aparición.** Desde la oleada 2 (`W3COMN SPUTWV`). Hay un único hueco de volador.
- **Movimiento.** El tipo, la altura y el sentido se eligen al azar. Un bombardero avanza 1 píxel cada 3 frames y un satélite, 1 píxel cada 2 (McFadden).
- **Disparo.** Disparan ICBM desde su posición, a veces varios a la vez, siempre dentro de los límites de la oleada. Puede cruzar la pantalla sin disparar.
- **Tiempos.** La altura, la pausa antes de reaparecer y el intervalo entre disparos dependen de la oleada (sección 7).

### 6.6 Selección de objetivos

- **Tope de ciudades** (`W3MAIN GUICBM`). En una oleada nunca hay más de 3 ciudades entre destruidas y apuntadas. Si ya han caído 2, los misiles restantes solo apuntan a una ciudad a la vez.
- **Rendición.** Si los tres silos se quedan sin ABM y ya han caído 3 ciudades, la oleada termina en el acto (`W3MAIN TALIVE`).

### 6.7 Fin de oleada, ciudades bonus y fin de partida

- **Final.** La oleada termina cuando se han lanzado y resuelto todos sus ICBM y smart bombs.
- **Recuento.** Es animado: 5 puntos por ABM sin disparar y 100 por ciudad en pie, por el multiplicador.
- **Ciudades bonus.** Se gana una cada `--bonus` puntos. Pueden ganarse varias en una oleada y la reserva no tiene un límite práctico. Al empezar la oleada se rellenan los cráteres con la reserva, y el cráter se elige al azar (McFadden).
- **Fin de partida.** Llega al cerrar una oleada sin ciudades en pie ni en reserva. "THE END" aparece ampliado, a escala 3×10, dentro de una gran explosión.
- **Récords.** Tabla de 5 puntuaciones con 3 iniciales, como el original. **Diseño:** vive en memoria, sin archivo, como una recreativa encendida.

---

## 7. Tablas por oleada

Listas para pegar en `missile.py`. El índice 0 corresponde a la oleada 1.

```python
# Oleadas 1 a 19. De la 20 en adelante se repite la 19.            (McFadden, rev. 3)
# La rev. 1 lanzaba 16, 18 y 20 ICBM en las oleadas 17 a 19.       (W3MAIN ICBWAV)
ICBM_COUNT  = (12, 15, 18, 12, 16, 14, 17, 10, 13, 16, 19, 12, 14, 16, 18, 14, 17, 19, 22)
SMART_COUNT = ( 0,  0,  0,  0,  0,  1,  1,  2,  3,  4,  4,  5,  5,  6,  6,  7,  7,  7,  7)  # W3MAIN CRMWAV

# Retardo entre pasos de ICBM, en frames y punto fijo 8.8: 0x04D0 = 4,8125 frames.
# De la oleada 15 en adelante vale 0: un paso por frame.            (W3MAIN WICSPH, WICSPL)
ICBM_DELAY_8_8 = (0x04D0, 0x02E0, 0x01C0, 0x0108, 0x00A0, 0x0060, 0x0040,
                  0x0020, 0x0010, 0x000A, 0x0006, 0x0004, 0x0002, 0x0001, 0x0000)

# Voladores, oleadas 2 a 8. De la 9 en adelante se repite la 8.
FLIER_COOLDOWN = (240, 160, 128, 128, 96, 64, 32)   # frames antes de reaparecer  (W3MAIN WSPLAU)
FLIER_FIRE_GAP = (128,  96,  64,  48, 32, 32, 16)   # frames entre disparos       (W3MAIN WSPFIR)
FLIER_ALTITUDE = ((148, 195), (148, 195), (132, 163), (132, 163),
                  (100, 131), (100, 131), (100, 131))                          # (McFadden)

# Radio de explosión en cada paso. La explosión acaba en el paso 27.  (W3MAIN OLDRAD, W3COMN EXDONE)
EXPLOSION_RADIUS = (0, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
                    13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0)

BONUS_CHOICES = (8000, 10000, 12000, 14000, 15000, 18000, 20000)              # (W3MAIN BONINL)
```

---

## 8. Puntuación

| Acción | Puntos base | Fuente |
|---|---|---|
| ICBM destruido | 25 | McFadden |
| Bombardero o satélite | 100, cuatro veces un ICBM | W3MAIN `SPUTKI` |
| Smart bomb | 125, cinco veces un ICBM | W3MAIN `CMKILL` |
| ABM sin disparar al cerrar la oleada | 5 | McFadden |
| Ciudad en pie al cerrar la oleada | 100 | McFadden |

Todo se multiplica por el multiplicador de la oleada (McFadden):

| Oleadas | 1–2 | 3–4 | 5–6 | 7–8 | 9–10 | 11 o más |
|---|---|---|---|---|---|---|
| Multiplicador | ×1 | ×2 | ×3 | ×4 | ×5 | ×6 |

En código: `multiplicador = min((oleada + 1) // 2, 6)`.

---

## 9. Color

- **Paleta.** Son 8 colores de 3 bits RGB: blanco, amarillo, magenta, rojo, cian, verde, azul y negro.
- **Parpadeo.** Un color recorre los 8 a 30 Hz. Lo usan las cabezas de misil, las explosiones y la X de destino. **Diseño:** cambia cada 2 frames.
- **Ruinas.** Una explosión sobre una ciudad deja su silueta en el color del terreno, como escombros y no como un agujero (McFadden).
- **Colores por oleada.** Hay 10 juegos y cambian cada 2 oleadas, así que la oleada 21 repite los colores de la 1 (McFadden):

| Oleadas | Fondo | Terreno | ICBM | Ciudad 1 | ABM y cursor | Ciudad 2 |
|---|---|---|---|---|---|---|
| 1–2 | negro | amarillo | rojo | cian | azul | azul |
| 3–4 | negro | amarillo | verde | cian | azul | azul |
| 5–6 | negro | azul | rojo | amarillo | verde | verde |
| 7–8 | negro | rojo | amarillo | amarillo | azul | azul |
| 9–10 | azul | amarillo | rojo | magenta | negro | negro |
| 11–12 | cian | amarillo | rojo | negro | azul | azul |
| 13–14 | magenta | verde | negro | negro | amarillo | amarillo |
| 15–16 | amarillo | verde | negro | blanco | rojo | rojo |
| 17–18 | blanco | rojo | magenta | amarillo | verde | verde |
| 19–20 | rojo | amarillo | negro | verde | azul | azul |

---

## 10. Texto

- **Rejilla.** Glifos de 8 × 8 píxeles con una línea libre arriba y otra a la derecha. Caben 32 columnas por 28 filas (McFadden).
- **Diseño.** La fuente es un diccionario dentro de `missile.py`: cada carácter son 7 filas de 7 bits. Solo se definen los caracteres necesarios: A–Z, 0–9 y algunos signos. No se usa `pygame.font`.
- **Mensajes.** `PLAYER`, `BONUS POINTS`, `BONUS CITY`, `LOW`, `OUT`, `GAME OVER`, `THE END`, `GREAT SCORE`, `ENTER YOUR INITIALS` y el título `MISSILE COMMAND` a escala 4×4. `DEFEND CITIES` solo aparece en las oleadas 1 a 3.

---

## 11. Sonido

El original usa el chip POKEY, con 4 canales. Tiene 8 efectos de evento y 2 continuos (McFadden):

- **Silo con poca munición**, al aparecer LOW.
- **Explosión.**
- **Lanzamiento de ABM.**
- **Puntos de bonus**, en el recuento.
- **Inicio de oleada.**
- **Fin de partida.**
- **Ciudad bonus**, una serie de tonos aleatorios al colocarla.
- **No puede disparar.**
- **Volador en pantalla**, continuo.
- **Smart bomb en pantalla**, continuo. Si coinciden con un volador, solo suena la smart bomb.

**Diseño.** Síntesis en Python puro: se generan las muestras con `array('h')` y se cargan con `pygame.mixer.Sound(buffer=...)`, a 22 050 Hz y en mono, al arrancar. Está comprobado con pygame-ce 2.5.8. Si el mezclador no arranca, el juego sigue sin sonido.

---

## 12. Piloto automático

En modo attract el ordenador juega la oleada 1 (McFadden). `--headless` usa el mismo piloto.

- Ataca los ICBM por orden de aparición.
- Mueve el cursor hacia el punto donde estará el misil dentro de 16 frames, a 2 píxeles por frame (`W3COMN AUTSPD`).
- Dispara desde el silo más cercano.
- Nunca tiene más de 2 ABM en vuelo.

---

## 13. Arquitectura interna

### Entidades

Todas son `@dataclass(slots=True)`:

```python
City(x: int, y: int, alive: bool)
Silo(x: int, y: int, abms: int, alive: bool)
Abm(x: float, y: float, tx: int, ty: int, vx: float, vy: float, steps_per_frame: int)
Icbm(x: float, y: float, tx: int, ty: int, vx: float, vy: float, trail_from: tuple[int, int], smart: bool)
Flier(kind: Literal["bomber", "satellite"], x: float, y: int, direction: int, fire_timer: int)
Explosion(x: int, y: int, step: int, offensive: bool)
```

### Estado

```python
class State(Enum):
    ATTRACT = auto()
    WAVE_START = auto()
    PLAYING = auto()
    WAVE_END = auto()
    GAME_OVER = auto()
    ENTER_INITIALS = auto()
```

`Game` guarda el estado actual, la oleada, la puntuación, la reserva de ciudades bonus, el próximo umbral de bonus, las listas de entidades, el contador de explosiones, el acumulador de retardo de los ICBM, el cursor y el `random.Random`. La pausa es un indicador aparte, no un estado.

### Bucle

```python
def update(game: Game, inp: Inputs) -> None: ...                       # lógica pura, sin pygame
def render(game: Game, screen: pygame.Surface, frame: int) -> None: ...  # solo dibujo
def play_sounds(game: Game, bank: SoundBank) -> None: ...              # solo audio
```

`update()` no reproduce sonidos: añade eventos a `game.sound_events` y `play_sounds()` los consume. Así la lógica queda libre de pygame.

---

## 14. Controles

| Acción | Ratón | Teclado |
|---|---|---|
| Mover el cursor | movimiento relativo, como un trackball | flechas, 3 píxeles por frame |
| Disparar desde el silo izquierdo, central o derecho | botón izquierdo, central o derecho | `Z`, `X`, `C` |
| Empezar partida | — | `Enter` o `1` |
| Pausa | — | `P` |
| Pantalla completa | — | `F11` |
| Salir | — | `Esc` |

**Diseño.** El ratón funciona en modo relativo con `pygame.mouse.set_relative_mode(True)`, presente en pygame-ce 2.5.8, la versión verificada. El teclado existe porque muchos touchpads no tienen botón central.

---

## 15. Comprobaciones de `--test`

- Las tablas tienen la longitud correcta: 19 oleadas de ICBM y smart bombs, 15 retardos, 7 entradas de voladores y 29 radios.
- El multiplicador vale 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6 y 6 en las oleadas 1 a 12.
- Colisión: con radio 13 y un ICBM, un blanco en (13, 0) está dentro y uno en (14, 0) está fuera.
- Con una semilla fija, ninguna oleada pierde más de 3 ciudades.
- Determinismo: dos simulaciones `--headless` con la misma semilla dan la misma puntuación.

---

## 16. Plan de implementación

Cada hito es un commit, y el juego debe arrancar en todos ellos.

1. Ventana escalada, bucle a 60 Hz y cursor con sus límites.
2. Terreno, ciudades y silos. ABM con su X de destino y explosiones octogonales.
3. ICBM con estela, tabla de oleadas, colisión cada 5 frames, reacciones en cadena e impactos.
4. Puntuación, multiplicador, recuento de fin de oleada y avisos LOW y OUT.
5. MIRV y ritmo de lanzamiento.
6. Bombarderos y satélites.
7. Smart bombs con esquiva.
8. Ciudades bonus, fin de partida, récords y modo attract.
9. Colores por oleada, parpadeo y sonido.
10. `--headless`, `--test`, `--seed` y ruff limpio.

---

## 17. Fuera de alcance

- **Emular la ROM.** `missile.py` reimplementa las reglas; no ejecuta código 6502.
- **Funciones de la máquina.** Mueble cóctel, partida a dos jugadores, monedero y autotest.
- **Idiomas.** El original traía inglés, español, francés y alemán. `missile.py` empieza solo en inglés.
- **Fallos de la rev. 2.** Ni el fallo de los 810.000 puntos ni el multiplicador ×256 de las oleadas 255 y 256.
- **Invenciones.** Ni potenciadores, ni modos nuevos, ni juego en línea.

---

## 18. Licencia

El código de este repositorio se publica bajo licencia **MIT**: ver [`LICENSE`](LICENSE).

`missile.py` no copia código de Atari ni de MAME. Solo reproduce los parámetros de juego documentados aquí. El fuente original de Atari se cita como referencia de estudio y no tiene licencia libre. *Missile Command* es una marca de Atari.

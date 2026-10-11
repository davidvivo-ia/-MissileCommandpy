# missile.py

**Missile Command** (Atari, 1980, Dave Theurer) recreado en Python, en **un solo archivo: `missile.py`**.

El núcleo es la recreativa: sus reglas y sus tablas están traducidas rutina a rutina del código fuente original de Atari. Encima va una capa de mejoras: gráficos HD de noche cinematográfica, munición infinita, partículas, humo, sonido estéreo, mando, estadísticas, récords que se guardan y el juego en español. `--classic` lo quita todo y deja la recreativa pura.

```bash
pip install pygame-ce
python missile.py
```

No hay más archivos. Cielo, nubes, ciudades, fuego y textos se generan por código al arrancar, y el sonido se sintetiza.

---

## 1. Requisitos

- **Python 3.10 o superior.** Probado con Python 3.13 y pygame-ce 2.5.8.
- **pygame-ce** para jugar. No hace falta nada más: ni NumPy ni archivos de sonido, imagen o fuente.
- Sin pygame funcionan igual `--test` y `--headless`, que solo usan la biblioteca estándar.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pygame-ce
python missile.py                # o ./missile.py en Linux y macOS
```

---

## 2. Cómo se juega

Caen misiles balísticos (ICBM) sobre seis ciudades y las defiendes desde tres silos de antimisiles (ABM). Cada ABM vuela hasta la mira y explota; la explosión destruye todo atacante que toque, y cada atacante destruido explota a su vez, así que las reacciones en cadena son la clave. El silo central dispara más rápido que los laterales. Si una oleada termina sin ciudades en pie ni ciudades extra en reserva, se acaba la partida.

**Munición.** Por defecto es infinita: los silos no se vacían nunca. Siguen valiendo los límites del original: 8 ABM en vuelo como mucho, y un silo destruido no dispara hasta la oleada siguiente. Con `I` en el menú, o con `--ammo limited`, vuelves a los 10 ABM por silo y oleada de la recreativa, con su bonificación por cada ABM sin disparar. Cada modo tiene su propia tabla de récords.

### Controles

| Acción | Ratón | Teclado | Mando |
|---|---|---|---|
| Apuntar | mover | flechas; Mayús para afinar | stick izquierdo o cruceta |
| Disparar desde el silo izquierdo, central o derecho | botón izquierdo, central o derecho | `Z` `X` `C` (o `A` `S` `D`) | `X` `A` `B` (o `LB` `Y` `RB`) |
| Empezar a uno o a dos jugadores | clic | `Enter` o `1`; `2` para dos | `A` o `Start` |
| Munición infinita sí o no, en el menú | — | `I` | — |
| Pausa | — | `P` o `Esc`; `Esc` en pausa sale | `Start` |
| Ayuda en pantalla | — | `F1` | — |
| Estilo gráfico: HD, retro o arcade | — | `F2` | — |
| Efectos sí o no | — | `F3` | — |
| Pantalla completa | — | `F11` | — |
| Captura de pantalla | — | `F12` | — |
| Sonido sí o no | — | `M` | — |
| Ratón normal o trackball | — | `T` | — |
| Inglés o español | — | `L` | — |

- **Ratón normal:** la mira sigue al puntero. Es lo más cómodo en un escritorio.
- **Modo trackball:** el ratón mueve la mira por desplazamiento, como el control original; `--sens` ajusta la velocidad.
- **El juego se pausa solo** si la ventana pierde el foco en plena oleada.
- **Iniciales:** se escriben con el teclado o se eligen moviendo el ratón, la rueda o las flechas.
- **La ventana se puede redimensionar.** El campo conserva la proporción del original y, si sobra ancho, aparecen los paneles laterales.

---

## 3. Opciones de línea de comandos

| Opción | Efecto | Por defecto |
|---|---|---|
| `--cities N` | Ciudades iniciales, de 4 a 7, como el DIP del original. Con 7, una queda en reserva. | 6 |
| `--bonus N` | Puntos por ciudad extra: 8000, 10000, 12000, 14000, 15000, 18000 o 20000. `0` las desactiva (modo torneo). | 10000 |
| `--wave N` | Oleada inicial, para entrenar las difíciles. | 1 |
| `--seed N` | Semilla: con las mismas acciones, la misma partida. | aleatoria |
| `--style hd\|retro\|arcade` | Estilo gráfico (sección 4). | `hd` |
| `--ammo infinite\|limited` | Munición infinita o la del original. | `infinite` |
| `--classic` | Recreativa pura: estilo arcade, munición del original, sin efectos ni estadísticas. | — |
| `--mouse abs\|rel` | Ratón normal o trackball. | `abs` |
| `--lang en\|es` | Idioma de los textos. | el del sistema |
| `--sens F` | Sensibilidad del modo trackball. | 1.0 |
| `--scale N` | Altura inicial de la ventana en múltiplos de 231 píxeles; `0` la elige según el monitor. | 0 |
| `--fullscreen` | Arranca a pantalla completa. | — |
| `--mute` | Arranca sin sonido. | — |
| `--no-save` | No lee ni escribe récords ni ajustes. | — |
| `--headless` | Simula una partida con el piloto automático, sin ventana, e imprime el resultado. Usa la munición del original salvo con `--ammo infinite`. | — |
| `--frames N` | Límite de frames para `--headless`. | 324000 |
| `--test` | Ejecuta las comprobaciones internas. | — |

Lo que eliges con `F2`, `F3`, `I`, `T`, `M` y `L` se guarda para la próxima vez; una opción en la línea de comandos manda sobre lo guardado.

---

## 4. Lo que añade a la recreativa

Nada de esto cambia las reglas ni la puntuación. La única excepción es la munición infinita, que es opcional y lleva su propia tabla de récords.

### Estilo HD, el de por defecto

Una noche de cine en vez de una pantalla de píxeles. Nada brilla de más: el cielo es oscuro y la luz fuerte sale solo de lo que arde.

- **Resolución real:** el campo se dibuja a la resolución de la ventana hasta 1080 líneas y se escala por encima; en 4K el factor es exactamente 2. Las líneas van suavizadas y los sprites se dibujan al triple de tamaño y se reducen, así que no se ve un solo píxel.
- **Cielo:** degradado nocturno que cambia de tono cada dos oleadas, como los colores del original. Lleva estrellas que titilan, la Vía Láctea, una luna creciente con halo, nubes que cruzan con el borde plateado por la luna y dos cordilleras al fondo.
- **Luz:** todo lo que arde ilumina lo que tiene cerca. Las explosiones tiñen el cielo, las nubes y el suelo, y una viñeta suave cierra el encuadre.
- **Fuego:** bolas de fuego con lóbulos irregulares que se enfrían de blanco a rojo y dejan humo, chispas, ascuas y escombros.
- **Suelo:** el relieve del original, suavizado, con textura de tierra y las laderas que miran a la luna plateadas.
- **Ciudades vivas:** ventanas encendidas, antenas con una luz roja que parpadea y dos focos antiaéreos que barren el cielo. Las ciudades caídas humean y dejan ascuas.
- **Silos con torreta:** el cañón sigue a la mira, el piloto indica la munición y cada disparo deja un fogonazo.
- **Atacantes:** estelas con halo, smart bombs como estrellas violetas que giran y un bombardero y un satélite con detalle.
- **Textos y paneles:** tipografía de verdad y, si la ventana es ancha, paneles laterales con puntos, récord, oleada, multiplicador, ciudades, munición y mejor cadena. La pausa y la ayuda aparecen sobre el campo desenfocado.

### Estilos retro y arcade

- **Retro:** los píxeles del original en una imagen de tubo, con brillo, líneas de barrido, rejilla de fósforo y viñeta.
- **Arcade:** los píxeles y los ocho colores puros del hardware, con los efectos apagados. Es el que usa `--classic`.

Los dos escalan por números enteros, para que cada píxel del original sea un bloque nítido.

### Con cualquier estilo

- **Explosiones más vivas:** el radio crece de forma continua en pantalla. La colisión sigue el calendario exacto del original.
- **Temblor y destello:** la pantalla tiembla y se ilumina con los impactos, y mucho más con «THE END».
- **Puntos flotantes y cadenas:** cada derribo muestra sus puntos. Desde dos derribos encadenados suena un tono que sube, y desde tres aparece «CADENA n».
- **Título que se desintegra:** un bombardeo barre «MISSILE COMMAND» y se come las letras, como el arranque de la recreativa.
- **Informe de misión** al acabar: oleadas superadas, derribos por tipo, mejor cadena, ciudades perdidas, derribos por ABM y tiempo.
- **Récords y ajustes que se guardan** (sección 8).
- **Sonido estéreo:** cada efecto suena a la izquierda o a la derecha según dónde ocurre.
- **Mando, ratón normal, pausa automática, capturas y textos en español.**

`F3` apaga los efectos en cualquier estilo: partículas, humo, temblor, destello, focos, puntos flotantes, tonos de cadena e informe de misión.

### Dos jugadores

La recreativa admitía dos jugadores por turnos y aquí también está: se empieza con la tecla `2`. Cada jugador conserva sus ciudades, su puntuación y sus ciudades extra. Juegan la misma oleada uno detrás de otro: jugador 1 oleada 1, jugador 2 oleada 1, jugador 1 oleada 2. Cuando uno se queda sin ciudades, el otro sigue solo. Al final cada uno ve su informe y, si entra en la tabla, escribe sus iniciales.

---

## 5. Fidelidad al original

### De dónde salen los números

| Etiqueta | Fuente | Qué se ha sacado |
|---|---|---|
| `W3COMN` | [historicalsource/missile-command](https://github.com/historicalsource/missile-command), archivo `W3COMN.XX` | Constantes del fuente rev. 1: ciudades, silos, límites del cursor, ventana de MIRV, diámetro de explosión. |
| `W3MAIN` | El mismo repositorio, archivo `A35820.1D` | Lógica: lanzamientos, objetivos, MIRV, voladores, smart bombs, explosiones, colisión, recuento y ciudades extra. |
| rev. 3 | [Listado desensamblado de 6502disassembly.com](https://6502disassembly.com/va-missile-command/MissileCommand.html), de Andy McFadden | Tablas finales de oleadas y colores, y comprobación de cada rutina en la última versión de Atari. |
| McFadden | [Su guía del juego](https://6502disassembly.com/va-missile-command/) | Contexto y comportamiento descrito; cuando contradice al código, manda el código. |

El fuente usa `.RADIX 16`: los números sin punto son hexadecimales (`5F` = 95) y los que llevan punto son decimales (`10.` = 10). Si la rev. 1 y la rev. 3 difieren, manda la rev. 3.

### Reglas que reproduce

- **Pantalla:** 256 × 231 píxeles, con la y hacia arriba como el hardware, a 60 frames por segundo.
- **ABM:** 10 por silo con la munición del original, 8 en vuelo como mucho y no más de 16 entre ABM y explosiones defensivas. El silo central avanza 7 pasos por frame y los laterales 3. Al quedar 3 aparece LOW, y OUT al vaciarse (`W3MAIN UPABMS`, `ABMLAU`).
- **Explosiones:** 20 huecos en 5 grupos; cada explosión avanza un paso cada 5 frames, con radio 0, 2, 3… 13 y vuelta a 0. Son octógonos y la colisión usa la distancia aproximada del original, el mayor más 3/8 del menor, con 1 de margen para un ICBM, 3 para una smart bomb y 6 para un volador. Por debajo de la línea 33 no dañan y por encima de la 209 no se crean (`PREXPL`, `DAMAGE`, `DELTA`, `DETONA`).
- **Reacciones en cadena:** todo atacante destruido explota y su explosión destruye a otros.
- **ICBM:** avanzan una unidad por paso con un retardo 8.8 por oleada, que da el reparto irregular 1-2-1-2 frames del original. No salen ataques nuevos mientras el ICBM más alto esté por encima de max(202 − 2 × oleada, 180), y salen como mucho 4 por frame (`UPICBM`, `ICBLAU`, `ICNORM`).
- **MIRV:** un ICBM a una altura de 128 a 159 puede soltar hasta 3 cabezas, cada una hacia un objetivo distinto. No ocurre con 12 o más explosiones ni en el modo de demostración (`MIRVER`).
- **Objetivos:** nunca hay más de 3 ciudades entre destruidas y apuntadas en una oleada; después los ataques van a los silos (`GUICBM`).
- **Smart bombs:** desde la oleada 6, como mucho 3 a la vez, y una de cada cuatro salidas mientras queden ICBM. Esquivan lo que brilla cerca sin cambiar de objetivo. Hasta la oleada 8 no pueden esquivar hacia arriba; desde la 9, sí (`CMNEWP`, constante `STUPID`).
- **Voladores:** desde la oleada 2. El satélite avanza 1 píxel cada 2 frames y el bombardero cada 3. Disparan hasta 3 ICBM a la vez, solo entre x = 48 y x = 207 (`ACTPLA`, `PROPLA`).
- **Final acelerado:** sin ABM, sin explosiones y con ataques en el aire, todo cae a velocidad máxima; si además han caído 3 ciudades, la oleada termina en el acto (`TALIVE`).
- **Recuento:** un ABM cada 6 frames y después las ciudades, que se retiran en el orden desordenado del índice interno original. Las ciudades extra se calculan al cerrar la oleada y rellenan cráteres al azar (`ENDWV1` a `ENDWV5`, `REGEN`, `CHEKBO`).
- **Puntuación:** 25 por ICBM, 100 por volador, 125 por smart bomb, 5 por ABM sin disparar y 100 por ciudad en pie, por un multiplicador de ×1 a ×6.
- **Colores:** los 10 juegos de la tabla `$694e`, decodificados byte a byte; cambian cada 2 oleadas.
- **Piloto de demostración:** ataca los ICBM por orden de aparición, apunta a donde estarán dentro de 16 frames, mueve la mira a 2 píxeles por frame y no lleva más de 2 ABM en vuelo.
- **Las ciudades destruidas** quedan, en los estilos retro y arcade, como silueta en el color del suelo: el efecto de ruina del hardware.

### Correcciones a la guía de McFadden

Al contrastar cada regla con el código, cuatro afirmaciones de su guía no coinciden con el propio listado de la rev. 3 ni con el fuente rev. 1. Aquí manda el código:

- **Smart bombs:** la guía dice que desde la oleada 9 no esquivan hacia arriba. El código hace lo contrario: hasta la 8 no suben y desde la 9 sí.
- **MIRV:** la guía habla de la altura máxima vista al recorrer los huecos. El registro que se compara conserva la altura del propio ICBM, así que el candidato es cualquier ICBM entre 128 y 159.
- **Altura de los voladores:** la guía da 148 a 195 en las oleadas 2 y 3. El código da 148 a 180, 132 a 164 en las oleadas 4 y 5, y 100 a 132 después.
- **Cadencia de disparo de los voladores:** la guía la da en frames. El contador avanza al moverse, así que son píxeles recorridos: 128, 96, 64, 48, 32, 32 y 16 según la oleada.

### Tablas por oleada

```python
# Oleadas 1 a 19; de la 20 en adelante se repite la 19 (rev. 3)
ICBM_COUNT  = (12, 15, 18, 12, 16, 14, 17, 10, 13, 16, 19, 12, 14, 16, 18, 14, 17, 19, 22)
SMART_COUNT = ( 0,  0,  0,  0,  0,  1,  1,  2,  3,  4,  4,  5,  5,  6,  6,  7,  7,  7,  7)
# Retardo entre pasos de ICBM en frames, punto fijo 8.8: 0x04D0 = 4,8125 frames
ICBM_DELAY  = (0x04D0, 0x02E0, 0x01C0, 0x0108, 0x00A0, 0x0060, 0x0040, 0x0020,
               0x0010, 0x000A, 0x0006, 0x0004, 0x0002, 0x0001, 0x0000)
# Voladores, oleadas 2 a 8; de la 9 en adelante se repite la 8
FLIER_RECHARGE = (240, 160, 128, 128, 96, 64, 32)   # frames hasta el siguiente
FLIER_FIRE_GAP = (128,  96,  64,  48, 32, 32, 16)   # píxeles recorridos entre disparos
```

### Lo que se aproxima

- **La esquiva de las smart bombs:** el original lee píxeles de color parpadeante en 8 sondas alrededor de la bomba. Aquí las sondas preguntan por explosiones, marcas de destino y cabezas de misil cercanas, y eligen la salida con las mismas máscaras de 16 direcciones.
- **El sonido:** imita el estilo del chip POKEY con ondas cuadradas y ruido, pero no lo emula.
- **La tipografía, las ciudades, los voladores y el terreno** son diseño propio: no se ha copiado ningún gráfico de la ROM.
- **El bombardeo del título** sigue la idea del original, con un patrón propio.
- **Fuera de alcance:** la emulación de la ROM, el mueble cóctel, el monedero, el autotest y los fallos de la rev. 2, como el de los 810.000 puntos.

---

## 6. Arquitectura de `missile.py`

Unas 5.700 líneas en este orden:

1. **Tablas del original:** constantes, oleadas, colores, tipografía y sprites como texto.
2. **Entidades:** `Missile`, `Explosion`, `Flier`, `City`, `Silo`, `Player` y `Stats`, todas `dataclass` con `slots`.
3. **Lógica:** la clase `Game`, una máquina de fases. No importa pygame. Cada rutina de juego del original tiene su método, con el nombre de la rutina en el comentario.
4. **Piloto automático:** el fiel para la demostración y uno hábil para las simulaciones.
5. **Simulación y comprobaciones:** `--headless` y `--test`.
6. **Textos:** inglés y español.
7. **Render de píxeles (`PixelRenderer`):** dibuja a 256 × 231 y compone a escala entera con brillo, máscara CRT, temblor y destello. Es el de los estilos retro y arcade.
8. **Render HD (`HDRenderer`):** dibuja a la resolución de la ventana y suma encima una capa de luz a un cuarto de resolución. Lo caro, como cielo, suelo, ciudades, nubes y bolas de fuego, se dibuja una vez y se guarda. Durante el recuento de cada oleada prepara, pieza a pieza, los colores de la siguiente, para que el cambio no dé tirones.
9. **Sonido:** síntesis en Python puro, cargada en `pygame.mixer.Sound(buffer=…)`, con paneo estéreo.
10. **Controles, récords, ajustes y bucle principal.**

Los dos renders tienen la misma interfaz, así que `F2` los cambia en plena partida.

La lógica no conoce a quien la escucha: cada frame deja una lista de sucesos (`FX`) que el render convierte en partículas y el sonido en efectos. Por eso la misma partida corre con ventana, sin ventana o dentro de las pruebas.

El bucle va a paso fijo de 60 Hz, sin `dt`, porque todas las tablas del original cuentan frames. Si el ordenador no llega, el juego se ralentiza como la recreativa en vez de saltarse frames. En la máquina de pruebas, un frame HD cuesta unos 6 ms a 1920 × 1080, 11 ms a 2560 × 1440 y 14 ms en 4K; uno retro, unos 5 ms.

---

## 7. Pruebas

```bash
python missile.py --test                 # 19 comprobaciones de las reglas
python missile.py --headless --seed 3    # una partida completa sin ventana
ruff check missile.py && ruff format --check missile.py
```

`--test` comprueba, sin necesitar pygame:

- las tablas completas y el multiplicador;
- la colisión octogonal y el reloj 8.8 de los ICBM;
- que, para el mismo recorrido, el ABM central tarda 15 frames y los laterales 34;
- que una explosión dura unos 135 frames;
- el tope de 3 ciudades por oleada y que las smart bombs no suben antes de la oleada 9;
- la puntuación, las ciudades extra, el determinismo con semilla y partidas completas sin errores;
- que en oleadas altas aparecen smart bombs y voladores y que los MIRV se dividen;
- que todos los textos, también en español, tienen glifos y caben en pantalla;
- los turnos alternos a dos jugadores y la lectura y escritura de récords y ajustes;
- que con munición infinita los silos no bajan de 10 y los récords van a su propia tabla.

---

## 8. Datos que guarda

Los récords (`scores.json`) llevan una tabla por modo de munición, y los ajustes (`settings.json`) guardan estilo, efectos, munición, idioma, ratón y sonido. Los dos se guardan fuera del repositorio, en la carpeta de datos del usuario:

| Sistema | Carpeta |
|---|---|
| Linux | `~/.local/share/missile-py/` (o `$XDG_DATA_HOME/missile-py/`) |
| macOS | `~/Library/Application Support/missile-py/` |
| Windows | `%APPDATA%\missile-py\` |

Se escriben de forma atómica, y si el archivo falta o está dañado el juego arranca con los valores por defecto. Los récords de la versión 1.0 se leen como tabla de munición limitada. `--no-save` no toca nada. Las capturas de `F12` se guardan en la carpeta desde la que se lanza el juego, con la fecha y la hora en el nombre.

---

## 9. Licencia

El código se publica bajo licencia **MIT**: ver [`LICENSE`](LICENSE).

`missile.py` no copia código ni gráficos de Atari ni de MAME; reproduce las reglas y los parámetros de juego documentados aquí. El fuente original de Atari se cita como referencia de estudio y no tiene licencia libre. *Missile Command* es una marca de Atari, y este proyecto es un homenaje sin relación con la empresa.

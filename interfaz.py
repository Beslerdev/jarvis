"""
Interfaz holografica animada de JARVIS (pygame).
Estados: iniciando / espera / escuchando / pensando / hablando / rechazo
Teclas: F11 pantalla completa, ESC salir.
"""
import math
import random
import time
import datetime
import collections

import pygame


class Estado:
    """Estado compartido entre el asistente (hilo) y la interfaz (hilo principal)."""

    def __init__(self):
        self.modo = "iniciando"
        self.nivel = 0.0          # 0..1, intensidad de la voz de Jarvis
        self.simular_nivel = False
        self.usuario = ""
        self.jarvis = ""
        self.aviso = ""
        self.aviso_hasta = 0.0
        self.rechazo_hasta = 0.0
        self.activo = True

    def avisar(self, texto, segundos=3.0):
        self.aviso = texto
        self.aviso_hasta = time.time() + segundos

    def rechazar(self):
        self.rechazo_hasta = time.time() + 1.5
        self.avisar("VOZ NO AUTORIZADA", 1.5)


# Elementos opcionales de la pantalla
MOSTRAR_SUBTITULOS = False   # texto de lo que se habla, abajo
MOSTRAR_ONDA = False         # barras de sonido mientras habla

COLORES = {
    "iniciando": (0, 120, 200),
    "espera": (0, 150, 230),
    "escuchando": (0, 225, 255),
    "pensando": (255, 165, 40),
    "hablando": (110, 230, 255),
    "rechazo": (255, 50, 50),
}
ETIQUETAS = {
    "iniciando": "INICIANDO SISTEMAS",
    "espera": "EN ESPERA  -  DIGA \"JARVIS\"",
    "escuchando": "ESCUCHANDO",
    "pensando": "PROCESANDO",
    "hablando": "RESPONDIENDO",
    "rechazo": "ACCESO DENEGADO",
}


def mezclar(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def escalar(c, k):
    k = max(0.0, min(1.0, k))
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


class Brillo:
    """Sprites de resplandor radial (se suman con BLEND_ADD)."""

    def __init__(self):
        self.base = pygame.Surface((128, 128))
        for r in range(64, 0, -1):
            v = int(255 * (1 - r / 64) ** 2.2)
            pygame.draw.circle(self.base, (v, v, v), (64, 64), r)
        self.cache = {}

    def dibujar(self, sup, color, centro, radio, fuerza=1.0):
        radio = max(2, int(radio))
        clave = (escalar(color, fuerza), radio // 3 * 3)
        sprite = self.cache.get(clave)
        if sprite is None:
            sprite = pygame.transform.smoothscale(self.base, (clave[1] * 2 + 2, clave[1] * 2 + 2))
            sprite = sprite.copy()
            sprite.fill(clave[0], special_flags=pygame.BLEND_MULT)
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[clave] = sprite
        r = sprite.get_width() // 2
        sup.blit(sprite, (centro[0] - r, centro[1] - r), special_flags=pygame.BLEND_ADD)


class RedNeuronal:
    def __init__(self, n=95):
        self.nodos = []
        for _ in range(n):
            # punto aleatorio en una cascara esferica
            th = random.uniform(0, 2 * math.pi)
            ph = math.acos(random.uniform(-1, 1))
            r = random.uniform(0.45, 1.0)
            self.nodos.append([r * math.sin(ph) * math.cos(th), r * math.cos(ph), r * math.sin(ph) * math.sin(th)])
        self.energia = [0.0] * n
        vecinos = []
        for i, a in enumerate(self.nodos):
            d = sorted(range(n), key=lambda j: (a[0] - self.nodos[j][0]) ** 2 + (a[1] - self.nodos[j][1]) ** 2 + (a[2] - self.nodos[j][2]) ** 2)
            vecinos.append(d[1:4])
        aristas = set()
        for i, vs in enumerate(vecinos):
            for j in vs:
                aristas.add((min(i, j), max(i, j)))
        self.aristas = list(aristas)
        self.adyacencia = collections.defaultdict(list)
        for a, b in self.aristas:
            self.adyacencia[a].append(b)
            self.adyacencia[b].append(a)
        self.impulsos = []  # [origen, destino, progreso, profundidad]
        self.angulo = 0.0

    def disparar(self, cantidad):
        for _ in range(cantidad):
            i = random.randrange(len(self.nodos))
            self.energia[i] = 1.0
            for j in self.adyacencia[i]:
                self.impulsos.append([i, j, 0.0, 0])

    def actualizar(self, dt, velocidad_giro):
        self.angulo += dt * velocidad_giro
        self.energia = [e * math.exp(-dt * 3.0) for e in self.energia]
        nuevos = []
        for imp in self.impulsos:
            imp[2] += dt * 4.0
            if imp[2] >= 1.0:
                destino = imp[1]
                self.energia[destino] = 1.0
                if imp[3] < 3 and random.random() < 0.55:
                    siguientes = [k for k in self.adyacencia[destino] if k != imp[0]]
                    if siguientes:
                        nuevos.append([destino, random.choice(siguientes), 0.0, imp[3] + 1])
            else:
                nuevos.append(imp)
        self.impulsos = nuevos[:600]

    def proyectar(self, centro, radio):
        ca, sa = math.cos(self.angulo), math.sin(self.angulo)
        inc = 0.35
        ci, si = math.cos(inc), math.sin(inc)
        pts = []
        for x, y, z in self.nodos:
            x2 = x * ca - z * sa
            z2 = x * sa + z * ca
            y2 = y * ci - z2 * si
            z3 = y * si + z2 * ci
            p = 1.0 / (1.6 - z3 * 0.45)
            pts.append((centro[0] + x2 * radio * p, centro[1] + y2 * radio * p, (z3 + 1) / 2))
        return pts


def envolver(texto, fuente, ancho):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if fuente.size(prueba)[0] <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas[-3:]


def ejecutar(estado, titulo="J.A.R.V.I.S."):
    pygame.init()
    pygame.display.set_caption(titulo)
    pantalla = pygame.display.set_mode((1150, 780), pygame.RESIZABLE)
    reloj = pygame.time.Clock()
    f_chica = pygame.font.SysFont("consolas", 15)
    f_media = pygame.font.SysFont("consolas", 20)
    f_grande = pygame.font.SysFont("consolas", 30, bold=True)
    brillo = Brillo()
    red = RedNeuronal()
    historial = collections.deque([0.0] * 64, maxlen=64)
    color_actual = COLORES["iniciando"]
    rot = 0.0
    pantalla_completa = False
    t0 = time.time()

    while estado.activo:
        dt = reloj.tick(60) / 1000.0
        t = time.time() - t0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                estado.activo = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                pantalla_completa = not pantalla_completa
                pantalla = pygame.display.set_mode((0, 0) if pantalla_completa else (1150, 780),
                                                   pygame.FULLSCREEN if pantalla_completa else pygame.RESIZABLE)

        modo = "rechazo" if time.time() < estado.rechazo_hasta else estado.modo
        objetivo = COLORES.get(modo, COLORES["espera"])
        color_actual = mezclar(color_actual, objetivo, min(1.0, dt * 5))

        nivel = estado.nivel
        if modo == "hablando" and estado.simular_nivel:
            nivel = 0.35 + 0.45 * abs(math.sin(t * 9.0) * math.sin(t * 3.7))
        if modo != "hablando":
            nivel = 0.0
        historial.append(nivel)

        # actividad de la red segun el estado
        if modo == "hablando":
            red.disparar(int(nivel * 4 + (1 if random.random() < nivel * 2 else 0)))
            giro = 0.25 + nivel * 0.6
        elif modo == "pensando":
            red.disparar(1 if random.random() < 0.5 else 0)
            giro = 1.3
        elif modo == "escuchando":
            red.disparar(1 if random.random() < 0.12 else 0)
            giro = 0.35
        elif modo == "rechazo":
            red.disparar(1 if random.random() < 0.3 else 0)
            giro = 0.1
        else:
            red.disparar(1 if random.random() < 0.03 else 0)
            giro = 0.15
        red.actualizar(dt, giro)
        rot += dt * (2.5 if modo == "pensando" else 0.6)

        w, h = pantalla.get_size()
        cx, cy = w // 2, int(h * (0.43 if (MOSTRAR_SUBTITULOS or MOSTRAR_ONDA) else 0.5))
        R = int(min(w, h * 0.82) * 0.27)
        pantalla.fill((2, 6, 12))

        # rejilla de fondo
        for x in range(0, w, 40):
            pygame.draw.line(pantalla, (6, 16, 26), (x, 0), (x, h))
        for y in range(0, h, 40):
            pygame.draw.line(pantalla, (6, 16, 26), (0, y), (w, y))

        respiracion = 0.5 + 0.5 * math.sin(t * (4 if modo == "escuchando" else 1.5))
        brillo.dibujar(pantalla, color_actual, (cx, cy), R * 1.9, 0.18 + 0.12 * respiracion + nivel * 0.25)

        # anillos exteriores
        def arcos(radio, segmentos, hueco, angulo, grosor, k):
            rect = pygame.Rect(0, 0, radio * 2, radio * 2)
            rect.center = (cx, cy)
            paso = 2 * math.pi / segmentos
            for i in range(segmentos):
                a = angulo + i * paso
                pygame.draw.arc(pantalla, escalar(color_actual, k), rect, a, a + paso - hueco, grosor)

        arcos(int(R * 1.42), 3, 0.5, rot * 0.5, 3, 0.85)
        arcos(int(R * 1.34), 8, 0.25, -rot * 0.8, 2, 0.5)
        arcos(int(R * 1.52), 24, 0.18, rot * 0.25, 1, 0.35)
        for i in range(72):
            a = -rot * 0.35 + i * math.pi / 36
            largo = 10 if i % 6 == 0 else 4
            r1, r2 = R * 1.24, R * 1.24 + largo
            pygame.draw.line(pantalla, escalar(color_actual, 0.6),
                             (cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                             (cx + math.cos(a) * r2, cy + math.sin(a) * r2), 1)
        pygame.draw.circle(pantalla, escalar(color_actual, 0.25), (cx, cy), int(R * 1.15), 1)

        # red neuronal
        pts = red.proyectar((cx, cy), R * 1.45)
        for a, b in red.aristas:
            pa, pb = pts[a], pts[b]
            e = max(red.energia[a], red.energia[b])
            k = 0.08 + 0.25 * (pa[2] + pb[2]) / 2 + e * 0.8
            pygame.draw.aaline(pantalla, escalar(color_actual, k), pa[:2], pb[:2])
        for i, p in enumerate(pts):
            e = red.energia[i]
            k = 0.3 + 0.5 * p[2] + e
            pygame.draw.circle(pantalla, escalar(mezclar(color_actual, (255, 255, 255), e * 0.6), k),
                               (int(p[0]), int(p[1])), 2 + int(e * 2))
            if e > 0.25:
                brillo.dibujar(pantalla, color_actual, (int(p[0]), int(p[1])), 10 + e * 14, e * 0.9)
        for o, d, prog, _ in red.impulsos:
            x = pts[o][0] + (pts[d][0] - pts[o][0]) * prog
            y = pts[o][1] + (pts[d][1] - pts[o][1]) * prog
            brillo.dibujar(pantalla, (220, 250, 255), (int(x), int(y)), 7, 0.9)

        # nucleo
        rn = R * (0.16 + nivel * 0.10 + 0.015 * respiracion)
        brillo.dibujar(pantalla, color_actual, (cx, cy), rn * 3.2, 0.9)
        brillo.dibujar(pantalla, (255, 255, 255), (cx, cy), rn * 1.3, 0.5 + nivel * 0.5)
        arcos(int(R * 0.30), 6, 0.35, rot * 1.6, 2, 0.9)
        arcos(int(R * 0.36), 2, 1.2, -rot * 1.1, 1, 0.6)

        # onda de voz
        ancho_barra = 6
        base_y = int(cy + R * 1.68)
        inicio_x = cx - len(historial) * ancho_barra // 2
        for i, v in enumerate(historial if MOSTRAR_ONDA else []):
            alto = 2 + int(v * 38)
            x = inicio_x + i * ancho_barra
            pygame.draw.rect(pantalla, escalar(color_actual, 0.35 + v), (x, base_y - alto, ancho_barra - 2, alto * 2))

        # textos
        pantalla.blit(f_grande.render("J.A.R.V.I.S.", True, color_actual), (28, 22))
        ahora = datetime.datetime.now()
        pantalla.blit(f_media.render(ahora.strftime("%H:%M:%S"), True, escalar(color_actual, 0.8)), (30, 62))
        pantalla.blit(f_chica.render(ahora.strftime("%d/%m/%Y"), True, escalar(color_actual, 0.5)), (30, 88))
        etiqueta = f_media.render(ETIQUETAS.get(modo, ""), True, color_actual)
        pantalla.blit(etiqueta, (w - etiqueta.get_width() - 28, 30))
        if estado.aviso and time.time() < estado.aviso_hasta:
            av = f_media.render(estado.aviso, True, (255, 90, 90) if modo == "rechazo" else color_actual)
            pantalla.blit(av, (cx - av.get_width() // 2, int(cy - R * 1.62) - 20))

        y = base_y + 50
        if MOSTRAR_SUBTITULOS and estado.usuario:
            for linea in envolver("> " + estado.usuario, f_chica, w - 160):
                s = f_chica.render(linea, True, (150, 170, 185))
                pantalla.blit(s, (cx - s.get_width() // 2, y))
                y += 20
        if MOSTRAR_SUBTITULOS and estado.jarvis:
            for linea in envolver(estado.jarvis, f_media, w - 160):
                s = f_media.render(linea, True, mezclar(color_actual, (255, 255, 255), 0.4))
                pantalla.blit(s, (cx - s.get_width() // 2, y))
                y += 26

        pantalla.blit(f_chica.render("F11 pantalla completa  |  ESC salir", True, (40, 70, 90)), (28, h - 26))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    # Demo sin asistente: recorre los estados
    import threading
    e = Estado()

    def demo():
        for modo, seg in [("espera", 3), ("escuchando", 3), ("pensando", 3), ("hablando", 6)] * 3:
            e.modo = modo
            e.simular_nivel = True
            e.jarvis = "Demostración de la interfaz, señor." if modo == "hablando" else e.jarvis
            time.sleep(seg)
        e.activo = False
    threading.Thread(target=demo, daemon=True).start()
    ejecutar(e)

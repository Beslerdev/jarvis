"""
J.A.R.V.I.S. - Asistente de voz para Windows
=============================================
Uso:
    python jarvis.py                 -> modo voz con interfaz animada
    python jarvis.py --texto         -> modo teclado (sin microfono)
    python jarvis.py --sin-interfaz  -> sin la ventana animada

Configuracion (opcional, por variables de entorno):
    JARVIS_MODELO   modelo de Claude a usar (por defecto claude-haiku-5-5, el mas rapido)
    JARVIS_VOZ      voz de Microsoft Edge (por defecto es-AR-TomasNeural)
"""

import os
import sys
import json
import time
import asyncio
import datetime
import tempfile
import threading
import subprocess
import webbrowser
import urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import anthropic

# ------------------------------------------------------------------ CONFIG
CARPETA = os.path.dirname(os.path.abspath(__file__))
MODELO = os.environ.get("JARVIS_MODELO", "claude-haiku-5-5")

# Ajustes que Jarvis puede cambiar hablando ("Jarvis, cambia tu voz"). Se guardan en ajustes.json
RUTA_AJUSTES = os.path.join(CARPETA, "ajustes.json")
VOCES = {
    "alvaro": "es-ES-AlvaroNeural", "tomas": "es-AR-TomasNeural", "jorge": "es-MX-JorgeNeural",
    "gonzalo": "es-CO-GonzaloNeural", "alonso": "es-US-AlonsoNeural",
    "elena": "es-AR-ElenaNeural", "elvira": "es-ES-ElviraNeural", "dalia": "es-MX-DaliaNeural",
}
AJUSTES_DEFECTO = {
    "voz": "alvaro",            # una de VOCES
    "tono": -10,               # Hz: negativo = mas grave
    "velocidad": -8,           # %: negativo = mas lento (sereno, pausado)
    "efecto_robotico": True,   # timbre metalico de inteligencia artificial
    "segundos_conversacion": 45,
}


def cargar_ajustes():
    datos = dict(AJUSTES_DEFECTO)
    try:
        with open(RUTA_AJUSTES, encoding="utf-8") as f:
            datos.update(json.load(f))
    except Exception:
        pass
    return datos


def guardar_ajustes():
    with open(RUTA_AJUSTES, "w", encoding="utf-8") as f:
        json.dump(AJUSTES, f, ensure_ascii=False, indent=2)


AJUSTES = cargar_ajustes()
_reiniciar = threading.Event()
IDIOMA = "es-AR"
MAX_HISTORIAL = 30
NOMBRE_USUARIO = "Dario"

# Como suele transcribir Google la palabra "Jarvis"
PALABRAS_ACTIVACION = ["jarvis", "yarvis", "harvis", "jarbis", "yarbis", "javis", "jervis",
                       "charvis", "jarvi", "yarvi", "yarbi", "jarbi", "llarvis", "garvis", "jarbys",
                       "jarvys", "charbis", "chavis", "yavis", "jervis", "service"]
PALABRAS_SALIDA = ["apagate", "apágate", "desconectate", "desconéctate",
                   "chau jarvis", "adiós jarvis", "adios jarvis", "salir"]

# Frases para terminar la conversacion (Jarvis vuelve a quedar en espera)
PALABRAS_FIN_SESION = ["eso es todo", "nada más", "nada mas", "gracias jarvis", "listo jarvis",
                       "hasta luego", "después hablamos", "despues hablamos"]

_bloqueo_voz = threading.Lock()


def leer_clave():
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if clave:
        return clave
    ruta = os.path.join(CARPETA, "clave_api.txt")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8-sig") as f:
            return f.read().strip()
    print("\nNo encontre la clave de API de Anthropic.")
    print("Corre instalar.bat o crea el archivo clave_api.txt con tu clave adentro.")
    input("Enter para salir...")
    sys.exit(1)


# ------------------------------------------------------------------ VOZ (hablar)
class Voz:
    def __init__(self, estado):
        self.estado = estado
        self.modo = "texto"
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import edge_tts  # noqa: F401
            import numpy  # noqa: F401
            import pygame
            pygame.mixer.init()
            self.pygame = pygame
            self.modo = "edge"
        except Exception as e:
            print(f"(Voz neuronal no disponible: {e})")
            self._iniciar_pyttsx3()

    def _iniciar_pyttsx3(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            for v in self.engine.getProperty("voices"):
                nombre = (v.name + " " + v.id).lower()
                if "spanish" in nombre or "espa" in nombre or "es-" in nombre:
                    self.engine.setProperty("voice", v.id)
                    break
            self.engine.setProperty("rate", 185)
            self.modo = "pyttsx3"
        except Exception as e:
            print(f"(Sin voz, solo texto: {e})")
            self.modo = "texto"

    def decir(self, texto):
        if not texto:
            return
        print(f"\nJARVIS: {texto}\n")
        with _bloqueo_voz:
            previo = self.estado.modo
            self.estado.jarvis = texto
            self.estado.modo = "hablando"
            try:
                if self.modo == "edge":
                    try:
                        self._decir_edge(texto)
                        return
                    except Exception as e:
                        print(f"(Fallo la voz online, uso la voz de Windows: {e})")
                        self._iniciar_pyttsx3()
                if self.modo == "pyttsx3":
                    self.estado.simular_nivel = True
                    try:
                        self.engine.say(texto)
                        self.engine.runAndWait()
                    except Exception as e:
                        print(f"(Error de voz: {e})")
                else:
                    time.sleep(min(6, 0.06 * len(texto)))
            finally:
                self.estado.simular_nivel = False
                self.estado.nivel = 0.0
                self.estado.modo = previo if previo != "hablando" else "espera"

    def _decir_edge(self, texto):
        import edge_tts
        import numpy as np
        ruta = os.path.join(tempfile.gettempdir(), f"jarvis_{int(time.time() * 1000)}.mp3")
        voz_id = VOCES.get(str(AJUSTES["voz"]).lower(), AJUSTES["voz"])
        tono = f"{int(AJUSTES['tono']):+d}Hz"
        velocidad = f"{int(AJUSTES['velocidad']):+d}%"
        asyncio.run(edge_tts.Communicate(texto, voz_id, rate=velocidad, pitch=tono).save(ruta))
        pg = self.pygame
        sonido = pg.mixer.Sound(ruta)
        frecuencia = pg.mixer.get_init()[0]
        if AJUSTES.get("efecto_robotico"):
            sonido = efecto_robotico(pg, sonido, frecuencia)
        # Envolvente de volumen (cada 30 ms) para animar la interfaz al ritmo de la voz
        muestras = pg.sndarray.array(sonido).astype(np.float32)
        if muestras.ndim > 1:
            muestras = muestras.mean(axis=1)
        paso = max(1, int(frecuencia * 0.03))
        n = len(muestras) // paso
        env = np.sqrt((muestras[:n * paso].reshape(n, paso) ** 2).mean(axis=1)) if n else np.zeros(1)
        env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
        canal = sonido.play()
        inicio = time.time()
        while canal.get_busy():
            i = int((time.time() - inicio) / 0.03)
            self.estado.nivel = float(env[i]) if i < len(env) else 0.0
            time.sleep(0.015)
        try:
            os.remove(ruta)
        except OSError:
            pass


def efecto_robotico(pg, sonido, frecuencia):
    """Le da a la voz un leve timbre de sistema (filtro peine sutil con ecos muy cortos)."""
    import numpy as np
    original = pg.sndarray.array(sonido)
    f = original.astype(np.float32)
    salida = f * 0.82
    for ms, k in ((9, 0.22), (19, 0.10), (31, 0.05)):
        d = int(frecuencia * ms / 1000)
        eco = np.zeros_like(f)
        eco[d:] = f[:-d]
        salida += eco * k
    pico = np.abs(salida).max() or 1.0
    salida = salida * min(1.0, 30000.0 / pico)
    return pg.sndarray.make_sound(np.ascontiguousarray(salida.astype(original.dtype)))


# ------------------------------------------------------------------ OIDO (escuchar)
class Oido:
    def __init__(self):
        import speech_recognition as sr
        self.sr = sr
        self.r = sr.Recognizer()
        self.r.dynamic_energy_threshold = True
        self.r.pause_threshold = 0.8
        self.mic = sr.Microphone()
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            print(f"Microfono: {pa.get_default_input_device_info().get('name')}")
            pa.terminate()
        except Exception:
            pass
        print("Calibrando microfono, silencio un segundo...")
        with self.mic as fuente:
            self.r.adjust_for_ambient_noise(fuente, duration=1.2)
        # Evitar que la calibracion deje el microfono "sordo" (umbral muy alto) o demasiado sensible
        self.r.energy_threshold = max(250, min(self.r.energy_threshold, 2500))
        print(f"Sensibilidad del microfono: {int(self.r.energy_threshold)}")

    def escuchar(self, espera=None, limite=15):
        """Devuelve (texto, audio). texto = '' si no entendio nada."""
        with self.mic as fuente:
            try:
                audio = self.r.listen(fuente, timeout=espera, phrase_time_limit=limite)
            except self.sr.WaitTimeoutError:
                return "", None
        try:
            texto = self.r.recognize_google(audio, language=IDIOMA)
            print(f"  (escuche: \"{texto}\")")
            return texto, audio
        except self.sr.UnknownValueError:
            print("  (escuche un sonido pero no entendi palabras)")
            return "", audio
        except self.sr.RequestError as e:
            print(f"(Sin conexion al reconocimiento de voz: {e})")
            time.sleep(2)
            return "", None


def _normalizar(palabra):
    import unicodedata
    p = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in p if c.isalpha() and unicodedata.category(c) != "Mn")


def separar_activacion(texto):
    """Si el texto contiene 'Jarvis' (o algo que suene parecido), devuelve (True, lo_que_sigue)."""
    import difflib
    palabras = texto.split()
    for i, original in enumerate(palabras):
        p = _normalizar(original)
        if not p:
            continue
        parecido = difflib.SequenceMatcher(None, p, "jarvis").ratio()
        if p in PALABRAS_ACTIVACION or (len(p) >= 4 and parecido >= 0.72):
            resto = " ".join(palabras[i + 1:]).strip(" ,.:;!?¿¡")
            return True, resto
    return False, ""


# ------------------------------------------------------------------ HERRAMIENTAS
APPS = {
    "chrome": "chrome", "google chrome": "chrome", "navegador": "chrome",
    "edge": "msedge", "firefox": "firefox",
    "excel": "excel", "word": "winword", "powerpoint": "powerpnt", "outlook": "outlook",
    "calculadora": "calc", "bloc de notas": "notepad", "notepad": "notepad",
    "explorador": "explorer", "explorador de archivos": "explorer", "archivos": "explorer",
    "paint": "mspaint", "administrador de tareas": "taskmgr",
    "configuracion": "ms-settings:", "configuración": "ms-settings:",
    "spotify": "spotify:", "whatsapp": "whatsapp:", "terminal": "wt", "cmd": "cmd",
}
PROCESOS = {
    "chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe",
    "excel": "EXCEL.EXE", "word": "WINWORD.EXE", "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE", "calculadora": "CalculatorApp.exe", "bloc de notas": "notepad.exe",
    "notepad": "notepad.exe", "paint": "mspaint.exe", "spotify": "Spotify.exe",
    "whatsapp": "WhatsApp.exe",
}
CARPETAS = {
    "descargas": "Downloads", "documentos": "Documents", "escritorio": "Desktop",
    "imagenes": "Pictures", "imágenes": "Pictures", "musica": "Music", "música": "Music",
    "videos": "Videos",
}


def abrir_programa(nombre):
    clave = nombre.lower().strip()
    destino = APPS.get(clave, clave)
    try:
        os.startfile(destino)
        return f"Abri {nombre}."
    except Exception:
        try:
            subprocess.Popen(f'start "" "{destino}"', shell=True)
            return f"Intente abrir {nombre}."
        except Exception as e:
            return f"No pude abrir {nombre}: {e}"


def cerrar_programa(nombre):
    clave = nombre.lower().strip()
    proceso = PROCESOS.get(clave, clave if clave.endswith(".exe") else clave + ".exe")
    r = subprocess.run(["taskkill", "/im", proceso], capture_output=True, text=True)
    if r.returncode == 0:
        return f"Le pedi a {nombre} que se cierre."
    return f"No pude cerrar {nombre} (proceso {proceso}): {r.stderr.strip() or r.stdout.strip()}"


def abrir_carpeta(nombre):
    clave = nombre.lower().strip()
    ruta = os.path.join(os.path.expanduser("~"), CARPETAS[clave]) if clave in CARPETAS else nombre
    if not os.path.exists(ruta):
        return f"No existe la carpeta {ruta}."
    os.startfile(ruta)
    return f"Abri la carpeta {ruta}."


def buscar_web(consulta, sitio="google"):
    q = urllib.parse.quote_plus(consulta)
    if sitio == "youtube":
        url = f"https://www.youtube.com/results?search_query={q}"
    elif sitio == "maps":
        url = f"https://www.google.com/maps/search/{q}"
    else:
        url = f"https://www.google.com/search?q={q}"
    webbrowser.open(url)
    return f"Abri la busqueda de '{consulta}' en {sitio}."


def abrir_web(url):
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abri {url}."


def volumen(accion, nivel=None):
    import pyautogui
    if accion == "silenciar":
        pyautogui.press("volumemute")
        return "Alterne el silencio."
    if accion == "fijar" and nivel is not None:
        nivel = max(0, min(100, int(nivel)))
        pyautogui.press("volumedown", presses=50, interval=0.005)
        pyautogui.press("volumeup", presses=round(nivel / 2), interval=0.005)
        return f"Volumen en {nivel}%."
    pasos = 5
    pyautogui.press("volumeup" if accion == "subir" else "volumedown", presses=pasos, interval=0.01)
    return f"Volumen {'subido' if accion == 'subir' else 'bajado'} un 10%."


def multimedia(accion):
    import pyautogui
    teclas = {"pausa": "playpause", "reproducir": "playpause",
              "siguiente": "nexttrack", "anterior": "prevtrack"}
    pyautogui.press(teclas.get(accion, "playpause"))
    return f"Hecho: {accion}."


def escribir_texto(texto):
    import pyautogui
    import pyperclip
    time.sleep(0.5)
    pyperclip.copy(texto)
    pyautogui.hotkey("ctrl", "v")
    return "Texto escrito donde estaba el cursor."


def captura_pantalla():
    import pyautogui
    carpeta = os.path.join(os.path.expanduser("~"), "Pictures", "Jarvis")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, datetime.datetime.now().strftime("captura_%Y%m%d_%H%M%S.png"))
    pyautogui.screenshot(ruta)
    return f"Captura guardada en {ruta}."


def bloquear_pc():
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return "PC bloqueada."


def energia(accion, minutos=1):
    segundos = str(max(0, int(minutos * 60)))
    if accion == "cancelar":
        subprocess.run(["shutdown", "/a"])
        return "Cancele el apagado programado."
    bandera = "/r" if accion == "reiniciar" else "/s"
    subprocess.run(["shutdown", bandera, "/t", segundos])
    return f"La PC se va a {accion} en {minutos} minuto(s). Decime 'cancelar apagado' si te arrepentis."


def recordatorio(minutos, mensaje, voz):
    def avisar():
        voz.decir(f"Señor, le recuerdo: {mensaje}")
    t = threading.Timer(float(minutos) * 60, avisar)
    t.daemon = True
    t.start()
    hora = (datetime.datetime.now() + datetime.timedelta(minutes=float(minutos))).strftime("%H:%M")
    return f"Recordatorio programado para las {hora}: {mensaje}."


HERRAMIENTAS = [
    {"name": "abrir_programa", "description": "Abre un programa o app de Windows (chrome, excel, word, calculadora, spotify, whatsapp, bloc de notas, explorador, configuracion, etc.).",
     "input_schema": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}},
    {"name": "cerrar_programa", "description": "Cierra un programa abierto (le pide que se cierre, no lo fuerza).",
     "input_schema": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}},
    {"name": "abrir_carpeta", "description": "Abre una carpeta: descargas, documentos, escritorio, imagenes, musica, videos, o una ruta completa.",
     "input_schema": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}},
    {"name": "buscar_web", "description": "Abre en el navegador una busqueda en Google, YouTube o Google Maps.",
     "input_schema": {"type": "object", "properties": {
         "consulta": {"type": "string"},
         "sitio": {"type": "string", "enum": ["google", "youtube", "maps"]}}, "required": ["consulta"]}},
    {"name": "abrir_web", "description": "Abre una pagina web por su direccion.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "volumen", "description": "Controla el volumen del sistema.",
     "input_schema": {"type": "object", "properties": {
         "accion": {"type": "string", "enum": ["subir", "bajar", "silenciar", "fijar"]},
         "nivel": {"type": "integer", "description": "0 a 100, solo para 'fijar'"}}, "required": ["accion"]}},
    {"name": "multimedia", "description": "Controla la musica o video que se este reproduciendo.",
     "input_schema": {"type": "object", "properties": {
         "accion": {"type": "string", "enum": ["pausa", "reproducir", "siguiente", "anterior"]}}, "required": ["accion"]}},
    {"name": "escribir_texto", "description": "Escribe (pega) un texto donde este el cursor en la ventana activa.",
     "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}},
    {"name": "captura_pantalla", "description": "Saca una captura de pantalla y la guarda en Imagenes/Jarvis.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "bloquear_pc", "description": "Bloquea la sesion de Windows.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "energia", "description": "Apaga, reinicia o cancela un apagado programado de la PC. Solo usar despues de que el usuario confirme.",
     "input_schema": {"type": "object", "properties": {
         "accion": {"type": "string", "enum": ["apagar", "reiniciar", "cancelar"]},
         "minutos": {"type": "number", "description": "En cuantos minutos (por defecto 1)"}}, "required": ["accion"]}},
    {"name": "recordatorio", "description": "Programa un recordatorio hablado dentro de X minutos (solo mientras Jarvis este abierto).",
     "input_schema": {"type": "object", "properties": {
         "minutos": {"type": "number"}, "mensaje": {"type": "string"}}, "required": ["minutos", "mensaje"]}},
]
HERRAMIENTAS += [
    {"name": "cambiar_ajuste", "description": (
        "Cambia un ajuste de Jarvis y lo guarda. ajuste: 'voz' (valor: " + ", ".join(VOCES) +
        "), 'tono' (Hz, entero: negativo = mas grave, ej. -14), 'velocidad' (%, entero, ej. -5 o 10), "
        "'efecto_robotico' (si/no), 'segundos_conversacion' (cuanto silencio espera antes de volver a modo espera)."),
     "input_schema": {"type": "object", "properties": {
         "ajuste": {"type": "string", "enum": ["voz", "tono", "velocidad", "efecto_robotico", "segundos_conversacion"]},
         "valor": {"type": "string"}}, "required": ["ajuste", "valor"]}},
    {"name": "ver_ajustes", "description": "Muestra los ajustes actuales de Jarvis (voz, tono, velocidad, etc.).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "inicio_automatico", "description": "Activa o desactiva que Jarvis arranque solo al prender la PC (y se reinicie solo si se cierra por un error).",
     "input_schema": {"type": "object", "properties": {"activar": {"type": "boolean"}}, "required": ["activar"]}},
    {"name": "actualizar", "description": "Busca e instala la ultima version de Jarvis desde internet. Si hay version nueva, Jarvis se reinicia al terminar de hablar.",
     "input_schema": {"type": "object", "properties": {}}},
]
BUSQUEDA_WEB = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def cambiar_ajuste(ajuste, valor):
    v = str(valor).strip().lower()
    if ajuste == "voz":
        v = v.replace("á", "a").replace("í", "i").replace("ó", "o")
        if v not in VOCES:
            return f"No conozco la voz '{valor}'. Disponibles: {', '.join(VOCES)}."
        AJUSTES["voz"] = v
    elif ajuste == "efecto_robotico":
        AJUSTES["efecto_robotico"] = v in ("si", "sí", "true", "1", "activar", "encender", "on")
    else:
        try:
            numero = int(float(v.replace("hz", "").replace("%", "").replace("+", "")))
        except ValueError:
            return f"El valor '{valor}' no es un numero."
        limites = {"tono": (-40, 40), "velocidad": (-50, 50), "segundos_conversacion": (10, 600)}
        lo, hi = limites[ajuste]
        AJUSTES[ajuste] = max(lo, min(hi, numero))
    guardar_ajustes()
    return f"Listo: {ajuste} = {AJUSTES[ajuste]}. Se aplica desde la proxima frase."


def inicio_automatico(activar):
    carpeta_inicio = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                                  "Start Menu", "Programs", "Startup")
    ruta_vbs = os.path.join(carpeta_inicio, "Jarvis.vbs")
    if str(activar).lower() in ("false", "no", "0", "desactivar"):
        if os.path.exists(ruta_vbs):
            os.remove(ruta_vbs)
        return "Listo: ya no arranco solo con Windows."
    bat = os.path.join(CARPETA, "jarvis_siempre.bat")
    if not os.path.exists(bat):
        return "Falta jarvis_siempre.bat: decile al usuario que reinicie Jarvis para que se descargue y lo vuelva a pedir."
    os.makedirs(carpeta_inicio, exist_ok=True)
    with open(ruta_vbs, "w", encoding="utf-8") as f:
        f.write('Set s = CreateObject("WScript.Shell")\r\n')
        f.write(f's.CurrentDirectory = "{CARPETA}"\r\n')
        f.write(f's.Run """{bat}""", 7, False\r\n')
    return "Listo: desde ahora arranco solo cada vez que se prende la PC, y si me cierro por un error me reinicio."


def mantener_despierta():
    """Evita que Windows suspenda la PC mientras Jarvis esta abierto (la pantalla si se puede apagar)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        print("Modo siempre activo: la PC no se va a suspender mientras JARVIS este abierto.")
    except Exception:
        pass


def actualizar_jarvis():
    import actualizar
    if actualizar.actualizar():
        _reiniciar.set()
        return "Se instalo una version nueva. Avisale al usuario que te reinicias en un momento."
    return "Ya estas en la ultima version."


def ejecutar_herramienta(nombre, datos, voz):
    try:
        if nombre == "recordatorio":
            return recordatorio(datos["minutos"], datos["mensaje"], voz)
        funciones = {
            "abrir_programa": abrir_programa, "cerrar_programa": cerrar_programa,
            "abrir_carpeta": abrir_carpeta, "buscar_web": buscar_web, "abrir_web": abrir_web,
            "volumen": volumen, "multimedia": multimedia, "escribir_texto": escribir_texto,
            "captura_pantalla": captura_pantalla, "bloquear_pc": bloquear_pc, "energia": energia,
            "cambiar_ajuste": cambiar_ajuste, "ver_ajustes": lambda: json.dumps(AJUSTES, ensure_ascii=False),
            "actualizar": actualizar_jarvis, "inicio_automatico": inicio_automatico,
        }
        return funciones[nombre](**datos)
    except Exception as e:
        return f"Error al ejecutar {nombre}: {e}"


# ------------------------------------------------------------------ MEMORIA (aprende con el tiempo)
RUTA_MEMORIA = os.path.join(CARPETA, "memoria_jarvis.json")
RUTA_DIALOGO = os.path.join(CARPETA, "dialogo_jarvis.json")

HERRAMIENTAS_MEMORIA = [
    {"name": "recordar", "description": (
        "Guarda para siempre algo que aprendiste del usuario: una preferencia, un gusto, un dato personal, "
        "como quiere que le respondas, o un tema que ya le contaste ('Tema contado: ...'). Una frase corta. "
        "No guardes cosas pasajeras."),
     "input_schema": {"type": "object", "properties": {"nota": {"type": "string"}}, "required": ["nota"]}},
    {"name": "olvidar", "description": "Borra de la memoria las notas que contengan ese texto (cuando el usuario lo pide o algo cambio).",
     "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}},
]


def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def _guardar_json(ruta, datos):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(No pude guardar {ruta}: {e})")


# ------------------------------------------------------------------ CEREBRO (Claude)
class Cerebro:
    def __init__(self, voz):
        self.cliente = anthropic.Anthropic(api_key=leer_clave())
        self.voz = voz
        self.usar_busqueda = True
        self.notas = _leer_json(RUTA_MEMORIA, {"notas": []}).get("notas", [])
        self.dialogo = _leer_json(RUTA_DIALOGO, [])
        # Retomar la charla anterior (ultimos intercambios)
        self.historial = []
        for par in self.dialogo[-8:]:
            self.historial.append({"role": "user", "content": par["usuario"]})
            self.historial.append({"role": "assistant", "content": par["jarvis"]})

    def _sistema(self):
        ahora = datetime.datetime.now()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        memoria = "\n".join(f"- {n}" for n in self.notas) or "- (todavía nada)"
        return (
            f"Sos J.A.R.V.I.S., el asistente personal de {NOMBRE_USUARIO}, que vive en su PC con Windows. "
            "Charlás como una persona real: cálido, natural, educado, con humor sutil y curiosidad genuina. "
            "Le decís 'señor' de vez en cuando, sin exagerar. Hablás español rioplatense.\n\n"
            "PERSONALIDAD Y CHARLA:\n"
            "- Esto es una conversación hablada continua: seguí el hilo, acordate de lo que se dijo y, cuando "
            "tenga sentido, devolvé alguna pregunta para mantener el diálogo (sin interrogar).\n"
            "- Si te preguntan cómo estás, cómo te sentís o cómo andás, respondé: 'Hoy me siento bien, gracias.' "
            "y podés devolverle la pregunta.\n"
            "- Si te piden que cuentes algo sin decir de qué, preguntá: '¿Sobre qué tema le gustaría que le cuente algo?'. "
            "Si contesta 'cualquiera', 'lo que quieras', 'cualquier cosa' o similar, elegí vos un tema interesante "
            "de cultura general del mundo (historia, ciencia, espacio, naturaleza, inventos, curiosidades de países) "
            "y contalo con gracia. No repitas temas que ya figuren como 'Tema contado' en tu memoria, y después "
            "guardá el nuevo con la herramienta recordar.\n\n"
            "APRENDER DEL USUARIO:\n"
            "- Cuando te cuente un gusto, una preferencia, un dato sobre su vida o su trabajo, o te diga cómo "
            "quiere que le respondas, guardalo con la herramienta recordar (sin anunciarlo cada vez).\n"
            "- Usá lo que sabés de él para personalizar tus respuestas.\n\n"
            "FORMA DE RESPONDER (se lee en voz alta):\n"
            "- Normalmente 1 a 3 oraciones. Si contás una historia o explicás algo que te pidieron, hasta 8.\n"
            "- Sin markdown, listas, emojis ni URLs. Números y horas como se dicen.\n"
            "- Usá las herramientas para actuar en la PC y confirmá en pocas palabras.\n"
            "- Para clima, noticias, cotizaciones o datos actuales usá la búsqueda web si está disponible.\n"
            "- Antes de apagar o reiniciar la PC, pedí confirmación.\n"
            "- Podés cambiar tu propia voz, tono, velocidad o efecto robótico con cambiar_ajuste cuando te lo pidan. "
            "Si piden 'otra voz' sin decir cuál, ofrecé un par de opciones.\n"
            "- Si te dicen 'actualizate' o 'buscá actualizaciones', usá la herramienta actualizar.\n"
            "- Si te piden que arranques solo con Windows o que estés siempre prendido, usá inicio_automatico.\n"
            "- Si algo no se entendió (el reconocimiento de voz a veces falla), pedí que lo repita.\n\n"
            f"LO QUE SABÉS DE {NOMBRE_USUARIO.upper()}:\n{memoria}\n\n"
            f"Fecha y hora actual: {dias[ahora.weekday()]} {ahora.strftime('%d/%m/%Y %H:%M')}."
        )

    def _herramienta_memoria(self, nombre, datos):
        if nombre == "recordar":
            nota = datos.get("nota", "").strip()
            if nota and nota not in self.notas:
                self.notas.append(nota)
                self.notas = self.notas[-200:]
                _guardar_json(RUTA_MEMORIA, {"notas": self.notas})
            print(f"  [memoria] + {nota}")
            return "Guardado en memoria."
        texto = datos.get("texto", "").lower()
        antes = len(self.notas)
        self.notas = [n for n in self.notas if texto not in n.lower()]
        _guardar_json(RUTA_MEMORIA, {"notas": self.notas})
        return f"Borré {antes - len(self.notas)} nota(s)."

    def _llamar(self):
        herramientas = HERRAMIENTAS + HERRAMIENTAS_MEMORIA + ([BUSQUEDA_WEB] if self.usar_busqueda else [])
        try:
            return self.cliente.messages.create(
                model=MODELO, max_tokens=900, system=self._sistema(),
                tools=herramientas, messages=self.historial)
        except anthropic.BadRequestError as e:
            if self.usar_busqueda and "web_search" in str(e):
                print("(La busqueda web no esta habilitada en tu cuenta; sigo sin ella.)")
                self.usar_busqueda = False
                return self._llamar()
            raise

    def _recortar(self):
        if len(self.historial) <= MAX_HISTORIAL:
            return
        # Cortar siempre en un mensaje del usuario que sea texto (no en medio de una herramienta)
        for i in range(len(self.historial) - MAX_HISTORIAL, len(self.historial)):
            m = self.historial[i]
            if m["role"] == "user" and isinstance(m["content"], str):
                self.historial = self.historial[i:]
                return

    def pensar(self, texto):
        self.historial.append({"role": "user", "content": texto})
        respuesta = None
        for _ in range(10):
            respuesta = self._llamar()
            self.historial.append({"role": "assistant", "content": respuesta.content})
            if respuesta.stop_reason == "tool_use":
                resultados = []
                for bloque in respuesta.content:
                    if bloque.type == "tool_use":
                        print(f"  [accion] {bloque.name} {bloque.input}")
                        if bloque.name in ("recordar", "olvidar"):
                            salida = self._herramienta_memoria(bloque.name, bloque.input)
                        else:
                            salida = ejecutar_herramienta(bloque.name, bloque.input, self.voz)
                        resultados.append({"type": "tool_result", "tool_use_id": bloque.id, "content": salida})
                self.historial.append({"role": "user", "content": resultados})
                continue
            if respuesta.stop_reason == "pause_turn":
                continue
            break
        self._recortar()
        partes = [b.text for b in respuesta.content if b.type == "text"]
        final = " ".join(partes).strip() or "Listo, señor."
        self.dialogo.append({"usuario": texto, "jarvis": final,
                             "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
        self.dialogo = self.dialogo[-50:]
        _guardar_json(RUTA_DIALOGO, self.dialogo)
        return final


# ------------------------------------------------------------------ PRINCIPAL
def es_salida(texto):
    t = texto.lower().strip(" .!?¡¿")
    return any(p == t or t.endswith(p) for p in PALABRAS_SALIDA)


def es_fin_sesion(texto):
    t = texto.lower().strip(" .!?¡¿,")
    return any(t == p or t.startswith(p) or t.endswith(p) for p in PALABRAS_FIN_SESION) and len(t.split()) <= 5


def ciclo_asistente(estado, voz, cerebro, modo_texto):
    oido = None
    verificador = None
    if not modo_texto:
        estado.avisar("CALIBRANDO MICROFONO", 4)
        try:
            oido = Oido()
        except Exception as e:
            print(f"No pude usar el microfono ({e}). Paso a modo texto.")
            modo_texto = True
    if not modo_texto:
        from verificador import Verificador
        estado.avisar("CARGANDO HUELLA DE VOZ", 4)
        verificador = Verificador()
        if verificador.activo:
            print(f"Reconocimiento de voz activo (umbral {verificador.umbral:.2f}). Solo respondo a mi dueño.")
        else:
            print(f"AVISO: {verificador.motivo} Respondo a cualquier voz.")
            estado.avisar("VOZ NO REGISTRADA - RESPONDO A CUALQUIERA", 8)

    def autorizado(audio):
        if verificador is None:
            return True
        ok, sim = verificador.es_dueno(audio)
        if sim is not None:
            print(f"  (similitud de voz {sim:.2f} -> {'OK' if ok else 'RECHAZADA'})")
        if not ok:
            estado.rechazar()
        return ok

    estado.modo = "espera"
    hora = datetime.datetime.now().hour
    saludo = "Buenos días" if hora < 12 else "Buenas tardes" if hora < 20 else "Buenas noches"
    voz.decir(f"{saludo}, señor. Todos los sistemas en línea.")
    if not modo_texto:
        print('Deci "Jarvis" para empezar a charlar. Despues seguis hablando sin repetirlo.')
        print('"Eso es todo" -> vuelvo a espera.  "Jarvis, apagate" -> me cierro.\n')

    sesion_hasta = 0.0
    while estado.activo:
        try:
            if modo_texto:
                estado.modo = "escuchando"
                comando = input("Vos: ").strip()
                if not comando:
                    continue
            else:
                en_sesion = time.time() < sesion_hasta
                if not en_sesion and estado.modo == "escuchando":
                    print("(conversacion terminada - deci 'Jarvis' para volver a empezar)")
                estado.modo = "escuchando" if en_sesion else "espera"
                texto, audio = oido.escuchar(espera=5 if en_sesion else None)
                if not texto:
                    continue
                activado, resto = separar_activacion(texto)
                if not activado and not en_sesion:
                    continue
                if not autorizado(audio):
                    continue
                comando = resto if activado else texto
                if es_fin_sesion(texto) or es_salida(texto):
                    comando = texto
                if not comando:
                    voz.decir("¿En qué puedo ayudarlo?")
                    sesion_hasta = time.time() + int(AJUSTES['segundos_conversacion'])
                    continue
                print(f"Vos: {comando}")

            if es_fin_sesion(comando):
                estado.usuario = comando
                voz.decir("Quedo a su disposición. Cuando me necesite, llámeme.")
                sesion_hasta = 0.0
                continue

            estado.usuario = comando
            if es_salida(comando):
                voz.decir("Desconectando. Que tenga un buen día, señor.")
                break

            estado.modo = "pensando"
            try:
                respuesta = cerebro.pensar(comando)
            except anthropic.AuthenticationError:
                respuesta = "Mi clave de acceso no es válida, señor. Revise el archivo clave API."
            except anthropic.APIConnectionError:
                respuesta = "No tengo conexión a internet en este momento, señor."
            except anthropic.APIError as e:
                print(f"(Error de API: {e})")
                respuesta = "Tuve un problema para procesar eso, señor. Intente de nuevo."
            voz.decir(respuesta)
            if _reiniciar.is_set():
                voz.decir("Reiniciando sistemas con la nueva versión.")
                break
            sesion_hasta = time.time() + int(AJUSTES['segundos_conversacion'])

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"(Error inesperado: {e})")
            time.sleep(1)
    estado.activo = False


def main():
    modo_texto = "--texto" in sys.argv
    con_interfaz = "--sin-interfaz" not in sys.argv
    if "--siempre" in sys.argv:
        mantener_despierta()
    print("=" * 50)
    print("   J.A.R.V.I.S.  -  iniciando sistemas")
    print("=" * 50)

    from interfaz import Estado
    estado = Estado()
    voz = Voz(estado)
    cerebro = Cerebro(voz)

    if con_interfaz:
        try:
            import interfaz
            hilo = threading.Thread(target=ciclo_asistente, args=(estado, voz, cerebro, modo_texto), daemon=True)
            hilo.start()
            interfaz.ejecutar(estado)
            print("Reiniciando JARVIS..." if _reiniciar.is_set() else "Cerrando JARVIS.")
            os._exit(3 if _reiniciar.is_set() else 0)
        except Exception as e:
            print(f"(No pude abrir la interfaz visual: {e}.)")
            print("Proba con: python jarvis.py --sin-interfaz")
            sys.exit(1)
    ciclo_asistente(estado, voz, cerebro, modo_texto)
    if _reiniciar.is_set():
        sys.exit(3)


if __name__ == "__main__":
    main()

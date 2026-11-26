"""
Actualizador automatico de JARVIS.
Baja la ultima version desde GitHub (Beslerdev/jarvis) y reemplaza solo los archivos que cambiaron.
Tus datos (clave, voz registrada, memoria, ajustes) nunca se tocan: no estan en el repositorio.
"""
import os
import sys
import json
import subprocess
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = "Beslerdev/jarvis"
RAMA = "main"
CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_VERSION = os.path.join(CARPETA, ".version")
NO_TOCAR = {"iniciar_jarvis.bat"}  # se esta ejecutando mientras actualizamos


def _bajar(url, accept=None):
    cabeceras = {"User-Agent": "jarvis-actualizador"}
    if accept:
        cabeceras["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=20) as r:
        return r.read()


def _leer(ruta):
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except OSError:
        return None


def actualizar():
    """Devuelve True si se instalo una version nueva."""
    try:
        sha = _bajar(f"https://api.github.com/repos/{REPO}/commits/{RAMA}",
                     "application/vnd.github.sha").decode().strip()
    except Exception as e:
        print(f"(No pude buscar actualizaciones: {e}. Sigo con la version actual.)")
        return False
    actual = (_leer(RUTA_VERSION) or b"").decode().strip()
    if sha == actual:
        print("JARVIS esta actualizado.")
        return False

    print("Hay una version nueva de JARVIS. Actualizando...")
    try:
        arbol = json.loads(_bajar(f"https://api.github.com/repos/{REPO}/git/trees/{sha}?recursive=1"))
        req_antes = _leer(os.path.join(CARPETA, "requirements.txt"))
        cambiados = []
        for item in arbol.get("tree", []):
            ruta = item["path"]
            if item["type"] != "blob" or ruta in NO_TOCAR or ruta.startswith("."):
                continue
            destino = os.path.join(CARPETA, *ruta.split("/"))
            datos = _bajar(f"https://raw.githubusercontent.com/{REPO}/{sha}/{ruta}")
            if _leer(destino) == datos:
                continue
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            temporal = destino + ".nuevo"
            with open(temporal, "wb") as f:
                f.write(datos)
            os.replace(temporal, destino)
            cambiados.append(ruta)
            print(f"  actualizado: {ruta}")

        if "requirements.txt" in cambiados and req_antes is not None:
            print("Instalando librerias nuevas...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r",
                            os.path.join(CARPETA, "requirements.txt")])
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "resemblyzer>=0.1.4"])

        with open(RUTA_VERSION, "w") as f:
            f.write(sha)
        print(f"Listo: {len(cambiados)} archivo(s) actualizados.")
        return bool(cambiados)
    except Exception as e:
        print(f"(Fallo la actualizacion: {e}. Sigo con la version actual.)")
        return False


if __name__ == "__main__":
    actualizar()

"""
Registra tu voz para que JARVIS solo te responda a vos.
Vas a leer en voz alta unas frases; se guarda una "huella de voz" en mi_voz.npy.
"""
import sys
import json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import numpy as np
    import speech_recognition as sr
except ModuleNotFoundError as e:
    print(f"Falta una libreria: {e.name}. Ejecuta instalar.bat (la version nueva).")
    input("Enter para salir...")
    raise SystemExit

from verificador import RUTA_HUELLA, RUTA_CONFIG, audio_a_wav

FRASES = [
    "Jarvis, abrí Excel y buscá el reporte de la semana.",
    "Jarvis, ¿cómo va a estar el clima mañana a la mañana?",
    "Jarvis, subí el volumen y poné un poco de música.",
    "Hoy tengo que revisar los pedidos y llamar al depósito.",
    "Jarvis, recordame en veinte minutos que tengo una reunión.",
    "El campo está lindo, ojalá llueva la semana que viene.",
    "Jarvis, abrí el navegador y buscá las noticias de hoy.",
    "Uno, dos, tres, cuatro, cinco, seis, siete, ocho, nueve, diez.",
]


def main():
    print("=" * 60)
    print("  Cargando el reconocimiento de voz (la primera vez tarda unos segundos)...")
    from resemblyzer import VoiceEncoder, preprocess_wav
    print("  REGISTRO DE VOZ PARA JARVIS")
    print("=" * 60)
    print("Vas a leer 8 frases en voz alta, con tu voz normal,")
    print("a la distancia del microfono a la que le vas a hablar a Jarvis.")
    print("Mejor en un lugar sin otras personas hablando.\n")
    input("Apreta Enter cuando estes listo...")

    encoder = VoiceEncoder(device="cpu", verbose=False)
    r = sr.Recognizer()
    r.pause_threshold = 1.0
    mic = sr.Microphone()
    with mic as fuente:
        print("\nCalibrando (silencio un segundo)...")
        r.adjust_for_ambient_noise(fuente, duration=1.5)

    embeddings = []
    for i, frase in enumerate(FRASES, 1):
        while True:
            print(f"\n[{i}/{len(FRASES)}] Lee en voz alta:\n    \"{frase}\"")
            with mic as fuente:
                try:
                    audio = r.listen(fuente, timeout=10, phrase_time_limit=12)
                except sr.WaitTimeoutError:
                    print("  No escuche nada, probemos de nuevo.")
                    continue
            wav = preprocess_wav(audio_a_wav(audio), source_sr=16000)
            if len(wav) < 16000 * 1.0:
                print("  Muy corto, repetila un poco mas lento.")
                continue
            embeddings.append(encoder.embed_utterance(wav))
            print("  OK")
            break

    emb = np.array(embeddings)
    huella = emb.mean(axis=0)
    huella /= np.linalg.norm(huella)
    sims = emb @ huella
    umbral = float(np.clip(sims.min() - 0.08, 0.62, 0.82))
    np.save(RUTA_HUELLA, huella)
    with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
        json.dump({"umbral": round(umbral, 3)}, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Listo! Voz registrada. Similitud de tus frases: {sims.min():.2f} a {sims.max():.2f}")
    print(f"Umbral de aceptacion: {umbral:.2f}  (se puede ajustar en mi_voz.json)")
    print("  - Si Jarvis a veces no te reconoce: baja el umbral (ej. 0.68)")
    print("  - Si le responde a otra persona: subilo (ej. 0.80)")
    print("=" * 60)
    input("\nEnter para salir...")


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as e:
        print(f"\nFalta una libreria: {e.name}")
        print("Volve a ejecutar instalar.bat (la version nueva) y espera a que diga Listo!")
    except OSError as e:
        print(f"\nProblema con el microfono: {e}")
        print("Revisa que el microfono este conectado y permitido en Configuracion > Privacidad > Microfono.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nError: {e}  (saca una foto y pasamela)")

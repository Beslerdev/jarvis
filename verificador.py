"""
Verificacion de hablante: compara cada frase con la "huella de voz" registrada
con registrar_voz.py. Si no hay huella registrada, deja pasar a cualquiera.
"""
import os
import json

import numpy as np

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_HUELLA = os.path.join(CARPETA, "mi_voz.npy")
RUTA_CONFIG = os.path.join(CARPETA, "mi_voz.json")


def audio_a_wav(audio_data):
    """speech_recognition.AudioData -> numpy float32 a 16 kHz."""
    crudo = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
    return np.frombuffer(crudo, dtype=np.int16).astype(np.float32) / 32768.0


class Verificador:
    def __init__(self):
        self.activo = False
        self.motivo = ""
        if not os.path.exists(RUTA_HUELLA):
            self.motivo = "No hay voz registrada (ejecuta registrar_mi_voz.bat)."
            return
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
        except Exception as e:
            self.motivo = f"No se pudo cargar el reconocimiento de voz: {e}"
            return
        self.encoder = VoiceEncoder(device="cpu", verbose=False)
        self.preprocesar = preprocess_wav
        self.huella = np.load(RUTA_HUELLA)
        self.umbral = 0.75
        if os.path.exists(RUTA_CONFIG):
            with open(RUTA_CONFIG, encoding="utf-8") as f:
                self.umbral = float(json.load(f).get("umbral", self.umbral))
        self.activo = True

    def embedding(self, wav):
        try:
            limpio = self.preprocesar(wav, source_sr=16000)
        except Exception:
            limpio = wav
        if len(limpio) < 16000 * 0.3:
            limpio = wav
        return self.encoder.embed_utterance(limpio)

    def similitud(self, audio_data):
        return float(self.embedding(audio_a_wav(audio_data)) @ self.huella)

    def es_dueno(self, audio_data):
        """Devuelve (autorizado, similitud)."""
        if not self.activo or audio_data is None:
            return True, None
        s = self.similitud(audio_data)
        return s >= self.umbral, s

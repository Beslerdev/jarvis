"""Escucha las voces disponibles para elegir la de Jarvis."""
import asyncio, os, tempfile, time
import edge_tts, pygame
FRASE = "Buenas tardes, señor. Todos los sistemas en línea. ¿En qué puedo ayudarle?"
VOCES = [("es-ES-AlvaroNeural", "-6Hz"), ("es-ES-AlvaroNeural", "-12Hz"), ("es-AR-TomasNeural", "-6Hz"),
         ("es-MX-JorgeNeural", "-6Hz"), ("es-CO-GonzaloNeural", "-6Hz"), ("es-US-AlonsoNeural", "-6Hz")]
pygame.mixer.init()
for voz, tono in VOCES:
    print(f"Voz: {voz}  tono: {tono}")
    ruta = os.path.join(tempfile.gettempdir(), "prueba_voz.mp3")
    asyncio.run(edge_tts.Communicate(FRASE, voz, pitch=tono).save(ruta))
    s = pygame.mixer.Sound(ruta); c = s.play()
    while c.get_busy(): time.sleep(0.05)
    time.sleep(0.6)
print("\nPara cambiarla, edita VOZ y TONO al principio de jarvis.py")
input("Enter para salir...")

import subprocess
import threading

from django.conf import settings

def parler(texte: str):
    def _run():
        try:
            piper = subprocess.Popen(
                ["piper", "--model", settings.PIPER_MODEL, "--output_raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            aplay = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                stdin=piper.stdout,
                stderr=subprocess.DEVNULL,
            )
            piper.stdin.write(texte.encode("utf-8"))
            piper.stdin.close()
            piper.stdout.close()
            aplay.wait()
        except Exception as e:
            print(f"[TTS] Erreur : {e}")

    threading.Thread(target=_run, daemon=True).start()
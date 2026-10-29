import subprocess

SONS = {
    'normal':   '/usr/share/sounds/freedesktop/stereo/message-new-instant.oga',
    'low':      '/usr/share/sounds/freedesktop/stereo/message.oga',
    'critical': '/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga',
}

def notifier_bureau(titre: str, message: str, urgence: str = 'normal'):
    try:
        # Notification visuelle GNOME
        subprocess.run([
            'notify-send',
            titre,
            message,
            f'--urgency={urgence}',
            '--icon=appointment-reminder',
            '--expire-time=8000',
            '--app-name=Rappel Vocal',
        ], check=False)

        # Son de notification
        son = SONS.get(urgence, SONS['normal'])
        subprocess.Popen(
            ['paplay', son],
            stderr=subprocess.DEVNULL
        )

    except Exception as e:
        print(f'[NOTIF] Erreur : {e}')
import logging
import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_scheduler = None


def verifier_rappels():
    """Vérifie toutes les minutes les rappels à déclencher"""
    from .models import Rappel

    rappels = Rappel.objects.filter(
        actif=True,
        declenche=False,
        heure_rappel__lte=timezone.now(),
    )
    for rappel in rappels:
        logger.info(f"Déclenchement : {rappel.titre}")
        if not rappel.declencher():
            logger.error(f"Erreur rappel {rappel.titre}")


def _doit_demarrer():
    if not settings.SCHEDULER_ACTIF:
        return False
    commande = sys.argv[1] if len(sys.argv) > 1 else ''
    if commande == 'runserver':
        # L'autoreloader lance deux processus : on ne démarre que dans l'enfant
        return os.environ.get('RUN_MAIN') == 'true' or '--noreload' in sys.argv
    # Pas de scheduler pendant migrate, shell, test, etc. ; oui sous gunicorn/uwsgi
    return 'manage.py' not in sys.argv[0]


def demarrer():
    global _scheduler
    if _scheduler is not None or not _doit_demarrer():
        return

    _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    _scheduler.add_job(
        verifier_rappels,
        trigger=IntervalTrigger(minutes=1),
        id='verifier_rappels',
        name='Vérification des rappels',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler démarré — vérification toutes les minutes")

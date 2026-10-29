from datetime import timedelta

from django.db import models
from django.utils import timezone


class Rappel(models.Model):
    FREQUENCE_CHOICES = [
        ('once',   'Une fois'),
        ('daily',  'Quotidien'),
        ('weekly', 'Hebdomadaire'),
    ]
    INTERVALLES = {
        'daily':  timedelta(days=1),
        'weekly': timedelta(weeks=1),
    }

    titre        = models.CharField(max_length=200)
    message      = models.TextField(blank=True)
    heure_rappel = models.DateTimeField()
    frequence    = models.CharField(max_length=20, choices=FREQUENCE_CHOICES, default='once')
    vocal        = models.BooleanField(default=True)
    notif_bureau = models.BooleanField(default=True)
    actif        = models.BooleanField(default=True)
    declenche    = models.BooleanField(default=False)
    cree_le      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['heure_rappel']
        verbose_name = 'Rappel'
        verbose_name_plural = 'Rappels'

    def __str__(self):
        return f"{self.titre} — {timezone.localtime(self.heure_rappel):%d/%m/%Y %H:%M}"

    @property
    def est_bientot(self):
        """Actif et prévu dans moins d'une heure."""
        maintenant = timezone.now()
        return self.actif and maintenant <= self.heure_rappel <= maintenant + timedelta(hours=1)

    def texte_vocal(self):
        return f"{self.titre}. {self.message}" if self.message else self.titre

    def jouer(self):
        """Émet la notification et/ou la voix, sans toucher à l'état du rappel."""
        from .services.notifier import notifier_bureau
        from .services.tts import parler

        if self.notif_bureau:
            notifier_bureau(self.titre, self.message)
        if self.vocal:
            parler(self.texte_vocal())

    def planifier_suivant(self):
        """Désactive un rappel unique, ou avance un rappel récurrent à sa prochaine
        occurrence future (sans rattraper une à une les occurrences manquées)."""
        intervalle = self.INTERVALLES.get(self.frequence)
        if intervalle is None:
            self.actif = False
            self.declenche = True
        else:
            maintenant = timezone.now()
            while self.heure_rappel <= maintenant:
                self.heure_rappel += intervalle
            self.declenche = False
        self.save(update_fields=['actif', 'declenche', 'heure_rappel'])

    def declencher(self):
        """Joue le rappel, planifie la suite et journalise le résultat."""
        try:
            self.jouer()
            HistoriqueNotification.objects.create(rappel=self, succes=True)
            return True
        except Exception as e:
            HistoriqueNotification.objects.create(rappel=self, succes=False, erreur=str(e))
            return False
        finally:
            # Même en cas d'erreur, on avance : sinon le rappel échoue en boucle chaque minute
            self.planifier_suivant()


class HistoriqueNotification(models.Model):
    rappel       = models.ForeignKey(Rappel, on_delete=models.CASCADE, related_name='historique')
    declenche_le = models.DateTimeField(auto_now_add=True)
    succes       = models.BooleanField(default=True)
    erreur       = models.TextField(blank=True)

    class Meta:
        ordering = ['-declenche_le']

    def __str__(self):
        return f"{self.rappel.titre} — {'OK' if self.succes else 'ERREUR'}"

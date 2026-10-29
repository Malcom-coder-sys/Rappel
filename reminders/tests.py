from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import HistoriqueNotification, Rappel
from .scheduler import verifier_rappels


@patch('reminders.services.tts.parler')
@patch('reminders.services.notifier.notifier_bureau')
class DeclenchementTests(TestCase):

    def creer(self, **kwargs):
        defaults = dict(titre='Test', message='msg', heure_rappel=timezone.now() - timedelta(minutes=1))
        defaults.update(kwargs)
        return Rappel.objects.create(**defaults)

    def test_rappel_unique_desactive(self, notif, parler):
        r = self.creer()
        verifier_rappels()
        r.refresh_from_db()
        self.assertFalse(r.actif)
        notif.assert_called_once()
        parler.assert_called_once_with('Test. msg')
        self.assertEqual(HistoriqueNotification.objects.filter(succes=True).count(), 1)

    def test_quotidien_saute_les_occurrences_manquees(self, notif, parler):
        r = self.creer(frequence='daily', heure_rappel=timezone.now() - timedelta(days=3, minutes=5))
        verifier_rappels()
        r.refresh_from_db()
        self.assertTrue(r.actif)
        self.assertFalse(r.declenche)
        self.assertGreater(r.heure_rappel, timezone.now())
        self.assertLess(r.heure_rappel, timezone.now() + timedelta(days=1))
        self.assertEqual(notif.call_count, 1)

    def test_erreur_journalisee_sans_boucle(self, notif, parler):
        notif.side_effect = RuntimeError('boom')
        r = self.creer()
        verifier_rappels()
        verifier_rappels()
        r.refresh_from_db()
        self.assertFalse(r.actif)
        self.assertEqual(HistoriqueNotification.objects.filter(succes=False).count(), 1)

    def test_api_notifier_garde_la_recurrence(self, notif, parler):
        r = self.creer(frequence='weekly')
        resp = self.client.post(reverse('api_notifier'), {'id': r.id}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertTrue(r.actif)
        self.assertFalse(r.declenche)


class VuesTests(TestCase):

    def test_pages(self):
        r = Rappel.objects.create(titre='A', heure_rappel=timezone.now())
        for url in ['dashboard', 'rappels_list', 'rappel_create', 'historique', 'settings']:
            self.assertEqual(self.client.get(reverse(url)).status_code, 200, url)
        self.assertEqual(self.client.get(reverse('rappel_edit', args=[r.pk])).status_code, 200)

    def test_suppression_refuse_get(self):
        r = Rappel.objects.create(titre='A', heure_rappel=timezone.now())
        self.assertEqual(self.client.get(reverse('rappel_delete', args=[r.pk])).status_code, 405)
        self.client.post(reverse('rappel_delete', args=[r.pk]))
        self.assertFalse(Rappel.objects.exists())

    def test_creation_heure_locale(self):
        self.client.post(reverse('rappel_create'), {
            'titre': 'Réveil', 'heure_rappel': '2030-01-01T08:00', 'vocal': 'on',
        })
        r = Rappel.objects.get()
        self.assertEqual(timezone.localtime(r.heure_rappel).hour, 8)
        self.assertTrue(r.vocal)
        self.assertFalse(r.notif_bureau)

    def test_creation_date_invalide(self):
        resp = self.client.post(reverse('rappel_create'), {'titre': 'X', 'heure_rappel': 'nope'}, follow=True)
        self.assertContains(resp, 'Date et heure invalides')
        self.assertFalse(Rappel.objects.exists())

    @patch('reminders.views.settings')
    def test_api_token(self, settings):
        settings.API_TOKEN = 'secret'
        self.assertEqual(self.client.get(reverse('api_rappels')).status_code, 401)
        resp = self.client.get(reverse('api_rappels'), HTTP_AUTHORIZATION='Bearer secret')
        self.assertEqual(resp.status_code, 200)

import json

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import HistoriqueNotification, Rappel
from .services.tts import parler


def _parse_heure(valeur):
    """Convertit '2026-10-29T14:30' (heure locale) en datetime aware."""
    dt = parse_datetime(valeur or '')
    if dt is None:
        raise ValueError("Date et heure invalides")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _remplir(rappel, data):
    """Applique les champs du formulaire à un rappel (sans le sauvegarder)."""
    titre = data.get('titre', '').strip()
    if not titre:
        raise ValueError("Le titre est obligatoire")
    rappel.titre        = titre
    rappel.message      = data.get('message', '').strip()
    rappel.heure_rappel = _parse_heure(data.get('heure_rappel'))
    rappel.frequence    = data.get('frequence', 'once')
    rappel.vocal        = 'vocal' in data
    rappel.notif_bureau = 'notif_bureau' in data
    rappel.declenche    = False


def _paginer(request, queryset, par_page=20):
    return Paginator(queryset, par_page).get_page(request.GET.get('page'))


# ── Dashboard ──
def dashboard(request):
    rappels_a_venir = Rappel.objects.filter(actif=True)[:5]
    historique      = HistoriqueNotification.objects.select_related('rappel')[:6]

    stats = {
        'actifs':           Rappel.objects.filter(actif=True).count(),
        'aujourd_hui':      Rappel.objects.filter(actif=True, heure_rappel__date=timezone.localdate()).count(),
        'total_declenches': HistoriqueNotification.objects.filter(succes=True).count(),
        'erreurs':          HistoriqueNotification.objects.filter(succes=False).count(),
    }

    return render(request, 'reminders/dashboard.html', {
        'stats':           stats,
        'rappels_a_venir': rappels_a_venir,
        'historique':      historique,
    })


# ── Liste des rappels ──
def rappels_list(request):
    rappels = Rappel.objects.all()

    q = request.GET.get('q')
    if q:
        rappels = rappels.filter(titre__icontains=q)

    frequence = request.GET.get('frequence')
    if frequence:
        rappels = rappels.filter(frequence=frequence)

    statut = request.GET.get('statut')
    if statut == 'actif':
        rappels = rappels.filter(actif=True)
    elif statut == 'done':
        rappels = rappels.filter(actif=False)

    filtres = request.GET.copy()
    filtres.pop('page', None)

    return render(request, 'reminders/rappels_list.html', {
        'rappels': _paginer(request, rappels),
        'filtres': filtres.urlencode(),
    })


# ── Créer un rappel ──
def rappel_create(request):
    if request.method == 'POST':
        rappel = Rappel()
        try:
            _remplir(rappel, request.POST)
            rappel.save()
            messages.success(request, 'Rappel créé.')
            return redirect('rappels_list')
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, 'reminders/rappel_form.html')


# ── Créer un rappel rapide (depuis dashboard) ──
@require_POST
def rappel_create_quick(request):
    rappel = Rappel()
    try:
        _remplir(rappel, request.POST)
        rappel.save()
        messages.success(request, 'Rappel créé.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('dashboard')


# ── Modifier un rappel ──
def rappel_edit(request, pk):
    rappel = get_object_or_404(Rappel, pk=pk)

    if request.method == 'POST':
        try:
            _remplir(rappel, request.POST)
            rappel.actif = 'actif' in request.POST
            rappel.save()
            messages.success(request, 'Rappel modifié.')
            return redirect('rappels_list')
        except ValueError as e:
            messages.error(request, str(e))
            rappel.refresh_from_db()

    return render(request, 'reminders/rappel_form.html', {'rappel': rappel})


# ── Supprimer un rappel ──
@require_POST
def rappel_delete(request, pk):
    rappel = get_object_or_404(Rappel, pk=pk)
    rappel.delete()
    messages.success(request, 'Rappel supprimé.')
    return redirect('rappels_list')


# ── Tester un rappel immédiatement (sans modifier sa planification) ──
@require_POST
def rappel_test(request, pk):
    rappel = get_object_or_404(Rappel, pk=pk)
    try:
        rappel.jouer()
        HistoriqueNotification.objects.create(rappel=rappel, succes=True)
        messages.success(request, f'Test déclenché : {rappel.titre}')
    except Exception as e:
        HistoriqueNotification.objects.create(rappel=rappel, succes=False, erreur=str(e))
        messages.error(request, f'Erreur test : {e}')
    return redirect(request.POST.get('next') or 'rappels_list')


# ── Historique ──
def historique(request):
    hist = HistoriqueNotification.objects.select_related('rappel')
    stats = {
        'total':   hist.count(),
        'succes':  hist.filter(succes=True).count(),
        'erreurs': hist.filter(succes=False).count(),
    }
    return render(request, 'reminders/historique.html', {
        'historique': _paginer(request, hist, 30),
        'stats':      stats,
    })


# ── Paramètres ──
def settings_view(request):
    return render(request, 'reminders/settings.html', {
        'piper_model': settings.PIPER_MODEL,
        'n8n_url':     settings.N8N_URL,
        'api_url':     request.build_absolute_uri('/api/rappels/'),
        'api_token':   bool(settings.API_TOKEN),
        'scheduler':   settings.SCHEDULER_ACTIF,
    })


@require_POST
def tester_voix(request):
    parler("Bonjour, ceci est un test de la voix Piper.")
    messages.success(request, 'Test vocal lancé.')
    return redirect('settings')


# ══ API POUR N8N ══

def _token_valide(request):
    if not settings.API_TOKEN:
        return True
    return request.headers.get('Authorization') == f'Bearer {settings.API_TOKEN}'


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_rappels(request):
    if not _token_valide(request):
        return JsonResponse({'erreur': 'non autorisé'}, status=401)

    if request.method == 'GET':
        rappels = Rappel.objects.filter(
            actif=True,
            declenche=False,
            heure_rappel__lte=timezone.now(),
        ).values()
        return JsonResponse(list(rappels), safe=False)

    try:
        data = json.loads(request.body)
        rappel = Rappel.objects.create(
            titre=data['titre'],
            message=data.get('message', ''),
            heure_rappel=_parse_heure(data['heure_rappel']),
            frequence=data.get('frequence', 'once'),
            vocal=data.get('vocal', True),
            notif_bureau=data.get('notif_bureau', True),
        )
        return JsonResponse({'id': rappel.id, 'status': 'créé'}, status=201)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'erreur': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_notifier(request):
    if not _token_valide(request):
        return JsonResponse({'erreur': 'non autorisé'}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'erreur': str(e)}, status=400)

    rappel_id = data.get('id')
    if rappel_id:
        # Rappel existant : même logique que le scheduler (récurrence + historique)
        rappel = Rappel.objects.filter(id=rappel_id).first()
        if rappel is None:
            return JsonResponse({'erreur': 'rappel introuvable'}, status=404)
        ok = rappel.declencher()
        return JsonResponse({'status': 'ok' if ok else 'erreur'}, status=200 if ok else 500)

    # Notification ponctuelle, sans rappel enregistré
    try:
        Rappel(
            titre=data.get('titre', 'Rappel'),
            message=data.get('message', ''),
            vocal=data.get('vocal', True),
            notif_bureau=data.get('notif_bureau', True),
        ).jouer()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'erreur': str(e)}, status=500)

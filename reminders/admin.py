from django.contrib import admin

from .models import HistoriqueNotification, Rappel


@admin.register(Rappel)
class RappelAdmin(admin.ModelAdmin):
    list_display  = ('titre', 'heure_rappel', 'frequence', 'vocal', 'notif_bureau', 'actif')
    list_filter   = ('frequence', 'actif', 'vocal', 'notif_bureau')
    search_fields = ('titre', 'message')


@admin.register(HistoriqueNotification)
class HistoriqueNotificationAdmin(admin.ModelAdmin):
    list_display = ('rappel', 'declenche_le', 'succes')
    list_filter  = ('succes',)

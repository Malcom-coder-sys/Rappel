from django.urls import path
from . import views

urlpatterns = [
    # Pages
    path('',                      views.dashboard,          name='dashboard'),
    path('rappels/',              views.rappels_list,        name='rappels_list'),
    path('rappels/nouveau/',      views.rappel_create,       name='rappel_create'),
    path('rappels/rapide/',       views.rappel_create_quick, name='rappel_create_quick'),
    path('rappels/<int:pk>/edit/',   views.rappel_edit,      name='rappel_edit'),
    path('rappels/<int:pk>/delete/', views.rappel_delete,    name='rappel_delete'),
    path('rappels/<int:pk>/test/',   views.rappel_test,      name='rappel_test'),
    path('historique/',           views.historique,          name='historique'),
    path('settings/',             views.settings_view,       name='settings'),
    path('settings/test-voix/',   views.tester_voix,         name='tester_voix'),

    # API pour n8n
    path('api/rappels/',  views.api_rappels,  name='api_rappels'),
    path('api/notifier/', views.api_notifier, name='api_notifier'),
]
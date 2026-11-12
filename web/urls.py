from django.urls import path

from . import views

urlpatterns = [
    path("", views.games, name="home"),
    path("games/new/", views.game_new, name="game_new"),
    path("games/<int:game_id>/", views.game_detail, name="game"),
    path("games/<int:game_id>/action/", views.game_action, name="game_action"),
]

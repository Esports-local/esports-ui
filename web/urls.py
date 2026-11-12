from django.urls import path

from . import views

urlpatterns = [
    path("", views.games, name="home"),
    path("games/new/", views.game_new, name="game_new"),
    path("games/<int:game_id>/", views.game_detail, name="game"),
    path("games/<int:game_id>/action/", views.game_action, name="game_action"),
    path("drama/", views.home, name="drama"),
    path("series/<int:series_id>/", views.series_detail, name="series"),
    path("series/<int:series_id>/predict/", views.predict, name="predict"),
    path("episodes/<int:episode_id>/", views.episode_review, name="episode"),
    path("episodes/<int:episode_id>/lines/<int:scene_id>/<int:index>/", views.review_line, name="review_line"),
]

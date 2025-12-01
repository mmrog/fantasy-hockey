from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.league_dashboard, name='league_dashboard'),
    path('roster/', views.team_roster, name='team_roster'),
    path('lineup/', views.daily_lineup, name='daily_lineup'),
    path('accounts/', include('django.contrib.auth.urls')),

]

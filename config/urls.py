"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LogoutView
from league import views as league_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Home page
    path('', league_views.home, name='home'),

    # League routes
    path('league/', include('league.urls')),

    # Django built-in authentication routes
    path('accounts/', include('django.contrib.auth.urls')),

    # Custom logout route that ALLOWS GET and redirects home
    path(
        'logout/',
        LogoutView.as_view(next_page='tsn.ca'),
        name='logout'
    ),
]

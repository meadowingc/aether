"""
URL configuration for aether project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from accounts.views import logout_view
from two_factor.urls import urlpatterns as tf_urls
from django.conf import settings

urlpatterns = [
    # Two-factor authentication routes (login, setup, profile, backup tokens)
    path("", include(tf_urls)),
    path("logout/", logout_view, name="logout"),
    path("accounts/", include("accounts.urls")),
    path('', include('aether_notes.urls')),
]

if settings.ADMIN_ENABLED:
    urlpatterns += [path('admin/', admin.site.urls)]

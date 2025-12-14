from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/halte/", views.get_halte_list, name="get_halte_list"),
    path('analytics/', views.analytics_view, name='analytics')
]

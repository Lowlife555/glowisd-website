from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('factory/', views.factory, name='factory'),
    path('custom/', views.custom, name='custom'),
    path('contact/', views.contact, name='contact'),
    path('robots.txt', views.robots, name='robots'),
]

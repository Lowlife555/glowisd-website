from django.urls import path

from . import views

urlpatterns = [
    path('pay/<int:pk>/', views.payment_start, name='payment_start'),
    path('pay/success/<str:order_no>/', views.payment_success, name='payment_success'),
    path('pay/cancel/<str:order_no>/', views.payment_cancel, name='payment_cancel'),
    path('pay/webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]

from django.urls import path
from . import views


urlpatterns = [
    path('chat/<int:order_id>/', views.chat, name="chat"),
]

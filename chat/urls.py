from django.urls import path
from . import views

urlpatterns = [
    path(
        "", views.chat_view, name="chat_view"
    ),  # empty path means /chat/ hits chat_view
]

from django.urls import re_path

from taiga.urls import urlpatterns as taiga_urlpatterns

from .api import UsersViewSet

urlpatterns = [
    re_path(r"^api/v1/users/password_recovery/?$",
            UsersViewSet.as_view({"post": "password_recovery"}), name="vetor-password-recovery"),
    *taiga_urlpatterns,
]

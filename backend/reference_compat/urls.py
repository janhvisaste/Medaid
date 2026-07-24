from django.urls import path

from .views import assess_reference_compat

urlpatterns = [
    path("assess/", assess_reference_compat, name="reference_compat_assess"),
]

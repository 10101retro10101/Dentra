from django.contrib import admin
from django.urls import path
from django.urls import re_path as url
from .views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", index, name="index"),
    path("auth", Auth.as_view()),
    path("app_version", AppVersion.as_view()),
    path("union_models", UnionModels.as_view()),
    path("save_model", saveModel.as_view())
]

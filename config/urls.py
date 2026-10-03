from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("timetable.urls")),
]

handler403 = "core.views.forbidden"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"

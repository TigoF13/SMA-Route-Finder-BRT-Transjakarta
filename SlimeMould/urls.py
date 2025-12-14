from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔹 Ini penting agar /api/halte/ bisa dikenali
    path('', include('myapp.urls')),
]
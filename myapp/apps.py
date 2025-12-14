# myapp/apps.py

from django.apps import AppConfig

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    # Metode ready() sekarang bisa dikosongkan atau dihapus.
    # Tidak ada lagi evaluasi yang berjalan saat server startup.
    def ready(self):
        pass
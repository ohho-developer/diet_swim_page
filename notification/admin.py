from django.contrib import admin
from .models import FCMDevice


# Register your models here.
@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'registration_id', 'name', 'active')
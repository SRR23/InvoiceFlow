from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'company', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'email', 'company', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

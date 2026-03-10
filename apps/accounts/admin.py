from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""
    list_display = ('email', 'first_name', 'last_name', 'company_name', 'is_business_user', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_business_user', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'company_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'company_name', 'phone', 'currency')}),
        ('OAuth', {'fields': ('google_id',)}),
        ('Permissions', {'fields': ('is_business_user', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_business_user', 'is_staff', 'is_active'),
        }),
    )

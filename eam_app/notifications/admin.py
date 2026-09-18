from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'tenant', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at', 'tenant')
    search_fields = ('title', 'message', 'recipient__username')
    readonly_fields = ('id', 'created_at')

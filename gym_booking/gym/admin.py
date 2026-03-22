from django.contrib import admin
from .models import Trainer, Session, Booking


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'specialization', 'is_active', 'created_at']
    list_filter = ['is_active', 'specialization']
    search_fields = ['first_name', 'last_name', 'email']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'trainer', 'date', 'start_time', 'end_time', 'capacity', 'current_bookings', 'is_active']
    list_filter = ['is_active', 'date', 'trainer']
    search_fields = ['title', 'trainer__first_name', 'trainer__last_name']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'session', 'status', 'booked_at']
    list_filter = ['status']
    search_fields = ['user__username', 'session__title']

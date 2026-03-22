from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Trainer(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    specialization = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.specialization})"

    def clean(self):
        if not self.first_name or not self.first_name.strip():
            raise ValidationError({'first_name': 'First name cannot be blank.'})
        if not self.last_name or not self.last_name.strip():
            raise ValidationError({'last_name': 'Last name cannot be blank.'})
        if not self.specialization or not self.specialization.strip():
            raise ValidationError({'specialization': 'Specialization cannot be blank.'})

    class Meta:
        ordering = ['last_name', 'first_name']


class Session(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    trainer = models.ForeignKey(Trainer, on_delete=models.PROTECT, related_name='sessions')
    date = models.DateField() #Неполная валидация даты и времени
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    current_bookings = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} on {self.date} ({self.start_time}–{self.end_time})"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'end_time must be after start_time.'})

    class Meta:
        ordering = ['date', 'start_time']


class Booking(models.Model):
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_PENDING, 'Pending'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
    booked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking #{self.pk}: {self.user.username} → {self.session.title} [{self.status}]"

    class Meta:
        unique_together = ('user', 'session')
        ordering = ['-booked_at']

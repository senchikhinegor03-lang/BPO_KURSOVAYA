from rest_framework import serializers
from .models import Trainer, Session, Booking
from users.serializers import UserSummarySerializer


class TrainerSerializer(serializers.ModelSerializer):
    """Serializer for Trainer model with unique email validation."""

    class Meta:
        #отсуствует валидация телефона и почты
        model = Trainer
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'phone', 'specialization', 'bio', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_email(self, value):
        value = value.lower()
        qs = Trainer.objects.filter(email__iexact=value)
        # Exclude current instance on update
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A trainer with this email already exists.")
        return value


class SessionSerializer(serializers.ModelSerializer):
    """Serializer for Session model with nested trainer info and computed fields."""

    trainer_name = serializers.SerializerMethodField(read_only=True)
    available_spots = serializers.SerializerMethodField(read_only=True) #Нет проверки на отрицательные значения available_spots

    class Meta:
        model = Session
        fields = [
            'id', 'title', 'description', 'trainer', 'trainer_name',
            'date', 'start_time', 'end_time',
            'capacity', 'current_bookings', 'available_spots',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'current_bookings', 'created_at']

    def get_trainer_name(self, obj):
        return f"{obj.trainer.first_name} {obj.trainer.last_name}"

    def get_available_spots(self, obj):
        return obj.capacity - obj.current_bookings


class BookingSerializer(serializers.ModelSerializer):
    #Не учитывается статус бронирования при проверке лимитов
    """Serializer for Booking model with nested user and session objects."""
#Отсутствие валидации лимита вместимости при создании бронирования
    user = UserSummarySerializer(read_only=True)
    session = SessionSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'user', 'session', 'status', 'booked_at']
        read_only_fields = ['id', 'booked_at']

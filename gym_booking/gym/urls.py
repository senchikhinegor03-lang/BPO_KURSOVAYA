from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrainerViewSet, SessionViewSet, BookingViewSet, UserBookingsView

router = DefaultRouter()
router.register(r'trainers', TrainerViewSet, basename='trainer')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('users/<int:user_id>/bookings/', UserBookingsView.as_view(), name='user-bookings'),
]

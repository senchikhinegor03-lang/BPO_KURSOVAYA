from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Trainer, Session, Booking
from .serializers import TrainerSerializer, SessionSerializer, BookingSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow GET (list/detail) to anyone (AllowAny).
    Restrict POST, PUT, PATCH, DELETE to Admin users only.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class TrainerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Trainer resource.

    - GET list:   only is_active=True trainers, public access (Requirements 2.1, 2.2)
    - GET detail: full profile, public access (Requirement 2.3)
    - POST/PUT:   Admin only (Requirement 2.6)
    - DELETE:     soft-delete — sets is_active=False instead of removing (Requirement 2.4, 2.5)
    """
    serializer_class = TrainerSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        # List endpoint returns only active trainers; detail allows any (for admin access)
        if self.action == 'list':
            return Trainer.objects.filter(is_active=True)
        return Trainer.objects.all()

    def destroy(self, request, *args, **kwargs):
        """Soft-delete: mark trainer as inactive instead of deleting the record."""
        trainer = self.get_object()
        trainer.is_active = False
        trainer.save(update_fields=['is_active'])
        return Response(status=204)


class SessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Session resource.

    - GET list:   only is_active=True, optional ?date=YYYY-MM-DD filter, public (Requirements 3.1, 3.2)
    - GET detail: full data with trainer and booking counter, public (Requirement 3.2)
    - POST/PUT:   Admin only (Requirement 3.3)
    - DELETE:     cancel all related Bookings, then delete Session (Requirements 3.5, 3.6)
    """
    serializer_class = SessionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = Session.objects.select_related('trainer')
        if self.action == 'list':
            qs = qs.filter(is_active=True)
            date_param = self.request.query_params.get('date')
            if date_param:
                qs = qs.filter(date=date_param)
        return qs

    def destroy(self, request, *args, **kwargs):
        """Cancel all related bookings, then delete the session."""
        session = self.get_object()
        # Cancel all non-cancelled bookings and reset counter
        active_bookings = session.bookings.exclude(status=Booking.STATUS_CANCELLED)
        active_bookings.update(status=Booking.STATUS_CANCELLED)
        session.current_bookings = 0
        session.save(update_fields=['current_bookings'])
        session.delete()
        return Response(status=204)


class IsOwnerOrAdmin(permissions.BasePermission):
    """Object-level permission: allow access only to the booking owner or an Admin."""

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user == request.user


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Booking resource.

    - GET list:   own bookings for regular users, all bookings for Admins (Req 4.2)
    - GET detail: owner or Admin only (Req 4.3, 4.7)
    - POST:       authenticated user; capacity check; increment current_bookings (Req 4.1, 4.6)
    - PUT status: update status; adjust current_bookings on cancel/restore (Req 4.4)
    - DELETE:     soft-cancel; decrement current_bookings; owner or Admin (Req 4.5, 4.7)
    - GET /users/{id}/bookings/: all bookings for a user (Admin or self) (Req 5.3)
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Booking.objects.select_related('user', 'session__trainer')
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def get_permissions(self):
        if self.action in ('retrieve', 'destroy', 'update_status'):
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        """Override to apply object-level permissions for detail actions."""
        queryset = Booking.objects.select_related('user', 'session__trainer')
        obj = get_object_or_404(queryset, pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        POST /api/gym/bookings/
        Create a booking for the authenticated user.
        Validates capacity and increments current_bookings atomically.
        Requirements: 4.1, 4.6
        """
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'session_id': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Lock the session row to prevent race conditions
        try:
            session = Session.objects.select_for_update().get(pk=session_id)
        except Session.DoesNotExist:
            return Response({'session_id': 'Session not found.'}, status=status.HTTP_400_BAD_REQUEST)

        # Capacity check (Requirement 4.6)
        if session.current_bookings >= session.capacity:
            return Response(
                {'detail': 'This session is fully booked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent duplicate bookings
        if Booking.objects.filter(user=request.user, session=session).exists():
            return Response(
                {'detail': 'You already have a booking for this session.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = Booking.objects.create(
            user=request.user,
            session=session,
            status=Booking.STATUS_CONFIRMED,
        )
        session.current_bookings += 1
        session.save(update_fields=['current_bookings'])

        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'], url_path='status')
    @transaction.atomic
    def update_status(self, request, pk=None):
        """
        PUT /api/gym/bookings/{id}/status/
        Update booking status and adjust session counter accordingly.
        Requirements: 4.4
        """
        booking = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = [Booking.STATUS_CONFIRMED, Booking.STATUS_CANCELLED, Booking.STATUS_PENDING]
        if new_status not in valid_statuses:
            return Response(
                {'status': f'Must be one of: {", ".join(valid_statuses)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = booking.status
        if old_status == new_status:
            serializer = self.get_serializer(booking)
            return Response(serializer.data)

        session = Session.objects.select_for_update().get(pk=booking.session_id)

        # Transitioning to cancelled: free up a spot
        if new_status == Booking.STATUS_CANCELLED and old_status != Booking.STATUS_CANCELLED:
            if session.current_bookings > 0:
                session.current_bookings -= 1
                session.save(update_fields=['current_bookings'])

        # Transitioning away from cancelled: consume a spot
        elif old_status == Booking.STATUS_CANCELLED and new_status != Booking.STATUS_CANCELLED:
            if session.current_bookings >= session.capacity:
                return Response(
                    {'detail': 'Cannot restore booking: session is fully booked.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            session.current_bookings += 1
            session.save(update_fields=['current_bookings'])

        booking.status = new_status
        booking.save(update_fields=['status', 'updated_at'])

        serializer = self.get_serializer(booking)
        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/gym/bookings/{id}/
        Soft-cancel: set status to cancelled and decrement current_bookings.
        Requirements: 4.5, 4.7
        """
        booking = self.get_object()

        if booking.status != Booking.STATUS_CANCELLED:
            session = Session.objects.select_for_update().get(pk=booking.session_id)
            if session.current_bookings > 0:
                session.current_bookings -= 1
                session.save(update_fields=['current_bookings'])

        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=['status', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)



class UserBookingsView(APIView):
    """
    GET /api/gym/users/{user_id}/bookings/
    Returns all bookings for a given user.
    Accessible by Admin or the user themselves. (Requirement 5.3)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        # Only Admin or the user themselves may access
        if not request.user.is_staff and request.user.pk != user_id:
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(User, pk=user_id)
        bookings = Booking.objects.filter(user=target_user).select_related('user', 'session__trainer')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

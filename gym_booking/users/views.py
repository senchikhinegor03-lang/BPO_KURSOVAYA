from rest_framework import generics, permissions
from django.contrib.auth.models import User
from .serializers import UserRegisterSerializer, UserProfileSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UsersListView(generics.ListAPIView):
    """Admin-only endpoint to list all users. (Requirement 1.4)"""
    queryset = User.objects.all().order_by('id')
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAdminUser]

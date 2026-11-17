"""Дополнительные API для фронтенда.

В исходном бэкенде не было:
  * регистрации пользователей (был только вход по JWT);
  * изменения и удаления записи в личной аптечке (были только GET и POST).
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import UserMedication, UserProfile
from .serializers import UserMedicationSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Регистрация: {username, password, email?}. После неё фронтенд сам делает вход."""
    username = str(request.data.get('username') or '').strip()
    password = str(request.data.get('password') or '')
    email = str(request.data.get('email') or '').strip()

    if len(username) < 3:
        return Response({'error': 'Імя карыстальніка павінна змяшчаць не менш за 3 сімвалы.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username__iexact=username).exists():
        return Response({'error': 'Карыстальнік з такім імем ужо існуе.'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_password(password, user=User(username=username, email=email))
    except ValidationError as exc:
        return Response({'error': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    UserProfile.objects.get_or_create(user=user)
    return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def my_medication_detail(request, pk):
    """Изменить или удалить запись из личной аптечки (только свою)."""
    item = get_object_or_404(UserMedication, pk=pk, user=request.user)

    if request.method == 'DELETE':
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = UserMedicationSerializer(item, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

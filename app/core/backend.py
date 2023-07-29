from rest_framework.authentication import BaseAuthentication

from .models import User


class BasicRequestBodyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        user_name = request.META.get('HTTP_USERNAME')
        try:
            user = User.objects.get(user_name=user_name)
            return user, None
        except User.DoesNotExist:
            return None

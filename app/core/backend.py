from rest_framework.authentication import BaseAuthentication

from .models import User


class BasicRequestBodyAuthentication(BaseAuthentication):
    """
    This serves as the custom authentication logic for each incoming request. This just requires the user_name to
    be present in the request header.
    """
    def authenticate(self, request):
        user_name = request.META.get('HTTP_USERNAME')
        try:
            user = User.objects.get(user_name=user_name)
            return user, None
        except User.DoesNotExist:
            return None

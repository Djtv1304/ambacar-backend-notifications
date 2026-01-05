"""
Authentication classes for internal service-to-service communication.
"""
from rest_framework import authentication, exceptions
from django.conf import settings


class InternalServiceAuthentication(authentication.BaseAuthentication):
    """
    Authentication for internal services using API Key in headers.
    Expected header: X-Internal-Secret

    Usage:
        class MyInternalView(APIView):
            authentication_classes = [InternalServiceAuthentication]

            def post(self, request):
                # Request is authenticated if it reaches here
                ...
    """

    def authenticate(self, request):
        """
        Authenticate the request using X-Internal-Secret header.

        Returns:
            tuple: (None, None) if authenticated
            None: if no authentication header present (allows other auth to try)

        Raises:
            AuthenticationFailed: if API key is invalid
        """
        api_key = request.META.get('HTTP_X_INTERNAL_SECRET')

        if not api_key:
            return None  # No header = don't attempt to authenticate

        if api_key != settings.INTERNAL_API_SECRET_KEY:
            raise exceptions.AuthenticationFailed('Invalid internal API key')

        # Return user=None, auth=None (authenticated but no user object)
        return (None, None)

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 Unauthenticated response.
        """
        return 'X-Internal-Secret'

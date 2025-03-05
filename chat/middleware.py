from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from channels.middleware import BaseMiddleware
from urllib.parse import parse_qs
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

class JWTAuthMiddleware(BaseMiddleware):
    """ WebSocket Authentication Middleware for JWT tokens """

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token", [None])[0]  # Extract token from query params

        if token:
            try:
                # Decode JWT Token
                decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

                # Fetch user based on JWT payload (ensure your JWT contains 'user_id')
                user_id = decoded_data.get("user_id")  # Adjust key based on your JWT payload

                if user_id:
                    user = await self.get_user(user_id)
                    scope["user"] = user if user else AnonymousUser()
                else:
                    scope["user"] = AnonymousUser()
            except jwt.ExpiredSignatureError:
                print("JWT Token has expired")
                scope["user"] = AnonymousUser()
            except jwt.InvalidTokenError:
                print("Invalid JWT Token")
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        close_old_connections()
        return await super().__call__(scope, receive, send)

    @staticmethod
    async def get_user(user_id):
        """ Fetch user asynchronously from the database """
        try:
            return await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            return None

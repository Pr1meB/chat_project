"""
ASGI config for chat_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django  # Import Django setup module
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.routing import websocket_urlpatterns


# Set the default settings module for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_project.settings")

# Initialize Django
django.setup()  # ✅ Ensures Django is fully set up before importing models/middleware

from chat.middleware import JWTAuthMiddleware

# Define the ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})

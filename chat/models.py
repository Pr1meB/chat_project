import base64
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class Profile(models.Model):
    # Extend the built-in User with additional fields if needed.
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # For now, no profile pic.
    bio = models.TextField(blank=True, null=True)
    # You might store online status here (or handle it in-memory).
    online = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class Chat(models.Model):
    """
    A private chat between two users.
    """
    participants = models.ManyToManyField(User, related_name="chats")
    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat #{self.id}"

    @classmethod
    def get_or_create_chat(cls, user1: User, user2: User):
        """
        Ensures only one chat exists between the same two participants.
        """
        chat = cls.objects.filter(
            participants=user1
        ).filter(participants=user2).first()

        if chat:
            return chat, False  # Chat already exists
        
        # Create a new chat
        chat = cls.objects.create()
        chat.participants.add(user1, user2)
        return chat, True  # New chat created


class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    # Message content stored in encrypted form (here: base64 encoded)
    content = models.TextField()
    # Media type can be "text", "image", "audio", "video"
    media_type = models.CharField(max_length=10, default="text")
    timestamp = models.DateTimeField(auto_now_add=True)

    def encrypt_content(self):
        # A simple encryption example (Base64)
        encoded = base64.b64encode(self.content.encode("utf-8")).decode("utf-8")
        return encoded

    def decrypt_content(self):
        try:
            decoded = base64.b64decode(self.content.encode("utf-8")).decode("utf-8")
        except Exception:
            decoded = self.content
        return decoded

    def __str__(self):
        return f"{self.sender.username}: {self.content[:20]}"

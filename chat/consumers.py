import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Accept the connection and add the user to the chat group."""
        await self.accept()

        # Extract user ID from scope (assuming authentication middleware)
        self.user_id = self.scope["user"].id if self.scope["user"].is_authenticated else None
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]  # Get chat ID from the URL route

        if self.user_id and self.chat_id:
            self.chat_group_name = f"chat_{self.chat_id}"
            await self.channel_layer.group_add(self.chat_group_name, self.channel_name)  # ✅ Add user to chat group

    async def disconnect(self, close_code):
        """Remove user from groups upon disconnect."""
        if self.chat_id:
            await self.channel_layer.group_discard(f"chat_{self.chat_id}", self.channel_name)


    async def receive(self, text_data):
        """
        Handles incoming WebSocket messages with event-based communication.
        Supported Events:
          - start_chat
          - new_message
          - update_profile
          - delete_chat
          - typing_indicator
          - user_online
          - user_offline
        """
        data = json.loads(text_data)
        event_type = data.get("event")
        payload = data.get("payload")

        if event_type == "start_chat":
            await self.channel_layer.group_send(
                f"user_{payload.get('recipient_id')}",
                {"type": "chat_started", "chat": payload.get("chat")},
            )

        elif event_type == "new_message":
            message_data = payload.get("message", {})

            # Ensure content is included
            message_data["content"] = payload.get("message", {}).get("content", "No content")

            # ✅ Broadcast message to all users in the chat group
            await self.channel_layer.group_send(
                f"chat_{payload.get('chat_id')}",
                {
                    "type": "new_message",
                    "message": message_data
                },
            )


        elif event_type == "update_profile":
            # Notify other users that this user's profile was updated.
            await self.channel_layer.group_send(
                "online_users",
                {"type": "profile_updated", "profile": payload.get("profile")},
            )

        elif event_type == "delete_chat":
            # Inform chat participants that a chat was deleted.
            await self.channel_layer.group_send(
                f"chat_{payload.get('chat_id')}",
                {"type": "chat_deleted", "chat_id": payload.get("chat_id")},
            )

        elif event_type == "typing_indicator":
            # Notify a recipient when the user is typing.
            await self.channel_layer.group_send(
                f"user_{payload.get('recipient_id')}",
                {"type": "user_typing", "user_id": payload.get("user_id")},
            )

        elif event_type == "user_online":
            await self.channel_layer.group_send(
                "online_users",
                {"type": "user_online", "user_id": payload.get("user_id")},
            )

        elif event_type == "user_offline":
            await self.channel_layer.group_send(
                "online_users",
                {"type": "user_offline", "user_id": payload.get("user_id")},
            )

    async def chat_started(self, event):
        """Send chat started event to the recipient."""
        await self.send(text_data=json.dumps({"event": "chat_started", "data": event["chat"]}))

    async def new_message(self, event):
        """Send a new message event to the recipient."""
        await self.send(text_data=json.dumps({
            "event": "new_message",
            "payload": {
                "message": {
                    "id": event["message"]["id"],
                    "sender": {
                        "id": event["message"]["sender"]["id"],
                        "username": event["message"]["sender"]["username"]
                    },
                    "content": event["message"]["content"],  # ✅ Ensure content is sent
                    "mediaType": event["message"]["mediaType"],
                    "timestamp": event["message"]["timestamp"]
                }
            }
        }))



    async def profile_updated(self, event):
        """Notify all users when a profile is updated."""
        await self.send(text_data=json.dumps({"event": "profile_updated", "data": event["profile"]}))

    async def chat_deleted(self, event):
        """Notify chat participants when a chat is deleted."""
        await self.send(text_data=json.dumps({"event": "chat_deleted", "data": {"chat_id": event["chat_id"]}}))

    async def user_typing(self, event):
        """Send typing indicator event to recipient."""
        await self.send(text_data=json.dumps({"event": "user_typing", "data": {"user_id": event["user_id"]}}))

    async def user_online(self, event):
        """Broadcast when a user comes online."""
        await self.send(text_data=json.dumps({"event": "user_online", "data": {"user_id": event["user_id"]}}))

    async def user_offline(self, event):
        """Broadcast when a user goes offline."""
        await self.send(text_data=json.dumps({"event": "user_offline", "data": {"user_id": event["user_id"]}}))

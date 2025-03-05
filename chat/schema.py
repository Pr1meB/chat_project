import strawberry
import strawberry_django
from strawberry import auto
from typing import List, Optional
from django.contrib.auth.models import User
from chat.models import Profile, Chat, Message
from django.contrib.auth import authenticate
import base64
from strawberry_django.optimizer import DjangoOptimizerExtension
from asgiref.sync import sync_to_async
import jwt
from django.contrib.auth import get_user_model
from django.conf import settings
import asyncio

User = get_user_model()
SECRET_KEY = settings.SECRET_KEY  # Use Django settings for security

# --- Types ---
@strawberry_django.type(User)
class UserType:
    id: int
    username: str
    email: str

@strawberry_django.type(Profile)
class ProfileType:
    bio: Optional[str]
    online: bool

@strawberry_django.type(Chat)
class ChatType:
    id: int
    started_at: str
    participants: List[UserType]  # List of users in the chat

@strawberry_django.type(Message)
class MessageType:
    id: int
    sender: UserType
    media_type: str
    timestamp: str
    content: str

    # # Override content to return the decrypted value
    # @strawberry.field
    # def content(self, root: Message) -> str:
    #     return root.decrypt_content()



# --- Input Types for Mutations ---
@strawberry.input
class SignupInput:
    username: str
    email: str
    password: str

@strawberry.input
class LoginInput:
    username: str
    password: str

@strawberry.input
class SendMessageInput:
    chat_id: int
    sender_id: int
    content: str
    media_type: Optional[str] = "text"

@strawberry.input
class StartChatInput:
    user1_id: int
    user2_id: int

# --- Auth Response ---
@strawberry.type
class AuthPayload:
    token: str
    user: UserType

# --- Queries ---
@strawberry.type
class Query:
    # Get all users
    @strawberry.field
    async def all_users(self) -> List[UserType]:
        users = await sync_to_async(list)(User.objects.all())
        return [UserType(id=user.id, username=user.username, email=user.email) for user in users]

    # Get a single user by ID
    @strawberry.field
    async def get_user(self, user_id: int) -> Optional[UserType]:
        try:
            user = await sync_to_async(User.objects.get)(id=user_id)
            return UserType(id=user.id, username=user.username, email=user.email)
        except User.DoesNotExist:
            return None

    # Get online users
    @strawberry.field
    async def online_users(self) -> List[UserType]:
        profiles = await sync_to_async(lambda: list(Profile.objects.filter(online=True)))()
    
        async def get_user_data(profile):
            user = await sync_to_async(lambda: profile.user)()  # Fetch related user asynchronously
            return UserType(id=user.id, username=user.username, email=user.email)
    
        return await asyncio.gather(*[get_user_data(profile) for profile in profiles])


    # Get user profile by ID
    @strawberry.field
    async def profile(self, user_id: int) -> Optional[ProfileType]:
        try:
            profile = await sync_to_async(Profile.objects.get)(user__id=user_id)
            return ProfileType(bio=profile.bio, online=profile.online)
        except Profile.DoesNotExist:
            return None

    # Get all chats for a user
    @strawberry.field
    async def all_chats(self, user_id: int) -> List[ChatType]:
        user = await sync_to_async(User.objects.get)(id=user_id)
        chats = await sync_to_async(lambda: list(user.chats.all()))()  # Fetch chats asynchronously

        async def get_chat_data(chat):
            participants = await sync_to_async(lambda: list(chat.participants.all()))()  # Fetch participants asynchronously
            return ChatType(id=chat.id, started_at=str(chat.started_at), participants=participants)

        return await asyncio.gather(*[get_chat_data(chat) for chat in chats])



    # Get chat details by chat ID
    @strawberry.field
    async def get_chat(self, chat_id: int) -> Optional[ChatType]:
        try:
            chat = await sync_to_async(Chat.objects.get)(id=chat_id)

            # Fetch participants asynchronously
            participants = await sync_to_async(lambda: list(chat.participants.all()))()

            return ChatType(
                id=chat.id, 
                started_at=str(chat.started_at), 
                participants=participants
            )
        except Chat.DoesNotExist:
            return None


    # Get all messages in a chat
    @strawberry.field
    async def all_messages(self, chat_id: int) -> List[MessageType]:
        chat = await sync_to_async(Chat.objects.get)(id=chat_id)
    
        # Fetch messages asynchronously
        messages = await sync_to_async(lambda: list(chat.messages.order_by("timestamp")))()
    
        async def get_message_data(msg):
            sender = await sync_to_async(lambda: msg.sender)()  # Fetch sender asynchronously
            return MessageType(
                id=msg.id, 
                sender=sender,  # Ensure sender is properly fetched
                media_type=msg.media_type, 
                timestamp=str(msg.timestamp),
                content=str(msg.decrypt_content())
            )
    
        return await asyncio.gather(*[get_message_data(msg) for msg in messages])


    # Get messages sent by a specific user
    @strawberry.field
    async def user_messages(self, user_id: int) -> List[MessageType]:
        messages = await sync_to_async(list)(Message.objects.filter(sender__id=user_id).order_by("-timestamp"))
        return [
            MessageType(
                id=msg.id, 
                sender=msg.sender, 
                media_type=msg.media_type, 
                timestamp=str(msg.timestamp),
                content=str(msg.decrypt_content())
            ) 
            for msg in messages
        ]

    # Get latest message in a chat
    @strawberry.field
    async def latest_message(self, chat_id: int) -> Optional[MessageType]:
        try:
            # Fetch latest message asynchronously
            message = await sync_to_async(lambda: Message.objects.filter(chat_id=chat_id).order_by("-timestamp").first())()
        
            if not message:
                return None  # No messages exist in this chat
        
            # Ensure all attributes are properly retrieved
            sender = await sync_to_async(lambda: message.sender)()  

            return MessageType(
                id=message.id, 
                sender=sender,  
                media_type=message.media_type, 
                timestamp=str(message.timestamp),
                content=str(message.decrypt_content())  # Ensure decrypt_content() is sync-safe
            )
        except Exception as e:
            print(f"Error fetching latest message: {e}")
            return None



# --- Mutations ---
@strawberry.type
class Mutation:
    # User signup
    @strawberry.mutation
    async def signup(self, input: SignupInput) -> AuthPayload:
        user = await sync_to_async(User.objects.create_user)(
            username=input.username,
            email=input.email,
            password=input.password,
        )
        await sync_to_async(Profile.objects.create)(user=user)

        # Generate JWT token
        token = jwt.encode({"user_id": user.id}, SECRET_KEY, algorithm="HS256")

        return AuthPayload(token=token, user=user)

    # User login
    @strawberry.mutation
    async def login(self, input: LoginInput) -> Optional[AuthPayload]:
        user = await sync_to_async(authenticate)(username=input.username, password=input.password)
        if user:
            profile, _ = await sync_to_async(Profile.objects.get_or_create)(user=user)
            profile.online = True
            await sync_to_async(profile.save)()

            token = jwt.encode({"user_id": user.id}, SECRET_KEY, algorithm="HS256")
            return AuthPayload(token=token, user=user)
        return None

    # Update user profile
    @strawberry.mutation
    async def update_profile(self, user_id: int, bio: str) -> Optional[ProfileType]:
        try:
            profile = await sync_to_async(Profile.objects.get)(user__id=user_id)
            profile.bio = bio
            await sync_to_async(profile.save)()
            return ProfileType(bio=profile.bio, online=profile.online)
        except Profile.DoesNotExist:
            return None

    # Start a chat between two users
    @strawberry.mutation
    async def start_chat(self, input: StartChatInput) -> ChatType:
        user1 = await sync_to_async(User.objects.get)(id=input.user1_id)
        user2 = await sync_to_async(User.objects.get)(id=input.user2_id)
        chat, created = await sync_to_async(Chat.get_or_create_chat)(user1, user2)
        # await sync_to_async(chat.participants.add)(user1, user2)
        await sync_to_async(chat.save)()
        return ChatType(id=chat.id, started_at=str(chat.started_at), participants=[user1, user2])

    # Send a message in a chat
    @strawberry.mutation
    async def send_message(self, input: SendMessageInput) -> MessageType:
        # Fetch chat and sender asynchronously
        chat = await sync_to_async(Chat.objects.get)(id=input.chat_id)
        sender = await sync_to_async(User.objects.get)(id=input.sender_id)

        # Encrypt message content
        encrypted_content = base64.b64encode(input.content.encode("utf-8")).decode("utf-8")

        # Save message asynchronously
        message = await sync_to_async(Message.objects.create)(
            chat=chat,
            sender=sender,
            content=encrypted_content,
            media_type=input.media_type or "text"
        )

        # Explicitly decrypt the content before returning the response
        decrypted_content = message.decrypt_content()

        return MessageType(
            id=message.id,
            sender=sender,
            media_type=message.media_type,
            timestamp=str(message.timestamp),
            content=decrypted_content  # ✅ Ensure decrypted content is returned
        )

    # Mark messages as read
    @strawberry.mutation
    async def mark_messages_read(self, chat_id: int, user_id: int) -> bool:
        messages = await sync_to_async(list)(Message.objects.filter(chat__id=chat_id, sender__id=user_id))
        for msg in messages:
            msg.read = True
            await sync_to_async(msg.save)()
        return True

    # Delete a chat
    @strawberry.mutation
    async def delete_chat(self, chat_id: int) -> bool:
        try:
            chat = await sync_to_async(Chat.objects.get)(id=chat_id)
            await sync_to_async(chat.delete)()
            return True
        except Chat.DoesNotExist:
            return False

    # Delete a message
    @strawberry.mutation
    async def delete_message(self, message_id: int) -> bool:
        try:
            message = await sync_to_async(Message.objects.get)(id=message_id)
            await sync_to_async(message.delete)()
            return True
        except Message.DoesNotExist:
            return False

    # Logout Mutation (update user online status)
    @strawberry.mutation
    async def logout(self, user_id: int) -> bool:
        try:
            profile = await sync_to_async(Profile.objects.get)(user__id=user_id)
            profile.online = False
            await sync_to_async(profile.save)()
            return True
        except Profile.DoesNotExist:
            return False

# --- Define GraphQL Schema ---
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[DjangoOptimizerExtension],
)

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import REACTION_MAP
from .services import connection_for, create_reaction


class CoupleConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.connection = await self.get_connection()
        if not self.scope["user"].is_authenticated or not self.connection:
            await self.close(code=4403)
            return
        self.group_name = f"couple_{self.connection.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "ready", "message": "Your quiet connection is open."})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") != "reaction":
            await self.send_json({"type": "error", "message": "Unsupported event."})
            return
        reaction_type = content.get("reaction_type")
        if reaction_type not in REACTION_MAP:
            await self.send_json({"type": "error", "message": "That reaction is not available."})
            return
        reaction, error = await self.save_reaction(reaction_type, content.get("mood_id"))
        if error:
            await self.send_json({"type": "error", "message": error})

    async def mood_event(self, event):
        await self.send_json({"type": "mood", "sender_id": event["sender_id"], "mood_id": event["mood_id"], "mood_type": event["mood_type"]})

    async def reaction_event(self, event):
        await self.send_json({"type": "reaction", "sender_id": event["sender_id"], "reaction_id": event["reaction_id"], "reaction_type": event["reaction_type"]})

    @database_sync_to_async
    def get_connection(self):
        return connection_for(self.scope["user"])

    @database_sync_to_async
    def save_reaction(self, reaction_type, mood_id):
        return create_reaction(self.scope["user"], reaction_type, mood_id)


#The WebSocket consumer sends progress messages to the client. Each client joins a channel group named analysis_<session_id>. When the pipeline uses group_send, the progress_message method relays JSON messages to the frontend.

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AnalysisConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'analysis_{self.session_id}'

        # Join room group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from group
    async def progress_message(self, event):
        message = event['message']
        # Send message to WebSocket client
        await self.send(text_data=json.dumps({'message': message}))
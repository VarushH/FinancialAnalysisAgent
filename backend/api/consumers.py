# backend/api/consumers.py
"""
WebSocket consumers for real-time progress updates.
Supports both progress messages and checkpoint notifications.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AnalysisConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for analysis progress updates.
    Handles real-time messaging between the workflow and client.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'analysis_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        logger.info(f"WebSocket connected for session {self.session_id}")
        
        # Send initial connection message
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to analysis progress stream',
            'session_id': self.session_id
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for session {self.session_id}")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages from client.
        Clients can send approval confirmations via WebSocket.
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'approve':
                # Client approving a checkpoint
                feedback = data.get('feedback', '')
                checkpoint = data.get('checkpoint')
                
                await self.send(text_data=json.dumps({
                    'type': 'approval_received',
                    'checkpoint': checkpoint,
                    'message': 'Approval received, processing...'
                }))
                
            elif message_type == 'ping':
                # Keepalive ping
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'message': 'Connection alive'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON message'
            }))
    
    async def progress_message(self, event):
        """
        Receive progress message from workflow and send to WebSocket client.
        """
        message = event.get('message', '')
        
        await self.send(text_data=json.dumps({
            'type': 'progress',
            'message': message
        }))
    
    async def checkpoint_required(self, event):
        """
        Notify client that a human-in-the-loop checkpoint requires approval.
        """
        checkpoint = event.get('checkpoint', '')
        details = event.get('details', {})
        
        await self.send(text_data=json.dumps({
            'type': 'checkpoint',
            'checkpoint': checkpoint,
            'requires_approval': True,
            'details': details,
            'message': f'Approval required at checkpoint: {checkpoint}'
        }))
    
    async def workflow_completed(self, event):
        """
        Notify client that workflow has completed.
        """
        report_url = event.get('report_url')
        
        await self.send(text_data=json.dumps({
            'type': 'completed',
            'report_url': report_url,
            'message': 'Analysis completed successfully!'
        }))
    
    async def workflow_error(self, event):
        """
        Notify client of workflow error.
        """
        error = event.get('error', 'Unknown error')
        agent = event.get('agent')
        recoverable = event.get('recoverable', False)
        
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error,
            'agent': agent,
            'recoverable': recoverable,
            'message': f'Error in {agent}: {error}' if agent else f'Error: {error}'
        }))
    
    async def state_update(self, event):
        """
        Send workflow state update to client.
        """
        state = event.get('state', {})
        
        await self.send(text_data=json.dumps({
            'type': 'state_update',
            'current_agent': state.get('current_agent'),
            'status': state.get('status'),
            'messages': state.get('messages', [])[-3:]  # Last 3 messages
        }))
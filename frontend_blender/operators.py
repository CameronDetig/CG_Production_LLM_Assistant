"""
Operator definitions for CG Production Assistant addon.
Handles user interactions and API calls.
"""

import bpy
import os
import tempfile
import threading
import queue
import webbrowser
import urllib.request
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator

from .api_client import get_api_client, reset_api_client, APIClient
from .utils import image_to_base64, format_chat_response, get_temp_image_path


# ============================================================================
# Authentication Operators
# ============================================================================

class CG_OT_Login(Operator):
    """Log in to the CG Production Assistant backend"""
    bl_idname = "cg_assistant.login"
    bl_label = "Login"
    bl_description = "Authenticate with the backend"
    
    _timer = None
    _client = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            response = self._client.get_response()
            if response:
                status, result = response
                props = context.scene.cg_assistant
                prefs = context.preferences.addons[__package__].preferences
                
                if status == 'success' and result.success:
                    # Store token and user info
                    prefs.auth_token = result.data.get('id_token', '')
                    prefs.user_email = result.data.get('user_id', props.login_email)
                    props.is_authenticated = True
                    props.auth_status = f"Logged in as {prefs.user_email}"
                    props.login_password = ""  # Clear password
                    
                    # Load conversations
                    bpy.ops.cg_assistant.refresh_conversations()
                else:
                    error_msg = result.error if hasattr(result, 'error') else str(result)
                    props.auth_status = f"Login failed: {error_msg}"
                    props.is_authenticated = False
                
                props.is_loading = False
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        
        if not props.login_email or not props.login_password:
            self.report({'WARNING'}, "Please enter email and password")
            return {'CANCELLED'}
        
        props.is_loading = True
        props.auth_status = "Logging in..."
        
        self._client = get_api_client(context)
        self._client.authenticate_async(props.login_email, props.login_password)
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CG_OT_DemoLogin(Operator):
    """Quick login with demo account"""
    bl_idname = "cg_assistant.demo_login"
    bl_label = "Demo Login"
    bl_description = "Login with the demo account"
    
    _timer = None
    _client = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            response = self._client.get_response()
            if response:
                status, result = response
                props = context.scene.cg_assistant
                prefs = context.preferences.addons[__package__].preferences
                
                if status == 'success' and result.success:
                    prefs.auth_token = result.data.get('id_token', '')
                    prefs.user_email = result.data.get('user_id', prefs.demo_email)
                    props.is_authenticated = True
                    props.auth_status = f"Logged in as {prefs.user_email}"
                    
                    # Load conversations
                    bpy.ops.cg_assistant.refresh_conversations()
                else:
                    error_msg = result.error if hasattr(result, 'error') else str(result)
                    props.auth_status = f"Demo login failed: {error_msg}"
                
                props.is_loading = False
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        prefs = context.preferences.addons[__package__].preferences
        
        props.is_loading = True
        props.auth_status = "Logging in with demo account..."
        
        self._client = get_api_client(context)
        self._client.authenticate_async(prefs.demo_email, prefs.demo_password)
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CG_OT_Logout(Operator):
    """Log out from the CG Production Assistant"""
    bl_idname = "cg_assistant.logout"
    bl_label = "Logout"
    bl_description = "Log out from the backend"
    
    def execute(self, context):
        props = context.scene.cg_assistant
        prefs = context.preferences.addons[__package__].preferences
        
        # Clear authentication
        prefs.auth_token = ""
        prefs.user_email = ""
        props.is_authenticated = False
        props.auth_status = "Logged out"
        
        # Clear conversations
        context.scene.cg_conversations.clear()
        props.current_conversation_id = ""
        
        # Clear chat history
        context.scene.cg_chat_history.clear()
        
        # Reset API client
        reset_api_client()
        
        return {'FINISHED'}


# ============================================================================
# Conversation Operators
# ============================================================================

class CG_OT_RefreshConversations(Operator):
    """Refresh the conversations list"""
    bl_idname = "cg_assistant.refresh_conversations"
    bl_label = "Refresh Conversations"
    bl_description = "Reload conversations from the server"
    
    _timer = None
    _client = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            response = self._client.get_response()
            if response:
                status, result = response
                props = context.scene.cg_assistant
                
                if status == 'success' and result.success:
                    conversations = result.data.get('conversations', [])
                    
                    # Clear and rebuild conversations list
                    context.scene.cg_conversations.clear()
                    for conv in conversations:
                        item = context.scene.cg_conversations.add()
                        item.conversation_id = conv.get('conversation_id', '')
                        item.title = conv.get('title', 'Untitled')
                
                props.is_loading = False
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        
        if not props.is_authenticated:
            self.report({'WARNING'}, "Please log in first")
            return {'CANCELLED'}
        
        props.is_loading = True
        
        self._client = get_api_client(context)
        self._client.get_conversations_async()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CG_OT_LoadConversation(Operator):
    """Load a conversation"""
    bl_idname = "cg_assistant.load_conversation"
    bl_label = "Load Conversation"
    bl_description = "Load the selected conversation"
    
    conversation_id: StringProperty()
    
    _timer = None
    _client = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            response = self._client.get_response()
            if response:
                status, result = response
                props = context.scene.cg_assistant
                
                if status == 'success' and result.success:
                    conversation = result.data.get('conversation', {})
                    messages = conversation.get('messages', [])
                    
                    # Clear and rebuild chat history
                    context.scene.cg_chat_history.clear()
                    for msg in messages:
                        item = context.scene.cg_chat_history.add()
                        item.role = msg.get('role', 'user')
                        item.content = msg.get('content', '') or ''
                    
                    props.current_conversation_id = self.conversation_id
                
                props.is_loading = False
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        
        if not self.conversation_id:
            # Get from selected index
            if props.conversation_index < len(context.scene.cg_conversations):
                self.conversation_id = context.scene.cg_conversations[props.conversation_index].conversation_id
        
        if not self.conversation_id:
            self.report({'WARNING'}, "No conversation selected")
            return {'CANCELLED'}
        
        props.is_loading = True
        
        self._client = get_api_client(context)
        self._client.get_conversation_async(self.conversation_id)
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CG_OT_NewConversation(Operator):
    """Start a new conversation"""
    bl_idname = "cg_assistant.new_conversation"
    bl_label = "New Conversation"
    bl_description = "Start a new conversation"
    
    def execute(self, context):
        props = context.scene.cg_assistant
        
        # Clear current conversation
        props.current_conversation_id = ""
        context.scene.cg_chat_history.clear()
        context.scene.cg_blend_files.clear()
        props.message_input = ""
        props.current_response = ""
        
        return {'FINISHED'}


class CG_OT_DeleteConversation(Operator):
    """Delete the selected conversation"""
    bl_idname = "cg_assistant.delete_conversation"
    bl_label = "Delete Conversation"
    bl_description = "Delete the selected conversation"
    
    _timer = None
    _client = None
    _conversation_id = ""
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            response = self._client.get_response()
            if response:
                status, result = response
                props = context.scene.cg_assistant
                
                if status == 'success' and result.success:
                    # Clear if current conversation was deleted
                    if props.current_conversation_id == self._conversation_id:
                        props.current_conversation_id = ""
                        context.scene.cg_chat_history.clear()
                    
                    # Refresh conversations list
                    bpy.ops.cg_assistant.refresh_conversations()
                else:
                    error_msg = result.error if hasattr(result, 'error') else str(result)
                    self.report({'ERROR'}, f"Failed to delete: {error_msg}")
                
                props.is_loading = False
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        
        if props.conversation_index >= len(context.scene.cg_conversations):
            self.report({'WARNING'}, "No conversation selected")
            return {'CANCELLED'}
        
        self._conversation_id = context.scene.cg_conversations[props.conversation_index].conversation_id
        
        if not self._conversation_id:
            self.report({'WARNING'}, "Invalid conversation")
            return {'CANCELLED'}
        
        props.is_loading = True
        
        self._client = get_api_client(context)
        self._client.delete_conversation_async(self._conversation_id)
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


# ============================================================================
# Chat Operators
# ============================================================================

class CG_OT_SendMessage(Operator):
    """Send a message to the assistant"""
    bl_idname = "cg_assistant.send_message"
    bl_label = "Send Message"
    bl_description = "Send your message to the assistant"
    
    _timer = None
    _client = None
    _response_queue = None
    _thread = None
    _accumulated_text = ""
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            props = context.scene.cg_assistant
            
            # Check for response
            response = self._client.get_response()
            if response:
                status, result = response
                
                if status == 'success' and result.success:
                    # Parse and process the response
                    events = result.data.get('events', [])
                    final_text = result.data.get('text', '')
                    
                    # Extract blend files and conversation ID
                    text, blend_files, conv_id = format_chat_response(events)
                    
                    # Update assistant message with final text
                    if len(context.scene.cg_chat_history) > 0:
                        context.scene.cg_chat_history[-1].content = final_text
                    
                    # Update conversation ID
                    if conv_id:
                        props.current_conversation_id = conv_id
                        # Refresh conversations to show new one
                        bpy.ops.cg_assistant.refresh_conversations()
                    
                    # Store blend files
                    context.scene.cg_blend_files.clear()
                    for bf in blend_files:
                        item = context.scene.cg_blend_files.add()
                        item.name = bf.get('name', '')
                        item.file_path = bf.get('file_path', '')
                        item.download_url = bf.get('download_url', '')
                        item.thumbnail_url = bf.get('thumbnail_url', '')
                else:
                    error_msg = result.error if hasattr(result, 'error') else str(result)
                    if len(context.scene.cg_chat_history) > 0:
                        context.scene.cg_chat_history[-1].content = f"Error: {error_msg}"
                
                props.is_loading = False
                props.has_image_attached = False
                props.captured_image_path = ""
                self.cancel(context)
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        props = context.scene.cg_assistant
        
        if not props.message_input.strip() and not props.has_image_attached:
            self.report({'WARNING'}, "Please enter a message or attach an image")
            return {'CANCELLED'}
        
        if not props.is_authenticated:
            self.report({'WARNING'}, "Please log in first")
            return {'CANCELLED'}
        
        # Add user message to history
        user_msg = context.scene.cg_chat_history.add()
        user_msg.role = "user"
        user_msg.content = props.message_input or "Find similar images"
        
        # Add placeholder for assistant response
        assistant_msg = context.scene.cg_chat_history.add()
        assistant_msg.role = "assistant"
        assistant_msg.content = "Thinking..."
        
        props.is_loading = True
        
        # Prepare image if attached
        image_base64 = None
        if props.has_image_attached and props.captured_image_path:
            image_base64 = image_to_base64(props.captured_image_path)
        
        # Send request
        self._client = get_api_client(context)
        self._client.chat_stream_async(
            query=props.message_input or "Find similar images to the uploaded image",
            conversation_id=props.current_conversation_id if props.current_conversation_id else None,
            image_base64=image_base64
        )
        
        # Clear input
        props.message_input = ""
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


# ============================================================================
# Image Operators
# ============================================================================

class CG_OT_UploadImage(Operator):
    """Upload an image for visual search"""
    bl_idname = "cg_assistant.upload_image"
    bl_label = "Upload Image"
    bl_description = "Select an image file to attach to your query"
    
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.bmp;*.tiff", options={'HIDDEN'})
    
    def execute(self, context):
        props = context.scene.cg_assistant
        
        if os.path.exists(self.filepath):
            props.captured_image_path = self.filepath
            props.has_image_attached = True
            self.report({'INFO'}, f"Image attached: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "File not found")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class CG_OT_CaptureViewport(Operator):
    """Capture the current viewport for visual search"""
    bl_idname = "cg_assistant.capture_viewport"
    bl_label = "Capture Viewport"
    bl_description = "Render the current viewport and attach to your query"
    
    def execute(self, context):
        props = context.scene.cg_assistant
        
        # Store original render settings
        scene = context.scene
        original_filepath = scene.render.filepath
        original_file_format = scene.render.image_settings.file_format
        original_res_x = scene.render.resolution_x
        original_res_y = scene.render.resolution_y
        original_res_percentage = scene.render.resolution_percentage
        
        try:
            # Set up for viewport render
            temp_path = get_temp_image_path("cg_viewport")
            scene.render.filepath = temp_path
            scene.render.image_settings.file_format = 'PNG'
            scene.render.resolution_x = 512
            scene.render.resolution_y = 512
            scene.render.resolution_percentage = 100
            
            # Render viewport
            bpy.ops.render.opengl(write_still=True)
            
            # Store path
            props.captured_image_path = temp_path + ".png"  # Blender adds extension
            props.has_image_attached = True
            
            self.report({'INFO'}, "Viewport captured")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to capture viewport: {str(e)}")
            return {'CANCELLED'}
        
        finally:
            # Restore original settings
            scene.render.filepath = original_filepath
            scene.render.image_settings.file_format = original_file_format
            scene.render.resolution_x = original_res_x
            scene.render.resolution_y = original_res_y
            scene.render.resolution_percentage = original_res_percentage
        
        return {'FINISHED'}


class CG_OT_ClearImage(Operator):
    """Clear the attached image"""
    bl_idname = "cg_assistant.clear_image"
    bl_label = "Clear Image"
    bl_description = "Remove the attached image"
    
    def execute(self, context):
        props = context.scene.cg_assistant
        props.captured_image_path = ""
        props.has_image_attached = False
        return {'FINISHED'}


# ============================================================================
# Blend File Operators
# ============================================================================

class CG_OT_OpenBlendFile(Operator):
    """Download and open a .blend file"""
    bl_idname = "cg_assistant.open_blend_file"
    bl_label = "Open Blend File"
    bl_description = "Download and open this .blend file in Blender"
    
    file_url: StringProperty()
    file_name: StringProperty()
    
    _timer = None
    _thread = None
    _download_path = ""
    _download_complete = False
    _download_error = ""
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if self._download_complete:
                self.cancel(context)
                
                if self._download_error:
                    self.report({'ERROR'}, self._download_error)
                    return {'CANCELLED'}
                
                # Open the downloaded file
                try:
                    bpy.ops.wm.open_mainfile(filepath=self._download_path)
                    self.report({'INFO'}, f"Opened: {self.file_name}")
                except Exception as e:
                    self.report({'ERROR'}, f"Failed to open file: {str(e)}")
                
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        # Check for unsaved changes
        if bpy.data.is_dirty:
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)
    
    def execute(self, context):
        if not self.file_url:
            self.report({'ERROR'}, "No download URL available")
            return {'CANCELLED'}
        
        # Set up download path
        temp_dir = tempfile.gettempdir()
        self._download_path = os.path.join(temp_dir, self.file_name)
        
        # Start download in background thread
        def download():
            try:
                urllib.request.urlretrieve(self.file_url, self._download_path)
                self._download_complete = True
            except Exception as e:
                self._download_error = str(e)
                self._download_complete = True
        
        self._thread = threading.Thread(target=download, daemon=True)
        self._thread.start()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Downloading {self.file_name}...")
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CG_OT_OpenInBrowser(Operator):
    """Open a URL in the web browser"""
    bl_idname = "cg_assistant.open_in_browser"
    bl_label = "Open in Browser"
    bl_description = "Open this URL in your web browser"
    
    url: StringProperty()
    
    def execute(self, context):
        if self.url:
            webbrowser.open(self.url)
        return {'FINISHED'}


class CG_OT_CopyFilePath(Operator):
    """Copy file path to clipboard"""
    bl_idname = "cg_assistant.copy_file_path"
    bl_label = "Copy Path"
    bl_description = "Copy the file path to clipboard"
    
    path: StringProperty()
    
    def execute(self, context):
        if self.path:
            context.window_manager.clipboard = self.path
            self.report({'INFO'}, "Path copied to clipboard")
        return {'FINISHED'}


# ============================================================================
# UI State Operators
# ============================================================================

class CG_OT_ToggleLoginPanel(Operator):
    """Toggle the login panel visibility"""
    bl_idname = "cg_assistant.toggle_login_panel"
    bl_label = "Toggle Login"
    bl_description = "Show or hide the login form"
    
    def execute(self, context):
        props = context.scene.cg_assistant
        props.show_login_panel = not props.show_login_panel
        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

classes = [
    CG_OT_Login,
    CG_OT_DemoLogin,
    CG_OT_Logout,
    CG_OT_RefreshConversations,
    CG_OT_LoadConversation,
    CG_OT_NewConversation,
    CG_OT_DeleteConversation,
    CG_OT_SendMessage,
    CG_OT_UploadImage,
    CG_OT_CaptureViewport,
    CG_OT_ClearImage,
    CG_OT_OpenBlendFile,
    CG_OT_OpenInBrowser,
    CG_OT_CopyFilePath,
    CG_OT_ToggleLoginPanel,
]


def register():
    """Register operator classes."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister operator classes."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

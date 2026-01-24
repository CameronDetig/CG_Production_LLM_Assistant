"""
Property definitions for CG Production Assistant addon.
Defines PropertyGroups for state management.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    CollectionProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


class CG_ChatMessage(PropertyGroup):
    """A single chat message."""
    role: StringProperty(
        name="Role",
        description="Message role (user or assistant)",
        default="user"
    )
    content: StringProperty(
        name="Content",
        description="Message content",
        default=""
    )


class CG_Conversation(PropertyGroup):
    """A conversation entry for the dropdown."""
    conversation_id: StringProperty(
        name="Conversation ID",
        description="Unique conversation identifier",
        default=""
    )
    title: StringProperty(
        name="Title",
        description="Conversation title",
        default="New Conversation"
    )


class CG_BlendFileItem(PropertyGroup):
    """A .blend file from query results."""
    name: StringProperty(
        name="File Name",
        description="Name of the blend file",
        default=""
    )
    file_path: StringProperty(
        name="File Path",
        description="Path to the file in S3",
        default=""
    )
    download_url: StringProperty(
        name="Download URL",
        description="Presigned S3 URL for download",
        default=""
    )
    thumbnail_url: StringProperty(
        name="Thumbnail URL",
        description="URL to thumbnail image",
        default=""
    )


class CG_AssistantPreferences(bpy.types.AddonPreferences):
    """Addon preferences for persistent storage."""
    bl_idname = __package__
    
    api_endpoint: StringProperty(
        name="API Endpoint",
        description="Backend API URL",
        default="https://fhvltd2p33ejzyk5l5tgxyz4340qrghe.lambda-url.us-east-1.on.aws",
        subtype='NONE'
    )
    
    demo_email: StringProperty(
        name="Demo Email",
        description="Demo account email for quick login",
        default="demo@cgassistant.com"
    )
    
    demo_password: StringProperty(
        name="Demo Password",
        description="Demo account password",
        default="DemoPass10!",
        subtype='PASSWORD'
    )
    
    auth_token: StringProperty(
        name="Auth Token",
        description="Current authentication token",
        default="",
        subtype='PASSWORD'
    )
    
    user_email: StringProperty(
        name="User Email",
        description="Currently logged in user email",
        default=""
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_endpoint")
        layout.separator()
        layout.label(text="Demo Account:")
        layout.prop(self, "demo_email")
        layout.prop(self, "demo_password")


class CG_SceneProperties(PropertyGroup):
    """Scene-level properties for the addon."""
    
    # Authentication state
    is_authenticated: BoolProperty(
        name="Is Authenticated",
        description="Whether user is logged in",
        default=False
    )
    
    auth_status: StringProperty(
        name="Auth Status",
        description="Authentication status message",
        default="Not logged in"
    )
    
    # Login form fields
    login_email: StringProperty(
        name="Email",
        description="Email for login",
        default=""
    )
    
    login_password: StringProperty(
        name="Password",
        description="Password for login",
        default="",
        subtype='PASSWORD'
    )
    
    # Conversation management
    current_conversation_id: StringProperty(
        name="Current Conversation ID",
        description="ID of the active conversation",
        default=""
    )
    
    conversation_index: IntProperty(
        name="Conversation Index",
        description="Index of selected conversation in list",
        default=0
    )
    
    # Chat state
    message_input: StringProperty(
        name="Message",
        description="Message to send",
        default=""
    )
    
    is_loading: BoolProperty(
        name="Is Loading",
        description="Whether a request is in progress",
        default=False
    )
    
    current_response: StringProperty(
        name="Current Response",
        description="Streaming response accumulator",
        default=""
    )
    
    # Image for query
    captured_image_path: StringProperty(
        name="Captured Image Path",
        description="Path to viewport capture or uploaded image",
        default="",
        subtype='FILE_PATH'
    )
    
    has_image_attached: BoolProperty(
        name="Has Image Attached",
        description="Whether an image is attached to the query",
        default=False
    )
    
    # Chat history index for UIList
    chat_history_index: IntProperty(
        name="Chat History Index",
        description="Index of selected chat message",
        default=0
    )
    
    # Blend files index for UIList
    blend_files_index: IntProperty(
        name="Blend Files Index",
        description="Index of selected blend file",
        default=0
    )
    
    # UI state
    show_login_panel: BoolProperty(
        name="Show Login Panel",
        description="Whether to show the login form",
        default=False
    )


# All classes to register
classes = [
    CG_ChatMessage,
    CG_Conversation,
    CG_BlendFileItem,
    CG_AssistantPreferences,
    CG_SceneProperties,
]


def register():
    """Register property classes."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register scene properties
    bpy.types.Scene.cg_assistant = PointerProperty(type=CG_SceneProperties)
    
    # Register collection properties on scene
    bpy.types.Scene.cg_chat_history = CollectionProperty(type=CG_ChatMessage)
    bpy.types.Scene.cg_conversations = CollectionProperty(type=CG_Conversation)
    bpy.types.Scene.cg_blend_files = CollectionProperty(type=CG_BlendFileItem)


def unregister():
    """Unregister property classes."""
    # Remove scene properties
    del bpy.types.Scene.cg_blend_files
    del bpy.types.Scene.cg_conversations
    del bpy.types.Scene.cg_chat_history
    del bpy.types.Scene.cg_assistant
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

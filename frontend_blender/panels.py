"""
Panel definitions for CG Production Assistant addon.
Creates the UI in the 3D View sidebar.
"""

import bpy
from bpy.types import Panel, UIList
import os

from .utils import truncate_text, wrap_text


# ============================================================================
# UILists for displaying collections
# ============================================================================

class CG_UL_ChatHistory(UIList):
    """UIList for displaying chat messages."""
    bl_idname = "CG_UL_ChatHistory"
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Role indicator
            if item.role == 'user':
                row.label(text="", icon='USER')
            else:
                row.label(text="", icon='OUTLINER_OB_LIGHT')
            
            # Message content (truncated)
            content = truncate_text(item.content, 60)
            row.label(text=content)
            
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='CHAT')


class CG_UL_Conversations(UIList):
    """UIList for displaying conversations."""
    bl_idname = "CG_UL_Conversations"
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=truncate_text(item.title, 30), icon='OUTLINER_OB_FONT')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OUTLINER_OB_FONT')


class CG_UL_BlendFiles(UIList):
    """UIList for displaying blend files from results."""
    bl_idname = "CG_UL_BlendFiles"
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=truncate_text(item.name, 25), icon='FILE_BLEND')
            
            # Action buttons
            if item.download_url:
                op = row.operator("cg_assistant.open_blend_file", text="", icon='IMPORT')
                op.file_url = item.download_url
                op.file_name = item.name
            
            if item.file_path:
                op = row.operator("cg_assistant.copy_file_path", text="", icon='COPYDOWN')
                op.path = item.file_path
                
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_BLEND')


# ============================================================================
# Main Panel
# ============================================================================

class CG_PT_MainPanel(Panel):
    """Main panel for CG Production Assistant."""
    bl_idname = "CG_PT_MainPanel"
    bl_label = "CG Production Assistant"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        prefs = context.preferences.addons[__package__].preferences
        
        # Loading indicator
        if props.is_loading:
            row = layout.row()
            row.alert = True
            row.label(text="Loading...", icon='SORTTIME')


class CG_PT_AuthPanel(Panel):
    """Authentication panel."""
    bl_idname = "CG_PT_AuthPanel"
    bl_label = "Authentication"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    bl_parent_id = "CG_PT_MainPanel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw_header(self, context):
        props = context.scene.cg_assistant
        if props.is_authenticated:
            self.layout.label(text="", icon='CHECKMARK')
        else:
            self.layout.label(text="", icon='ERROR')
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        prefs = context.preferences.addons[__package__].preferences
        
        # Status display
        box = layout.box()
        if props.is_authenticated:
            box.label(text=f"Logged in as: {prefs.user_email}", icon='USER')
            box.operator("cg_assistant.logout", text="Logout", icon='PANEL_CLOSE')
        else:
            box.label(text=props.auth_status, icon='INFO')
            
            # Demo login button
            box.operator("cg_assistant.demo_login", text="Demo Login", icon='PLAY')
            
            # Login form toggle
            box.operator("cg_assistant.toggle_login_panel", 
                        text="Show Login Form" if not props.show_login_panel else "Hide Login Form",
                        icon='TRIA_DOWN' if props.show_login_panel else 'TRIA_RIGHT')
            
            if props.show_login_panel:
                col = box.column(align=True)
                col.prop(props, "login_email", text="Email")
                col.prop(props, "login_password", text="Password")
                col.operator("cg_assistant.login", text="Login", icon='CHECKMARK')


class CG_PT_ConversationsPanel(Panel):
    """Conversations management panel."""
    bl_idname = "CG_PT_ConversationsPanel"
    bl_label = "Conversations"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    bl_parent_id = "CG_PT_MainPanel"
    
    @classmethod
    def poll(cls, context):
        return context.scene.cg_assistant.is_authenticated
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        
        # Conversations list
        row = layout.row()
        row.template_list(
            "CG_UL_Conversations", "",
            context.scene, "cg_conversations",
            props, "conversation_index",
            rows=3
        )
        
        # Action buttons
        row = layout.row(align=True)
        row.operator("cg_assistant.new_conversation", text="New", icon='FILE_NEW')
        row.operator("cg_assistant.load_conversation", text="Load", icon='IMPORT')
        row.operator("cg_assistant.delete_conversation", text="Delete", icon='TRASH')
        row.operator("cg_assistant.refresh_conversations", text="", icon='FILE_REFRESH')


class CG_PT_ChatPanel(Panel):
    """Chat interface panel with message input."""
    bl_idname = "CG_PT_ChatPanel"
    bl_label = "Chat"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    bl_parent_id = "CG_PT_MainPanel"
    
    @classmethod
    def poll(cls, context):
        return context.scene.cg_assistant.is_authenticated
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        
        # Chat history list - larger with more rows
        row = layout.row()
        row.template_list(
            "CG_UL_ChatHistory", "",
            context.scene, "cg_chat_history",
            props, "chat_history_index",
            rows=8
        )
        
        # Show selected message content in expandable box
        if props.chat_history_index < len(context.scene.cg_chat_history):
            selected_msg = context.scene.cg_chat_history[props.chat_history_index]
            
            msg_box = layout.box()
            role_text = "You:" if selected_msg.role == 'user' else "Assistant:"
            msg_box.label(text=role_text, icon='USER' if selected_msg.role == 'user' else 'OUTLINER_OB_LIGHT')
            
            # Wrap long content with wider width for sidebar
            content_lines = wrap_text(selected_msg.content, 55)
            for line in content_lines[:12]:  # Show more lines
                msg_box.label(text=line)
            if len(content_lines) > 12:
                msg_box.label(text=f"... ({len(content_lines) - 12} more lines)")
        
        layout.separator()
        
        # Message input section (combined from InputPanel)
        layout.label(text="New Message:", icon='EDITMODE_HLT')
        layout.prop(props, "message_input", text="")
        
        # Send button
        row = layout.row()
        row.scale_y = 1.5
        row.enabled = not props.is_loading
        
        if props.has_image_attached:
            row.operator("cg_assistant.send_message", text="Send with Image", icon='EXPORT')
        else:
            row.operator("cg_assistant.send_message", text="Send Message", icon='EXPORT')


class CG_PT_BlendFilesPanel(Panel):
    """Panel for displaying .blend files from results."""
    bl_idname = "CG_PT_BlendFilesPanel"
    bl_label = "Blend Files"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    bl_parent_id = "CG_PT_MainPanel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return len(context.scene.cg_blend_files) > 0
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        
        layout.label(text=f"Found {len(context.scene.cg_blend_files)} .blend files:", icon='FILE_BLEND')
        
        row = layout.row()
        row.template_list(
            "CG_UL_BlendFiles", "",
            context.scene, "cg_blend_files",
            props, "blend_files_index",
            rows=3
        )
        
        # Show details for selected file
        if props.blend_files_index < len(context.scene.cg_blend_files):
            selected = context.scene.cg_blend_files[props.blend_files_index]
            
            box = layout.box()
            box.label(text=selected.name, icon='FILE_BLEND')
            
            row = box.row(align=True)
            if selected.download_url:
                op = row.operator("cg_assistant.open_blend_file", text="Open in Blender", icon='IMPORT')
                op.file_url = selected.download_url
                op.file_name = selected.name
            
            if selected.thumbnail_url:
                op = row.operator("cg_assistant.open_in_browser", text="View Thumbnail", icon='IMAGE_DATA')
                op.url = selected.thumbnail_url
            
            if selected.file_path:
                row = box.row()
                op = row.operator("cg_assistant.copy_file_path", text="Copy Path", icon='COPYDOWN')
                op.path = selected.file_path


class CG_PT_ImagePanel(Panel):
    """Panel for image attachment - for visual similarity search."""
    bl_idname = "CG_PT_ImagePanel"
    bl_label = "Image for Query"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CG Assistant"
    bl_parent_id = "CG_PT_MainPanel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.cg_assistant.is_authenticated
    
    def draw_header(self, context):
        props = context.scene.cg_assistant
        if props.has_image_attached:
            self.layout.label(text="", icon='CHECKMARK')
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cg_assistant
        
        # Status
        if props.has_image_attached:
            box = layout.box()
            filename = os.path.basename(props.captured_image_path) if props.captured_image_path else "Image"
            box.label(text=f"Attached: {filename}", icon='IMAGE_DATA')
            box.operator("cg_assistant.clear_image", text="Clear Image", icon='X')
        else:
            layout.label(text="Attach an image for visual similarity search", icon='INFO')
        
        # Action buttons
        row = layout.row(align=True)
        row.operator("cg_assistant.upload_image", text="Upload Image", icon='FILEBROWSER')
        row.operator("cg_assistant.capture_viewport", text="Capture Viewport", icon='RESTRICT_RENDER_OFF')


# ============================================================================
# Registration
# ============================================================================

classes = [
    CG_UL_ChatHistory,
    CG_UL_Conversations,
    CG_UL_BlendFiles,
    CG_PT_MainPanel,
    CG_PT_AuthPanel,
    CG_PT_ConversationsPanel,
    CG_PT_ChatPanel,
    CG_PT_ImagePanel,
    CG_PT_BlendFilesPanel,
]


def register():
    """Register panel classes."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister panel classes."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

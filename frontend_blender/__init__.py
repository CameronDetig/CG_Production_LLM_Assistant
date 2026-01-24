"""
CG Production Assistant - Blender Addon
A chatbot interface for querying CG production asset metadata.
"""

bl_info = {
    "name": "CG Production Assistant",
    "author": "CG Production Team",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "location": "View3D > Sidebar > CG Assistant",
    "description": "AI-powered assistant for querying CG production asset metadata",
    "category": "3D View",
}

import bpy

from . import properties
from . import operators
from . import panels


# List of all classes to register
classes = []


def register():
    """Register all addon classes."""
    # Register properties first
    properties.register()
    
    # Register operators
    operators.register()
    
    # Register panels
    panels.register()
    
    print(f"CG Production Assistant v{'.'.join(map(str, bl_info['version']))} registered")


def unregister():
    """Unregister all addon classes."""
    # Unregister in reverse order
    panels.unregister()
    operators.unregister()
    properties.unregister()
    
    print("CG Production Assistant unregistered")


if __name__ == "__main__":
    register()

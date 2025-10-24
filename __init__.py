bl_info = {
    "name": "Sheetris",
    "author": "Beraldo Leal <bleal@redhat.com>",
    "version": (0, 0, 10),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Sheetris",
    "description": "Optimize cutting layouts for sheet materials (plywood, MDF, acrylic, etc.)",
    "category": "Object",
    "doc_url": "https://github.com/beraldoleal/sheetris",
    "tracker_url": "https://github.com/beraldoleal/sheetris/issues",
}

# Import modules
if "bpy" in locals():
    # Reload modules when reloading addon
    import importlib
    if "properties" in locals():
        importlib.reload(properties)
    if "operators" in locals():
        importlib.reload(operators)
    if "panels" in locals():
        importlib.reload(panels)
    if "packer" in locals():
        importlib.reload(packer)

import bpy

from . import properties
from . import operators
from . import panels


def register():
    properties.register()
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()

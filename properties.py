"""
Property groups for Sheetris addon.
"""

import bpy


class PlywoodDimensionItem(bpy.types.PropertyGroup):
    """Individual dimension entry"""
    letter: bpy.props.StringProperty(name="Letter")  # A, B, C, etc.
    dimension: bpy.props.StringProperty(name="Dimension")
    quantity: bpy.props.IntProperty(name="Quantity")
    object_names: bpy.props.StringProperty(name="Object Names")  # Comma-separated


class PlywoodSummaryItem(bpy.types.PropertyGroup):
    """Summary item for plywood pieces"""
    thickness: bpy.props.FloatProperty(name="Thickness (mm)")
    piece_count: bpy.props.IntProperty(name="Total Pieces")
    dimensions: bpy.props.CollectionProperty(type=PlywoodDimensionItem)
    show_details: bpy.props.BoolProperty(name="Show Details", default=False)


class PlywoodProperties(bpy.types.PropertyGroup):
    sheet_width: bpy.props.FloatProperty(
        name="Width",
        description="Plywood sheet width in mm",
        default=1220.0,
        min=100.0,
        max=10000.0
    )
    sheet_length: bpy.props.FloatProperty(
        name="Length",
        description="Plywood sheet length in mm",
        default=2440.0,
        min=100.0,
        max=10000.0
    )
    saw_kerf: bpy.props.FloatProperty(
        name="Saw Kerf",
        description="Saw blade width in mm (spacing between pieces)",
        default=3.0,
        min=0.0,
        max=50.0
    )
    color_mode: bpy.props.EnumProperty(
        name="Color By",
        description="How to color the pieces",
        items=[
            ('THICKNESS', "Thickness", "Color all pieces of same thickness with same color"),
            ('DIMENSION', "Dimension", "Color pieces with same dimensions with same color"),
        ],
        default='THICKNESS'
    )
    page_size: bpy.props.EnumProperty(
        name="Page Size",
        description="Paper size for printing reports",
        items=[
            ('A4', "A4 (210×297mm)", "A4 paper - standard in Europe"),
            ('A3', "A3 (297×420mm)", "A3 paper - larger format"),
            ('LETTER', "Letter (8.5×11\")", "Letter paper - standard in US"),
            ('TABLOID', "Tabloid (11×17\")", "Tabloid/Ledger - larger US format"),
        ],
        default='A4'
    )
    page_orientation: bpy.props.EnumProperty(
        name="Orientation",
        description="Page orientation for printing",
        items=[
            ('LANDSCAPE', "Landscape", "Horizontal orientation - better for sheets"),
            ('PORTRAIT', "Portrait", "Vertical orientation"),
        ],
        default='LANDSCAPE'
    )
    packing_algorithm: bpy.props.EnumProperty(
        name="Packing Algorithm",
        description="Choose the bin packing algorithm to use",
        items=[
            ('GUILLOTINE', "Guillotine", "Fast but may waste space - makes only straight cuts"),
            ('MAXRECTS', "MaxRects", "Better space efficiency - tries multiple positions"),
            ('SKYLINE', "Skyline", "Good balance of speed and efficiency - uses bottom-left placement"),
        ],
        default='MAXRECTS'
    )


# Registration
classes = (
    PlywoodDimensionItem,
    PlywoodSummaryItem,
    PlywoodProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.plywood_props = bpy.props.PointerProperty(type=PlywoodProperties)
    bpy.types.Scene.plywood_summary = bpy.props.CollectionProperty(type=PlywoodSummaryItem)


def unregister():
    del bpy.types.Scene.plywood_props
    del bpy.types.Scene.plywood_summary
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

"""
UI panels for Sheetris addon.
"""

import bpy


class PLYWOOD_PT_main_panel(bpy.types.Panel):
    """Sheetris Panel"""
    bl_label = "Sheetris"
    bl_idname = "PLYWOOD_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sheetris'

    def draw(self, context):
        layout = self.layout
        props = context.scene.plywood_props

        # Display version
        from . import bl_info
        version_str = ".".join(str(v) for v in bl_info["version"])
        layout.label(text=f"Sheetris v{version_str}", icon='INFO')
        layout.separator()

        layout.label(text="Sheet Dimensions (mm):")
        layout.prop(props, "sheet_width")
        layout.prop(props, "sheet_length")
        layout.prop(props, "saw_kerf")

        layout.separator()
        layout.label(text="Packing Settings:")
        layout.prop(props, "packing_algorithm")
        layout.prop(props, "color_mode")

        layout.separator()
        layout.label(text="Print Settings:")
        layout.prop(props, "page_size")
        layout.prop(props, "page_orientation")

        layout.separator()
        layout.operator("plywood.create_layout", icon='MOD_BUILD')
        layout.operator("plywood.clean_layouts", icon='TRASH')

        # Show print button if summary exists
        if context.scene.plywood_summary:
            layout.operator("plywood.print_report", icon='FILE_TEXT')

        # Display summary if available
        if context.scene.plywood_summary:
            layout.separator()
            layout.label(text="Summary:", icon='INFO')

            for item in context.scene.plywood_summary:
                box = layout.box()
                row = box.row()
                row.prop(item, "show_details",
                        icon='TRIA_DOWN' if item.show_details else 'TRIA_RIGHT',
                        text=f"{item.thickness:.0f}mm - {item.piece_count} pieces",
                        emboss=False)

                if item.show_details and item.dimensions:
                    # Table header
                    col = box.column(align=True)
                    header_row = col.row(align=True)
                    header_row.label(text="Label")
                    header_row.label(text="Dimension")
                    header_row.label(text="Qty")

                    col.separator(factor=0.3)

                    # Table rows
                    for dim_item in item.dimensions:
                        row = col.row(align=True)
                        # Show letter label
                        row.label(text=dim_item.letter)
                        # Make dimension clickable to select pieces
                        op = row.operator("plywood.select_pieces", text=dim_item.dimension, emboss=True)
                        op.object_names = dim_item.object_names
                        row.label(text=str(dim_item.quantity))


# Registration
classes = (
    PLYWOOD_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

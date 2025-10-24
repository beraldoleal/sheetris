"""
Operators for Sheetris addon.
"""

import bpy
import bmesh
import math
import os
import tempfile
import subprocess
from datetime import datetime
from mathutils import Vector
from collections import defaultdict

from .packer import GuillotinePacker


class PLYWOOD_OT_create_layout(bpy.types.Operator):
    """Create plywood sheet layout from selected objects"""
    bl_idname = "plywood.create_layout"
    bl_label = "Create Layout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.plywood_props

        # Get selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Check if any object has scale applied (not equal to 1)
        objects_with_scale = []
        for obj in selected_objects:
            scale = obj.scale
            if abs(scale.x - 1.0) > 0.0001 or abs(scale.y - 1.0) > 0.0001 or abs(scale.z - 1.0) > 0.0001:
                objects_with_scale.append(obj.name)

        if objects_with_scale:
            self.report({'ERROR'}, f"Objects have scale applied (must be 1,1,1): {', '.join(objects_with_scale)}")
            self.report({'ERROR'}, "Please apply scale (Ctrl+A > Scale) before running")
            return {'CANCELLED'}

        # Group objects by thickness and find bounding box of all objects
        thickness_groups = defaultdict(list)
        all_max_x = float('-inf')
        all_min_y = float('inf')

        for obj in selected_objects:
            # Get world-space bounding box dimensions
            bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            min_corner = Vector((min(v.x for v in bbox_corners),
                                min(v.y for v in bbox_corners),
                                min(v.z for v in bbox_corners)))
            max_corner = Vector((max(v.x for v in bbox_corners),
                                max(v.y for v in bbox_corners),
                                max(v.z for v in bbox_corners)))

            # Track overall bounding box
            all_max_x = max(all_max_x, max_corner.x)
            all_min_y = min(all_min_y, min_corner.y)

            dimensions = max_corner - min_corner
            thickness = min(dimensions.x, dimensions.y, dimensions.z)

            # Round to avoid floating point precision issues
            thickness_key = round(thickness, 6)
            thickness_groups[thickness_key].append(obj)

        # Create materials for color coding
        materials = {}
        colors = [
            (1.0, 0.3, 0.3, 1.0),  # Red
            (0.3, 1.0, 0.3, 1.0),  # Green
            (0.3, 0.3, 1.0, 1.0),  # Blue
            (1.0, 1.0, 0.3, 1.0),  # Yellow
            (1.0, 0.3, 1.0, 1.0),  # Magenta
            (0.3, 1.0, 1.0, 1.0),  # Cyan
            (1.0, 0.6, 0.3, 1.0),  # Orange
            (0.6, 0.3, 1.0, 1.0),  # Purple
        ]

        # Process each thickness group
        saw_kerf = props.saw_kerf / 1000.0  # Convert mm to Blender units (meters)
        sheet_width = props.sheet_width / 1000.0
        sheet_length = props.sheet_length / 1000.0

        # Start layout away from original objects (1 meter spacing)
        spacing = 1.0  # 1 meter gap
        global_x_offset = all_max_x + spacing if all_max_x != float('-inf') else 0

        for idx, (thickness, objects) in enumerate(sorted(thickness_groups.items())):
            # Create collection for this thickness
            collection_name = f"Plywood_{thickness*1000:.1f}mm"

            # Remove existing collection if it exists
            if collection_name in bpy.data.collections:
                old_collection = bpy.data.collections[collection_name]
                for obj in old_collection.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(old_collection)

            # Create new collection
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)

            # Materials will be created based on color mode
            thickness_material = None  # For THICKNESS mode
            dimension_materials = {}  # For DIMENSION mode

            if props.color_mode == 'THICKNESS':
                # Create single material for this thickness
                mat_name = f"Plywood_Mat_{thickness*1000:.1f}mm"
                if mat_name in bpy.data.materials:
                    thickness_material = bpy.data.materials[mat_name]
                else:
                    thickness_material = bpy.data.materials.new(name=mat_name)
                    thickness_material.use_nodes = True
                    thickness_material.diffuse_color = colors[idx % len(colors)]
                materials[thickness] = thickness_material

            # Build dimension-to-letter mapping for this thickness group
            dimension_to_letter = {}
            temp_dimension_groups = defaultdict(list)
            for obj in objects:
                # Calculate dimension key
                local_bbox = [Vector(corner) for corner in obj.bound_box]
                local_min = Vector((min(v.x for v in local_bbox),
                                   min(v.y for v in local_bbox),
                                   min(v.z for v in local_bbox)))
                local_max = Vector((max(v.x for v in local_bbox),
                                   max(v.y for v in local_bbox),
                                   max(v.z for v in local_bbox)))
                local_dims = local_max - local_min
                dims = sorted([local_dims.x * 1000, local_dims.y * 1000, local_dims.z * 1000])
                dim_key = f"{dims[1]:.0f}x{dims[2]:.0f}"
                temp_dimension_groups[dim_key].append(obj)

            # Assign letters
            letter_idx = 0
            for dim_key in sorted(temp_dimension_groups.keys()):
                dimension_to_letter[dim_key] = chr(65 + letter_idx)  # A, B, C, etc.
                letter_idx += 1

            # Prepare all pieces for this thickness group
            pieces_to_pack = []

            for obj in objects:
                # Duplicate object
                new_obj = obj.copy()
                new_obj.data = obj.data.copy()
                collection.objects.link(new_obj)

                # Center the origin to geometry (important for rotation!)
                # Calculate bounding box center in local space
                local_bbox = [Vector(corner) for corner in new_obj.bound_box]
                local_center = sum((Vector(b) for b in local_bbox), Vector()) / 8

                # Shift all vertices so center is at origin
                mesh = new_obj.data
                for vert in mesh.vertices:
                    vert.co -= local_center

                # Update mesh
                mesh.update()

                # Adjust object location to compensate
                world_offset = new_obj.matrix_world.to_3x3() @ local_center
                new_obj.location += world_offset

                # Get local bounding box dimensions (not world-space) - needed for both material and packing
                local_bbox = [Vector(corner) for corner in new_obj.bound_box]
                local_min = Vector((min(v.x for v in local_bbox),
                                   min(v.y for v in local_bbox),
                                   min(v.z for v in local_bbox)))
                local_max = Vector((max(v.x for v in local_bbox),
                                   max(v.y for v in local_bbox),
                                   max(v.z for v in local_bbox)))
                local_dims = local_max - local_min

                # Find which local axis is thickness (smallest dimension)
                dims_with_axis = [
                    (local_dims.x, 0, 'X'),  # X axis
                    (local_dims.y, 1, 'Y'),  # Y axis
                    (local_dims.z, 2, 'Z')   # Z axis
                ]
                dims_with_axis.sort()

                thickness_dim, thickness_idx, thickness_name = dims_with_axis[0]
                width_dim, width_idx, width_name = dims_with_axis[1]
                height_dim, height_idx, height_name = dims_with_axis[2]

                # Reset rotation and apply transformation to align thickness with Z
                new_obj.rotation_euler = (0, 0, 0)

                # Rotate object so thickness axis points up (Z)
                if thickness_idx == 0:  # X is thickness, rotate +90° around Y to make X -> +Z
                    new_obj.rotation_euler = (0, math.radians(90), 0)
                    # After rotation: local X -> world Z, local Y -> world Y, local Z -> world -X
                    piece_width = local_dims.z   # Z becomes width (X axis)
                    piece_height = local_dims.y  # Y stays height (Y axis)
                elif thickness_idx == 1:  # Y is thickness, rotate -90° around X to make Y -> +Z
                    new_obj.rotation_euler = (math.radians(-90), 0, 0)
                    # After rotation: local X -> world X, local Y -> world Z, local Z -> world -Y
                    piece_width = local_dims.x   # X stays width (X axis)
                    piece_height = local_dims.z  # Z becomes height (Y axis)
                else:  # Z is thickness (idx == 2), no rotation needed
                    # local X -> world X, local Y -> world Y, local Z -> world Z
                    piece_width = local_dims.x
                    piece_height = local_dims.y

                # Apply material based on color mode
                if props.color_mode == 'THICKNESS':
                    # Use single material for this thickness
                    mat = thickness_material
                else:  # DIMENSION mode
                    # Get dimension key
                    dims = sorted([local_dims.x * 1000, local_dims.y * 1000, local_dims.z * 1000])
                    dim_key = f"{dims[1]:.0f}x{dims[2]:.0f}"

                    # Create or get material for this dimension
                    if dim_key not in dimension_materials:
                        color_idx = len(dimension_materials)
                        mat_name = f"Plywood_Mat_{thickness*1000:.1f}mm_{dim_key}"
                        if mat_name in bpy.data.materials:
                            mat = bpy.data.materials[mat_name]
                        else:
                            mat = bpy.data.materials.new(name=mat_name)
                            mat.use_nodes = True
                            mat.diffuse_color = colors[color_idx % len(colors)]
                        dimension_materials[dim_key] = mat
                    else:
                        mat = dimension_materials[dim_key]

                # Apply material to object
                if new_obj.data.materials:
                    new_obj.data.materials[0] = mat
                else:
                    new_obj.data.materials.append(mat)

                # Get dimension key and letter for this piece
                dims = sorted([local_dims.x * 1000, local_dims.y * 1000, local_dims.z * 1000])
                dim_key = f"{dims[1]:.0f}x{dims[2]:.0f}"
                piece_letter = dimension_to_letter.get(dim_key, "?")

                # Store piece data for packing
                pieces_to_pack.append({
                    'original_obj': obj,
                    'new_obj': new_obj,
                    'width': piece_width,
                    'height': piece_height,
                    'thickness': thickness_dim,
                    'thickness_idx': thickness_idx,
                    'local_dims': local_dims,
                    'letter': piece_letter
                })

            # Sort pieces by area (largest first) for better packing
            pieces_to_pack.sort(key=lambda p: p['width'] * p['height'], reverse=True)

            # Pack pieces using Guillotine algorithm
            packer = GuillotinePacker(sheet_width, sheet_length, saw_kerf)

            for piece in pieces_to_pack:
                new_obj = piece['new_obj']
                piece_width = piece['width']
                piece_height = piece['height']
                thickness_dim = piece['thickness']

                # Pack the piece
                result = packer.pack_piece(piece, piece_width, piece_height)

                if result is None:
                    self.report({'ERROR'}, f"Piece too large to fit on sheet: {new_obj.name}")
                    continue

                sheet_index, x, y, placed_width, placed_height, rotated = result

                # If packer rotated the piece, we need to rotate it 90° around Z
                if rotated:
                    new_obj.rotation_euler.z += math.radians(90)

                # Position piece (offset by global_x_offset for this thickness group)
                # Add sheet_index offset in Y direction to separate pieces across multiple sheets
                piece_x = global_x_offset + x + placed_width/2
                piece_y = (sheet_index * sheet_length) + y + placed_height/2
                piece_z = thickness_dim/2
                new_obj.location = (piece_x, piece_y, piece_z)

                # Create text label for this piece
                text_data = bpy.data.curves.new(name=f"Label_{piece['letter']}", type='FONT')
                text_data.body = piece['letter']
                text_data.size = min(placed_width, placed_height) * 0.3  # 30% of smallest dimension
                text_data.align_x = 'CENTER'
                text_data.align_y = 'CENTER'

                text_obj = bpy.data.objects.new(name=f"Label_{new_obj.name}", object_data=text_data)
                collection.objects.link(text_obj)

                # Position text on top of the piece
                text_obj.location = (piece_x, piece_y, piece_z + thickness_dim)
                text_obj.rotation_euler = (0, 0, 0)  # Flat on XY plane, readable from above

            # Create reference planes for plywood sheets
            sheets_needed = len(packer.sheets)

            # Create sheet material (semi-transparent gray)
            sheet_mat_name = "Plywood_Sheet_Reference"
            if sheet_mat_name in bpy.data.materials:
                sheet_mat = bpy.data.materials[sheet_mat_name]
            else:
                sheet_mat = bpy.data.materials.new(name=sheet_mat_name)
                sheet_mat.use_nodes = True
                sheet_mat.diffuse_color = (0.5, 0.5, 0.5, 0.3)  # Gray, semi-transparent
                # Set blend mode to alpha blend
                sheet_mat.blend_method = 'BLEND'

            # Create plane for each sheet
            for sheet_idx in range(sheets_needed):
                sheet_y_pos = sheet_idx * sheet_length

                # Create plane mesh
                bm = bmesh.new()
                bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
                mesh_name = f"Sheet_{thickness*1000:.1f}mm_{sheet_idx+1}"
                mesh = bpy.data.meshes.new(mesh_name)
                bm.to_mesh(mesh)
                bm.free()

                # Create object
                sheet_obj = bpy.data.objects.new(mesh_name, mesh)
                collection.objects.link(sheet_obj)

                # Scale to sheet dimensions (plane is 2x2, so scale by half the dimension)
                sheet_obj.scale = (sheet_width/2, sheet_length/2, 1)
                # Position at sheet location (centered) - offset by global_x_offset
                sheet_obj.location = (global_x_offset + sheet_width/2, sheet_y_pos + sheet_length/2, -0.001)  # Slightly below pieces

                # Apply material
                sheet_obj.data.materials.append(sheet_mat)

            # Update global X offset for next thickness group (place next group to the right)
            global_x_offset += sheet_width + (saw_kerf * 10)  # Extra spacing between thickness groups

        # Build summary data for UI display
        context.scene.plywood_summary.clear()
        for thickness, objects in sorted(thickness_groups.items()):
            # Group pieces by dimensions
            dimension_groups = defaultdict(list)

            for obj in objects:
                # Get dimensions
                local_bbox = [Vector(corner) for corner in obj.bound_box]
                local_min = Vector((min(v.x for v in local_bbox),
                                   min(v.y for v in local_bbox),
                                   min(v.z for v in local_bbox)))
                local_max = Vector((max(v.x for v in local_bbox),
                                   max(v.y for v in local_bbox),
                                   max(v.z for v in local_bbox)))
                local_dims = local_max - local_min

                # Sort dimensions to get width x height (excluding thickness)
                dims = sorted([local_dims.x * 1000, local_dims.y * 1000, local_dims.z * 1000])
                width = dims[1]  # Second smallest
                height = dims[2]  # Largest

                dim_key = f"{width:.0f}x{height:.0f}"
                dimension_groups[dim_key].append(obj.name)

            # Add summary entry for this thickness
            summary_item = context.scene.plywood_summary.add()
            summary_item.thickness = thickness * 1000  # Convert to mm
            summary_item.piece_count = len(objects)

            # Add dimension entries with letter labels
            letter_idx = 0
            for dim_key, obj_names in sorted(dimension_groups.items()):
                dim_item = summary_item.dimensions.add()
                dim_item.letter = chr(65 + letter_idx)  # A=65, B=66, etc.
                dim_item.dimension = dim_key
                dim_item.quantity = len(obj_names)
                dim_item.object_names = ",".join(obj_names)
                letter_idx += 1

        self.report({'INFO'}, f"Created layout for {len(thickness_groups)} thickness groups")
        return {'FINISHED'}


class PLYWOOD_OT_select_pieces(bpy.types.Operator):
    """Select pieces with this dimension"""
    bl_idname = "plywood.select_pieces"
    bl_label = "Select Pieces"
    bl_options = {'REGISTER', 'UNDO'}

    object_names: bpy.props.StringProperty()

    def execute(self, context):
        # Deselect all
        bpy.ops.object.select_all(action='DESELECT')

        # Select specified objects
        obj_names = self.object_names.split(',')
        selected_count = 0

        for obj_name in obj_names:
            if obj_name in bpy.data.objects:
                obj = bpy.data.objects[obj_name]
                obj.select_set(True)
                selected_count += 1

        self.report({'INFO'}, f"Selected {selected_count} pieces")
        return {'FINISHED'}


class PLYWOOD_OT_print_report(bpy.types.Operator):
    """Generate PDF print report"""
    bl_idname = "plywood.print_report"
    bl_label = "Print Report"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4, A3, LETTER, TABLOID
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import Table, TableStyle
        except ImportError:
            self.report({'ERROR'}, "reportlab not installed. Run: pip install reportlab")
            return {'CANCELLED'}

        import os
        import tempfile
        import subprocess
        from datetime import datetime

        if not context.scene.plywood_summary:
            self.report({'WARNING'}, "No layout to print. Create a layout first.")
            return {'CANCELLED'}

        props = context.scene.plywood_props
        sheet_width_mm = props.sheet_width
        sheet_length_mm = props.sheet_length

        # Map page sizes
        page_size_map = {
            'A4': A4,
            'A3': A3,
            'LETTER': LETTER,
            'TABLOID': TABLOID,
        }

        page_size = page_size_map[props.page_size]

        # Swap if landscape
        if props.page_orientation == 'LANDSCAPE':
            page_size = (page_size[1], page_size[0])

        # Create PDF
        pdf_path = os.path.join(tempfile.gettempdir(), "plywood_layout_report.pdf")
        c = canvas.Canvas(pdf_path, pagesize=page_size)
        page_width, page_height = page_size

        # Margins
        margin = 15 * mm
        printable_width = page_width - (2 * margin)
        printable_height = page_height - (2 * margin)

        # Draw title page with summary
        y_pos = page_height - margin - 20
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin, y_pos, "Sheetris - Cutting Layout Report")

        y_pos -= 30
        c.setFont("Helvetica", 10)
        c.drawString(margin, y_pos, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        y_pos -= 15
        c.drawString(margin, y_pos, f"Sheet Size: {sheet_width_mm:.0f}mm × {sheet_length_mm:.0f}mm")
        y_pos -= 15
        c.drawString(margin, y_pos, f"Saw Kerf: {props.saw_kerf:.1f}mm")
        y_pos -= 30

        # Draw summary tables for each thickness
        for item in context.scene.plywood_summary:
            if y_pos < 150:  # Not enough space, new page
                c.showPage()
                y_pos = page_height - margin - 20

            # Thickness header
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y_pos, f"{item.thickness:.0f}mm Plywood - {item.piece_count} pieces")
            y_pos -= 20

            # Table data
            table_data = [['Label', 'Dimension (mm)', 'Quantity']]
            for dim_item in item.dimensions:
                table_data.append([dim_item.letter, dim_item.dimension, str(dim_item.quantity)])

            # Create table
            col_widths = [40, 150, 60]
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            table_width, table_height = table.wrap(0, 0)
            table.drawOn(c, margin, y_pos - table_height)
            y_pos -= table_height + 30

        # Now draw layout sheets for each thickness
        for item in context.scene.plywood_summary:
            collection_name = f"Plywood_{item.thickness:.1f}mm"
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]

                # Collect all pieces (non-text, non-sheet objects)
                pieces = []
                for obj in collection.all_objects:
                    if obj.type == 'MESH' and not obj.name.startswith('Label_') and not obj.name.startswith('Sheet_'):
                        # Get object position and dimensions in world space
                        loc = obj.location
                        bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

                        min_x = min(v.x for v in bbox)
                        max_x = max(v.x for v in bbox)
                        min_y = min(v.y for v in bbox)
                        max_y = max(v.y for v in bbox)

                        width = (max_x - min_x) * 1000  # Convert to mm
                        height = (max_y - min_y) * 1000
                        x = min_x * 1000
                        y = min_y * 1000

                        # Find the label for this piece
                        label = "?"
                        label_obj_name = f"Label_{obj.name}"
                        if label_obj_name in bpy.data.objects:
                            label_obj = bpy.data.objects[label_obj_name]
                            if hasattr(label_obj.data, 'body'):
                                label = label_obj.data.body

                        pieces.append({
                            'x': x,
                            'y': y,
                            'width': width,
                            'height': height,
                            'label': label
                        })

                # Draw PDF sheets
                if pieces:
                    # Calculate bounds
                    min_x = min(p['x'] for p in pieces)
                    min_y = min(p['y'] for p in pieces)
                    max_y = max(p['y'] + p['height'] for p in pieces)

                    # Adjust to start from 0
                    offset_x = min_x
                    offset_y = min_y

                    # Calculate number of sheets needed
                    total_height = max_y - min_y
                    num_sheets = int(total_height / sheet_length_mm) + 1

                    # Define colors for pieces
                    piece_colors = [
                        colors.Color(1, 0.6, 0.6),  # Light red
                        colors.Color(0.6, 1, 0.6),  # Light green
                        colors.Color(0.6, 0.6, 1),  # Light blue
                        colors.Color(1, 1, 0.6),    # Light yellow
                        colors.Color(1, 0.6, 1),    # Light magenta
                        colors.Color(0.6, 1, 1),    # Light cyan
                        colors.Color(1, 0.8, 0.6),  # Light orange
                        colors.Color(0.8, 0.6, 1),  # Light purple
                    ]

                    # Calculate scale to fit sheet on page (leave room for title)
                    title_space = 50
                    available_height = printable_height - title_space
                    scale_x = printable_width / (sheet_width_mm * mm)
                    scale_y = available_height / (sheet_length_mm * mm)
                    scale = min(scale_x, scale_y)

                    for sheet_idx in range(num_sheets):
                        c.showPage()  # New page for each sheet

                        sheet_min_y = sheet_idx * sheet_length_mm
                        sheet_max_y = (sheet_idx + 1) * sheet_length_mm

                        # Draw title
                        c.setFont("Helvetica-Bold", 16)
                        title_y = page_height - margin - 20
                        c.drawString(margin, title_y, f"Sheet {sheet_idx + 1} - {item.thickness:.0f}mm Plywood")

                        # Draw scale info
                        c.setFont("Helvetica", 10)
                        c.drawString(margin, title_y - 20, f"Scale: 1:{1/scale:.1f} | Actual sheet: {sheet_width_mm:.0f}×{sheet_length_mm:.0f}mm")

                        # Calculate drawing area (centered)
                        draw_width = sheet_width_mm * mm * scale
                        draw_height = sheet_length_mm * mm * scale
                        draw_x = margin + (printable_width - draw_width) / 2
                        draw_y = margin + (available_height - draw_height) / 2

                        # Draw sheet border
                        c.setStrokeColor(colors.black)
                        c.setLineWidth(2)
                        c.rect(draw_x, draw_y, draw_width, draw_height, stroke=1, fill=0)

                        # Draw grid (every 100mm)
                        c.setStrokeColor(colors.Color(0.9, 0.9, 0.9))
                        c.setLineWidth(0.5)
                        for x in range(0, int(sheet_width_mm), 100):
                            grid_x = draw_x + (x * mm * scale)
                            c.line(grid_x, draw_y, grid_x, draw_y + draw_height)
                        for y in range(0, int(sheet_length_mm), 100):
                            grid_y = draw_y + (y * mm * scale)
                            c.line(draw_x, grid_y, draw_x + draw_width, grid_y)

                        # Draw pieces
                        for piece in pieces:
                            piece_y_start = piece['y'] - offset_y
                            piece_y_end = piece_y_start + piece['height']

                            # Check if piece is on this sheet
                            if piece_y_start < sheet_max_y and piece_y_end > sheet_min_y:
                                px = piece['x'] - offset_x
                                py = piece_y_start - sheet_min_y

                                # Convert to PDF coordinates
                                rect_x = draw_x + (px * mm * scale)
                                rect_y = draw_y + (py * mm * scale)
                                rect_w = piece['width'] * mm * scale
                                rect_h = piece['height'] * mm * scale

                                # Choose color based on label
                                color_idx = ord(piece['label'][0]) % len(piece_colors) if piece['label'] else 0
                                c.setFillColor(piece_colors[color_idx])
                                c.setStrokeColor(colors.black)
                                c.setLineWidth(1)
                                c.rect(rect_x, rect_y, rect_w, rect_h, stroke=1, fill=1)

                                # Draw label
                                c.setFillColor(colors.black)
                                font_size = min(piece['width'], piece['height']) * 0.25 * scale
                                c.setFont("Helvetica-Bold", max(font_size, 8))
                                label_x = rect_x + rect_w / 2
                                label_y = rect_y + rect_h / 2
                                c.drawCentredString(label_x, label_y + 5, piece['label'])

                                # Draw dimensions
                                dim_text = f"{piece['width']:.0f}×{piece['height']:.0f}"
                                c.setFont("Helvetica", max(font_size * 0.6, 6))
                                c.drawCentredString(label_x, label_y - font_size, dim_text)

        # Save PDF
        c.save()

        # Open the PDF - cross-platform
        import platform

        if platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', pdf_path])
        elif platform.system() == 'Windows':
            os.startfile(pdf_path)
        else:  # Linux
            subprocess.Popen(['xdg-open', pdf_path])

        self.report({'INFO'}, f"PDF saved: {pdf_path}")
        return {'FINISHED'}


class PLYWOOD_OT_clean_layouts(bpy.types.Operator):
    """Remove all plywood layout collections and objects"""
    bl_idname = "plywood.clean_layouts"
    bl_label = "Clean All Layouts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Find all collections that start with "Plywood_"
        collections_to_remove = []
        for collection in bpy.data.collections:
            if collection.name.startswith("Plywood_"):
                collections_to_remove.append(collection)

        if not collections_to_remove:
            self.report({'INFO'}, "No plywood layouts to clean")
            return {'FINISHED'}

        # Remove objects and collections
        for collection in collections_to_remove:
            # Remove all objects in the collection
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)

            # Remove the collection
            bpy.data.collections.remove(collection)

        # Clean up materials
        materials_to_remove = []
        for mat in bpy.data.materials:
            if mat.name.startswith("Plywood_Mat_") or mat.name == "Plywood_Sheet_Reference":
                materials_to_remove.append(mat)

        for mat in materials_to_remove:
            bpy.data.materials.remove(mat)

        # Clear summary
        context.scene.plywood_summary.clear()

        self.report({'INFO'}, f"Removed {len(collections_to_remove)} plywood layout collections")
        return {'FINISHED'}




# Registration
classes = (
    PLYWOOD_OT_create_layout,
    PLYWOOD_OT_select_pieces,
    PLYWOOD_OT_print_report,
    PLYWOOD_OT_clean_layouts,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

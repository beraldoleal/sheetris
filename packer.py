"""
Multiple bin packing algorithms for optimizing sheet material layouts.
Supports Guillotine, MaxRects, and Skyline algorithms.
"""


class FreeRectangle:
    """Represents a free rectangle in the sheet"""
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class GuillotinePacker:
    """Guillotine bin packing algorithm for 2D rectangle packing"""

    def __init__(self, sheet_width, sheet_height, saw_kerf=0):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.saw_kerf = saw_kerf
        self.sheets = []  # List of sheets, each sheet has free rectangles and placed pieces
        self.current_sheet = None
        self._start_new_sheet()

    def _start_new_sheet(self):
        """Start a new sheet"""
        self.current_sheet = {
            'free_rects': [FreeRectangle(0, 0, self.sheet_width, self.sheet_height)],
            'placed_pieces': []  # [(piece_data, x, y, width, height, rotated)]
        }
        self.sheets.append(self.current_sheet)

    def _find_best_free_rect(self, piece_width, piece_height):
        """Find best free rectangle for this piece. Returns (rect, rotated, score)"""
        best_rect = None
        best_rotated = False
        best_score = float('inf')

        for rect in self.current_sheet['free_rects']:
            # Try normal orientation
            if rect.width >= piece_width and rect.height >= piece_height:
                # Use "Best Short Side Fit" heuristic
                leftover_x = rect.width - piece_width
                leftover_y = rect.height - piece_height
                score = min(leftover_x, leftover_y)

                if score < best_score:
                    best_score = score
                    best_rect = rect
                    best_rotated = False

            # Try rotated orientation (90 degrees)
            if rect.width >= piece_height and rect.height >= piece_width:
                leftover_x = rect.width - piece_height
                leftover_y = rect.height - piece_width
                score = min(leftover_x, leftover_y)

                if score < best_score:
                    best_score = score
                    best_rect = rect
                    best_rotated = True

        return best_rect, best_rotated

    def _split_free_rect(self, rect, piece_x, piece_y, piece_width, piece_height):
        """Split a free rectangle after placing a piece using guillotine cuts"""
        new_rects = []

        # Calculate leftover space
        leftover_x = rect.width - piece_width
        leftover_y = rect.height - piece_height

        # Choose split direction based on which leftover is larger
        # This creates a single guillotine cut, preventing overlaps
        if leftover_x > leftover_y:
            # Horizontal split - piece on left, free space on right
            # Right rectangle (full height)
            if leftover_x > self.saw_kerf:
                new_rects.append(FreeRectangle(
                    piece_x + piece_width + self.saw_kerf,
                    rect.y,
                    leftover_x - self.saw_kerf,
                    rect.height
                ))
            # Top rectangle (only above piece, not extending into right area)
            if leftover_y > self.saw_kerf:
                new_rects.append(FreeRectangle(
                    rect.x,
                    piece_y + piece_height + self.saw_kerf,
                    piece_width,
                    leftover_y - self.saw_kerf
                ))
        else:
            # Vertical split - piece on bottom, free space on top
            # Top rectangle (full width)
            if leftover_y > self.saw_kerf:
                new_rects.append(FreeRectangle(
                    rect.x,
                    piece_y + piece_height + self.saw_kerf,
                    rect.width,
                    leftover_y - self.saw_kerf
                ))
            # Right rectangle (only beside piece, not extending into top area)
            if leftover_x > self.saw_kerf:
                new_rects.append(FreeRectangle(
                    piece_x + piece_width + self.saw_kerf,
                    rect.y,
                    leftover_x - self.saw_kerf,
                    piece_height
                ))

        return new_rects

    def pack_piece(self, piece_data, piece_width, piece_height):
        """
        Try to pack a piece. Returns (sheet_index, x, y, placed_width, placed_height, rotated)
        If can't fit in current sheet, starts a new one.
        """
        # Try to find space in current sheet
        best_rect, rotated = self._find_best_free_rect(piece_width, piece_height)

        # If doesn't fit, start new sheet
        if best_rect is None:
            self._start_new_sheet()
            best_rect, rotated = self._find_best_free_rect(piece_width, piece_height)

            # If still doesn't fit (piece larger than sheet!), return None
            if best_rect is None:
                return None

        # Determine final dimensions based on rotation
        if rotated:
            final_width = piece_height
            final_height = piece_width
        else:
            final_width = piece_width
            final_height = piece_height

        # Place piece at the rectangle position
        piece_x = best_rect.x
        piece_y = best_rect.y

        # Record placement
        sheet_index = len(self.sheets) - 1
        self.current_sheet['placed_pieces'].append(
            (piece_data, piece_x, piece_y, final_width, final_height, rotated)
        )

        # Remove used rectangle and add split rectangles
        self.current_sheet['free_rects'].remove(best_rect)
        new_rects = self._split_free_rect(best_rect, piece_x, piece_y, final_width, final_height)
        self.current_sheet['free_rects'].extend(new_rects)

        return (sheet_index, piece_x, piece_y, final_width, final_height, rotated)


class MaxRectsPacker:
    """
    MaxRects bin packing algorithm - better space utilization than Guillotine.
    Uses the "Best Short Side Fit" heuristic and maintains multiple free rectangles.
    """

    def __init__(self, sheet_width, sheet_height, saw_kerf=0):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.saw_kerf = saw_kerf
        self.sheets = []
        self.current_sheet = None
        self._start_new_sheet()

    def _start_new_sheet(self):
        """Start a new sheet"""
        self.current_sheet = {
            'free_rects': [FreeRectangle(0, 0, self.sheet_width, self.sheet_height)],
            'placed_pieces': []
        }
        self.sheets.append(self.current_sheet)

    def _is_contained_in(self, rect_a, rect_b):
        """Check if rect_a is fully contained in rect_b"""
        return (rect_a.x >= rect_b.x and rect_a.y >= rect_b.y and
                rect_a.x + rect_a.width <= rect_b.x + rect_b.width and
                rect_a.y + rect_a.height <= rect_b.y + rect_b.height)

    def _find_best_free_rect(self, piece_width, piece_height):
        """Find best free rectangle using Best Short Side Fit heuristic"""
        best_rect = None
        best_rotated = False
        best_score = float('inf')
        best_score_secondary = float('inf')

        for rect in self.current_sheet['free_rects']:
            # Try normal orientation
            if rect.width >= piece_width and rect.height >= piece_height:
                leftover_x = rect.width - piece_width
                leftover_y = rect.height - piece_height
                short_side = min(leftover_x, leftover_y)
                long_side = max(leftover_x, leftover_y)

                if short_side < best_score or (short_side == best_score and long_side < best_score_secondary):
                    best_score = short_side
                    best_score_secondary = long_side
                    best_rect = rect
                    best_rotated = False

            # Try rotated orientation
            if rect.width >= piece_height and rect.height >= piece_width:
                leftover_x = rect.width - piece_height
                leftover_y = rect.height - piece_width
                short_side = min(leftover_x, leftover_y)
                long_side = max(leftover_x, leftover_y)

                if short_side < best_score or (short_side == best_score and long_side < best_score_secondary):
                    best_score = short_side
                    best_score_secondary = long_side
                    best_rect = rect
                    best_rotated = True

        return best_rect, best_rotated

    def _split_free_rect(self, used_rect, piece_x, piece_y, piece_width, piece_height):
        """Split free rectangles after placing a piece - MaxRects style"""
        new_rects = []

        for rect in self.current_sheet['free_rects'][:]:  # Iterate over copy
            # If this rect intersects with the placed piece
            if not (piece_x >= rect.x + rect.width or
                    piece_x + piece_width <= rect.x or
                    piece_y >= rect.y + rect.height or
                    piece_y + piece_height <= rect.y):

                # Create new rectangles from the splits
                # Left side
                if piece_x > rect.x:
                    new_rects.append(FreeRectangle(
                        rect.x,
                        rect.y,
                        piece_x - rect.x,
                        rect.height
                    ))

                # Right side
                if piece_x + piece_width + self.saw_kerf < rect.x + rect.width:
                    new_rects.append(FreeRectangle(
                        piece_x + piece_width + self.saw_kerf,
                        rect.y,
                        rect.x + rect.width - (piece_x + piece_width + self.saw_kerf),
                        rect.height
                    ))

                # Bottom side
                if piece_y > rect.y:
                    new_rects.append(FreeRectangle(
                        rect.x,
                        rect.y,
                        rect.width,
                        piece_y - rect.y
                    ))

                # Top side
                if piece_y + piece_height + self.saw_kerf < rect.y + rect.height:
                    new_rects.append(FreeRectangle(
                        rect.x,
                        piece_y + piece_height + self.saw_kerf,
                        rect.width,
                        rect.y + rect.height - (piece_y + piece_height + self.saw_kerf)
                    ))

        # Remove rectangles that are contained in other rectangles
        self.current_sheet['free_rects'] = []
        for rect in new_rects:
            is_contained = False
            for other in new_rects:
                if rect != other and self._is_contained_in(rect, other):
                    is_contained = True
                    break
            if not is_contained and rect.width > 0 and rect.height > 0:
                self.current_sheet['free_rects'].append(rect)

    def pack_piece(self, piece_data, piece_width, piece_height):
        """Try to pack a piece"""
        best_rect, rotated = self._find_best_free_rect(piece_width, piece_height)

        if best_rect is None:
            self._start_new_sheet()
            best_rect, rotated = self._find_best_free_rect(piece_width, piece_height)

            if best_rect is None:
                return None

        if rotated:
            final_width = piece_height
            final_height = piece_width
        else:
            final_width = piece_width
            final_height = piece_height

        piece_x = best_rect.x
        piece_y = best_rect.y

        sheet_index = len(self.sheets) - 1
        self.current_sheet['placed_pieces'].append(
            (piece_data, piece_x, piece_y, final_width, final_height, rotated)
        )

        self._split_free_rect(best_rect, piece_x, piece_y, final_width, final_height)

        return (sheet_index, piece_x, piece_y, final_width, final_height, rotated)


class SkylinePacker:
    """
    Skyline bin packing algorithm - maintains a skyline of the bottom edge.
    Good balance between speed and efficiency.
    """

    class SkylineNode:
        def __init__(self, x, y, width):
            self.x = x
            self.y = y
            self.width = width

    def __init__(self, sheet_width, sheet_height, saw_kerf=0):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.saw_kerf = saw_kerf
        self.sheets = []
        self.current_sheet = None
        self._start_new_sheet()

    def _start_new_sheet(self):
        """Start a new sheet"""
        self.current_sheet = {
            'skyline': [self.SkylineNode(0, 0, self.sheet_width)],
            'placed_pieces': []
        }
        self.sheets.append(self.current_sheet)

    def _find_best_position(self, piece_width, piece_height):
        """Find best position along the skyline using Bottom-Left heuristic"""
        best_y = float('inf')
        best_x = 0
        best_index = -1
        best_rotated = False

        # Try normal orientation
        for i, node in enumerate(self.current_sheet['skyline']):
            y, can_fit, width_left = self._calculate_fit(i, piece_width, piece_height)
            if can_fit and y < best_y:
                best_y = y
                best_x = node.x
                best_index = i
                best_rotated = False

        # Try rotated orientation
        for i, node in enumerate(self.current_sheet['skyline']):
            y, can_fit, width_left = self._calculate_fit(i, piece_height, piece_width)
            if can_fit and y < best_y:
                best_y = y
                best_x = node.x
                best_index = i
                best_rotated = True

        if best_index == -1:
            return -1, 0, 0, False

        return best_index, best_x, best_y, best_rotated

    def _calculate_fit(self, index, width, height):
        """Calculate if piece fits at given skyline index"""
        x = self.current_sheet['skyline'][index].x
        if x + width > self.sheet_width:
            return 0, False, 0

        y = 0
        width_left = width
        i = index

        # Find the maximum y along the width of the piece
        while width_left > 0 and i < len(self.current_sheet['skyline']):
            node = self.current_sheet['skyline'][i]
            y = max(y, node.y)

            if y + height > self.sheet_height:
                return 0, False, 0

            width_left -= node.width
            i += 1

        return y, True, width_left

    def _add_skyline_level(self, index, x, y, width, height):
        """Add a new level to the skyline after placing a piece"""
        new_node = self.SkylineNode(x, y + height + self.saw_kerf, width)

        # Insert the new node
        self.current_sheet['skyline'].insert(index, new_node)

        # Merge any nodes at the same level
        i = index + 1
        while i < len(self.current_sheet['skyline']):
            curr = self.current_sheet['skyline'][i]
            prev = self.current_sheet['skyline'][i - 1]

            if curr.x < prev.x + prev.width:
                shrink = prev.x + prev.width - curr.x
                curr.x += shrink
                curr.width -= shrink

                if curr.width <= 0:
                    self.current_sheet['skyline'].pop(i)
                    continue
                else:
                    break
            else:
                break

            i += 1

        # Merge nodes at the same height
        i = 0
        while i < len(self.current_sheet['skyline']) - 1:
            curr = self.current_sheet['skyline'][i]
            next_node = self.current_sheet['skyline'][i + 1]

            if curr.y == next_node.y:
                curr.width += next_node.width
                self.current_sheet['skyline'].pop(i + 1)
            else:
                i += 1

    def pack_piece(self, piece_data, piece_width, piece_height):
        """Try to pack a piece"""
        index, x, y, rotated = self._find_best_position(piece_width, piece_height)

        if index == -1:
            self._start_new_sheet()
            index, x, y, rotated = self._find_best_position(piece_width, piece_height)

            if index == -1:
                return None

        if rotated:
            final_width = piece_height
            final_height = piece_width
        else:
            final_width = piece_width
            final_height = piece_height

        sheet_index = len(self.sheets) - 1
        self.current_sheet['placed_pieces'].append(
            (piece_data, x, y, final_width, final_height, rotated)
        )

        self._add_skyline_level(index, x, y, final_width, final_height)

        return (sheet_index, x, y, final_width, final_height, rotated)

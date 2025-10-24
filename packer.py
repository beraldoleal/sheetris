"""
Guillotine bin packing algorithm for optimizing sheet material layouts.
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

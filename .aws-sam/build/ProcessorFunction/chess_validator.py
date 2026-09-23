from dataclasses import dataclass

FILES = "abcdefgh"
RANKS = "12345678"

class ChessValidationError(Exception):
    pass

@dataclass
class Piece:
    color: str
    kind: str

def initial_board():
    board = {}
    for f in FILES:
        board[f"{f}2"] = Piece("white", "P")
        board[f"{f}7"] = Piece("black", "P")
    board.update({
        "a1": Piece("white", "R"), "b1": Piece("white", "N"),
        "c1": Piece("white", "B"), "d1": Piece("white", "Q"),
        "e1": Piece("white", "K"), "f1": Piece("white", "B"),
        "g1": Piece("white", "N"), "h1": Piece("white", "R"),
        "a8": Piece("black", "R"), "b8": Piece("black", "N"),
        "c8": Piece("black", "B"), "d8": Piece("black", "Q"),
        "e8": Piece("black", "K"), "f8": Piece("black", "B"),
        "g8": Piece("black", "N"), "h8": Piece("black", "R"),
    })
    return board

def square_to_xy(s):
    return FILES.index(s[0]), RANKS.index(s[1])

def xy_to_square(x, y):
    return FILES[x] + RANKS[y]

def valid_square(s):
    return isinstance(s, str) and len(s) == 2 and s[0] in FILES and s[1] in RANKS

def path_clear(board, start, end):
    sx, sy = square_to_xy(start)
    ex, ey = square_to_xy(end)
    dx, dy = ex - sx, ey - sy
    stepx = 0 if dx == 0 else (1 if dx > 0 else -1)
    stepy = 0 if dy == 0 else (1 if dy > 0 else -1)
    x, y = sx + stepx, sy + stepy
    while (x, y) != (ex, ey):
        if xy_to_square(x, y) in board:
            return False
        x += stepx
        y += stepy
    return True

def piece_attacks_square(board, source, target):
    piece = board[source]
    sx, sy = square_to_xy(source)
    tx, ty = square_to_xy(target)
    dx, dy = tx - sx, ty - sy
    adx, ady = abs(dx), abs(dy)
    
    if piece.kind == "P":
        direction = 1 if piece.color == "white" else -1
        return adx == 1 and dy == direction
    if piece.kind == "N":
        return (adx, ady) in ((1, 2), (2, 1))
    if piece.kind == "K":
        return max(adx, ady) == 1
    if piece.kind == "R":
        return (dx == 0 or dy == 0) and path_clear(board, source, target)
    if piece.kind == "B":
        return adx == ady and path_clear(board, source, target)
    if piece.kind == "Q":
        return (dx == 0 or dy == 0 or adx == ady) and path_clear(board, source, target)
    return False

def square_attacked_by(board, target, color):
    return any(
        piece.color == color and piece_attacks_square(board, source, target)
        for source, piece in board.items()
    )

def king_square(board, color):
    for square, piece in board.items():
        if piece.color == color and piece.kind == "K":
            return square
    raise ChessValidationError(f"{color.capitalize()} king is missing.")

def in_check(board, color):
    attacker = "black" if color == "white" else "white"
    return square_attacked_by(board, king_square(board, color), attacker)

def pseudo_legal_move(board, start, end, color):
    if start not in board:
        return False, "No piece exists on the starting square."
    piece = board[start]
    if piece.color != color:
        return False, "It is not this player's piece."
    target = board.get(end)
    if target and target.color == color:
        return False, "Destination square contains a friendly piece."
        
    sx, sy = square_to_xy(start)
    ex, ey = square_to_xy(end)
    dx, dy = ex - sx, ey - sy
    adx, ady = abs(dx), abs(dy)
    
    if piece.kind == "P":
        direction = 1 if color == "white" else -1
        start_rank = 1 if color == "white" else 6
        if dx == 0 and dy == direction and end not in board:
            return True, ""
        if dx == 0 and sy == start_rank and dy == 2 * direction and end not in board:
            if xy_to_square(sx, sy + direction) not in board:
                return True, ""
        if adx == 1 and dy == direction and target and target.color != color:
            return True, ""
        return False, "Illegal pawn movement."
        
    if piece.kind == "N":
        ok = (adx, ady) in ((1, 2), (2, 1))
        return ok, "" if ok else "Illegal knight movement."
    if piece.kind == "B":
        ok = adx == ady and path_clear(board, start, end)
        return ok, "" if ok else "Illegal bishop movement."
    if piece.kind == "R":
        ok = (dx == 0 or dy == 0) and path_clear(board, start, end)
        return ok, "" if ok else "Illegal rook movement."
    if piece.kind == "Q":
        ok = (dx == 0 or dy == 0 or adx == ady) and path_clear(board, start, end)
        return ok, "" if ok else "Illegal queen movement."
    if piece.kind == "K":
        ok = max(adx, ady) == 1
        return ok, "" if ok else "Illegal king movement."
    return False, "Unknown chess piece."

def apply_move(board, start, end):
    new = board.copy()
    piece = new.pop(start)
    new[end] = piece
    return new

def legal_moves_for_color(board, color):
    moves = []
    for start, piece in board.items():
        if piece.color != color:
            continue
        for f in FILES:
            for r in RANKS:
                end = f + r
                if start == end:
                    continue
                legal, _ = pseudo_legal_move(board, start, end, color)
                if not legal:
                    continue
                candidate = apply_move(board, start, end)
                try:
                    if not in_check(candidate, color):
                        moves.append((start, end))
                except ChessValidationError:
                    pass
    return moves

def validate_game(lines):
    board = initial_board()
    moves = 0
    current_color = "white"
    
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ChessValidationError(
                f"Line {line_no}: expected 'start end', for example 'e2 e4'."
            )
        start, end = parts
        if not valid_square(start):
            raise ChessValidationError(f"Line {line_no}: invalid start square '{start}'.")
        if not valid_square(end):
            raise ChessValidationError(f"Line {line_no}: invalid destination square '{end}'.")
        if start == end:
            raise ChessValidationError(f"Line {line_no}: start and destination squares are identical.")
        if start not in board:
            raise ChessValidationError(f"Line {line_no}: no piece on {start}.")
            
        piece = board[start]
        if piece.color != current_color:
            raise ChessValidationError(f"Line {line_no}: it is {current_color}'s turn.")
            
        legal, reason = pseudo_legal_move(board, start, end, current_color)
        if not legal:
            raise ChessValidationError(f"Line {line_no}: {start} {end} is invalid. {reason}")
            
        candidate = apply_move(board, start, end)
        if in_check(candidate, current_color):
            raise ChessValidationError(
                f"Line {line_no}: move {start} {end} leaves the {current_color} king in check."
            )
            
        board = candidate
        moves += 1
        opponent = "black" if current_color == "white" else "white"
        
        if in_check(board, opponent) and not legal_moves_for_color(board, opponent):
            return {
                "valid": True,
                "winner": current_color,
                "moves": moves,
                "board": board,
                "checkmate": True,
            }
        current_color = opponent
        
    if moves == 0:
        raise ChessValidationError("The chess file does not contain any moves.")
        
    return {
        "valid": True,
        "winner": "draw",
        "moves": moves,
        "board": board,
        "checkmate": False,
    }


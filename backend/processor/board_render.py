from PIL import Image, ImageDraw, ImageFont
FILES = "abcdefgh"
RANKS = "87654321"
PIECE_LETTERS = {
"K": "K",
"Q": "Q",
"R": "R",
"B": "B",
"N": "N",
"P": "P",
}
def load_font(size):
candidates = [
"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
"/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]
for path in candidates:
try:
return ImageFont.truetype(path, size)
except OSError:
pass
return ImageFont.load_default()
def render_board(board, output_path):
square = 90
margin = 45
board_size = square * 8
image = Image.new(
"RGB",
(board_size + margin * 2, board_size + margin * 2),
(35, 35, 35),
)
draw = ImageDraw.Draw(image)
light = (240, 217, 181)
dark = (181, 136, 99)
piece_font = load_font(48)
label_font = load_font(18)
for row, rank in enumerate(RANKS):
for col, file_name in enumerate(FILES):
x0 = margin + col * square
y0 = margin + row * square
x1 = x0 + square
y1 = y0 + square
fill = light if (row + col) % 2 == 0 else dark
draw.rectangle([x0, y0, x1, y1], fill=fill)
sq = file_name + rank
piece = board.get(sq)
if piece:
symbol = PIECE_LETTERS[piece.kind]
if piece.color == "black":
symbol = symbol.lower()
bbox = draw.textbbox((0, 0), symbol, font=piece_font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
draw.text(
(x0 + (square - tw) / 2,
y0 + (square - th) / 2 - 4),
symbol,
font=piece_font,
fill=(250, 250, 250) if piece.color == "white" else (20, 20, 20),
stroke_width=2,
stroke_fill=(20, 20, 20) if piece.color == "white" else (250, 250, 250),
)
for col, file_name in enumerate(FILES):
draw.text(
(margin + col * square + square / 2, margin + board_size + 8),
file_name,
font=label_font,
fill=(250, 250, 250),
anchor="ma",
)
for row, rank in enumerate(RANKS):
draw.text(
(margin - 14, margin + row * square + square / 2),
rank,
font=label_font,
fill=(250, 250, 250),
anchor="mm",
)
image.save(output_path, "PNG", optimize=True)
return output_path

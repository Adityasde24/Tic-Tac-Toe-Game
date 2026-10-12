import os
import re
import random
import streamlit as st

try:
    from groq import Groq
except Exception:
    Groq = None

MODEL_NAME = "openai/gpt-oss-120b"

st.set_page_config(page_title="Tic Tac Toe", page_icon="⭕", layout="centered")

# Keep the 3x3 grid in three columns even on a phone (Streamlit stacks columns by default)
st.markdown(
    """
    <style>
    div[data-testid="stHorizontalBlock"] {flex-direction: row !important; flex-wrap: nowrap !important;}
    div[data-testid="stColumn"], div[data-testid="column"] {min-width: 0 !important; flex: 1 1 0 !important; width: auto !important;}
    div.stButton > button {height: 4.5rem; font-size: 2rem; font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)


# =====================================================
# Groq client (key comes from Streamlit secrets or an environment variable)
# Without a key the AI strategy falls back to the rule-based one.
# =====================================================
@st.cache_resource
def get_client():
    if Groq is None:
        return None
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        try:
            key = st.secrets["GROQ_API_KEY"]
        except Exception:
            key = None
    if not key:
        return None
    try:
        return Groq(api_key=key)
    except Exception:
        return None


# =====================================================
# GAME LOGIC
# =====================================================
WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def check_winner(board):
    for a, b, c in WIN_LINES:
        if board[a] != "" and board[a] == board[b] == board[c]:
            return board[a]
    if "" not in board:
        return "Draw"
    return None


def available_moves(board):
    return [i for i, cell in enumerate(board) if cell == ""]


def other_player(symbol):
    return "O" if symbol == "X" else "X"


def random_move(board):
    return random.choice(available_moves(board))


def find_winning_move(board, player):
    for move in available_moves(board):
        trial = board[:]
        trial[move] = player
        if check_winner(trial) == player:
            return move
    return None


def rule_based_move(board, me):
    opponent = other_player(me)
    move = find_winning_move(board, me)
    if move is not None:
        return move
    move = find_winning_move(board, opponent)
    if move is not None:
        return move
    if board[4] == "":
        return 4
    for group in ([0, 2, 6, 8], [1, 3, 5, 7]):
        options = [c for c in group if board[c] == ""]
        if options:
            return random.choice(options)


def make_system_prompt(me):
    opponent = other_player(me)
    return (
        f"You are an expert Tic-Tac-Toe player. You play as {me} against {opponent}. "
        "Choose your move using this priority order: "
        "1) If you can win this turn, take the winning cell. "
        f"2) Otherwise, if {opponent} can win next turn, block that cell. "
        "3) Otherwise take the centre (cell 4), then a corner (0, 2, 6, 8), then a side (1, 3, 5, 7). "
        "Reply with ONLY the single digit of the cell you choose and nothing else."
    )


def board_to_text(board):
    cells = [board[i] if board[i] != "" else str(i) for i in range(9)]
    rows = [" | ".join(cells[r:r + 3]) for r in (0, 3, 6)]
    return "\n---------\n".join(rows)


def ai_move(board, me):
    available = available_moves(board)
    client = get_client()
    if client is None:
        st.session_state.note = "AI key not set, so the rule-based strategy was used."
        return rule_based_move(board, me)

    user_prompt = (
        f"Current board (numbers are empty cells):\n{board_to_text(board)}\n\n"
        f"Available cells: {available}\n"
        f"You are {me}. Which cell do you play?"
    )
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": make_system_prompt(me)},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL_NAME,
            temperature=0.2,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content or ""
        match = re.search(r"\d", reply)
        if match and int(match.group()) in available:
            return int(match.group())
        st.session_state.note = "AI gave an invalid move, so the rule-based strategy was used."
    except Exception:
        st.session_state.note = "AI call failed, so the rule-based strategy was used."
    return rule_based_move(board, me)


def pick_computer_move(board, strategy, me):
    if strategy == "Random":
        return random_move(board)
    if strategy == "Rule-based":
        return rule_based_move(board, me)
    return ai_move(board, me)


# =====================================================
# APP STATE AND ACTIONS
# =====================================================
ss = st.session_state
ss.setdefault("board", [""] * 9)
ss.setdefault("cur", "X")
ss.setdefault("over", False)
ss.setdefault("scores", {"X": 0, "O": 0, "Draw": 0})
ss.setdefault("note", "")

MODES = ["Vs Computer", "Two Player"]
STRATEGIES = ["Random", "Rule-based", "AI (Groq)"]
SYMBOLS = ["X (go first)", "O (go second)"]


def human_symbol():
    return "X" if ss.get("sym", SYMBOLS[0]).startswith("X") else "O"


def vs_computer():
    return ss.get("mode", MODES[0]) == "Vs Computer"


def play(index):
    ss.board[index] = ss.cur
    result = check_winner(ss.board)
    if result:
        ss.over = True
        ss.scores[result] += 1
    else:
        ss.cur = other_player(ss.cur)


def computer_if_needed():
    if vs_computer() and not ss.over and ss.cur == other_player(human_symbol()):
        play(pick_computer_move(ss.board, ss.get("strat", "AI (Groq)"), ss.cur))


def new_game():
    ss.board = [""] * 9
    ss.cur = "X"
    ss.over = False
    ss.note = ""
    computer_if_needed()          # the computer opens when you play O


def settings_changed():
    ss.scores = {"X": 0, "O": 0, "Draw": 0}
    new_game()


def reset_scores():
    ss.scores = {"X": 0, "O": 0, "Draw": 0}


def on_cell(index):
    if ss.over or ss.board[index] != "":
        return
    play(index)
    computer_if_needed()


def names():
    if vs_computer():
        human = human_symbol()
        return {human: f"You ({human})", other_player(human): f"Computer ({other_player(human)})"}
    return {"X": "Player X", "O": "Player O"}


# =====================================================
# UI
# =====================================================
st.title("Tic Tac Toe")

st.radio("Mode", MODES, key="mode", horizontal=True, on_change=settings_changed)
two_player = not vs_computer()
st.radio("Computer strategy", STRATEGIES, index=2, key="strat", horizontal=True,
         on_change=settings_changed, disabled=two_player)
st.radio("Your symbol (X always goes first)", SYMBOLS, key="sym", horizontal=True,
         on_change=settings_changed, disabled=two_player)

# the computer opens the very first game if you chose O before the first click
if vs_computer() and ss.board == [""] * 9 and ss.cur == other_player(human_symbol()) and not ss.over:
    computer_if_needed()

n = names()
result = check_winner(ss.board)
if result is None:
    status = f"{n[ss.cur]}'s turn"
elif result == "Draw":
    status = "It's a draw!"
elif not vs_computer():
    status = f"Player {result} wins! 🎉"
else:
    status = "You win! 🎉" if result == human_symbol() else "You lose! 😢"
st.subheader(status)

for r in range(3):
    cols = st.columns(3)
    for c in range(3):
        i = r * 3 + c
        cols[c].button(ss.board[i] or "\u00a0", key=f"cell{i}", on_click=on_cell,
                       args=(i,), use_container_width=True)

st.write(f"{n['X']}: {ss.scores['X']}   |   {n['O']}: {ss.scores['O']}   |   Draws: {ss.scores['Draw']}")
if ss.note:
    st.caption(ss.note)

left, right = st.columns(2)
if ss.over:
    left.button("Play again", on_click=new_game, type="primary", use_container_width=True)
right.button("Reset scores", on_click=reset_scores, use_container_width=True)

''' NOTE: The AI mode needs a Groq API key. For security, no key is included.
 Set your own before running (PowerShell):
     $env:GROQ_API_KEY="your_key_here"
 Without a key, the game still works and falls back to the rule-based strategy.'''
import os
import re
import random
import tkinter as tk
from tkinter import messagebox

'''# Tic Tac Toe GUI with AI (Groq) integration
# STEP 1: Groq client setup (from the professor's template)
# Groq() automatically reads the GROQ_API_KEY environment variable.
# If the key or the library is missing, client stays None and the
# game still works by falling back to the rule-based strategy.'''
try:
    from groq import Groq
    client = Groq()
except Exception as error:
    print("Groq not available, AI mode will use the rule-based fallback:", error)
    client = None

MODEL_NAME = "openai/gpt-oss-120b" # change this to your preferred model

'''
# GAME LOGIC (no GUI code)
# Board = list of 9 cells: "" (empty), "X" or "O"
# Index layout:  0 1 2
#                3 4 5
#                6 7 8
'''

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # columns
    (0, 4, 8), (2, 4, 6),              # diagonals
]


def check_winner(board):
    """Return 'X', 'O', 'Draw', or None if the game is still going."""
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


'''
# COMPUTER STRATEGIES (the computer plays whichever symbol the human didn't pick)
# Each one takes the board and returns a cell index 0-8.
'''

# ---- Strategy 1: random (version 1 of the assignment) ----
def random_move(board):
    return random.choice(available_moves(board))


# ---- Strategy 2: rule-based (works offline, also the AI fallback) ----
def find_winning_move(board, player):
    """Return a cell where `player` would win immediately, else None."""
    for move in available_moves(board):
        trial = board[:]          # copy so the real board is not changed
        trial[move] = player
        if check_winner(trial) == player:
            return move
    return None


def rule_based_move(board, me):
    opponent = other_player(me)
    # 1. Win if possible
    move = find_winning_move(board, me)
    if move is not None:
        return move
    # 2. Block the human's winning move
    move = find_winning_move(board, opponent)
    if move is not None:
        return move
    # 3. Take the centre
    if board[4] == "":
        return 4
    # 4. Corners, then sides. Random choice when equally good.
    for group in ([0, 2, 6, 8], [1, 3, 5, 7]):
        options = [c for c in group if board[c] == ""]
        if options:
            return random.choice(options)


# ---- Strategy 3: AI move using the Groq API
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
    """Draw the board as text. Empty cells show their index number."""
    cells = [board[i] if board[i] != "" else str(i) for i in range(9)]
    rows = [" | ".join(cells[r:r + 3]) for r in (0, 3, 6)]
    return "\n---------\n".join(rows)


def ai_move(board, me):
    available = available_moves(board)

    if client is None:
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
            temperature=0.2,     # low = more consistent, less creative
            max_tokens=1000,        # we only need one digit back
        )
        reply = response.choices[0].message.content
        match = re.search(r"\d", reply)

        # VALIDATE: never trust the AI blindly. Its answer must be a legal move.
        if match and int(match.group()) in available:
            return int(match.group())
        print("AI gave an invalid move:", repr(reply), "-> using fallback")

    except Exception as error:
        print("API call failed:", error, "-> using fallback")

    return rule_based_move(board, me)


def pick_computer_move(board, strategy, me):
    if strategy == "random":
        return random_move(board)
    if strategy == "rules":
        return rule_based_move(board, me)
    return ai_move(board, me)

# GUI

class TicTacToe:
    def __init__(self, root):
        self.root = root
        self.root.title("Tic Tac Toe")
        self.root.resizable(False, False)

        self.mode = tk.StringVar(value="computer")   # "computer" or "two_player"
        self.strategy = tk.StringVar(value="ai")     # "random", "rules" or "ai"
        self.human = tk.StringVar(value="X")         # the human's symbol (X always starts)
        self.pending = None                          # scheduled computer move, if any
        self.board = [""] * 9
        self.current = "X"
        self.game_over = False
        self.locked = False
        self.scores = {"X": 0, "O": 0, "Draw": 0}

        self.build_widgets()
        self.update_score_labels()

    #layout
    def build_widgets(self):
        mode_frame = tk.Frame(self.root)
        mode_frame.pack(pady=(8, 2))
        tk.Radiobutton(mode_frame, text="Vs Computer", variable=self.mode,
                       value="computer", command=self.change_mode).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="Two Player", variable=self.mode,
                       value="two_player", command=self.change_mode).pack(side="left", padx=10)

        strategy_frame = tk.Frame(self.root)
        strategy_frame.pack(pady=(0, 6))
        self.strategy_buttons = []
        for text, value in (("Random", "random"),
                            ("Rule-based", "rules"),
                            ("AI (Groq)", "ai")):
            rb = tk.Radiobutton(strategy_frame, text=text, variable=self.strategy,
                                value=value, command=self.change_mode)
            rb.pack(side="left", padx=8)
            self.strategy_buttons.append(rb)

        symbol_frame = tk.Frame(self.root)
        symbol_frame.pack(pady=(0, 6))
        self.symbol_buttons = []
        for text, value in (("Play as X (first)", "X"),
                            ("Play as O (second)", "O")):
            rb = tk.Radiobutton(symbol_frame, text=text, variable=self.human,
                                value=value, command=self.change_mode)
            rb.pack(side="left", padx=8)
            self.symbol_buttons.append(rb)

        self.status = tk.Label(self.root, text="", font=("Arial", 14))
        self.status.pack()

        grid = tk.Frame(self.root)
        grid.pack(padx=10, pady=10)
        self.buttons = []
        for i in range(9):
            btn = tk.Button(grid, text="", font=("Arial", 32, "bold"),
                            width=4, height=2, command=lambda i=i: self.on_click(i))
            btn.grid(row=i // 3, column=i % 3)
            self.buttons.append(btn)

        self.score_label = tk.Label(self.root, text="", font=("Arial", 12))
        self.score_label.pack(pady=5)

        tk.Button(self.root, text="Reset Scores", command=self.reset_scores).pack(pady=(0, 10))

        self.update_status()

    #helpers
    def computer_symbol(self):
        return other_player(self.human.get())

    def player_names(self):
        if self.mode.get() == "computer":
            human = self.human.get()
            computer = self.computer_symbol()
            return {human: f"You ({human})", computer: f"Computer ({computer})"}
        return {"X": "Player X", "O": "Player O"}

    def update_status(self):
        names = self.player_names()
        self.status.config(text=f"{names[self.current]}'s turn")

    def update_score_labels(self):
        names = self.player_names()
        self.score_label.config(
            text=f"{names['X']}: {self.scores['X']}    "
                 f"{names['O']}: {self.scores['O']}    "
                 f"Draws: {self.scores['Draw']}"
        )

    #game flow
    def on_click(self, index):
        if self.game_over or self.locked or self.board[index] != "":
            return
        self.make_move(index)

        if self.game_over:
            return

        self.schedule_computer_if_needed()

    def schedule_computer_if_needed(self):
        """If it is the computer's turn, lock the board and let it move shortly."""
        if (self.mode.get() == "computer" and not self.game_over
                and self.current == self.computer_symbol()):
            self.locked = True
            self.pending = self.root.after(400, self.computer_turn)

    def computer_turn(self):
        self.pending = None
        if self.game_over:
            return
        self.status.config(text="Computer is thinking...")
        self.root.update_idletasks()          # show the message before the API call
        index = pick_computer_move(self.board, self.strategy.get(),
                                   self.computer_symbol())
        self.locked = False
        self.make_move(index)

    def make_move(self, index):
        self.board[index] = self.current
        color = "blue" if self.current == "X" else "red"
        self.buttons[index].config(text=self.current, fg=color)

        result = check_winner(self.board)
        if result:
            self.end_game(result)
        else:
            self.current = "O" if self.current == "X" else "X"
            self.update_status()

    def end_game(self, result):
        self.game_over = True
        self.scores[result] += 1
        self.update_score_labels()

        if result == "Draw":
            msg = "It's a draw!"
        elif self.mode.get() == "computer":
            msg = "You win! 🎉" if result == self.human.get() else "You lose! 😢"
        else:
            msg = f"Player {result} wins! 🎉"

        again = messagebox.askyesno("Game Over", f"{msg}\n\nPlay again?")
        if again:
            self.new_game()
        else:
            self.root.destroy()

    def new_game(self):
        if self.pending is not None:          # cancel any computer move still queued
            self.root.after_cancel(self.pending)
            self.pending = None
        self.board = [""] * 9
        self.current = "X"
        self.game_over = False
        self.locked = False
        for btn in self.buttons:
            btn.config(text="")
        self.update_status()
        self.schedule_computer_if_needed()    # computer opens when the human plays O

    def change_mode(self):
        # Strategy and symbol choice only matter when playing the computer
        state = "normal" if self.mode.get() == "computer" else "disabled"
        for rb in self.strategy_buttons + self.symbol_buttons:
            rb.config(state=state)
        self.reset_scores()
        self.new_game()

    def reset_scores(self):
        self.scores = {"X": 0, "O": 0, "Draw": 0}
        self.update_score_labels()


if __name__ == "__main__":
    root = tk.Tk()
    TicTacToe(root)
    root.mainloop()
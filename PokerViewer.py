"""
PokerViewer.py - watch your UNMODIFIED Poker.py being played.

Keep Cards.py, Poker.py (your original) and this file in one folder, then run:
    python PokerViewer.py            (or: python PokerViewer.py path/to/Poker.py)

How it works: Poker.py is run in a background thread. A trace hook notices when
certain functions in it are called or return, and pauses the game there so the
window can draw the current state (players, river, pot) read straight from
Poker.py's own variables. Poker.py itself is never edited or imported normally.

It looks for these names in Poker.py:
  BotDecision(player, call_amount, ...)  DealFirstCards()  DealRiver()
  BettingRound()  CheckWinner()  CheckPlayerBust()
and these variables:  players, river, pot
If you rename any of them, update the matching spot in Runner.tracer below.
"""
import math
import os
import queue
import runpy
import sys
import threading
import traceback
import tkinter as tk

RUN_NAME = "__poker_game__"
PHASES = ["Pre-flop", "Flop", "Turn", "River"]
HAND_NAMES = {1: "Royal Flush", 2: "Straight Flush", 3: "Four of a Kind", 4: "Full House",
              5: "Flush", 6: "Straight", 7: "Three of a Kind", 8: "Two Pair",
              9: "Pair", 10: "High Card"}


class StopGame(BaseException):
    """Raised inside the game thread to abandon a game (New game button)."""


class Runner:
    """Runs Poker.py in a thread and pauses it at interesting moments."""

    def __init__(self, path):
        self.path = path
        self.q = queue.Queue()
        self.go = threading.Semaphore(0)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.started = False
        self.stopped = False
        self.g = None            # Poker.py's globals (live!)
        self.seats = []          # all players, in fixed seating order
        self.hand = 0
        self.street = 0
        self.last = {}           # player name -> last action text
        self.pending = None
        self.winner = None
        self.bust_before = 0

    # -- thread plumbing --------------------------------------------------------
    def fetch(self):
        """Advance the game to its next pause. Returns (kind, data)."""
        if not self.started:
            self.started = True
            self.thread.start()
        else:
            self.go.release()
        return self.q.get()

    def stop(self):
        self.stopped = True
        self.go.release()

    def _run(self):
        folder = os.path.dirname(os.path.abspath(self.path))
        if folder not in sys.path:
            sys.path.insert(0, folder)
        sys.settrace(self.tracer)
        try:
            runpy.run_path(self.path, run_name=RUN_NAME)
            self.q.put(("done", None))
        except StopGame:
            pass
        except BaseException:
            self.q.put(("error", traceback.format_exc()))
        finally:
            sys.settrace(None)

    def emit(self, message, acting=None, reveal=False, winners=(), slow=False):
        if self.stopped:
            raise StopGame
        self.q.put(("event", {
            "message": message, "phase": PHASES[min(self.street, 3)], "hand": self.hand,
            "acting": acting, "reveal": reveal, "winners": list(winners), "slow": slow}))
        self.go.acquire()
        if self.stopped:
            raise StopGame

    # -- hooks into Poker.py ----------------------------------------------------
    def flush(self):
        """Report the previous bot action now that Poker.py has applied it."""
        if not self.pending:
            return
        player, action, call_amount = self.pending
        self.pending = None
        if action == "fold":
            text = "Fold"
        elif action == "stay":
            text = "Check"
        elif action == "call":
            text = f"Call {call_amount}"
        elif action == "raise":
            text = f"Raise to {player.bet_this_round}"
        else:
            text = str(action)
        if action in ("call", "raise") and player.chipcount == 0:
            text += " (all in)"
        self.last[player.name] = text
        self.emit(f"{player.name}: {text}", acting=player.name)

    def tracer(self, frame, event, arg):
        if event != "call" or frame.f_globals.get("__name__") != RUN_NAME:
            return None
        if self.g is None:
            self.g = frame.f_globals
        name = frame.f_code.co_name
        argnames = frame.f_code.co_varnames[:frame.f_code.co_argcount]

        if name == "BotDecision":
            self.flush()

            def on_decision(f, ev, a):
                if ev == "return":
                    player = f.f_locals[argnames[0]]
                    call_amount = f.f_locals[argnames[1]]
                    self.pending = (player, a, call_amount)
                return on_decision
            return on_decision

        if name == "BettingRound":
            def on_round(f, ev, a):
                if ev == "return":
                    self.flush()
                    self.street += 1
                    self.last.clear()
                return on_round
            return on_round

        if name == "DealFirstCards":
            def on_deal(f, ev, a):
                if ev == "return":
                    if not self.seats:
                        self.seats = list(self.g["players"])
                    self.hand += 1
                    self.street = 0
                    self.last.clear()
                    self.emit(f"Hand {self.hand}: cards dealt")
                return on_deal
            return on_deal

        if name == "DealRiver":
            def on_river(f, ev, a):
                if ev == "return":
                    self.emit("Community card dealt")
                return on_river
            return on_river

        if name == "CheckWinner":
            def on_winner(f, ev, a):
                if ev == "return" and a is not None:
                    self.winner = a
                    alive = [p for p in self.g["players"] if not p.folded]
                    hn = HAND_NAMES.get(a.status, "")
                    self.emit(f"{a.name} wins with {hn}", reveal=len(alive) > 1,
                              winners=[a.name], slow=True)
                return on_winner
            return on_winner

        if name == "CheckPlayerBust":
            self.bust_before = {p.name for p in self.g["players"]}
            if self.winner:
                self.emit(f"{self.winner.name} collects the pot ({self.g['pot']})",
                          winners=[self.winner.name])

            def on_bust(f, ev, a):
                if ev == "return":
                    gone = self.bust_before - {p.name for p in self.g["players"]}
                    if gone:
                        self.emit("Busted: " + ", ".join(sorted(gone)))
                return on_bust
            return on_bust
        return None


# ----------------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------------
SUIT_SYMBOL = {"Hearts": "\u2665", "Diamonds": "\u2666", "Clubs": "\u2663", "Spades": "\u2660"}
SUIT_COLOR = {"Hearts": "#c62828", "Diamonds": "#c62828", "Clubs": "#111111", "Spades": "#111111"}
RANK_SHORT = {"Jack": "J", "Queen": "Q", "King": "K", "Ace": "A"}
W, H = 860, 660
FELT, FELT_DARK = "#1b6b3a", "#124d29"


class PokerApp:
    def __init__(self, root, path):
        self.root = root
        self.path = path
        root.title("Poker Viewer")
        root.configure(bg="#222")

        left = tk.Frame(root, bg="#222")
        left.pack(side="left")
        self.canvas = tk.Canvas(left, width=W, height=H, bg="#222", highlightthickness=0)
        self.canvas.pack()

        bar = tk.Frame(left, bg="#222")
        bar.pack(fill="x", pady=6)
        self.play_btn = tk.Button(bar, text="Pause", width=8, command=self.toggle_play)
        self.play_btn.pack(side="left", padx=4)
        tk.Button(bar, text="Step", width=6, command=self.step_once).pack(side="left", padx=4)
        tk.Button(bar, text="New game", width=9, command=self.new_game).pack(side="left", padx=4)
        tk.Label(bar, text="Speed", bg="#222", fg="white").pack(side="left", padx=(14, 2))
        self.speed = tk.Scale(bar, from_=1, to=10, orient="horizontal", length=140,
                              bg="#222", fg="white", highlightthickness=0)
        self.speed.set(5)
        self.speed.pack(side="left")
        self.show_all = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Show all cards", variable=self.show_all, bg="#222",
                       fg="white", selectcolor="#444", activebackground="#222",
                       command=self.redraw).pack(side="left", padx=14)

        right = tk.Frame(root, bg="#222")
        right.pack(side="left", fill="y", padx=(0, 8), pady=8)
        tk.Label(right, text="Game log", bg="#222", fg="white").pack(anchor="w")
        self.log = tk.Text(right, width=34, height=38, bg="#111", fg="#ddd",
                           state="disabled", wrap="word")
        self.log.pack(fill="y", expand=True)

        self.playing = True
        self.after_id = None
        self.runner = None
        self.new_game()

    # -- control ----------------------------------------------------------------
    def new_game(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.runner:
            self.runner.stop()
            self.runner.thread.join(timeout=1) if self.runner.started else None
        self.runner = Runner(self.path)
        self.finished = False
        self.event = None
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.advance()
        if self.playing:
            self.schedule()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.config(text="Pause" if self.playing else "Play")
        if self.playing:
            self.schedule()
        elif self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def step_once(self):
        if self.playing:
            self.toggle_play()
        self.advance()

    def delay(self):
        base = int(1600 / (self.speed.get() ** 1.3)) + 20
        return base * 3 if self.event and self.event["slow"] else base

    def schedule(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(self.delay(), self.tick)

    def tick(self):
        self.after_id = None
        if not self.playing or self.finished:
            return
        self.advance()
        if not self.finished:
            self.schedule()

    def advance(self):
        if self.finished:
            return
        kind, data = self.runner.fetch()
        if kind == "event":
            self.event = data
        elif kind == "done":
            self.finished = True
            alive = self.runner.g["players"] if self.runner.g else []
            who = alive[0].name if alive else "Nobody"
            self.event = {"message": f"{who} wins the game!", "phase": "Game over",
                          "hand": self.runner.hand, "acting": None, "reveal": False,
                          "winners": [who], "slow": False}
        else:  # error inside Poker.py
            self.finished = True
            self.event = {"message": "Poker.py raised an error", "phase": "Error",
                          "hand": self.runner.hand, "acting": None, "reveal": False,
                          "winners": [], "slow": False}
            self.log_text("\n" + data)
        self.log_event(self.event)
        self.redraw()

    def log_text(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def log_event(self, ev):
        if ev["message"].startswith("Hand "):
            self.log_text(f"\n--- {ev['message']} ---")
        else:
            self.log_text(f"[{ev['phase']}] {ev['message']}")

    # -- drawing ----------------------------------------------------------------
    def redraw(self):
        c = self.canvas
        c.delete("all")
        cx, cy = W / 2, H / 2 - 10
        c.create_oval(cx - 380, cy - 250, cx + 380, cy + 250, fill=FELT_DARK, outline="#5d4037", width=10)
        c.create_oval(cx - 360, cy - 232, cx + 360, cy + 232, fill=FELT, outline="")
        ev, g = self.event, self.runner.g
        if not ev or g is None:
            return

        c.create_text(cx, cy - 95, text=f"Hand #{ev['hand']}  |  {ev['phase']}",
                      fill="#bfe8c9", font=("Helvetica", 12))
        c.create_text(cx, cy - 72, text=f"Pot: {g['pot']}", fill="white", font=("Helvetica", 18, "bold"))

        river = g["river"]
        for i in range(5):
            x = cx - 5 * 31 + i * 62 + 4
            if i < len(river):
                self.draw_card(x, cy - 40, river[i], True, 54, 76)
            else:
                c.create_rectangle(x, cy - 40, x + 54, cy + 36, outline="#2f8f56", dash=(3, 3))

        c.create_text(cx, cy + 72, text=ev["message"], fill="#ffe082", font=("Helvetica", 13, "bold"))

        seats = self.runner.seats
        n = max(len(seats), 1)
        for idx, p in enumerate(seats):
            ang = math.pi / 2 + idx * 2 * math.pi / n   # first player at the bottom
            self.draw_seat(cx + 335 * math.cos(ang), cy + 235 * math.sin(ang), p, ev, g)

    def draw_seat(self, x, y, p, ev, g):
        c = self.canvas
        out = p not in g["players"]
        bw, bh = 196, 86
        x0, y0 = x - bw / 2, y - bh / 2
        dim = out or p.folded
        outline, width = "#888", 2
        if ev["acting"] == p.name:
            outline, width = "#ffd54f", 4
        if p.name in ev["winners"]:
            outline, width = "#69f0ae", 5
        c.create_rectangle(x0, y0, x0 + bw, y0 + bh, fill="#3a3a3a" if dim else "#263238",
                           outline=outline, width=width)
        c.create_text(x0 + 10, y0 + 16, anchor="w", text=p.name,
                      fill="#888" if dim else "white", font=("Helvetica", 11, "bold"))
        c.create_text(x0 + 10, y0 + 36, anchor="w", text=f"Chips: {p.chipcount}",
                      fill="#888" if dim else "#ffd54f", font=("Helvetica", 10))
        status = "OUT" if out else ("Folded" if p.folded else self.runner.last.get(p.name, ""))
        c.create_text(x0 + 10, y0 + 56, anchor="w", text=status, fill="#b0bec5",
                      font=("Helvetica", 9), width=100)
        shows = ev["reveal"] and (not p.folded or p.name in ev["winners"])
        if shows and not out:
            c.create_text(x0 + 10, y0 + 74, anchor="w", text=HAND_NAMES.get(p.status, ""),
                          fill="#69f0ae", font=("Helvetica", 9, "bold"))
        if out or not p.hand:
            return
        face_up = self.show_all.get() or shows
        for i, card in enumerate(p.hand):
            self.draw_card(x0 + bw - 86 + i * 40, y0 + 19, card, face_up, 36, 50, dim=p.folded)

    def draw_card(self, x, y, card, face_up, w, h, dim=False):
        c = self.canvas
        if not face_up:
            c.create_rectangle(x, y, x + w, y + h, fill="#1565c0", outline="white", width=2)
            c.create_rectangle(x + 4, y + 4, x + w - 4, y + h - 4, outline="#90caf9")
            return
        c.create_rectangle(x, y, x + w, y + h, fill="#bdbdbd" if dim else "white", outline="#333")
        color = SUIT_COLOR[card.symbol]
        rank = RANK_SHORT.get(card.number, card.number)
        big = max(10, w // 3)
        c.create_text(x + 4, y + 4, anchor="nw", text=rank, fill=color, font=("Helvetica", big, "bold"))
        c.create_text(x + w / 2, y + h * 0.68, text=SUIT_SYMBOL[card.symbol], fill=color,
                      font=("Helvetica", int(big * 1.6)))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    poker_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "Poker.py")
    root = tk.Tk()
    PokerApp(root, poker_path)
    root.mainloop()

from Cards import *
import random
from collections import Counter
from itertools import combinations

playerNum =  5
players = []
river = []
pot = 0

class Player(object):
    def __init__ (self, name):
        self.name = "Player" + name
        self.chipcount = 10000
        self.hand = []
        self.status = (10, ())
        self.bet_this_round = 0
        self.folded = False
        self.all_in = False

def DealFirstCards():
    for i in range(2):
        for player in players:
            current_card = random.choice(deck)
            player.hand.append(current_card)
            deck.remove(current_card)

def DealRiver():
    current_card = random.choice(deck)
    river.append(current_card)
    deck.remove(current_card)

def CheckPlayerBust():
    players[:] = [p for p in players if p.chipcount > 0]


def get_hand_status(cards):
    values = sorted(rank_values[card.number] for card in cards)
    counts = Counter(values)
    groups = sorted(counts.values(), reverse=True)
    is_flush = len({card.symbol for card in cards}) == 1
    unique_values = sorted(counts)
    is_wheel = unique_values == [2, 3, 4, 5, 14]
    is_straight = len(unique_values) == 5 and (
        unique_values[-1] - unique_values[0] == 4 or is_wheel
    )

    # Order by group size first, then by card value
    # (e.g. full house 9-9-9-4-4 -> [9, 4]; two pair K-K-7-7-2 -> [13, 7, 2])
    ordered = sorted(counts, key=lambda v: (counts[v], v), reverse=True)

    # The wheel (A-2-3-4-5) is a 5-high straight, not ace-high
    if is_wheel:
        ordered = [5, 4, 3, 2, 1]

    tiebreak = tuple(-v for v in ordered)

    if is_straight and is_flush:
        category = 1 if unique_values[-1] == 14 and unique_values[0] == 10 else 2
    elif groups[0] == 4:
        category = 3
    elif groups == [3, 2]:
        category = 4
    elif is_flush:
        category = 5
    elif is_straight:
        category = 6
    elif groups[0] == 3:
        category = 7
    elif groups == [2, 2, 1]:
        category = 8
    elif groups[0] == 2:
        category = 9
    else:
        category = 10

    return (category, tiebreak)

def CheckWinners():
    contenders = [p for p in players if not p.folded]
    best = min(p.status for p in contenders)
    return [p for p in contenders if p.status == best]

def BettingRound():
    global pot
    current_bet = 0
    min_raise = 100

    active_players = [
        p for p in players
        if not p.folded and not p.all_in
    ]

    pending = active_players.copy()

    while pending and sum(not p.folded for p in players) > 1:

        player = pending.pop(0)

        call_amount = current_bet - player.bet_this_round

        action = BotDecision(player, call_amount, current_bet)

        if action == "fold":
            player.folded = True

        elif action == "stay":
            if call_amount != 0:
                raise ValueError("Cannot stay when facing a bet")

        elif action == "call":
            amount = min(call_amount, player.chipcount)

            player.chipcount -= amount
            player.bet_this_round += amount
            pot += amount

            if player.chipcount == 0:
                player.all_in = True

        elif action == "raise":
            raise_amount = min_raise

            if player.chipcount < call_amount + raise_amount:
                raise ValueError("Insufficient chips to raise")

            amount = call_amount + raise_amount

            player.chipcount -= amount
            player.bet_this_round += amount
            pot += amount

            current_bet = player.bet_this_round

            # Other players must respond to the raise
            pending = [
                p for p in players
                if not p.folded
                and not p.all_in
                and p != player
            ]

        else:
            raise ValueError("Invalid bot action")

    for player in players:
        player.bet_this_round = 0

def BotDecision(player, call_amount, current_bet):

    if call_amount == 0:
        actions = ["stay", "raise"]

    else:
        actions = ["fold", "call", "raise"]

    if player.chipcount < call_amount + 100:
        actions.remove("raise")

    return random.choice(actions)

def RotateSeats():
    players.append(players.pop(0))


#Start of the game Setting up all the players at the Table

for i in range(playerNum):
    players.append(Player(str(i+1)))


def TestFairness(hands=10000):
    global pot, deck

    wins = {p.name: 0 for p in players}
    ties = {p.name: 0 for p in players}

    for _ in range(hands):
        pot = 0
        river.clear()
        deck = baseDeck.copy()

        for player in players:
            player.hand.clear()
            player.chipcount = 10000   # reset so nobody busts
            player.folded = False
            player.all_in = False
            player.bet_this_round = 0

        RotateSeats()
        DealFirstCards()
        BettingRound()
        for _ in range(3):
            DealRiver()
        BettingRound()
        DealRiver()
        BettingRound()
        DealRiver()
        for player in players:
            cards = player.hand + river
            player.status = min(get_hand_status(h) for h in combinations(cards, 5))
        BettingRound()

        winners = CheckWinners()
        for w in winners:
            if len(winners) == 1:
                wins[w.name] += 1
            else:
                ties[w.name] += 1

    return wins, ties

"""
wins, ties = TestFairness(10000)
print("Outright wins:", wins)
print("Split pots:   ", ties)

Unmark this if you want to check fairness for 10000 hands statistically
"""

while len(players) > 1:
    pot = 0
    river.clear()
    deck = baseDeck.copy()

    for player in players:
        player.hand.clear()
        player.folded = False
        player.all_in = False
        player.bet_this_round = 0

    DealFirstCards()
    BettingRound()
    for i in range(3):
        DealRiver()
    BettingRound()
    DealRiver()
    BettingRound()
    DealRiver()
    for player in players:
        cards = player.hand + river
        player.status = min(get_hand_status(hand) for hand in combinations(cards, 5))
    BettingRound()
    #for player in players:
        #print(f"{player.name} has a hand status of {player.status} with cards: {[f'{card.number} of {card.symbol}' for card in player.hand]} and river: {[f'{card.number} of {card.symbol}' for card in river]}")
    winners = CheckWinners()
    share, remainder = divmod(pot, len(winners))
    for w in winners:
        w.chipcount += share
    winners[0].chipcount += remainder  # odd chips go to the first winner
    CheckPlayerBust()

for player in players:
    print(player.name, player.chipcount)
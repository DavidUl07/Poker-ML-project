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
        self.status = 10
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
    for player in players:
        if player.chipcount == 0:
            players.remove(player)


def get_hand_status(cards):
    values = sorted(rank_values[card.number] for card in cards)
    counts = Counter(values)
    groups = sorted(counts.values(), reverse=True)
    is_flush = len({card.symbol for card in cards}) == 1
    unique_values = sorted(counts)
    is_straight = len(unique_values) == 5 and (
        unique_values[-1] - unique_values[0] == 4
        or unique_values == [2, 3, 4, 5, 14]
    )

    if is_straight and is_flush:
            return 1 if unique_values[-1] == 14 and unique_values[0] == 10 else 2
    if groups[0] == 4:
        return 3
    if groups == [3, 2]:
        return 4
    if is_flush:
        return 5
    if is_straight:
        return 6
    if groups[0] == 3:
        return 7
    if groups == [2, 2, 1]:
        return 8
    if groups[0] == 2:
        return 9
    return 10

def CheckWinner():
    winner = players[0]
    for player in players[1:]:
        if player.status < winner.status and not player.folded:
            winner = player
    return winner

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


#Start of the game Setting up all the players at the Table

for i in range(playerNum):
    players.append(Player(str(i+1)))


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
    winner = CheckWinner()
    #print(f"{winner.name} wins!")
    winner.chipcount += pot
    CheckPlayerBust()

for player in players:
    print(player.name, player.chipcount)
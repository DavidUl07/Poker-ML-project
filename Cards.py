class Card():
    def __init__ (self, symbol, number):
        self.symbol = symbol
        self.number = number
        self.name = self.number + " of " + self.symbol

numbers = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
symbols = ["Hearts", "Diamonds", "Clubs", "Spades"]

deck = [Card(symbol, number) for symbol in symbols for number in numbers]
baseDeck = deck.copy()
delt = []

rank_values = {str(value): value for value in range(2, 11)}
rank_values.update({"Jack": 11, "Queen": 12, "King": 13, "Ace": 14})


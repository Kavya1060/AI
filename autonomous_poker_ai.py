import re
import random
from enum import Enum
from treys import Card, Deck, Evaluator

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel 
from rich.text import Text

console = Console()

def print_hand(cards, prefix=""):
    """Helper to cleanly print cards using rich for UI."""
    if not cards:
        console.print(f"[bold]{prefix}[/bold] None")
        return
        
    card_strs = []
    for c in cards:
        s = Card.int_to_str(c)
        rank, suit = s[0], s[1]
        
        # Color code suits
        if suit in ['h', 'd']:
            color = "red"
        elif suit == 'c':
            color = "green"
        else: # spades
            color = "blue"
            
        # Add suit symbols
        symbols = {'h': '♥', 'd': '♦', 'c': '♣', 's': '♠'}
        suit_sym = symbols.get(suit, suit)
        card_strs.append(f"[{color}][{rank}{suit_sym}][/{color}]")
        
    formatted_cards = " ".join(card_strs)
    if prefix:
        console.print(f"[bold]{prefix}[/bold] {formatted_cards}")
    else:
        console.print(formatted_cards)

# ==========================================
# 1. MODELS: Player & Table & Pots
# ==========================================
class Player:
    def __init__(self, name: str, stack: int, is_ai: bool = False):
        self.name = name
        self.stack = stack
        self.is_ai = is_ai
        
        self.hole_cards = []
        self.is_active = True
        self.is_all_in = False
        self.current_bet = 0
        self.total_invested = 0
        
        # Stats tracking
        self.history = []

    def reset_for_hand(self):
        self.hole_cards = []
        self.is_active = self.stack > 0
        self.is_all_in = False
        self.current_bet = 0
        self.total_invested = 0

    def reset_for_round(self):
        self.current_bet = 0

    def bet(self, amount: int) -> int:
        if amount >= self.stack:
            actual = self.stack
            self.is_all_in = True
        else:
            actual = amount
        self.stack -= actual
        self.current_bet += actual
        self.total_invested += actual
        return actual

class Pot:
    def __init__(self):
        self.amount = 0
        self.eligible_players = []

    def add(self, amount: int):
        self.amount += amount

class Table:
    def __init__(self, small_blind: int, big_blind: int):
        self.players = []
        self.community_cards = []
        self.small_blind_amount = small_blind
        self.big_blind_amount = big_blind
        self.button_idx = 0
        self.pots = [Pot()]

    def add_player(self, player: Player):
        self.players.append(player)

    def reset_for_hand(self):
        self.community_cards = []
        self.pots = [Pot()]
        for p in self.players:
            p.reset_for_hand()

    def get_total_pot_size(self):
        return sum(pot.amount for pot in self.pots)
        
    def get_active_players(self):
        return [p for p in self.players if p.is_active]


# ==========================================
# 2. DECK MANAGER & INPUT VALIDATOR
# ==========================================
class DeckManager:
    SUITS = {
        'SPADE': 's', 'SPADES': 's', 'HEART': 'h', 'HEARTS': 'h',
        'DIAMOND': 'd', 'DIAMONDS': 'd', 'CLUB': 'c', 'CLUBS': 'c'
    }
    RANKS = {
        'TWO': '2', '2': '2', 'THREE': '3', '3': '3', 'FOUR': '4', '4': '4',
        'FIVE': '5', '5': '5', 'SIX': '6', '6': '6', 'SEVEN': '7', '7': '7',
        'EIGHT': '8', '8': '8', 'NINE': '9', '9': '9', 'TEN': 'T', '10': 'T',
        'JACK': 'J', 'QUEEN': 'Q', 'KING': 'K', 'ACE': 'A'
    }

    def __init__(self):
        self.deck = Deck()
        self.drawn_cards = set()

    def parse_card(self, card_str: str) -> int:
        clean_str = re.sub(r'\s+', ' ', card_str.strip().upper())
        parts = clean_str.split(' ')
        
        suit_word, rank_word = None, None
        if len(parts) == 2:
            suit_word, rank_word = parts[0], parts[1]
            if suit_word in self.RANKS and rank_word in self.SUITS:
                suit_word, rank_word = rank_word, suit_word
        elif len(parts) == 3 and parts[1] == "OF":
            rank_word, suit_word = parts[0], parts[2]
        else:
            raise ValueError(f"Invalid format '{card_str}'. Use 'Suit Rank' (e.g., 'Diamond Nine').")
                
        if suit_word not in self.SUITS or rank_word not in self.RANKS:
            raise ValueError("Invalid suit or rank.")
            
        return Card.new(f"{self.RANKS[rank_word]}{self.SUITS[suit_word]}")

    def draw_specific(self, card_str: str) -> int:
        card_int = self.parse_card(card_str)
        if card_int in self.drawn_cards:
            raise ValueError(f"Duplicate card detected: {Card.int_to_str(card_int)}")
        self.drawn_cards.add(card_int)
        if card_int in self.deck.cards:
            self.deck.cards.remove(card_int)
        return card_int

# ==========================================
# 3. GAME STATE CONTROLLER
# ==========================================
class GamePhase(Enum):
    PRE_FLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4

class GameController:
    def __init__(self, table: Table):
        self.table = table
        self.phase = GamePhase.PRE_FLOP
        self.current_idx = 0
        self.min_raise = table.big_blind_amount
        self.highest_bet = 0
        self.acted_this_round = set()
        
    def start_hand(self):
        self.table.reset_for_hand()
        self.phase = GamePhase.PRE_FLOP
        self.table.button_idx = (self.table.button_idx + 1) % len(self.table.players)
        
        sb_idx = self._next_active(self.table.button_idx)
        bb_idx = self._next_active(sb_idx)
        
        sb_amt = self.table.players[sb_idx].bet(self.table.small_blind_amount)
        bb_amt = self.table.players[bb_idx].bet(self.table.big_blind_amount)
        self.table.pots[0].add(sb_amt + bb_amt)
        
        self.highest_bet = self.table.big_blind_amount
        self.min_raise = self.table.big_blind_amount
        self.current_idx = self._next_active(bb_idx)
        self.acted_this_round = set()

    def _next_active(self, start_idx: int) -> int:
        n = len(self.table.players)
        for i in range(1, n + 1):
            idx = (start_idx + i) % n
            p = self.table.players[idx]
            if p.is_active and not p.is_all_in: return idx
        return -1

    def is_round_over(self) -> bool:
        active_not_allin = [p for p in self.table.players if p.is_active and not p.is_all_in]
        if len(active_not_allin) <= 1 and len(self.table.get_active_players()) > 1:
            pass # Special case for all-ins needing calls

        for i, p in enumerate(self.table.players):
            if p.is_active and not p.is_all_in:
                if i not in self.acted_this_round or p.current_bet < self.highest_bet:
                    return False
        return True

    def get_legal_actions(self):
        p = self.table.players[self.current_idx]
        call_amt = self.highest_bet - p.current_bet
        actions = {"FOLD": True, "CALL": min(call_amt, p.stack)}
        actions["CHECK"] = call_amt == 0
        
        if p.stack > call_amt:
            actions["RAISE_TO_MIN"] = min(self.highest_bet + self.min_raise, p.stack + p.current_bet)
            actions["RAISE_TO_MAX"] = p.stack + p.current_bet
        else:
            actions["RAISE_TO_MIN"] = actions["RAISE_TO_MAX"] = False
        return actions

    def process_action(self, action: str, amount: int = 0):
        p = self.table.players[self.current_idx]
        legal = self.get_legal_actions()
        
        if action == 'FOLD':
            p.is_active = False
        elif action == 'CHECK' and legal['CHECK']:
            pass
        elif action == 'CALL' and legal['CALL'] is not False:
            self.table.pots[0].add(p.bet(legal['CALL']))
        elif action == 'RAISE' and legal['RAISE_TO_MIN']:
            if not amount:
                raise ValueError(f"You must specify an amount to RAISE (e.g. RAISE {legal['RAISE_TO_MIN']})")
                
            min_legal = self.highest_bet + self.min_raise
            if amount < min_legal and amount != p.stack + p.current_bet:
                raise ValueError(f"Raise total ({amount}) must be at least ({min_legal}) or All-In.")
                
            raise_add = amount - p.current_bet
            if raise_add < 0:
                raise ValueError(f"Invalid raise, you already bet {p.current_bet}.")
                
            self.table.pots[0].add(p.bet(raise_add))
            
            if amount - self.highest_bet >= self.min_raise:
                self.min_raise = amount - self.highest_bet
                self.acted_this_round = set()
            self.highest_bet = amount
        else:
            raise ValueError(f"Illegal action {action}")

        self.acted_this_round.add(self.current_idx)
        if not self.is_round_over():
            self.current_idx = self._next_active(self.current_idx)

    def advance_phase(self):
        self.phase = GamePhase(self.phase.value + 1)
        for p in self.table.players: p.reset_for_round()
        self.highest_bet = 0
        self.min_raise = self.table.big_blind_amount
        self.acted_this_round = set()
        self.current_idx = self._next_active(self.table.button_idx)

# ==========================================
# 4. AI STRATEGY ENGINE & EVALUATOR
# ==========================================
class AIEngine:
    def __init__(self):
        self.evaluator = Evaluator()

    def _monte_carlo_equity(self, pocket_cards, board_cards, iterations=500):
        """Simulates `iterations` hands to estimate win probability."""
        if not pocket_cards:
            return 0.0

        wins = 0
        ties = 0

        # We need a clean deck to draw from for simulations
        # Start with a full deck and remove known cards
        known_cards = set(pocket_cards + board_cards)
        
        for _ in range(iterations):
            # Create a fresh list of available cards for this simulation
            full_deck = Deck()
            available_cards = [c for c in full_deck.cards if c not in known_cards]
            random.shuffle(available_cards)

            # 1. Deal opponent cards
            opp_cards = [available_cards.pop(), available_cards.pop()]

            # 2. Deal remaining board cards
            needed_board_cards = 5 - len(board_cards)
            simulated_board = list(board_cards)
            for _ in range(needed_board_cards):
                simulated_board.append(available_cards.pop())

            # 3. Evaluate hands
            ai_rank = self.evaluator.evaluate(simulated_board, pocket_cards)
            opp_rank = self.evaluator.evaluate(simulated_board, opp_cards)

            # Lower rank is better in treys
            if ai_rank < opp_rank:
                wins += 1
            elif ai_rank == opp_rank:
                ties += 1

        equity = (wins + (ties / 2)) / iterations
        return equity

    def get_decision(self, game: GameController, ai_player: Player):
        legal = game.get_legal_actions()
        pot = game.table.get_total_pot_size()
        to_call = legal.get('CALL', 0) if legal.get('CALL') else 0
        
        # 1. Evaluate True Equity via Monte Carlo
        equity = self._monte_carlo_equity(ai_player.hole_cards, game.table.community_cards)
            
        # 2. Pot Odds
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0

        # 3. Decision Logic (GTO/EV Inspired Simplified)
        if equity > 0.70 and legal['RAISE_TO_MIN']:
            min_raise_abs = game.highest_bet + game.min_raise
            target_amount = game.highest_bet + int(pot * (equity - 0.5)) # Bet bigger the larger our equity
            raise_size = max(min_raise_abs, target_amount)
            final_raise = min(raise_size, ai_player.stack + ai_player.current_bet)
            return {"action": "RAISE", "amount": final_raise, "reason": f"High Equity ({equity:.2f}) -> Value Bet"}
        elif equity > pot_odds:
            if legal['CHECK']: return {"action": "CHECK", "amount": 0, "reason": "Free card"}
            return {"action": "CALL", "amount": to_call, "reason": f"Equity ({equity:.2f}) > Pot Odds ({pot_odds:.2f}) -> +EV Call"}
        else:
            if legal['CHECK']: return {"action": "CHECK", "amount": 0, "reason": "Free card with weak hand"}
            return {"action": "FOLD", "amount": 0, "reason": f"-EV situation. Equity ({equity:.2f}) < Pot Odds ({pot_odds:.2f})"}



# ==========================================
# 5. MAIN INTERACTIVE LOOP
# ==========================================
def main():
    console.print(Panel.fit("[bold yellow]TEXAS HOLD'EM AUTONOMOUS AI ENGINE[/bold yellow]", border_style="bold blue"))
    
    # Setup Table
    def get_int_input(prompt_text, default_val):
        while True:
            val = input(f"{prompt_text} [{default_val}]: ").strip()
            if not val:
                return default_val
            try:
                return int(val)
            except ValueError:
                console.print("[bold red]Invalid input. Please enter a valid number.[/bold red]")

    num_players = get_int_input("Enter total number of players (2-10)", 2)
    bb = get_int_input("Enter Big Blind amount", 20)
    stack = get_int_input("Enter starting stack size", 1000)
        
    table = Table(small_blind=bb//2, big_blind=bb)
    table.add_player(Player("AI_Bot", stack, is_ai=True))
    table.add_player(Player("Human", stack))
    for i in range(2, num_players):
        table.add_player(Player(f"Opponent_{i}", stack))
        
    game = GameController(table)
    deck_mgr = DeckManager()
    ai = AIEngine()
    
    # Start Hand
    game.start_hand()
    console.print("\n[bold cyan]--- NEW HAND DEALT ---[/bold cyan]")
    
    # 1. Ask for AI Hole Cards (Strict validation)
    ai_cards = []
    for i in range(2):
        while True:
            try:
                card_str = input(f"Input AI Hole Card {i+1} (e.g. 'Spade Ace'): ")
                ai_cards.append(deck_mgr.draw_specific(card_str))
                break
            except ValueError as e:
                console.print(f"[bold red]Error: {e}. Please try again.[/bold red]")
    table.players[0].hole_cards = ai_cards
    print_hand(ai_cards, "-> Tracking AI_Bot:")

    # Game Loop Logic (Simplified version of round progression)
    while game.phase != GamePhase.SHOWDOWN:
        console.print(f"\n[bold magenta]--- {game.phase.name} ---[/bold magenta]")
        if game.phase == GamePhase.FLOP:
            console.print("[italic]Please input the 3 Flop cards:[/italic]")
            board = []
            for i in range(3):
                while True:
                    try:
                        board.append(deck_mgr.draw_specific(console.input(f"    [bold]Card {i+1}:[/bold] ")))
                        break
                    except ValueError as e:
                        console.print(f"    [bold red]Error: {e}. Please try again.[/bold red]")
            table.community_cards.extend(board)
        elif game.phase in [GamePhase.TURN, GamePhase.RIVER]:
            while True:
                try:
                    board = [deck_mgr.draw_specific(console.input(f"[bold]Input {game.phase.name} card:[/bold] "))]
                    table.community_cards.extend(board)
                    break
                except ValueError as e:
                    console.print(f"    [bold red]Error: {e}. Please try again.[/bold red]")
            
        print_hand(table.community_cards, "\nBoard:")
        console.print(f"💰 [bold green]Pot: {table.get_total_pot_size()}[/bold green]\n")
        
        if game.is_round_over() and len(table.get_active_players()) > 1:
            console.print("  [italic dim]-> Betting bypassed: Players are all-in![/italic dim]")
            
        while not game.is_round_over():
            p = table.players[game.current_idx]
            if not p.is_active or p.is_all_in:
                game.current_idx = game._next_active(game.current_idx)
                continue
                
            console.print(f"\n[bold green]  -> {p.name}'s Turn[/bold green] [dim](Stack: {p.stack}, Bet: {p.current_bet})[/dim]")
            
            if p.is_ai:
                dec = ai.get_decision(game, p)
                console.print(f"    [bold yellow]🤖 AI DECISION:[/bold yellow] [bold]{dec['action']} {dec['amount']}[/bold] | [italic dim]REASON: {dec['reason']}[/italic dim]")
                game.process_action(dec['action'], dec['amount'])
            else:
                legal = game.get_legal_actions()
                legal_str = ", ".join([f"{k}: {v}" for k,v in legal.items() if v is not False])
                console.print(f"    [dim]Legal Actions Available: {legal_str}[/dim]")
                while True:
                    act_str = console.input(f"    [bold]Enter Action for {p.name}[/bold] (e.g. FOLD, CHECK, CALL, RAISE 50): ").strip().upper()
                    parts = act_str.split()
                    act = parts[0] if parts else ""
                    
                    try:
                        amt = 0
                        if len(parts) > 1:
                            try:
                                amt = int(parts[1])
                            except ValueError:
                                console.print("    [bold red]Invalid amount. Please enter a number for bets/raises.[/bold red]")
                                continue
                                
                        game.process_action(act, amt)
                        break # Valid action processed
                    except Exception as e:
                        console.print(f"    [bold red]Invalid move: {e}[/bold red]")
                    
        # Check if hand ended early (everyone else folded)
        if len(table.get_active_players()) == 1:
            console.print(f"\n[bold yellow]*** {table.get_active_players()[0].name} wins by default! Everyone else folded. ***[/bold yellow]")
            break
            
        game.advance_phase()
        
    console.print(Panel("\n[bold magenta]--- SHOWDOWN ---[/bold magenta]", expand=False))
    active_players = table.get_active_players()
    if len(active_players) == 1:
        winner = active_players[0]
        console.print(f"[bold yellow]*** {winner.name} wins {table.get_total_pot_size()} by default! Everyone else folded. ***[/bold yellow]")
        winner.stack += table.get_total_pot_size()
    else:
        print_hand(table.players[0].hole_cards, "AI_Bot had:")
        for p in active_players:
            if p.is_ai:
                continue
            console.print(f"\n[bold]--- {p.name}'s Hole Cards ---[/bold]")
            mucked = False
            while True:
                c1 = console.input(f"Input {p.name} Card 1 (or press Enter to muck): ").strip()
                if not c1:
                    p.hole_cards = [] # Mucked
                    mucked = True
                    break
                try:
                    card1 = deck_mgr.draw_specific(c1)
                    break
                except ValueError as e:
                    console.print(f"    [bold red]Error: {e}. Please try again.[/bold red]")
                    
            if not mucked:
                while True:
                    c2 = console.input(f"Input {p.name} Card 2: ").strip()
                    try:
                        card2 = deck_mgr.draw_specific(c2)
                        p.hole_cards = [card1, card2]
                        print_hand(p.hole_cards, f"-> {p.name} shows:")
                        break
                    except ValueError as e:
                        console.print(f"    [bold red]Error: {e}. Please try again.[/bold red]")

        showdown_players = [p for p in active_players if p.hole_cards]
        if not showdown_players:
            console.print("[bold red]Everyone mucked! This shouldn't happen, distributing pot back to players.[/bold red]")
            # Simple handling for illegal everybody-muck scenario
        else:
            best_rank = float('inf')
            winners = []
            console.print("\n[bold cyan]--- RESULTS ---[/bold cyan]")
            
            res_table = RichTable(show_header=True, header_style="bold magenta")
            res_table.add_column("Player", width=15)
            res_table.add_column("Hand Class")
            res_table.add_column("Score", justify="right")
            
            for p in showdown_players:
                rank = ai.evaluator.evaluate(table.community_cards, p.hole_cards)
                class_str = ai.evaluator.class_to_string(ai.evaluator.get_rank_class(rank))
                res_table.add_row(p.name, class_str, str(rank))
                if rank < best_rank:
                    best_rank = rank
                    winners = [p]
                elif rank == best_rank:
                    winners.append(p)
            
            console.print(res_table)
            pot_size = table.get_total_pot_size()
            win_amount = pot_size // len(winners)
            for w in winners:
                console.print(f"[bold yellow]🏆 *** {w.name} WINS {win_amount}! *** 🏆[/bold yellow]")
                w.stack += win_amount

    console.print("\n[bold cyan]Round completed. Updated Stacks:[/bold cyan]")
    stack_table = RichTable(show_header=True, header_style="bold magenta")
    stack_table.add_column("Player", style="dim", width=15)
    stack_table.add_column("Stack Size", justify="right")
    stack_table.add_column("Status", justify="center")
    
    for p in table.players:
        if p.stack <= 0:
            status = "[dim]Busto[/dim]"
        elif p.is_all_in:
            status = "[red]All-In[/red]"
        elif not p.is_active:
            status = "[dim]Folded[/dim]"
        else:
            status = "[green]Active[/green]"
        stack_table.add_row(p.name, f"[bold]{p.stack}[/bold]", status)
        
    console.print(stack_table)
    console.print("[dim]Hand Over.[/dim]")

if __name__ == "__main__":
    main()

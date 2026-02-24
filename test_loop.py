from autonomous_poker_ai import Table, Player, GameController, GamePhase

def test_pot_size(bb, stack):
    table = Table(small_blind=bb//2, big_blind=bb)
    p1 = Player("Human", stack)
    p2 = Player("AI_Bot", stack, is_ai=True)
    table.add_player(p1)
    table.add_player(p2)

    game = GameController(table)
    game.start_hand()
    print(f"Testing BB={bb}, Stack={stack} -> Pot: {table.get_total_pot_size()}, P1 All-in: {p1.is_all_in}, P2 All-in: {p2.is_all_in}")

test_pot_size(bb=100, stack=1000) # Normal: Pot = 150
test_pot_size(bb=200, stack=100)  # Tiny Stack: Pot = 200, both all in
test_pot_size(bb=134, stack=100)  # Tiny Stack: Pot = 167 

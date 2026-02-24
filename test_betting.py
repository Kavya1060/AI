from autonomous_poker_ai import *
def test():
    table = Table(10, 20)
    p1 = Player("P1", 1000)
    p2 = Player("P2", 1000)
    table.add_player(p1)
    table.add_player(p2)
    game = GameController(table)
    
    # Pre-flop
    game.start_hand()
    print("Pre-flop started. is_round_over?", game.is_round_over())
    
    # P1 (button) is SB, P2 is BB. Current_idx should be next after BB, which is SB (P1).
    print("Current idx:", game.current_idx)
    
    # P1 CALLs
    game.process_action("CALL")
    print("After P1 call, is_round_over?", game.is_round_over())
    
    # P2 CHECKs
    game.process_action("CHECK")
    print("After P2 check, is_round_over?", game.is_round_over())
    
    # advance
    game.advance_phase()
    print("\nAdvanced phase to Flop")
    print("Flop started. is_round_over?", game.is_round_over())

test()

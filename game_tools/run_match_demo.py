"""Demo: create a Match with two players and print filtered states."""
from game_tools.game_engine import Match
from game_tools.playmat_manager import Zone


def demo():
    m = Match()
    p1 = m.add_player("Alice")
    p2 = m.add_player("Bob")

    # Place some sample cards into each player's deck/hand for demonstration
    try:
        p1.playmat.place_card_by_number(Zone.OSHI, "hSD01-001")
        p1.playmat.place_card_by_number(Zone.DECK, "hBP01-025", face_up=False)
        p1.playmat.place_card_by_number(Zone.HAND, "hSD01-005")

        p2.playmat.place_card_by_number(Zone.OSHI, "hSD01-002")
        p2.playmat.place_card_by_number(Zone.DECK, "hBP01-028", face_up=False)
        p2.playmat.place_card_by_number(Zone.HAND, "hSD01-006")
    except Exception:
        pass

    print("\n=== Alice view ===")
    print(m.get_filtered_state(p1.id))
    print("\n=== Bob view ===")
    print(m.get_filtered_state(p2.id))


if __name__ == "__main__":
    demo()

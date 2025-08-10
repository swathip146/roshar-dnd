import random

# D&D 5e Point Buy cost table
POINT_BUY_COST = {
    8: 0, 9: 1, 10: 2, 11: 3,
    12: 4, 13: 5, 14: 7, 15: 9
}

ABILITY_NAMES = ["Strength", "Dexterity", "Constitution",
                 "Intelligence", "Wisdom", "Charisma"]

POINTS_BUDGET = 27  # standard 5e budget


def calculate_cost(score):
    """Return the point-buy cost of a given ability score."""
    return POINT_BUY_COST.get(score, None)


def total_cost(scores):
    """Return total point cost for a list of scores."""
    return sum(calculate_cost(s) for s in scores)


def random_point_buy():
    """Generate random ability scores that follow point-buy rules."""
    while True:
        scores = [8] * 6
        points_left = POINTS_BUDGET

        # Randomly distribute points
        while points_left > 0:
            idx = random.randint(0, 5)
            if scores[idx] < 15:
                cost_next = calculate_cost(scores[idx] + 1) - calculate_cost(scores[idx])
                if points_left >= cost_next:
                    scores[idx] += 1
                    points_left -= cost_next
                else:
                    break
            else:
                continue

        if total_cost(scores) <= POINTS_BUDGET:
            return scores


def print_scores(scores):
    """Nicely print ability scores with names."""
    print("Generated Ability Scores (Point Buy):")
    for name, score in zip(ABILITY_NAMES, scores):
        print(f"{name:12}: {score}")
    print(f"Total Point Cost: {total_cost(scores)} / {POINTS_BUDGET}")


if __name__ == "__main__":
    # Example usage
    scores = random_point_buy()
    print_scores(scores)

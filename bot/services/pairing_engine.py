import logging
import random
from collections import defaultdict
from copy import deepcopy
from itertools import permutations

PairingResult = tuple[bool, dict[int, int]]
"""Returned by find_combination: (success, {santa_id: receiver_id})"""


class PairingEngine:
    """Pure pairing logic — no DB, no Telegram dependencies.

    ``find_combination`` takes lists of participant IDs and blocked
    pairings and returns a valid secret-santa assignment if one exists.
    """

    @staticmethod
    def find_combination(
        participants: list[int],
        blocked_pairings: list[list[int]],
    ) -> PairingResult:
        # permutations before removing blocked pairings
        unfiltered_permutations = list(permutations(participants, 2))
        logging.info(f"unfiltered permutations: {len(unfiltered_permutations)}")

        # permutations after removing blocked pairings
        filtered_permutations: dict[int, set[int]] = defaultdict(set)
        filtered_permutation_count = 0
        for permutation in unfiltered_permutations:
            blocked = False
            for blocked_pairing in blocked_pairings:
                if permutation[0] in blocked_pairing and permutation[1] in blocked_pairing:
                    blocked = True
                    break
            if not blocked:
                filtered_permutation_count += 1
                filtered_permutations[permutation[0]].add(permutation[1])

        logging.info(f"filtered permutations: {filtered_permutation_count}")

        if not filtered_permutations:
            return False, {}

        # sort permutations by least number of pairings
        sorted_permutations = sorted(filtered_permutations.items(), key=lambda x: len(x[1]))

        return PairingEngine.get_random_pairing(sorted_permutations)

    @staticmethod
    def get_random_pairing(
        remaining_participants: list[tuple[int, set[int]]],
        gifting: list[int] | None = None,
    ) -> PairingResult:
        if gifting is None:
            gifting = []
        remaining_participants_copy = deepcopy(remaining_participants)
        this_participant = remaining_participants_copy.pop(0)
        logging.info(this_participant)
        gifting.append(this_participant[0])
        participant_pairings = this_participant[1]
        if len(remaining_participants_copy) == 0:
            final_pairings = {this_participant[0]: participant_pairings.pop()}
            return True, final_pairings

        while len(participant_pairings) > 0:
            random_receiver = random.sample(list(participant_pairings), 1)[0]
            participant_pairings.remove(random_receiver)
            possible = True
            new_remaining_participants = deepcopy(remaining_participants_copy)
            remaining_pairings_list = [remaining_participant[1] for remaining_participant in new_remaining_participants]
            for remaining_pairings in remaining_pairings_list:
                if len(remaining_pairings) == 1 and random_receiver in remaining_pairings:
                    possible = False
                    break
                remaining_pairings.discard(random_receiver)
            if not possible:
                continue
            success, final_pairings = PairingEngine.get_random_pairing(new_remaining_participants, gifting)
            if success:
                final_pairings[this_participant[0]] = random_receiver
                return success, final_pairings
            continue

        return False, {}

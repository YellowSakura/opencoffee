from typing import Tuple
from scipy.sparse import csr_matrix
from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper
from opencoffee.pair_generator_algorithms.generic_pair_generator_algorithm import GenericPairGeneratorAlgorithm


class MaxDistanceGeneratorAlgorithm(GenericPairGeneratorAlgorithm):
    """ The class defines TODO. """

    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        users.sort()

        # Retrieve the list of all accessible public channels
        channel_ids = messaging_api_wrapper.get_public_channel_ids()

        # Build a sparse matrix to compute users distance
        u_distance_matrix = csr_matrix((len(users), len(users)), dtype = int)









        u_distance_matrix[0, 0] += 1

        print(f"Users:\n{users}\n")
        print(f"Distance matrix:\n{u_distance_matrix.toarray()}")


    def _get_coordinate(self, users: list[str], user1: str, user2: str) -> Tuple[int, int]:
        """ TODO """

        # Ensure that the coordinates take into account the lexicographic
        # order of user IDs.
        if user1 > user2:
            user1, user2 = user2, user1

        index1 = users.index(user1)
        index2 = users.index(user2)

        return (index1, index2)

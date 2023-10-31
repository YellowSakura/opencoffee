import time

from itertools import combinations
from typing import Tuple
from scipy.sparse import lil_matrix
from tqdm import tqdm
from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper
from opencoffee.pair_generator_algorithms.generic_pair_generator_algorithm import GenericPairGeneratorAlgorithm


class MaxDistanceGeneratorAlgorithm(GenericPairGeneratorAlgorithm):
    """ The class defines a strategy for generating pairs of users who usually do not
        interact with each other.
        This is achieved by checking the number of public channels in which various pairs
        are concurrently present, seeking the maximum distance (minimum number of
        simultaneous presences). """

    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        # Sorting is crucial to ensure the accurate computation of the
        # distance matrix among different users.
        users.sort()

        # Build a sparse matrix to compute users distance.
        # dtype uses unsigned int.
        u_distance_matrix = lil_matrix((len(users), len(users)), dtype = 'uint16')

        # Retrieve the list of all accessible public channels
        channel_ids = messaging_api_wrapper.get_public_channel_ids()

        # The distance matrix is constructed by iterating through all public
        # channels and checking for the presence of all possible combinations
        # of users for which pairs need to be created.
        for channel_id in tqdm(channel_ids, desc = 'Check channels'):
            channel_users = messaging_api_wrapper.get_users_from_channel(channel_id, [])
            channel_users.sort()

            # The sparse matrix is populated by adding an integer unit value
            # for each (previously sorted) pair of users.
            # ATTENTION: Sorting users optimizes the structure of the matrix,
            # as only the elements above the main diagonal will be populated.
            for user1, user2 in combinations(users, 2):
                if user1 in channel_users and user2 in channel_users:
                    indexes = self._get_sparse_matrix_index(users, user1, user2)
                    u_distance_matrix[indexes] += 1

            # Delay applied to avoid encountering an API rate limit
            time.sleep(.5)
        # <-- build a sparse matrix to compute users distance





        self._logger.debug("Users:\n%s", users)
        self._logger.debug("Distance matrix:\n%s", u_distance_matrix.toarray())


    def _get_sparse_matrix_index(self, users: list[str], user1: str, user2: str) -> Tuple[int, int]:
        """ The method ensures generating an appropriate tuple of integers, containing
            the indices usable to access the sparse distance matrix.
            The users' positions (previously sorted) in conjunction with the logic of
            generating the sparse matrix require that the matrix access coordinates
            take into account only the elements above the main diagonal.

            Example: Suppose we have users A and Z, with indices 0 and 26.
            The sparse matrix to access the distance between these two users should
            always be 0 and 26 (row 0 and column 26) and never 26 and 0 (row 26 and
            column 0). """

        # Ensure that the coordinates take into account the lexicographic
        # order of user IDs.
        if user1 > user2:
            user1, user2 = user2, user1

        return (users.index(user1), users.index(user2))

import random
import time

from itertools import combinations
from typing import Dict, List, Tuple
from scipy.sparse import lil_matrix
from tqdm import tqdm
from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper
from opencoffee.pair_generator_algorithms.generic_pair_generator_algorithm import GenericPairGeneratorAlgorithm


class MaxDistanceGeneratorAlgorithm(GenericPairGeneratorAlgorithm):
    """ The class defines a strategy for generating pairs of users who usually do not
        interact with each other.
        This is achieved by checking the number of public channels in which various
        pairs are concurrently present, seeking the maximum distance (minimum number
        of simultaneous presences). """

    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        # Sorting is crucial to ensure the accurate computation of the
        # distance matrix among different users.
        users.sort()

        # Retrieve the list of all accessible public channels
        channel_ids = messaging_api_wrapper.get_public_channel_ids()

        # Build a sparse matrix to compute user distances.
        # Since the distance between A and B is the same as between B and A, we
        # have a symmetric matrix, so we can store it efficiently.
        # Distance is never negative, so we use unsigned integers.
        u_distance_matrix = self._build_distance_matrix(messaging_api_wrapper, users, channel_ids)

        # Generate a copy of the user list that we use to generate pairs.
        #
        # ATTENTION: It's crucial to keep the original user list unchanged
        # as it allows, through the _get_sparse_matrix_index function, to
        # have a proper reference to users in the distance matrix.
        working_users = users.copy()

        # Shuffle the working users list before any logic
        random.shuffle(working_users)

        # Generate pairs from the working user's list -->
        pbar = tqdm(total = len(working_users), desc = 'Generate pairs')
        while len(working_users) > 1:
            current_user = working_users.pop(0)

            # The distance_dict dictionary will contain, in an ordered manner,
            # distances as keys and as values, a list of users' IDs associated
            # with the same distance.
            # This will be the reference data structure used to find the best
            # match for the current user.
            distance_dict: Dict[int, List[str]] = {}

            for test_user in users:
                # Ignoring users who have already been processed, so who are
                # not in the working_users list, and avoiding distance checks
                # between a user and themselves.
                if test_user not in working_users or test_user == current_user:
                    continue

                indexes = self._get_sparse_matrix_index(users, current_user, test_user)
                distance = u_distance_matrix[indexes]

                print(f"{current_user} è distante {distance} da {test_user}")

        pbar.close()
        # <-- generate pairs from the working user's list


    def _build_distance_matrix(self, messaging_api_wrapper: GenericMessagingApiWrapper, users: list[str],
                               channel_ids: list[str]) -> lil_matrix:
        """ The function effectively creates the distance matrix between all users
            in the users list and the list of input channels.

            Parameters:
                - users (list[str]): The list of users on which to calculate the various distances.
                - channel_id (str): The list of chat channel IDs to check for the presence of users.

            Returns:
                lil_matrix: A sparse matrix with the details of the distances
        """

        u_distance_matrix = lil_matrix((len(users), len(users)), dtype = 'uint16')

        # The distance matrix is constructed by iterating through all public
        # channels and checking for the presence of all possible combinations
        # of users for which pairs need to be created.
        for channel_id in tqdm(channel_ids, desc = 'Check channels'):
            channel_users = messaging_api_wrapper.get_users_from_channel(channel_id, [])
            channel_users.sort()

            # The sparse matrix is populated by adding an integer unit value
            # for each (previously sorted) pair of users.
            #
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
        self._logger.debug("Built distance matrix\n%s", u_distance_matrix.toarray())

        return u_distance_matrix


    def _get_sparse_matrix_index(self, users: list[str], user1: str, user2: str) -> Tuple[int, int]:
        """ The method ensures generating an appropriate tuple of integers, containing
            the indices usable to access the sparse distance matrix (symmetric matrix).
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

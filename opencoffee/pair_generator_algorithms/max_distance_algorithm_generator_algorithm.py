import random
import sys
import time

from itertools import combinations
from typing import Dict, List, Tuple
from scipy.sparse import lil_matrix
from tqdm import tqdm
from opencoffee.errors import GroupwareCommunicationError
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

        # Build the distance matrix
        try:
            u_distance_matrix = self._build_distance_matrix(messaging_api_wrapper, users)
        except GroupwareCommunicationError as e:
            self._logger.critical("Error while constructing the distance matrix, there is an issue with listing groups "
                                  "or their members within the group: %s", e)
            sys.exit(-1)

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
            u_distance_dict = self._build_user_distance_dict(users, working_users, current_user, u_distance_matrix)

            try:
                retry = 0

                for value in u_distance_dict.items():

                    # Retrieve and remove a random value from the list, trying to get
                    # combinations of users who haven't had a recent three-way
                    # conversation with the OpenCoffee bot.
                    target_user = random.choice(value)

                    # TODO AGGIUNGERE LOGICHE

            except GroupwareCommunicationError as e:
                self._logger.critical("Error getting recent message for the pair (%s, %s): %s", current_user, target_user, e)
                sys.exit(-1)

            self._logger.debug("%s has a row in the distance matrix of: %s", current_user, u_distance_dict)

        pbar.close()
        # <-- generate pairs from the working user's list


    def _build_distance_matrix(self, messaging_api_wrapper: GenericMessagingApiWrapper, users: list[str]) -> lil_matrix:
        """ The function effectively creates the distance matrix between all users
            in the users list.

            Parameters:
                - users (list[str]): The list of users on which to calculate the
                                     various distances

            Returns:
                lil_matrix: A sparse matrix with the details of the distances.
        """

        # Since the distance between A and B is the same as between B and A, we
        # have a symmetric matrix, so we can store it efficiently with a sparse
        # matrix, using in addition unsigned integers because distance is never
        # negative.
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


    def _build_user_distance_dict(self, users: list[str], working_users: list[str], current_user: str,
                                  u_distance_matrix: lil_matrix) -> Dict[int, List[str]]:
        """ The method will build a custom-generated dictionary, in an ordered
            manner, with all distances from the current_user.
            The keys will represent the distance values, and the values will
            be lists of users' IDs associated with the same distance.
            This will be the reference data structure used to find the best
            match for the current_user.

            Parameters:
                - users (list[str]): The list of users on which to calculate the
                                     various distances.
                - working_users (list[str]): The list of users already worked.
                - current_user (str): The user for whom we are building the
                                      dictionary.
                - u_distance_matrix (lil_matrix): The sparse matrix with the
                                                  details of the distances.

            Returns:
                Dict[int, List[str]]: The dictionary for the current_user.
        """

        distance_dict: Dict[int, List[str]] = {}

        for test_user in users:
            # Ignoring users who have already been processed, so who are
            # not in the working_users list, and avoiding distance checks
            # between a user and themselves.
            if test_user not in working_users or test_user == current_user:
                continue

            indexes = self._get_sparse_matrix_index(users, current_user, test_user)
            distance = u_distance_matrix[indexes]

            # Dictionary initialization for the current_user -->
            if distance not in distance_dict:
                distance_dict[distance] = []

            distance_dict[distance].append(test_user)

        # Sort the dictionary by distances (keys)
        sorted_keys = sorted(distance_dict.keys())
        distance_dict = {key: distance_dict[key] for key in sorted_keys}
        # <-- dictionary initialization for the current_user

        return distance_dict


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

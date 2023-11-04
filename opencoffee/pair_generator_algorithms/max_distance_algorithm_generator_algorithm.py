import random
import sys
import time

from itertools import combinations
from typing import Dict, List, Optional, Tuple
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
                candidate_user = self._search_pair_for_user(current_user, u_distance_dict, messaging_api_wrapper)

                if candidate_user is None:
                    self._logger.debug("\tNo valid pairs found for %s!", current_user)

                    self._ignored.append(current_user)

                    # Progress bar updated only for the current user, ignored in this
                    # round.
                    pbar.update(1)
                else:
                    working_users.remove(candidate_user)
                    self._pairs.append((current_user, candidate_user))

                    # Progress bar updated for the current user and the candidate user, used as
                    # pair for this round.
                    pbar.update(2)

            except GroupwareCommunicationError as e:
                self._logger.critical("Error searching pair for the user %s: %s", current_user, e)
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
            # Delay applied to avoid encountering an API rate limit
            time.sleep(.5)

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
        # <-- distance matrix construction

        self._logger.debug("Users:\n%s", users)
        self._logger.debug("Built distance matrix\n%s", u_distance_matrix.toarray())

        return u_distance_matrix


    def _build_user_distance_dict(self, users: list[str], working_users: list[str], current_user: str,
                                  u_distance_matrix: lil_matrix) -> Dict[int, List[str]]:
        """ The method builds a custom-generated dictionary in an ordered manner,
            which contains all distances from the current user.
            The keys represent the distance values, and the values consist of
            lists of user IDs associated with the same distance.
            This output will serve as the reference data structure used to find
            the best match for the current user

            Parameters:
                - users (list[str]): The list of users on which to calculate the
                    various distances.
                - working_users (list[str]): The list of users already worked.
                - current_user (str): The user for whom we are building the
                    dictionary.
                - u_distance_matrix (lil_matrix): The sparse matrix with the
                    details of the distances.

            Returns:
                Dict[int, List[str]]: The dictionary for the current user.
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

            # First initialization for a specific distance
            if distance not in distance_dict:
                distance_dict[distance] = []

            distance_dict[distance].append(test_user)

        # Sort the dictionary by distances (keys)
        sorted_keys = sorted(distance_dict.keys())
        distance_dict = {key: distance_dict[key] for key in sorted_keys}

        return distance_dict


    def _search_pair_for_user(self, current_user: str, u_distance_dict: Dict[int, List[str]],
                              messaging_api_wrapper: GenericMessagingApiWrapper) -> Optional[str]:
        """ The method searches for the best match for the current user, utilizing
            the dictionary containing all distances.
            The best match not only takes into account the distance between the
            current user and the candidate user but also checks if a similar
            combination has already been generated before.

            Parameters:
                - current_user (str): The user for whom we are searching for a match.
                - u_distance_dict Dict[int, List[str]]: The distance dictionary for
                    the current user.
                - messaging_api_wrapper (GenericMessagingApiWrapper): The wrapper
                    for accessing the API.

            Returns:
                Optional[str]: A string with the user ID, or None if no match is
                    found.
        """

        retry = 0
        max_retries = self._config.getint('slack', 'backtrack_max_attempts')

        for dict_elem in u_distance_dict.items():
            users_same_distance = dict_elem[1]

            # Retrieve and remove a random value from the list, trying to get
            # combinations of users who haven't had a recent three-way
            # conversation with the OpenCoffee bot.
            candidate_user = random.choice(users_same_distance)
            users_same_distance.remove(candidate_user)

            exist_recent_message = messaging_api_wrapper.exist_recent_message_exchange_in_pairs(
                    (current_user, candidate_user), self._config.getint('slack', 'backtrack_days'))

            # If a recently existing chat is detected, an attempt is made
            # to generate a new combination, up to a maximum defined in the
            # configuration.
            while exist_recent_message is True and retry < max_retries and len(users_same_distance) != 0:
                self._logger.debug("\tFound recent chat for (%s, %s), try different pairs!", current_user, candidate_user)

                candidate_user = random.choice(users_same_distance)
                users_same_distance.remove(candidate_user)
                retry += 1

                # Delay applied to avoid encountering an API rate limit
                time.sleep(.5)

                exist_recent_message = messaging_api_wrapper.exist_recent_message_exchange_in_pairs(
                        (current_user, candidate_user), self._config.getint('slack', 'backtrack_days'))

            if not exist_recent_message:
                return candidate_user

            if retry >= max_retries:
                return None

        return None


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

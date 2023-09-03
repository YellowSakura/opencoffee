import random
import sys
import time

from tqdm import tqdm

from opencoffee.errors import GroupwareCommunicationError
from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper
from opencoffee.pair_generator_algorithms.generic_pair_generator_algorithm import GenericPairGeneratorAlgorithm


class SimpleGeneratorAlgorithm(GenericPairGeneratorAlgorithm):
    """ The class defines a simple strategy for generating random user pairs, while ensuring
        that the various users being generated have not already interacted with each other
        through the OpenCoffee bot within a certain range of days defined by the configuration
        options. """

    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        # Shuffle the users list before any logic
        random.shuffle(users)

        # Generate random pairs from the user's list -->
        pbar = tqdm(total = len(users), desc = 'Generate pairs')
        while len(users) > 1:
            first = users.pop(0)

            # Retrieve and remove a random value from the list, trying to get
            # combinations of users who haven't had a recent three-way
            # conversation with the OpenCoffee bot.
            second = random.choice(users)

            try:
                exist_recent_message = messaging_api_wrapper.exist_recent_message_exchange_in_pairs((first, second),
                        self._config.getint('slack', 'backtrack_days'))
                retry = 0

                # If a recent pre-existing chat is detected, an attempt is made
                # to generate a new combination, up to a maximum of three attempts.
                while exist_recent_message is True and retry < self._config.getint('slack', 'backtrack_max_attempts'):
                    self._logger.debug("\tFound recent chat for (%s, %s), try different pairs!", first, second)

                    second = random.choice(users)
                    retry += 1

                    exist_recent_message = messaging_api_wrapper.exist_recent_message_exchange_in_pairs((first, second),
                            self._config.getint('slack', 'backtrack_days'))

                    # Delay applied to avoid encountering an API rate limit
                    time.sleep(0.5)

                if exist_recent_message:
                    self._logger.debug("\tNo valid pairs found for %s!", first)

                    self._ignored.append(first)

                    # Progress bar updated only for the user first, ignored in this
                    # round.
                    pbar.update(1)
                else:
                    users.remove(second)
                    self._pairs.append((first, second))

                    # Progress bar updated for the users first and second, used as
                    # pair for this round.
                    pbar.update(2)
            except GroupwareCommunicationError as e:
                self._logger.critical("Error getting recent message for the pair (%s, %s): %s", first, second, e)
                sys.exit(-1)

        # The progress bar is updated with the last user if it does not have an
        # associated pair, in this case with the value 1, otherwise with value 0.
        # In this way, we ensure at the end of the loop the progress bar will be
        # always at 100%.
        pbar.update(len(users))
        pbar.close()

        self._ignored.extend(users)
        # <-- generate random pairs from the user's list

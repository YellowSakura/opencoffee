from abc import ABC, abstractmethod
from typing import Iterable
from typing import Tuple


class GenericMessagingApiWrapper(ABC):
    """ Generic class that defines the methods that must be implemented mandatorily
        by the wrapper with the real logic. """

    @abstractmethod
    def get_users_from_channel(self, channel_id: str, ignore_users: Iterable[str]) -> list[str]:
        """ Reads all members inside the channel with the ID channel_id, excluding
            users defined in ignore_users. """


    @abstractmethod
    def send_message_to_pairs(self, pair: Tuple[str, ...], message: str) -> None:
        """ Send a message to a pair list of users.
            This involves two different services: the first one is opening a
            conversation, and the second one is sending the message itself. """


    @abstractmethod
    def exist_recent_message_exchange_in_pairs(self, pair: Tuple[str, ...], backtrack_days: int,
                                               limit: int = 1) -> bool:
        """ Determine if a list of users have a recent message exchanged by
            checking their history up to a certain number of days. """

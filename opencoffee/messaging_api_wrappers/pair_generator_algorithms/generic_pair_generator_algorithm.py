
import logging

from abc import ABC, abstractmethod
from typing import Iterable

from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper


class GenericPairGeneratorAlgorithm(ABC):
    """ Generic class that defines the methods that must be implemented mandatorily
        by the TODO """

    _pairs: Iterable[str]
    _ignored: Iterable[str]
    _logger: logging.Logger


    def __init__(self, logger: logging.Logger):
        self._pairs = []
        self._ignored = []
        self._logger = logger


    def get_pairs(self) -> Iterable[str]:
        """ TODO """
        return self._pairs


    def get_ignored(self) -> Iterable[str]:
        """ TODO """
        return self._ignored


    @abstractmethod
    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        """ TODO. """

        return

import configparser
import logging

from abc import ABC, abstractmethod
from typing import Tuple

from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper


class GenericPairGeneratorAlgorithm(ABC):
    """ Generic class that defines the methods that need to be implemented in classes that
        define the logic for creating a set of pairs given a list of users.
        By implementing this class, it's possibile define various strategies for generating
        pairs."""

    _pairs: list[Tuple[str, ...]]
    _ignored: list[str]
    _config: configparser.ConfigParser
    _logger: logging.Logger


    def __init__(self, config: configparser.ConfigParser, logger: logging.Logger):
        self._pairs = []
        self._ignored = []
        self._config = config
        self._logger = logger


    def get_pairs(self) -> list[Tuple[str, ...]]:
        """
            Returns:
                list[str]: The pairs calculated by the compute_pairs_from_users method.
        """
        return self._pairs


    def get_ignored(self) -> list[str]:
        """
            Returns:
                list[str]: The ignored users (if exists) calculated by the compute_pairs_from_users method."

        """
        return self._ignored


    @abstractmethod
    def compute_pairs_from_users(self, users: list[str], messaging_api_wrapper: GenericMessagingApiWrapper) -> None:
        """ The method defines the specific algorithm used to retrieve user pairs in accordance with the
            API wrapper reference.

            Parameters:
                - users: list[str]: The list of users from which to create pairs.
                - messaging_api_wrapper: GenericMessagingApiWrapper: The reference to the API wrapper for
                    query the specific remote service in order to generate pairs.
        """

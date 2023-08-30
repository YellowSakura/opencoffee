from datetime import datetime, timedelta
from typing import Iterable
from typing import Tuple

import slack_sdk

from slack_sdk.errors import SlackApiError
from opencoffee.errors import GroupwareCommunicationError
from opencoffee.messaging_api_wrappers.generic_service_connector import GenericServiceConnector


class SlackConnector(GenericServiceConnector):
    """ The class handles all the logic towards the Slack APIs, using the official
        SDK which is thus abstracted from the caller. """

    api_token: str
    client: slack_sdk.WebClient
    test_mode: bool


    def __init__(self, api_token, test_mode = False):
        self.api_token = api_token
        self.client = slack_sdk.WebClient(token = self.api_token)
        self.test_mode = test_mode


    def get_users_from_channel(self, channel_id: str, ignore_users: Iterable[str]) -> list[str]:
        """ Reads all members inside the channel with the ID channel_id, excluding
            users defined in ignore_users.

            Official Slack documentation:
                https://api.slack.com/methods/conversations.members

            Parameters:
                - channel_id (str): The channel ID from witch to read users.
                - ignore_users (Iterable[str]): The users to ignore.

            Returns:
                list[str]: The list of user IDs from a channel

            Raises:
                GroupwareCommunicationError: In case of Slack API error.
        """

        try:
            response = self.client.conversations_members(channel = channel_id)
            chanel_users = response['members']

            # Manage paginated results (100 members at a time)
            # https://api.slack.com/methods/conversations.members#arg_limit
            while response['response_metadata']['next_cursor']:
                response = self.client.conversations_members(channel = channel_id,
                                                             cursor = response['response_metadata']['next_cursor'])
                chanel_users.extend(response['members'])

            # All users configured to be ignored are removed from the members list
            users = [elem for elem in chanel_users if elem not in ignore_users]
        except SlackApiError as e:
            raise GroupwareCommunicationError(str(e), e.response) from e

        return users


    def send_message_to_pairs(self, pair: Tuple[str, ...], message: str) -> None:
        """ Send a message to a pair list of users.
            This involves two different services: the first one is opening a
            conversation, and the second one is sending the message itself.

            Official Slack documentation:
                https://api.slack.com/methods/conversations.open
                https://api.slack.com/methods/chat.postMessage

            Parameters:
                - pair (Tuple[str, ...]): Tuple containing the list of users
                    to whom to send the message.
                - message (str): Text message to send.

            Returns:
                None

            Raises:
                GroupwareCommunicationError: In case of Slack API error.
        """

        try:
            channel_id = self.client.conversations_open(users = pair)['channel']['id']

            if not self.test_mode:
                self.client.chat_postMessage(channel = channel_id, text = message)
        except SlackApiError as e:
            raise GroupwareCommunicationError(str(e), e.response) from e


    def exist_recent_message_exchange_in_pairs(self, pair: Tuple[str, ...], backtrack_days: int,
                                               limit: int = 1) -> bool:
        """ Determine if a list of users have a recent message exchanged by
            checking their history up to a certain number of days.
            The calls to the Slack API are designed to minimize the payload
            and the amount of data received.

            Official Slack documentation:
                https://api.slack.com/methods/conversations.history
                https://api.slack.com/methods/conversations.info

            Parameters:
                - pair (Tuple[str, ...]): Tuple containing the list of users
                    for whom to search for recent messages.
                - backtrack_days (int): Number of days (not negative) to check
                    the presence of a chat among the various users.
                - limit (int): Optional, the number of messages to extract.

            Returns:
                bool: True or False based on whether at least one message has
                    been found among the various users in the pair within the
                    last backtrack_days days.

            Raises:
                GroupwareCommunicationError: In case of Slack API error.
        """

        try:
            channel_id = self.client.conversations_open(users = pair)['channel']['id']
            oldest_timestamp = (datetime.today() - timedelta(days = backtrack_days)).timestamp()

            messages = self.client.conversations_history(channel = channel_id, oldest = str(oldest_timestamp),
                                                         limit = limit)['messages']
        except SlackApiError as e:
            raise GroupwareCommunicationError(str(e), e.response) from e

        return len(messages) == limit

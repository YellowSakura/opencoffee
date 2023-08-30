import argparse
import configparser
import gettext
import importlib.metadata
import json
import logging
import random
import sys
import time

from datetime import datetime
from typing import Callable
from tqdm import tqdm
from opencoffee.errors import GroupwareCommunicationError
from opencoffee.messaging_api_wrappers.generic_service_connector import GenericServiceConnector
from opencoffee.messaging_api_wrappers.slack_connector import SlackConnector
from opencoffee import utils


def main():
    """ The main function """

    # Command line argument management -->
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--conf',
        help = 'configuration file, default config.ini',
        default = 'config.ini')

    parser.add_argument('-a', '--action',
        choices = ['invitation', 'reminder'],
        help = 'action to perform: execute a new "invitation" round or send a "reminder" for the previous one',
        required = True)

    parser.add_argument('--version', action='version', version=importlib.metadata.version('opencoffee'))

    args = parser.parse_args()
    # <-- command line argument management

    # Read and check configuration file -->
    config = configparser.ConfigParser()
    if len(config.read(args.conf)) == 0:
        print(f'File "{args.conf}" not found or invalid', file = sys.stderr)
        sys.exit(-1)

    utils.check_config_values(config)
    # <-- read and check configuration file

    logger = utils.get_logger(config)

    # Apply translations -->
    _ = gettext.gettext

    if config.get('GENERIC', 'language', fallback = 'en') != 'en':
        new_language = gettext.translation('messages', localedir = 'opencoffee/locales',
                                           languages = [config['GENERIC']['language']])
        new_language.install()
        _ = new_language.gettext
    # <-- apply translations

    logger.info('OpenCoffee BEGIN')

    if config.getboolean('GENERIC', 'test_mode'):
        logger.warning('Test mode: ON - NO MESSAGES WILL BE SENT')

    slack_connector = SlackConnector(config['slack']['api_token'], config.getboolean('GENERIC', 'test_mode'))

    if args.action == 'invitation':
        manage_invitation_action(config, logger, slack_connector, _, args)
    elif args.action == 'reminder':
        manage_reminder_action(config, logger, slack_connector, _, args)

    logger.info('OpenCoffee END')


def manage_invitation_action(config: configparser.ConfigParser, logger: logging.Logger,
                             slack_connector: GenericServiceConnector, _: Callable[..., str],
                             args: argparse.Namespace) -> None:
    """ Manage the invitation action.
        The function takes all the members in a channel and randomly pairs
        them up. """

    try:
        users = slack_connector.get_users_from_channel(config['slack']['channel_id'], config['slack']['ignore_users'])
    except GroupwareCommunicationError as e:
        logger.error("Error getting list of users: %s", e)
        sys.exit(-1)

    # Shuffle the users list before any logic
    random.shuffle(users)

    # Generate random pairs from the user's list -->
    pairs = []
    ignored = []

    pbar = tqdm(total = len(users), desc = 'Generate pairs')
    while len(users) > 1:
        first = users.pop(0)

        # Retrieve and remove a random value from the list, trying to get
        # combinations of users who haven't had a recent three-way
        # conversation with the OpenCoffee bot.
        second = random.choice(users)

        try:
            exist_recent_message = slack_connector.exist_recent_message_exchange_in_pairs((first, second),
                    config.getint('slack', 'backtrack_days'))
            retry = 0

            # If a recent pre-existing chat is detected, an attempt is made
            # to generate a new combination, up to a maximum of three attempts.
            while exist_recent_message is True and retry < config.getint('slack', 'backtrack_max_attempts'):
                logger.debug("\tFound recent chat for (%s, %s), try different pairs!", first, second)

                second = random.choice(users)
                retry += 1

                exist_recent_message = slack_connector.exist_recent_message_exchange_in_pairs((first, second),
                        config.getint('slack', 'backtrack_days'))

                # Delay applied to avoid encountering an API rate limit
                time.sleep(0.5)

            if exist_recent_message:
                logger.debug("\tNo valid pairs found for %s!", first)

                ignored.append(first)

                # Progress bar updated only for the user first, ignored in this
                # round.
                pbar.update(1)
            else:
                users.remove(second)
                pairs.append((first, second))

                # Progress bar updated for the users first and second, used as
                # pair for this round.
                pbar.update(2)
        except GroupwareCommunicationError as e:
            logger.error("Error getting recent message for the pair (%s, %s): %s", first, second, e)
            sys.exit(-1)

    # The progress bar is updated with the last user if it does not have an
    # associated pair, in this case with the value 1, otherwise with value 0.
    # In this way, we ensure at the end of the loop the progress bar will be
    # always at 100%.
    pbar.update(len(users))
    pbar.close()

    ignored.extend(users)
    # <-- generate random pairs from the user's list

    logger.debug('Generated the pairs: %s', pairs)
    logger.info(f"The {utils.get_plural_or_singular(len(ignored), 'user', 'users')} {ignored} "
                f"{utils.get_plural_or_singular(len(ignored), 'has', 'have')} been excluded from this round!")

    # Send the invitation message to all the pairs, applying a small
    # delay between each send to avoid encountering an API rate limit.
    for pair in tqdm(pairs, desc = 'Send invitation messages'):
        try:
            slack_connector.send_message_to_pairs(pair, _(":wave: hi <!here>, sometimes it can be difficult to "
                            "know all your colleagues, so I take care of creating opportunities for a :coffee: "
                            "and a chat among all members in <#%s>.\n"
                            "What do you think about a time to get to know each other better?")
                % (config['slack']['channel_id']))
        except GroupwareCommunicationError as e:
            logger.warning("Error sending message to the pair (%s, %s), OpenCoffee will continue to the next send\
                           operation: %s", first, second, e)

        time.sleep(0.25)

    # Serialization of the pair list into a file for the reminder action.
    #
    # ATTENTION: The use of a suffix in the lexicographically sortable date format
    # is a fundamental condition for the program's operation.
    # Refer to the get_most_recent_file_history function. -->
    tail_file_name = utils.get_history_filename(config.getboolean('GENERIC', 'test_mode'), args.conf,
                                          datetime.now().strftime('%Y%m%d-%H%M'))

    with open(f"{config['GENERIC']['history_path']}{tail_file_name}", 'w', encoding = 'utf-8') as file:
        json.dump(pairs, file)

    logger.info(f"Generated {len(pairs)} {utils.get_plural_or_singular(len(pairs), 'pair', 'pairs')}")
    # <-- serialization of the pair list into a file for the reminder action


def manage_reminder_action(config: configparser.ConfigParser, logger: logging.Logger,
                           slack_connector: GenericServiceConnector, _: Callable[..., str],
                           args: argparse.Namespace) -> None:
    """ Manage the reminder action.
        Retrieve the file generated from the last run, containing the
        various sent messages, checking whether a reminder needs to be sent
        to the different users or not. """

    # The file of history generated from the last execution that sent
    # out the various invitations is retrieved.
    # For this reason, we define the tail_file_name pattern used to
    # search through files.
    tail_file_name = utils.get_history_filename(config.getboolean('GENERIC', 'test_mode'), args.conf)

    file_history = utils.get_most_recent_file_history(config['GENERIC']['history_path'], tail_file_name)

    if file_history is None:
        logger.warning('No valid file history found!')
        sys.exit(0)
    else:
        logger.info(f"Working on: {file_history}")
    # <-- retrieval of the latest pairs history

    with open(f"{config['GENERIC']['history_path']}{file_history}", 'r', encoding = 'utf-8') as file:

        reminder_sent = 0

        # Send the reminder message to all the pairs, applying a small
        # delay between each send to avoid encountering an API rate limit.
        for pair in tqdm(json.load(file), desc = 'Send reminder messages'):

            # An heuristic is applied to determine whether to send a reminder
            # message or not, by checking if users have exchanged at least 4
            # messages in the recent period.
            #
            # ATTENTION: The value 5 is used to include the message sent by
            # OpenCoffee in the count.
            exist_recent_messages = slack_connector.exist_recent_message_exchange_in_pairs(pair,
                    config.getint('slack', 'backtrack_days'), 5)

            if not exist_recent_messages:
                try:
                    logger.debug(f"Sending reminder to: {pair}")

                    slack_connector.send_message_to_pairs(pair, _(":slightly_smiling_face: hi <!here>, have you "
                                                                  "had the chance to schedule a time for a :coffee: "
                                                                  "and a chat?"))

                    reminder_sent += 1
                except GroupwareCommunicationError as e:
                    logger.warning("Error sending message to the pair (%s), OpenCoffee will continue to the next send\
                                   operation: %s", pair, e)

                time.sleep(0.25)

        logger.info(f"Sent {reminder_sent} {utils.get_plural_or_singular(reminder_sent, 'reminder', 'reminders')}")

import argparse
import configparser
import gettext
import importlib.metadata
import json
import logging
import sys
import time

from datetime import datetime
from typing import Callable
from tqdm import tqdm
from opencoffee.errors import GroupwareCommunicationError
from opencoffee.messaging_api_wrappers.generic_messaging_api_wrapper import GenericMessagingApiWrapper
from opencoffee.messaging_api_wrappers.slack_wrapper import SlackWrapper
from opencoffee.pair_generator_algorithms.simple_generator_algorithm import SimpleGeneratorAlgorithm
from opencoffee.pair_generator_algorithms.max_distance_algorithm_generator_algorithm import MaxDistanceGeneratorAlgorithm
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

    logger.info("OpenCoffee BEGIN: %s", str(sys.argv[1:]))

    if config.getboolean('GENERIC', 'test_mode'):
        logger.warning('Test mode: ON - NO MESSAGES WILL BE SENT')

    slack_wrapper = SlackWrapper(config['slack']['api_token'], config.getboolean('GENERIC', 'test_mode'))

    if args.action == 'invitation':
        manage_invitation_action(config, logger, slack_wrapper, _, args)
    elif args.action == 'reminder':
        manage_reminder_action(config, logger, slack_wrapper, _, args)

    logger.info("OpenCoffee END: %s", str(sys.argv[1:]))


def manage_invitation_action(config: configparser.ConfigParser, logger: logging.Logger,
                             slack_wrapper: GenericMessagingApiWrapper, _: Callable[..., str],
                             args: argparse.Namespace) -> None:
    """ Manage the invitation action.
        The function takes all the members in a channel and randomly pairs
        them up. """

    try:
        users = slack_wrapper.get_users_from_channel(config['slack']['channel_id'], config['slack']['ignore_users'])
    except GroupwareCommunicationError as e:
        logger.critical("Error getting list of users: %s", e)
        sys.exit(-1)

    # Generate random pairs from the user's list -->
    generator_algorithm_type = config.get('slack', 'generator_algorithm_type', fallback = 'simple')
    pair_generator = None

    if generator_algorithm_type == 'simple':
        pair_generator = SimpleGeneratorAlgorithm(config, logger)
    elif generator_algorithm_type == 'max-distance':
        pair_generator = MaxDistanceGeneratorAlgorithm(config, logger)
    else:
        print(f"Invalid {generator_algorithm_type} generator algorithm type")
        sys.exit(-1)

    pair_generator.compute_pairs_from_users(users, slack_wrapper)

    pairs = pair_generator.get_pairs()
    ignored = pair_generator.get_ignored()
    # <-- generate random pairs from the user's list

    logger.debug('Generated the pairs: %s', pairs)
    logger.info(f"The {utils.get_plural_or_singular(len(ignored), 'user', 'users')} {ignored} "
                f"{utils.get_plural_or_singular(len(ignored), 'has', 'have')} been excluded from this round!")

    # Send the invitation message to all the pairs, applying a small
    # delay between each send to avoid encountering an API rate limit.
    for pair in tqdm(pairs, desc = 'Send invitation messages'):
        try:
            slack_wrapper.send_message_to_pairs(pair, _(":wave: hi <!here>, sometimes it can be difficult to "
                            "know all your colleagues, so I take care of creating opportunities for a :coffee: "
                            "and a chat among all members in <#%s>.\n"
                            "What do you think about a time to get to know each other better?")
                % (config['slack']['channel_id']))
        except GroupwareCommunicationError as e:
            logger.warning("Error sending message to the pair (%s), OpenCoffee will continue to the next send\
                           operation: %s", pair, e)

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
                           slack_wrapper: GenericMessagingApiWrapper, _: Callable[..., str],
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
        logger.critical('No valid file history found!')
        sys.exit(0)
    else:
        logger.info(f"Working on: {file_history}")
    # <-- retrieval of the latest pairs history

    with open(f"{config['GENERIC']['history_path']}{file_history}", 'r', encoding = 'utf-8') as file:

        reminder_sent = 0
        pairs = json.load(file)

        # Send the reminder message to all the pairs, applying a small
        # delay between each send to avoid encountering an API rate limit.
        for pair in tqdm(pairs, desc = 'Send reminder messages'):

            # An heuristic is applied to determine whether to send a reminder
            # message or not, by checking if users have exchanged at least 4
            # messages in the recent period.
            #
            # ATTENTION: The value 5 is used to include the message sent by
            # OpenCoffee in the count.
            exist_recent_messages = slack_wrapper.exist_recent_message_exchange_in_pairs(pair,
                    config.getint('slack', 'backtrack_days'), 5)

            if not exist_recent_messages:
                try:
                    logger.debug(f"Sending reminder to: {pair}")

                    slack_wrapper.send_message_to_pairs(pair, _(":slightly_smiling_face: hi <!here>, have you "
                                                                  "had the chance to schedule a time for a :coffee: "
                                                                  "and a chat?"))

                    reminder_sent += 1
                except GroupwareCommunicationError as e:
                    logger.warning("Error sending message to the pair (%s), OpenCoffee will continue to the next send\
                                   operation: %s", pair, e)

                time.sleep(0.25)

        logger.info(f"Sent {reminder_sent} {utils.get_plural_or_singular(reminder_sent, 'reminder', 'reminders')}, "
                    f"{(reminder_sent/len(pairs)) * 100}% of total")

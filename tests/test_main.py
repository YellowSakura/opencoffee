import argparse
import configparser
import gettext
import json
import logging
import os

from helper_messaging_api_wrapper import HelperMessagingApiWrapper

import opencoffee


# Create of helper configuration file -->
helper_config = configparser.ConfigParser()
helper_config['GENERIC'] = {
    'test_mode': 'True',
    'history_path': 'tests/logs/'
}
helper_config['slack'] = {
    'channel_id': 'C0000000000',
    'ignore_users': '',
    'backtrack_days': '180',
    'backtrack_max_attempts': '3'
}
# <-- create of helper configuration file

# Other helper variables
helper_logger = logging.getLogger(__name__)
helper_wrapper = HelperMessagingApiWrapper()
_ = gettext.gettext
helper_args = argparse.Namespace(conf = 'pytest.ini')


def test_manage_invitation_action():
    """ Test function for the invitation action """

    # Test simple algorithm -->
    opencoffee.manage_invitation_action(helper_config, helper_logger, helper_wrapper, _, helper_args)

    tail_file_name = opencoffee.utils.get_history_filename(helper_config.getboolean('GENERIC', 'test_mode'),
                                                           helper_args.conf)
    file_history = opencoffee.utils.get_most_recent_file_history(helper_config['GENERIC']['history_path'],
                                                                 tail_file_name)

    if file_history is None:
        assert False

    with open(f"{helper_config['GENERIC']['history_path']}{file_history}", 'r', encoding = 'utf-8') as file:
        data = json.load(file)

        # The value 2 is related to the fact that the HelperMessagingApiWrapper
        # returns exactly four users.
        assert len(data) == 2
    # <-- test simple algorithm

    # Test max-distance algorithm -->
    helper_config['GENERIC']['generator_algorithm_type'] = 'max-distance'

    opencoffee.manage_invitation_action(helper_config, helper_logger, helper_wrapper, _, helper_args)

    tail_file_name = opencoffee.utils.get_history_filename(helper_config.getboolean('GENERIC', 'test_mode'),
                                                           helper_args.conf)
    file_history = opencoffee.utils.get_most_recent_file_history(helper_config['GENERIC']['history_path'],
                                                                 tail_file_name)

    if file_history is None:
        assert False

    with open(f"{helper_config['GENERIC']['history_path']}{file_history}", 'r', encoding = 'utf-8') as file:
        data = json.load(file)

        # The value 2 is related to the fact that the HelperMessagingApiWrapper
        # returns exactly four users.
        assert len(data) == 2
    # <-- test max-distance algorithm


def test_manage_reminder_action():
    """ Test function for the reminder action """

    opencoffee.manage_reminder_action(helper_config, helper_logger, helper_wrapper, _, helper_args)

    assert True

    # Cleaning up temporary file created by the invitation action -->
    tail_file_name = opencoffee.utils.get_history_filename(helper_config.getboolean('GENERIC', 'test_mode'),
                                                           helper_args.conf)
    file_history = opencoffee.utils.get_most_recent_file_history(helper_config['GENERIC']['history_path'],
                                                                 tail_file_name)

    os.remove(f"{helper_config['GENERIC']['history_path']}{file_history}")
    # <-- cleaning up temporary file created by the invitation action

import configparser
import logging
import os
import sys

from logging.handlers import TimedRotatingFileHandler


def check_config_values(config: configparser.ConfigParser) -> None:
    """ Check the coherence of the config file before using it """

    try:
        config.getboolean('GENERIC', 'test_mode')
        config.get('GENERIC', 'history_path')
        config.getboolean('log', 'log_to_file')
        config.get('log', 'log_path')
        config.getint('log', 'log_level')
        config.get('slack', 'api_token')
        config.get('slack', 'channel_id')
        config.get('slack', 'ignore_users')
        config.getint('slack', 'backtrack_days')
        config.getint('slack', 'backtrack_max_attempts')
    except configparser.NoOptionError as e:
        print(f"Invalid value in the config file for the key: {str(e)}", file = sys.stderr)
        sys.exit(-1)


def get_logger(config: configparser.ConfigParser) -> logging.Logger:
    """ Configuration of the logger used by OpenCoffee, including management
        and parameterization of the configuration file. """

    logger = logging.getLogger(__name__)
    logger.setLevel(config.getint('log', 'log_level'))

    # Stream handler (stdout)
    console_handler = logging.StreamHandler()

    # Log format
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    # File handler
    if config.getboolean('log', 'log_to_file'):
        file_handler = TimedRotatingFileHandler(config['log']['log_path'] + '/logs.log', when = 'midnight')

        # Log format
        file_handler.setFormatter(formatter)

        # Add the file handlers to the logger
        logger.addHandler(file_handler)

    return logger


def get_history_filename(is_test_mode: bool, current_config_file: str, suffix: str = '') -> str:
    """ Generate a standard file name containing the JSON of the various users
        subject to message sending.

        Parameters:
            - is_test_mode (bool): Indicates whether the current execution is in test mode.
            - current_config_file (str): Current configuration file.
            - suffix (str): Optional, specifies the suffix of the file, for example, using
                a timestamp.

        Returns:
            str: Name of the file that can be used for storing data.
    """

    tail_file_name = suffix
    if tail_file_name:
        tail_file_name += '-'

    # The reference to the current configuration file is appended, so that
    # we have different dedicated files for configuration.
    tail_file_name += f"{current_config_file}"

    # Mark the test mode file at the end of it, ensuring a robust condition
    # to recognize it.
    if is_test_mode:
        tail_file_name += '-TESTMODE'

    return f"{tail_file_name}.json"


def get_most_recent_file_history(history_path: str, tail_file_name: str) -> str | None:
    """ The function retrieves the most recent pairs file located in
        the history_path directory and with a filename ending in
        tail_file_name.

        ATTENTION: An heuristic based on the file name is implemented,
        leveraging the lexicographic sorting of file names, the most
        recent file that matches the expected pattern is retrieved.

        Parameters:
            - history_path (str): The path to search for the file.
            - tail_file_name (str): The end-of-file pattern.

        Return:
            str | None: The file name or None if no file is available.
        """

    # Heuristic application on the filename through listing and reverse
    # sorting.
    dir_list = os.listdir(history_path)
    dir_list.sort(reverse=True)

    for filename in dir_list:
        if filename.endswith(tail_file_name):
            return filename

    return None


def get_plural_or_singular(count: int, word_singular: str, world_plural: str):
    """ Get the singular or plural form of a word based on the count.

        Parameters:
            - word_singular (str): The singular word to get the form of.
            - world_plural (str): The plural word to get the form of.
            - count (int): The count associated with the word.

        Returns:
            str: The singular or plural form of the word based on the count.
    """

    if count == 1:
        return word_singular

    return world_plural

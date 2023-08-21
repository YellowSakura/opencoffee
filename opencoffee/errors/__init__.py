from slack_sdk.errors import SlackApiError


class GroupwareCommunicationError(SlackApiError):
    """ Specializing SlackApiError exception to handle an error, potentially
        within a cross-technology communication mechanism. """

    def __init__(self, message, response):
        self.response = response
        super(SlackApiError, self).__init__(message)

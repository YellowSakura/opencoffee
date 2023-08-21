from typing import Iterable
from typing import Tuple
from opencoffee.services.genericserviceconnector import GenericServiceConnector

class HelperConnector(GenericServiceConnector):
    """ Helper function with dummy values to simulate the actual invocation of a
        communication service. """

    def get_users_from_channel(self, channel_id: str, ignore_users: Iterable[str]) -> list[str]:
        return ['U0000000001', 'U0000000002', 'U0000000003', 'U0000000004', 'U0000000005']

    def send_message_to_pairs(self, pair: Tuple[str, ...], message: str) -> None:
        return

    def exist_recent_message_exchange_in_pairs(self, pair: Tuple[str, ...], backtrack_days: int,
                                               limit: int = 1) -> bool:
        return False

from datetime import datetime, time
from keystone import exception
from oslo_log import log

LOG = log.getLogger(__name__)


class TimeBasedMFARule:
    """
    Encapsulates time-based behavioral MFA logic.
    Determines if MFA should be required based on login time
    compared to allowed working hours.
    """

    def __init__(self, working_hours_start: str = "08:00", working_hours_end: str = "20:00"):
        """
        Initialize with working hours boundaries (HH:MM format).
        """
        self.working_hours_start = self._parse_time(working_hours_start)
        self.working_hours_end = self._parse_time(working_hours_end)
        LOG.debug(f"TimeBasedMFARule initialized with working hours: {self.working_hours_start} - {self.working_hours_end}")

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """
        Parse time from HH:MM string format.
        Raises ValidationError if format is invalid.
        """
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            LOG.error(f"Invalid time format: {time_str}. Expected HH:MM.")
            raise exception.ValidationError(attribute='working_hours', target='TimeBasedMFARule')

    def is_login_outside_working_hours(self, login_time: datetime) -> bool:
        """
        Check if login time falls outside configured working hours.

        Args:
            login_time (datetime): Timestamp of the login event.

        Returns:
            bool: True if MFA is required (login outside working hours), False otherwise.
        """
        login_t = login_time.time()
        LOG.debug(f"Checking login time {login_t} against allowed window {self.working_hours_start} - {self.working_hours_end}")

        # Normal case: working hours do not span midnight
        if self.working_hours_start <= self.working_hours_end:
            if login_t < self.working_hours_start or login_t > self.working_hours_end:
                LOG.info("Login outside working hours detected, MFA required.")
                return True
            return False

        # Case where working hours span midnight (e.g., 22:00 to 06:00)
        else:
            if self.working_hours_end < login_t < self.working_hours_start:
                LOG.info("Login outside working hours detected (spanning midnight), MFA required.")
                return True
            return False

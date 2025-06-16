from datetime import datetime, timedelta
from keystone import exception
from oslo_log import log

LOG = log.getLogger(__name__)

class FailedLoginRateRule:
    """
    Implements a failed login rate limiter.
    If 5 failed attempts occur within 5 minutes, lock the account for 15 minutes,
    then require MFA on the next login attempt.
    """

    def __init__(self, fail_threshold=5, fail_window_minutes=5, lock_duration_minutes=15):
        self.fail_threshold = fail_threshold
        self.fail_window = timedelta(minutes=fail_window_minutes)
        self.lock_duration = timedelta(minutes=lock_duration_minutes)
        self.failed_attempts = {}  # user_id -> list of datetime objects of failed attempts
        self.locked_accounts = {}  # user_id -> lock expiry datetime

    def _cleanup_old_attempts(self, user_id, current_time):
        attempts = self.failed_attempts.get(user_id, [])
        # Keep only attempts within fail_window
        self.failed_attempts[user_id] = [
            ts for ts in attempts if current_time - ts <= self.fail_window
        ]

    def record_failed_attempt(self, user_id, timestamp):
        """
        Record a failed login attempt at a specific timestamp.

        Args:
            user_id (str): User identifier.
            timestamp (datetime): Time of failed attempt.
        """
        attempts = self.failed_attempts.setdefault(user_id, [])
        attempts.append(timestamp)
        self._cleanup_old_attempts(user_id, timestamp)

        if len(self.failed_attempts[user_id]) >= self.fail_threshold:
            self.lock_account(user_id, timestamp)

    def lock_account(self, user_id, lock_start_time):
        self.locked_accounts[user_id] = lock_start_time + self.lock_duration
        self.failed_attempts[user_id].clear()
        LOG.info(f"Account {user_id} locked until {self.locked_accounts[user_id]} due to too many failed attempts.")

    def is_locked(self, user_id, current_time):
        expiry = self.locked_accounts.get(user_id)
        if expiry and current_time < expiry:
            return True
        elif expiry and current_time >= expiry:
            del self.locked_accounts[user_id]
        return False

    def evaluate_login_attempt(self, user_id, timestamp, success):
        """
        Evaluate a login attempt and determine MFA requirement or lock status.

        Args:
            user_id (str): User identifier.
            timestamp (datetime): Timestamp of the login attempt.
            success (bool): Whether the login was successful.

        Returns:
            str: 'locked' if account is currently locked,
                 'require_mfa' if login after lock expiry requires MFA,
                 'ok' otherwise.
        """
        if self.is_locked(user_id, timestamp):
            LOG.warning(f"Login attempt for locked account {user_id} at {timestamp}")
            return 'locked'

        if not success:
            self.record_failed_attempt(user_id, timestamp)
            return 'ok'

        # Successful login after lock expiry means require MFA
        if user_id in self.locked_accounts:
            LOG.info(f"User {user_id} login after lock expiry, MFA required.")
            del self.locked_accounts[user_id]  # Clear lock after MFA is done
            return 'require_mfa'

        # On successful login without lock history
        self.failed_attempts.pop(user_id, None)
        return 'ok'

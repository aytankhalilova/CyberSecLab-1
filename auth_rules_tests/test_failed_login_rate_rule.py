import unittest
from datetime import datetime, timedelta
import re
from oslo_log import log

LOG = log.getLogger(__name__)

class FailedLoginRateRule:
    def __init__(self, fail_threshold=5, fail_window_minutes=5, lock_duration_minutes=15):
        self.fail_threshold = fail_threshold
        self.fail_window = timedelta(minutes=fail_window_minutes)
        self.lock_duration = timedelta(minutes=lock_duration_minutes)
        self.failed_attempts = {}  # username -> list of datetime of failed attempts
        self.locked_accounts = {}  # username -> lock expiry datetime

    def _cleanup_old_attempts(self, username, current_time):
        attempts = self.failed_attempts.get(username, [])
        self.failed_attempts[username] = [
            ts for ts in attempts if current_time - ts <= self.fail_window
        ]

    def record_failed_attempt(self, username, timestamp):
        attempts = self.failed_attempts.setdefault(username, [])
        attempts.append(timestamp)
        self._cleanup_old_attempts(username, timestamp)

        if len(self.failed_attempts[username]) >= self.fail_threshold:
            self.lock_account(username, timestamp)

    def lock_account(self, username, lock_start_time):
        self.locked_accounts[username] = lock_start_time + self.lock_duration
        self.failed_attempts[username].clear()
        LOG.info(f"Account {username} locked until {self.locked_accounts[username]} due to too many failed attempts.")

    def is_locked(self, username, current_time):
        expiry = self.locked_accounts.get(username)
        if expiry and current_time < expiry:
            return True
        elif expiry and current_time >= expiry:
            del self.locked_accounts[username]
        return False

    def evaluate_login_attempt(self, username, timestamp, success):
        if self.is_locked(username, timestamp):
            LOG.warning(f"Login attempt for locked account {username} at {timestamp}")
            return 'locked'

        if not success:
            self.record_failed_attempt(username, timestamp)
            return 'ok'

        # Successful login after lock expiry means require MFA
        if username in self.locked_accounts:
            LOG.info(f"User {username} login after lock expiry, MFA required.")
            del self.locked_accounts[username]
            return 'require_mfa'

        self.failed_attempts.pop(username, None)
        return 'ok'


class KeystoneLogParser:
    """
    Parses logs and extracts username, timestamp, and login success/failure.
    Change the regex to match your exact log line format.
    """
    LOG_LINE_PATTERN = re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) .* '
        r'username=(?P<username>\S+) .* '
        r'authentication (?P<result>failed|succeeded)'
    )

    @staticmethod
    def parse_log_line(line):
        match = KeystoneLogParser.LOG_LINE_PATTERN.search(line)
        if not match:
            return None
        timestamp_str = match.group('timestamp')
        username = match.group('username')
        result = match.group('result')
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
        success = (result == 'succeeded')
        return username, timestamp, success

    @staticmethod
    def parse_log_file(filepath):
        attempts = []
        with open(filepath, 'r') as f:
            for line in f:
                parsed = KeystoneLogParser.parse_log_line(line)
                if parsed:
                    attempts.append(parsed)
        return attempts


class TestFailedLoginRateRule(unittest.TestCase):

    def setUp(self):
        self.rule = FailedLoginRateRule()

    def test_using_keystone_logs(self):
        log_file_path = '/opt/stack/logs/keystone.log'  # Change to your log file path
        attempts = KeystoneLogParser.parse_log_file(log_file_path)

        for username, timestamp, success in attempts:
            if username == 'test_user':   # Filter by username, not user_id
                result = self.rule.evaluate_login_attempt(username, timestamp, success)
                print(f'{timestamp} - User {username} login {"success" if success else "failed"} -> {result}')


if __name__ == '__main__':
    unittest.main()

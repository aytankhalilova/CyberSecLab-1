import unittest
from your_module import TimeBasedMFARule  # adjust this import
from oslo_log import log

LOG = log.getLogger(__name__)

class OpenStackLogParser:
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path

    def get_login_times_for_user(self, username: str):
        login_times = []
        with open(self.log_file_path, "r") as f:
            for line in f:
                if username in line and "logged in" in line:
                    try:
                        timestamp_str = line.split(" ")[0] + " " + line.split(" ")[1]
                        from datetime import datetime
                        login_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        login_times.append(login_time)
                    except Exception:
                        LOG.error(f"Failed to parse timestamp from log line: {line.strip()}")
        return login_times


class TestTimeBasedMFARuleWithLogs(unittest.TestCase):
    def setUp(self):
        self.mfa_rule = TimeBasedMFARule()
        self.log_parser = OpenStackLogParser("/opt/stack/logs/keystone.log")  # real path
        self.username = "test_user"

    def test_mfa_rule_on_logins(self):
        login_times = self.log_parser.get_login_times_for_user(self.username)
        self.assertTrue(len(login_times) > 0, "No login entries found for test_user in logs.")

        for login_time in login_times:
            is_outside = self.mfa_rule.is_login_outside_working_hours(login_time)
            status = "require_mfa" if is_outside else "ok"
            print(f"[{login_time.strftime('%Y-%m-%d %H:%M:%S')}] Login attempt: 200, {status}")

            if login_time.time() < self.mfa_rule.working_hours_start or login_time.time() > self.mfa_rule.working_hours_end:
                self.assertTrue(is_outside)
            else:
                self.assertFalse(is_outside)


if __name__ == "__main__":
    unittest.main()

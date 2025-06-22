# Custom Risk-Based Authentication Rules

This plugin extends Keystone authentication by adding **Risk-Based Authentication (RBA)** rules that dynamically require Multi-Factor Authentication (MFA) or temporarily block access based on user behavior and context.

---

## Rules Overview

### 1. Failed Login Rate Rule with Temporary Block and MFA

**What is it?**

This rule monitors the number of failed login attempts over a recent time window (e.g., 5 minutes).  

- If the number of failed attempts exceeds a configured threshold, the user is **temporarily blocked for 15 minutes** (no further login allowed during this block).  
- After the block period ends, subsequent login attempts will **require MFA** to continue.  

This approach helps prevent brute force and credential stuffing attacks by first blocking suspicious activity, then enforcing additional verification.

---

### 2. Time-Based MFA Rule

**What is it?**

This rule enforces MFA based on the login time relative to configured working hours.  

- If the user logs in **outside allowed working hours** (e.g., before 08:00 or after 20:00), MFA is required.  

This protects your system by adding an extra layer of verification during off-hours when risks are generally higher.

---

## Integration Guide

### 1. Add rule files

Place your rule implementations in your plugin directory:

```
keystone_rba_plugin/auth/plugins/failed_login_rate_rule.py
keystone_rba_plugin/auth/plugins/time_based_MFA_rule.py
```

### 2. Import rules in `rba.py`

```python
from keystone_rba_plugin.auth.plugins.failed_login_rate_rule import LoginRateRule
from keystone_rba_plugin.auth.plugins.time_based_MFA_rule import TimeBasedMFARule
```
### 3. Initialize rules in the `RiskBasedAuthentication` class

Modify the constructor in `rba.py` to initialize both rules:

```python
class RiskBasedAuthentication(base.AuthMethodHandler):
    def __init__(self, *args, **kwargs):
        super(RiskBasedAuthentication, self).__init__(*args, **kwargs)
        self.manager = manager.RBAManager()
        self.login_rate_rule = LoginRateRule(
            max_attempts=5,
            window_seconds=300,
            block_duration_seconds=900  # 15 minutes block
        )
        self.time_based_mfa_rule = TimeBasedMFARule(
            working_hours_start="08:00",
            working_hours_end="20:00"
        )
```
### 4. Update the `authenticate` method to apply rules with block logic

```python
def authenticate(self, auth_payload):
    user_info = core.RBAUserInfo.create(auth_payload, METHOD_NAME)
    login_time = datetime.utcnow()

    # Check if user is currently blocked due to login rate
    if self.login_rate_rule.is_block_active(user_info.user_id, login_time):
        raise exception.Forbidden(_('User is temporarily blocked due to excessive failed login attempts. Please try again later.'))

    # Check login rate rule to decide if block or MFA required
    if self.login_rate_rule.is_rate_exceeded(user_info.user_id, login_time):
        self.login_rate_rule.activate_block(user_info.user_id, login_time)  # start block period
        raise exception.Forbidden(_('User is temporarily blocked due to excessive failed login attempts. Please try again later.'))

    # After block period, require MFA on further attempts
    if self.login_rate_rule.is_mfa_required(user_info.user_id, login_time):
        raise exception.AdditionalAuthRequired(_('MFA required due to prior excessive login attempts.'))

    # Check time-based MFA rule
    if self.time_based_mfa_rule.is_login_outside_working_hours(login_time):
        raise exception.AdditionalAuthRequired(_('MFA required due to login outside working hours.'))

    try:
        result = self.manager.authenticate(
            user_id=user_info.user_id,
            features=user_info.features,
            passcode=user_info.passcode)

        status = result is None
        return base.AuthHandlerResponse(
            status=status,
            response_body=result,
            response_data={'user_id': user_info.user_id})

    except AssertionError:
        raise exception.Unauthorized(_('Invalid credentials.'))
```

### 5. Apply Rule Changes in DevStack Keystone

Run database migrations (if needed):

   ```bash
   keystone-manage db_sync
   ```

 Restart the Keystone service inside DevStack:

```bash
sudo systemctl restart devstack@keystone
```

---
## Summary

By combining the **Failed Login Rate Rule** with temporary blocking and MFA enforcement and the **Time-Based MFA Rule**, your Keystone RBA plugin:

- Temporarily blocks users who exceed failed login attempts, limiting brute force attacks.
- Requires MFA after the block period for continued attempts.
- Requires MFA for logins occurring outside configured working hours.

This layered approach improves security by adapting authentication requirements to both suspicious behavior and contextual risk factors.

For detailed security testing results, see the [Security Test Analysis](Tests.md) document.



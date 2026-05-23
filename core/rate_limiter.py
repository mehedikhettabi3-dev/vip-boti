import time

_user_message_times = {}


def is_spam(phone_number):
    try:
        now = time.time()
        timestamps = _user_message_times.get(phone_number, [])
        cutoff = now - 5
        timestamps = [t for t in timestamps if t > cutoff]
        timestamps.append(now)
        _user_message_times[phone_number] = timestamps
        if len(timestamps) > 3:
            return True
        return False
    except Exception:
        return False

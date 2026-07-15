import time


# user_id: timestamp when cooldown ends
cooldowns = {}


def get_remaining(user_id):
    if user_id not in cooldowns:
        return 0

    remaining = cooldowns[user_id] - time.time()

    if remaining <= 0:
        del cooldowns[user_id]
        return 0

    return int(remaining)


def set_cooldown(user_id, seconds):
    cooldowns[user_id] = time.time() + seconds
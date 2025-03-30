logs = []


def add_log(message):
    print(message)
    logs.append(message)


def clear_logs():
    logs.clear()


def get_logs():
    return logs

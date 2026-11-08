"""Group 11: branch-dependent targets. Both branches are executed by main()."""


class Sender:
    def send(self):
        return "sender"


class Mailer:
    def send(self):
        return "mailer"


def on_a():
    return "a"


def on_b():
    return "b"


def deliver(urgent):
    channel = Sender()
    if urgent:
        channel = Mailer()
    return channel.send()  # expect: cg_cases.g11_conflict.Sender.send, cg_cases.g11_conflict.Mailer.send


def notify(flag):
    handler = on_a if flag else on_b
    return handler()  # expect: cg_cases.g11_conflict.on_a, cg_cases.g11_conflict.on_b


class Dispatcher:
    def __init__(self, urgent):
        self.backend = Sender()
        if urgent:
            self.backend = Mailer()

    def run(self):
        return self.backend.send()  # expect: cg_cases.g11_conflict.Sender.send, cg_cases.g11_conflict.Mailer.send


def main():
    deliver(True)
    deliver(False)
    notify(True)
    notify(False)
    Dispatcher(True).run()
    return Dispatcher(False).run()

"""Group 10: not statically knowable. Tools must not claim a definite target."""
import importlib


class Plugin:
    def start(self):
        return "start"

    def stop(self):
        return "stop"


def secret_helper():
    return "secret"


def main(action="start", module_name="cg_cases.helpers"):
    plugin = Plugin()
    method = getattr(plugin, action)  # expect: external
    method()  # expect: unknown
    fn = eval("secret_helper")  # expect: external
    fn()  # expect: unknown
    module = importlib.import_module(module_name)  # expect: external
    return module.measure("abc")  # expect: unknown

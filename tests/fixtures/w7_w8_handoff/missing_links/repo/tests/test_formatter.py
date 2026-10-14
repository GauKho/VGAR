import importlib


def test_label_trim():
    module = importlib.import_module("formatter")
    function_name = "".join(("la", "bel"))
    target = getattr(module, function_name)
    assert target(" a ") == "a"


def test_label_empty():
    module = importlib.import_module("formatter")
    function_name = "".join(("la", "bel"))
    target = getattr(module, function_name)
    assert target("") == ""

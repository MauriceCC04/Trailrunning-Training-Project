import importlib

def test_imports() -> None:
    for mod in (
        "trailtraining.cli",
        "trailtraining.config",
        "trailtraining.pipelines.intervals",
        "trailtraining.data.combine",
    ):
        importlib.import_module(mod)
import subprocess


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["trailtraining", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_top_level_help() -> None:
    result = run_cli("-h")
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


def test_cli_subcommand_help() -> None:
    commands = [
        ["doctor", "-h"],
        ["auth-strava", "-h"],
        ["run-all", "-h"],
        ["forecast", "-h"],
        ["coach", "-h"],
        ["eval-coach", "-h"],
    ]

    for cmd in commands:
        result = run_cli(*cmd)
        assert (
            result.returncode == 0
        ), f"{cmd} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

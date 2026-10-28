import pytest


@pytest.fixture(autouse=True)
def _quiet_ci_environment(monkeypatch):
    """On GitHub, these variables make the code write into the run's summary page and talk to GitHub.
    Tests must never do that, or they flood the summary with fake results."""
    for name in ('GITHUB_STEP_SUMMARY', 'GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_REF_NAME'):
        monkeypatch.delenv(name, raising=False)

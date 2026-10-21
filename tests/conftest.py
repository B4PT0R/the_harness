from tests.fixtures.browser import bundle as bundle, page as page


import pytest


@pytest.fixture(autouse=True)
def no_live_quota_backend(monkeypatch):
    # Application lifespan tests must NEVER authenticate or redeem real credits.
    def offline():
        raise RuntimeError("quota backend disabled in tests")
    monkeypatch.setattr("the_harness.quota.sdk_client", offline)

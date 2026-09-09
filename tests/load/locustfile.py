"""Locust-only entrypoint; never import this module from the main pytest process."""

import itertools
import os
import random

from locust import HttpUser, events, task
from locust.exception import StopUser
from support import WEIGHTS, LoadError, WorkflowRunner, load_settings

try:
    SETTINGS = load_settings(
        os.environ.get("COYOTE3_LOAD_CONFIG", ""), os.environ.get("COYOTE3_LOAD_CREDENTIALS", "")
    )
except LoadError as exc:
    raise SystemExit(str(exc)) from None

ACCOUNTS = itertools.cycle(SETTINGS["accounts"])


@events.test_start.add_listener
def check_host(environment, **kwargs):
    """Reject host overrides that disagree with the pinned target.

    Args:
        environment: Locust runtime with optional CLI or web host override.
        **kwargs: Additional Locust event metadata.
    """
    if environment.host and environment.host.rstrip("/") != SETTINGS["target_url"]:
        environment.process_exit_code = 1
        environment.runner.quit()


class SyntheticUser(HttpUser):
    """Run one explicitly assigned persona using its own login cookie session."""

    host = SETTINGS["target_url"]

    def wait_time(self):
        """Return a bounded randomized think time in seconds."""
        return random.uniform(*SETTINGS["think_time_seconds"])

    def on_start(self):
        """Create a runner, validate the deployment, and log in once."""
        self.client.trust_env = False
        self.workflow = WorkflowRunner(
            self.client, SETTINGS, next(ACCOUNTS), self.environment.events.request.fire
        )
        try:
            self.workflow.start()
        except LoadError:
            self.environment.process_exit_code = 1
            self.environment.runner.quit()
            raise StopUser from None

    @task
    def execute(self):
        """Choose a weighted assigned workflow; failures remain visible in metrics."""
        flows = self.workflow.account["workflows"]
        flow = random.choices(flows, weights=[WEIGHTS[f] for f in flows], k=1)[0]
        try:
            self.workflow.run(flow)
        except LoadError:
            self.environment.process_exit_code = 1

    def on_stop(self):
        """Invalidate the session when the virtual user stops."""
        if hasattr(self, "workflow"):
            try:
                self.workflow.stop()
            except LoadError:
                self.environment.process_exit_code = 1

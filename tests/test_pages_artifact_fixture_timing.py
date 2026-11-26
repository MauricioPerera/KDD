"""Observe the Pages fixture with real Node and loopback HTTP."""

import unittest
from unittest.mock import patch

from tests import test_pages_artifact_delivery as delivery


PROBE = r"""
{
  const timeout = AbortSignal.timeout;
  AbortSignal.timeout = ms => {
    console.log('KDD_TIMING native-timeout ' + ms);
    return timeout(ms);
  };
  const fetch = globalThis.fetch;
  const timers = require('node:timers');
  const promises = require('node:timers/promises');
  const pause = promises.setTimeout;
  let dispatched = false;
  let requestSignal;
  const beforeDispatch = realTimer => (...args) => {
    if (!dispatched) console.log('KDD_TIMING startup timer');
    return realTimer(...args);
  };
  globalThis.setTimeout = beforeDispatch(globalThis.setTimeout);
  timers.setTimeout = beforeDispatch(timers.setTimeout);
  promises.setTimeout = (delay, value, options) => {
    if (!dispatched) console.log('KDD_TIMING startup timer');
    console.log('KDD_TIMING ' + (options?.signal === requestSignal ? 'wait' : 'wrong signal'));
    return pause(delay, value, options);
  };
  globalThis.fetch = async (input, options) => {
    requestSignal = options.signal;
    options.signal.addEventListener('abort', () => console.log('KDD_TIMING abort'), {once: true});
    await pause(__STARTUP_DELAY__);
    dispatched = true;
    console.log('KDD_TIMING request');
    const response = await fetch(input, options);
    console.log('KDD_TIMING headers');
    const json = response.json.bind(response);
    response.json = async () => {
      const body = await json();
      console.log('KDD_TIMING body');
      return body;
    };
    return response;
  };
}
"""


def observe(case, run, *, startup_delay=0):
    events = []
    execute = case.execute

    def recorded(*args, **kwargs):
        result, requests = execute(*args, **kwargs)
        events.extend(line.removeprefix("KDD_TIMING ") for line in result.stdout.splitlines()
                      if line.startswith("KDD_TIMING "))
        return result, requests

    prelude = PROBE.replace("__STARTUP_DELAY__", str(startup_delay))
    with patch.object(delivery, "NODE_RUNNER", prelude + delivery.NODE_RUNNER):
        with patch.object(case, "execute", recorded):
            run()
    return events


class PagesArtifactFixtureTiming(unittest.TestCase):
    def test_regular_http_lookup_uses_the_native_production_deadline(self):
        case = delivery.PagesArtifactDelivery("test_existing_exact_artifact_is_ready_on_first_request")
        events = observe(case, case.debug)
        self.assertEqual(events, ["native-timeout 30000", "request", "headers", "body"])

    def test_empty_list_abort_waits_for_http_even_after_slow_startup(self):
        case = delivery.PagesArtifactDelivery("test_empty_service_eventually_times_out")
        events = observe(case, case.debug, startup_delay=1200)
        self.assertEqual(events, ["request", "headers", "body", "abort", "wait"])

    def test_pending_body_abort_follows_headers_even_after_slow_startup(self):
        case = delivery.PagesArtifactDelivery("test_deadline_aborts_a_slow_lookup_before_accepting_its_result")
        events = observe(case, case.debug, startup_delay=1200)
        self.assertEqual(events, ["request", "headers", "abort"])


if __name__ == "__main__":
    unittest.main()

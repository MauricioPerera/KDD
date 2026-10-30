"""Exercise the real timeout fixture with a delayed but successful light process."""
import io
import unittest
from unittest import mock

from tests import test_contract_resource_scheduling as resource


class ResourceTimeoutMargin(unittest.TestCase):
    def test_timeout_fixture_preserves_other_command_with_slow_start(self):
        probe = resource.PROBE.replace(
            "else: time.sleep(.03)",
            "elif name=='a': time.sleep(2)\nelse: time.sleep(.03)",
        )
        self.assertNotEqual(probe, resource.PROBE)
        with mock.patch.object(resource, 'PROBE', probe):
            case = resource.ContractResourceScheduling(
                'test_exclusive_timeout_preserves_timeout_and_executes_the_rest')
            outcome = unittest.TextTestRunner(stream=io.StringIO()).run(case)
        self.assertTrue(outcome.wasSuccessful(),
                        f'fixture failures: {outcome.failures}; errors: {outcome.errors}')

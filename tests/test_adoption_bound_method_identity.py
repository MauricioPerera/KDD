"""Exercise the callable that an approved unittest case actually binds."""

from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_adoption_oracle_pass_identity as adoption


MARK_SOURCE = adoption.ORACLE_SOURCE.replace(
    "stream.write(self.id() +", "stream.write(value.strip().lower() +",
)
FACTORY = """def selected_case(name):
    generated = type('Generated', (Product,), {{
        '__module__': __name__, 'test_selected': getattr(Product, 'test_' + name)
    }})
    return generated('test_selected')


"""
CONDITIONAL = """def selected_case(name):
    class Generated(Product):
        if name == 'first':
            def test_selected(self):
                self.check_label(' First ')
        else:
            def test_selected(self):
                self.check_label(' Second ')
    return Generated('test_selected')


"""


CALLBACK = """def selected_case(name):
    import sys

    class Generated(Product):
        def __getattribute__(self, attribute):
            if attribute == 'test_selected':
                caller = sys._getframe(1)
                selected = name if caller.f_code is unittest.TestCase.run.__code__ else 'first'
                return getattr(self, 'test_' + selected)
            return super().__getattribute__(attribute)

    return Generated('test_selected')


"""
GENERATED_CODE = """def selected_case(name):
    namespace = {{}}
    definition = 'def test_selected(self): self.check_label(%r)' % name
    exec(compile(definition, __file__, 'exec'), namespace)
    generated = type('Generated', (Product,), {{
        '__module__': __name__, 'test_selected': namespace['test_selected']
    }})
    return generated('test_selected')


"""
WRAPPED = """def selected_case(name):
    from functools import wraps

    method = getattr(Product, 'test_' + name)

    @wraps(method, assigned=(), updated=())
    def selected(self):
        return method(self)

    generated = type('Generated', (Product,), {{
        '__module__': __name__, 'test_selected': selected
    }})
    return generated('test_selected')


"""

def selected_source(factory):
    return MARK_SOURCE.replace("def load_tests(", factory + "def load_tests(").replace(
        "Product('test_' + name) for name", "selected_case(name) for name",
    )


class AdoptionBoundMethodTests(unittest.TestCase):
    def setUp(self):
        self.consumer = adoption.AdoptionOraclePassIdentityTests()
        self.addCleanup(self.consumer.doCleanups)
        self.consumer.setUp()
        recorder = Path('scripts/unittest_oracle_runner.py')
        project = Path(__file__).resolve().parents[1]
        self.assertEqual((self.consumer.seed / recorder).read_bytes(), (project / recorder).read_bytes())

    def approve(self, selections, factory=FACTORY):
        with patch.object(adoption, "ORACLE_SOURCE", selected_source(factory)):
            return self.consumer.approve(selections)

    def assert_rejected(self, run, diagnostic):
        record = self.consumer.evidence(run)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertEqual((record["stage"], record["result"]), ("oracle", "fail"))
        self.assertIn(diagnostic, (run.stdout + run.stderr + record["error"]).lower())
        self.assertNotIn("oracle_inventory", record)

    def test_two_distinct_methods_bound_to_one_label_are_rejected(self):
        approved = self.approve((("first",), ("second",)))
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "different case ids")

    def test_two_distinct_definitions_with_one_qualified_name_are_rejected(self):
        approved = self.approve((("first",), ("second",)), CONDITIONAL)
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "different case ids")

    def test_receipt_records_the_callable_unittest_actually_invokes(self):
        approved = self.approve((("first",), ("second",)), CALLBACK)
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "different case ids")

    def test_distinct_generated_code_with_the_same_source_position_is_rejected(self):
        approved = self.approve((("first",), ("second",)), GENERATED_CODE)
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "different case ids")

    def test_decorated_cases_with_different_wrapped_definitions_are_rejected(self):
        approved = self.approve((("first",), ("second",)), WRAPPED)
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "different case ids")

    def test_recreated_classes_with_the_same_method_keep_the_public_label(self):
        approved = self.approve((("first",),) * 4)
        hosted = self.consumer.run_step(approved)
        terminal = self.consumer.invoke("entry", self.consumer.root / ".kdd/validate.py",
                                        ("--approved-ref", approved))
        expected = [{"path": adoption.CONTRACT, "ids": ["tests.test_product.Generated.test_selected"]}]
        self.assertEqual(self.consumer.marks(), ["first"] * 4)
        for run in (hosted, terminal):
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            record = self.consumer.evidence(run)
            self.assertEqual(record["oracle_inventory"], expected)
            self.assertEqual(record["verified_kdd_sha"], self.consumer.first)
            self.assertEqual(record["oracle_passes"], [1, 1])

    def test_two_definitions_cannot_credit_a_duplicate_public_label(self):
        approved = self.approve((("first", "second"),) * 2)
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "second"])
        self.assert_rejected(run, "duplicate")

    def test_label_only_second_receipt_cannot_replace_callable_evidence(self):
        self.consumer.modify_gate_receipt("""    from pathlib import Path
    import json
    status = main(sys.argv)
    receipt = Path(sys.argv[sys.argv.index('--oracle-receipt') + 1])
    if not status and receipt.name == 'oracle-pass-2.json':
        document = json.loads(receipt.read_text(encoding='utf-8'))
        document['contracts'][0]['ids'] = ['tests.test_product.Generated.test_selected']
        receipt.write_text(json.dumps(document), encoding='utf-8')
    sys.exit(status)""")
        approved = self.approve((("first",), ("first",)))
        run = self.consumer.run_step(approved)
        self.assertEqual(self.consumer.marks(), ["first", "first"])
        self.assert_rejected(run, "bound-method fingerprint")

import copy
from pluma.core.baseclasses.reporterbase import ReporterBase
import pytest
from pytest import fixture
from unittest.mock import MagicMock

from pluma.cli import TestsConfig, Configuration, TestsProvider, TestsConfigError

MINIMAL_CONFIG = {
    'sequence': []
}


class MockTestsProvider(TestsProvider):
    def display_name(self):
        return 'Mock provider'

    def configuration_key(self):
        return 'mock_tests'

    def all_tests(self, config: Configuration):
        return []


def make_mock_reporter_type(name, config_keys, raise_ex=False):
    class MockReporterType(ReporterBase):
        def __init__(self, arg):
            self.arg = arg

        @staticmethod
        def configuration_key() -> str:
            return name

        @staticmethod
        def display_name() -> str:
            return 'Mock Reporter'

        @classmethod
        def from_configuration(cls, config) -> ReporterBase:
            if raise_ex:
                raise RuntimeError('uh oh')
            return cls({key: config.pop(bool, key) for key in config_keys})
    return MockReporterType


@fixture
def minimal_testsconfig():
    return TestsConfig(Configuration(copy.deepcopy(MINIMAL_CONFIG)),
                       [MockTestsProvider()])


def test_TestsConfig_init_should_accept_list_of_providers():
    TestsConfig(Configuration(copy.deepcopy(MINIMAL_CONFIG)),
                [MockTestsProvider()])


def test_TestsConfig_init_should_accept_single_provider():
    TestsConfig(Configuration(copy.deepcopy(
        MINIMAL_CONFIG)), MockTestsProvider())


def test_TestsConfig_init_should_error_if_passed_no_config():
    with pytest.raises(ValueError):
        TestsConfig(None, MockTestsProvider())


def test_TestsConfig_init_should_error_if_passed_dict_for_config():
    with pytest.raises(ValueError):
        TestsConfig(None, MockTestsProvider())


def test_TestsConfig_init_should_error_if_passed_no_provider():
    with pytest.raises(ValueError):
        TestsConfig(Configuration(MINIMAL_CONFIG), None)


def test_TestsConfig_init_should_error_if_passed_empty_list_of_providers():
    with pytest.raises(ValueError):
        TestsConfig(Configuration(MINIMAL_CONFIG), [])


def test_TestsConfig__supported_actions_should_return_key_provider_dict():
    provider1_key1 = 'abc'
    provider1_key2 = 'def'
    provider1 = MagicMock(MockTestsProvider)
    provider1.configuration_key.return_value = [provider1_key1, provider1_key2]

    provider2_key = '123'
    provider2 = MagicMock(MockTestsProvider)
    provider2.configuration_key.return_value = provider2_key

    actions = TestsConfig._supported_actions([provider1, provider2])
    assert actions == {
        provider1_key1: provider1,
        provider1_key2: provider1,
        provider2_key: provider2
    }


def test_TestsConfig___supported_actions_should_error_on_already_registered_key():
    action_key = 'same_key'
    provider1 = MagicMock(MockTestsProvider)
    provider1.configuration_key.return_value = ['abc', action_key]

    provider2 = MagicMock(MockTestsProvider)
    provider2.configuration_key.return_value = action_key

    with pytest.raises(TestsConfigError):
        TestsConfig._supported_actions([provider1, provider2])


def test_TestsConfig_tests_from_action_should_return_all_tests():
    provider = MagicMock(MockTestsProvider)
    all_tests_return = [1, 2, 3]
    action_key = 'some_key'
    provider.configuration_key.return_value = action_key
    provider.all_tests.return_value = all_tests_return

    tests = TestsConfig.tests_from_action(action_key, {'some': 'settings'},
                                          {action_key: provider})
    assert tests == all_tests_return


def test_TestsConfig_tests_from_action_should_error_if_action_unsupported():
    with pytest.raises(TestsConfigError):
        TestsConfig.tests_from_action('abc', {'some': 'settings'}, {'def': MockTestsProvider})


def test_TestConfig__generate_reporters_generates_reporters_from_configuration():
    types = [make_mock_reporter_type('reporter_a', []), make_mock_reporter_type('reporter_b', [])]
    config = Configuration({
        'reporters': {
            'reporter_a': None,
            'reporter_b': None
        }
    })
    reporta, reportb = TestsConfig._generate_reporters(config, types)
    assert reporta.configuration_key() == 'reporter_a'
    assert reportb.configuration_key() == 'reporter_b'


def test_TestConfig_generate_reporters_generates_reporter_from_configuration_with_reporter_config():
    types = [
        make_mock_reporter_type('reporter_a', ['config_a', 'config_b']),
        make_mock_reporter_type('reporter_b', [])
    ]
    config = Configuration({
        'reporters': {
            'reporter_a': {'config_a': True, 'config_b': False},
            'reporter_b': None
        }
    })
    reporta, reportb = TestsConfig._generate_reporters(config, types)
    assert reporta.configuration_key() == 'reporter_a'
    assert reportb.configuration_key() == 'reporter_b'
    assert reporta.arg == {'config_a': True, 'config_b': False}


def test_TestConfig_generate_reporters_generates_no_reporters_from_no_configuration():
    types = [make_mock_reporter_type('reporter_a', []), make_mock_reporter_type('reporter_b', [])]
    config = Configuration({})
    reporters = TestsConfig._generate_reporters(config, types)
    assert reporters == []


def test_TestConfig_generate_reporters_throws_error_with_invalid_reporter():
    types = [make_mock_reporter_type('reporter_a', [])]
    config = Configuration({
        'reporters': {
            'invalid_reporter': None
        }
    })
    with pytest.raises(TestsConfigError):
        TestsConfig._generate_reporters(config, types)


def test_TestConfig_generate_reporters_throws_error_with_too_few_config_keys():
    types = [make_mock_reporter_type('reporter_a', ['config_a'])]
    config = Configuration({
        'reporters': {
            'reporter_a': None
        }
    })
    with pytest.raises(TestsConfigError):
        TestsConfig._generate_reporters(config, types)


def test_TestConfig_generate_reporters_throws_error_if_reporter_throws_error():
    types = [make_mock_reporter_type('reporter_a', [], raise_ex=True)]
    config = Configuration({
        'reporters': {
            'reporter_a': None
        }
    })
    with pytest.raises(TestsConfigError):
        TestsConfig._generate_reporters(config, types)


def test_TestConfig_generates_reporters():
    types = [make_mock_reporter_type('reporter_a', [])]
    config = copy.deepcopy(MINIMAL_CONFIG)
    config['settings'] = {
        'reporters': {
            'reporter_a': None
        }
    }
    test_config = TestsConfig(Configuration(config), [MockTestsProvider()], reporters=types)
    assert len(test_config.reporters) == 1
    assert test_config.reporters[0].configuration_key() == 'reporter_a'

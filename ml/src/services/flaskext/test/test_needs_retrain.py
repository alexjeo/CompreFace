from http import HTTPStatus

import pytest

from src.services.async_task_manager.async_task_manager import TrainingTaskManagerBase, TaskStatus
from src.services.flaskext.needs_retrain import needs_retrain
from src.services.utils.pytestutils import Expando

pytest.x = Expando()


@pytest.fixture
def task_manager(mocker):
    task_manager = TrainingTaskManagerMock()
    mocker.patch('src.services.flaskext.needs_retrain.get_training_task_manager', return_value=task_manager)
    return task_manager


@pytest.fixture
def client_with_retrain_endpoint(app):
    pytest.x.ENDPOINT_EXECUTED = False
    pytest.x.ENDPOINT_EXECUTED_BEFORE_TRAINING = False

    @app.route('/endpoint', methods=['POST'])
    @needs_retrain
    def endpoint():
        pytest.x.ENDPOINT_EXECUTED = True
        return 'success-body', HTTPStatus.OK

    return app.test_client()


@pytest.fixture
def client_with_retrain_endpoint_error(app):
    pytest.x.ENDPOINT_EXECUTED = False
    pytest.x.ENDPOINT_EXECUTED_BEFORE_TRAINING = False

    @app.route('/endpoint', methods=['POST'])
    @needs_retrain
    def endpoint():
        raise Exception

    return app.test_client()


@pytest.mark.parametrize("retrain_arg, retrain_action",
                         [(None, 'force'), ('yes', 'yes'), ('force', 'force'), ('no', 'no')])
def test__given_retrain_flag_value__when_requesting__then_starts_or_skips_retraining_depending_on_value(
        client_with_retrain_endpoint, mocker, retrain_arg, retrain_action, task_manager):
    pass

    endpoint = f'/endpoint?retrain={retrain_arg}' if retrain_arg is not None else '/endpoint'
    res = client_with_retrain_endpoint.post(endpoint, headers={'X-Api-Key': 'test-api-key'})

    assert res.status_code == HTTPStatus.OK, res.json
    assert res.data.decode() == 'success-body'
    assert task_manager.started_training_str == retrain_action


@pytest.mark.parametrize("retrain_arg", ['', 'unknown_value'])
def test__given_retrain_flag_empty_or_unknown_value__when_requesting__then_returns_error(
        client_with_retrain_endpoint, mocker, retrain_arg, task_manager):
    pass

    res = client_with_retrain_endpoint.post(f'/endpoint?retrain={retrain_arg}', headers={'X-Api-Key': 'test-api-key'})

    assert res.status_code == HTTPStatus.BAD_REQUEST, res.json
    assert task_manager.started_training_str == 'no'
    assert res.json['message'] == "400 Bad Request: 'retrain' parameter accepts only 'YES, NO, FORCE' values"


def test__when_requesting__then_starts_retraining_only_after_endpoint_function(
        client_with_retrain_endpoint, task_manager):
    pass

    res = client_with_retrain_endpoint.post('/endpoint?retrain=force', headers={'X-Api-Key': 'test-api-key'})

    assert res.status_code == HTTPStatus.OK, res.json
    assert res.data.decode() == 'success-body'
    assert pytest.x.ENDPOINT_EXECUTED_BEFORE_TRAINING


def test__given_retrain_decorator_raises_error__requesting__then_does_not_call_endpoint_function(
        client_with_retrain_endpoint, task_manager):
    pass

    res = client_with_retrain_endpoint.post('/endpoint?retrain=unknown-value', headers={'X-Api-Key': 'test-api-key'})

    assert res.status_code == HTTPStatus.BAD_REQUEST, res.json
    assert res.json['message'] == "400 Bad Request: 'retrain' parameter accepts only 'YES, NO, FORCE' values"
    assert not pytest.x.ENDPOINT_EXECUTED


def test__given_endpoint_raises_error__when_requesting__then_skips_retraining(
        client_with_retrain_endpoint_error, task_manager):
    pass

    res = client_with_retrain_endpoint_error.post('/endpoint', headers={'X-Api-Key': 'test-api-key'})

    assert res.status_code == HTTPStatus.INTERNAL_SERVER_ERROR, res.json
    assert task_manager.started_training_str == 'no'


class TrainingTaskManagerMock(TrainingTaskManagerBase):
    def __init__(self):
        self.status = TaskStatus.IDLE
        self.started_training_str = 'no'
        self.aborted_training = False

    def get_status(self, api_key) -> TaskStatus:
        return self.status

    def start_training(self, api_key, force=False):
        pytest.x.ENDPOINT_EXECUTED_BEFORE_TRAINING = pytest.x.ENDPOINT_EXECUTED
        self.started_training_str = 'force' if force else 'yes'

    def abort_training(self, api_key):
        self.aborted_training = False

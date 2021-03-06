import datetime
import unittest2
from datetime import timedelta
from mock import Mock, patch
from cfn_sphere.aws.cloudformation.template import CloudFormationTemplate
from cfn_sphere.aws.cloudformation.stack import CloudFormationStack
from cfn_sphere.aws.cloudformation.cfn_api import CloudFormation
from boto.cloudformation.stack import StackEvent, Stack
from boto.resultset import ResultSet


class CloudFormationApiTests(unittest2.TestCase):

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_get_stacks_correctly_calls_aws_api(self, cloudformation_mock):
        stacks = [Mock(spec=Stack), Mock(spec=Stack)]

        result = ResultSet()
        result.extend(stacks)
        result.next_token = None
        cloudformation_mock.connect_to_region.return_value.describe_stacks.return_value = result

        cfn = CloudFormation()
        self.assertListEqual(stacks, cfn.get_stacks())

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_get_stacks_correctly_aggregates_paged_results(self, cloudformation_mock):
        stacks_1 = [Mock(spec=Stack), Mock(spec=Stack)]
        stacks_2 = [Mock(spec=Stack), Mock(spec=Stack)]

        result_1 = ResultSet()
        result_1.extend(stacks_1)
        result_1.next_token = "my-next-token"

        result_2 = ResultSet()
        result_2.extend(stacks_2)
        result_2.next_token = None

        cloudformation_mock.connect_to_region.return_value.describe_stacks.side_effect = [result_1, result_2]

        cfn = CloudFormation()
        self.assertListEqual(stacks_1 + stacks_2, cfn.get_stacks())

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_wait_for_stack_event_returns_on_start_event_with_valid_timestamp(self, cloudformation_mock):
        timestamp = datetime.datetime.utcnow()

        template_mock = Mock(spec=CloudFormationTemplate)
        template_mock.url = "foo.yml"
        template_mock.get_template_body_dict.return_value = {}

        event = StackEvent()
        event.resource_type = "AWS::CloudFormation::Stack"
        event.resource_status = "UPDATE_IN_PROGRESS"
        event.event_id = "123"
        event.timestamp = timestamp

        stack_events_mock = Mock()
        stack_events_mock.describe_stack_events.return_value = [event]

        cloudformation_mock.connect_to_region.return_value = stack_events_mock

        cfn = CloudFormation()
        event = cfn.wait_for_stack_events("foo", "UPDATE_IN_PROGRESS",
                                          timestamp - timedelta(seconds=10),
                                          timeout=10)

        self.assertEqual(timestamp, event.timestamp)

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_wait_for_stack_event_returns_on_update_complete(self, cloudformation_mock):
        timestamp = datetime.datetime.utcnow()

        template_mock = Mock(spec=CloudFormationTemplate)
        template_mock.url = "foo.yml"
        template_mock.get_template_body_dict.return_value = {}

        event = StackEvent()
        event.resource_type = "AWS::CloudFormation::Stack"
        event.resource_status = "UPDATE_COMPLETE"
        event.event_id = "123"
        event.timestamp = timestamp

        stack_events_mock = Mock()
        stack_events_mock.describe_stack_events.return_value = [event]

        cloudformation_mock.connect_to_region.return_value = stack_events_mock

        cfn = CloudFormation()
        cfn.wait_for_stack_events("foo", "UPDATE_COMPLETE", timestamp - timedelta(seconds=10),
                                  timeout=10)

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_wait_for_stack_event_raises_exception_on_rollback(self, cloudformation_mock):
        timestamp = datetime.datetime.utcnow()

        template_mock = Mock(spec=CloudFormationTemplate)
        template_mock.url = "foo.yml"
        template_mock.get_template_body_dict.return_value = {}

        event = StackEvent()
        event.resource_type = "AWS::CloudFormation::Stack"
        event.resource_status = "ROLLBACK_COMPLETE"
        event.event_id = "123"
        event.timestamp = timestamp

        stack_events_mock = Mock()
        stack_events_mock.describe_stack_events.return_value = [event]

        cloudformation_mock.connect_to_region.return_value = stack_events_mock

        cfn = CloudFormation()
        with self.assertRaises(Exception):
            cfn.wait_for_stack_events("foo", ["UPDATE_COMPLETE"], timestamp - timedelta(seconds=10),
                                      timeout=10)

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation')
    def test_wait_for_stack_event_raises_exception_on_update_failure(self, cloudformation_mock):
        timestamp = datetime.datetime.utcnow()

        template_mock = Mock(spec=CloudFormationTemplate)
        template_mock.url = "foo.yml"
        template_mock.get_template_body_dict.return_value = {}

        event = StackEvent()
        event.resource_type = "AWS::CloudFormation::Stack"
        event.resource_status = "UPDATE_FAILED"
        event.event_id = "123"
        event.timestamp = timestamp

        stack_events_mock = Mock()
        stack_events_mock.describe_stack_events.return_value = [event]

        cloudformation_mock.connect_to_region.return_value = stack_events_mock

        cfn = CloudFormation()
        with self.assertRaises(Exception):
            cfn.wait_for_stack_events("foo", ["UPDATE_COMPLETE"], timestamp - timedelta(seconds=10),
                                      timeout=10)

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation.connect_to_region')
    @patch('cfn_sphere.aws.cloudformation.cfn_api.CloudFormation.wait_for_stack_action_to_complete')
    def test_create_stack_calls_cloudformation_api_properly(self, _, cloudformation_mock):
        stack = Mock(spec=CloudFormationStack)
        stack.name = "stack-name"
        stack.get_parameters_list.return_value = [('a', 'b')]
        stack.parameters = {}
        stack.template = Mock(spec=CloudFormationTemplate)
        stack.template.name = "template-name"
        stack.template.get_template_json.return_value = {'key': 'value'}
        stack.timeout = 42

        cfn = CloudFormation()
        cfn.create_stack(stack)

        cloudformation_mock.return_value.create_stack.assert_called_once_with('stack-name',
                                                                              capabilities=['CAPABILITY_IAM'],
                                                                              parameters=[('a', 'b')],
                                                                              template_body={'key': 'value'})

    @patch('cfn_sphere.aws.cloudformation.cfn_api.cloudformation.connect_to_region')
    @patch('cfn_sphere.aws.cloudformation.cfn_api.CloudFormation.wait_for_stack_action_to_complete')
    def test_update_stack_calls_cloudformation_api_properly(self, _, cloudformation_mock):
        stack = Mock(spec=CloudFormationStack)
        stack.name = "stack-name"
        stack.get_parameters_list.return_value = [('a', 'b')]
        stack.parameters = {}
        stack.template = Mock(spec=CloudFormationTemplate)
        stack.template.name = "template-name"
        stack.template.get_template_json.return_value = {'key': 'value'}
        stack.timeout = 42

        cfn = CloudFormation()
        cfn.update_stack(stack)

        cloudformation_mock.return_value.update_stack.assert_called_once_with('stack-name',
                                                                              capabilities=['CAPABILITY_IAM'],
                                                                              parameters=[('a', 'b')],
                                                                              template_body={'key': 'value'})

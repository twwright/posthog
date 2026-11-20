import uuid

import pytest
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings

import responses
import temporalio.worker
from parameterized import parameterized
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from posthog.models import Organization, ProxyRecord
from posthog.tasks.proxy import reconcile_proxy, reconcile_proxy_root_redirect
from posthog.temporal.proxy_service.common import (
    RecordDeletedException,
    SendProxyCreatedEmailInputs,
    UpdateProxyRecordInputs,
)
from posthog.temporal.proxy_service.create import (
    CreateCloudflareProxyInputs,
    CreateManagedProxyInputs,
    CreateManagedProxyWorkflow,
    ScheduleMonitorJobInputs,
    WaitForDNSRecordsInputs,
    create_cloudflare_custom_hostname,
)


def _make_mock_activities(failing_activity: str | None = None, error_type: str = "NonRetriableException"):
    """Create mock activities for the Cloudflare create-proxy workflow path.

    Args:
        failing_activity: Name of the activity that should raise. None means all succeed.
        error_type: The exception type string for the ApplicationError.
    """
    status_updates: list[str] = []

    def _maybe_raise(activity_name: str):
        if activity_name == failing_activity:
            raise ApplicationError(
                f"Mock error in {activity_name}",
                type=error_type,
                non_retryable=True,
            )

    @activity.defn(name="wait_for_dns_records")
    async def mock_wait_for_dns(inputs: WaitForDNSRecordsInputs):
        pass

    @activity.defn(name="activity_update_proxy_record")
    async def mock_update_record(inputs: UpdateProxyRecordInputs):
        status_updates.append(inputs.status)

    @activity.defn(name="create_cloudflare_custom_hostname")
    async def mock_create_hostname(inputs: CreateCloudflareProxyInputs):
        _maybe_raise("create_cloudflare_custom_hostname")

    @activity.defn(name="wait_for_cloudflare_certificate")
    async def mock_wait_cert(inputs: CreateCloudflareProxyInputs):
        _maybe_raise("wait_for_cloudflare_certificate")

    @activity.defn(name="activity_send_proxy_created_email")
    async def mock_send_email(inputs: SendProxyCreatedEmailInputs):
        _maybe_raise("activity_send_proxy_created_email")

    @activity.defn(name="schedule_monitor_job")
    async def mock_schedule_monitor(inputs: ScheduleMonitorJobInputs):
        pass

    activities = [
        mock_wait_for_dns,
        mock_update_record,
        mock_create_hostname,
        mock_wait_cert,
        mock_send_email,
        mock_schedule_monitor,
    ]

    return activities, status_updates


def _make_workflow_inputs():
    return CreateManagedProxyInputs(
        organization_id=uuid.uuid4(),
        proxy_record_id=uuid.uuid4(),
        domain="test.example.com",
        target_cname="target.example.com",
    )


@override_settings(
    CLOUDFLARE_PROXY_BASE_CNAME="proxy.example.com",
    CLOUDFLARE_ZONE_ID="test-zone",
    CLOUDFLARE_API_TOKEN="test-token",
    CLOUDFLARE_PROXY_KV_NAMESPACE_ID="test-kv",
    CLOUDFLARE_ACCOUNT_ID="test-account",
)
class TestCloudflareProxyActivation(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(name="Proxy test")
        self.record = ProxyRecord.objects.create(
            organization=self.organization,
            domain="analytics.example.com",
            target_cname="test.proxy.example.com",
            status=ProxyRecord.Status.VALID,
            root_redirect_url="https://www.example.com/",
        )
        self.hostnames_url = "https://api.cloudflare.com/client/v4/zones/test-zone/custom_hostnames"
        self.kv_url = "https://api.cloudflare.com/client/v4/accounts/test-account/storage/kv/namespaces/test-kv/values/analytics.example.com"
        self.hostname = {
            "id": "test-hostname",
            "hostname": self.record.domain,
            "status": "active",
            "ssl": {"status": "active"},
        }

    def _cloudflare(self, http: responses.RequestsMock, *, exists: bool) -> None:
        http.get(self.hostnames_url, json={"success": True, "result": [self.hostname] if exists else []})
        http.post(self.hostnames_url, json={"success": True, "result": self.hostname})
        http.delete(self.hostnames_url + "/test-hostname", json={"success": True, "result": {}})
        http.put(self.kv_url, json={"success": True, "result": {}})
        http.delete(self.kv_url, json={"success": True, "result": {}})

    @parameterized.expand(
        [
            (True, False),
            (None, False),
            (False, True),
            (False, None),
            (True, False, ProxyRecord.Status.DELETING),
            (True, False, ProxyRecord.Status.WAITING),
        ]
    )
    def test_activation_changes_reconcile_after_commit_and_keep_customer_settings(
        self, previous: bool | None, current: bool | None, status: str = ProxyRecord.Status.VALID
    ) -> None:
        self.record.status = status
        self.record.save(update_fields=["status"])
        Organization.objects.filter(pk=self.organization.pk).update(is_active=previous)
        self.organization.is_active = current

        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            self._cloudflare(http, exists=current is False)
            with patch("posthog.tasks.proxy.reconcile_proxy.delay", side_effect=reconcile_proxy.run):
                with self.captureOnCommitCallbacks(execute=True):
                    self.organization.save(update_fields=["is_active"])
                    self.assertEqual(len(http.calls), 0)

            self.assertEqual(
                [(call.request.method, call.request.url.split("?")[0]) for call in http.calls],
                [
                    ("GET", self.hostnames_url),
                    ("DELETE", self.hostnames_url + "/test-hostname"),
                    ("DELETE", self.kv_url),
                ]
                if current is False
                else [("GET", self.hostnames_url), ("POST", self.hostnames_url), ("PUT", self.kv_url)],
            )
            if current is not False:
                self.assertEqual(http.calls[-1].request.body, b"https://www.example.com/")

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, status)
        self.assertEqual(self.record.root_redirect_url, "https://www.example.com/")

    @parameterized.expand([(False, True), (False, False), (True, False), (True, True), (None, False)])
    def test_delayed_job_uses_current_organization_state(self, current: bool | None, exists: bool) -> None:
        Organization.objects.filter(pk=self.organization.pk).update(is_active=current)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            self._cloudflare(http, exists=exists)
            reconcile_proxy.run(str(self.organization.pk), str(self.record.pk))
            self.assertEqual(http.calls[-1].request.method, "DELETE" if current is False else "PUT")

    @parameterized.expand([("unchanged",), ("unrelated_save",), ("rollback",)])
    def test_saves_without_committed_activation_changes_do_not_reconcile(self, scenario: str) -> None:
        with patch("posthog.tasks.proxy.reconcile_proxy.delay", side_effect=reconcile_proxy.run):
            with responses.RequestsMock() as http:
                with self.captureOnCommitCallbacks(execute=True):
                    if scenario == "rollback":
                        with transaction.atomic():
                            self.organization.is_active = False
                            self.organization.save(update_fields=["is_active"])
                            transaction.set_rollback(True)
                    elif scenario == "unrelated_save":
                        self.organization.is_active = False
                        self.organization.save(update_fields=["name"])
                    else:
                        self.organization.save(update_fields=["is_active"])
                self.assertEqual(len(http.calls), 0)

    @parameterized.expand([("legacy",), ("deleting",), ("missing",), ("waiting",), ("timed_out",)])
    def test_reconciliation_does_not_provision_unavailable_records(self, scenario: str) -> None:
        record_id = str(self.record.pk)
        if scenario == "missing":
            self.record.delete()
        elif scenario == "legacy":
            self.record.target_cname = "legacy.example.com"
            self.record.save(update_fields=["target_cname"])
        else:
            self.record.status = scenario
            self.record.save(update_fields=["status"])
        with responses.RequestsMock() as http:
            reconcile_proxy.run(str(self.organization.pk), record_id)
            self.assertEqual(len(http.calls), 0)

    def test_deprovisioning_is_idempotent_when_hostname_is_already_absent(self) -> None:
        Organization.objects.filter(pk=self.organization.pk).update(is_active=False)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            self._cloudflare(http, exists=False)
            reconcile_proxy.run(str(self.organization.pk), str(self.record.pk))
            self.assertEqual([call.request.method for call in http.calls], ["GET", "DELETE"])
        self.assertTrue(ProxyRecord.objects.filter(pk=self.record.pk).exists())

    def test_redirect_job_does_not_restore_an_inactive_organization_redirect(self) -> None:
        Organization.objects.filter(pk=self.organization.pk).update(is_active=False)
        with responses.RequestsMock() as http:
            reconcile_proxy_root_redirect.run(str(self.record.pk))
            self.assertEqual(len(http.calls), 0)

    async def test_creation_without_root_redirect_does_not_write_kv(self) -> None:
        await ProxyRecord.objects.filter(pk=self.record.pk).aupdate(root_redirect_url=None)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            self._cloudflare(http, exists=False)
            await create_cloudflare_custom_hostname(
                CreateCloudflareProxyInputs(
                    organization_id=self.organization.pk,
                    proxy_record_id=self.record.pk,
                    domain=self.record.domain,
                )
            )
            self.assertEqual([call.request.method for call in http.calls], ["GET", "POST"])

    async def test_creation_does_not_provision_a_deactivated_organization(self) -> None:
        await Organization.objects.filter(pk=self.organization.pk).aupdate(is_active=False)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            self._cloudflare(http, exists=False)
            with self.assertRaises(RecordDeletedException):
                await create_cloudflare_custom_hostname(
                    CreateCloudflareProxyInputs(
                        organization_id=self.organization.pk,
                        proxy_record_id=self.record.pk,
                        domain=self.record.domain,
                    )
                )
            self.assertEqual([call.request.method for call in http.calls], ["GET", "DELETE"])


@pytest.mark.django_db(transaction=True)
@patch("posthog.temporal.proxy_service.create.use_cloudflare_proxy", return_value=True)
class TestCreateManagedProxyWorkflowErrorHandling:
    @pytest.mark.parametrize(
        "failing_activity",
        [
            "create_cloudflare_custom_hostname",
            "wait_for_cloudflare_certificate",
        ],
    )
    async def test_activity_error_sets_erroring_status(self, _mock_cloudflare, failing_activity):
        activities, status_updates = _make_mock_activities(failing_activity=failing_activity)
        task_queue = str(uuid.uuid4())

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[CreateManagedProxyWorkflow],
                activities=activities,
                workflow_runner=temporalio.worker.UnsandboxedWorkflowRunner(),
            ):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        CreateManagedProxyWorkflow.run,
                        _make_workflow_inputs(),
                        id=str(uuid.uuid4()),
                        task_queue=task_queue,
                    )

        assert "erroring" in status_updates

    async def test_record_deleted_exception_returns_without_error(self, _mock_cloudflare):
        activities, status_updates = _make_mock_activities(
            failing_activity="create_cloudflare_custom_hostname",
            error_type="RecordDeletedException",
        )
        task_queue = str(uuid.uuid4())

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[CreateManagedProxyWorkflow],
                activities=activities,
                workflow_runner=temporalio.worker.UnsandboxedWorkflowRunner(),
            ):
                await env.client.execute_workflow(
                    CreateManagedProxyWorkflow.run,
                    _make_workflow_inputs(),
                    id=str(uuid.uuid4()),
                    task_queue=task_queue,
                )

        assert "erroring" not in status_updates

    async def test_happy_path_sets_valid_status(self, _mock_cloudflare):
        activities, status_updates = _make_mock_activities()
        task_queue = str(uuid.uuid4())

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[CreateManagedProxyWorkflow],
                activities=activities,
                workflow_runner=temporalio.worker.UnsandboxedWorkflowRunner(),
            ):
                await env.client.execute_workflow(
                    CreateManagedProxyWorkflow.run,
                    _make_workflow_inputs(),
                    id=str(uuid.uuid4()),
                    task_queue=task_queue,
                )

        assert "valid" in status_updates
        assert "erroring" not in status_updates

    async def test_email_failure_does_not_fail_workflow(self, _mock_cloudflare):
        activities, status_updates = _make_mock_activities(failing_activity="activity_send_proxy_created_email")
        task_queue = str(uuid.uuid4())

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[CreateManagedProxyWorkflow],
                activities=activities,
                workflow_runner=temporalio.worker.UnsandboxedWorkflowRunner(),
            ):
                await env.client.execute_workflow(
                    CreateManagedProxyWorkflow.run,
                    _make_workflow_inputs(),
                    id=str(uuid.uuid4()),
                    task_queue=task_queue,
                )

        assert "valid" in status_updates
        assert "erroring" not in status_updates

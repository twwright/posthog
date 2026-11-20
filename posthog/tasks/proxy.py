from django.db import DatabaseError

import requests
from celery import shared_task
from redis.exceptions import RedisError

from posthog.managed_proxy import cloudflare_proxy_lock, reconcile_cloudflare_proxy
from posthog.models import ProxyRecord
from posthog.scoping_audit import skip_team_scope_audit
from posthog.tasks.utils import CeleryQueue
from posthog.temporal.proxy_service.cloudflare import CloudflareAPIError, update_cloudflare_proxy_root_redirect


@shared_task(
    ignore_result=True,
    queue=CeleryQueue.DEFAULT.value,
    autoretry_for=(CloudflareAPIError, DatabaseError, requests.RequestException, RedisError),
    retry_backoff=30,
    retry_backoff_max=3600,
    max_retries=10,
)
@skip_team_scope_audit
def reconcile_proxy_root_redirect(proxy_record_id: str) -> None:
    with cloudflare_proxy_lock(proxy_record_id):
        record = ProxyRecord.objects.filter(id=proxy_record_id).exclude(organization__is_active=False).first()
        if record is None:
            return

        update_cloudflare_proxy_root_redirect(record.domain, record.root_redirect_url)


@shared_task(
    ignore_result=True,
    queue=CeleryQueue.DEFAULT.value,
    autoretry_for=(CloudflareAPIError, DatabaseError, requests.RequestException, RedisError),
    retry_backoff=30,
    retry_backoff_max=3600,
    max_retries=10,
)
@skip_team_scope_audit
def reconcile_proxy(organization_id: str, proxy_record_id: str) -> None:
    reconcile_cloudflare_proxy(organization_id, proxy_record_id)

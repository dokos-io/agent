# @dokos: S3-compatible offsite storage needs ENDPOINT_URL on every boto3 client
from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from agent.database_server import DatabaseServer
from agent.site import Site
from agent.snapshot_recovery import SnapshotRecovery

ENDPOINT_URL = "https://s3.example.dokos.cloud"


def offsite(region=None, endpoint_url=ENDPOINT_URL):
    auth = {"ACCESS_KEY": "access", "SECRET_KEY": "secret"}
    if region:
        auth["REGION"] = region
    if endpoint_url:
        auth["ENDPOINT_URL"] = endpoint_url
    return {"bucket": "backups", "auth": auth, "path": "prefix"}


def bare(cls):
    return cls.__new__(cls)


class TestS3EndpointUrl(unittest.TestCase):
    def assert_endpoint(self, upload, expected=ENDPOINT_URL):
        for region in (None, "fr-par"):
            with self.subTest(region=region), patch("boto3.client", return_value=MagicMock()) as client:
                upload(offsite(region=region, endpoint_url=expected))
                client.assert_called_once()
                self.assertEqual(client.call_args.kwargs["endpoint_url"], expected)

    def test_site_backup_upload(self):
        site = bare(Site)
        self.assert_endpoint(lambda o: Site.upload_offsite_backup.__wrapped__(site, {}, o, True))

    def test_site_backup_upload_without_endpoint_uses_aws(self):
        site = bare(Site)
        self.assert_endpoint(
            lambda o: Site.upload_offsite_backup.__wrapped__(site, {}, o, True), expected=None
        )

    def test_binlog_upload(self):
        server = bare(DatabaseServer)
        self.assert_endpoint(lambda o: DatabaseServer.upload_binlogs_to_s3.__wrapped__(server, [], o))

    def test_audit_log_upload(self):
        server = bare(DatabaseServer)
        with TemporaryDirectory() as pending:
            server.audit_log_pending_directory = pending
            self.assert_endpoint(lambda o: DatabaseServer.upload_audit_logs_to_s3.__wrapped__(server, o))

    def test_snapshot_recovery_upload(self):
        recovery = bare(SnapshotRecovery)
        self.assert_endpoint(
            lambda o: SnapshotRecovery.upload_backup_files_to_s3.__wrapped__(recovery, {}, o)
        )

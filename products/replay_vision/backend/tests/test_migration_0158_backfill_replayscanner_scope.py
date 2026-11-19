import importlib.util
from pathlib import Path
from typing import Any

from posthog.test.base import BaseTest, TestMigrations

from products.replay_vision.backend.models.replay_scanner import ReplayScanner, ScannerModel, ScannerType
from products.replay_vision.backend.scope.load import derive_scope

_MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / "0158_backfill_replayscanner_scope.py"


def _migration():
    """The migration module, loaded by path because its name starts with a digit."""
    spec = importlib.util.spec_from_file_location("backfill_0158", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODEL = "gemini-3.8-flash"


class TestBackfillReplayScannerScope(TestMigrations):
    app = "replay_vision"
    migrate_from = "0157_drop_replayscanner_sampling_mode_column"
    migrate_to = "0158_backfill_replayscanner_scope"

    def setUpBeforeMigration(self, apps: Any) -> None:
        ReplayScanner = apps.get_model("replay_vision", "ReplayScanner")

        created = 0

        def scanner(**fields):
            nonlocal created
            created += 1
            # Named apart because a team may hold one configured scanner per name.
            defaults = {
                "team_id": self.team.id,
                "name": f"s{created}",
                "model": _MODEL,
                "scanner_config": {"prompt": "p"},
            }
            return ReplayScanner.objects.create(**{**defaults, **fields}).id

        self.native = scanner(
            scanner_type="experiment",
            scanner_config={"prompt": "p", "length": "medium", "experiment_id": 11, "variants": ["control", "test"]},
        )
        self.native_proportional = scanner(
            scanner_type="experiment",
            scanner_config={"prompt": "p", "experiment_id": 12, "variants": ["control"], "balance_variants": False},
        )
        self.native_every_variant = scanner(
            scanner_type="experiment",
            scanner_config={"prompt": "p", "experiment_id": 13},
        )
        self.native_waiting = scanner(
            scanner_type="experiment",
            scanner_config={"prompt": "p", "experiment_id": 14, "start_on_launch": True},
            enabled=False,
        )
        self.native_without_experiment = scanner(
            scanner_type="experiment",
            scanner_config={"prompt": "p"},
        )
        self.legacy_single = scanner(
            scanner_type="summarizer",
            experiment_targeting={"experiment_id": 21, "variant": "test"},
        )
        self.legacy_several = scanner(
            scanner_type="classifier",
            scanner_config={"prompt": "p", "tags": ["a"]},
            experiment_targeting={"experiment_id": 22, "variants": ["control", "test"]},
        )
        self.unscoped = scanner(scanner_type="monitor")
        self.already_scoped = scanner(
            scanner_type="summarizer",
            experiment_targeting={"experiment_id": 31},
            scope={"kind": "experiment", "experiment_id": 31, "variants": ["control"]},
        )

    def test_a_native_scanner_keeps_its_type_and_config(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.native)

        assert row.scanner_type == "experiment"
        assert row.scanner_config == {
            "prompt": "p",
            "length": "medium",
            "experiment_id": 11,
            "variants": ["control", "test"],
        }
        assert row.scope["experiment_id"] == 11
        assert row.scope["variants"] == ["control", "test"]

    def test_a_scanner_that_samples_proportionally_carries_its_balance(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.native_proportional)

        assert row.scope["balance"] is False
        assert row.scanner_config["balance_variants"] is False

    def test_a_default_balance_stays_out_of_the_backfilled_scope(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.native)

        assert "balance" not in row.scope
        assert "start_on_launch" not in row.scope

    def test_a_scanner_waiting_for_launch_carries_its_marker(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.native_waiting)

        assert row.scope["start_on_launch"] is True
        assert row.scanner_config["start_on_launch"] is True

    def test_watching_every_variant_stays_unnarrowed(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.native_every_variant)

        assert row.scope["experiment_id"] == 13
        assert "variants" not in row.scope

    def test_a_legacy_singular_variant_becomes_a_one_item_list(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.legacy_single)

        assert row.scope["experiment_id"] == 21
        assert row.scope["variants"] == ["test"]
        assert row.scanner_type == "summarizer"
        assert row.experiment_targeting == {"experiment_id": 21, "variant": "test"}

    def test_a_legacy_column_scanner_keeps_its_column(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.legacy_several)

        assert row.scanner_type == "classifier"
        assert row.scope["variants"] == ["control", "test"]
        assert row.experiment_targeting["variants"] == ["control", "test"]

    def test_a_scanner_watching_no_experiment_is_left_alone(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        unscoped = ReplayScanner.objects.get(id=self.unscoped)
        without_experiment = ReplayScanner.objects.get(id=self.native_without_experiment)

        assert unscoped.scope is None
        assert without_experiment.scope is None
        assert without_experiment.scanner_type == "experiment"

    def test_an_existing_scope_is_left_as_it_is(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.already_scoped)

        assert row.scope == {"kind": "experiment", "experiment_id": 31, "variants": ["control"]}
        assert "backfilled_at" not in row.scope

    def test_every_backfilled_row_is_stamped(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        backfilled = [
            self.native,
            self.native_proportional,
            self.native_every_variant,
            self.native_waiting,
            self.legacy_single,
            self.legacy_several,
        ]

        for scanner_id in backfilled:
            assert ReplayScanner.objects.get(id=scanner_id).scope["backfilled_at"]


class TestBackfillAgreesWithTheMirror(BaseTest):
    """The backfill must derive exactly what `ReplayScanner.save()`'s mirror derives.

    The mirror decides whether it owns a row's scope by comparing the stored blob against a fresh
    derivation. A backfilled scope that differs by one key reads as hand-set, and the mirror then
    stops following the row's legacy stores.
    """

    def test_a_native_config_derives_the_same_scope_either_way(self) -> None:
        config = {
            "prompt": "p",
            "experiment_id": 77,
            "variants": ["control", "test"],
            "balance_variants": False,
            "start_on_launch": True,
        }
        scanner = ReplayScanner(
            team_id=self.team.id,
            name="agreement",
            scanner_type=ScannerType.EXPERIMENT,
            scanner_config=config,
            model=ScannerModel.GEMINI_3_8_FLASH,
        )

        assert _migration()._scope_from_native_config(config) == derive_scope(scanner)


class TestClearBackfilledScope(TestMigrations):
    app = "replay_vision"
    migrate_from = "0158_backfill_replayscanner_scope"
    migrate_to = "0157_drop_replayscanner_sampling_mode_column"

    def setUpBeforeMigration(self, apps: Any) -> None:
        ReplayScanner = apps.get_model("replay_vision", "ReplayScanner")
        stamp = "2026-11-19T00:00:00+00:00"

        def scanner(**fields):
            defaults = {"team_id": self.team.id, "model": _MODEL}
            return ReplayScanner.objects.create(**{**defaults, **fields}).id

        self.backfilled = scanner(
            name="n1",
            scanner_type="experiment",
            scanner_config={"prompt": "p", "experiment_id": 11, "variants": ["control", "test"]},
            scope={"kind": "experiment", "experiment_id": 11, "backfilled_at": stamp},
        )
        self.set_by_hand = scanner(
            name="n2",
            scanner_type="summarizer",
            scanner_config={"prompt": "p"},
            experiment_targeting={"experiment_id": 31},
            scope={"kind": "experiment", "experiment_id": 31},
        )

    def test_a_backfilled_scope_is_cleared_and_nothing_else_moves(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.backfilled)

        assert row.scope is None
        assert row.scanner_type == "experiment"
        assert row.scanner_config["experiment_id"] == 11

    def test_a_scope_this_migration_did_not_write_is_left_alone(self) -> None:
        ReplayScanner = self.apps.get_model("replay_vision", "ReplayScanner")  # type: ignore[union-attr]
        row = ReplayScanner.objects.get(id=self.set_by_hand)

        assert row.scope == {"kind": "experiment", "experiment_id": 31}

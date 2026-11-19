from django.db import migrations, transaction

_BATCH_SIZE = 500

# Copied rather than imported: a migration must keep reading the shape the rows held when it was
# written, and the live model's choices move with the product.
_EXPERIMENT = "experiment"

# The `scanner_config` keys an experiment-type scanner keeps its scope in.
_CONFIG_SCOPE_KEYS = ("experiment_id", "variants", "balance_variants", "start_on_launch")


def _scope_from_native_config(config: dict) -> dict | None:
    """The scope an experiment-type scanner's `scanner_config` describes, or None if it names none."""
    experiment_id = config.get("experiment_id")
    if not isinstance(experiment_id, int):
        return None
    # Exactly what the mirror in `ReplayScanner.save()` derives from the same config, key for key.
    # It compares the stored blob against a fresh derivation to decide whether it owns a row's scope,
    # so an extra key here would make it read every backfilled row as one set by hand. That is also
    # why `variants_source` is absent: the mirror never writes it, so neither does this.
    scope: dict = {"kind": "experiment", "experiment_id": experiment_id}
    variants = config.get("variants")
    if variants:
        scope["variants"] = list(variants)
    # Both are omitted at their default, because the mirror in `ReplayScanner.save()` decides whether
    # it owns a row's scope by comparing the stored blob against a fresh derivation of it. Writing a
    # defaulted key here would make the mirror read a backfilled row as one set by hand.
    if config.get("balance_variants") is False:
        scope["balance"] = False
    if config.get("start_on_launch") is True:
        scope["start_on_launch"] = True
    return scope


def _scope_from_targeting(targeting: dict) -> dict | None:
    """The scope the legacy `experiment_targeting` column describes."""
    experiment_id = targeting.get("experiment_id")
    if not isinstance(experiment_id, int):
        return None
    scope: dict = {"kind": "experiment", "experiment_id": experiment_id}
    # The legacy column holds a singular `variant`; the scope shape has only the plural, so a single
    # watched variant becomes a one-item list. This is the same fold `stored_scope` does.
    variants = targeting.get("variants") or ([targeting["variant"]] if targeting.get("variant") else None)
    if variants:
        scope["variants"] = list(variants)
    return scope


def backfill_replayscanner_scope(apps, schema_editor):
    """Give every experiment-watching scanner its own `scope`, leaving its older stores in place.

    Only the column is written. The scanner keeps its type, its `scanner_config` and its
    `experiment_targeting`, so every reader that still keys on those sees exactly what it saw
    before. Retiring the `experiment` type is PR 11's job, with the branches that read it.
    """
    ReplayScanner = apps.get_model("replay_vision", "ReplayScanner")
    # The migration connection carries the lock_timeout that makes a contended row fail fast so the
    # runner retries; the default connection has no such bound and would block the deploy instead.
    alias = schema_editor.connection.alias
    last_pk = None
    while True:
        # Read and write in one transaction with the batch locked, so a scanner saved between the
        # two does not lose its edit to a stale copy. The stamp would make a retry skip that row.
        # Each batch commits alone, so an edit or a sweep waits on at most one batch's locks.
        with transaction.atomic(using=alias):
            rows = ReplayScanner.objects.using(alias).order_by("pk").select_for_update(of=("self",))
            if last_pk is not None:
                rows = rows.filter(pk__gt=last_pk)
            batch = list(
                rows.only("id", "scanner_type", "scanner_config", "experiment_targeting", "scope")[:_BATCH_SIZE]
            )
            if not batch:
                return
            last_pk = batch[-1].pk
            changed = []
            for scanner in batch:
                # A row that already carries a scope keeps it, whoever wrote it: the mirror derives
                # one on every save, so most rows written since that shipped already have the value
                # this would compute. Checked before any derivation, so a re-run reads each row once.
                if isinstance(scanner.scope, dict) and scanner.scope.get("kind"):
                    continue
                config = scanner.scanner_config if isinstance(scanner.scanner_config, dict) else {}
                targeting = scanner.experiment_targeting if isinstance(scanner.experiment_targeting, dict) else {}
                if scanner.scanner_type == _EXPERIMENT:
                    scope = _scope_from_native_config(config)
                elif targeting:
                    scope = _scope_from_targeting(targeting)
                else:
                    continue
                if scope is None:
                    # Nothing names an experiment, so there is no scope to derive. An experiment-type
                    # row in this state cannot build a scanner either; left alone for a person.
                    continue
                scanner.scope = scope
                changed.append(scanner)
            ReplayScanner.objects.using(alias).bulk_update(changed, ["scope"])


def noop_reverse(apps, schema_editor):
    """Nothing to undo: every scope this wrote is the one `ReplayScanner.save()` derives anyway.

    The backfill carries no stamp of its own, because the mirror decides whether it owns a row's
    scope by comparing the stored blob against a fresh derivation. A provenance key would fail that
    comparison, and the one save that clears a row's `experiment_targeting` would then leave the
    scope naming the removed experiment in place, so the scanner would keep sweeping it.

    Without a stamp there is nothing to tell a backfilled scope from a mirrored one, and clearing
    both would throw away values the mirror wrote. Reversing the migration therefore leaves the
    column as it is: the rows hold what a save would write, and `scope_for` still falls back to the
    older stores, which this never touched.
    """


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("replay_vision", "0157_drop_replayscanner_sampling_mode_column")]

    operations = [migrations.RunPython(backfill_replayscanner_scope, noop_reverse)]

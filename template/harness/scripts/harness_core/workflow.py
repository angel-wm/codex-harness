"""SDD transitions, reviewer contracts, and completion gates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .repository import HarnessError, atomic_write, changed_paths, git_is_clean
from .repository import implementation_fingerprint, json_load, json_write, paths, run_git, utc_now
from .specs import approval_is_current, canonical_spec_digest, traceability_ids, validate_spec
from .state import BLOCKABLE_STATES, SCHEMA_VERSION, find_feature, load_state


def update_current(root: Path, feature: dict[str, Any], next_step: str) -> None:
    """Write a concise durable current-session record."""
    text = (
        "# Current SDD session\n\n"
        f"- **Feature:** `{feature['name']}`\n"
        f"- **State:** `{feature['status']}`\n"
        f"- **Updated (UTC):** {utc_now()}\n\n"
        "## Next step\n\n"
        f"{next_step}\n"
    )
    atomic_write(paths(root)["current"], text)


def transition_spec_ready(root: Path, selector: str) -> dict[str, Any]:
    """Move one valid SDD feature from pending to spec_ready."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "pending":
        raise HarnessError("spec-ready requires a pending feature")
    if not feature["sdd"]:
        raise HarnessError("spec-ready applies only to SDD features")
    if any(item["status"] == "in_progress" for item in features_data["features"]):
        raise HarnessError("Another feature is already in_progress")
    if not config["commands"]["verify"]:
        raise HarnessError("Configure at least one verify command before spec-ready")
    _, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    feature["status"] = "spec_ready"
    feature["approval"] = None
    feature["block"] = None
    feature["review_cycles"] = 0
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, "Human reviews and commits the three spec files and feature state, then explicitly approves them.")
    return feature


def approve_feature(root: Path, selector: str) -> dict[str, Any]:
    """Record exact spec approval and move spec_ready to in_progress."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "spec_ready":
        raise HarnessError("approve requires a spec_ready feature")
    if any(item is not feature and item["status"] == "in_progress" for item in features_data["features"]):
        raise HarnessError("Another feature is already in_progress")
    if not config["commands"]["verify"]:
        raise HarnessError("Configure at least one verify command before approval")
    _, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    if config["workflow"]["require_clean_worktree"] and not git_is_clean(root):
        raise HarnessError("Approval requires a clean worktree; commit or stash reviewed spec/state changes first")
    baseline = run_git(root, ["rev-parse", "HEAD"]).stdout.strip()
    feature["approval"] = {
        "digest": canonical_spec_digest(root, feature),
        "approved_at": utc_now(),
        "baseline": baseline,
    }
    feature["status"] = "in_progress"
    feature["block"] = None
    feature["review_cycles"] = 0
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, "Run the sequential implementer, configured verification, and independent reviewer.")
    return feature


def read_review(path: Path, feature: dict[str, Any], expected_fingerprint: str, requirement_ids: set[str]) -> dict[str, Any]:
    """Validate a strict reviewer JSON verdict."""
    review = json_load(path)
    errors: list[str] = []
    if review.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
    if review.get("feature") != feature["name"]:
        errors.append("feature does not match")
    if review.get("implementation_fingerprint") != expected_fingerprint:
        errors.append("implementation_fingerprint is stale or incorrect")
    if review.get("verdict") not in {"APPROVED", "CHANGES_REQUESTED"}:
        errors.append("verdict must be APPROVED or CHANGES_REQUESTED")
    coverage = review.get("requirements")
    if not isinstance(coverage, list):
        errors.append("requirements must be an array")
    else:
        seen: set[str] = set()
        for entry in coverage:
            if not isinstance(entry, dict) or entry.get("id") not in requirement_ids:
                errors.append("requirements contains an invalid id")
                continue
            identifier = entry["id"]
            if identifier in seen:
                errors.append(f"requirements contains duplicate entry {identifier}")
            seen.add(identifier)
            covered = entry.get("covered")
            evidence = entry.get("evidence")
            if not isinstance(covered, bool) or not isinstance(evidence, str) or not evidence.strip():
                errors.append(f"requirements entry {identifier} needs covered boolean and non-empty evidence string")
        if seen != requirement_ids:
            errors.append("requirements coverage must include every requirement exactly once")
    if not isinstance(review.get("tasks_complete"), bool):
        errors.append("tasks_complete must be a boolean")
    checkpoints = review.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        errors.append("checkpoints must be a non-empty array")
    else:
        checkpoint_names: set[str] = set()
        for checkpoint in checkpoints:
            if not isinstance(checkpoint, dict):
                errors.append("checkpoints entries must be objects")
                continue
            name = checkpoint.get("name")
            passed = checkpoint.get("passed")
            if not isinstance(name, str) or not name.strip() or not isinstance(passed, bool):
                errors.append("checkpoints entries need a non-empty name and passed boolean")
                continue
            if name in checkpoint_names:
                errors.append(f"checkpoints contains duplicate entry {name!r}")
            checkpoint_names.add(name)
    findings = review.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and bool(item["path"].strip())
        and isinstance(item.get("remediation"), str)
        and bool(item["remediation"].strip())
        for item in findings
    ):
        errors.append("findings must be an array of non-empty path/remediation objects")
    if review.get("verdict") == "APPROVED":
        if review.get("tasks_complete") is not True or findings:
            errors.append("APPROVED requires tasks_complete true and no findings")
        if isinstance(coverage, list) and any(entry.get("covered") is not True for entry in coverage if isinstance(entry, dict)):
            errors.append("APPROVED requires all requirements covered")
        if isinstance(checkpoints, list) and any(
            checkpoint.get("passed") is not True for checkpoint in checkpoints if isinstance(checkpoint, dict)
        ):
            errors.append("APPROVED requires all checkpoints passed")
    if review.get("verdict") == "CHANGES_REQUESTED" and isinstance(findings, list) and not findings:
        errors.append("CHANGES_REQUESTED requires at least one actionable finding")
    if errors:
        raise HarnessError("Invalid review JSON:\n- " + "\n- ".join(errors))
    review["recorded_at"] = utc_now()
    return review


def record_review(root: Path, selector: str, input_path: Path) -> dict[str, Any]:
    """Persist a current structured reviewer verdict and enforce cycle limits."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "in_progress":
        raise HarnessError("record-review requires an in_progress feature")
    if not approval_is_current(root, feature):
        raise HarnessError("The approved spec digest is stale")
    spec, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    fingerprint = implementation_fingerprint(root, feature["approval"]["baseline"])
    review = read_review(input_path, feature, fingerprint, {item["id"] for item in spec["requirements"]})
    paths(root)["reviews"].mkdir(parents=True, exist_ok=True)
    json_write(paths(root)["reviews"] / f"{feature['name']}.json", review)
    findings_lines = "\n".join(
        f"- `{item['path']}` — {item['remediation']}" for item in review["findings"]
    ) or "- None."
    markdown = (
        f"# Review: {feature['name']}\n\n"
        f"- Verdict: **{review['verdict']}**\n"
        f"- Fingerprint: `{fingerprint}`\n"
        f"- Recorded: {review['recorded_at']}\n\n"
        f"## Findings\n\n{findings_lines}\n"
    )
    atomic_write(paths(root)["reviews"] / f"{feature['name']}.md", markdown)
    feature["review_cycles"] = feature.get("review_cycles", 0) + 1
    if review["verdict"] == "CHANGES_REQUESTED" and feature["review_cycles"] >= config["workflow"]["max_review_cycles"]:
        prior = feature["status"]
        feature["status"] = "blocked"
        feature["block"] = {
            "prior_status": prior,
            "reason": f"Review cycle limit reached ({feature['review_cycles']})",
            "blocked_at": utc_now(),
        }
    json_write(paths(root)["features"], features_data)
    next_step = "Complete the feature." if review["verdict"] == "APPROVED" else "Address only the recorded findings, then verify and review again."
    update_current(root, feature, next_step)
    return review


def complete_feature(root: Path, selector: str) -> dict[str, Any]:
    """Complete one feature after independently rechecking every final gate."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "in_progress":
        raise HarnessError("complete requires an in_progress feature")
    if not approval_is_current(root, feature):
        raise HarnessError("Completion rejected: approved spec digest is stale")
    spec, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Completion rejected by spec validation:\n- " + "\n- ".join(errors))
    incomplete = [item["id"] for item in spec["tasks"] if not item["complete"]]
    if incomplete:
        raise HarnessError("Completion rejected: incomplete tasks: " + ", ".join(incomplete))
    requirement_ids = {item["id"] for item in spec["requirements"]}
    report = paths(root)["progress"] / f"impl_{feature['name']}.md"
    missing_traceability = sorted(requirement_ids - traceability_ids(report), key=lambda item: int(item[1:]))
    if missing_traceability:
        raise HarnessError("Completion rejected: missing traceability for " + ", ".join(missing_traceability))
    fingerprint = implementation_fingerprint(root, feature["approval"]["baseline"])
    verification_path = paths(root)["verification"]
    if not verification_path.is_file():
        raise HarnessError("Completion rejected: no verification artifact")
    verification = json_load(verification_path)
    if not verification.get("success") or verification.get("group") != "verify":
        raise HarnessError("Completion rejected: latest verification did not succeed")
    if verification.get("feature") != feature["name"] or verification.get("implementation_fingerprint") != fingerprint:
        raise HarnessError("Completion rejected: verification is stale")
    review_path = paths(root)["reviews"] / f"{feature['name']}.json"
    if not review_path.is_file():
        raise HarnessError("Completion rejected: no recorded review")
    review = json_load(review_path)
    if review.get("verdict") != "APPROVED" or review.get("implementation_fingerprint") != fingerprint:
        raise HarnessError("Completion rejected: review is absent, non-approved, or stale")
    feature["status"] = "done"
    feature["block"] = None
    completed_at = utc_now()
    json_write(paths(root)["features"], features_data)
    history_path = paths(root)["history"]
    existing = history_path.read_text(encoding="utf-8") if history_path.is_file() else "# SDD history\n"
    entry = (
        f"\n## {completed_at} — {feature['title']} (`{feature['name']}`)\n\n"
        f"- Feature ID: {feature['id']}\n"
        f"- Approved spec: `{feature['approval']['digest']}`\n"
        f"- Implementation: `{fingerprint}`\n"
        f"- Verification: successful\n"
        f"- Review cycles: {feature['review_cycles']}\n"
    )
    atomic_write(history_path, existing.rstrip() + "\n" + entry)
    atomic_write(
        paths(root)["current"],
        "# Current SDD session\n\n- **Feature:** _none_\n- **Started (UTC):** _—_\n- **Coordinator:** _—_\n\n## Plan\n\n_—_\n\n## Log\n\n_—_\n\n## Next step\n\n_—_\n",
    )
    if config["git"]["auto_commit_on_done"]:
        exact_paths = changed_paths(root, feature["approval"]["baseline"])
        if not exact_paths:
            raise HarnessError("Feature completed, but auto-commit found no changed paths")
        for relative in exact_paths:
            run_git(root, ["add", "--", relative])
        message = config["git"]["commit_message"].format(
            feature_name=feature["name"], feature_title=feature["title"]
        )
        commit = run_git(root, ["commit", "-m", message], check=False)
        if commit.returncode != 0:
            detail = commit.stderr.strip() or commit.stdout.strip()
            raise HarnessError(f"Feature completed, but auto-commit failed non-destructively: {detail}")
    return {"feature": feature["name"], "status": "done", "implementation_fingerprint": fingerprint}


def block_feature(root: Path, selector: str, reason: str) -> dict[str, Any]:
    """Record a durable blocker while preserving the resumable prior state."""
    _, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] not in BLOCKABLE_STATES:
        raise HarnessError("Only pending, spec_ready, or in_progress features can be blocked")
    prior = feature["status"]
    feature["status"] = "blocked"
    feature["block"] = {"prior_status": prior, "reason": reason.strip(), "blocked_at": utc_now()}
    if not feature["block"]["reason"]:
        raise HarnessError("A non-empty block reason is required")
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, f"Blocked: {reason.strip()} Explicit human direction is required to resume.")
    return feature


def resume_feature(root: Path, selector: str) -> dict[str, Any]:
    """Restore a blocked feature to its recorded valid prior state."""
    _, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "blocked" or not isinstance(feature.get("block"), dict):
        raise HarnessError("resume requires a blocked feature")
    prior = feature["block"].get("prior_status")
    if prior not in BLOCKABLE_STATES:
        raise HarnessError("Blocked feature has no valid prior state")
    if prior == "in_progress" and any(
        item is not feature and item["status"] == "in_progress" for item in features_data["features"]
    ):
        raise HarnessError("Cannot resume: another feature is in_progress")
    feature["status"] = prior
    feature["block"] = None
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, f"Resumed to {prior}; continue only within the existing approved scope.")
    return feature

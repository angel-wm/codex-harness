"""Strict specifications, tasks, traceability, and approval digests."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


def validate_spec(root: Path, feature: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Validate all three spec files for one feature."""
    requirements_path, design_path, tasks_path = spec_paths(root, feature)
    missing = [str(path.relative_to(root)) for path in (requirements_path, design_path, tasks_path) if not path.is_file()]
    if missing:
        return {}, [f"Missing spec file: {item}" for item in missing]
    requirements, errors = parse_requirements(requirements_path.read_text(encoding="utf-8"))
    acceptance_count = len(feature.get("acceptance", []))
    if acceptance_count:
        covered = {number for requirement in requirements for number in requirement["acceptance"]}
        expected = set(range(1, acceptance_count + 1))
        missing_acceptance = sorted(expected - covered)
        unknown_acceptance = sorted(covered - expected)
        if missing_acceptance:
            errors.append("Unmapped acceptance criteria: " + ", ".join(f"A{item}" for item in missing_acceptance))
        if unknown_acceptance:
            errors.append("Unknown acceptance mappings: " + ", ".join(f"A{item}" for item in unknown_acceptance))
    design = design_path.read_text(encoding="utf-8").strip()
    if len(design) < 100:
        errors.append("design.md must contain substantive design decisions")
    if "alternative" not in design.lower():
        errors.append("design.md must document at least one rejected alternative")
    requirement_ids = {item["id"] for item in requirements}
    tasks, task_errors = parse_tasks(tasks_path.read_text(encoding="utf-8"), requirement_ids)
    errors.extend(task_errors)
    referenced = {identifier for task in tasks for identifier in task["requirements"]}
    unreferenced = sorted(requirement_ids - referenced, key=lambda item: int(item[1:]))
    if unreferenced:
        errors.append("Requirements not referenced by any task: " + ", ".join(unreferenced))
    return {"requirements": requirements, "tasks": tasks}, errors


def approval_is_current(root: Path, feature: dict[str, Any]) -> bool:
    """Return whether the stored approval matches the normalized current spec."""
    approval = feature.get("approval")
    return isinstance(approval, dict) and approval.get("digest") == canonical_spec_digest(root, feature)


def parse_tasks(text: str, requirement_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse ordered executable tasks with requirement references."""
    errors: list[str] = []
    tasks: list[dict[str, Any]] = []
    pattern = re.compile(r"(?m)^- \[([ xX])\] T(\d+)\s+.+?(?:Covers|Requirements):\s*([^\n.]+)\.?")
    for match in pattern.finditer(text):
        references = re.findall(r"R\d+", match.group(3))
        tasks.append(
            {
                "id": f"T{match.group(2)}",
                "number": int(match.group(2)),
                "complete": match.group(1).lower() == "x",
                "requirements": references,
            }
        )
    if not tasks:
        return [], ["tasks.md must contain tasks like '- [ ] T1 — ... Covers: R1.'"]
    for expected, task in enumerate(tasks, start=1):
        if task["number"] != expected:
            errors.append(f"Task IDs must be sequential; expected T{expected}, found {task['id']}")
        if not task["requirements"]:
            errors.append(f"{task['id']} must reference at least one requirement")
        unknown = sorted(set(task["requirements"]) - requirement_ids)
        if unknown:
            errors.append(f"{task['id']} references unknown requirements: {', '.join(unknown)}")
    return tasks, errors


def parse_requirements(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse strict English EARS requirements and their acceptance mappings."""
    errors: list[str] = []
    matches = list(re.finditer(r"(?m)^## (R(\d+))\s*$", text))
    if not matches:
        return [], ["requirements.md must contain headings beginning with ## R1"]
    requirements: list[dict[str, Any]] = []
    expected = 1
    ears = re.compile(
        r"^(?:The system MUST .+|WHEN .+, the system MUST .+|"
        r"WHILE .+, the system MUST .+|WHERE .+, the system MUST .+|"
        r"IF .+ THEN the system MUST .+)$"
    )
    for index, match in enumerate(matches):
        identifier = match.group(1)
        number = int(match.group(2))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        statement_lines: list[str] = []
        acceptance: list[int] = []
        for line in body.splitlines():
            stripped = line.strip()
            mapping = re.fullmatch(r"Acceptance:\s*(A\d+(?:\s*,\s*A\d+)*)", stripped)
            if mapping:
                acceptance.extend(int(item[1:]) for item in re.findall(r"A\d+", mapping.group(1)))
            elif stripped and not stripped.startswith("<!--"):
                statement_lines.append(stripped)
        statement = " ".join(statement_lines)
        if number != expected:
            errors.append(f"Requirement IDs must be sequential; expected R{expected}, found {identifier}")
            expected = number
        expected += 1
        if statement.count("MUST") != 1:
            errors.append(f"{identifier} must contain exactly one uppercase MUST obligation")
        if re.search(r"\b(?:MAY|SHOULD|COULD)\b", statement):
            errors.append(f"{identifier} contains a soft obligation")
        if not ears.fullmatch(statement):
            errors.append(f"{identifier} does not match a strict English EARS form")
        requirements.append({"id": identifier, "statement": statement, "acceptance": acceptance})
    return requirements, errors


def canonical_spec_digest(root: Path, feature: dict[str, Any]) -> str:
    """Hash normalized spec content while ignoring task checkbox state."""
    digest = hashlib.sha256()
    for path in spec_paths(root, feature):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        if path.name == "tasks.md":
            text = re.sub(r"(?m)^- \[[xX]\]", "- [ ]", text)
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def traceability_ids(report_path: Path) -> set[str]:
    """Extract requirements with explicit arrow-based evidence entries."""
    if not report_path.is_file():
        return set()
    return set(re.findall(r"(?m)^- (R\d+)\s*(?:→|->)\s*\S.+$", report_path.read_text(encoding="utf-8")))


def spec_paths(root: Path, feature: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Return requirements, design, and tasks paths for a feature."""
    base = root / "harness" / "specs" / feature["name"]
    return base / "requirements.md", base / "design.md", base / "tasks.md"

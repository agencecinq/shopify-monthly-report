#!/usr/bin/env python3
"""
Structure checks for the plugin, to run before packaging or opening a PR.

Catches what the plugin installer rejects (a description over 1024 characters,
a name that is not kebab-case) and what it accepts but breaks at run time (a
SKILL.md pointing at a reference file that is not in the package).

    python3 tools/validate_plugin.py .
"""

import json
import os
import re
import sys

DESCRIPTION_LIMIT = 1024
WARN_AT = 950


def read_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def frontmatter_description(fm):
    folded = re.search(r"description:\s*>\s*\n((?:\s{2}.*\n?)+)", fm)
    if folded:
        return " ".join(l.strip() for l in folded.group(1).splitlines() if l.strip())
    single = re.search(r"^description:\s*(.+)$", fm, re.M)
    return single.group(1).strip().strip("\"'") if single else ""


def main(root):
    errors, warnings = [], []

    manifest_meta = None
    manifest = os.path.join(root, ".claude-plugin", "plugin.json")
    if not os.path.exists(manifest):
        errors.append("plugin.json missing")
    else:
        with open(manifest, encoding="utf-8") as fh:
            meta = manifest_meta = json.load(fh)
        if not re.fullmatch(r"[a-z0-9-]+", meta.get("name", "")):
            errors.append(f"plugin name is not kebab-case: {meta.get('name')!r}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", meta.get("version", "")):
            errors.append(f"version is not semver: {meta.get('version')!r}")
        if len(meta.get("description", "")) > DESCRIPTION_LIMIT:
            errors.append(f"plugin.json description over {DESCRIPTION_LIMIT}")

    # Without this file a GitHub repository is not an installable source: the
    # plugin manifest alone is what the client sees rejected.
    market = os.path.join(root, ".claude-plugin", "marketplace.json")
    if not os.path.exists(market):
        errors.append("marketplace.json missing, the repository cannot be added "
                      "with /plugin marketplace add")
    else:
        with open(market, encoding="utf-8") as fh:
            listing = json.load(fh)
        if not re.fullmatch(r"[a-z0-9-]+", listing.get("name", "")):
            errors.append(f"marketplace name is not kebab-case: "
                          f"{listing.get('name')!r}")
        entries = listing.get("plugins") or []
        if not entries:
            errors.append("marketplace.json lists no plugins")
        for entry in entries:
            if entry.get("source") not in ("./", ".") or not manifest_meta:
                continue
            # The entry and the manifest describe the same plugin, so a
            # disagreement installs one version under another's name.
            for field in ("name", "version"):
                if field in entry and entry[field] != manifest_meta.get(field):
                    errors.append(f"marketplace.json {field} {entry[field]!r} "
                                  f"disagrees with plugin.json "
                                  f"{manifest_meta.get(field)!r}")

    skills_dir = os.path.join(root, "skills")
    found = 0
    entries = sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []
    for name in entries:
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.exists(skill_md):
            errors.append(f"skills/{name} has no SKILL.md")
            continue
        found += 1
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()

        fm = read_frontmatter(text)
        if fm is None:
            errors.append(f"skills/{name} has no frontmatter")
            continue
        for field in ("name", "description"):
            if f"{field}:" not in fm:
                errors.append(f"skills/{name} is missing field {field}")

        declared = re.search(r"^name:\s*(.+)$", fm, re.M)
        if declared and not re.fullmatch(r"[a-z0-9-]+", declared.group(1).strip()):
            errors.append(f"skills/{name} name is not kebab-case")

        size = len(frontmatter_description(fm))
        if size > DESCRIPTION_LIMIT:
            errors.append(f"skills/{name}: description {size} over {DESCRIPTION_LIMIT}")
        elif size > WARN_AT:
            warnings.append(f"skills/{name}: description {size}, close to the limit")
        else:
            print(f"  skills/{name}: description {size} characters")

        # A broken reference passes installation and fails at run time, in front
        # of a client, which is the worse of the two.
        for ref in set(re.findall(r"references/([a-z0-9._-]+\.md)", text)):
            if not os.path.exists(os.path.join(skills_dir, name, "references", ref)):
                errors.append(f"skills/{name} references references/{ref}, "
                              f"which does not exist")
        for script in set(re.findall(r"scripts/([a-z0-9._-]+\.py)", text)):
            if not os.path.exists(os.path.join(skills_dir, name, "scripts", script)):
                errors.append(f"skills/{name} references scripts/{script}, "
                              f"which does not exist")

    print(f"  {found} skill(s)")

    # Language catalogues must expose the same keys, or a deck built in one
    # language silently falls back to another.
    for name in entries:
        i18n = os.path.join(skills_dir, name, "i18n")
        if not os.path.isdir(i18n):
            continue
        catalogues = {}
        for f in sorted(os.listdir(i18n)):
            if not f.endswith(".json"):
                continue
            with open(os.path.join(i18n, f), encoding="utf-8") as fh:
                catalogues[f[:-5]] = flatten(json.load(fh))
        if "en" not in catalogues:
            errors.append(f"skills/{name}/i18n has no en.json to fall back on")
            continue
        base = catalogues["en"]
        for code, keys in catalogues.items():
            if code == "en":
                continue
            missing, extra = sorted(base - keys), sorted(keys - base)
            if missing:
                warnings.append(f"{code}.json missing {len(missing)} key(s), "
                                f"falls back to English: {missing[:3]}")
            if extra:
                warnings.append(f"{code}.json has {len(extra)} unused key(s): "
                                f"{extra[:3]}")
        print(f"  languages: {', '.join(sorted(catalogues))}")

    for w in warnings:
        print("  WARNING:", w)
    if errors:
        print("\nFAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print("\nStructure OK.")
    return 0


def flatten(node, prefix=""):
    keys = set()
    for k, v in node.items():
        if k.startswith("_"):
            continue
        path = f"{prefix}{k}"
        keys |= flatten(v, path + ".") if isinstance(v, dict) else {path}
    return keys


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))

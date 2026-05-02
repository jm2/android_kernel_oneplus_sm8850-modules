#!/usr/bin/env python3
# bazel_kbuild_diff.py — translation correctness check
#
# Given a BUILD.bazel (and any *.bzl it loads) and a hand-written Kbuild,
# extract every `define_oplus_ddk_module(...)` block from the Bazel side and
# verify the Kbuild has matching:
#   - obj-m / obj-y target for each module's `name`
#   - <name>-y source list covers `srcs` (modulo .h files in the glob)
#   - ccflags-y -I... entries for each `includes` path
#   - ccflags-y -DCONFIG_X for each `local_defines` entry
#   - KBUILD_EXTRA_SYMBOLS pointing at every `ko_deps` producer
#
# Limitations:
#   - Starlark is parsed by regex, not interpreted. Conditional
#     constructs (if/elif on platform), string formatting, and
#     native.glob() with non-trivial args produce best-effort matches.
#   - When in doubt, the script flags the case rather than silently
#     accepting it. Manual review takes the false-positive flags.
#
# Phase 2 of the OnePlus 15 LineageOS implementation plan.

import argparse
import re
import sys
from pathlib import Path


# Match define_oplus_ddk_module(...) including newlines.
MODULE_DEF_RE = re.compile(
    r"define_oplus_ddk_module\s*\(\s*(.*?)\s*\)\s*$",
    re.DOTALL | re.MULTILINE,
)
# Match key=value entries in a Bazel call.
ARG_RE = re.compile(r'^\s*(\w+)\s*=\s*(.+?),?\s*$', re.MULTILINE)
STRING_LIST_RE = re.compile(r'\[\s*((?:"[^"]*"\s*,?\s*)*)\]')
GLOB_RE = re.compile(r'native\.glob\s*\(\s*(\[.*?\])\s*\)', re.DOTALL)
QUOTED_RE = re.compile(r'"([^"]*)"')


def parse_bazel_modules(text: str) -> list:
    """Extract all define_oplus_ddk_module(...) calls. Returns list of dicts."""
    modules = []
    # Be permissive about how the call looks; greedy enough to grab nested ()
    # for native.glob([...]).
    pos = 0
    while True:
        i = text.find("define_oplus_ddk_module", pos)
        if i < 0:
            break
        # Find matching closing paren by paren-counting from i
        depth = 0
        j = i
        while j < len(text):
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(text):
            break
        body = text[i + len("define_oplus_ddk_module") : j + 1]
        modules.append(parse_module_body(body))
        pos = j + 1
    return modules


def parse_module_body(body: str) -> dict:
    """Parse a single define_oplus_ddk_module(...) body."""
    name = ""
    srcs = []
    includes = []
    ko_deps = []
    local_defines = []
    # name = "..."
    m = re.search(r'\bname\s*=\s*"([^"]*)"', body)
    if m:
        name = m.group(1)
    # srcs = native.glob([...]) or srcs = [...]
    m = GLOB_RE.search(body)
    if m:
        srcs = [s for s in QUOTED_RE.findall(m.group(1))]
    else:
        m = re.search(r'\bsrcs\s*=\s*(\[.*?\])', body, re.DOTALL)
        if m:
            srcs = QUOTED_RE.findall(m.group(1))
    # includes = [...]
    m = re.search(r'\bincludes\s*=\s*(\[.*?\])', body, re.DOTALL)
    if m:
        includes = QUOTED_RE.findall(m.group(1))
    # ko_deps = [...] (may also appear as variable reference outside this body —
    # not handled by the regex; flag as ambiguous)
    m = re.search(r'\bko_deps\s*=\s*(\[.*?\])', body, re.DOTALL)
    if m:
        ko_deps = QUOTED_RE.findall(m.group(1))
    # local_defines = [...]
    m = re.search(r'\blocal_defines\s*=\s*(\[.*?\])', body, re.DOTALL)
    if m:
        local_defines = QUOTED_RE.findall(m.group(1))
    return {
        "name": name,
        "srcs": srcs,
        "includes": includes,
        "ko_deps": ko_deps,
        "local_defines": local_defines,
    }


def parse_kbuild(text: str) -> dict:
    """Extract obj-m, *-y source lists, ccflags-y, KBUILD_EXTRA_SYMBOLS."""
    obj_m = []
    src_lists = {}  # name -> [.o files]
    ccflags = []
    kbuild_extra = []
    # obj-m += foo.o
    for m in re.finditer(r'^\s*obj-m\s*[:+]?=\s*(.+?)(?:\s*#.*)?$', text, re.MULTILINE):
        obj_m.extend(o.strip() for o in m.group(1).split() if o.strip())
    # foo-y := bar.o baz.o (or +=)
    for m in re.finditer(r'^\s*(\w+)-y\s*[:+]?=\s*(.+?)(?:\s*#.*)?$', text, re.MULTILINE):
        name = m.group(1)
        src_lists.setdefault(name, []).extend(
            o.strip() for o in m.group(2).split() if o.strip()
        )
    # ccflags-y += ...
    for m in re.finditer(r'^\s*ccflags-y\s*[:+]?=\s*(.+?)(?:\s*#.*)?$', text, re.MULTILINE):
        ccflags.extend(o.strip() for o in m.group(1).split() if o.strip())
    # KBUILD_EXTRA_SYMBOLS += ...
    for m in re.finditer(
            r'^\s*KBUILD_EXTRA_SYMBOLS\s*[:+]?=\s*(.+?)(?:\s*#.*)?$',
            text, re.MULTILINE):
        kbuild_extra.extend(o.strip() for o in m.group(1).split() if o.strip())
    return {
        "obj_m": obj_m,
        "src_lists": src_lists,
        "ccflags": ccflags,
        "kbuild_extra": kbuild_extra,
    }


def diff(bazel_modules: list, kbuild: dict) -> list:
    """Return list of (severity, message) tuples for any discrepancy."""
    issues = []
    expected_targets = {m["name"] for m in bazel_modules if m["name"]}
    actual_targets = {o.replace(".o", "") for o in kbuild["obj_m"]}
    for tgt in sorted(expected_targets - actual_targets):
        issues.append(("error", f"missing obj-m target: {tgt}.o"))
    for tgt in sorted(actual_targets - expected_targets):
        issues.append(("warn", f"extra obj-m target not in BUILD.bazel: {tgt}.o"))

    for m in bazel_modules:
        name = m["name"]
        if not name:
            continue
        # Compare srcs (.c files only; ignore .h glob entries)
        bazel_csrcs = [s for s in m["srcs"] if s.endswith(".c")]
        bazel_objs = {Path(s).with_suffix(".o").name for s in bazel_csrcs}
        kbuild_objs = set(kbuild["src_lists"].get(name, []))
        # If no per-target src list, default is <name>.o (single-source case)
        if not kbuild_objs and len(bazel_objs) == 1:
            continue
        for missing in sorted(bazel_objs - kbuild_objs):
            issues.append(("error",
                           f"{name}: missing source object {missing}"))
        for extra in sorted(kbuild_objs - bazel_objs):
            issues.append(("warn",
                           f"{name}: kbuild has extra object {extra}"))

        # Compare local_defines (CONFIG_* flags)
        for define in m["local_defines"]:
            flag = f"-D{define}"
            if not any(flag in c for c in kbuild["ccflags"]):
                issues.append(("warn",
                               f"{name}: local_define {define} not "
                               f"surfaced in ccflags-y"))

        # Compare includes
        for inc in m["includes"]:
            inc_norm = inc.rstrip("/")
            inc_clean = "." if inc_norm == "" else inc_norm
            # Accept either -I<path> or -I$(srctree)/$(src)/<path>
            if not any(("-I" + inc_clean) in c or
                       (inc_clean != "." and inc_clean in c)
                       for c in kbuild["ccflags"]):
                issues.append(("warn",
                               f"{name}: include path '{inc}' "
                               f"not surfaced in ccflags-y"))

        # Compare ko_deps (intermodule deps)
        for dep in m["ko_deps"]:
            depname = dep.split(":")[-1]
            if not any(depname in s for s in kbuild["kbuild_extra"]):
                issues.append(("info",
                               f"{name}: ko_dep {dep} -- ensure its "
                               f"Module.symvers is in KBUILD_EXTRA_SYMBOLS"))
    return issues


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bazel", required=True, action="append",
                    help="Path to BUILD.bazel or *.bzl. Repeat for multiple files.")
    ap.add_argument("--kbuild", required=True,
                    help="Path to Kbuild file to verify")
    ap.add_argument("--strict", action="store_true",
                    help="Treat warnings as errors")
    args = ap.parse_args(argv)

    bazel_text = "\n".join(Path(p).read_text() for p in args.bazel if Path(p).exists())
    kbuild_text = Path(args.kbuild).read_text()

    bazel_modules = parse_bazel_modules(bazel_text)
    kbuild_parsed = parse_kbuild(kbuild_text)

    print(f"# bazel: {len(bazel_modules)} modules defined "
          f"({', '.join(m['name'] for m in bazel_modules if m['name'])})")
    print(f"# kbuild: {len(kbuild_parsed['obj_m'])} obj-m targets")

    issues = diff(bazel_modules, kbuild_parsed)
    if not issues:
        print("OK: no discrepancies found")
        return 0
    for sev, msg in issues:
        print(f"{sev}: {msg}")
    error_count = sum(1 for s, _ in issues if s == "error")
    warn_count = sum(1 for s, _ in issues if s == "warn")
    print(f"\n{error_count} error(s), {warn_count} warning(s)")
    if error_count or (args.strict and warn_count):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

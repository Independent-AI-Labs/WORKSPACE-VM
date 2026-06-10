#!/bin/bash
# Moon-driven flow phases for the e2e install test. Sourced by
# scripts/setup/test_install_e2e.sh — kept in a separate file so the
# main test script stays under the 512-line file-length contract.
#
# Phase 7 of the moon-as-orchestrator migration. Probes the post-
# migration workflow that the bare install test predates:
#
#   Phase 9:  moon project-graph integrity + mandatory tier 0+1 present
#   Phase 10: tag filtering — --tags python returns >0 projects
#   Phase 11: bootstrap-repos data-driven walk (no-op against
#             already-cloned workspace; catches script regressions)
#   Phase 12: cacheable check task — cold ci:lint vs cached run
#   Phase 13: update-walk topology — workspace:update graph
#             includes ci:update + dataops:update nodes
#
# All phases skip cleanly when moon binary isn't on PATH (smoke-test
# mode); hard-fail when moon IS available but produces broken output.

# Resolve moon binary once for all phases.
if [ -x ".boot-linux/bin/moon" ]; then
    MOON=".boot-linux/bin/moon"
elif command -v moon &> /dev/null; then
    MOON="moon"
else
    MOON=""
fi

# --- Phase 9: moon graph integrity ---
echo ""
echo "=========================================="
echo "PHASE 9: Moon graph integrity"
echo "=========================================="

if [ -z "$MOON" ]; then
    echo "[SKIP] moon binary not on PATH and not in .boot-linux/bin"
else
    "$MOON" project-graph --json > moon_graph.json 2>&1
    if [ $? -ne 0 ]; then
        echo "[FAIL] moon project-graph --json failed"
        head -20 moon_graph.json
        exit 1
    fi
    echo "[PASS] moon project-graph parses cleanly"

    for expected in workspace ci dataops; do
        if ! grep -q "\"id\": \"$expected\"" moon_graph.json; then
            echo "[FAIL] moon graph missing required project: $expected"
            exit 1
        fi
    done
    echo "[PASS] mandatory projects present in graph"
fi

# --- Phase 10: tag filter sanity ---
echo ""
echo "=========================================="
echo "PHASE 10: Tag filter sanity"
echo "=========================================="

if [ -n "$MOON" ]; then
    "$MOON" query projects --tags python > tagged_python.json 2>&1
    if [ $? -ne 0 ]; then
        echo "[FAIL] moon query projects --tags python failed"
        head tagged_python.json
        exit 1
    fi
    PYTHON_COUNT=$(.venv/bin/python -c \
        "import json; d=json.load(open('tagged_python.json')); print(len(d.get('projects',[])))" 2>&1)
    if [ -z "$PYTHON_COUNT" ] || [ "$PYTHON_COUNT" = "0" ]; then
        echo "[FAIL] python-tagged project count is 0 — tags missing or query broken"
        exit 1
    fi
    echo "[PASS] tags resolve: --tags python returns $PYTHON_COUNT projects"
fi

# --- Phase 11: bootstrap-repos data-driven walk ---
echo ""
echo "=========================================="
echo "PHASE 11: bootstrap-repos data-driven clone walk"
echo "=========================================="

if [ ! -x "workspace/scripts/bin/bootstrap-repos" ]; then
    echo "[FAIL] bootstrap-repos missing or not executable"
    exit 1
fi
if [ ! -f "workspace/config/workspace-clones.yaml" ]; then
    echo "[FAIL] workspace/config/workspace-clones.yaml missing"
    exit 1
fi
echo "[PASS] bootstrap-repos + workspace-clones.yaml present"

bash workspace/scripts/bin/bootstrap-repos > bootstrap_repos.log 2>&1
if [ $? -ne 0 ]; then
    echo "[FAIL] bootstrap-repos failed against already-cloned workspace"
    head bootstrap_repos.log
    exit 1
fi
if ! grep -q "bootstrap-repos:" bootstrap_repos.log; then
    echo "[FAIL] bootstrap-repos didn't emit expected status line"
    head bootstrap_repos.log
    exit 1
fi
echo "[PASS] bootstrap-repos walk succeeded"

# --- Phase 12: cacheable check task ---
echo ""
echo "=========================================="
echo "PHASE 12: Cacheable check task — cold + cached"
echo "=========================================="

if [ -n "$MOON" ]; then
    # rc captured for inspection; cache warmup is the intent.
    cold_start=$(date +%s%N)
    "$MOON" run ci:lint > moon_cold.log 2>&1; cold_rc=$?
    cold_end=$(date +%s%N)
    cold_ms=$(( (cold_end - cold_start) / 1000000 ))
    echo "[INFO] cold ci:lint = ${cold_ms}ms (rc=$cold_rc)"

    # rc captured; assertion is on duration + 'cached' marker.
    cached_start=$(date +%s%N)
    "$MOON" run ci:lint > moon_cached.log 2>&1; cached_rc=$?
    cached_end=$(date +%s%N)
    cached_ms=$(( (cached_end - cached_start) / 1000000 ))
    echo "[INFO] cached ci:lint = ${cached_ms}ms"

    if [ "$cached_ms" -gt 1000 ]; then
        echo "[FAIL] second run of ci:lint took ${cached_ms}ms — cache not working"
        exit 1
    fi
    if ! grep -q "cached" moon_cached.log; then
        echo "[FAIL] second run output missing 'cached' marker — cache not working"
        tail -5 moon_cached.log
        exit 1
    fi
    echo "[PASS] moon caching works (cold ${cold_ms}ms → cached ${cached_ms}ms)"
fi

# --- Phase 13: update-walk topology ---
echo ""
echo "=========================================="
echo "PHASE 13: update-walk ordering (^:update walks tier 0 → 1 → 2)"
echo "=========================================="

if [ -n "$MOON" ]; then
    "$MOON" action-graph "workspace:update" --dot > update_graph.dot 2>&1
    if [ $? -ne 0 ]; then
        echo "[FAIL] moon action-graph workspace:update failed"
        head update_graph.dot
        exit 1
    fi
    if ! grep -q "ci:update" update_graph.dot; then
        echo "[FAIL] update graph missing ci:update node"
        exit 1
    fi
    if ! grep -q "dataops:update" update_graph.dot; then
        echo "[FAIL] update graph missing dataops:update node"
        exit 1
    fi
    echo "[PASS] update-walk action graph includes ci:update + dataops:update"
fi

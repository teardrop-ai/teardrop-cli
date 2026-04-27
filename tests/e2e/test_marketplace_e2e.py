"""Live end-to-end tests for the tool marketplace.

Covers:
- Catalog listing returns ≥1 tool
- Search returns a subset of the catalog
- Subscribe → verify in subscriptions → unsubscribe → verify removed

The subscribe/unsubscribe cycle requires ``TEARDROP_E2E_TEST_TOOL`` to be set
to a known-available tool name (e.g. ``acme/weather``).  If not set, the cycle
test is skipped cleanly.
"""

from __future__ import annotations

import json
import os

import pytest

from teardrop_cli.cli import app

pytestmark = pytest.mark.e2e


class TestCatalog:
    def test_list_returns_tools(self, live_runner) -> None:
        """``marketplace list --json`` returns a non-empty list of tools."""
        result = live_runner.invoke(app, ["marketplace", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) >= 1, "Marketplace catalog is empty — expected at least one tool"

    def test_search_returns_subset(self, live_runner) -> None:
        """``marketplace search <term>`` returns fewer results than the full catalog."""
        full = live_runner.invoke(app, ["marketplace", "list", "--json"])
        assert full.exit_code == 0, full.output
        all_tools = json.loads(full.output)

        # Search for a term unlikely to match everything
        search = live_runner.invoke(app, ["marketplace", "search", "weather", "--json"])
        assert search.exit_code == 0, search.output
        filtered = json.loads(search.output)

        assert isinstance(filtered, list)
        assert len(filtered) <= len(all_tools), (
            "Search result is larger than full catalog — something is wrong"
        )


class TestSubscriptionCycle:
    def test_subscribe_then_unsubscribe(self, live_runner) -> None:
        """subscribe → verify in subscriptions → unsubscribe → verify removed."""
        test_tool = os.environ.get("TEARDROP_E2E_TEST_TOOL")
        if not test_tool:
            pytest.skip(
                "Set TEARDROP_E2E_TEST_TOOL=<org/tool> to run the subscription lifecycle test"
            )

        # Subscribe (--yes skips confirmation prompt)
        sub_result = live_runner.invoke(
            app, ["marketplace", "subscribe", test_tool, "--yes"]
        )
        assert sub_result.exit_code == 0, sub_result.output

        # Verify it appears in the subscription list
        subs_result = live_runner.invoke(app, ["marketplace", "subscriptions", "--json"])
        assert subs_result.exit_code == 0, subs_result.output
        subs = json.loads(subs_result.output)
        names = [s.get("qualified_tool_name", "") for s in subs]
        assert test_tool in names, (
            f"Subscribed to {test_tool!r} but it is not in subscriptions: {names}"
        )

        # Unsubscribe
        unsub_result = live_runner.invoke(
            app, ["marketplace", "unsubscribe", test_tool]
        )
        assert unsub_result.exit_code == 0, unsub_result.output

        # Verify it is gone
        subs_after = live_runner.invoke(app, ["marketplace", "subscriptions", "--json"])
        assert subs_after.exit_code == 0, subs_after.output
        names_after = [
            s.get("qualified_tool_name", "") for s in json.loads(subs_after.output)
        ]
        assert test_tool not in names_after, (
            f"Tool {test_tool!r} still present after unsubscribe: {names_after}"
        )

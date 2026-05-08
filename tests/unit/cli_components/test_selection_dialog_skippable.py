"""Regression tests for the select-all / deselect-all + skippable interaction.

The 'a' and 'n' shortcuts must keep `dialog.skipped` consistent with
`dialog.selected`, otherwise the renderer (which checks `skipped` before
the regular checkbox prefix) draws the wrong glyph for skippable items.
"""

from __future__ import annotations

from ami.cli_components.selection_dialog import (
    SelectionDialog,
    SelectionDialogConfig,
)


def _two_skippable_items() -> list[dict]:
    return [
        {"id": "a", "label": "A", "value": "a", "is_header": False},
        {"id": "b", "label": "B", "value": "b", "is_header": False},
    ]


class TestSelectAllSkippableInteraction:
    def test_a_key_clears_skipped_for_skippable_items(self) -> None:
        """Select-all removes skippable items from `skipped` so the renderer
        draws the selected checkbox instead of the skip glyph. Mirrors
        `_toggle_group_selection`'s 'select all' branch."""
        config = SelectionDialogConfig(multi=True, skippable_ids={"a", "b"})
        dialog = SelectionDialog(_two_skippable_items(), config)
        assert dialog.skipped == {0, 1}

        dialog._handle_key("a")

        assert dialog.selected == {0, 1}
        assert dialog.skipped == set()

    def test_n_key_restores_skipped_state_for_skippable_items(self) -> None:
        """Deselect-all puts skippable items back into `skipped` so the
        dialog returns to its initial appearance after 'a' then 'n'."""
        config = SelectionDialogConfig(multi=True, skippable_ids={"a", "b"})
        dialog = SelectionDialog(_two_skippable_items(), config)
        dialog._handle_key("a")
        assert dialog.skipped == set()

        dialog._handle_key("n")

        assert dialog.selected == set()
        assert dialog.skipped == {0, 1}

    def test_a_key_does_not_disturb_disabled_items(self) -> None:
        """Select-all skips disabled items so their state isn't churned.
        Mirrors `_toggle_group_selection`'s toggleable filter."""
        items = [
            {
                "id": "locked",
                "label": "Locked",
                "value": "x",
                "is_header": False,
                "disabled": True,
            },
            {"id": "open", "label": "Open", "value": "y", "is_header": False},
        ]
        config = SelectionDialogConfig(multi=True, skippable_ids={"locked"})
        dialog = SelectionDialog(items, config)
        initial_selected = set(dialog.selected)
        initial_skipped = set(dialog.skipped)

        dialog._handle_key("a")

        # `open` (idx 1) gets selected; `locked` (idx 0) untouched.
        assert dialog.selected == initial_selected | {1}
        assert dialog.skipped == initial_skipped

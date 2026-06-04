from workspace.cli.legend import (
    C_DIM,
    C_RESET,
    Legend,
    LegendGroup,
    LegendItem,
    get_visual_width,
    pad_center,
)

_HELLO_LEN = 5
_ABC123_LEN = 6
_W2 = 2
_W5 = 5
_W6 = 6
_PAD_6 = 6
_PAD_3 = 3
_PAD_4 = 4
_ONE_ITEM = 1
_THREE_ITEMS = 3
_W80 = 80
_W10 = 10


class TestGetVisualWidth:
    def test_ascii_text(self):
        assert get_visual_width("hello") == _HELLO_LEN
        assert get_visual_width("abc123") == _ABC123_LEN

    def test_ansi_codes_stripped(self):
        assert get_visual_width("\033[32mok\033[0m") == _W2
        assert get_visual_width("\033[1;36mhello\033[0m") == _HELLO_LEN

    def test_single_wide_emoji(self):
        assert get_visual_width("🟢") == _W2

    def test_variation_selector_emoji(self):
        assert get_visual_width("♻️") == _W2

    def test_east_asian_wide_character(self):
        assert get_visual_width("あ") == _W2

    def test_east_asian_fullwidth_character(self):
        assert get_visual_width("\uff21") == _W2

    def test_mixed_content(self):
        width = get_visual_width("🟢 ok")
        assert width == _W5

    def test_empty_string_returns_zero(self):
        assert get_visual_width("") == 0

    def test_multiple_emojis(self):
        width = get_visual_width("🟢🔴⚪")
        assert width == _W6


class TestPadCenter:
    def test_centers_text_with_padding(self):
        result = pad_center("ok", _PAD_6)
        assert result == "  ok  "

    def test_text_already_at_target_width(self):
        result = pad_center("abc", _PAD_3)
        assert result == "abc"

    def test_text_exceeding_width(self):
        result = pad_center("long_text", _PAD_4)
        assert result == "long_text"


class TestLegendItem:
    def test_constructor_sets_icon_and_label(self):
        item = LegendItem("🟢", "ok")
        assert item.icon == "🟢"
        assert item.label == "ok"

    def test_slots_restricts_attributes(self):
        item = LegendItem("🟢", "ok")
        try:
            item.extra = "value"
            has_extra = True
        except AttributeError:
            has_extra = False
        assert not has_extra


class TestLegendGroup:
    def test_empty_group(self):
        group = LegendGroup([])
        assert group.items == []

    def test_single_item(self):
        item = LegendItem("🟢", "ok")
        group = LegendGroup([item])
        assert len(group.items) == _ONE_ITEM
        assert group.items[0].icon == "🟢"
        assert group.items[0].label == "ok"

    def test_multiple_items(self):
        items = [
            LegendItem("🟢", "ok"),
            LegendItem("🔴", "fail"),
            LegendItem("🟡", "warn"),
        ]
        group = LegendGroup(items)
        assert len(group.items) == _THREE_ITEMS
        assert group.items[1].icon == "🔴"


class TestLegend:
    def test_single_group_dim_true(self):
        group = LegendGroup([LegendItem("🟢", "ok")])
        legend = Legend([group], dim=True)
        result = legend.render(_W80)

        assert result.icons_line.startswith(C_DIM)
        assert result.icons_line.endswith(C_RESET)
        assert result.labels_line.startswith(C_DIM)
        assert result.labels_line.endswith(C_RESET)

    def test_single_group_dim_false(self):
        group = LegendGroup([LegendItem("🟢", "ok")])
        legend = Legend([group], dim=False)
        result = legend.render(_W80)

        assert C_DIM not in result.icons_line
        assert C_DIM not in result.labels_line
        assert C_RESET not in result.icons_line
        assert C_RESET not in result.labels_line

    def test_multiple_groups_with_separator(self):
        group1 = LegendGroup([LegendItem("🟢", "ok")])
        group2 = LegendGroup([LegendItem("🔴", "fail")])
        legend = Legend([group1, group2], dim=False)
        result = legend.render(_W80)

        assert "│" in result.icons_line
        assert "│" in result.labels_line
        assert "🟢" in result.icons_line
        assert "🔴" in result.icons_line
        assert "ok" in result.labels_line
        assert "fail" in result.labels_line

    def test_custom_separator(self):
        group1 = LegendGroup([LegendItem("🟢", "ok")])
        group2 = LegendGroup([LegendItem("🔴", "fail")])
        legend = Legend([group1, group2], separator="/", dim=False)
        result = legend.render(_W80)

        assert " / " in result.icons_line
        assert " / " in result.labels_line

    def test_empty_groups_list(self):
        legend = Legend([], dim=False)
        result = legend.render(_W80)

        assert result.icons_line.strip() == ""
        assert result.labels_line.strip() == ""

    def test_narrow_width(self):
        group = LegendGroup([LegendItem("🟢", "ok")])
        legend = Legend([group], dim=False)
        result = legend.render(_W10)

        assert len(result.icons_line) > 0
        assert len(result.labels_line) > 0

    def test_render_returns_tuple_fields(self):
        group = LegendGroup([LegendItem("🟢", "ok")])
        legend = Legend([group], dim=False)
        result = legend.render(_W80)

        assert hasattr(result, "icons_line")
        assert hasattr(result, "labels_line")
        assert isinstance(result.icons_line, str)
        assert isinstance(result.labels_line, str)

    def test_dim_rendered_lines_have_prefix_suffix(self):
        group = LegendGroup([LegendItem("🟢", "ok")])
        legend = Legend([group], dim=True)
        result = legend.render(_W80)

        stripped_icons = result.icons_line
        inner_icons = stripped_icons[len(C_DIM) : -len(C_RESET)]
        assert not inner_icons.startswith(C_DIM)
        assert not inner_icons.endswith(C_RESET)

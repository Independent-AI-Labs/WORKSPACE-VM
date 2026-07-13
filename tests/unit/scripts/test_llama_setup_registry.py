"""Unit tests for llama-setup registry loader."""

from workspace.scripts.llama_setup_registry import load_registry, stack_by_id

MIN_STACK_COUNT = 5
MIN_PREREQ_COUNT = 4
LLAMAFILE_VULKAN_BUILD_STEPS = 3


def test_load_registry_has_default_stacks() -> None:
    registry = load_registry()
    assert len(registry.stacks) >= MIN_STACK_COUNT
    assert len(registry.prereqs) >= MIN_PREREQ_COUNT


def test_stack_by_id_llamafile_vulkan_server() -> None:
    registry = load_registry()
    stack = stack_by_id(registry, "llamafile_vulkan_server")
    assert stack is not None
    assert stack.deploy is not None
    assert stack.deploy.kind == "llamafile"
    assert stack.deploy.gpu == "vulkan"
    assert len(stack.build_steps) == LLAMAFILE_VULKAN_BUILD_STEPS

import subprocess
import sys
import textwrap


def test_core_and_fake_imports_do_not_load_optional_live_packages() -> None:
    script = textwrap.dedent(
        """
        import builtins
        import sys

        real_import = builtins.__import__

        def reject_optional_imports(name, globals=None, locals=None, fromlist=(), level=0):
            if name.split(".", 1)[0] in {"agents", "openai"}:
                raise AssertionError(f"optional package imported: {name}")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = reject_optional_imports

        import agent_course
        import agent_course.agents
        import agent_course.models
        from agent_course.models.fake import FakeModelGateway

        assert FakeModelGateway is not None
        assert "agents" not in sys.modules
        assert "openai" not in sys.modules
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

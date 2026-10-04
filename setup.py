"""Source launcher and setuptools build compatibility adapter."""
import sys

BUILD_COMMANDS = frozenset(("egg_info", "dist_info", "bdist_wheel", "sdist", "build", "build_py", "editable_wheel", "clean"))

def main(argv=None):
    from respectedbrain.cli import main as dispatch
    args = list(sys.argv[1:] if argv is None else argv)
    mode = "setup"
    for flag, command in (("--install", "setup"), ("--modify", "setup"), ("--update", "update"), ("--repair", "repair"), ("--uninstall", "uninstall"), ("--dashboard", "dashboard")):
        if flag in args:
            args.remove(flag)
            mode = command
            break
    args = ["--vault" if value == "--vault-path" else value for value in args]
    if mode == "setup" and not args:
        args = ["--gui"]
    return dispatch([mode, *args])

if __name__ == "__main__":
    if any(argument in BUILD_COMMANDS for argument in sys.argv[1:]):
        from setuptools import setup
        setup()
    else:
        raise SystemExit(main())

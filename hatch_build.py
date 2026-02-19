"""
Hatch build hook — shows welcome message after pip install.
"""

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        pass

    def finalize(self, version, build_data, artifact_path):
        try:
            from src.welcome import print_welcome
            print_welcome()
        except Exception:
            pass

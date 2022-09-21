import textwrap

from expkit.base.command.base import CommandTemplate, CommandOptions, CommandArgumentCount
from expkit.base.logger import get_logger
from expkit.framework.build_organizer import BuildOrganizer
from expkit.framework.database import register_command
from expkit.framework.parser import ConfigParser

LOGGER = get_logger(__name__)


@register_command
class ServerCommand(CommandTemplate):
    def __init__(self):
        super().__init__(".build", CommandArgumentCount(0, 2), textwrap.dedent('''\
            Builds an exploit according to the config.json file,
            the specified platform, and architecture.
            '''), textwrap.dedent('''\
            Builds an exploit according to the config.json file,
            the specified platform, and architecture. If no platform
            or architecture is specified, the default non-platform-arch-specific
            specific DUMMY platform or DUMMY architecture is used.
            '''))

    def get_pretty_description_header(self) -> str:
        return f"{super().get_pretty_description_header()} [platform] [architecture]"

    def _execute_command(self, options: CommandOptions, *args) -> bool:
        if options.config is None:
            LOGGER.critical("No config file specified.")

        parser = ConfigParser()
        root = parser.parse(options.config)

        build_organizer = BuildOrganizer(root)
        build_organizer.initialize()

        return True

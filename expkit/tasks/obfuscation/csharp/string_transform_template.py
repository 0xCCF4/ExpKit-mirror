import base64
import re
import threading
from pathlib import Path
from typing import List, Optional, Callable, Dict

from expkit.base.logger import get_logger
from expkit.base.architecture import PlatformArchitecture
from expkit.base.stage import StageTaskTemplate
from expkit.framework.database import register_task

def __transform_base64(input: str) -> str:
    if len(input) > 0:
        b64 = base64.b64encode(input.encode("utf8")).decode("utf8")
        out = f"Encoding.UTF8.GetString(Convert.FromBase64String(\"{b64}\"))"
    else:
        out = "\"\""
    return out


TRANSFORMATIONS = {
    "base64": __transform_base64
}

LOGGER = get_logger(__name__)

STATUS_NORMAL = 0
STATUS_STRING = 1
STATUS_AT_STRING = 2


@register_task
class CSharpStringTransformTemplate(StageTaskTemplate):
    def __init__(self):
        super().__init__(
            name="task.obfuscation.csharp.string_transform_template",
            description="Transforms all strings within CSharp source code to prevent signature detection of used strings.",
            platform=PlatformArchitecture.ALL,
            parameters={
                "files": Dict[str, str],  # target, origin
                "OBF_STRING_ENCODING": Optional[str]
            }  # mapping from input to output files
        )

        self.__status: int = 0
        self.__parse_lock = threading.Lock()

    def execute(self, parameters: dict) -> bool:
        super().execute(parameters)

        for target, origin in parameters["files"]:
            origin_path = Path(origin)
            target_path = Path(target)

            if not origin_path.exists() or not origin_path.is_file():
                LOGGER.error(f"Source file {origin} does not exist")
                return False

            if target_path.exists() and target_path.is_file():
                LOGGER.warning(f"Target source file {target} already exists")

            origin_source = origin_path.read_text("utf-8")

            transform = TRANSFORMATIONS.get(parameters.get("OBF_STRING_ENCODING", "base64"), None)
            if transform is None:
                LOGGER.error(f"Unknown string encoding {parameters.get('OBF_STRING_ENCODING', 'base64')}")
                return False

            LOGGER.debug(f"Transforming {origin} to {target}")
            target_source = self._transform(origin_source, transform)

            target_path.write_text(target_source, "utf-8")
            return True

    def _transform(self, source: str, transform: Callable[[re.Match], str]) -> str:
        with self.__parse_lock:
            self.__status = STATUS_NORMAL

            old_source = ""
            cmp = re.compile(r'(@)?(\"[^\"]|\"\")', re.MULTILINE | re.DOTALL)
            while old_source != source:
                old_source = source
                source = cmp.sub(self._parse_source, source, count=1)
            source = source.replace("\\{{CONTINUE_NA_STRING}}", "{{CONTINUE_NA_STRING}}")

            cmp = re.compile(r'(\{\{BEGIN_NA_STRING\}\})(.*?)(\{\{END_NA_STRING\}\})', re.MULTILINE | re.DOTALL)
            source = cmp.sub(self._replace_strings_normal, source)
            cmp = re.compile(r'(\{\{BEGIN_AT_STRING\}\})(.*?)(\{\{END_AT_STRING\}\})', re.MULTILINE | re.DOTALL)
            source = cmp.sub(transform, source)
            return source

    def _parse_source(self, match: re.Match) -> str:

        index = match.start()

        escaped_quote = False

        while index - 1 > 0:
            if match.string[index - 1] == "\\":
                escaped_quote = not escaped_quote
                index -= 1
            else:
                break

        at_sign = match.group(1) == "@"
        double_quote = match.group(2) == "\"\""
        prefix = "" if match.group(1) is None else match.group(1)
        postfix = match.group(2)[1:]

        result = match.group(0)

        if self.__status == STATUS_NORMAL:  # no string
            if at_sign:
                self.__status = STATUS_AT_STRING  # @ string
                token = "{{BEGIN_AT_STRING}}"
                result = token + postfix
            else:
                self.__status = STATUS_STRING  # normal string
                token = "{{BEGIN_NA_STRING}}"
                result = token + postfix
        elif self.__status == STATUS_AT_STRING:  # @ string
            if double_quote:
                token = "{{CONTINUE_AT_STRING}}"
                result = prefix + token
            else:
                self.__status = STATUS_NORMAL
                token = "{{END_AT_STRING}}"
                result = prefix + token + postfix
        elif self.__status == STATUS_STRING:  # normal string
            if escaped_quote:
                token = "{{CONTINUE_NA_STRING}}"
                result = prefix + token + postfix
            else:
                self.__status = STATUS_NORMAL
                token = "{{END_NA_STRING}}"
                result = prefix + token + postfix

        # print(match.string[index:match.start()], match.group(0), " --> ", result)
        return result

    def _replace_strings_normal(self, match: re.Match) -> str:
        prefix = match.group(1)
        content: str = match.group(2)
        postfix = match.group(3)

        def replace_slash(m):
            index = m.start()
            escape = False

            while index - 1 > 0:
                if m.string[index - 1] == "\\":
                    escape = not escape
                    index -= 1
                else:
                    break

            if escape:
                return m.group(0)

            operator = m.group(1)
            if operator == "\\":
                return "{{BL}}"
            elif operator == "n":
                return "\n"
            else:
                raise ValueError(f"Unknown operator {operator}")

        content_old = ""
        content_resolved = content
        while content_old != content_resolved:
            content_old = content_resolved
            content_resolved = re.sub(r'\\(.)', replace_slash, content_resolved, count=1)

        content_resolved = content_resolved.replace("{{BL}}", "\\")

        out = "{{BEGIN_AT_STRING}}" + content_resolved + "{{END_AT_STRING}}"
        # print(str(match.group(0)), " --> ", content, " --> ", content_resolved, " --> ", out)
        return out

"""Executable source contract for the exact authorized Remote screen source."""
import ast
import shlex


def validate_screen_target(source: str) -> bool:
    try:
        tree = ast.parse(source)
        selector = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "screen_target")
        scope = {"__builtins__": {}, "isinstance": isinstance, "int": int, "bool": bool,
                 "dict": dict, "ValueError": ValueError}
        exec(compile(ast.Module(body=[selector], type_ignores=[]), "<screen-target>", "exec"), scope)
        build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build")
        head = next(n.value for n in ast.walk(build) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "head" for t in n.targets))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "screen_target"]
        if len(calls) != 1 or [ast.unparse(arg) for arg in calls[0].args] != ["node_id", "node_props"]:
            return False
        parses = [n for n in ast.walk(build) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr == "parse_launch"]
        if not parses or not all(any(isinstance(n, ast.Name) and n.id == "head"
                                     for n in ast.walk(call.args[0])) for call in parses):
            return False
        for props, expected in (({"pipewire-serial": 1466}, ("target-object", 1466)), ({}, ("path", 78))):
            target = scope["screen_target"](78, props)
            if target != expected:
                return False
            ns = {"pipeline_fd": 12, "pipewire_target": target, "FRAME_KEEPALIVE_MS": 1000,
                  "state": {"fps": 30}}
            launch = eval(compile(ast.Expression(body=head), "<capture-prefix>", "eval"),
                          {"__builtins__": {}}, ns)
            words = shlex.split(launch.split("!", 1)[0])
            pairs = [word.split("=", 1) for word in words[1:]]
            settings = dict(pairs)
            if (words[0] != "pipewiresrc" or len(settings) != len(pairs)
                    or settings.get(expected[0]) != str(expected[1])
                    or ("path" if expected[0] == "target-object" else "target-object") in settings
                    or "node.dont-fallback=(boolean)true" not in settings.get("stream-properties", "")):
                return False
        return True
    except (SyntaxError, StopIteration, KeyError, ValueError, TypeError, NameError, IndexError):
        return False

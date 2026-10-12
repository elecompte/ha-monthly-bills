"""Check frontend registration using an in-memory HTTP/frontend double."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/monthly_bills"


class FrontendRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_static_files_and_versioned_module_are_registered(self):
        paths = []
        modules = []
        async def register(configs):
            paths.extend(configs)
        namespace = {
            "__file__": str(ROOT / "frontend.py"),
            "Path": Path,
            "StaticPathConfig": lambda *args: args,
            "frontend": SimpleNamespace(add_extra_js_url=lambda hass, url: modules.append(url)),
        }
        tree = ast.parse((ROOT / "frontend.py").read_text())
        nodes = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "frontend.py"), "exec"), namespace)
        hass = SimpleNamespace(http=SimpleNamespace(async_register_static_paths=register))
        await namespace["async_register_frontend"](hass)
        self.assertEqual(paths, [("/monthly_bills_static", str(ROOT / "www"), False)])
        self.assertEqual(modules, ["/monthly_bills_static/monthly-bills-badge.js?v=0.3.6"])
        self.assertTrue((ROOT / "www/monthly-bills-badge.js").is_file())

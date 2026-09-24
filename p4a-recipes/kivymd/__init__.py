import os
import shutil
from os.path import join

from pythonforandroid.logger import info
from pythonforandroid.recipe import PythonRecipe


class KivyMDRecipe(PythonRecipe):
    # KivyMD 1.1.1 was never published to PyPI (only 1.0.x / 2.0.0 are there),
    # so it is built from the GitHub source archive. It is pure python and its
    # only runtime dependencies are kivy + pillow (both available as recipes).
    #
    # NOTE: KivyMD's setup.py computes the `package_data` entry for *.kv files
    # with a dynamic glob (see the FIXME pointing at KivyMD issue #1305). That
    # does not survive p4a's `pip install .` (PEP 517 build), so the .kv UI
    # definition files are missing from site-packages and KivyMD then dies at
    # import time with:
    #     FileNotFoundError: .../kivymd/uix/card/card.kv
    # Therefore, after the normal build, every non-.py file from the source
    # tree is copied into the installed package.
    version = "1.1.1"
    url = "https://github.com/kivymd/KivyMD/archive/{version}.zip"
    site_packages_name = "kivymd"
    depends = ["kivy", "pillow"]

    def _find_source_package(self, arch):
        build_dir = self.get_build_dir(arch.arch)
        guesses = [join(build_dir, "kivymd")]
        try:
            entries = os.listdir(build_dir)
        except OSError:
            entries = []
        for entry in entries:
            guesses.append(join(build_dir, entry, "kivymd"))
        for guess in guesses:
            if os.path.isfile(join(guess, "__init__.py")):
                return guess
        return None

    def _site_packages_dir(self, arch):
        ctx = self.ctx
        candidates = [
            (getattr(ctx, "get_site_packages_dir", None), arch),
            (getattr(ctx, "get_site_packages_dir", None), arch.arch),
            (getattr(ctx, "get_python_install_dir", None), arch.arch),
        ]
        for fn, arg in candidates:
            if fn is None:
                continue
            try:
                path = fn(arg)
            except Exception:
                continue
            if path and os.path.isdir(path):
                return path
        return None

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)
        src_pkg = self._find_source_package(arch)
        site_root = self._site_packages_dir(arch)
        if not src_pkg or not site_root:
            info("kivymd: could not locate source/site-packages dirs, "
                 "skipping data-file copy")
            return
        dst_pkg = join(site_root, "kivymd")
        copied = 0
        for root, _dirs, files in os.walk(src_pkg):
            for filename in files:
                if filename.endswith((".py", ".pyc", ".pyo")):
                    continue
                rel = os.path.relpath(join(root, filename), src_pkg)
                target = join(dst_pkg, rel)
                if os.path.exists(target):
                    continue
                target_dir = os.path.dirname(target)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(join(root, filename), target)
                copied += 1
        info("kivymd: copied {} data files (*.kv, *.ttf, ...) into "
             "site-packages/kivymd".format(copied))


recipe = KivyMDRecipe()

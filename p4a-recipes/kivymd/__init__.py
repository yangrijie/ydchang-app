from pythonforandroid.recipe import PythonRecipe


class KivyMDRecipe(PythonRecipe):
    # KivyMD 1.1.1 was never published to PyPI (only 1.0.x / 2.0.0 are there),
    # so build it from the GitHub source archive. It is a pure-python package
    # whose only runtime deps are kivy + pillow (both available as recipes).
    version = "1.1.1"
    url = "https://github.com/kivymd/KivyMD/archive/{version}.zip"
    site_packages_name = "kivymd"
    depends = ["kivy", "pillow"]


recipe = KivyMDRecipe()

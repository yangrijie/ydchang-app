[app]
title = 源达投顾
package.name = org.ydchang.app
package.domain = org
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,txt,db
source.include_dirs = assets

version = 1.0.0

# kivymd pinned to 1.1.1: the UI code uses KivyMD 1.x APIs
# (kivymd.uix.toolbar.MDTopAppBar, MDDialog(title/text/buttons), MDFlatButton,
#  MDRaisedButton, MDLabel(font_style/theme_text_color) ...) which were removed
# or renamed in KivyMD 2.0. KivyMD 1.1.1 only needs kivy + pillow.
requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.1,kivymd==1.1.1,pillow,requests

android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED

android.api = 33
android.minapi = 24
android.build_tools_version = 33.0.0
# p4a develop's libthorvg (a kivy dependency) needs libomp.so shipped with newer NDKs.
android.ndk = 28c

android.archs = arm64-v8a, armeabi-v7a

services = YDChangService:services.ydchang_service

android.private_storage = True

android.release_artifact = apk

p4a.local_recipes = ./p4a-recipes

# master's run_pymodules_install has a broken "pip install -U pip" step that
# corrupts the build venv pip (open_rich_spinner ImportError) -> use develop
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 0
build_dir = .buildozer

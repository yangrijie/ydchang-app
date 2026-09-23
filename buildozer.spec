[app]
title = 源达投顾
package.name = org.ydchang.app
package.domain = org
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,txt,db
source.include_dirs = assets

version = 1.0.0

requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0,kivymd==2.0.0,materialyoucolor,pillow,materialshapes,pycairo,asynckivy,requests

android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED

android.api = 33
android.minapi = 24
android.build_tools_version = 33.0.0
android.ndk = 25b

android.archs = arm64-v8a, armeabi-v7a

services = YDChangService:services.ydchang_service

android.private_storage = True

android.release_artifact = apk

# local recipe dir (overrides materialyoucolor version to 3.0.4)
p4a.local_recipes = ./p4a-recipes

# use develop branch: master's run_pymodules_install has a broken "pip install -U pip"
# step that corrupts the build venv pip (open_rich_spinner ImportError)
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 0
build_dir = .buildozer

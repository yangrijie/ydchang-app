[app]
title = 源达投顾
package.name = org.ydchang.app
package.domain = org
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,txt,db
source.include_dirs = assets

version = 1.0.0

requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0,kivymd==2.0.0,requests
android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED

android.api = 33
android.minapi = 24
android.build_tools_version = 33.0.0
android.ndk = 25b

services = YDChangService:services.ydchang_service

android.private_storage = True

android.release_artifact = apk

# avoid pip dependency resolution failures for kivymd on Android
android.pip = --no-deps

[buildozer]
log_level = 2
warn_on_root = 0
build_dir = .buildozer

android.archs = arm64-v8a, armeabi-v7a

p4a.branch = stable
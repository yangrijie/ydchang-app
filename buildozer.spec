[app]
title = 源达投顾
package.name = org.ydchang.app
package.domain = org
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,txt,db
source.include_dirs = assets

version = 1.0.0

requirements = python3,kivy==2.1.0,kivymd==1.1.1,requests
# 必须包含的权限:
#   INTERNET - 网络访问
#   ACCESS_NETWORK_STATE - 检测网络状态
#   FOREGROUND_SERVICE - 前台服务(锁屏持续采集)
#   POST_NOTIFICATIONS - Android 13+ 显示前台服务通知
#   WAKE_LOCK - 锁屏后 CPU 保持唤醒
#   RECEIVE_BOOT_COMPLETED - 开机自启(可选)
android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED

# 前台服务类型,Android 14+ 强制要求
android.api = 33
android.minapi = 24
# 指定 build-tools 版本 (与 workflow 中安装的一致)
android.build_tools_version = 33.0.0
# SDK 路径由 Docker 镜像 (kivy/buildozer) 内部管理,不在这里指定

# 服务/前台 Service 配置
services = YDChangService:services.ydchang_service

# 资源/图标
# (使用默认图标,后续可替换)
# icon.filename = %(source.dir)s/assets/icon.png

# 不需要访问外部存储 (DB 在 app 私有目录)
android.private_storage = True

# 调试时可以 false, 发布时 true (签名)
android.release_artifact = aapk-debug

[buildozer]
log_level = 2
# Docker 容器内以 root 运行,需要关闭 root 警告
warn_on_root = 0

# 构建环境
build_dir = .buildozer

# 架构: 兼容绝大多数安卓设备 (arm64-v8a 为主)
android.archs = arm64-v8a, armeabi-v7a

# 不使用 p4a 的 master,使用稳定版
p4a.branch = stable

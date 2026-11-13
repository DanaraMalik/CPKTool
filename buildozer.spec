[app]
title = CPK Tool eFootball
package.name = cpktool
package.domain = org.cpkmod
source.dir = .
source.include_exts = py,png,jpg,kv,json
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pyjnius,android
orientation = portrait
fullscreen = 0
android.permissions = MANAGE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.ndk = 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1

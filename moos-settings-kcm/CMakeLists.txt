cmake_minimum_required(VERSION 3.24)
project(moos_settings_kcm LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ECM 6.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Quick Qml)
find_package(KF6 6.0 REQUIRED COMPONENTS CoreAddons KCMUtils I18n)

kcmutils_add_qml_kcm(kcm_moos DISABLE_DESKTOP_FILE_GENERATION SOURCES moos_settings.cpp)
target_link_libraries(kcm_moos PRIVATE Qt6::Core Qt6::Quick Qt6::Qml
    KF6::CoreAddons KF6::KCMUtils KF6::I18n)

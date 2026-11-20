cmake_minimum_required(VERSION 3.16.0)
# Keep the existing version stable when building without Git commits or tags.
set(PROJECT_VER "1")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(zk_stark_private_maintenance)


cmake_minimum_required(VERSION 3.20)

project(MasterThesis LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Performance experiments must be optimised. Without this, a plain
# `cmake -S . -B build` would give an unoptimised build (about 35x slower).
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_subdirectory(experiments/01-matrix-multiplication)
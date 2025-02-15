# Find SIP
# ~~~~~~~~
#
# SIP website: http://www.riverbankcomputing.co.uk/sip/index.php
#
# Find the installed version of SIP. FindSIP should be called after Python
# has been found.
#
# This file defines the following variables:
#
# SIP_VERSION - The version of SIP found expressed as a 6 digit hex number
#     suitable for comparison as a string.
#
# SIP_VERSION_STR - The version of SIP found as a human readable string.
#
# SIP_EXECUTABLE - Path and filename of the SIP command line executable.
#
# SIP_INCLUDE_DIR - Directory holding the SIP C++ header file.
#
# SIP_DEFAULT_SIP_DIR - Default directory where .sip files should be installed
#     into.

# Copyright (c) 2007, Simon Edwards <simon@simonzone.com>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.



IF(SIP_VERSION)
  # Already in cache, be silent
  SET(SIP_FOUND TRUE)
ELSE(SIP_VERSION)

  if (EXISTS "${CMAKE_MODULE_PATH}/FindSIP.py")
    set (_find_sip_py "${CMAKE_MODULE_PATH}/FindSIP.py")
  else()
    FIND_FILE(_find_sip_py FindSIP.py PATHS ${CMAKE_MODULE_PATH})
  endif()

  if (NOT EXISTS ${_find_sip_py})
    message(FATAL_ERROR "Failed to find FindSIP.py in \"${CMAKE_MODULE_PATH}\"")
  endif()

  EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${_find_sip_py} OUTPUT_VARIABLE sip_config)
  IF(sip_config)
    STRING(REGEX REPLACE "^sip_version:([^\n]+).*$" "\\1" SIP_VERSION ${sip_config})
    STRING(REGEX REPLACE ".*\nsip_version_str:([^\n]+).*$" "\\1" SIP_VERSION_STR ${sip_config})
    STRING(REGEX REPLACE ".*\nsip_bin:([^\n]+).*$" "\\1" SIP_EXECUTABLE ${sip_config})
    IF(NOT SIP_DEFAULT_SIP_DIR)
        STRING(REGEX REPLACE ".*\ndefault_sip_dir:([^\n]+).*$" "\\1" SIP_DEFAULT_SIP_DIR ${sip_config})
    ENDIF(NOT SIP_DEFAULT_SIP_DIR)
    STRING(REGEX REPLACE ".*\nsip_inc_dir:([^\n]+).*$" "\\1" SIP_INCLUDE_DIRECTORY ${sip_config})
    SET(SIP_FOUND TRUE)
  ENDIF(sip_config)

  # Check that it really exists
  FIND_PATH( SIP_INCLUDE_DIR sip.h PATHS ${SIP_INCLUDE_DIRECTORY} )

  include ( FindPackageHandleStandardArgs )
  find_package_handle_standard_args( SIP DEFAULT_MSG SIP_VERSION_STR SIP_INCLUDE_DIR SIP_EXECUTABLE )

#  IF(SIP_FOUND)
#    IF(NOT SIP_FIND_QUIETLY)
#      MESSAGE(STATUS "Found SIP version: ${SIP_VERSION_STR}")
#    ENDIF(NOT SIP_FIND_QUIETLY)
#  ELSE(SIP_FOUND)
#    IF(SIP_FIND_REQUIRED)
#      MESSAGE(FATAL_ERROR "Could not find SIP")
#    ENDIF(SIP_FIND_REQUIRED)
#  ENDIF(SIP_FOUND)

  mark_as_advanced ( _find_sip_py )

ENDIF(SIP_VERSION)

#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# -*- coding: utf-8 -*-
"""SUSCRCPY 2.0.0 Desktop Application Launcher."""
import os
import sys

if sys.platform.startswith("linux") and "DISPLAY" in os.environ:
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

from main import main

if __name__ == "__main__":
    sys.exit(main())

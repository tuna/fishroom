#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import print_function, division, unicode_literals
import sys
from os.path import dirname
sys.path.insert(0, dirname(dirname(__file__)))
from fishroom.textstore import Vinergy


if __name__ == "__main__":

    p = Vinergy()
    print(p.new_paste("test new paste, lallala", "bigeagle"))

# vim: ts=4 sw=4 sts=4 expandtab

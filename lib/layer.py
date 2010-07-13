# This file is part of MyPaint.
# Copyright (C) 2007-2008 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from numpy import *

import tiledsurface, strokemap, strokemap_pb2

class Layer:
    def __init__(self,name=""):
        self.surface = tiledsurface.Surface()
        self.opacity = 1.0
        self.name = name
        self.visible = True
        self.clear()

    def get_effective_opacity(self):
        if self.visible:
            return self.opacity
        else:
            return 0.0
    effective_opacity = property(get_effective_opacity)

    def clear(self):
        self.strokes = [] # contains StrokeInfo instances (not stroke.Stroke)
        self.surface.clear()

    def load_from_pixbuf(self, pixbuf):
        self.strokes = []
        self.surface.load_from_data(pixbuf)

    def save_snapshot(self):
        return (self.strokes[:], self.surface.save_snapshot(), self.opacity)

    def load_snapshot(self, data):
        strokes, data, self.opacity = data
        self.strokes = strokes[:]
        self.surface.load_snapshot(data)

    def add_stroke(self, stroke, snapshot_before):
        before = snapshot_before[1] # extract surface snapshot
        after  = self.surface.save_snapshot()
        info = strokemap.StrokeInfo()
        info.init_from_snapshots(stroke.brush_settings, before, after)
        self.strokes.append(info)

    def save_strokemap_to_string(self, translate_x, translate_y):
        sl = strokemap_pb2.StrokeList()
        for stroke in self.strokes:
            stroke_pb = sl.strokes.add()
            stroke.save_to_pb(stroke_pb, translate_x, translate_y)
        return sl.SerializeToString()

    def load_strokemap_from_string(self, data, translate_x, translate_y):
        sl = strokemap_pb2.StrokeList()
        sl.ParseFromString(data)
        for stroke_pb in sl.strokes:
            stroke = strokemap.StrokeInfo()
            stroke.init_from_pb(stroke_pb, translate_x, translate_y)
            self.strokes.append(stroke)

    def merge_into(self, dst):
        """
        Merge this layer into dst, modifying only dst.
        """
        # We must respect layer visibility, because saving a
        # transparent PNG just calls this function for each layer.
        src = self
        dst.strokes.extend(self.strokes)
        for tx, ty in dst.surface.get_tiles():
            surf = dst.surface.get_tile_memory(tx, ty, readonly=False)
            surf[:,:,:] *= dst.effective_opacity
        for tx, ty in src.surface.get_tiles():
            surf = dst.surface.get_tile_memory(tx, ty, readonly=False)
            src.surface.composite_tile_over(surf, tx, ty, opacity=src.effective_opacity)
        dst.opacity = 1.0

    def merge_step(self, dst, step):
        """
        Merge this layer partially into dst, modifying both src and dst.
        """
        # We must respect layer visibility, because saving a
        # transparent PNG just calls this function for each layer.
        assert step >= 0 and step <= 1
        src = self
        print '.'
        for tx, ty in src.surface.get_tiles():
            # modify dst
            surf = dst.surface.get_tile_memory(tx, ty, readonly=False)
            src.surface.composite_tile_over(surf, tx, ty, opacity=src.effective_opacity*step)

            # modify src
            surf = src.surface.get_tile_memory(tx, ty, readonly=False)
            surf[:,:,:] *= 1.0 - step


    def get_stroke_info_at(self, x, y):
        x, y = int(x), int(y)
        for s in reversed(self.strokes):
            if s.touches_pixel(x, y):
                return s




# This file is part of MyPaint.
# Copyright (C) 2008 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This class converts between flat 8bit RGB(A) and tiled RGBA storage.
# It is used for rendering updates, but also for save/load.

from gtk import gdk
import mypaintlib,  helpers
from tiledsurface import N
import sys, numpy

class Surface:
    """Wraps a gdk.Pixbuf, making its memory accessible by tile.

    Pixbuf-surfaces use a gdk.Pixbuf (8 bit RGBU or RGBA data) for storage,
    with memory also accessible per-tile, compatible with tiledsurface.Surface.
    The RGB data is stored with gamma compression because pixbufs are designed
    for immediate display.
    """

    def __init__(self, x, y, w, h, alpha=False, data=None):
        assert w>0 and h>0
        # We create and use a pixbuf enlarged to the tile boundaries internally.
        # Variables ex, ey, ew, eh and epixbuf store the enlarged version.
        self.x, self.y, self.w, self.h = x, y, w, h
        #print x, y, w, h
        tx = self.tx = x/N
        ty = self.ty = y/N
        self.ex = tx*N
        self.ey = ty*N
        tw = (x+w-1)/N - tx + 1
        th = (y+h-1)/N - ty + 1

        self.ew = tw*N
        self.eh = th*N

        #print 'b:', self.ex, self.ey, self.ew, self.eh
        # OPTIMIZE: remove assertions here?
        assert self.ew >= w and self.eh >= h
        assert self.ex <= x and self.ey <= y

        self.has_alpha = alpha

        self.epixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, True, 8, self.ew, self.eh)
        dx = x-self.ex
        dy = y-self.ey
        self.pixbuf  = self.epixbuf.subpixbuf(dx, dy, w, h)

        assert self.ew <= w + 2*N-2
        assert self.eh <= h + 2*N-2

        if not alpha:
            if mypaintlib.heavy_debug:
                # detect uninitialized memory; slows down scrolling slightly
                self.epixbuf.fill(0xff44ff44)
        else:
            self.epixbuf.fill(0x00000000) # keep undefined regions transparent

        arr = helpers.gdkpixbuf2numpy(self.epixbuf)

        discard_transparent = False

        if data is not None:
            dst = arr[dy:dy+h,dx:dx+w,:]
            assert data.shape[2] == 4, 'rgbu or rgba expected, not rgb'
            dst[:,:,:] = data
            if self.has_alpha:
                # this surface will be used read-only
                discard_transparent = True

        self.tile_memory_dict = {}
        for ty in range(th):
            for tx in range(tw):
                buf = arr[ty*N:(ty+1)*N,tx*N:(tx+1)*N,:]
                if discard_transparent and not buf[:,:,3].any():
                    continue
                self.tile_memory_dict[(self.tx+tx, self.ty+ty)] = buf

    def get_tiles(self):
        return self.tile_memory_dict.keys()

    def get_tile_memory(self, tx, ty):
        return self.tile_memory_dict[(tx, ty)]

    def blit_tile_into(self, dst, dst_has_alpha, tx, ty):
        """Extracts linear rgba16 data, as used elsewhere.
        """
        assert dst_has_alpha is True
        assert dst.dtype == 'uint16', '16 bit dst expected'
        src = self.tile_memory_dict[(tx, ty)]
        mypaintlib.tile_convert_nonlinear_rgba8_to_linear_rgba16(src, dst)

# throttle excesssive calls to the save/render feedback_cb
TILES_PER_CALLBACK = 256

def render_as_pixbuf(surface, *rect, **kwargs):
    alpha = kwargs.get('alpha', False)
    mipmap_level = kwargs.get('mipmap_level', 0)
    feedback_cb = kwargs.get('feedback_cb', None)
    if not rect:
        rect = surface.get_bbox()
    x, y, w, h, = rect
    s = Surface(x, y, w, h, alpha)
    tn = 0
    for tx, ty in s.get_tiles():
        dst = s.get_tile_memory(tx, ty)
        surface.blit_tile_into(dst, alpha, tx, ty, mipmap_level=mipmap_level)
        if feedback_cb is not None and tn % TILES_PER_CALLBACK == 0:
            feedback_cb()
        tn += 1
    return s.pixbuf

def save_as_png(surface, filename, *rect, **kwargs):
    alpha = kwargs['alpha']
    feedback_cb = kwargs.get('feedback_cb', None)
    if not rect:
        rect = surface.get_bbox()
    x, y, w, h, = rect
    assert x % N == 0 and y % N == 0, 'only saving of full tiles is implemented (for now)'
    assert w % N == 0 and h % N == 0, 'only saving of full tiles is implemented (for now)'
    if w == 0 or h == 0:
        # workaround to save empty documents
        x, y, w, h = 0, 0, N, N

    arr = numpy.empty((N, w, 4), 'uint8') # rgba or rgbu

    tn_ref = [0]   # is there a nicer way of letting callbacks in swig code increment this?
    ty_list = range(y/N, (y+h)/N)

    def render_tile_scanline():
        ty = ty_list.pop(0)
        for tx_rel in xrange(w/N):
            # OPTIMIZE: shortcut for empty tiles (not in tiledict)?
            dst = arr[:,tx_rel*N:(tx_rel+1)*N,:]
            surface.blit_tile_into(dst, alpha, x/N+tx_rel, ty)
            if feedback_cb is not None and tn_ref[0] % TILES_PER_CALLBACK == 0:
                feedback_cb()
            tn_ref[0] += 1
        return arr

    if kwargs.get('single_tile_pattern', False):
        render_tile_scanline()
        def render_tile_scanline():
            return arr

    filename_sys = filename.encode(sys.getfilesystemencoding()) # FIXME: should not do that, should use open(unicode_object)
    mypaintlib.save_png_fast_progressive(filename_sys, w, h, alpha, render_tile_scanline)

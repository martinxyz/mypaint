# This file is part of MyPaint.
# Copyright (C) 2009 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import numpy, gtk
gdk = gtk.gdk

import mypaintlib, helpers
from tiledsurface import N, MAX_MIPMAP_LEVEL, get_tiles_bbox
import pixbufsurface

class BackgroundError(Exception):
    pass


class Background:
    """A background surface.

    Internally, the tiles use uint16 linear light.
    """

    def __init__(self, obj, mipmap_level=0):
        """Constructs from a pixbuf, an rgb triple, or a numpy array.

        `obj` is either a ``gdk.Pixbuf``, an RGB triple whose elements range
        from 0 to 255, or a ``numpy.ndarray``. The array case is used
        internally along with `mipmap_level` when generating mipmaps.
        """
        gamma_expand = False
        if isinstance(obj, gdk.Pixbuf):
            obj = helpers.gdkpixbuf2numpy(obj)
            gamma_expand = True
        elif not isinstance(obj, numpy.ndarray):
            r, g, b = obj
            obj = numpy.zeros((N, N, 3), dtype='uint8')
            obj[:,:,:] = r, g, b
            # Assume linear. Similarly, any numpy arrays passed in
            # are assumed to be already linear.

        h, w = obj.shape[0:2]
        self.tw = w/N
        self.th = h/N
        #print obj
        if obj.shape[0:2] != (self.th*N, self.tw*N):
            raise BackgroundError, 'unsupported background tile size: %dx%d' \
              % (w, h)

        if gamma_expand:
            tmp_obj = numpy.empty((h, w, 4), dtype='uint8')
            tmp_obj[:,:,:3] = obj
            tmp_obj[:,:,3] = 255
            obj = pixbufsurface.Surface(0, 0, w, h, alpha=False, data=tmp_obj)
            del tmp_obj
        elif obj.dtype == 'uint8':
            obj = (obj.astype('uint32') * (1<<15) / 255).astype('uint16')

        # Populate tiles
        self.tiles = {}
        for ty in range(self.th):
            for tx in range(self.tw):
                tile = numpy.empty((N, N, 4), dtype='uint16') # rgbu
                if gamma_expand:
                    obj.blit_tile_into(tile, True, tx, ty)
                else:
                    tile[:,:,:3] = obj[N*ty:N*(ty+1), N*tx:N*(tx+1), :3]
                self.tiles[tx, ty] = tile
        del obj

        # generate mipmap
        self.mipmap_level = mipmap_level
        if mipmap_level < MAX_MIPMAP_LEVEL:
            mipmap_obj = numpy.zeros((self.th*N, self.tw*N, 4), dtype='uint16')
            for ty in range(self.th*2):
                for tx in range(self.tw*2):
                    src = self.get_tile_memory(tx, ty)
                    mypaintlib.tile_downscale_rgba16(src, mipmap_obj, tx*N/2, ty*N/2)
            self.mipmap = Background(mipmap_obj, mipmap_level+1)

    def get_tile_memory(self, tx, ty):
        return self.tiles[(tx%self.tw, ty%self.th)]

    def blit_tile_into(self, dst, dst_has_alpha, tx, ty, mipmap_level=0):
        assert dst_has_alpha is False
        if self.mipmap_level < mipmap_level:
            return self.mipmap.blit_tile_into(dst, dst_has_alpha, tx, ty, mipmap_level)
        rgbu = self.get_tile_memory(tx, ty)
        # render solid or tiled background
        #dst[:] = rgb # 13 times slower than below, with some bursts having the same speed as below (huh?)
        # note: optimization for solid colors is not worth it, it gives only 2x speedup (at best)
        if dst.dtype == 'uint16':
            # this will do memcpy, not worth to bother skipping the u channel
            mypaintlib.tile_copy_rgba16_into_rgba16(rgbu, dst)
        else:
            # this case is for saving the background
            assert dst.dtype == 'uint8'
            # note: when saving the background layer we usually
            # convert here the same tile over and over again. But it
            # does help much to cache this conversion result. The
            # save_ora speedup when doing this is below 1%, even for a
            # single-layer ora.
            mypaintlib.tile_convert_linear_rgbu16_to_nonlinear_rgbu8(rgbu, dst)

    def get_pattern_bbox(self):
        return get_tiles_bbox(self.tiles)

    def save_as_png(self, filename, *rect, **kwargs):
        assert 'alpha' not in kwargs
        kwargs['alpha'] = False
        if len(self.tiles) == 1:
            kwargs['single_tile_pattern'] = True
        pixbufsurface.save_as_png(self, filename, *rect, **kwargs)

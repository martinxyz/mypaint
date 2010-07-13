# This file is part of MyPaint.
# Copyright (C) 2008 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import gtk, gobject, cairo, random
gdk = gtk.gdk
from math import floor, ceil, pi, log

from lib import helpers, tiledsurface, pixbufsurface
import cursor

class TiledDrawWidget(gtk.DrawingArea):
    """
    This widget displays a document (../lib/document*.py).
    
    It can show the document translated, rotated or zoomed. It does
    not respond to user input except for painting. Painting events are
    passed to the document after applying the inverse transformation.
    """

    def __init__(self, document):
        gtk.DrawingArea.__init__(self)
        self.connect("expose-event", self.expose_cb)
        self.connect("enter-notify-event", self.enter_notify_cb)
        self.connect("leave-notify-event", self.leave_notify_cb)
        self.connect("size-allocate", self.size_allocate_cb)

        # workaround for https://gna.org/bugs/?14372
        def at_application_start(*trash):
            self.connect("motion-notify-event", self.motion_notify_cb)
            self.connect("button-press-event", self.button_press_cb)
        gobject.idle_add(at_application_start)

        self.set_events(gdk.EXPOSURE_MASK
                        | gdk.POINTER_MOTION_MASK
                        | gdk.ENTER_NOTIFY_MASK
                        | gdk.LEAVE_NOTIFY_MASK
                        # for some reason we also need to specify events handled in drawwindow.py:
                        | gdk.BUTTON_PRESS_MASK
                        | gdk.BUTTON_RELEASE_MASK
                        )

        self.set_extension_events (gdk.EXTENSION_EVENTS_ALL)

        self.doc = document
        self.doc.canvas_observers.append(self.canvas_modified_cb)
        self.doc.brush.settings_observers.append(self.brush_modified_cb)

        self.cursor_info = None

        self.last_event_time = None
        self.last_event_x = None
        self.last_event_y = None
        self.last_event_device = None
        self.last_painting_pos = None
        self.device_observers = []

        self.visualize_rendering = False

        self.translation_x = 0.0
        self.translation_y = 0.0
        self.scale = 1.0
        self.rotation = 0.0
        self.mirrored = False
        # only used when forcing translation_x/y aligned to full pixels
        self.translation_subpixel_x = 0.0
        self.translation_subpixel_y = 0.0

        self.has_pointer = False
        self.dragfunc = None

        self.current_layer_solo = False
        self.show_layers_above = True

        self.overlay_layer = None

        # gets overwritten for the main window
        self.zoom_max = 5.0
        self.zoom_min = 1/5.0
        
        #self.scroll_at_edges = False
        self.pressure_mapping = None
        self.bad_devices = []

    #def set_scroll_at_edges(self, choice):
    #    self.scroll_at_edges = choice
      
    def enter_notify_cb(self, widget, event):
        self.has_pointer = True
    def leave_notify_cb(self, widget, event):
        self.has_pointer = False

    def size_allocate_cb(self, widget, allocation):
        new_size = tuple(allocation)[2:4]
        old_size = getattr(self, 'current_size', new_size)
        self.current_size = new_size
        if new_size != old_size:
            # recenter
            dx = old_size[0] - new_size[0]
            dy = old_size[1] - new_size[1]
            self.scroll(dx/2, dy/2)

    def motion_notify_cb(self, widget, event):
        if self.last_event_time:
            dtime = (event.time - self.last_event_time)/1000.0
            dx = event.x - self.last_event_x
            dy = event.y - self.last_event_y
        else:
            dtime = None
        if event.device != self.last_event_device:
            for f in self.device_observers:
                f(self.last_event_device, event.device)
        self.last_event_x = event.x
        self.last_event_y = event.y
        self.last_event_time = event.time
        self.last_event_device = event.device
        if dtime is None:
            return

        if self.dragfunc:
            self.dragfunc(dx, dy)
            return

        cr = self.get_model_coordinates_cairo_context()
        x, y = cr.device_to_user(event.x, event.y)
        
        pressure = event.get_axis(gdk.AXIS_PRESSURE)

        if pressure is not None and (pressure > 1.0 or pressure < 0.0):
            if event.device.name not in self.bad_devices:
                print 'WARNING: device "%s" is reporting bad pressure %+f' % (event.device.name, pressure)
                self.bad_devices.append(event.device.name)
            if pressure > 1000.0 or pressure < -1000.0:
                # infinity: use button state (instead of clamping in brush.hpp)
                # https://gna.org/bugs/?14709
                pressure = None

        if pressure is None:
            if event.state & gdk.BUTTON1_MASK:
                pressure = 0.5
            else:
                pressure = 0.0
        
        if event.state & gdk.CONTROL_MASK:
            # color picking, do not paint
            # Don't simply return; this is a workaround for unwanted lines in https://gna.org/bugs/?16169
            pressure = 0.0
            
        ### CSS experimental - scroll when touching the edge of the screen in fullscreen mode
        #
        # Disabled for the following reasons:
        # - causes irritation when doing fast strokes near the edge
        # - scrolling speed depends on the number of events received (can be a huge difference between tablets/mouse)
        # - also, mouse button scrolling is usually enough
        #
        #if self.scroll_at_edges and pressure <= 0.0:
        #  screen_w = gdk.screen_width()
        #  screen_h = gdk.screen_height()
        #  trigger_area = 10
        #  if (event.x <= trigger_area):
        #    self.scroll(-10,0)
        #  if (event.x >= (screen_w-1)-trigger_area):
        #    self.scroll(10,0)
        #  if (event.y <= trigger_area):
        #    self.scroll(0,-10)
        #  if (event.y >= (screen_h-1)-trigger_area):
        #    self.scroll(0,10)

        if self.pressure_mapping:
            pressure = self.pressure_mapping(pressure)
        if event.state & gdk.SHIFT_MASK:
            pressure = 0.0

        if pressure:
            self.last_painting_pos = x, y

        self.doc.stroke_to(dtime, x, y, pressure) # TODO: add interrupt_at?
        self.queue_draw()

    def button_press_cb(self, win, event):
        if (event.state & gdk.SHIFT_MASK) and self.last_painting_pos:
            dst = self.get_cursor_in_model_coordinates()
            self.doc.straight_line(self.last_painting_pos, dst)

    def canvas_modified_cb(self, x1, y1, w, h):
        if not self.window:
            return
        
        if w == 0 and h == 0:
            # full redraw (used when background has changed)
            #print 'full redraw'
            self.queue_draw()
            return

        cr = self.get_model_coordinates_cairo_context()

        if self.is_translation_only():
            x, y = cr.user_to_device(x1, y1)
            self.queue_draw_area(int(x), int(y), w, h)
        else:
            # create an expose event with the event bbox rotated/zoomed
            # OPTIMIZE: this is estimated to cause at least twice more rendering work than neccessary
            # transform 4 bbox corners to screen coordinates
            corners = [(x1, y1), (x1+w-1, y1), (x1, y1+h-1), (x1+w-1, y1+h-1)]
            corners = [cr.user_to_device(x, y) for (x, y) in corners]
            self.queue_draw_area(*helpers.rotated_rectangle_bbox(corners))

    def expose_cb(self, widget, event):
        self.update_cursor() # hack to get the initial cursor right
        #print 'expose', tuple(event.area)
        self.repaint(event.area)
        return True

    def get_model_coordinates_cairo_context(self, cr=None):
        if cr is None:
            cr = self.window.cairo_create()
        cr.translate(self.translation_x, self.translation_y)
        cr.rotate(self.rotation)
        cr.scale(self.scale, self.scale)
        if self.mirrored:
            m = list(cr.get_matrix())
            m[0] = -m[0]
            m[2] = -m[2]
            cr.set_matrix(cairo.Matrix(*m))
        return cr

    def is_translation_only(self):
        return self.rotation == 0.0 and self.scale == 1.0 and not self.mirrored

    def get_cursor_in_model_coordinates(self):
        x, y, modifiers = self.window.get_pointer()
        cr = self.get_model_coordinates_cairo_context()
        return cr.device_to_user(x, y)

    def get_visible_layers(self):
        # FIXME: tileddrawwidget should not need to know whether the document has layers
        layers = self.doc.layers
        if not self.show_layers_above:
            layers = self.doc.layers[0:self.doc.layer_idx+1]
        layers = [l for l in layers if l.visible]
        return layers

    def repaint(self, device_bbox=None):
        if device_bbox is None:
            w, h = self.window.get_size()
            device_bbox = (0, 0, w, h)
        #print 'device bbox', tuple(device_bbox)

        gdk_clip_region = self.window.get_clip_region()
        x, y, w, h = device_bbox
        sparse = not gdk_clip_region.point_in(x+w/2, y+h/2)

        cr = self.window.cairo_create()

        # actually this is only neccessary if we are not answering an expose event
        cr.rectangle(*device_bbox)
        cr.clip()

        # fill it all white, though not required in the most common case
        if self.visualize_rendering:
            # grey
            tmp = random.random()
            cr.set_source_rgb(tmp, tmp, tmp)
            cr.paint()

        # bye bye device coordinates
        self.get_model_coordinates_cairo_context(cr)

        # choose best mipmap
        mipmap_level = max(0, int(ceil(log(1/self.scale,2))))
        #mipmap_level = max(0, int(floor(log(1.0/self.scale,2)))) # slightly better quality but clearly slower
        mipmap_level = min(mipmap_level, tiledsurface.MAX_MIPMAP_LEVEL)
        cr.scale(2**mipmap_level, 2**mipmap_level)

        translation_only = self.is_translation_only()

        # calculate the final model bbox with all the clipping above
        x1, y1, x2, y2 = cr.clip_extents()
        if not translation_only:
            # Looks like cairo needs one extra pixel rendered for interpolation at the border.
            # If we don't do this, we get dark stripe artefacts when panning while zoomed.
            x1 -= 1
            y1 -= 1
            x2 += 1
            y2 += 1
        x1, y1 = int(floor(x1)), int(floor(y1))
        x2, y2 = int(ceil (x2)), int(ceil (y2))

        # alpha=True is just to get hardware acceleration, we don't
        # actually use the alpha channel. Speedup factor 3 for
        # ATI/Radeon Xorg driver (and hopefully others).
        # TODO: measure effect on pure software rendering
        surface = pixbufsurface.Surface(x1, y1, x2-x1+1, y2-y1+1, alpha=True)

        del x1, y1, x2, y2, w, h

        model_bbox = surface.x, surface.y, surface.w, surface.h
        #print 'model bbox', model_bbox

        # not sure if it is a good idea to clip so tightly
        # has no effect right now because device_bbox is always smaller
        cr.rectangle(*model_bbox)
        cr.clip()

        layers = self.get_visible_layers()

        if self.visualize_rendering:
            surface.pixbuf.fill((int(random.random()*0xff)<<16)+0x00000000)

        tiles = surface.get_tiles()

        background = None
        if self.current_layer_solo:
            background = self.neutral_background_pixbuf
            layers = [self.doc.layer]
            # this is for hiding instead
            #layers.pop(self.doc.layer_idx)
        if self.overlay_layer:
            idx = layers.index(self.doc.layer)
            layers.insert(idx+1, self.overlay_layer)

        for tx, ty in tiles:
            if sparse:
                # it is worth checking whether this tile really will be visible
                # (to speed up the L-shaped expose event during scrolling)
                # (speedup clearly visible; slowdown measurable when always executing this code)
                N = tiledsurface.N
                if translation_only:
                    x, y = cr.user_to_device(tx*N, ty*N)
                    bbox = (int(x), int(y), N, N)
                else:
                    #corners = [(tx*N, ty*N), ((tx+1)*N-1, ty*N), (tx*N, (ty+1)*N-1), ((tx+1)*N-1, (ty+1)*N-1)]
                    # same problem as above: cairo needs to know one extra pixel for interpolation
                    corners = [(tx*N-1, ty*N-1), ((tx+1)*N, ty*N-1), (tx*N-1, (ty+1)*N), ((tx+1)*N, (ty+1)*N)]
                    corners = [cr.user_to_device(x_, y_) for (x_, y_) in corners]
                    bbox = gdk.Rectangle(*helpers.rotated_rectangle_bbox(corners))

                if gdk_clip_region.rect_in(bbox) == gdk.OVERLAP_RECTANGLE_OUT:
                    continue


            dst = surface.get_tile_memory(tx, ty)
            self.doc.blit_tile_into(dst, tx, ty, mipmap_level, layers, background)

        if translation_only:
            # not sure why, but using gdk directly is notably faster than the same via cairo
            x, y = cr.user_to_device(surface.x, surface.y)
            self.window.draw_pixbuf(None, surface.pixbuf, 0, 0, int(x), int(y), dither=gdk.RGB_DITHER_MAX)
        else:
            cr.set_source_pixbuf(surface.pixbuf, surface.x, surface.y)
            pattern = cr.get_source()
            # Required for ATI drivers, to avoid a slower-than-software fallback
            # https://gna.org/bugs/?16122 and https://bugs.freedesktop.org/show_bug.cgi?id=28670
            # However, when using an alpha channel in the source image
            # (as we do now) performance is much better without this.
            #pattern.set_extend(cairo.EXTEND_PAD)

            # We could set interpolation mode here (eg nearest neighbour)
            #pattern.set_filter(cairo.FILTER_NEAREST)  # 1.6s
            #pattern.set_filter(cairo.FILTER_FAST)     # 2.0s
            #pattern.set_filter(cairo.FILTER_GOOD)     # 3.1s
            #pattern.set_filter(cairo.FILTER_BEST)     # 3.1s
            #pattern.set_filter(cairo.FILTER_BILINEAR) # 3.1s

            if self.scale > 1.5:
                # pixelize at high zoom-in levels
                pattern.set_filter(cairo.FILTER_NEAREST)

            cr.paint()

        if self.visualize_rendering:
            # visualize painted bboxes (blue)
            cr.set_source_rgba(0, 0, random.random(), 0.4)
            cr.paint()

    def align_translation(self):
        """
        Align translation to integer pixel coordinates. Keep track of
        the remainder to allow incremental sub-pixel scrolling.
        """
        if self.is_translation_only():
            tx_real = self.translation_x + self.translation_subpixel_x
            ty_real = self.translation_y + self.translation_subpixel_y
            self.translation_x = round(tx_real)
            self.translation_y = round(ty_real)
            self.translation_subpixel_x = tx_real - self.translation_x
            self.translation_subpixel_y = ty_real - self.translation_y
        else:
            # forget about the subpixel translation (which was never executed)
            self.translation_subpixel_x = 0.0
            self.translation_subpixel_y = 0.0

    def scroll(self, dx, dy):
        self.translation_x -= dx
        self.translation_y -= dy
        self.align_translation()
        if False:
            # This speeds things up nicely when scrolling is already
            # fast, but produces temporary artefacts and an
            # annoyingliy non-constant framerate otherwise.
            #
            # It might be worth it if it was done only once per
            # redraw, instead of once per motion event. Maybe try to
            # implement something like "queue_scroll" with priority
            # similar to redraw?
            self.window.scroll(int(-dx), int(-dy))
        else:
            self.queue_draw()

    def rotozoom_with_center(self, function, at_pointer=False):
        if at_pointer and self.has_pointer and self.last_event_x is not None:
            cx, cy = self.last_event_x, self.last_event_y
        else:
            w, h = self.window.get_size()
            cx, cy = w/2.0, h/2.0
        cr = self.get_model_coordinates_cairo_context()
        cx_device, cy_device = cr.device_to_user(cx, cy)
        function()
        self.scale = helpers.clamp(self.scale, self.zoom_min, self.zoom_max)
        cr = self.get_model_coordinates_cairo_context()
        cx_new, cy_new = cr.user_to_device(cx_device, cy_device)
        self.translation_x += cx - cx_new
        self.translation_y += cy - cy_new

        # this is for fast scrolling with only tanslation
        self.rotation = self.rotation % (2*pi)
        if self.is_translation_only():
            self.translation_x = int(self.translation_x)
            self.translation_y = int(self.translation_y)
        self.align_translation()

        self.queue_draw()

    def zoom(self, zoom_step):
        def f(): self.scale *= zoom_step
        self.rotozoom_with_center(f, at_pointer=True)

    def set_zoom(self, zoom):
        def f(): self.scale = zoom
        self.rotozoom_with_center(f, at_pointer=True)

    def rotate(self, angle_step):
        def f(): self.rotation += angle_step
        self.rotozoom_with_center(f)

    def set_rotation(self, angle):
        def f(): self.rotation = angle
        self.rotozoom_with_center(f)

    def mirror(self):
        def f(): self.mirrored = not self.mirrored
        self.rotozoom_with_center(f)

    def set_mirrored(self, mirrored):
        def f(): self.mirrored = mirrored
        self.rotozoom_with_center(f)

    def start_drag(self, dragfunc):
        self.dragfunc = dragfunc
    def stop_drag(self, dragfunc):
        if self.dragfunc == dragfunc:
            self.dragfunc = None

    def recenter_document(self):
        x, y, w, h = self.doc.get_bbox()
        desired_cx_user = x+w/2
        desired_cy_user = y+h/2

        cr = self.get_model_coordinates_cairo_context()
        w, h = self.window.get_size()
        cx_user, cy_user = cr.device_to_user(w/2, h/2)

        self.translation_x += (cx_user - desired_cx_user)*self.scale
        self.translation_y += (cy_user - desired_cy_user)*self.scale
        self.queue_draw()

    def brush_modified_cb(self):
        self.update_cursor()

    def update_cursor(self):
        if not self.window: return

        b = self.doc.brush
        radius = b.get_actual_radius()*self.scale
        c = cursor.get_brush_cursor(radius, b.is_eraser())
        self.window.set_cursor(c)

    def toggle_show_layers_above(self):
        self.show_layers_above = not self.show_layers_above
        self.queue_draw()


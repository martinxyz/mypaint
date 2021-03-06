# This file is part of MyPaint.
# Copyright (C) 2017 by the MyPaint Development Team.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


"""Properties UI showing the current layer."""


# Imports:

from __future__ import division, print_function

import os
import logging
from collections import namedtuple

from lib.modes import STACK_MODES
from lib.modes import STANDARD_MODES
from lib.modes import PASS_THROUGH_MODE
from lib.modes import MODE_STRINGS
import lib.xml
from lib.gettext import C_

import cairo
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf


# Module constants:

logger = logging.getLogger(__name__)


# Class defs:


_LayerFlagUIInfo = namedtuple("_LayerFlagUIInfo", [
    # View objects
    "togglebutton",
    "image",
    # Model details
    "property",
    # Mapping: 2-tuples, indexed by int(property)
    "togglebutton_active",
    "image_icon_name",
])


class LayerPropertiesUI:
    """Presents a widget for editing the current layer's properties.

    Implemented as a Pythonic MVP Presenter that observes the main
    document Model via its exposed lib.observable events.

    The View part is an opaque GTK widget that can be plugged into the
    rest of the UI anywhere.  It's instantiated on demand: its
    corresponding UI XML can be found in layerprops.glade in the same
    directory as this one.

    """

    # Class setting vars:

    _LAYER_MODE_TOOLTIP_MARKUP_TEMPLATE = "<b>{name}</b>\n{description}"
    _PREVIEW_SIZE = 256
    _BOOL_PROPERTIES = [
        _LayerFlagUIInfo(
            togglebutton="layer-locked-togglebutton",
            image="layer-locked-image",
            property="locked",
            togglebutton_active=[False, True],
            image_icon_name=[
                "mypaint-object-unlocked-symbolic",
                "mypaint-object-locked-symbolic",
            ],
        ),
        _LayerFlagUIInfo(
            togglebutton="layer-hidden-togglebutton",
            image="layer-hidden-image",
            property="visible",
            togglebutton_active=[True, False],
            image_icon_name=[
                "mypaint-object-hidden-symbolic",
                "mypaint-object-visible-symbolic",
            ],
        ),
    ]
    _FLAG_ICON_SIZE = Gtk.IconSize.LARGE_TOOLBAR

    # Initialization:

    def __init__(self, docmodel):
        self._docmodel = docmodel
        self._root = docmodel.layer_stack
        self._builder = None
        self._layer = None
        self._processing_model_updates = False

    def _ensure_model_connected(self):
        if self._layer:
            return
        root = self._root
        root.current_path_updated += self._m_layer_changed_cb
        root.layer_properties_changed += self._m_layer_props_changed_cb
        root.layer_thumbnail_updated += self._m_layer_thumbnail_updated_cb
        self._layer = root.current

    def _ensure_view_connected(self):
        if self._builder:
            return
        builder_xml = os.path.splitext(__file__)[0] + ".glade"
        builder = Gtk.Builder()
        builder.set_translation_domain("mypaint")
        builder.add_from_file(builder_xml)
        builder.connect_signals(self)
        self._builder = builder

        # 3-column mode liststore (id, name, sensitive)
        store = self._get_view_object("layer-mode-liststore")
        store.clear()
        modes = STACK_MODES + STANDARD_MODES
        for mode in modes:
            label, desc = MODE_STRINGS.get(mode)
            store.append([mode, label, True])

        # Update to the curent state of the model
        self._layer = self._root.current
        self._m2v_all()

    # Accessors:

    @property
    def widget(self):
        """Get the view GTK widget."""
        self._ensure_view_connected()
        self._ensure_model_connected()
        return self._get_view_object("layer-properties-widget")

    def _get_view_object(self, id):
        self._ensure_view_connected()
        obj = self._builder.get_object(id)
        if not obj:
            raise ValueError("No UI object with ID %r" % (id,))
        return obj

    # Model monitoring and response:

    def _m_layer_changed_cb(self, root, layerpath):
        """Handle a change of the currently active layer."""
        self._layer = root.current
        self._m2v_all()

    def _m_layer_props_changed_cb(self, root, layerpath, layer, changed):
        """Handle a change of layer properties."""
        if layer is not self._layer:
            return
        assert not self._processing_model_updates
        self._processing_model_updates = True
        try:
            if "mode" in changed:
                self._m2v_mode()
            if "opacity" in changed:
                self._m2v_opacity()
            if "locked" in changed:
                info = [i for i in self._BOOL_PROPERTIES
                        if (i.property == "locked")][0]
                self._m2v_layer_flag(info)
            if "visible" in changed:
                info = [i for i in self._BOOL_PROPERTIES
                        if (i.property == "visible")][0]
                self._m2v_layer_flag(info)
            if "name" in changed:
                self._m2v_name()
        except:
            logger.exception("Error while processing updates from the model")
        finally:
            self._processing_model_updates = False

    def _m_layer_thumbnail_updated_cb(self, root, layerpath, layer):
        """Handle the thumbnail of a layer changing."""
        if layer is not self._layer:
            return
        self._m2v_preview()

    def _m2v_all(self):
        assert not self._processing_model_updates
        self._processing_model_updates = True
        try:
            self._m2v_preview()
            self._m2v_name()
            self._m2v_mode()
            self._m2v_opacity()
            for info in self._BOOL_PROPERTIES:
                self._m2v_layer_flag(info)
        except:
            logger.exception("Exception while updating the view")
        finally:
            self._processing_model_updates = False

    def _m2v_preview(self):
        assert self._processing_model_updates
        layer = self._layer
        if not layer:
            return
        preview = make_preview(layer.thumbnail, self._PREVIEW_SIZE)
        image = self._get_view_object("layer-preview-image")
        image.set_from_pixbuf(preview)

    def _m2v_name(self):
        assert self._processing_model_updates
        entry = self._get_view_object("layer-name-entry")
        layer = self._layer

        if not layer:
            entry.set_sensitive(False)
            return
        elif not entry.get_sensitive():
            entry.set_sensitive(True)

        name = layer.name
        if name is None:
            name = layer.DEFAULT_NAME
        entry.set_text(name)

    def _m2v_mode(self):
        assert self._processing_model_updates
        combo = self._get_view_object("layer-mode-combo")
        layer = self._layer

        if not layer:
            combo.set_sensitive(False)
            return
        elif not combo.get_sensitive():
            combo.set_sensitive(True)

        active_iter = None
        for row in combo.get_model():
            mode = row[0]
            if mode == layer.mode:
                active_iter = row.iter
            row[2] = (mode in layer.PERMITTED_MODES)

        combo.set_active_iter(active_iter)

    def _m2v_opacity(self):
        assert self._processing_model_updates
        adj = self._get_view_object("layer-opacity-adjustment")
        scale = self._get_view_object("layer-opacity-scale")
        layer = self._layer

        opacity_is_adjustable = not (
            layer is None
            or layer is self._docmodel.layer_stack
            or layer.mode == PASS_THROUGH_MODE
        )
        scale.set_sensitive(opacity_is_adjustable)
        if not opacity_is_adjustable:
            return

        percentage = layer.opacity * 100
        adj.set_value(percentage)

    def _m2v_layer_flag(self, info):
        assert self._processing_model_updates

        layer = self._layer
        propval = getattr(layer, info.property)
        propval_idx = int(propval)

        togbut = self._get_view_object(info.togglebutton)
        new_active = bool(info.togglebutton_active[propval_idx])
        togbut.set_active(new_active)

        image = self._get_view_object(info.image)
        new_icon = str(info.image_icon_name[propval_idx])
        image.set_from_icon_name(new_icon, self._FLAG_ICON_SIZE)

    # View monitoring and response (callback names defined in .glade XML):

    def _v_layer_mode_combo_query_tooltip_cb(self, combo, x, y, kbd, tooltip):
        if not self._layer:
            return False
        label, desc = MODE_STRINGS.get(self._layer.mode, (None, None))
        if not (label and desc):
            return False
        template = self._LAYER_MODE_TOOLTIP_MARKUP_TEMPLATE
        markup = template.format(
            name = lib.xml.escape(label),
            description = lib.xml.escape(desc),
        )
        tooltip.set_markup(markup)
        return True

    def _v_layer_name_entry_changed_cb(self, entry):
        if self._processing_model_updates:
            return
        if not self._layer:
            return

        # Update the model
        newname = entry.get_text()
        oldname = self._layer.name
        if newname == oldname:
            return
        self._docmodel.rename_current_layer(newname)

        # The model sometimes refuses to apply the name chosen in the
        # view: names have to be non-empty and unique.
        error_class = Gtk.STYLE_CLASS_WARNING
        style = entry.get_style_context()
        if self._layer.name != newname:
            style.add_class(error_class)
        elif style.has_class(error_class):
            style.remove_class(error_class)

    def _v_layer_mode_combo_changed_cb(self, combo):
        if self._processing_model_updates:
            return
        if not self._layer:
            return

        # Update the (doc)model if it has changed
        old_mode = self._layer.mode
        store = combo.get_model()
        new_mode = store.get_value(combo.get_active_iter(), 0)
        if new_mode == old_mode:
            return
        self._docmodel.set_current_layer_mode(new_mode)

    def _v_layer_opacity_adjustment_value_changed_cb(self, adjustment, *etc):
        if self._processing_model_updates:
            return
        if not self._layer:
            return
        opacity = adjustment.get_value() / 100.0
        self._docmodel.set_current_layer_opacity(opacity)

    def _v_layer_hidden_togglebutton_toggled_cb(self, btn):
        info = [i for i in self._BOOL_PROPERTIES
                if (i.property == "visible")][0]
        self._v2m_layer_flag(info)

    def _v_layer_locked_togglebutton_toggled_cb(self, btn):
        info = [i for i in self._BOOL_PROPERTIES
                if (i.property == "locked")][0]
        self._v2m_layer_flag(info)

    def _v2m_layer_flag(self, info):
        if self._processing_model_updates:
            return
        layer = self._layer
        if not layer:
            return

        togbut = self._get_view_object(info.togglebutton)
        togbut_active = bool(togbut.get_active())
        new_propval = bool(info.togglebutton_active.index(togbut_active))
        if bool(getattr(layer, info.property)) != new_propval:
            setattr(layer, info.property, new_propval)

        new_propval_idx = int(new_propval)
        image = self._get_view_object(info.image)
        new_icon = str(info.image_icon_name[new_propval_idx])
        image.set_from_icon_name(new_icon, self._FLAG_ICON_SIZE)


class LayerPropertiesDialog (Gtk.Dialog):
    """Interim dialog for editing the current layer's properties."""
    # Expect this to be replaced with a popover hanging off the layers
    # dockable when the main UI workspace allows for that (floating
    # windows as GtkOverlay overlay children needed 1st)

    TITLE_TEXT = C_(
        "layer properties dialog: title",
        u"Layer Properties",
    )
    DONE_BUTTON_TEXT = C_(
        "layer properties dialog: done button",
        u"Done",
    )

    def __init__(self, parent, docmodel):
        flags = (
            Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        Gtk.Dialog.__init__(
            self, self.TITLE_TEXT, parent, flags,
            (self.DONE_BUTTON_TEXT, Gtk.ResponseType.OK),
        )
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        ui = LayerPropertiesUI(docmodel)
        self.vbox.pack_start(ui.widget, True, True, 0)
        self.set_default_response(Gtk.ResponseType.OK)


# Helpers:

def make_preview(thumb, preview_size):
    """Convert a layer's thumbnail into a nice preview image."""

    # Check size
    check_size = 2
    while check_size < (preview_size / 6) and check_size < 16:
        check_size *= 2

    blank = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, True, 8,
        preview_size, preview_size,
    )
    blank.fill(0x00000000)

    if thumb is None:
        thumb = blank

    # Make a square of chex
    preview = blank.composite_color_simple(
        dest_width=preview_size,
        dest_height=preview_size,
        interp_type=GdkPixbuf.InterpType.NEAREST,
        overall_alpha=255,
        check_size=check_size,
        color1=0xff707070,
        color2=0xff808080,
    )

    w = thumb.get_width()
    h = thumb.get_height()
    scale = preview_size / max(w, h)
    w *= scale
    h *= scale
    x = (preview_size - w) // 2
    y = (preview_size - h) // 2

    thumb.composite(
        dest=preview,
        dest_x=x,
        dest_y=y,
        dest_width=w,
        dest_height=h,
        offset_x=x,
        offset_y=y,
        scale_x=scale,
        scale_y=scale,
        interp_type=GdkPixbuf.InterpType.BILINEAR,
        overall_alpha=255,
    )

    # Add some very minor decorations..
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, preview_size, preview_size)
    cr = cairo.Context(surf)
    Gdk.cairo_set_source_pixbuf(cr, preview, 0, 0)
    cr.paint()

    cr.set_source_rgba(1, 1, 1, 0.1)
    cr.rectangle(0.5, 0.5, preview_size-1, preview_size-1)
    cr.set_line_width(1.0)
    cr.stroke()

    surf.flush()

    preview = Gdk.pixbuf_get_from_surface(
        surf,
        0, 0, preview_size, preview_size,
    )

    return preview

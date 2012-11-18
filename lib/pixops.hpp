/* This file is part of MyPaint.
 * Copyright (C) 2008-2009 by Martin Renold <martinxyz@gmx.ch>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

// make the "heavy_debug" readable from python
#ifdef HEAVY_DEBUG
const bool heavy_debug = true;
#else
const bool heavy_debug = false;
#endif

// downscale a tile to half its size using bilinear interpolation
// used for generating mipmaps for tiledsurface and background
void tile_downscale_rgba16(PyObject *src, PyObject *dst, int dst_x, int dst_y) {
#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT16);
  assert(PyArray_ISCARRAY(src));

  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));
#endif

  PyArrayObject* src_arr = ((PyArrayObject*)src);
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

  for (int y=0; y<TILE_SIZE/2; y++) {
    uint16_t * src_p = (uint16_t*)(src_arr->data + (2*y)*src_arr->strides[0]);
    uint16_t * dst_p = (uint16_t*)(dst_arr->data + (y+dst_y)*dst_arr->strides[0]);
    dst_p += 4*dst_x;
    for(int x=0; x<TILE_SIZE/2; x++) {
      dst_p[0] = src_p[0]/4 + (src_p+4)[0]/4 + (src_p+4*TILE_SIZE)[0]/4 + (src_p+4*TILE_SIZE+4)[0]/4;
      dst_p[1] = src_p[1]/4 + (src_p+4)[1]/4 + (src_p+4*TILE_SIZE)[1]/4 + (src_p+4*TILE_SIZE+4)[1]/4;
      dst_p[2] = src_p[2]/4 + (src_p+4)[2]/4 + (src_p+4*TILE_SIZE)[2]/4 + (src_p+4*TILE_SIZE+4)[2]/4;
      dst_p[3] = src_p[3]/4 + (src_p+4)[3]/4 + (src_p+4*TILE_SIZE)[3]/4 + (src_p+4*TILE_SIZE+4)[3]/4;
      src_p += 8;
      dst_p += 4;
    }
  }
}


#include "compositing.hpp"
#include "blendmodes.hpp"



// Composite one tile over another.

template <typename B>
static inline void
tile_composite_data (PyObject *src,
                     PyObject *dst,
                     const bool dst_has_alpha,
                     const float src_opacity)
{
#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT16);
  assert(PyArray_ISCARRAY(src));

  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));

  PyArrayObject* dst_arr = ((PyArrayObject*)dst);
  assert(dst_arr->strides[0] == 4*sizeof(fix15_short_t)*TILE_SIZE);
  assert(dst_arr->strides[1] == 4*sizeof(fix15_short_t));
  assert(dst_arr->strides[2] ==   sizeof(fix15_short_t));
#endif

  const fix15_short_t opac = fix15_short_clamp(src_opacity * fix15_one);
  if (opac == 0)
    return;

  const fix15_short_t* const src_p = (fix15_short_t *)
                                        ((PyArrayObject*)src)->data;
  fix15_short_t*       const dst_p = (fix15_short_t *)
                                        ((PyArrayObject*)dst)->data;
  if (dst_has_alpha) {
    BufferComp<BufferCompOutputRGBA, TILE_SIZE*TILE_SIZE*4, B>
        ::composite_src_over(src_p, dst_p, opac);
  }
  else {
    BufferComp<BufferCompOutputRGBX, TILE_SIZE*TILE_SIZE*4, B>
        ::composite_src_over(src_p, dst_p, opac);
  }
}


void
tile_composite_normal (PyObject *src,
                       PyObject *dst,
                       const bool dst_has_alpha,
                       const float src_opacity)
{
    tile_composite_data<NormalBlendMode>(src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_multiply (PyObject *src,
                         PyObject *dst,
                         const bool dst_has_alpha,
                         const float src_opacity)
{
    tile_composite_data<MultiplyBlendMode>(src,dst,dst_has_alpha,src_opacity);
}


void
tile_composite_screen (PyObject *src,
                       PyObject *dst,
                       const bool dst_has_alpha,
                       const float src_opacity)
{
    tile_composite_data<ScreenBlendMode>(src,dst,dst_has_alpha,src_opacity);
}


void
tile_composite_overlay (PyObject *src,
                        PyObject *dst,
                        const bool dst_has_alpha,
                        const float src_opacity)
{
    tile_composite_data<OverlayBlendMode>(src,dst,dst_has_alpha,src_opacity);
}


void
tile_composite_hard_light (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<HardLightBlendMode>(src,dst,dst_has_alpha,src_opacity);
}


void
tile_composite_lighten (PyObject *src,
                        PyObject *dst,
                        const bool dst_has_alpha,
                        const float src_opacity)
{
    tile_composite_data<LightenBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_darken (PyObject *src,
                       PyObject *dst,
                       const bool dst_has_alpha,
                       const float src_opacity)
{
    tile_composite_data<DarkenBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_soft_light (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<SoftLightBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_color_dodge (PyObject *src,
                            PyObject *dst,
                            const bool dst_has_alpha,
                            const float src_opacity)
{
    tile_composite_data<ColorDodgeBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_color_burn (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<ColorBurnBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_difference (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<DifferenceBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_exclusion (PyObject *src,
                          PyObject *dst,
                          const bool dst_has_alpha,
                          const float src_opacity)
{
    tile_composite_data<ExclusionBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}

void
tile_composite_hue (PyObject *src,
                    PyObject *dst,
                    const bool dst_has_alpha,
                    const float src_opacity)
{
    tile_composite_data<HueBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_saturation (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<SaturationBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_color (PyObject *src,
                      PyObject *dst,
                      const bool dst_has_alpha,
                      const float src_opacity)
{
    tile_composite_data<ColorBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}


void
tile_composite_luminosity (PyObject *src,
                           PyObject *dst,
                           const bool dst_has_alpha,
                           const float src_opacity)
{
    tile_composite_data<LuminosityBlendMode>
        (src, dst, dst_has_alpha, src_opacity);
}




// used to e.g. copy the background before starting to composite over it
//
// simply array copying (numpy assignment operator) is about 13 times slower, sadly
// The above comment is true when the array is sliced; it's only about two
// times faster now, in the current usecae.
void tile_copy_rgba16_into_rgba16(PyObject * src, PyObject * dst) {
  PyArrayObject* src_arr = ((PyArrayObject*)src);
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));
  assert(dst_arr->strides[1] == 4*sizeof(uint16_t));
  assert(dst_arr->strides[2] ==   sizeof(uint16_t));

  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));
  assert(src_arr->strides[1] == 4*sizeof(uint16_t));
  assert(src_arr->strides[2] ==   sizeof(uint16_t));
#endif

  memcpy(dst_arr->data, src_arr->data, TILE_SIZE*TILE_SIZE*4*sizeof(uint16_t));
  /* the code below can be used if it is not ISCARRAY, but only ISBEHAVED:
  char * src_p = src_arr->data;
  char * dst_p = dst_arr->data;
  for (int y=0; y<TILE_SIZE; y++) {
    memcpy(dst_p, src_p, TILE_SIZE*4);
    src_p += src_arr->strides[0];
    dst_p += dst_arr->strides[0];
  }
  */
}

void tile_clear(PyObject * dst) {
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_TYPE(dst) == NPY_UINT8);
  assert(PyArray_ISBEHAVED(dst));
  assert(dst_arr->strides[1] <= 8);
#endif

  for (int y=0; y<TILE_SIZE; y++) {
    uint8_t  * dst_p = (uint8_t*)(dst_arr->data + y*dst_arr->strides[0]);
    memset(dst_p, 0, TILE_SIZE*dst_arr->strides[1]);
    dst_p += dst_arr->strides[0];
  }
}

// noise used for dithering (the same for each tile)
static const int dithering_noise_size = 64*64*2;
static uint16_t dithering_noise[dithering_noise_size];
static void precalculate_dithering_noise_if_required()
{
  static bool have_noise = false;
  if (!have_noise) {
    // let's make some noise
    for (int i=0; i<dithering_noise_size; i++) {
      // random number in range [0.03 .. 0.97] * (1<<15)
      //
      // We could use the full range, but like this it is much easier
      // to guarantee 8bpc load-save roundtrips don't alter the
      // image. With the full range we would have to pay a lot
      // attention to rounding converting 8bpc to our internal format.
      dithering_noise[i] = (rand() % (1<<15)) * 240/256 + (1<<15) * 8/256;
    }
    have_noise = true;
  }
}

// used mainly for saving layers (transparent PNG)
void tile_convert_rgba16_to_rgba8(PyObject * src, PyObject * dst) {
  PyArrayObject* src_arr = ((PyArrayObject*)src);
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT8);
  assert(PyArray_ISBEHAVED(dst));
  assert(dst_arr->strides[1] == 4*sizeof(uint8_t));
  assert(dst_arr->strides[2] ==   sizeof(uint8_t));

  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT16);
  assert(PyArray_ISBEHAVED(src));
  assert(src_arr->strides[1] == 4*sizeof(uint16_t));
  assert(src_arr->strides[2] ==   sizeof(uint16_t));
#endif

  precalculate_dithering_noise_if_required();
  int noise_idx = 0;

  for (int y=0; y<TILE_SIZE; y++) {
    uint16_t * src_p = (uint16_t*)(src_arr->data + y*src_arr->strides[0]);
    uint8_t  * dst_p = (uint8_t*)(dst_arr->data + y*dst_arr->strides[0]);
    for (int x=0; x<TILE_SIZE; x++) {
      uint32_t r, g, b, a;
      r = *src_p++;
      g = *src_p++;
      b = *src_p++;
      a = *src_p++;
#ifdef HEAVY_DEBUG
      assert(a<=(1<<15));
      assert(r<=(1<<15));
      assert(g<=(1<<15));
      assert(b<=(1<<15));
      assert(r<=a);
      assert(g<=a);
      assert(b<=a);
#endif
      // un-premultiply alpha (with rounding)
      if (a != 0) {
        r = ((r << 15) + a/2) / a;
        g = ((g << 15) + a/2) / a;
        b = ((b << 15) + a/2) / a;
      } else {
        r = g = b = 0;
      }
#ifdef HEAVY_DEBUG
      assert(a<=(1<<15));
      assert(r<=(1<<15));
      assert(g<=(1<<15));
      assert(b<=(1<<15));
#endif

      /*
      // Variant A) rounding
      const uint32_t add_r = (1<<15)/2;
      const uint32_t add_g = (1<<15)/2;
      const uint32_t add_b = (1<<15)/2;
      const uint32_t add_a = (1<<15)/2;
      */
      
      /*
      // Variant B) naive dithering
      // This can alter the alpha channel during a load->save cycle.
      const uint32_t add_r = rand() % (1<<15);
      const uint32_t add_g = rand() % (1<<15);
      const uint32_t add_b = rand() % (1<<15);
      const uint32_t add_a = rand() % (1<<15);
      */

      /*
      // Variant C) slightly better dithering
      // make sure we don't dither rounding errors (those did occur when converting 8bit-->16bit)
      // this preserves the alpha channel, but we still add noise to the highly transparent colors
      const uint32_t add_r = (rand() % (1<<15)) * 240/256 + (1<<15) * 8/256;
      const uint32_t add_g = add_r; // hm... do not produce too much color noise
      const uint32_t add_b = add_r;
      const uint32_t add_a = (rand() % (1<<15)) * 240/256 + (1<<15) * 8/256;
      // TODO: error diffusion might work better than random dithering...
      */

      // Variant C) but with precalculated noise (much faster)
      //
      const uint32_t add_r = dithering_noise[noise_idx++];
      const uint32_t add_g = add_r; // hm... do not produce too much color noise
      const uint32_t add_b = add_r;
      const uint32_t add_a = dithering_noise[noise_idx++];

#ifdef HEAVY_DEBUG
      assert(add_a < (1<<15));
      assert(add_a >= 0);
      assert(noise_idx <= dithering_noise_size);
#endif

      *dst_p++ = (r * 255 + add_r) / (1<<15);
      *dst_p++ = (g * 255 + add_g) / (1<<15);
      *dst_p++ = (b * 255 + add_b) / (1<<15);
      *dst_p++ = (a * 255 + add_a) / (1<<15);
    }
    src_p += src_arr->strides[0];
    dst_p += dst_arr->strides[0];
  }
}

// used after compositing (when displaying, or when saving solid PNG or JPG)
void tile_convert_rgbu16_to_rgbu8(PyObject * src, PyObject * dst) {
  PyArrayObject* src_arr = ((PyArrayObject*)src);
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT8);
  assert(PyArray_ISBEHAVED(dst));
  assert(PyArray_STRIDE(dst, 1) == 4*sizeof(uint8_t));
  assert(PyArray_STRIDE(dst, 2) == sizeof(uint8_t));

  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT16);
  assert(PyArray_ISBEHAVED(src));
  assert(PyArray_STRIDE(src, 1) == 4*sizeof(uint16_t));
  assert(PyArray_STRIDE(src, 2) ==   sizeof(uint16_t));
#endif

  precalculate_dithering_noise_if_required();
  int noise_idx = 0;

  for (int y=0; y<TILE_SIZE; y++) {
    uint16_t * src_p = (uint16_t*)(src_arr->data + y*src_arr->strides[0]);
    uint8_t  * dst_p = (uint8_t*)(dst_arr->data + y*dst_arr->strides[0]);
    for (int x=0; x<TILE_SIZE; x++) {
      uint32_t r, g, b;
      r = *src_p++;
      g = *src_p++;
      b = *src_p++;
      src_p++; // alpha unused
#ifdef HEAVY_DEBUG
      assert(r<=(1<<15));
      assert(g<=(1<<15));
      assert(b<=(1<<15));
#endif
      
      /*
      // rounding
      const uint32_t add = (1<<15)/2;
      */
      // dithering
      const uint32_t add = dithering_noise[noise_idx++];
      
      *dst_p++ = (r * 255 + add) / (1<<15);
      *dst_p++ = (g * 255 + add) / (1<<15);
      *dst_p++ = (b * 255 + add) / (1<<15);
      *dst_p++ = 255;
    }
#ifdef HEAVY_DEBUG
    assert(noise_idx <= dithering_noise_size);
#endif
    src_p += src_arr->strides[0];
    dst_p += dst_arr->strides[0];
  }
}

// used mainly for loading layers (transparent PNG)
void tile_convert_rgba8_to_rgba16(PyObject * src, PyObject * dst) {
  PyArrayObject* src_arr = ((PyArrayObject*)src);
  PyArrayObject* dst_arr = ((PyArrayObject*)dst);

#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISBEHAVED(dst));
  assert(dst_arr->strides[1] == 4*sizeof(uint16_t));
  assert(dst_arr->strides[2] ==   sizeof(uint16_t));

  assert(PyArray_DIM(src, 0) == TILE_SIZE);
  assert(PyArray_DIM(src, 1) == TILE_SIZE);
  assert(PyArray_DIM(src, 2) == 4);
  assert(PyArray_TYPE(src) == NPY_UINT8);
  assert(PyArray_ISBEHAVED(src));
  assert(src_arr->strides[1] == 4*sizeof(uint8_t));
  assert(src_arr->strides[2] ==   sizeof(uint8_t));
#endif

  for (int y=0; y<TILE_SIZE; y++) {
    uint8_t  * src_p = (uint8_t*)(src_arr->data + y*src_arr->strides[0]);
    uint16_t * dst_p = (uint16_t*)(dst_arr->data + y*dst_arr->strides[0]);
    for (int x=0; x<TILE_SIZE; x++) {
      uint32_t r, g, b, a;
      r = *src_p++;
      g = *src_p++;
      b = *src_p++;
      a = *src_p++;

      // convert to fixed point (with rounding)
      r = (r * (1<<15) + 255/2) / 255;
      g = (g * (1<<15) + 255/2) / 255;
      b = (b * (1<<15) + 255/2) / 255;
      a = (a * (1<<15) + 255/2) / 255;

      // premultiply alpha (with rounding), save back
      *dst_p++ = (r * a + (1<<15)/2) / (1<<15);
      *dst_p++ = (g * a + (1<<15)/2) / (1<<15);
      *dst_p++ = (b * a + (1<<15)/2) / (1<<15);
      *dst_p++ = a;
    }
  }
}

// Flatten a premultiplied rgba layer, using "bg" as background.
// (bg is assumed to be flat, bg.alpha is ignored)
//
// dst.color = dst OVER bg.color
// dst.alpha = unmodified
//
void tile_rgba2flat(PyObject * dst, PyObject * bg) {
#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));

  assert(PyArray_DIM(bg, 0) == TILE_SIZE);
  assert(PyArray_DIM(bg, 1) == TILE_SIZE);
  assert(PyArray_DIM(bg, 2) == 4);
  assert(PyArray_TYPE(bg) == NPY_UINT16);
  assert(PyArray_ISCARRAY(bg));
#endif
  
  uint16_t * dst_p  = (uint16_t*)PyArray_DATA(dst);
  uint16_t * bg_p  = (uint16_t*)PyArray_DATA(bg);
  for (int i=0; i<TILE_SIZE*TILE_SIZE; i++) {
    // resultAlpha = 1.0 (thus it does not matter if resultColor is premultiplied alpha or not)
    // resultColor = topColor + (1.0 - topAlpha) * bottomColor
    const uint32_t one_minus_top_alpha = (1<<15) - dst_p[3];
    dst_p[0] += ((uint32_t)one_minus_top_alpha*bg_p[0]) / (1<<15);
    dst_p[1] += ((uint32_t)one_minus_top_alpha*bg_p[1]) / (1<<15);
    dst_p[2] += ((uint32_t)one_minus_top_alpha*bg_p[2]) / (1<<15);
    dst_p += 4;
    bg_p += 4;
  }
}

// Make a flat layer translucent again. When calculating the new color
// and alpha, it is assumed that the layer will be displayed OVER the
// background "bg". Alpha is increased where required.
//
// dst.alpha = MIN(dst.alpha, minimum alpha required for correct result)
// dst.color = calculated such that (dst_output OVER bg = dst_input.color)
//
void tile_flat2rgba(PyObject * dst, PyObject * bg) {
#ifdef HEAVY_DEBUG
  assert(PyArray_DIM(dst, 0) == TILE_SIZE);
  assert(PyArray_DIM(dst, 1) == TILE_SIZE);
  assert(PyArray_DIM(dst, 2) == 4);
  assert(PyArray_TYPE(dst) == NPY_UINT16);
  assert(PyArray_ISCARRAY(dst));

  assert(PyArray_DIM(bg, 0) == TILE_SIZE);
  assert(PyArray_DIM(bg, 1) == TILE_SIZE);
  assert(PyArray_DIM(bg, 2) == 4);
  assert(PyArray_TYPE(bg) == NPY_UINT16);
  assert(PyArray_ISCARRAY(bg));
#endif
  
  uint16_t * dst_p  = (uint16_t*)PyArray_DATA(dst);
  uint16_t * bg_p  = (uint16_t*)PyArray_DATA(bg);
  for (int i=0; i<TILE_SIZE*TILE_SIZE; i++) {

    // 1. calculate final dst.alpha
    uint16_t final_alpha = 0;
    for (int i=0; i<3;i++) {
      int32_t color_change = (int32_t)dst_p[i] - bg_p[i];
      const uint16_t small_change = 0;
      if (color_change > small_change) {
        final_alpha = MAX(final_alpha, (int64_t)color_change*(1<<15) / ((1<<15) - bg_p[i]));
      } else if (color_change < small_change) {
        final_alpha = MAX(final_alpha, (int64_t)-color_change*(1<<15) / bg_p[i]);
      } else {
        // color_change == 0; no need to increment alpha
      }

      final_alpha = MAX(final_alpha, dst_p[3]);
#ifdef HEAVY_DEBUG
      assert(final_alpha <= (1<<15));
#endif
    }
    
    // 2. calculate dst.color and update dst
    dst_p[3] = final_alpha;
    if (final_alpha > 0) {
      for (int i=0; i<3;i++) {
        int32_t color_change = (int32_t)dst_p[i] - bg_p[i];
        //int64_t res = bg_p[i] + (int64_t)color_change*(1<<15) / final_alpha;
        // premultiplied with final_alpha
        int64_t res = (uint32_t)bg_p[i]*final_alpha/(1<<15) + (int64_t)color_change;
        /*
          just clamp (if change was forced to zero)
        assert(res <= (1<<15));
        assert(res >= -1);
        res = CLAMP(res, 0, (1<<15)); // fixme: better handling of rounding errors maybe?
        */
        res = CLAMP(res, 0, final_alpha);
        // Also, the result ist probably often exact zero or exact
        // (1<<15), why are we even (re)calculating those...?
        dst_p[i] = res;
#ifdef HEAVY_DEBUG
        assert(dst_p[i] <= dst_p[3]);
#endif
      }
    } else {
      dst_p[0] = 0;
      dst_p[1] = 0;
      dst_p[2] = 0;
    }
    dst_p += 4;
    bg_p += 4;
  }
}

// used in strokemap.py
//
// Calculates a 1-bit bitmap of the stroke shape using two snapshots
// of the layer (the layer before and after the stroke).
//
// If the alpha increases a lot, we want the stroke to appear in
// the strokemap, even if the color did not change. If the alpha
// decreases a lot, we want to ignore the stroke (eraser). If
// the alpha decreases just a little, but the color changes a
// lot (eg. heavy smudging or watercolor brushes) we want the
// stroke still to be pickable.
//
// If the layer alpha was (near) zero, we record the stroke even if it
// is barely visible. This gives a bigger target to point-and-select.
//
void tile_perceptual_change_strokemap(PyObject * a, PyObject * b, PyObject * res) {

  assert(PyArray_TYPE(a) == NPY_UINT16);
  assert(PyArray_TYPE(b) == NPY_UINT16);
  assert(PyArray_TYPE(res) == NPY_UINT8);
  assert(PyArray_ISCARRAY(a));
  assert(PyArray_ISCARRAY(b));
  assert(PyArray_ISCARRAY(res));

  uint16_t * a_p  = (uint16_t*)PyArray_DATA(a);
  uint16_t * b_p  = (uint16_t*)PyArray_DATA(b);
  uint8_t * res_p = (uint8_t*)PyArray_DATA(res);

  for (int y=0; y<TILE_SIZE; y++) {
    for (int x=0; x<TILE_SIZE; x++) {

      int32_t color_change = 0;
      // We want to compare a.color with b.color, but we only know
      // (a.color * a.alpha) and (b.color * b.alpha).  We multiply
      // each component with the alpha of the other image, so they are
      // scaled the same and can be compared.

      for (int i=0; i<3; i++) {
        int32_t a_col = (uint32_t)a_p[i] * b_p[3] / (1<<15); // a.color * a.alpha*b.alpha
        int32_t b_col = (uint32_t)b_p[i] * a_p[3] / (1<<15); // b.color * a.alpha*b.alpha
        color_change += abs(b_col - a_col);
      }
      // "color_change" is in the range [0, 3*a_a]
      // if either old or new alpha is (near) zero, "color_change" is (near) zero

      int32_t alpha_old = a_p[3];
      int32_t alpha_new = b_p[3];

      // Note: the thresholds below are arbitrary choices found to work okay

      // We report a color change only if both old and new color are
      // well-defined (big enough alpha).
      bool is_perceptual_color_change = color_change > MAX(alpha_old, alpha_new)/16;

      int32_t alpha_diff = alpha_new - alpha_old; // no abs() here (ignore erasers)
      // We check the alpha increase relative to the previous alpha.
      bool is_perceptual_alpha_increase = alpha_diff > (1<<15)/4;

      // this one is responsible for making fat big ugly easy-to-hit pointer targets
      bool is_big_relative_alpha_increase  = alpha_diff > (1<<15)/64 && alpha_diff > alpha_old/2;

      if (is_perceptual_alpha_increase || is_big_relative_alpha_increase || is_perceptual_color_change) {
        res_p[0] = 1;
      } else {
        res_p[0] = 0;
      }

      a_p += 4;
      b_p += 4;
      res_p += 1;
    }
  }
}


/* This file is part of MyPaint.
 * Copyright (C) 2008-2011 by Martin Renold <martinxyz@gmx.ch>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */


// parameters to those methods:
//
// rgba: A pointer to 16bit rgba data with premultiplied alpha.
//       The range of each components is limited from 0 to 2^15.
//
// mask: Contains the dab shape, that is, the intensity of the dab at
//       each pixel. Usually rendering is done for one tile at a
//       time. The mask is LRE encoded to jump quickly over regions
//       that are not affected by the dab.
//
// opacity: overall strenght of the blending mode. Has the same
//          influence on the dab as the values inside the mask.


// We are manipulating pixels with premultiplied alpha directly.
// This is an "over" operation (opa = topAlpha).
// In the formula below, topColor is assumed to be premultiplied.
//
//               opa_a      <   opa_b      >
// resultAlpha = topAlpha + (1.0 - topAlpha) * bottomAlpha
// resultColor = topColor + (1.0 - topAlpha) * bottomColor
//
void draw_dab_pixels_BlendMode_Normal (uint16_t * mask,
                                       uint16_t * rgba,
                                       uint16_t color_r,
                                       uint16_t color_g,
                                       uint16_t color_b,
                                       uint16_t opacity) {

  while (1) {
    for (; mask[0]; mask++, rgba+=4) {
      uint32_t opa_a = mask[0]*(uint32_t)opacity/(1<<15); // topAlpha
      uint32_t opa_b = (1<<15)-opa_a; // bottomAlpha
      rgba[3] = opa_a + opa_b * rgba[3] / (1<<15);
      rgba[0] = (opa_a*color_r + opa_b*rgba[0])/(1<<15);
      rgba[1] = (opa_a*color_g + opa_b*rgba[1])/(1<<15);
      rgba[2] = (opa_a*color_b + opa_b*rgba[2])/(1<<15);

    }
    if (!mask[1]) break;
    rgba += mask[1];
    mask += 2;
  }
};

// This blend mode is used for smudging and erasing.  Smudging
// allows to "drag" around transparency as if it was a color.  When
// smuding over a region that is 60% opaque the result will stay 60%
// opaque (color_a=0.6).  For normal erasing color_a is set to 0.0
// and color_r/g/b will be ignored. This function can also do normal
// blending (color_a=1.0).
//
void draw_dab_pixels_BlendMode_Normal_and_Eraser (uint16_t * mask,
                                                  uint16_t * rgba,
                                                  uint16_t color_r,
                                                  uint16_t color_g,
                                                  uint16_t color_b,
                                                  uint16_t color_a,
                                                  uint16_t opacity) {

  while (1) {
    for (; mask[0]; mask++, rgba+=4) {
      uint32_t opa_a = mask[0]*(uint32_t)opacity/(1<<15); // topAlpha
      uint32_t opa_b = (1<<15)-opa_a; // bottomAlpha
      opa_a = opa_a * color_a / (1<<15);
      rgba[3] = opa_a + opa_b * rgba[3] / (1<<15);
      rgba[0] = (opa_a*color_r + opa_b*rgba[0])/(1<<15);
      rgba[1] = (opa_a*color_g + opa_b*rgba[1])/(1<<15);
      rgba[2] = (opa_a*color_b + opa_b*rgba[2])/(1<<15);

    }
    if (!mask[1]) break;
    rgba += mask[1];
    mask += 2;
  }
};

// This is BlendMode_Normal with locked alpha channel.
//
void draw_dab_pixels_BlendMode_LockAlpha (uint16_t * mask,
                                          uint16_t * rgba,
                                          uint16_t color_r,
                                          uint16_t color_g,
                                          uint16_t color_b,
                                          uint16_t opacity) {

  while (1) {
    for (; mask[0]; mask++, rgba+=4) {
      uint32_t opa_a = mask[0]*(uint32_t)opacity/(1<<15); // topAlpha
      uint32_t opa_b = (1<<15)-opa_a; // bottomAlpha
      
      opa_a *= rgba[3];
      opa_a /= (1<<15);
          
      rgba[0] = (opa_a*color_r + opa_b*rgba[0])/(1<<15);
      rgba[1] = (opa_a*color_g + opa_b*rgba[1])/(1<<15);
      rgba[2] = (opa_a*color_b + opa_b*rgba[2])/(1<<15);
    }
    if (!mask[1]) break;
    rgba += mask[1];
    mask += 2;
  }
};


// Sum up the color/alpha components inside the masked region.
// Called by get_color().
//
void get_color_pixels_accumulate (uint16_t * mask,
                                  uint16_t * rgba,
                                  float * sum_weight,
                                  float * sum_r,
                                  float * sum_g,
                                  float * sum_b,
                                  float * sum_a
                                  ) {


  // The sum of a 64x64 tile fits into a 32 bit integer, but the sum
  // of an arbitrary number of tiles may not fit. We assume that we
  // are processing a single tile at a time, so we can use integers.
  // But for the result we need floats.

  uint32_t weight = 0;
  uint32_t r = 0;
  uint32_t g = 0;
  uint32_t b = 0;
  uint32_t a = 0;

  while (1) {
    for (; mask[0]; mask++, rgba+=4) {
      uint32_t opa = mask[0];
      weight += opa;
      r      += opa*rgba[0]/(1<<15);
      g      += opa*rgba[1]/(1<<15);
      b      += opa*rgba[2]/(1<<15);
      a      += opa*rgba[3]/(1<<15);

    }
    if (!mask[1]) break;
    rgba += mask[1];
    mask += 2;
  }

  // convert integer to float outside the performance critical loop
  *sum_weight += weight;
  *sum_r += r;
  *sum_g += g;
  *sum_b += b;
  *sum_a += a;
};

// Overlay blending mode (or something similar)
//
void draw_dab_pixels_BlendMode_Overlay (uint16_t * mask,
                                        uint16_t * rgba,
                                        uint16_t * bg,
                                        uint16_t color_r,
                                        uint16_t color_g,
                                        uint16_t color_b,
                                        uint16_t opacity) {

  uint16_t color[3];
  color[0] = color_r;
  color[1] = color_g;
  color[2] = color_b;

  while (1) {
    for (; mask[0]; mask++, rgba+=4, bg+=3) {
      uint32_t opa_a = mask[0]*(uint32_t)opacity/(1<<15);

      uint32_t c[3];

      for (int i=0; i<3;i++) {
        assert(rgba[i] <= rgba[3]);
        assert(opa_a <= (1<<15));
        
        /* old version (premultiplied alpha, locked alpha only)
        int32_t slope = 2*((int32_t)color[i])-(1<<15);
        
        uint16_t tmp;
        if (rgba[i] < rgba[3]/2) {
          // multiply
          tmp = rgba[i];
        } else {
          // screen
          tmp = rgba[3] - rgba[i];
        }
        rgba[i] += opa_a * tmp / (1<<15) * slope / (1<<15);

        assert(rgba[i] <= rgba[3]);
        */

        // composite to get visible image
        c[i] = (uint32_t)rgba[i] + ((1<<15) - rgba[3])*bg[i] / (1<<15);
        assert(c[i] <= (1<<15));

        // apply effect to visible image
        int64_t slope = (int64_t)2*color[i]-(1<<15);
        uint16_t tmp;
        if (c[i] < (1<<15)/2) {
          // multiply
          tmp = c[i]; // range 0..(1<<15)/2-1
        } else {
          // screen
          tmp = (1<<15) - c[i]; // range 0..(1<<15)/2
        }
        int64_t change = tmp * slope / (1<<15);
        int64_t tmp2 = c[i] + (int64_t)opa_a * change / (1<<15);
        assert(tmp2 <= (1<<15));
        assert(tmp2 >= 0);
        c[i] = CLAMP(tmp2, 0, (1<<15));
      }
      
      uint16_t final_alpha = rgba[3];
      for (int i=0; i<3;i++) {
        int32_t color_change = (int32_t)c[i] - bg[i];
        uint16_t minimal_alpha;
        if (color_change > 0) {
          minimal_alpha = (int64_t)color_change*(1<<15) / ((1<<15) - bg[i]);
        } else if (color_change < 0) {
          minimal_alpha = (int64_t)-color_change*(1<<15) / bg[i];
        } else {
          // color_change == 0
          minimal_alpha = 0;
        }
        final_alpha = MAX(final_alpha, minimal_alpha);
        assert(final_alpha <= (1<<15));
      }
      rgba[3] = final_alpha;
      if (final_alpha > 0) {
        for (int i=0; i<3;i++) {
          int32_t color_change = (int32_t)c[i] - bg[i];
          //int64_t res = bg[i] + (int64_t)color_change*(1<<15) / final_alpha;
          // premultiplied with final_alpha
          int64_t res = (uint32_t)bg[i]*final_alpha/(1<<15) + (int64_t)color_change;
          assert(res <= (1<<15));
          assert(res >= -1);
          res = CLAMP(res, 0, (1<<15)); // fixme: better handling of rounding errors maybe?
          // Also, the result ist often exact zero or exact (1<<15), why are we even 
          // (re)calculating those...?
          rgba[i] = res;
          assert(rgba[i] <= rgba[3]);
        }
      }

      /*
      // todo: back-calculate alpha in the inner loop
      // lazy coder's version: just maximize alpha
      rgba[0] = c[0];
      rgba[1] = c[1];
      rgba[2] = c[2];
      rgba[3] = (1<<15);
      */
        
    }
    if (!mask[1]) break;
    rgba += mask[1];
    bg += mask[1] / 4 * 3; // fixme
    mask += 2;
  }
};


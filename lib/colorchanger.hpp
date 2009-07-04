/* This file is part of MyPaint.
 * Copyright (C) 2008 by Martin Renold <martinxyz@gmx.ch>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#include "lcms.h"

class ColorChanger {
public:
  static const int size = 256;

  float brush_h, brush_s, brush_v;
  void set_brush_color(float h, float s, float v)
  {
    brush_h = h;
    brush_s = s;
    brush_v = v;
  }

#ifndef SWIG

  struct PrecalcData {
    int h;
    int s;
    int v;
    //signed char s;
    //signed char v;
  };

  PrecalcData * precalcData[4];
  int precalcDataIndex;

  ColorChanger()
  {
    precalcDataIndex = -1;
    for (int i=0; i<4; i++) {
      precalcData[i] = NULL;
    }
  }

  PrecalcData * precalc_data(float phase0)
  {
    // Hint to the casual reader: some of the calculation here do not
    // what I originally intended. Not everything here will make sense.
    // It does not matter in the end, as long as the result looks good.

    int width, height;
    float width_inv, height_inv;
    int x, y, i;
    PrecalcData * result;

    width = size;
    height = size;
    result = (PrecalcData*)malloc(sizeof(PrecalcData)*width*height);

    //phase0 = rand_double (rng) * 2*M_PI;

    width_inv = 1.0/width;
    height_inv = 1.0/height;

    i = 0;
    for (y=0; y<height; y++) {
      for (x=0; x<width; x++) {
        float v_factor = 0.6;
        float s_factor = 0.6;
        float h_factor = 0.4;

#define factor2_func(x) ((x)*(x)*SIGN(x))
        float v_factor2 = 0.013;
        float s_factor2 = 0.013;
        float h_factor2 = 0.02;

        int stripe_width = 20;

        float h = 0;
        float s = 0;
        float v = 0;

        int dx = x-width/2;
        int dy = y-height/2;

        // hue
        if (dy > 0) {
          h += float(dy-stripe_width)/stripe_width * 16;
        } else {
          h += float(dy+stripe_width)/stripe_width * 16;
        }
        h = h*h_factor + factor2_func(h)*h_factor2;
        if (abs(dx) > size*0.30) {
          s = 10000;
          v = 10000;
        }

        // horizontal and vertical lines
        int min = ABS(dx);
        if (ABS(dy) < min) min = ABS(dy);
        if (min < stripe_width) {
          h = 0;
          // x-axis = value, y-axis = saturation
          v =    dx*v_factor + factor2_func(dx)*v_factor2;
          s = - (dy*s_factor + factor2_func(dy)*s_factor2);
          // but not both at once
          if (ABS(dx) > ABS(dy)) {
            // horizontal stripe
            s = 0.0;
          } else {
            // vertical stripe
            v = 0.0;
          }
        }

        result[i].h = (int)h;
        result[i].v = (int)v;
        result[i].s = (int)s;
        i++;
      }
    }
    return result;
  }

  void get_hsv(float &h, float &s, float &v, PrecalcData * pre)
  {
    h = brush_h + pre->h/360.0;
    s = brush_s + pre->s/255.0;
    v = brush_v + pre->v/255.0;

    h -= floor(h);
    s = CLAMP(s, 0.0, 1.0);
    v = CLAMP(v, 0.0, 1.0);

  }

#endif /* #ifndef SWIG */

  /*
  void lcms_test() {
    
    for (i=0; i < 5; i++)
      {


        // Fill in the Float Lab
        
        Lab[i].L = 10.0;
        Lab[i].a = 4.1;
        Lab[i].b = 2.2;
        
        cmsDoTransform(hTransform, Lab, RGB, 1);
        
        printf("RGB result: %d %d %d\n", (int)RGB[0], (int)RGB[1], (int)RGB[2]);
        //.. Do whatsever with the RGB values in RGB[3]
      }
    
  }
  */


  void render(PyObject * arr)
  {
    uint8_t * pixels;
    int x, y;
    float h, s, v;


    cmsHPROFILE hInProfile, hOutProfile;
    cmsHTRANSFORM hTransform;
    int i;
    BYTE RGB[3];
    cmsCIELab Lab[5];
    cmsCIELCh LCh[5];
    hInProfile  = cmsCreateLabProfile(NULL);
    hOutProfile = cmsCreate_sRGBProfile();
    hTransform = cmsCreateTransform(hInProfile,
                                    TYPE_Lab_DBL,
                                    hOutProfile,
                                    TYPE_RGB_8,
                                    INTENT_PERCEPTUAL, 0);
    
    assert(PyArray_ISCARRAY(arr));
    assert(PyArray_NDIM(arr) == 3);
    assert(PyArray_DIM(arr, 0) == size);
    assert(PyArray_DIM(arr, 1) == size);
    assert(PyArray_DIM(arr, 2) == 4);
    pixels = (uint8_t*)((PyArrayObject*)arr)->data;
    
    precalcDataIndex++;
    precalcDataIndex %= 4;

    PrecalcData * pre = precalcData[precalcDataIndex];
    if (!pre) {
      pre = precalcData[precalcDataIndex] = precalc_data(2*M_PI*(precalcDataIndex/4.0));
    }

    for (y=0; y<size; y++) {
      for (x=0; x<size; x++) {

        /*
        get_hsv(h, s, v, pre);
        pre++;
        hsv_to_rgb_range_one (&h, &s, &v);
        */
        uint8_t * p = pixels + 4*(y*size + x);
        Lab[i].L = 80.0;
        Lab[i].a = -130.0*(x-size/2)/size;
        Lab[i].b = -130.0*(y-size/2)/size;
        
        /*
        cmsCIELCh LCh[1];
        LCh[i].L = 30.0;
        //LCh[i].C = 50.0;
        LCh[i].C = 100.0*x/size;
        LCh[i].h = 360.0*y/size;

        cmsLCh2Lab(Lab, LCh);
        */

        cmsDoTransform(hTransform, Lab, p, 1);
        p[3] = 255;
      }
    }

    cmsDeleteTransform(hTransform);
    cmsCloseProfile(hInProfile);
    cmsCloseProfile(hOutProfile);
  }

  PyObject* pick_color_at(float x_, float y_)
  {
    float h,s,v;
    PrecalcData * pre = precalcData[precalcDataIndex];
    assert(precalcDataIndex >= 0);
    assert(pre != NULL);
    int x = CLAMP(x_, 0, size);
    int y = CLAMP(y_, 0, size);
    pre += y*size + x;
    get_hsv(h, s, v, pre);
    return Py_BuildValue("fff",h,s,v);
  }
};

#!/usr/bin/env python
from pylab import *

# Calculate lookup table for converting 15bit sRGB to 15bit linear light and back.
# (According to Wikipedia.)

N = 2**15+1
inputs = arange(2**15+1, dtype=float)
inputs_float = inputs/(1<<15)

a = 0.055
lin2srgb = (1.0+a)*inputs_float**(1.0/2.4) - a
r = inputs_float<=0.0031308
lin2srgb[r] = 12.92 * inputs_float[r]
lin2srgb *= (1<<15)
lin2srgb = (lin2srgb+0.5).astype('uint16')

#print 'lin2srgb', lin2srgb

srgb2lin = ((inputs_float+a)/(1.0+a))**2.4
r = inputs_float<=0.04045
srgb2lin[r] = inputs_float[r]/12.92
srgb2lin *= (1<<15)
srgb2lin = (srgb2lin+0.5).astype('uint16')

#print 'srgb2lin', srgb2lin

#print max(abs(srgb2lin[lin2srgb] - inputs))
#print max(abs(lin2srgb[srgb2lin] - inputs))
#print max(abs(lin2srgb[srgb2lin[lin2srgb[srgb2lin[lin2srgb[srgb2lin]]]]] - inputs))

def table2const(t, name):
   s = 'const uint16_t %s[%d] = {\n' % (name, N)
   s += '  '
   s += ', '.join([str(x) for x in t])
   s += '\n'
   s += '};\n'
   return s

print table2const(srgb2lin, 'srgb2lin')
print table2const(lin2srgb, 'lin2srgb')

#!/usr/bin/env python3
"""Source VIDEO-RLE OBS regression with byte-exact expected positions.
This tests original packet grammar, NOT original motion-to-frame semantics.
"""
import importlib.util
import pathlib
import struct
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools/decode-original-obs-bulk.py'
spec=importlib.util.spec_from_file_location('obs_native_source_codec',MODULE)
codec=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=codec
spec.loader.exec_module(codec)


def encode_640_rows(rows,width,height):
    # Rows contain (y, x, palette-index byte string) in original VIDEO pixels.
    payload=bytearray(struct.pack('<HH',len(rows),rows[0][0]*640+rows[0][1]))
    cursor=rows[0][0]*640+rows[0][1]
    for i,(y,x,data) in enumerate(rows):
        pos=y*640+x
        if i:
            assert 0<=pos-cursor<=65535
            payload.extend(struct.pack('<H',pos-cursor))
            cursor=pos
        n=len(data)
        payload.extend((n//4,n%4))
        payload.extend(data)
        cursor+=n
    assert cursor==(height-1)*640+width
    return bytes(payload)


class NativeOBS(unittest.TestCase):
    def setUp(self):
        self.width=50;self.height=3
        # Three rows with deliberately DIFFERENT native x positions.
        self.data=encode_640_rows([
            (0,5,bytes([1]*18)),(1,16,bytes([4]*19)),
            (2,32,bytes([10]*18))],self.width,self.height)
        self.palette=bytes([c for x in range(256) for c in (x,0,255-x)])

    def test_native_packet_pixel_x_and_bottom_up_coordinates(self):
        image,info=codec.decode_rows(self.data,self.width,self.height,self.palette)
        self.assertEqual(info['videoStride'],640)
        self.assertEqual(info['nativePackets'],3)
        self.assertEqual(info['scanlineX'],'ORIGINAL-VIDEO-RUN-CURSOR; NOT CENTERED')
        # Source indexed pixels are at distinct SOURCE xs, not centered.
        self.assertEqual(image.getpixel((5,2)),(1,0,254,255))
        self.assertEqual(image.getpixel((16,1)),(4,0,251,255))
        self.assertEqual(image.getpixel((49,0)),(10,0,245,255))
        self.assertEqual(image.getpixel((24,2))[3],0)

    def test_wrong_final_cursor_and_truncated_source_never_accepted(self):
        with self.assertRaisesRegex(ValueError,'final 640-stride cursor'):
            codec.decode_rows(self.data,self.width+1,self.height,self.palette)
        with self.assertRaises(ValueError):
            codec.decode_rows(self.data[:-1],self.width,self.height,self.palette)
        with self.assertRaises(ValueError):
            codec.decode_rows(self.data+b'\x00',self.width,self.height,self.palette)

    def test_source_buffer_bounds_reject_wrap_and_overshoot(self):
        body=bytearray(self.data)
        # Move the first true source run outside its declared native width.
        body[2:4]=struct.pack('<H',self.width+2)
        with self.assertRaisesRegex(ValueError,'outside frame'):
            codec.decode_rows(bytes(body),self.width,self.height,self.palette)
        # True source palette must be present; otherwise cannot mark recovered.
        with self.assertRaisesRegex(ValueError,'palette truncated'):
            codec.decode_rows(self.data,self.width,self.height,self.palette[:30])


if __name__=='__main__':
    unittest.main()

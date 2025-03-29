# functions.py
import math
import numpy as np

# Global resolutions
UVEL32_RESOLUTION = 1 / (2**24 - 1)  # For 24-bit, ~5.96e-8
UACC32_RESOLUTION = 1 / (2**20 - 1)  # For 20-bit, ~9.54e-7

# test_functions.py
import unittest
import math
from utils import (
    split_20bit_to_components,
    split_24bit_to_components,
    combine_12_4bit,
    combine_8_8bit,
    combine_to_20bit,
    combine_to_24bit,
    convert_vel_rpm_revs,
    convert_acc_rpm_revs,
)

class TestBitFunctions(unittest.TestCase):
    def test_split_20bit_to_components(self):
        # Test case 1: value = 0.05
        value = 0.05
        scaled_value = int(value / UACC32_RESOLUTION)  # ≈ 52428
        expected_scaled = 52428
        self.assertEqual(scaled_value, expected_scaled)

        sixteen_bit, four_bit = split_20bit_to_components(value)
        # Recombine and check
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, scaled_value)

        # Test case 2: value = 0.5 (half the range)
        value = 0.5
        scaled_value = int(value / UACC32_RESOLUTION)  # ≈ 524287
        expected_scaled = 524287
        self.assertEqual(scaled_value, expected_scaled)

        sixteen_bit, four_bit = split_20bit_to_components(value)

        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, scaled_value)

        # Test case 3: Edge case, value = 0.0
        value = 0.0
        sixteen_bit, four_bit = split_20bit_to_components(value)
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, 0)

        # Test case 4: Edge case, value = 1.0
        value = 1.0
        scaled_value = int(value / UACC32_RESOLUTION)  # 1048575
        sixteen_bit, four_bit = split_20bit_to_components(value)
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, scaled_value)

        # Test case 5: Invalid input
        self.assertIsNone(split_20bit_to_components(-0.1))
        self.assertIsNone(split_20bit_to_components(1.1))

    def test_split_24bit_to_components(self):
        # Test case 1: value = 0.5
        value = 0.5
        scaled_value = int(value / UVEL32_RESOLUTION)  # ≈ 8388607
        expected_scaled = 8388607
        self.assertEqual(scaled_value, expected_scaled)

        sixteen_bit, eight_bit = split_24bit_to_components(value)

        # Recombine
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, scaled_value)

        # Test case 2: value = 0.0
        sixteen_bit, eight_bit = split_24bit_to_components(0.0)
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, 0)

        # Test case 3: value = 1.0
        scaled_value = int(1.0 / UVEL32_RESOLUTION)  # 16777215
        sixteen_bit, eight_bit = split_24bit_to_components(1.0)
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, scaled_value)

        # Test case 4: Invalid input
        self.assertIsNone(split_24bit_to_components(-0.1))
        self.assertIsNone(split_24bit_to_components(1.1))

    def test_combine_20bit(self):
        # Test case 1: sixteen_bit = 52428, four_bit = 0 (from your screenshot)
        sixteen_bit, four_bit = 52428, 0
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, 52428)

        # Test case 2: sixteen_bit = 65535, four_bit = 15 (max values)
        sixteen_bit, four_bit = 65535, 15
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, 1048575)  # 11111111111111111111

        # Test case 3:
        sixteen_bit, four_bit = 32000, 4
        combined = combine_to_20bit(sixteen_bit, four_bit)
        self.assertEqual(combined, 294144)
        

    def test_combine_24bit(self): ## TODO - muuta tää 24 bit versioon
        # Test case 1: 
        sixteen_bit, eight_bit = 52428, 0
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, 52428)

        # Test case 2: (max values)
        sixteen_bit, eight_bit = 65535, 255
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, 16777215)

        # Test case 3:
        sixteen_bit, eight_bit = 32000, 33
        combined = combine_to_24bit(sixteen_bit, eight_bit)
        self.assertEqual(combined, 2194688)

    def test_combine_12_4bit(self):
        # Test case 1: whole_num = 70, four_bit = 0 (from your screenshot)
        whole_num, four_bit = 70, 0
        combined = combine_12_4bit(whole_num, four_bit)
        self.assertEqual(combined, 1120)  # 70 << 4 = 1120

        # Test case 2: Max values
        whole_num, four_bit = 4095, 15
        combined = combine_12_4bit(whole_num, four_bit)
        self.assertEqual(combined, 65535)  # 1111111111111111

        # Test case 3:
        whole_num, four_bit = 2000, 4
        combined = combine_12_4bit(whole_num, four_bit)
        self.assertEqual(combined, 32004)

    def test_combine_8_8bit(self):
        # Test case 1: whole_num = 1, eight_bit = 127
        whole_num, eight_bit = 1, 127
        combined = combine_8_8bit(whole_num, eight_bit)
        self.assertEqual(combined, 383)

        # Test case 2: Max values
        whole_num, eight_bit = 255, 255
        combined = combine_8_8bit(whole_num, eight_bit)
        self.assertEqual(combined, 65535)

    def test_convert_vel_rpm_revs(self):
        # Test case 1: 
        expected_result = (256, 0)
        result = convert_vel_rpm_revs(60)
        self.assertTupleEqual(expected_result, result)
        self.assertEqual(result[0], 256)  
        self.assertEqual(result[1], 0)    

        # Test case 2: 
        expected_result = (512, 0)
        result = convert_vel_rpm_revs(120)
        self.assertTupleEqual(expected_result, result)
        self.assertEqual(result[0], 512) 
        self.assertEqual(result[1], 0)

        # Test case 3: 
        expected_result = (106, 43690)
        result = convert_vel_rpm_revs(25)
        self.assertTupleEqual(expected_result, result)
        self.assertEqual(result[0], 106) 
        self.assertEqual(result[1], 43690)

        # Test case 4: 
        expected_result = (354, 8737)
        result = convert_vel_rpm_revs(83)
        self.assertTupleEqual(expected_result, result)
        self.assertEqual(result[0], 354) 
        self.assertEqual(result[1], 8737)        

        # Test case 5: 
        self.assertIsNone(split_20bit_to_components(-0.1))
        self.assertIsNone(split_20bit_to_components(300))


    def test_convert_acc_rpm_revs(self):
        # Test case 1: 
        expected_result = (16, 0)
        result = convert_acc_rpm_revs(60)
        self.assertEqual(result[0], 16) 
        self.assertEqual(result[1], 0)

        # Test case 2: 
        expected_result = (32, 0)
        result = convert_acc_rpm_revs(120)
        self.assertEqual(result[0], 32) 
        self.assertEqual(result[1], 0)

        # Test case 3: 
        expected_result = (7, 65535)
        result = convert_acc_rpm_revs(30)
        self.assertEqual(result[0], 7) 
        self.assertEqual(result[1], 65535)

        # Test case 4: 
        expected_result = (41, 21844)
        result = convert_acc_rpm_revs(155)
        self.assertEqual(result[0], 41) 
        self.assertEqual(result[1], 21844)

        # Test case 5: 
        self.assertIsNone(split_20bit_to_components(-0.1))
        self.assertIsNone(split_20bit_to_components(300))

if __name__ == '__main__':
    unittest.main()
def test_function():
    pass
    
def shift_bits(number, shift_bit_amount):
        number = number & 0xffff
        result = number >> shift_bit_amount
        return result

test_function()

resolution = 0.00000095367431640625

x = 1.0/resolution
print(f"Resolution: {x}")

shifted_bits = shift_bits(1048576, 4)
print(f"shifted bits: {shifted_bits}")


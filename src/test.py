def shift_bits(number, shift_bit_amount):
        number = number & 0xffff
        result = number >> shift_bit_amount
        return result

def test_function():
    # Test case 1: Your example with 5 (0000000000000101 in 16-bit)
    print(f"Input: 5 (binary: {bin(5)[2:].zfill(16)})")
    result = extract_12bit(5)
    print(f"Output: {result} (binary: {bin(result)[2:].zfill(16)})")
    
    # Test case 2: A larger number
    test_num = 0b1010101010101010  # 16-bit number
    test_num2 = 0b1111111111110000  # 16-bit number
    print(f"\nInput: {test_num2} (binary: {bin(test_num2)[2:].zfill(16)})")
    result = extract_12bit(test_num2)
    print(f"Output: {result} (binary: {bin(result)[2:].zfill(16)})")

test_function()
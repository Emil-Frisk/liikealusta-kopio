FAULT_RESET_BIT = 15
ENABLE_MAINTAINED_BIT = 1
ALTERNATE_MODE_BIT = 7
UVEL32_RESOLUTION = 0.000000059604644775390625
UACC32_RESOLUTION = 0.00000095367431640625

def is_nth_bit_on(n, number):
            mask = 1 << n
            return (number & mask) != 0

# Only allows the needed bits
def IEG_MODE_bitmask_default(number):
        mask = (1 << FAULT_RESET_BIT) | (1 << ENABLE_MAINTAINED_BIT)
        number = number & 0xFFFF
        return number & mask

def IEG_MODE_bitmask_alternative(number):
        mask = (1 << FAULT_RESET_BIT) | (1 << ALTERNATE_MODE_BIT) |(1 << ENABLE_MAINTAINED_BIT) 
        number = number & 0xFFFF
        return number & mask

def IEG_MODE_bitmask_enable(number):
        mask = (1 << ENABLE_MAINTAINED_BIT)
        number = number & 0xFFFF
        return number & mask

# UVEL32 8.8 | UACC 12.4 | UCUR 9.7
def shift_bits(number, shift_bit_amount):
        number = number & 0xffff
        result = number >> shift_bit_amount
        return result

def split_24bit_to_components(value):
    """
    Splits a number between 0 and 1 into two parts: a 16-bit piece and an 8-bit piece.

    This function takes a float (between 0 and 1) and imagines it as a 24-bit number 
    (like a big binary counter with 24 slots). It then splits that into:
    - A 16-bit part (the lower 16 bits, or the smaller details).
    - An 8-bit part (the upper 8 bits, or the bigger chunks).
    These two parts together make up the original 24-bit value.

    Args:
        value (float): A number between 0 and 1 (inclusive). 
                       Anything outside this range returns None.

    Returns:
        tuple: (sixteen_bit, eight_bit) where:
               - sixteen_bit (int): The lower 16 bits (0-65535).
               - eight_bit (int): The upper 8 bits (0-255).
        None: If the input is less than 0 or greater than 1.

   Notes:
        - UVEL32_RESOLUTION = 1 / (2^24 - 1) ensures the full 24-bit range (0 to 
          16,777,215) maps to 0-1. So, value * (1 / resolution) gives the 24-bit 
          integer, and the function splits that into 16-bit and 8-bit chunks.
        - Input is capped at 0-1 because it represents a fraction of the max 
          24-bit value (16,777,215).

    """
    # Check if input is valid (between 0 and 1)
    if value < 0 or value > 1:
        return None

    # Scale the float to a 24-bit integer using a resolution constant
    scaled_value = int(value / UVEL32_RESOLUTION)

    # Keep only the lowest 24 bits (mask with 0xFFFFFF, which is 16777215)
    scaled_value = scaled_value & 0xFFFFFF

    # Grab the top 8 bits (shift right 16 positions, mask with 0xFF for 8 bits)
    eight_bit = (scaled_value >> 16) & 0xFF

    # Grab the bottom 16 bits (mask with 0xFFFF for 16 bits)
    sixteen_bit = scaled_value & 0xFFFF

    # Return the two parts as a tuple
    return sixteen_bit, eight_bit

def split_20bit_to_components(value):
    """
    Read split_24bit_to_components funktion for details
    """
    if value < 0 or value > 1:
           return None
    
    scaled_value = int(value / UACC32_RESOLUTION)
    
    scaled_value = scaled_value & 0xFFFFF # 20 bits 

    # Extract 4-bit high part (bits 16-19)
    four_bit = (scaled_value >> 16) & 0x0F
    # Extract 16-bit low part (bits 0-15)
    sixteen_bit = scaled_value & 0xFFFF
    
    return sixteen_bit, four_bit

def combine_to_24bit(sixteen_bit, eight_bit):
    # Ensure inputs are within their bit limits
    sixteen_bit = sixteen_bit & 0xFFFF
    eight_bit = eight_bit & 0xFF      
    
    # Shift the 8-bit number 16 positions left and OR it with the 16-bit number
    result = (eight_bit << 16) | sixteen_bit
    
    return result

def combine_to_20bit(sixteen_bit, four_bit):
    # Ensure inputs are within their bit limits
    sixteen_bit = sixteen_bit & 0xFFFF
    four_bit = four_bit & 0x0F 
    
    # Shift the 4-bit number 16 positions left and OR it with the 16-bit number
    result = (four_bit << 16) | sixteen_bit
    
    return result

def combine_8_8bit(whole, decimal):
       # 16 bit limit
       whole << 8
       sixteen_bit = whole | decimal
       sixteen_bit = sixteen_bit & 0xFFFF
       return sixteen_bit
       


sixteen_bit, eight_bit = split_24bit_to_components(0.9)

print(f"sixteen-bit: {sixteen_bit}\neight-bit: {eight_bit}")
whole_number_bit = 1 << 8

result = combine_8_8bit(1, eight_bit)

print(f"result(bin) : {bin(result)}")
print(f"result : {result}")


FAULT_RESET_BIT = 15
ENABLE_MAINTAINED_BIT = 1
ALTERNATE_MODE_BIT = 7

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
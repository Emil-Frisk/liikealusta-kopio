# import time

UPOS16_MAX = 65535
decimal = 32000 / UPOS16_MAX

whole_num = 3

moi = whole_num + decimal

def IEG_MODE_bitmask_default(number):
        mask = (1 << 15) | (1 << 1)
        number = number & 0xFFFF
        return number & mask

def IEG_MODE_bitmask_alternative(number):
        mask = (1 << 15) | (1 << 7) |(1 << 1) 
        number = number & 0xFFFF
        return number & mask

def IEG_MODE_bitmask_enable(number):
        mask = (1 << 1)
        number = number & 0xFFFF
        return number & mask

test = IEG_MODE_bitmask_enable(3)
test2 = IEG_MODE_bitmask_alternative(65535)
test3 = IEG_MODE_bitmask_default(65535)


print(bin(test))
print(bin(test2))
print(bin(test3))

# print(moi)
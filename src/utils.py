def is_nth_bit_on(n, number):
            mask = 1 << n
            return (number & mask) != 0
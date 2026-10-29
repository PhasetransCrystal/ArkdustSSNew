import random
import sys

# Use `pip install pyperclip` to enable auto copy result. Optional.
try:
    import pyperclip
    FLAG = True
except ImportError:
    FLAG = False


# Use cmd: python masc_gen.py length to generate

BLOCKS = "███████▓▓▓▓▓▒▒▒▒░▀▄■▃▅▆▇▍▋▊▉▗▘▝▙▚▛▜▞▟"

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else int(input("please input count:"))
    rst = "".join(random.choice(BLOCKS) for _ in range(n))
    print(rst)
    if FLAG:
        pyperclip.copy(rst)
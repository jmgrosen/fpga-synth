import os
from functools import reduce
from nmigen import *
from nmigen_boards.arty_s7 import ArtyS7_50Platform
from nmigen_boards.ulx3s import ULX3S_85F_Platform
from nmigen_stdio.serial import AsyncSerialTX

PLATFORM = os.environ.get('SYNTH_PLATFORM', None)
if PLATFORM not in {'ArtyS7', 'ULX3S'}:
    raise ValueError(f"{PLATFORM!r} is an unsupported SYNTH_PLATFORM")

SAMPLE_WIDTH = 16
PCM_WIDTH = 8
SAMPLE_FREQ = 50000  # 44100
if PLATFORM == 'ArtyS7':
    BCLK = 100000000  # 100 MHz
elif PLATFORM == 'ULX3S':
    BCLK = 25000000  # 25 MHz
BAUDRATE = 1000000  # 1 Mbaud

class SynthesizerSource(Elaboratable):
    def __init__(self):
        super().__init__()
        self.ack = Signal()
        self.sample = Signal(SAMPLE_WIDTH)
        self.rdy = Signal()

class SquareWave(SynthesizerSource):
    def __init__(self, freq):
        super().__init__()
        self.period = round(SAMPLE_FREQ / freq)
        self.current = Signal(range(self.period))

    def elaborate(self, platform):
        m = Module()

        with m.FSM():
            with m.State("COMPUTE"):
                with m.If(self.current > self.period // 2):
                    m.d.sync += self.sample.eq((2 ** SAMPLE_WIDTH) - 1)
                with m.Else():
                    m.d.sync += self.sample.eq(0)

                m.d.sync += self.current.eq(self.current + 1)
                with m.If(self.current == self.period):
                    m.d.sync += self.current.eq(0)

                m.next = "WAITING"

            with m.State("READY"):
                with m.If(self.ack):
                    m.d.sync += self.rdy.eq(0)
                    m.next = "COMPUTE"

            with m.State("WAITING"):
                with m.If(~self.ack):
                    m.d.sync += self.rdy.eq(1)
                    m.next = "READY"

        return m

class TriangleWave(SynthesizerSource):
    def __init__(self, freq):
        super().__init__()
        self.period = round(SAMPLE_FREQ / freq)
        self.current = Signal(range(self.period))

    def elaborate(self, platform):
        m = Module()

        with m.FSM():
            with m.State("COMPUTE"):
                target = (((2 ** SAMPLE_WIDTH) - 1) * self.current) // (self.period // 2)
                with m.If(self.current > self.period // 2):
                    m.d.sync += self.sample.eq(target)
                with m.Else():
                    m.d.sync += self.sample.eq(((2 ** SAMPLE_WIDTH) - 1) - (target - ((2 ** SAMPLE_WIDTH) - 1)))

                m.d.sync += self.current.eq(self.current + 1)
                with m.If(self.current == self.period):
                    m.d.sync += self.current.eq(0)

                m.next = "WAITING"

            with m.State("READY"):
                with m.If(self.ack):
                    m.d.sync += self.rdy.eq(0)
                    m.next = "COMPUTE"

            with m.State("WAITING"):
                with m.If(~self.ack):
                    m.d.sync += self.rdy.eq(1)
                    m.next = "READY"

        return m

def gen_sin_lut(n):
    return [math.sin((i / n) * (math.pi / 2)) for i in range(n)]

# class Sine(Elaboratable):
#     def __init__(self, in_width, out_width=SAMPLE_WIDTH, lut_width=10):
#         super().__init__()
#         self.i = Signal(in_width)
#         self.ack = Signal()
#         self.o = Signal(signed(out_width))
#         self.rdy = Signal()
#         self.lut_width = lut_width
# 
#     def elaborate(self, platform):
#         m = Module()
# 
#         lut = Array([Const(math.round(x * (2**(self.o.width-1) - 1)), unsigned(self.o.width-1))
#                      for x in gen_sin_lut(2**self.lut_width)])
# 
#         with m.FSM():
#             with m.State("COMPUTE"):
#                 # TODO actually think about phase when i'm not sleepy
#                 flip_input = self.i[-2]
#                 negate_output = self.i[-1]
#                 unphased = self.i[:-2] # assume we're in the first of the four phases
#                 almost_out = Signal(unsigned(self.o.width-1))
#                 # TODO preprocess in certain phases
#                 with m.If(unphased & (2**(unphased.width - self.lut_width) - 1) == 0):
#                     m.d.sync += almost_out.eq(lut[unphased])
#                 with m.Else():
#                     lower_i = unphased[-self.lut_width:]
#                     upper_i = lower_i + 1
#                     lower = lut[lower_i]
#                     upper = Mux(lower_i.all(), 2**almost_out.width - 1, lut[upper_i])
#                     adjust = unphased.width - self.lut_width
#                     m.d.sync += almost_out.eq(lower + ((upper - lower) * unphased[:-self.lut_width]) >> adjust)
#                 m.d.comb += self.o.eq(Mux(negate_output, almost_out, -almost_out))
# 
#             with m.State("READY"):
# 
# class SineWave(SynthesizerSource):
#     def __init__(self, freq):
#         super().__init__()
#         self.period = round(SAMPLE_FREQ / freq)
#         self.current = Signal(range(self.period))
# 
#     def elaborate(self, platform):
#         m = Module()
# 
#         with m.FSM():
#             with m.State("COMPUTE"):
#                 target = (((2 ** SAMPLE_WIDTH) - 1) * self.current) // (self.period // 2)
#                 with m.If(self.current > self.period // 2):
#                     m.d.sync += self.sample.eq(target)
#                 with m.Else():
#                     m.d.sync += self.sample.eq(((2 ** SAMPLE_WIDTH) - 1) - (target - ((2 ** SAMPLE_WIDTH) - 1)))
# 
#                 m.d.sync += self.current.eq(self.current + 1)
#                 with m.If(self.current == self.period):
#                     m.d.sync += self.current.eq(0)
# 
#                 m.next = "WAITING"
# 
#             with m.State("READY"):
#                 with m.If(self.ack):
#                     m.d.sync += self.rdy.eq(0)
#                     m.next = "COMPUTE"
# 
#             with m.State("WAITING"):
#                 with m.If(~self.ack):
#                     m.d.sync += self.rdy.eq(1)
#                     m.next = "READY"
# 
#         return m

class Synthesizer(Elaboratable):
    def __init__(self, components):
        super().__init__()
        self.components = components
        self.divider = BCLK // SAMPLE_FREQ

    def elaborate(self, platform):
        m = Module()
        tx = m.submodules.tx = AsyncSerialTX(divisor=BCLK // BAUDRATE, data_bits=PCM_WIDTH)
        m.submodules += self.components
        m.d.comb += platform.request("uart", 0).tx.eq(m.submodules.tx.o)

        sample = Signal(range(len(self.components) * 2 ** SAMPLE_WIDTH))
        counter = Signal(range(self.divider))

        m.d.sync += counter.eq(counter + 1)
        with m.If(counter == self.divider):
            m.d.sync += counter.eq(0)

        with m.FSM():
            with m.State("COMPUTE"):
                with m.If(reduce((lambda t, c: t & c.rdy), self.components, 1)):
                    m.d.sync += sample.eq(sum(c.sample for c in self.components))
                    m.next = "SENDACK"

            with m.State("SENDACK"):
                for c in self.components:
                    m.d.sync += c.ack.eq(1)
                with m.If(tx.rdy):
                    m.d.sync += tx.data.eq((sample // len(self.components)) >> (SAMPLE_WIDTH - PCM_WIDTH))
                    m.d.sync += tx.ack.eq(1)
                    m.next = "IDLE"

            with m.State("IDLE"):
                for c in self.components:
                    m.d.sync += c.ack.eq(0)
                m.d.sync += tx.ack.eq(0)
                with m.If(counter == 0):
                    m.next = "COMPUTE"

        return m

class Blinky(Elaboratable):
    def elaborate(self, platform):
        m = Module()
        counter = Signal(26)
        m.d.sync += counter.eq(counter + 1)
        m.d.comb += platform.request("led", 0).o.eq(counter[-1])
        return m


if __name__ == "__main__":
    synth = Synthesizer([SquareWave(500),
                         SquareWave(600),
                         SquareWave(700),
                         TriangleWave(500),
                         TriangleWave(600),
                         TriangleWave(700)])

    if PLATFORM == "ArtyS7":
        platform = ArtyS7_50Platform()
    elif PLATFORM == "ULX3S":
        platform = ULX3S_85F_Platform()

    platform.build(synth, do_program=True, program_opts=dict(flash=False))

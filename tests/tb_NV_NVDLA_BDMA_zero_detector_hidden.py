import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb.result import TestFailure


CLOCK_PERIOD_NS = 2  # 500 MHz (arbitrary but safe)


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 1
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    await Timer(10, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def send_beat(dut, data):
    """Send one 512-bit beat respecting ready/valid"""
    dut.nvdla_bdma_inp_data_pd.value = data
    dut.nvdla_bdma_inp_data_pvld.value = 1

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def send_block(dut, beats, data_generator):
    """Send a full block of data"""
    for _ in range(beats):
        data = data_generator()
        await send_beat(dut, data)


@cocotb.test()
async def test_all_zero_block(dut):
    """Block with all-zero data should assert blk_is_zero=1"""

    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLOCK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    # Enable zero detector, block size = 16 beats
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0  # 16 beats

    # Send 16 zero beats
    await send_block(dut, 16, lambda: 0)

    # Wait for block result valid
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            break

    assert dut.nvdla_bdma_out_blk_is_zero.value == 1, \
        "Expected block to be detected as ALL ZERO"


@cocotb.test()
async def test_non_zero_block(dut):
    """Block containing a non-zero word should assert blk_is_zero=0"""

    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLOCK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0  # 16 beats

    def data_gen():
        # One non-zero word in the block
        if data_gen.counter == 7:
            val = 0x1
        else:
            val = 0
        data_gen.counter += 1
        return val

    data_gen.counter = 0

    await send_block(dut, 16, data_gen)

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            break

    assert dut.nvdla_bdma_out_blk_is_zero.value == 0, \
        "Expected block to be detected as NON-ZERO"


@cocotb.test()
async def test_bypass_mode(dut):
    """Bypass mode should pass data through and never assert block valid"""

    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLOCK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0  # bypass
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    await send_beat(dut, 0xDEADBEEF)

    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_data_pvld.value == 1
    assert dut.nvdla_bdma_out_data_pd.value == 0xDEADBEEF
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test()
async def test_pass_through_data_integrity(dut):
    """Verify output data matches input data"""

    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLOCK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 1  # 32 beats

    test_value = int("A5" * 64, 16)  # 512-bit pattern

    await send_beat(dut, test_value)
    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_data_pd.value == test_value, \
        "Pass-through data mismatch"


def test_tb_NV_NVDLA_BDMA_zero_detector_runner():
    """Test runner for cocotb-test"""
    # run(
    #     verilog_sources=["sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v"],
    #     toplevel="NV_NVDLA_BDMA_zero_detector",
    #     module="tb_NV_NVDLA_BDMA_zero_detector_hidden",
    #     simulator="icarus",
    #     compile_args=["-g2012", "-I", "sources"],
    # )


    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [
        proj_path / "sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v",
    ]
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        always=True,
    )
    
    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="tb_NV_NVDLA_BDMA_zero_detector_hidden"
    )

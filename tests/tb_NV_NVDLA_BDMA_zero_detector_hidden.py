# test_zero_detector.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
import random

CLK_PERIOD_NS = 10


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    await Timer(50, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def send_beat(dut, value):
    """Send one input beat and wait for acceptance"""
    dut.nvdla_bdma_inp_data_pd.value = value
    dut.nvdla_bdma_inp_data_pvld.value = 1

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def recv_data(dut):
    """Receive one output data beat"""
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            data = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return data


async def recv_zero_meta(dut):
    """Receive one zero-detection result"""
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            z = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return z


@cocotb.test()
async def test_bypass_mode(dut):
    """Bypass mode: data passes through, no metadata"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0

    test_vectors = [0x00, 0x12, 0xFF, 0x01]

    for val in test_vectors:
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Bypass data mismatch: {out} != {val}"

        # Metadata must never assert in bypass
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    cocotb.log.info("Bypass mode test PASSED")


@cocotb.test()
async def test_enabled_basic(dut):
    """Enabled mode: check zero detection correctness"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    test_vectors = [
        0x00,
        0x01,
        0x00,
        0xA5,
        0x00,
    ]

    expected_zero = [1, 0, 1, 0, 1]

    for val, exp_z in zip(test_vectors, expected_zero):
        await send_beat(dut, val)

        out_data = await recv_data(dut)
        out_z = await recv_zero_meta(dut)

        assert out_data == val, "Data mismatch"
        assert out_z == exp_z, f"Zero detect mismatch for {val:#x}"

    cocotb.log.info("Enabled basic zero-detect test PASSED")


@cocotb.test()
async def test_backpressure(dut):
    """Independent backpressure on data and metadata"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    values = [0x00, 0x11, 0x00, 0x22]

    for val in values:
        await send_beat(dut, val)

        # Randomly stall data or metadata
        stall_data = random.choice([True, False])
        stall_meta = random.choice([True, False])

        if not stall_data:
            data = await recv_data(dut)
            assert data == val

        if not stall_meta:
            z = await recv_zero_meta(dut)
            assert z == (1 if val == 0 else 0)

        # Eventually accept both
        if stall_data:
            data = await recv_data(dut)
            assert data == val

        if stall_meta:
            z = await recv_zero_meta(dut)
            assert z == (1 if val == 0 else 0)

    cocotb.log.info("Backpressure test PASSED")


@cocotb.test()
async def test_disable_clears_state(dut):
    """Disabling clears pending metadata"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await send_beat(dut, 0x00)

    # Disable before accepting metadata
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    cocotb.log.info("Disable-clears-state test PASSED")


# ✅ REQUIRED: Pytest wrapper function
def test_tb_NV_NVDLA_BDMA_zero_detector_runner():
    """Pytest wrapper for cocotb testbench"""
    import os
    from pathlib import Path
    
    # Ensure Python encoding is set for Windows PowerShell compatibility
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Try to import runner from cocotb_tools (Cocotb 1.8+)
    try:
        from cocotb_tools.runner import get_runner
    except ImportError:
        # Fallback for older Cocotb versions
        try:
            from cocotb.runner import get_runner
        except ImportError:
            raise ImportError(
                "Could not import get_runner from cocotb_tools.runner or cocotb.runner.\n"
                "Please install cocotb-tools: pip install cocotb-tools\n"
                "Or ensure you have Cocotb 1.8+ installed: pip install cocotb"
            )
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    # 8-bit interface version
    sources = [
        proj_path / "sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v",
    ]
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        always=True,
        timescale=("1ns", "1ns"),
    )
    
    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="tb_NV_NVDLA_BDMA_zero_detector_hidden"
    )


if __name__ == "__main__":
    # For standalone execution
    test_tb_NV_NVDLA_BDMA_zero_detector_runner()
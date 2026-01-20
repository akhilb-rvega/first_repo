# -*- coding: utf-8 -*-
# test_zero_detector.py
import sys
import cocotb
from cocotb.clock import Clock
import random
import os
from pathlib import Path
from collections import deque
from cocotb_tools.runner import get_runner
from cocotb.triggers import RisingEdge, Timer
import glob
from cocotb_test.simulator import run


# Set UTF-8 encoding for Python I/O operations
os.environ["PYTHONIOENCODING"] = "utf-8"

# Reconfigure stdout/stderr to use UTF-8 encoding (especially important on Windows)
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')


CLK_PERIOD_NS = 10


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await Timer(50, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def send_input(dut, data):
    dut.nvdla_bdma_inp_data_pd.value = data
    dut.nvdla_bdma_inp_data_pvld.value = 1

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def accept_output(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            data = int(dut.nvdla_bdma_out_data_pd.value)
            break
    dut.nvdla_bdma_out_data_prdy.value = 0
    return data


async def accept_zero_flag(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            flag = int(dut.nvdla_bdma_out_blk_is_zero.value)
            break
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    return flag


@cocotb.test()
async def test_zero_detector(dut):
    """Main test: runs multiple sub-tests"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    # ------------------------------------------------------------
    # Test case 1: Single zero byte
    # ------------------------------------------------------------
    await send_input(dut, 0x00)
    out = await accept_output(dut)
    flag = await accept_zero_flag(dut)

    assert out == 0x00, "Data mismatch for zero input"
    assert flag == 1, "Zero not detected"

    # ------------------------------------------------------------
    # Test case 2: Single non-zero byte
    # ------------------------------------------------------------
    await send_input(dut, 0xAB)
    out = await accept_output(dut)
    flag = await accept_zero_flag(dut)

    assert out == 0xAB, "Data mismatch"
    assert flag == 0, "False zero detection"

    # ------------------------------------------------------------
    # Test case 3: Enable = 0 (zero flag must not assert)
    # ------------------------------------------------------------
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await send_input(dut, 0x00)
    out = await accept_output(dut)

    await RisingEdge(dut.nvdla_core_clk)
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, \
        "Zero flag asserted when disabled"

    # ------------------------------------------------------------
    # Test case 4: Re-enable and send non-zero
    # ------------------------------------------------------------
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await send_input(dut, 0x55)
    out = await accept_output(dut)
    flag = await accept_zero_flag(dut)
    assert flag == 0

    # ------------------------------------------------------------
    # Test case 5: Backpressure on output data
    # ------------------------------------------------------------
    await send_input(dut, 0x00)
    await Timer(50, units="ns")
    dut.nvdla_bdma_out_data_prdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    out = int(dut.nvdla_bdma_out_data_pd.value)
    flag = await accept_zero_flag(dut)
    assert out == 0x00 and flag == 1

    # ------------------------------------------------------------
    # Test case 6: Backpressure on zero flag
    # ------------------------------------------------------------
    await send_input(dut, 0x22)
    out = await accept_output(dut)
    await Timer(50, units="ns")
    flag = await accept_zero_flag(dut)
    assert flag == 0

    # ------------------------------------------------------------
    # Test case 7: Max value (0xFF)
    # ------------------------------------------------------------
    await send_input(dut, 0xFF)
    out = await accept_output(dut)
    flag = await accept_zero_flag(dut)
    assert out == 0xFF and flag == 0

    # ------------------------------------------------------------
    # Test case 8: Random data
    # ------------------------------------------------------------
    for _ in range(3):
        val = random.randint(0, 255)
        await send_input(dut, val)
        out = await accept_output(dut)
        flag = await accept_zero_flag(dut)
        assert out == val
        assert flag == (1 if val == 0 else 0)

    # ------------------------------------------------------------
    # Test case 9: Rapid back-to-back inputs
    # ------------------------------------------------------------
    for val in [0x00, 0x01, 0x00]:
        await send_input(dut, val)
        out = await accept_output(dut)
        flag = await accept_zero_flag(dut)
        assert flag == (1 if val == 0 else 0)

    # ------------------------------------------------------------
    # Test case 10: Reset during operation
    # ------------------------------------------------------------
    await send_input(dut, 0x00)
    dut.nvdla_core_rstn.value = 0
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    assert dut.nvdla_bdma_out_data_pvld.value == 0


def test_NV_NVDLA_BDMA_zero_detector_hidden():
    """Pytest-compatible cocotb test runner using cocotb_tools.runner"""
    sim = os.getenv("SIM", "icarus")
    proj_dir = Path(__file__).resolve().parent.parent
    rtl_dir = proj_dir / "sources" / "vmod" / "nvdla" / "bdma"
    vlibs_dir = proj_dir / "sources" / "vmod" / "vlibs"
    rams_model_dir = proj_dir / "sources" / "vmod" / "rams" / "model"
    rams_synth_dir = proj_dir / "sources" / "vmod" / "rams" / "synth"
    include_dir = proj_dir / "sources" / "vmod" / "include"
    # ------------------------------------------------------------------
    # Collect sources
    # ------------------------------------------------------------------
    # Exclude duplicate SSYNC modules
    vlibs_sources = sorted([
        str(f) for f in vlibs_dir.glob("*.v")
        if f.name not in ["p_SSYNC3DO.v", "p_SSYNC3DO_S_PPP.v"]
    ])
    rams_model_sources = sorted(str(f) for f in rams_model_dir.glob("*.v"))
    rams_synth_sources = sorted(str(f) for f in rams_synth_dir.glob("*.v"))
    # Exclude patterns for RTL sources
    EXCLUDE_PATTERNS = ["sram_stub", "simple_tb_assembly_buffer", "nv_ram_sim_models", "ram_stubs"]
    rtl_sources = sorted(
        str(f) for f in rtl_dir.glob("*.v")
        if not any(p in f.name for p in EXCLUDE_PATTERNS)
    )
    verilog_sources = (
        vlibs_sources +
        rams_model_sources +
        rams_synth_sources +
        rtl_sources
    )
    # ------------------------------------------------------------------
    # Runner flow
    # ------------------------------------------------------------------
    runner = get_runner(sim)
    runner.build(
        sources=verilog_sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        includes=[str(include_dir), str(vlibs_dir)],
        defines={
            "SYNTHESIS": 1, # Skip unsupported SV constructs in Icarus
        },
        build_args=["-g2012"],
        always=True,
    )
    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="test_NV_NVDLA_BDMA_zero_detector_hidden",
    )

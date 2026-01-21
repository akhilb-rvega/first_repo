# -*- coding: utf-8 -*-
# test_NV_NVDLA_BDMA_zero_detector_hidden.py

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, with_timeout
from cocotb.triggers import SimTimeoutError
from cocotb_tools.runner import get_runner

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
CLK_PERIOD_NS = 10
PER_TEST_TIMEOUT_NS = 120_000
MAX_WAIT_CYCLES = 50

# -----------------------------------------------------------------------------
# Hard per-test timeout wrapper
# -----------------------------------------------------------------------------
async def run_with_timeout(coro, name, timeout_ns=PER_TEST_TIMEOUT_NS):
    try:
        await with_timeout(coro, timeout_ns, "ns")
    except Exception as e:
        raise SimTimeoutError(f"[TIMEOUT] {name} exceeded {timeout_ns} ns") from e

# -----------------------------------------------------------------------------
# Helpers (all bounded waits)
# -----------------------------------------------------------------------------
async def start_clock(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())

async def reset_dut(dut, clock_running=True):
    if not clock_running:
        dut.nvdla_core_clk.value = 0

    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0

    await Timer(50, "ns")

    dut.nvdla_core_rstn.value = 1
    if clock_running:
        await RisingEdge(dut.nvdla_core_clk)

async def send_input(dut, val):
    dut.nvdla_bdma_inp_data_pd.value = val
    dut.nvdla_bdma_inp_data_pvld.value = 1

    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            dut.nvdla_bdma_inp_data_pvld.value = 0
            return
    raise SimTimeoutError("inp_data_prdy never asserted")

async def recv_output(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            val = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return val
    raise SimTimeoutError("out_data_pvld never asserted")

async def recv_zero_flag(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            val = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return val
    raise SimTimeoutError("zero_flag_vld never asserted")

# -----------------------------------------------------------------------------
# TESTS 
# -----------------------------------------------------------------------------

@cocotb.test()
async def test_basic_zero(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0x00)
        assert await recv_output(dut) == 0x00
        assert await recv_zero_flag(dut) == 1
    await run_with_timeout(body(), "test_basic_zero")

@cocotb.test()
async def test_basic_nonzero(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0xA5)
        assert await recv_output(dut) == 0xA5
        assert await recv_zero_flag(dut) == 0
    await run_with_timeout(body(), "test_basic_nonzero")

@cocotb.test()
async def test_enable_after_valid(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        await send_input(dut, 0x00)  # before enable
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await recv_output(dut)
    await run_with_timeout(body(), "test_enable_after_valid")

@cocotb.test()
async def test_no_clock_during_reset(dut):
    async def body():
        await reset_dut(dut, clock_running=False)
        await start_clock(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0x01)
        await recv_output(dut)
    await run_with_timeout(body(), "test_no_clock_during_reset")

@cocotb.test()
async def test_output_backpressure_first(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_data_prdy.value = 0
        await send_input(dut, 0x00)
        await Timer(30, "ns")
        assert await recv_output(dut) == 0x00
    await run_with_timeout(body(), "test_output_backpressure_first")

@cocotb.test()
async def test_zero_flag_backpressure_only(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
        await send_input(dut, 0x00)
        await recv_output(dut)
        await Timer(20, "ns")
        assert await recv_zero_flag(dut) == 1
    await run_with_timeout(body(), "test_zero_flag_backpressure_only")

@cocotb.test()
async def test_reset_mid_transaction(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0x00)
        dut.nvdla_core_rstn.value = 0
        await Timer(20, "ns")
        dut.nvdla_core_rstn.value = 1
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 0
    await run_with_timeout(body(), "test_reset_mid_transaction")

@cocotb.test()
async def test_multiple_sequential_inputs(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        for v in [0, 1, 0, 2]:
            await send_input(dut, v)
            assert await recv_output(dut) == v
            assert await recv_zero_flag(dut) == (1 if v == 0 else 0)
    await run_with_timeout(body(), "test_multiple_sequential_inputs")

@cocotb.test()
async def test_randomized_backpressure(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        for _ in range(5):
            dut.nvdla_bdma_out_data_prdy.value = random.randint(0, 1)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = random.randint(0, 1)
            v = random.randint(0, 255)
            await send_input(dut, v)
            await recv_output(dut)
            await recv_zero_flag(dut)
    await run_with_timeout(body(), "test_randomized_backpressure")

@cocotb.test()
async def test_disable_midstream(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0x00)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
        await recv_output(dut)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    await run_with_timeout(body(), "test_disable_midstream")

@cocotb.test()
async def test_max_value(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_input(dut, 0xFF)
        assert await recv_output(dut) == 0xFF
        assert await recv_zero_flag(dut) == 0
    await run_with_timeout(body(), "test_max_value")

@cocotb.test()
async def test_idle_no_activity(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        await Timer(200, "ns")
        assert dut.nvdla_bdma_out_data_pvld.value == 0
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    await run_with_timeout(body(), "test_idle_no_activity")


# ---------------------------------------------------------------------
# Pytest-compatible runner
# ---------------------------------------------------------------------
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

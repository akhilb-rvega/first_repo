# -*- coding: utf-8 -*-
# test_NV_NVDLA_BDMA_zero_detector_hidden.py

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, with_timeout
from cocotb.result import SimTimeoutError
from cocotb_tools.runner import get_runner

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
CLK_PERIOD_NS = 10
PER_TEST_TIMEOUT_NS = 150_000
MAX_WAIT_CYCLES = 50

# -----------------------------------------------------------------------------
# Hard per-test timeout
# -----------------------------------------------------------------------------
async def run_with_timeout(coro, name):
    try:
        await with_timeout(coro, PER_TEST_TIMEOUT_NS, "ns")
    except Exception as e:
        raise SimTimeoutError(f"[TIMEOUT] {name}") from e

# -----------------------------------------------------------------------------
# Helpers (all bounded)
# -----------------------------------------------------------------------------
async def start_clock(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())

async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await Timer(50, "ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)

async def send_beat(dut, val):
    dut.nvdla_bdma_inp_data_pd.value = val
    dut.nvdla_bdma_inp_data_pvld.value = 1
    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            dut.nvdla_bdma_inp_data_pvld.value = 0
            return
    raise SimTimeoutError("send_beat timeout")

async def recv_data(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            v = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return v
    raise SimTimeoutError("recv_data timeout")

async def recv_zero(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    for _ in range(MAX_WAIT_CYCLES):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            v = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return v
    raise SimTimeoutError("recv_zero timeout")

# -----------------------------------------------------------------------------
# BASIC FUNCTIONAL TESTS
# -----------------------------------------------------------------------------

@cocotb.test()
async def test_basic_zero(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_beat(dut, 0x00)
        assert await recv_data(dut) == 0x00
        assert await recv_zero(dut) == 1
    await run_with_timeout(body(), "test_basic_zero")

@cocotb.test()
async def test_basic_nonzero(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_beat(dut, 0xA5)
        assert await recv_data(dut) == 0xA5
        assert await recv_zero(dut) == 0
    await run_with_timeout(body(), "test_basic_nonzero")

@cocotb.test()
async def test_multiple_sequential(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        for v in [0, 1, 0, 2]:
            await send_beat(dut, v)
            assert await recv_data(dut) == v
            assert await recv_zero(dut) == (1 if v == 0 else 0)
    await run_with_timeout(body(), "test_multiple_sequential")

# -----------------------------------------------------------------------------
# ADVERSARIAL / CDC-STYLE CORNER CASES
# -----------------------------------------------------------------------------

@cocotb.test()
async def test_no_metadata_without_data_accept(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_data_prdy.value = 0
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
        await send_beat(dut, 0x00)
        await Timer(40, "ns")
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    await run_with_timeout(body(), "test_no_metadata_without_data_accept")

@cocotb.test()
async def test_metadata_long_backpressure_survival(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
        await send_beat(dut, 0x00)
        await recv_data(dut)
        await Timer(200, "ns")
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1
        assert await recv_zero(dut) == 1
    await run_with_timeout(body(), "test_metadata_long_backpressure_survival")

@cocotb.test()
async def test_disable_flushes_pending_metadata(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
        await send_beat(dut, 0x00)
        await recv_data(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    await run_with_timeout(body(), "test_disable_flushes_pending_metadata")

@cocotb.test()
async def test_metadata_single_shot(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_beat(dut, 0x00)
        await recv_data(dut)
        assert await recv_zero(dut) == 1
        await Timer(100, "ns")
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
    await run_with_timeout(body(), "test_metadata_single_shot")

@cocotb.test()
async def test_data_advances_metadata_stalls(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
        await send_beat(dut, 0x00)
        assert await recv_data(dut) == 0x00
        await send_beat(dut, 0xFF)
        await Timer(30, "ns")
        assert dut.nvdla_bdma_out_data_pvld.value == 0
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
        assert await recv_zero(dut) == 1
    await run_with_timeout(body(), "test_data_advances_metadata_stalls")

@cocotb.test()
async def test_zero_not_combinational(dut):
    async def body():
        await start_clock(dut)
        await reset_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await send_beat(dut, 0x00)
        await recv_data(dut)
        dut.nvdla_bdma_out_data_pd.value = 0xFF
        await RisingEdge(dut.nvdla_core_clk)
        assert await recv_zero(dut) == 1
    await run_with_timeout(body(), "test_zero_not_combinational")


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
